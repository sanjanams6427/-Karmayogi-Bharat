# TTS GPU Sharding — using all 4 GPUs for a single language

> **UPDATED (2026-09-16):** the per-chunk heartbeat described below killed
> healthy workers: one 6-segment chunk of long segments legitimately exceeds
> the 480s stall budget, and partial results were only written per chunk, so
> every respawn restarted its bucket from zero — observed: all 4 workers
> killed at exactly 480s three times in a row, all 67 segments silenced.
> Now: the worker registers a heartbeat callback with pipeline.tts that fires
> after EVERY generation attempt (Parler batch/single, VITS chunk, MMS
> segment), chunk size is 2 (resume granularity), workers get capped
> OMP/MKL_NUM_THREADS (cores ÷ workers — decode was CPU-bound at 15-35% GPU
> util with 4 uncapped workers), and Parler timeouts stop cleanly in-loop via
> max_time (see PARLER_TIMEOUT_FIX.md header note), so one overrun no longer
> cascades into a 100% timeout storm.

**Problem:** `pipeline/tts.py`'s `DEVICE` is a module-level constant read from
`PIPELINE_GPU` once at import time — one process can only ever use one GPU.
The existing multi-GPU code (`dub_course_parallel`) only parallelizes across
*different target languages* (one language per GPU-pinned worker process).
A single-language job — including the segment editor, which is always
single-language — always ran on exactly 1 of 4 GPUs, no matter how many
were free. Measured on this machine: TTS is 88-92% of total dub time, so
this was the single biggest lever available for speed.

## What was built

`pipeline/tts_shard.py` — `synthesize_segments_sharded(segments, lang,
output_dir, num_gpus=None)`. Drop-in replacement for
`TTSEngine().synthesize_segments()` that:

1. Splits `segments` into N buckets (N = `torch.cuda.device_count()`,
   capped at segment count) using a greedy longest-processing-time-first
   assignment (`_balanced_buckets`) — sorts by word count descending,
   always adds the next segment to the currently lightest bucket. Keeps
   worker wall-time close to even; a plain contiguous/round-robin split can
   leave one worker holding most of the long/slow segments while the rest
   finish early and sit idle.
2. Spawns one worker per bucket via `multiprocessing.get_context("spawn")`,
   each with its own `PIPELINE_GPU` env var set **before** `pipeline.tts` is
   ever imported in that process — identical requirement and pattern to
   `dubbing_pipeline._worker_dub_langs` (the existing per-language workers).
3. Each worker loads its own `TTSEngine()` and calls the unmodified
   `synthesize_segments()` on its bucket — same batching, same long-segment
   split, same MMS fallback as before. Nothing about single-segment TTS
   behavior changed, only how the segment list gets divided across GPUs.
4. Merges results back by segment `id` into the original input order —
   downstream code (audio assembly) depends on order matching the input.
5. Falls back to the original single-GPU, in-process call when there's only
   1 GPU or fewer than `MIN_SEGMENTS_FOR_SHARDING = 8` segments (below that,
   the per-worker model-load cost isn't worth it).

## Where it's wired in

- **`SegmentEditor.synthesize_all()`** (`pipeline/segment_editor.py`) — always
  uses it. A segment-editor session is always a single language, so there is
  never a competing multi-language worker already using the other GPUs.
  Unconditionally safe.
- **`DubbingPipeline.dub_video()`** (`pipeline/dubbing_pipeline.py`) — gained
  a `shard_tts_gpus: bool = False` parameter. When `True`, its TTS step
  (`Step 4/6`) calls `synthesize_segments_sharded()` instead of
  `self.tts.synthesize_segments()`.
- **`DubbingPipeline.dub_course()`** — now sets `shard_tts_gpus=True` only
  when `len(tgt_langs) == 1`. With more than one target language, the
  existing `dub_course_parallel` language-bucket path is used unchanged
  (`num_gpus > 1 and len(tgt_langs) > 1` — note the added second condition).

## The oversubscription trap this avoids

`shard_tts_gpus` defaults to `False` and is **never** set `True` inside
`_worker_dub_langs`, which calls `pipeline.dub_video()` directly (not
through `dub_course()`). This matters: `_worker_dub_langs` runs *inside* a
`dub_course_parallel` worker that is already pinned to one GPU for its
bucket of languages. If sharding were also enabled there, every one of the
N language-workers would try to additionally spawn its own M-GPU shard pool
— N×M processes contending for the same 4 physical GPUs at once. That kind
of multi-process GPU contention is exactly what was implicated in the
Sept 2026 GPU driver wedge investigation (`docs/GPU_MEMORY_FIX.md`,
`docs/PARLER_TIMEOUT_FIX.md`). Sharding is only ever entered from a context
that is provably not already sharing the GPU pool with a sibling worker:
the segment editor (never has siblings) and `dub_course()`'s single-language
branch (routes around `dub_course_parallel` entirely for that case).

## What this does and doesn't fix

Fixes: GPU utilization for single-language jobs (was ~1 of 4 GPUs, now up
to 4) and the wall-clock time this costs (measured ~88-92% of total dub
time is TTS; sharding targets exactly that portion).

Does not fix: Parler-TTS's occasional long generation / 75s-timeout
behavior (`docs/PARLER_TIMEOUT_FIX.md`) — sharding runs more generations
concurrently across GPUs, it doesn't make any single generation faster or
more likely to find an early stop point. A worker whose bucket happens to
draw more of the slow segments will still take longer than its siblings;
the LPT bucket balancing reduces this by estimated word count, but a
timeout is not predictable from word count alone.

## Incident: 4-way sharding hit a 100% timeout rate (2026-09-16)

First real test of 4-GPU sharding: correct GPU placement (confirmed via
the per-GPU assignment/summary logging below), but **zero segments
succeeded across all 4 workers** for 8+ minutes, and `nvidia-smi` itself
hung — the same symptom as the original single-GPU driver wedge that
started this whole investigation, but system-wide this time.

Root cause (best-supported explanation, not fully proven): `tts.py`'s
Parler timeout handlers abandon a timed-out generation's thread rather
than killing it (`docs/PARLER_TIMEOUT_FIX.md` §3 — Python cannot kill a
running thread, so the abandoned GPU work keeps running in the
background). That was an accepted, bounded cost at 1 GPU. At 4 GPUs
running simultaneously, each worker independently retries failed segments
through several fallback layers (batch → single retry ×2 → split-in-half
→ MMS), each layer capable of its own timeout and its own abandoned
thread. With 4 GPUs each accumulating abandoned work at once, the total
system-wide abandoned-GPU-work load is roughly 4x what any single GPU run
ever produced — plausibly enough to back up the driver badly enough for
`nvidia-smi` to hang, and likely compounded further by 4 Python processes
contending for the same host CPU/RAM during autoregressive decode
(latency-sensitive to host-dispatch overhead per token).

## Fix: per-worker watchdog (kill-and-respawn)

Added to `tts_shard.py` / `tts_shard_worker.py`:

- Each worker now processes its bucket in chunks of `_CHUNK_SIZE = 6`
  segments (one `synthesize_segments()` call per chunk) instead of one
  call for the whole bucket, writing partial results to its `out_N.json`
  and touching a heartbeat file (`hb_N.txt`) after every chunk.
- The parent polls every `_POLL_INTERVAL = 3s`. If a worker's heartbeat
  goes stale for longer than `_HEARTBEAT_STALL_BUDGET = 480s` (8 minutes
  — sized above the legitimate worst case: a 6-segment chunk where every
  segment cascades through the full fallback chain can genuinely take
  several minutes), the parent kills that OS process outright
  (`proc.kill()` → `TerminateProcess`, which actually reclaims the
  process's GPU work — unlike abandoning a thread inside a still-alive
  process) and respawns a fresh worker for the same bucket.
- The respawned worker reads the existing `out_N.json` and skips
  already-completed segment ids — it resumes, it doesn't restart the
  whole bucket.
- After `_MAX_RESPAWNS = 2` respawns without a clean finish, that GPU's
  remaining segments get silence (`tts_silent_failure: True`, matching
  the existing silence-as-last-resort pattern used throughout `tts.py`)
  instead of blocking the job indefinitely.

**Known limitation, stated honestly:** `TerminateProcess` can itself fail
against a process wedged in an uninterruptible driver call — this was
observed directly during the incident that prompted this fix (two
consecutive `Stop-Process -Force` attempts both failed against processes
stuck this way). If that happens here, the watchdog still respawns a new
worker for that GPU; if the old process truly didn't die, the two will
contend for the same card. The respawn cap exists specifically so that
scenario is bounded rather than infinite. This has not yet been
re-tested against a live repeat of the original failure — next run
should confirm whether the watchdog actually recovers, or only reduces
blast radius.

## Expected impact (measured baseline: this repo's test video, 67 segments)

TTS phase measured at ~32 min of a ~36 min total job (single GPU). With
4-way sharding, realistic speedup is ~3-3.5x on the TTS phase (not a clean
4x — each worker pays its own Parler-large load cost, in parallel but not
free, plus bucket imbalance from timeout variance) →
TTS ~32 min → ~9-10 min, fixed non-TTS overhead (~4 min) unchanged →
total ~13-15 min, down from ~36 min.
