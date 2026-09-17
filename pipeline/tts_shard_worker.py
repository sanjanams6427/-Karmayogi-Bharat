# ============================================================
# Standalone TTS shard worker process.
#
# Run as its own OS process (via subprocess.Popen, NOT multiprocessing.Pool)
# with PIPELINE_GPU already set in its environment BEFORE this interpreter
# even starts. This matters: pipeline/__init__.py eagerly imports
# pipeline.tts at package-import time, and pipeline.tts's DEVICE is a
# module-level constant read from PIPELINE_GPU once at import time. A
# multiprocessing.Pool worker has to import the pipeline package (to
# unpickle its target function) before that function's own body ever runs
# — so setting os.environ["PIPELINE_GPU"] inside the worker function is too
# late; DEVICE is already fixed to whatever was in the environment when the
# pool worker's first task got unpickled (in practice: cuda:0 for every
# worker, since none of them had PIPELINE_GPU set yet at that point).
# Launching a real subprocess with env= sidesteps this entirely — the OS
# sets the environment before Python is even loaded, so there is no import
# to race.
#
# Processes its bucket in small chunks rather than one call, writing partial
# results + a heartbeat file after each chunk. This is what lets the parent
# (pipeline/tts_shard.py) run a watchdog: if this process stalls (a Parler
# generation that never returns — the abandoned-thread failure mode
# documented in docs/PARLER_TIMEOUT_FIX.md, which can pile up badly when 4
# GPUs are each doing this at once), the parent kills this process and
# respawns a fresh one. Chunked partial-result writes mean the respawned
# worker resumes from wherever this one got to, instead of starting the
# whole bucket over.
#
# Usage: python -m pipeline.tts_shard_worker <input_json> <output_json> <heartbeat_path>
#   input_json:  {"segments": [...], "lang": "hin", "output_dir": "..."}
#   output_json: overwritten after every chunk with results-so-far; final
#                content on clean exit is the complete bucket result list.
#   heartbeat_path: touched at startup and after every chunk — the parent
#                watches this file's mtime to detect a stalled worker.
# ============================================================
import os
import sys
import json
import time
from pathlib import Path

# Segments per synthesize_segments() call. This is the RESUME granularity:
# partial results are only written after a whole chunk, so a killed worker
# loses at most one chunk of work. 6 was catastrophic in practice — a chunk
# of 6 long segments legitimately takes longer than the parent's stall
# budget, and a worker killed mid-chunk-1 had written nothing, so every
# respawn restarted the full bucket from zero (observed 2026-09-16: three
# 8-minute attempts each restarting at 17/17, then silence for everything).
# Stall detection no longer depends on chunk size at all — the worker
# registers a per-generation-attempt heartbeat callback with pipeline.tts.
_CHUNK_SIZE = 2


def _touch(path: Path) -> None:
    path.write_text(str(time.time()), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: python -m pipeline.tts_shard_worker <input_json> <output_json> <heartbeat_path>",
              file=sys.stderr)
        return 2
    in_path, out_path, hb_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    data = json.loads(in_path.read_text(encoding="utf-8"))

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from pipeline.logger import get_logger
    from pipeline import tts as tts_mod  # noqa: E402 — must come after PIPELINE_GPU is set (by the parent's env=)
    from pipeline.tts import TTSEngine

    # Heartbeat after EVERY generation attempt (Parler batch/single, VITS
    # chunk, MMS segment) — not just per chunk. The parent's watchdog can
    # then use a stall budget that means "no generation attempt finished in
    # N seconds" (a real wedge) instead of "one chunk took longer than N"
    # (which killed healthy workers mid-chunk).
    tts_mod.set_heartbeat_callback(lambda: _touch(hb_path))

    log = get_logger("pipeline.tts_shard_worker")
    gpu_id = os.environ.get("PIPELINE_GPU", "?")
    lang = data["lang"]
    output_dir = data["output_dir"]
    segments = data["segments"]

    # Resume support: a respawned worker gets the SAME out_path. Whatever
    # results are already sitting there are from a prior attempt this
    # process is continuing — skip those ids instead of redoing them.
    done_results: list = []
    if out_path.exists():
        try:
            done_results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            done_results = []
    done_ids = {r["id"] for r in done_results}
    remaining = [s for s in segments if s["id"] not in done_ids]

    _touch(hb_path)  # alive signal before model load even starts
    log.info(f"[GPU {gpu_id}][{lang}] shard start — {len(remaining)}/{len(segments)} "
             f"segments remaining, ids={[s['id'] for s in remaining]}")

    t0 = time.time()
    engine = TTSEngine()
    all_results = list(done_results)
    n_chunks = (len(remaining) + _CHUNK_SIZE - 1) // _CHUNK_SIZE
    for ci in range(0, len(remaining), _CHUNK_SIZE):
        chunk = remaining[ci:ci + _CHUNK_SIZE]
        chunk_results = engine.synthesize_segments(chunk, lang, output_dir)
        all_results.extend(chunk_results)
        out_path.write_text(json.dumps(all_results, ensure_ascii=False), encoding="utf-8")
        _touch(hb_path)
        log.info(f"[GPU {gpu_id}][{lang}] chunk {ci // _CHUNK_SIZE + 1}/{n_chunks} done "
                 f"({len(all_results)}/{len(segments)} total)")
        if engine.wedged:
            # A generate() call never returned even past its deadline + grace:
            # a thread of THIS process is stuck in a driver call, holding GPU
            # work only process death can reclaim. Results so far are written —
            # exit nonzero so the parent respawns a fresh process that resumes
            # from them, instead of continuing to synthesize in a compromised
            # process (which is how one wedge used to poison a whole bucket).
            log.error(f"[GPU {gpu_id}][{lang}] engine WEDGED — exiting after "
                      f"{len(all_results)}/{len(segments)} segments for a fresh respawn")
            return 3

    elapsed = time.time() - t0
    n_silent = sum(1 for r in all_results if r.get("tts_silent_failure"))
    log.info(f"[GPU {gpu_id}][{lang}] shard done — {len(all_results)}/{len(segments)} segments "
             f"in {elapsed:.1f}s ({n_silent} silent-failure)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
