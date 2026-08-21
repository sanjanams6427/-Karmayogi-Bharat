# Codebase Update — August 20, 2026

All changed files dated Aug 20 09:34. Unchanged files remain Aug 11.

---

## New Files Added

### finetune/finetune_parler_tts.py
Full fine-tune of Indic Parler-TTS Large on all 22 Indian languages.
- Input data: `datasets/tts/<lang>/train.jsonl` + `dev.jsonl`
- Format: `{"text": "...", "audio_path": "path/to/file.wav", "lang": "hin"}`
- Uses EnCodec/DAC codec encoding on GPU — audio → codec tokens on device
- Cosine LR, label smoothing (0.05), early stopping (patience=2), 5 epochs
- Per-language sampling weights: bod/doi/kok/san = 3×, kas/mai/mni/sat/snd = 2×, hin = 2×
- Saves to `checkpoints/parler_tts/best/`
- TTS pipeline auto-loads from `checkpoints/parler_tts/best/` if present

### scripts/eval_finetuned.py
Compare fine-tuned vs base IndicTrans2 on dev set using ChrF scoring.
- Usage: `python scripts/eval_finetuned.py --direction en_indic --langs hin ben tam --n 100`
- Loads both models, runs translation, prints per-language ChrF delta table
- Shows delta with ✅/⚠️ flags

### scripts/fill_gap_langs.py
Fetches parallel data for 8 gap languages from public HF datasets.
- Gap langs: bod, doi, kas, kok, mni, mai, san, sat
- Sources: ai4bharat/IN22-Gen, ai4bharat/IN22-Conv, facebook/flores, Helsinki-NLP/opus-100
- Deduplicates by src, uses FLORES for dev/test, rest for train
- Usage: `python scripts/fill_gap_langs.py [--langs bod doi ...] [--force]`

### scripts/verify_datasets.py
Deep verification of all 22 language parallel datasets.
- Checks: line counts, JSON validity, empty src/tgt, bad length ratios, missing lang fields, duplicate src, script sanity
- Script range spot-check on first 200 records per language
- Tolerances: wrong_script < 5% OK, duplicate_src < 6% OK (TM 3× repeat factor)
- Prints full table + PASS/WARN per language

### scripts/download_tts_data.py
Downloads TTS audio data (text+audio pairs) for Parler-TTS fine-tuning.
- Sources: google/fleurs (14 Indian langs), ai4bharat/Kathbath (12 langs), psk/indic-tts-966h (6 langs)
- Output: `datasets/tts/<lang>/train.jsonl` + `dev.jsonl`
- Resamples all audio to 44100Hz, clips at 20s, min 0.5s
- Creates `datasets/tts_wav/` directory for WAV files

---

## New Dataset Directories

### datasets/tts/
TTS training data for Parler-TTS fine-tuning. 14 languages present:
`asm, ben, guj, hin, kan, mal, mar, nep, ory, pan, snd, tam, tel, urd`
Each has `train.jsonl` + `dev.jsonl`

### datasets/parallel/ — gap languages filled
bod, doi, kok, san now have train/dev/test.jsonl (were empty before)
- bod: train=1.5MB, doi: 500KB, kok: 496KB, san: 1.4MB

---

## Updated Pipeline Files

### pipeline/asr.py
- beam_size: 5 → 4
- vad_parameters: added `speech_pad_ms=200`
- Language-specific merge windows: tam/tel/mal/kan → min_words=5, min_dur=2.0, max_dur=15.0
- Hallucination stripping expanded:
  - `_HALLUC_DEVA_RE`: Devanagari hallucination prefixes
  - `_HALLUC_BOUNDARY_RE`: leading punctuation/Indic punctuation artifacts
  - Tamil virama-initial fragment regex (U+0B80–U+0BFF)
  - Telugu virama-initial fragment regex (U+0C00–U+0C7F)
- All patterns pre-compiled at module level

### pipeline/lang_config.py
- SEAMLESS_CODES: added `"kas": "kas"` — SeamlessM4Tv2 now supports Kashmiri text translation

### pipeline/tts.py (major — +28KB)
- Added `NUMBA_DISABLE_JIT=1` env var at import (prevents NumPy version crash)
- PARLER_DIR priority: `checkpoints/parler_tts/best/` → large → mini (fine-tuned auto-loaded)
- `_PARLER_SKIP_LANGS` now includes `"tam"` and `"tel"` — skip Parler, go to MMS VITS
- `_MMS_STANDALONE_LANGS`: ALL 22 languages now use standalone VITS from `models/mms_standalone/<lang>/`
  Old: shared base + adapter swaps. New: individual VITS per language.
- Per-language `_PARLER_DESCS`: language-specific Indian voice prompts (was single generic desc)

### pipeline/subtitles.py
- Added `_clean_sub_text()`: strips leading punctuation artifacts from subtitle text
- `generate_srt()` and `generate_vtt()`: accept `video_duration` param to extend last subtitle
- Added `burn_subtitles()`: hardcodes SRT into video stream via ffmpeg
- Added `embed_subtitles_soft()`: embeds SRT as selectable soft track (mov_text), falls back to burn

### pipeline/dubbing_pipeline.py (+4KB)
- `_repair_asr_segments()` NEW: merges Whisper mid-sentence splits. Detects continuation segments (start with lowercase/punctuation), merges into previous. Fixes dangling conjunctions at end of last segment.
- Quality gate REMOVED: score < 0.30 no longer silences segments. All translations go to TTS. Low score = flagged for human review only. Gaps in video worse than imperfect translation.
- `_worker_tts_split()` NEW: TTS-only parallel worker. Splits TTS across primary + spare GPUs round-robin. ~2x speedup when spare GPU available.
- `voice_clone` param removed from `dub_video()` and `dub_course()` — voice cloning no longer in main pipeline API.
- TTS CUDA error recovery: CUDA/illegal-memory error resets engine, clears GPU cache, retries with MMS fallback automatically.
- `_worker_dub_langs()`: frees VRAM between languages (`cuda.empty_cache()`), unloads TTS engine between languages to free ~4GB.

### pipeline/translator.py (+7KB)
- `_SEAMLESS_FIRST = {"mni"}`: Manipuri now routed to SeamlessM4T first (handles natively, better than Hindi pivot).
- `_build_foreign_word_re()` + `_clean_mixed_lang()`: Full Unicode script-range system. Pre-built per-language regexes strip foreign-script runs. 22 language scripts with exact codepoint ranges.
- `_naturalise()`: New rule-based readability cleanup — removes repeated adjacent words, fixes "word ," → "word,", collapses multi-punctuation.
- `_final_quality_check()`: 10-rule final gate on every translation (non-empty, completeness, grammar, fluency, placeholder restore, corruption-free, placeholder-free, mixed-lang, formatting, professional). Applied to all paths.
- Maithili drift guard: detects मैथिली tokens (छथि/अछि/कयल/छत्हि) in Hindi output → retries via NLLB.
- Agglutinative language fix: tam/tel/mal/kan/hin/mar/ben/guj/pan/ory/asm/mai/nep/urd get max_new_tokens=1024 and no_repeat_ngram_size=0 (was 3 for all). Ngram penalty blocks morphological suffixes in agglutinative scripts.
- Solo retry for short batch outputs: if batch result < 50% source length, re-runs segment solo to catch BOS/EOS bleed in batch padding.
- `torch.compile()` applied to IndicTrans2 after loading for ~20% speedup (silent fallback if unavailable).

### pipeline/video_processor.py (+7KB)
- Added `_has_audio_stream()` method
- Added `_probe()` method: ffprobe with fallback to ffmpeg stderr Duration parsing
- Added `_run()` method: unified ffmpeg/ffprobe runner replacing subprocess.run calls

### finetune/finetune_indictrans.py (v2 — +5.5KB)
1. All 22 langs in en_indic (was 12 — mni/sat/kas/snd/bod/doi now included)
2. Per-language sampling weights by dataset size + resource tier
3. Label smoothing: 0.1
4. Cosine LR schedule (was linear)
5. Curriculum: gold data first, synthetic mixed in later epochs
6. Quality filter: drops pairs where len(tgt)/len(src) < 0.3 or > 5.0
7. TM/HF upweight: 5× (was 3×)
8. 5 epochs with early stopping patience=2 (was 3 epochs, no early stop)
9. Separate dev eval per language group
10. indic_indic: all 22×22 pairs (was 21 hand-picked)

### scripts/download_models.py (+4KB)
Now downloads all 22 standalone MMS-TTS VITS models to `models/mms_standalone/<lang>/`:
- 11 mandatory: tam/tel/hin/kan/mal/ben/mar/guj/pan/ory/asm
- Gap langs: doi(dgo)/bod/mni/kok/kas(urd-arabic proxy)/urd/nep/mai/san/sat/snd

### ui/app.py (+6KB)
- `_job_semaphore`: only 1 job at a time. New jobs return "Another job is already running."
- Tab 1 redesigned: voice clone removed. Added quality scores Dataframe per language with score bar, pass/fail, duration ratio. `_build_scores_table()` and `_format_quality_summary()` helpers added.
- Tab 2 extended: accepts DOCX/TXT directly. Format-preserving DOCX via `translate_docx()`. PDF returns explicit §3.1 error. `_chunk_text()` for sentence-boundary-aware text splitting. `_translate_plain_doc()` new function.
- Tab 3 (QA): SLA threshold table and penalty schedule added to UI.
- Tab 4 (Human Review): `_rv_approve_all()` fixed, review stats display added.
- Live Logs: `warnings.filterwarnings` suppresses Gradio/Starlette deprecation noise.
- Server binding: `app.launch()` binds to `172.23.198.15` with port scan 7860–7870 for free port.

### requirements.txt (-1.4KB)
- Cleaned/reduced — some dependencies removed or consolidated

---

## Architecture Changes Summary

1. **MMS-TTS all-standalone VITS** — no shared adapter model. Every language has its own dedicated VITS model. Eliminates adapter-swap latency.

2. **Parler-TTS fine-tune pipeline complete** — `finetune_parler_tts.py` + `download_tts_data.py` + `datasets/tts/` data ready. Fine-tuned checkpoint auto-loaded by `tts.py`.

3. **Tamil and Telugu skip Parler** → MMS VITS standalone (better quality for Dravidian scripts).

4. **Kashmiri in SeamlessM4T** — SeamlessM4Tv2 supports Kashmiri text translation now.

5. **Gap language data filled** — bod/doi/kok/san parallel datasets now present.

6. **New tooling** — `eval_finetuned.py` (MT quality comparison) + `verify_datasets.py` (data integrity).

7. **Subtitle pipeline extended** — soft embed and hardcode burn options added.

8. **ASR hallucination removal improved** — Devanagari, Tamil, Telugu specific patterns added.

---

## File Size Reference

| File | Aug 11 | Aug 20 | Change |
|---|---|---|---|
| pipeline/tts.py | 34,379 | 62,410 | +28,031 (major) |
| pipeline/translator.py | 47,858 | 55,240 | +7,382 |
| pipeline/video_processor.py | 18,565 | 25,556 | +6,991 |
| ui/app.py | 45,601 | 51,675 | +6,074 |
| pipeline/dubbing_pipeline.py | 69,484 | 73,756 | +4,272 |
| scripts/download_models.py | 2,094 | 6,374 | +4,280 |
| finetune/finetune_indictrans.py | 17,181 | 22,692 | +5,511 |
| pipeline/asr.py | 9,887 | 11,076 | +1,189 |
| pipeline/subtitles.py | 5,174 | 6,473 | +1,299 |
| pipeline/lang_config.py | 4,175 | 4,258 | +83 |
| finetune/finetune_parler_tts.py | — | 16,134 | NEW |
| scripts/download_tts_data.py | — | 11,733 | NEW |
| scripts/verify_datasets.py | — | 8,784 | NEW |
| scripts/fill_gap_langs.py | — | 8,554 | NEW |
| scripts/eval_finetuned.py | — | 6,623 | NEW |
| requirements.txt | 4,747 | 3,377 | -1,370 (cleaned) |
