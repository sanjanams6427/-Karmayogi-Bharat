# ============================================================
# GPU-sharded TTS synthesis
#
# Splits ONE language's segments across ALL available GPUs, instead of the
# single GPU any one process is pinned to (pipeline/tts.py DEVICE is a
# module-level constant read from PIPELINE_GPU at import time — one process
# can only ever use one GPU).
#
# Workers are launched as real OS subprocesses (subprocess.Popen with an
# explicit env=), NOT multiprocessing.Pool — see pipeline/tts_shard_worker.py
# for why: a Pool worker on Windows has to import the pipeline package (to
# unpickle its target function) before that function's own body runs, and
# pipeline/__init__.py eagerly imports pipeline.tts, whose DEVICE constant
# is fixed at that import — before a Pool worker function ever gets a
# chance to set PIPELINE_GPU itself. That raced every worker onto cuda:0
# simultaneously (observed directly: every shard OOM'd then hit "illegal
# memory access" on its very first batch). A real subprocess has its
# environment set by the OS before the interpreter even starts, so there is
# no import to race.
#
# WATCHDOG (see docs/TTS_GPU_SHARDING.md): a Parler generation that times
# out leaves its GPU work abandoned (Python cannot kill a thread — see
# docs/PARLER_TIMEOUT_FIX.md). At 1 GPU that was an accepted, bounded cost.
# Running 4 GPUs' worth of shard workers at once was observed to compound
# this badly: a real run hit a 100% timeout rate across all 4 workers
# simultaneously and nvidia-smi itself hung, mirroring the original
# single-GPU driver wedge but system-wide. The watchdog below bounds this:
# each worker reports a heartbeat between small chunks of its bucket: if a
# worker goes quiet for too long, the watchdog kills that OS process
# (a real TerminateProcess actually reclaims its GPU work, unlike an
# abandoned thread inside a still-alive process) and respawns a fresh one,
# which resumes from whatever chunk results the killed worker already
# wrote out — not from scratch. After a small number of respawns without
# progress, that GPU's remaining segments get silence rather than blocking
# the whole job indefinitely.
#
# Known limitation: TerminateProcess can itself fail to take effect on a
# process wedged in an uninterruptible driver call (observed directly
# during the incident that prompted this — two consecutive Stop-Process
# -Force attempts both failed against processes stuck this way). The
# watchdog still respawns in that case; if the old process truly didn't
# die, it and the new one will contend for the same GPU. The respawn cap
# exists specifically so that scenario can't loop forever.
#
# Callers: SegmentEditor.synthesize_all() (always single-language, always
# safe to use every GPU) and DubbingPipeline.dub_video() when explicitly
# told it's the only language in this run (shard_tts_gpus=True) — NEVER
# from inside a dub_course_parallel worker, which is already pinned to one
# GPU for its language bucket; sharding there too would oversubscribe the
# GPUs (N language-workers x M TTS-shard-workers on the same 4 cards).
# ============================================================

import os
import sys
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .logger import get_logger

log = get_logger(__name__)

# Below this many segments, per-worker spawn + model-load overhead (each
# worker loads its own copy of Parler-large) outweighs the parallelism gain —
# just run in-process on the single GPU instead.
MIN_SEGMENTS_FOR_SHARDING = 8

# No heartbeat for this long = worker considered stalled. The worker
# registers a per-generation-attempt heartbeat callback with pipeline.tts
# (see tts_shard_worker.py), so under ANY legitimate workload — including a
# full fallback cascade — beats arrive at least every ~150s (one generation
# deadline + wedge grace). The longest legitimately silent stretch is model
# load at startup (~45-90s, covered by the fresh heartbeat written at spawn).
# 480s of silence therefore means the process is truly wedged, not slow.
# NOTE: this used to be a per-CHUNK heartbeat, and a chunk of long segments
# legitimately exceeded this budget — the watchdog was killing healthy
# workers mid-chunk (observed 2026-09-16: every worker killed at exactly
# 480s three times in a row, all 67 segments ended as silence).
_HEARTBEAT_STALL_BUDGET = 480  # seconds
# Total attempts per bucket = 1 initial + this many respawns, then give up
# on that GPU's remaining segments (silence) rather than retry forever.
_MAX_RESPAWNS = 2
_POLL_INTERVAL = 3  # seconds between watchdog checks

_REPO_ROOT = Path(__file__).parent.parent


def _balanced_buckets(segments: list[dict], n: int) -> list[list[dict]]:
    """Greedy longest-processing-time-first split: place the longest segments
    first, always into the currently lightest bucket. A plain contiguous or
    round-robin split can leave one worker with most of the long/slow
    segments while the others sit idle waiting on it; LPT keeps the buckets'
    estimated workload close to even so no single worker dominates wall time.
    """
    buckets: list[list[dict]] = [[] for _ in range(n)]
    loads = [0] * n
    ordered = sorted(segments, key=lambda s: len(s.get("text", "").split()), reverse=True)
    for seg in ordered:
        i = loads.index(min(loads))
        buckets[i].append(seg)
        loads[i] += max(len(seg.get("text", "").split()), 1)
    return buckets


def _spawn_worker(gpu_id: int, bucket: list[dict], lang: str, output_dir: str,
                  tmp_dir: Path, n_workers: int = 1) -> dict:
    in_path  = tmp_dir / f"in_{gpu_id}.json"
    out_path = tmp_dir / f"out_{gpu_id}.json"
    hb_path  = tmp_dir / f"hb_{gpu_id}.txt"
    in_path.write_text(
        json.dumps({"segments": bucket, "lang": lang, "output_dir": output_dir},
                  ensure_ascii=False),
        encoding="utf-8",
    )
    hb_path.write_text(str(time.time()), encoding="utf-8")  # fresh heartbeat at spawn time
    env = os.environ.copy()
    env["PIPELINE_GPU"] = str(gpu_id)
    # Cap CPU threads per worker. Parler's autoregressive decode is heavily
    # CPU/launch-bound (observed: 15-35% GPU util during healthy sharded
    # generation), and each torch process defaults its intra-op pool to ALL
    # cores — N workers × all-cores oversubscribes the CPU and slows every
    # worker's decode toward its deadline. Split the cores instead.
    threads = max(2, (os.cpu_count() or 8) // max(n_workers, 1))
    env.setdefault("OMP_NUM_THREADS", str(threads))
    env.setdefault("MKL_NUM_THREADS", str(threads))
    proc = subprocess.Popen(
        [sys.executable, "-m", "pipeline.tts_shard_worker",
         str(in_path), str(out_path), str(hb_path)],
        cwd=str(_REPO_ROOT), env=env,
    )
    return {"proc": proc, "in_path": in_path, "out_path": out_path, "hb_path": hb_path}


def _write_silence(path: str, duration: float, sr: int = 44100) -> None:
    import numpy as np
    import soundfile as sf
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    silence = np.zeros(int(max(0.1, duration) * sr), dtype=np.float32)
    sf.write(path, silence, sr, subtype="PCM_16")


def _kill_and_respawn(w: dict, gpu_id: int, lang: str, output_dir: str, tmp_dir: Path) -> None:
    try:
        w["proc"].kill()
        w["proc"].wait(timeout=10)
    except Exception as e:
        # See module docstring — TerminateProcess can itself fail against a
        # truly wedged process. Respawning anyway is still the best
        # available option; the respawn cap bounds the damage if the old
        # process really is still alive and now contending for this GPU.
        log.error(f"[{lang}] GPU {gpu_id} — kill did not confirm ({e}); "
                  f"respawning anyway, old process may still be running")
    w["respawns"] += 1
    log.warning(f"[{lang}] GPU {gpu_id} respawn {w['respawns']}/{_MAX_RESPAWNS}")
    fresh = _spawn_worker(gpu_id, w["bucket"], lang, output_dir, tmp_dir,
                          n_workers=w.get("n_workers", 1))
    w.update(fresh)
    w["start_t"] = time.time()


def synthesize_segments_sharded(segments: list[dict], lang: str, output_dir: str,
                                num_gpus: int | None = None) -> list[dict]:
    """Drop-in replacement for TTSEngine().synthesize_segments() that spreads
    the work across every available GPU instead of just one.

    Falls back to a single in-process TTSEngine call (identical to the
    unsharded path) when there's only 1 GPU or too few segments to justify
    per-worker model-load overhead. Result order always matches the input
    `segments` order, same as the unsharded function.
    """
    import torch
    if num_gpus is None:
        num_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 0
    # Concurrency cap. This box has wedged the display driver twice under
    # sustained 4-way concurrent Parler decode (Sept 2026 incident, and again
    # 2026-09-16 18:14 — system froze, worker logged WEDGED, no TDR event in
    # the Windows log). GPU util was only 6-30% at the time, so this is WDDM/
    # driver contention, not GPU load. 2 concurrent workers has never wedged.
    # Fewer workers also decode FASTER per GPU (less CPU contention), so the
    # throughput cost is well under 2x. Set TTS_SHARD_MAX_GPUS=4 to opt back
    # into full-width sharding (e.g. after a driver clean-reinstall).
    _cap = os.environ.get("TTS_SHARD_MAX_GPUS", "2")
    try:
        num_gpus = min(num_gpus, max(1, int(_cap)))
    except ValueError:
        log.warning(f"TTS_SHARD_MAX_GPUS={_cap!r} is not an int — ignoring")

    if num_gpus <= 1 or len(segments) < MIN_SEGMENTS_FOR_SHARDING:
        from .tts import TTSEngine
        return TTSEngine().synthesize_segments(segments, lang, output_dir)

    n_workers = min(num_gpus, len(segments))
    buckets = [b for b in _balanced_buckets(segments, n_workers) if b]

    log.info(f"[{lang}] Sharding {len(segments)} segments across {len(buckets)} GPU(s):")
    for gpu_id, bucket in enumerate(buckets):
        ids = [s["id"] for s in bucket]
        log.info(f"  GPU {gpu_id}: {len(bucket)} segments, ids={ids}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="tts_shard_"))
    t_start = time.time()
    workers: dict[int, dict] = {}
    try:
        for gpu_id, bucket in enumerate(buckets):
            w = _spawn_worker(gpu_id, bucket, lang, output_dir, tmp_dir,
                              n_workers=len(buckets))
            w.update({"bucket": bucket, "respawns": 0, "done": False,
                      "gave_up": False, "start_t": time.time(),
                      "n_workers": len(buckets)})
            workers[gpu_id] = w

        # ── Watchdog loop ────────────────────────────────────────────────
        while any(not w["done"] and not w["gave_up"] for w in workers.values()):
            time.sleep(_POLL_INTERVAL)
            for gpu_id, w in workers.items():
                if w["done"] or w["gave_up"]:
                    continue
                ret = w["proc"].poll()
                if ret is not None:
                    if ret == 0 and w["out_path"].exists():
                        w["done"] = True
                        w["elapsed"] = time.time() - w["start_t"]
                        log.info(f"[{lang}] GPU {gpu_id} worker finished cleanly")
                    else:
                        log.error(f"[{lang}] GPU {gpu_id} worker exited unexpectedly "
                                  f"(code={ret}) — treating as a stall")
                        if w["respawns"] >= _MAX_RESPAWNS:
                            w["gave_up"] = True
                            log.error(f"[{lang}] GPU {gpu_id} exhausted {_MAX_RESPAWNS} "
                                      f"respawns — giving up on its remaining segments")
                        else:
                            _kill_and_respawn(w, gpu_id, lang, output_dir, tmp_dir)
                    continue
                hb_mtime = w["hb_path"].stat().st_mtime if w["hb_path"].exists() else w["start_t"]
                hb_age = time.time() - hb_mtime
                if hb_age > _HEARTBEAT_STALL_BUDGET:
                    log.error(f"[{lang}] GPU {gpu_id} worker STALLED — no heartbeat for "
                              f"{hb_age:.0f}s (budget {_HEARTBEAT_STALL_BUDGET}s)")
                    if w["respawns"] >= _MAX_RESPAWNS:
                        w["gave_up"] = True
                        log.error(f"[{lang}] GPU {gpu_id} exhausted {_MAX_RESPAWNS} "
                                  f"respawns — giving up on its remaining segments")
                    else:
                        _kill_and_respawn(w, gpu_id, lang, output_dir, tmp_dir)

        # ── Collect results ─────────────────────────────────────────────
        merged_by_id: dict = {}
        gave_up_gpus = []
        per_gpu_summary = []
        for gpu_id, w in workers.items():
            partial = []
            if w["out_path"].exists():
                try:
                    partial = json.loads(w["out_path"].read_text(encoding="utf-8"))
                except Exception:
                    partial = []
            for r in partial:
                merged_by_id[r["id"]] = r
            if w["done"]:
                per_gpu_summary.append((gpu_id, len(partial), w.get("elapsed", 0.0), w["respawns"]))
            if w["gave_up"]:
                gave_up_gpus.append(gpu_id)
                missing_in_bucket = [s for s in w["bucket"] if s["id"] not in merged_by_id]
                for seg in missing_in_bucket:
                    slot = max(0.5, seg.get("end", 0) - seg.get("start", 0))
                    audio_path = str(Path(output_dir) / f"seg_{seg['id']:04d}.wav")
                    _write_silence(audio_path, slot)
                    merged_by_id[seg["id"]] = {**seg, "audio_path": audio_path,
                                               "tts_silent_failure": True}
                log.error(f"[{lang}] GPU {gpu_id} — {len(missing_in_bucket)} segment(s) "
                          f"filled with silence after giving up")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    total_elapsed = time.time() - t_start
    log.info(f"[{lang}] Sharded TTS summary — {len(segments)} segments, "
             f"{len(buckets)} GPU(s), wall time {total_elapsed:.1f}s:")
    for gpu_id, n_done, gpu_elapsed, respawns in per_gpu_summary:
        respawn_note = f", {respawns} respawn(s)" if respawns else ""
        log.info(f"  GPU {gpu_id}: {n_done} segments in {gpu_elapsed:.1f}s "
                 f"({n_done / max(gpu_elapsed, 0.01):.2f} segs/s{respawn_note})")
    if gave_up_gpus:
        log.error(f"[{lang}] GPU(s) that never recovered (silence used): {gave_up_gpus}")

    missing = [seg["id"] for seg in segments if seg["id"] not in merged_by_id]
    if missing:
        # Shouldn't happen — gave_up buckets are backfilled with silence
        # above. Surface loudly rather than silently dropping segments.
        raise RuntimeError(f"[{lang}] Sharded TTS lost {len(missing)} segment(s) "
                           f"(ids={missing[:10]}{'...' if len(missing) > 10 else ''}) "
                           f"with no explanation")

    return [merged_by_id[seg["id"]] for seg in segments]
