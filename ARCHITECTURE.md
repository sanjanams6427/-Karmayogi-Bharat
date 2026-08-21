Section 4 — Core ContentSection 4 — Core Contentection 4 — Core**Starting the Session:****Starting the Session:****Starting the Session:**

# KB Translation System — Architecture & Deep Analysis

> Generated: 2026-08-12 | Contract: RFB IN-KBL-543730-NC-RFB

## What This Is

A **government contract system** built to fulfill the iGOT Karmayogi platform's requirement to dub and translate e-learning content from English into all 22 constitutionally scheduled Indian languages. Core constraint driving every design decision: **fully offline, no API keys, no data leaves the system** — hard requirement for government data sovereignty compliance.

---

## The Big Picture Goal

The tender mandates:

- Translate/dub e-learning course videos into 22 Indian languages
- Generate subtitles (SRT/VTT), translated quizzes (DOCX/XLSX), metadata
- Meet a 98% linguistic accuracy SLA
- Submit monthly delivery reports, QA self-certification docs, and upload to the CBP portal
- No transliteration (must be real translation into target script)
- Content exclusions: PM/President speeches and YouTube-only content are blocked

The system automates the entire delivery pipeline from raw video to final CBP-portal-uploaded multilingual package.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Entry Points                              │
│  scripts/dub.py (CLI)          ui/app.py (Gradio, 8 tabs)  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              DubbingPipeline (orchestrator)                  │
│  dubbing_pipeline.py — the single brain of the system       │
│  - Input validation, job locking, checkpoint/resume         │
│  - 6-step pipeline with S2ST fast-path                      │
│  - Multi-GPU distribution via multiprocessing.spawn         │
│  - Metadata, quiz, QA, monthly/completion/inception reports │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼───────┐ ┌───▼────────┐
│  ASR        │ │ Translator  │ │  TTS       │ │ VideoProc  │
│  asr.py     │ │ translator  │ │  tts.py    │ │ video_     │
│             │ │ .py         │ │            │ │ processor  │
│ faster-     │ │ IndicTrans2 │ │ Parler-TTS │ │ .py        │
│ whisper     │ │ → Seamless  │ │ → MMS-TTS  │ │            │
│ large-v3    │ │ → NLLB-200  │ │ → XTTS-v2  │ │ ffmpeg     │
└─────────────┘ └────────────┘ └────────────┘ └────────────┘
       │              │              │
┌──────▼──────────────▼──────────────▼──────────────────────┐
│                 Support Layer                               │
│  quality.py      — heuristic + ChrF + back-translation     │
│  glossary.py     — 22 × per-language JSON glossaries       │
│  translation_    — govt TM + human feedback, fuzzy match   │
│  memory.py                                                  │
│  retry.py        — crash-safe job checkpoints              │
│  lang_detect.py  — per-segment language tagging            │
│  subtitles.py    — SRT + VTT generation                    │
│  llm_enhancer.py — optional Groq/Gemini post-edit          │
│  cbp_uploader.py — CBP portal upload                       │
│  voice_clone.py  — Coqui XTTS-v2                           │
│  logger.py       — structured JSON pipeline + audit logs   │
└────────────────────────────────────────────────────────────┘
```

---

## The 6-Step Pipeline (Core Execution Path)

### Step 1 — Audio Extraction

ffmpeg strips audio to 16kHz mono WAV. Stale-cache detection: if the source video is newer than `source.wav`, it re-extracts automatically.

### Step 1b — S2ST Fast-Path (optional)

For Indic→Indic pairs (only `hin/ben/kan/tel/urd`), SeamlessM4T is attempted for direct speech-to-speech translation. If it succeeds, steps 2–5 are skipped entirely. English source always goes through the full pipeline.

### Step 2 — ASR (Automatic Speech Recognition)

faster-whisper large-v3 with:

- `condition_on_previous_text=False` (hallucination guard)
- Multi-temperature fallback `[0.0, 0.2, 0.4]`
- VAD filtering, word-level timestamps
- Custom `_merge_segments` producing natural 6–12 second sentence-length chunks
- Per-segment language detection for mixed-language content
- Nastaliq normalisation post-processes Urdu/Kashmiri/Sindhi

### Step 3 — Translation

Three-engine fallback chain per language group:

| Route             | Primary                     | Fallback 1  | Fallback 2 |
| ----------------- | --------------------------- | ----------- | ---------- |
| Most Indian langs | IndicTrans2 (fine-tuned)    | SeamlessM4T | NLLB-200   |
| mni, sat, san     | IndicTrans2 via Hindi pivot | NLLB-200    | —         |
| kok, snd, kas     | NLLB-200                    | —          | —         |

**Translation protection stack** (applied before any engine sees the text):

- Format tokens (`{name}`, `%s`, `${var}`, `{{jinja}}`) → `__FMT0__` placeholders
- Non-translatable content (URLs, file paths, code) → `__NT0__` placeholders
- Factual tokens (numbers, dates, currency, measurements) → `__F0__` placeholders
- All three are restored after translation

**Translation memory** is checked first (exact HF correction → exact govt TM → 85% fuzzy match), before hitting the ML engines.

**GPU batch translation:** all pending segments for a language are sent as a single batch. Checkpointing is per-segment — a crash mid-translation resumes exactly where it stopped.

**Quality gate:** segments scoring < 0.30 are silenced (translated text set to `""`) — no wrong-language audio is sent to TTS.

### Step 4 — TTS (Text-to-Speech)

Three-engine fallback:

- **Parler-TTS Indic Large** (primary) — 44kHz, single model for all 22 languages, generic style description. Skips `sat/kas/snd` (can't render those scripts).
- **MMS-TTS** — Facebook's shared VITS base with per-language adapter swaps. Dogri (`doi`) uses standalone `facebook/mms-tts-dgo`.
- **XTTS-v2** — Coqui open-source, last resort; also used for voice cloning (tender Tier 2 pricing) for 10 languages.

### Step 5 — Audio Assembly

Segments placed at original timestamps. Audio that overruns its slot is time-stretched at max 1.35×, then hard-trimmed if still over. Gaps are padded with silence. Result is a dubbed WAV with exactly the original video's duration.

### Step 6 — Output

- SRT + VTT subtitles generated from translated segments
- ffmpeg muxes dubbed audio back into the video
- Duration ratio check: if output >20% longer than original → KB approval flag set in metadata (tender §5.1B)
- Metadata JSON written with quality scores, transcript, translations, model versions, git commit hash, contract reference

---

## Data Flow Summary

```
Input MP4
  → Audio extraction (ffmpeg)
    → [S2ST fast-path for Indic→Indic, skip to output if successful]
    → ASR segments (faster-whisper, with timestamps)
      → Exclusion check
      → [TM lookup per segment]
      → Batch translation (IndicTrans2 → Seamless → NLLB)
        → Quality scoring per segment
          → Quality gate (silence failures)
          → TTS synthesis per segment (Parler → MMS → XTTS)
            → Audio assembly at timestamps (1.35× max stretch)
              → Subtitle generation (SRT + VTT)
              → ffmpeg mux
              → Duration ratio check
              → Metadata JSON + QA cert DOCX
                → CBP portal upload (optional)

Output: MP4 + SRT + VTT + metadata.json + qa_cert.docx + quiz.docx/xlsx
```

---

## Resilience Architecture

| Mechanism                 | File                    | Behaviour                                                                                                                   |
| ------------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Crash-safe resume         | `retry.py`            | `JobCheckpoint` persists every translated segment atomically (write-to-tmp, rename). Resumes from last completed segment. |
| Concurrent job protection | `dubbing_pipeline.py` | Per`(course_id, lang)` threading locks prevent duplicate job overwrites.                                                  |
| Stale cache detection     | `dubbing_pipeline.py` | Source WAV re-extracted if input video has newer mtime.                                                                     |
| Completeness guards       | `dubbing_pipeline.py` | 3 separate checks ensure no translation slot is silently dropped. Falls back to per-segment if batch returns wrong count.   |
| Empty translation retry   | `dubbing_pipeline.py` | Empty output for non-empty source triggers full fallback chain retry. Never writes English source text to non-English TTS.  |

---

## Multi-GPU Strategy

When `num_gpus > 1` and dubbing all 22 languages:

1. ASR runs **once** in the main process (cached to `_asr_shared/asr_cache.json`)
2. Languages are round-robin distributed across GPUs (~5–6 per GPU for 4 GPUs)
3. Workers spawn via `multiprocessing.spawn` (not fork — Windows-safe) with `PIPELINE_GPU` env var
4. Each worker gets exclusive GPU for translate + TTS + assemble
5. Shared ASR cache seeded into each worker's job checkpoint — skips redundant transcription
6. Results merged back, shared cache cleaned up

---

## Quality Scoring System (`quality.py`)

Every translated segment scored 0–1 via 8 heuristic checks:

| Check                                                         | Penalty       |
| ------------------------------------------------------------- | ------------- |
| Extreme length ratio (< 0.3× or > 4× source words)          | −0.25        |
| Source language leakage (< 50% native script in output)       | −0.30        |
| Repetition loop (4 identical consecutive words)               | −0.35        |
| Untranslated (exact copy or > 80% Latin for non-Latin target) | −0.35–0.40  |
| Too short (≥5 source words but < 2 output words)             | −0.30        |
| Transliteration detected (tender §3.2 compliance)            | −0.35        |
| Missing factual tokens (numbers/dates dropped)                | −0.20        |
| ChrF character n-gram score                                   | informational |

For QA reports, `score_segment_full()` adds back-translation (translate output back to English, measure word overlap). Low overlap < 0.25 adds −0.15 penalty.

**Three tiers:**

- ≥ 0.55 → ✅ Pass
- 0.30–0.55 → ⚠️ Needs human review
- < 0.30 → ❌ Failed → silenced (no TTS)

---

## Translation Memory Architecture (`scripts/translation_memory.py`)

**Five-tier lookup priority:**

1. Exact match in human feedback corrections (highest trust)
2. Exact match in govt TM
3. 85% fuzzy match via `SequenceMatcher` across both stores
4. ML translation engines (IndicTrans2 / SeamlessM4T / NLLB)
5. LLM post-edit (optional — only if API key set in `.env`)

Human corrections are upweighted **3×** when exported for fine-tuning injection.
Correction log (`correction_log.jsonl`) provides full audit trail.

**TM files:**

```
translation_memory/
  govt_tm.jsonl         ← domain TM (starts empty, must be seeded)
  human_feedback.jsonl  ← human corrections
  correction_log.jsonl  ← audit trail
```

---

## Contract Compliance Layer

Direct hooks into KB tender contractual requirements:

| Requirement              | Implementation                                                           |
| ------------------------ | ------------------------------------------------------------------------ |
| §3.1 Content exclusions | Regex patterns block PM/President speeches and YouTube links             |
| §3.2 No transliteration | Automated script-range detection, scored and flagged                     |
| §4.2 CBP portal upload  | `cbp_uploader.py` — login + multi-asset package upload                |
| §5.1B Duration ratio    | >20% longer than original → approval flag in metadata JSON              |
| Deliverable 4.5.iv       | `generate_correction_report()` — Correction & Closure Report          |
| Payment Milestone 1      | `generate_inception_report()` — T0+15 days inception doc              |
| Deliverable 4.6          | `generate_completion_report()` — consolidated final report + glossary |
| Monthly delivery         | `generate_monthly_report()` — hours delivered per language            |

Every job writes to `audit.log` as structured JSON with model versions and git commit hash.

---

## Language Code Mapping (22 Languages)

| Code | Language  | Script     | IndicTrans2 Code | Notes                                    |
| ---- | --------- | ---------- | ---------------- | ---------------------------------------- |
| asm  | Assamese  | Bengali    | asm_Beng         |                                          |
| ben  | Bengali   | Bengali    | ben_Beng         |                                          |
| guj  | Gujarati  | Gujarati   | guj_Gujr         |                                          |
| hin  | Hindi     | Devanagari | hin_Deva         |                                          |
| kan  | Kannada   | Kannada    | kan_Knda         |                                          |
| mal  | Malayalam | Malayalam  | mal_Mlym         |                                          |
| mar  | Marathi   | Devanagari | mar_Deva         |                                          |
| ory  | Odia      | Odia       | ory_Orya         |                                          |
| pan  | Punjabi   | Gurmukhi   | pan_Guru         |                                          |
| tam  | Tamil     | Tamil      | tam_Taml         |                                          |
| tel  | Telugu    | Telugu     | tel_Telu         |                                          |
| bod  | Bodo      | Devanagari | brx_Deva         | ⚠️ Not Tibetan — Bodo uses Devanagari |
| doi  | Dogri     | Devanagari | doi_Deva         | Standalone MMS VITS:`mms-tts-dgo`      |
| kas  | Kashmiri  | Arabic     | kas_Arab         | MMS uses Urdu Arabic adapter             |
| kok  | Konkani   | Devanagari | gom_Deva         | Uses Goan Konkani flores200 code         |
| mni  | Manipuri  | Bengali    | mni_Beng         |                                          |
| mai  | Maithili  | Devanagari | mai_Deva         |                                          |
| nep  | Nepali    | Devanagari | npi_Deva         | flores200 code is`npi` not `nep`     |
| san  | Sanskrit  | Devanagari | san_Deva         | Via Hindi pivot                          |
| sat  | Santhali  | Ol Chiki   | sat_Olck         | Parler-TTS skips — goes direct to MMS   |
| snd  | Sindhi    | Arabic     | snd_Arab         | Parler-TTS skips — goes direct to MMS   |
| urd  | Urdu      | Arabic     | urd_Arab         |                                          |

---

## Strengths

- **Genuinely offline-first** — all models local, no external calls in hot path (LLM is opt-in)
- **Robust failure handling** — crash resume, completeness guards, per-segment retry mean partial work is never lost
- **Compliance-baked-in** — tender requirements coded directly into execution logic, not afterthoughts
- **Smart resource sharing** — single ASR pass shared across all 22 language workers in multi-GPU mode
- **Script-aware quality checks** — transliteration detector and script-range scoring understand Indian linguistics

## Weaknesses / Risks

- **TTS quality for rare languages** — `sat/kas/snd` fall through to MMS adapter proxies (Kashmiri → Urdu Arabic adapter), incorrect prosody expected
- **S2ST limited to 5 languages** — fast-path only for `hin/ben/kan/tel/urd`; other 17 always take slow path
- **Translation memory empty by default** — `govt_tm.jsonl` starts empty; needs seeding with real govt-verified term pairs
- **`kok` dialect risk** — uses `gom_Deva` (Goan Konkani), may not match all Konkani dialects
- **`bod` naming ambiguity** — internal code `bod` = Bodo (brx_Deva), but ISO 639-3 `bod` = Tibetan — could confuse future maintainers
- **No streaming progress** — UI Live Logs tab polls every 3s but pipeline is blocking; long jobs give no segment-level progress signal
- **Windows ASR throughput limit** — `num_workers=1` for faster-whisper (>1 deadlocks on Windows — no fork)

---

## Key Files Quick Reference

| File                                | Role                                              |
| ----------------------------------- | ------------------------------------------------- |
| `pipeline/dubbing_pipeline.py`    | Central orchestrator (69KB) — all pipeline logic |
| `pipeline/translator.py`          | Translation engines + token protection (47KB)     |
| `pipeline/tts.py`                 | TTS fallback chain (34KB)                         |
| `pipeline/asr.py`                 | ASR engine + segment merging (9.9KB)              |
| `pipeline/quality.py`             | Quality scoring (10.9KB)                          |
| `pipeline/retry.py`               | Checkpoint/resume + retry decorator (3.3KB)       |
| `pipeline/lang_config.py`         | All language code mappings (4.2KB)                |
| `pipeline/llm_enhancer.py`        | Optional LLM post-edit (6.4KB)                    |
| `pipeline/voice_clone.py`         | XTTS-v2 voice cloning (5.6KB)                     |
| `pipeline/video_processor.py`     | ffmpeg wrapper (18.6KB)                           |
| `pipeline/cbp_uploader.py`        | CBP portal upload (6.5KB)                         |
| `scripts/translation_memory.py`   | Govt TM + human feedback (13.9KB)                 |
| `scripts/dub.py`                  | CLI entry point (13.5KB)                          |
| `ui/app.py`                       | Gradio 8-tab UI (45.6KB)                          |
| `finetune/finetune_indictrans.py` | IndicTrans2 fine-tuning (17.2KB)                  |
| `finetune/ds_zero3.json`          | DeepSpeed ZeRO-3 multi-GPU config                 |
