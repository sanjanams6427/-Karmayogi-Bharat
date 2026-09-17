# GPU Memory Leak Fix — Web UI Batch & Segment Editor

**Symptom reported:** running a translation/dubbing job from the web UI froze
the whole machine — not just the app.

**Root cause:** neither web-UI code path ever freed GPU memory between
languages, and neither ever used more than one GPU even when several were
available. This doc records what was actually happening, what changed, and
what did *not* change.

---

## 1. What was wrong

### 1a. Models were never evicted

`DubbingPipeline` (used by the batch/oneshot flow) and `SegmentEditor` (used
by the interactive editor) both lazy-load their translator and TTS engines as
cached instance properties:

```python
@property
def translator(self):
    if self._translator is None:
        self._translator = Translator()
    return self._translator
```

`Translator` itself caches every distinct engine it ever loads
(`self._indic_trans2[direction]`, `self._seamless`, `self._nllb`) for its own
lifetime, with no eviction. Depending on which languages a job touches, this
can mean IndicTrans2 (up to 3 directions), SeamlessM4T (~10GB) and NLLB-200
(~2.4GB) are all resident in VRAM *simultaneously* — on top of TTS (Parler ~3.6GB
+ per-language MMS + XTTS) and ASR (~3GB) — and none of it was ever released.

- **Batch flow** (`api/web_routes.py::_run_batch_job`): created one
  `DubbingPipeline()` and looped over every requested language, reusing the
  same pipeline object with **zero cleanup** between iterations.
- **Segment editor** (`api/server.py`): `_editor = SegmentEditor()` is a
  **module-level singleton**, created once when the server process starts and
  shared by *every session, every video, every target language, for the
  server's entire uptime*. Its cached engines were never reset — not between
  segments, not between sessions.
- The one path that partially got this right — `_worker_dub_langs()`, used
  only by the multi-GPU CLI flow (`scripts/dub.py --num-gpus`) — reset
  `pipeline._tts` between languages but never `pipeline._translator`, so even
  that path leaked on the translation side.

On Windows, once VRAM is exhausted the NVIDIA driver's WDDM layer falls back
to slow shared/system memory and can trigger a TDR (driver timeout/reset).
Since the GPU also drives the desktop, that's what presented as "the whole
system freezes."

### 1b. Only GPU 0 was ever used

Every engine picks its device the same way, defaulting to GPU 0 unless a
`PIPELINE_GPU` env var says otherwise:

```python
_gpu = os.environ.get("PIPELINE_GPU", "0")
DEVICE = f"cuda:{_gpu}"
```

`PIPELINE_GPU` is only ever set to anything else inside
`_worker_dub_langs()`, i.e. only when the CLI is run with
`--num-gpus`. **Neither web-UI flow ever called into that path** — both
called `dub_video()` directly. So on a machine with 4 GPUs, the web UI ran
every model, for every language, on GPU 0 alone, while the rest sat idle —
which made the eviction bug above far more likely to actually exhaust VRAM.

---

## 2. What changed

### `pipeline/dubbing_pipeline.py`

- **New: `DubbingPipeline.unload_models()`** — drops `self._translator` and
  `self._tts` (so their internal engine caches go with them), then
  `torch.cuda.synchronize()` + `torch.cuda.empty_cache()`. ASR is
  deliberately left loaded — it's one fixed model reused for the same audio
  across a job, not something that accumulates variants.
- **`dub_course()`** (the single-GPU sequential path) now calls
  `self.unload_models()` after every language, and takes an optional
  `progress_callback` invoked after each language completes.
- **`dub_course_parallel()`** (the multi-GPU path):
  - `_worker_dub_langs()` now calls `pipeline.unload_models()` between
    languages instead of only clearing `pipeline._tts` — closes the
    translator-side leak that existed even in the "working" path.
  - Result collection switched from `pool.map()` (blocks until every GPU
    finishes) to `pool.imap_unordered()`, streaming each GPU worker's
    results back as its language bucket finishes, and invoking
    `progress_callback(group)` per worker so callers get incremental
    progress instead of a bar frozen at 0% for the whole job.

### `pipeline/segment_editor.py`

- **New: `SegmentEditor.unload_models()`** — same eviction as above. Called
  automatically at the end of `stitch()` and `stitch_with_extensions()`,
  i.e. when a session's work is actually done. This is safe to call while
  other sessions are active on the same shared `_editor`: it only clears
  cached engine objects, not session state, so a concurrently active
  session's next translate/TTS call just reloads what it needs — a latency
  cost, not a correctness issue.

### `api/web_routes.py`

- **New: `_apply_dubbing_result(job, tgt_lang, result)`** — extracted from
  the old inline per-language block so both the sequential and parallel
  code paths update `job.results` identically. This also **fixes a
  pre-existing bug**: `dub_video()` never raises on failure — it catches
  internally and returns a `DubbingResult` with `success=False`. The old
  code only had a `try/except` around the call, so a failed language was
  never caught by it and was recorded as `"completed"` with empty/wrong
  output paths. The new helper checks `result.success` explicitly.
- **`_run_batch_job()`** now:
  - Detects available GPUs via `torch.cuda.device_count()` and calls
    `pipeline.dub_course(..., num_gpus=n_gpus, progress_callback=...)`
    instead of looping over `dub_video()` itself — so the batch endpoint
    now actually uses every GPU the machine has, the same way the CLI's
    `--num-gpus` flag does, with no separate code path to maintain.
  - Falls back to the single-GPU sequential path automatically when only
    one GPU is available (or none — `n_gpus` clamps to `1`).
  - Calls `pipeline.unload_models()` once more in a `finally` block after
    the whole job, belt-and-braces.
  - `BatchJobState` gained a `num_gpus_used` field so the job status
    reflects how many GPUs a given run actually used.

---

## 3. What did *not* change

- ASR is still loaded once per job/session and reused — it was never part of
  the leak and doesn't need eviction.
- The segment editor's `_editor` is still a single global singleton shared
  across sessions — that's the existing architecture, not something this fix
  redesigns. What changed is that it now *releases* its engines when a
  session finishes stitching, instead of holding them for the server's
  entire uptime.
- Per-segment translate/TTS calls in the segment editor (`/translate/{seg_id}`,
  `/tts/{seg_id}`) are **not** evicted after each call — only at session end
  (on `stitch`). Evicting on every click would force a model reload on the
  very next click, which would make the interactive editor unusably slow.
  If a session is abandoned before reaching `stitch` (browser closed, user
  never finishes), its engines stay cached until either another session's
  `stitch` runs or the server restarts — a known, accepted gap, not silently
  missed.

---

## 4. Live GPU Monitor (new web UI tab)

To actually *see* all of the above happening instead of taking it on faith,
there's now a **📈 GPU Monitor** tab in the web UI showing, live:

- per-GPU utilization + VRAM meters (from `nvidia-smi`)
- a rolling VRAM-over-time chart, one line per GPU
- which engines are currently resident (`asr`, `translator:indictrans2:en_indic`,
  `tts:parler`, …) as chips, with how long ago each was loaded
- a scrolling timeline of every **load** / **swap** / **evict** event, so you
  can watch e.g. `SeamlessM4T loaded` followed later by
  `translator:seamless evicted` instead of inferring it from a memory graph
  alone

### New module: `pipeline/gpu_monitor.py`

Two independent pieces:

1. `get_gpu_stats()` — shells out to `nvidia-smi`, returns per-GPU
   utilization/VRAM/temperature, or `{"available": False, ...}` if there's
   no NVIDIA driver on PATH (never raises). **Known quirk, fixed here:**
   some virtualized/GPU-passthrough drivers report a sentinel value for
   `memory.used` (observed in testing: `17592186044375`, ≈2⁴⁴) instead of a
   real reading — `get_gpu_stats()` clamps `mem_used_mb` to `mem_total_mb`
   so the UI never shows "used > total".
2. A small thread-safe in-memory event log — `log_load()` / `log_swap()` /
   `log_evict()` / `evict_all(prefix)` / `recent_events()` /
   `currently_loaded()`. Engine keys follow a `"<family>:<detail>"`
   convention (`translator:indictrans2:en_indic`, `tts:mms_base`, …) so
   `evict_all("translator:")` can free everything under a family without
   needing to know every specific engine that might be loaded.

This is instrumentation only — it observes the existing lazy-load
properties and `unload_models()` calls, it doesn't change what gets loaded
or when. Hooked in at every actual `from_pretrained(...)` call site:
`pipeline/translator.py` (IndicTrans2 ×3 directions, SeamlessM4T, NLLB),
`pipeline/tts.py` (Parler-TTS, MMS-TTS base + adapter swaps, standalone
VITS per language), and the `asr` properties / `unload_models()` methods
in both `pipeline/dubbing_pipeline.py` and `pipeline/segment_editor.py`.

### New API endpoints (`api/web_routes.py`)

- `GET /api/gpu/stats` — current stats + `currently_loaded()`.
- `GET /api/gpu/events?since=<ts>&limit=<n>` — events after `since`, for
  incremental polling.

### New frontend (`web/gpu-monitor.js`, markup in `web/index.html`, styles
appended to `web/style.css`)

Plain vanilla JS, no build step or chart library — consistent with the
rest of `web/`. Polls both endpoints every 1.5s **only while its tab is
active**, plots VRAM history on a hand-drawn `<canvas>` line chart, and
renders the event timeline as a scrolling list. Verified end-to-end with
`fastapi.testclient.TestClient` (both endpoints return `200` with the
expected shape, and a simulated load→evict cycle round-trips correctly
through `/api/gpu/events` and `/api/gpu/stats`'s `loaded` field).

---

## 5. How to verify

```bash
# Sanity-check the edited modules still import cleanly
venv\Scripts\python -c "import pipeline.dubbing_pipeline, pipeline.segment_editor, api.server"

# Start the server, open the app, then open the 📈 GPU Monitor tab —
# it's the easiest way to watch this live without a separate terminal.
python run_web.py
```

From the **GPU Monitor** tab: start a batch job spanning several languages
that hit different translation engines (e.g. `hin`, `ben`, `mni`, `sat` —
IndicTrans2, NLLB, SeamlessM4T, and the Hindi-pivot path respectively) and
confirm:
- the event timeline shows a `load` for each new engine as that language's
  routing rule needs it, and an `evict` for `translator:*`/`tts:*` after
  each language finishes
- the VRAM chart drops back down between languages instead of climbing
  monotonically for the whole job
- if more than one GPU is available, more than one line appears on the
  chart with real activity, not just GPU 0

(Or, without the UI: `nvidia-smi -l 1` in a separate terminal works too —
the GPU Monitor tab is just reading the same `nvidia-smi` data plus the
load/evict events, rendered live.)
