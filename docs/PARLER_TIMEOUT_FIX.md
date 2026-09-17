# Parler-TTS Timeout Fix — "STUCK FOR LONG TIME" Taking Longer Than Logged

> **SUPERSEDED (2026-09-16):** the abandon-the-thread timeout described below
> is no longer the primary mechanism. Parler generations now carry a hard
> deadline INSIDE the generation loop via `generate(max_time=...)` →
> transformers `MaxTimeCriteria` (verified in the installed parler_tts +
> transformers source, and tested live: a 2400-token generation given
> `max_time=3` returned in 5s). A slow generation stops cleanly with NO
> abandoned GPU thread — the thread-timeout survives only as a "+30s wedge
> grace" backstop for true driver stalls (logged as `WEDGED`). Deadlines are
> also token-scaled (ceiling 120s); the old 75s ceiling gave real 60s
> generations ~20% headroom, which caused the timeout cascades in sharded
> runs. See pipeline/tts.py.

**Symptom reported:** a Hindi batch job logged
`[pipeline.tts] Parler single TIMEOUT [hin] after 75s STUCK FOR LONG TIME`
and the job kept running for far longer than 75s afterward — looked hung,
wasn't fully deadlocked, just very slow.

Related to, but distinct from, `docs/GPU_MEMORY_FIX.md` — that doc covers
VRAM never being *released*; this one covers GPU work never being properly
*abandoned*.

---

## 1. Why Parler times out at all (expected, not a bug)

`pipeline/tts.py::_calc_max_tokens()` caps Parler-TTS generation at 2400
tokens (~28s of audio). Parler generates audio autoregressively, and for
some Hindi text it doesn't find a natural stopping point — it runs the
*entire* 2400-token generation instead of stopping early. On an A6000 that
alone can take 60–75s. This isn't corruption, it's a known Parler-TTS
behavior for certain inputs.

There's an intentional safety net for this: `_PARLER_TIMEOUT_CEILING = 75`
(seconds) bounds how long any single generation is allowed to run before
the code gives up on it and falls back to MMS-TTS for that segment. That
part was already working as designed.

## 2. The actual bug: the timeout handler blocked on the thing it was timing out on

All three Parler timeout handlers (`_parler_generate_batch`,
`_parler_generate_single`, `_synthesize_parler`) followed this pattern:

```python
except concurrent.futures.TimeoutError:
    log.error(f"... TIMEOUT ... STUCK FOR LONG TIME")
    _ex.shutdown(wait=False)          # detaches the thread — correct
    if torch.cuda.is_available():
        torch.cuda.synchronize()      # <-- the bug
        torch.cuda.empty_cache()
    return False
```

`_ex.shutdown(wait=False)` correctly detaches from the timed-out thread
without waiting for it — Python can't force-kill a thread, so the
abandoned `model.generate()` call keeps running on the GPU in the
background regardless. That's an accepted limitation (see §3).

But `torch.cuda.synchronize()` right after that **blocks the calling
thread until every queued operation on the current CUDA stream finishes**
— including the kernels the abandoned thread is still pushing to that same
default stream. So the actual sequence was:

1. Wait up to 75s for the future.
2. Log "TIMEOUT ... STUCK FOR LONG TIME".
3. Call `synchronize()` — which then blocks for however much *longer* the
   abandoned generation takes to actually finish on its own.
4. Only then does the function return `False` and let MMS fallback proceed.

Step 3 silently defeated the entire point of the 75s ceiling. The log line
told you it gave up at 75s; the code didn't actually give up until later,
however much later depended on how badly that specific generation was
stuck.

**Fix:** removed the `torch.cuda.synchronize()` (and the `empty_cache()`
that depended on it) from all three timeout branches. Nothing useful was
being reclaimed there anyway — the abandoned thread still holds live
references to its own tensors, so `empty_cache()` can't free that memory
until the thread's frame actually exits on its own. The timeout handler
now does exactly what its log message says: logs, detaches, returns
immediately.

## 3. What's still true — the honest limitation

Python cannot cancel a running thread. After a timeout, the abandoned
generation keeps consuming GPU compute until it naturally completes,
competing with whatever runs next on the same shared `self._parler_model`.
This fix stops the *pipeline* from blocking on it — it does not stop the
*GPU* from being contended by it for a while. If you see several Hindi
segments in a row hit the 75s ceiling back to back, some slowdown from that
GPU contention is expected; it should no longer compound into a full stall
per occurrence.

A cleaner fix for that residual issue would mean running Parler generation
in an actually-killable subprocess instead of a thread — a bigger
architectural change, not done here. Flagging it in case it comes up again.

## 4. Files changed

- `pipeline/tts.py` — three timeout-exception blocks
  (`_parler_generate_batch`, `_parler_generate_single`, `_synthesize_parler`),
  each with the `torch.cuda.synchronize()` call removed and a comment
  explaining why, so it doesn't get re-added later without the context.

## 5. Follow-up: segment editor TTS was slow AND more failure-prone than it needed to be

Once the timeout fix above was in and the timing was still frustratingly
slow, two more real gaps turned up by comparing the segment editor's TTS
path against the oneshot/batch flow's — which does the same job much
faster and more robustly, using code that already existed in this file.

**Gap 1 — no batching.** `SegmentEditor.synthesize_all()` called
`synthesize_single()` once per segment, sequentially — one GPU round-trip
per segment. `TTSEngine.synthesize_segments()` (used by oneshot dubbing)
batches 4 segments per Parler forward pass instead, with the batch size
already tuned on this exact hardware (4×A6000, 48GB each — see
`SYSTEM_MEMORY.md §17`), already handling OOM gracefully (falls back to
singles per-batch on `torch.cuda.OutOfMemoryError`, doesn't crash).

**Fix:** `synthesize_all()` now builds the same `{id, text, start, end}`
list `synthesize_segments()` expects, calls it once, and maps the results
back onto `Segment` objects (`tts_audio_path`, `tts_duration` — read via
`soundfile.info()` since the batched function doesn't return duration
directly — `tts_engine`, `approved` reset). Fewer, much better-utilized
GPU calls instead of many small ones. Progress reporting is coarser as a
result (0% → 100%, not per-segment) since `synthesize_segments()` doesn't
expose incremental progress — a reasonable trade given the whole operation
is now much shorter.

`synthesize_segment()` (single-segment, used to regenerate one segment
after reviewing it) is **unchanged** — still uses `synthesize_single()`
with its own voice-pinning, exactly as before. Only "Generate All" changed.

**Gap 2 — the single-segment path had no long-segment safety net.**
`synthesize_segments()` pre-splits any segment over 45 words into
sentence-level chunks (`_synthesize_long_segment()`) *before* ever
attempting one continuous generation — long segments are exactly the ones
most likely to hit Parler's "doesn't find a stop point" failure mode this
whole doc is about. `_synthesize_parler()` (used by `synthesize_single()`,
i.e. every individual per-segment call) had no such check — it always
went straight to one monolithic generation attempt, capped at the 2400-token
ceiling, no matter how long the segment.

**Fix:** `_synthesize_parler()` now checks `len(text.split()) > 45` right
after resolving `desc_ids`/`encoder_outputs` (before generating) and
redirects to `_synthesize_long_segment()` when true — same function the
batch path already uses, same voice-consistency inputs, just reached from
one more call site. Applies to any future single-segment regeneration too,
not just the initial batch pass.

## 6. How to verify

Watch `scripts/watch_pipeline.ps1` during a Hindi batch job. If a segment
hits the timeout, the red "TIMEOUT" line should be followed almost
immediately by the MMS fallback log for that same segment — not by a long
silent gap before anything else happens.
