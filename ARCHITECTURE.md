# KB Translation System — Architecture & Workflow
**iGOT Karmayogi | RFB IN-KBL-543730-NC-RFB**

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ENTRY POINTS                                 │
│                                                                     │
│   ┌──────────────┐          ┌──────────────────────────────────┐   │
│   │  Gradio UI   │          │         CLI (dub.py)             │   │
│   │  ui/app.py   │          │  --video --src --tgt --force     │   │
│   └──────┬───────┘          └────────────────┬─────────────────┘   │
│          └──────────────┬───────────────────-┘                     │
└─────────────────────────┼───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   DubbingPipeline (dubbing_pipeline.py)             │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  ASREngine   │  │  Translator  │  │  TTSEngine   │  (lazy load) │
│  │   asr.py     │  │translator.py │  │   tts.py     │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │VideoProcessor│  │  Glossary    │  │  Subtitles   │             │
│  │video_proc.py │  │ glossary.py  │  │ subtitles.py │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Quality    │  │  LangConfig  │  │  JobCheckpt  │             │
│  │  quality.py  │  │lang_config.py│  │   retry.py   │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MODEL LAYER                                 │
│                                                                     │
│  faster-whisper    IndicTrans2      Parler-TTS     SeamlessM4T      │
│  large-v3          (fine-tuned)     Indic          v2               │
│  models/indic_asr/ checkpoints/     models/        models/          │
│                    indictrans/      indic_parler_   seamless/        │
│                    en_indic/best/   tts/                            │
│                                                                     │
│                    NLLB-200         MMS-TTS                         │
│                    models/nllb/     models/mms/                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Pipeline Workflow

```
INPUT: MP4 / MP3 / WAV / FLAC
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  STEP 0 — Validation & Skip Check                   │
│  • File exists, format allowed, size ≤ 2GB          │
│  • If output already exists (>500KB) → skip         │
│  • force=True → delete existing outputs, re-run     │
│  • KB exclusion check (PM/President speech, YouTube)│
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1 — Audio Extraction                          │
│  ffmpeg → 16kHz mono WAV                            │
│  Cached in tmp/<job_id>/source.wav                  │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │  S2ST Fast Path?        │
          │  src + tgt both in      │
          │  SEAMLESS_S2ST_LANGS?   │
          │  (hin/ben/kan/tel/urd)  │
          └────────────┬────────────┘
               YES ▼        NO ▼
    ┌──────────────────┐    │
    │ SeamlessM4T S2ST │    │
    │ Direct speech →  │    │
    │ speech (no ASR,  │    │
    │ no TTS needed)   │    │
    │ → mux → OUTPUT   │    │
    └──────────────────┘    │
                            ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2 — ASR (Automatic Speech Recognition)        │
│  Model: faster-whisper large-v3                     │
│  • condition_on_previous_text=False                 │
│  • temperature=[0.0, 0.2, 0.4] (hallucination fix) │
│  • no_speech_threshold=0.6                          │
│  • compression_ratio_threshold=2.4                  │
│  Output: segments [{id, start, end, text, lang}]    │
│  Checkpoint saved → resume on crash                 │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3 — Translation                               │
│  GPU batch (single forward pass per language)       │
│                                                     │
│  Routing logic:                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ 1. IndicTrans2 (fine-tuned checkpoint)      │   │
│  │    checkpoints/indictrans/en_indic/best/    │   │
│  │    → falls back to models/indic_tr/         │   │
│  │    num_beams=5, no_repeat_ngram=3,          │   │
│  │    repetition_penalty=1.2                   │   │
│  │                                             │   │
│  │ 2. SeamlessM4T (text translation fallback)  │   │
│  │    for langs in SEAMLESS_CODES              │   │
│  │                                             │   │
│  │ 3. NLLB-200 (final fallback)                │   │
│  │    kok (Konkani) → NLLB only                │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Glossary injection → domain terms protected        │
│  Quality scoring per segment (heuristic + ChrF)     │
│  Checkpoint per segment → resume on crash           │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4 — TTS (Text-to-Speech)                      │
│                                                     │
│  Primary: Parler-TTS Indic                          │
│  • Single model, all 22 languages                   │
│  • Speaker desc: "speaks slowly and deliberately"   │
│                                                     │
│  Fallback: MMS-TTS (VITS)                           │
│  • length_scale=1.15 (15% slower, clearer)          │
│  • Low-pass filter at 7500Hz (reduces harshness)    │
│                                                     │
│  Output: per-segment WAV files in tmp/tts_segments/ │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5 — Audio Assembly                            │
│  • Each segment placed at exact original timestamp  │
│  • TTS sped up to fit slot (max 1.4x, was 2.0x)    │
│  • Hard trim to slot duration                       │
│  • 10ms fade-in only (no fade-out — was causing     │
│    audible dips between words)                      │
│  Output: dubbed.wav (exact original duration)       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 6 — Output Generation                         │
│  • ffmpeg mux: replace audio in video               │
│  • Stretch dubbed audio to exact video duration     │
│  • AAC 192k, -shortest flag                         │
│  • Duration ratio check (>1.2x → KB approval flag) │
│  • SRT + VTT subtitle generation                    │
│  • metadata.json (quality scores + transcript)      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
OUTPUT: output/<course_id>/<lang_code>/
        ├── <course_id>_<lang>.mp4
        ├── <course_id>_<lang>.srt
        ├── <course_id>_<lang>.vtt
        └── <course_id>_<lang>_metadata.json
```

---

## Translation Engine Routing

```
English Input
     │
     ▼
Is lang == "kok" (Konkani)?
     │
  YES▼                    NO▼
NLLB-200            IndicTrans2
(kok_Deva)          fine-tuned checkpoint
                    checkpoints/indictrans/en_indic/best/
                         │
                    Success? ──NO──► SeamlessM4T
                         │               │
                    YES  ▼          Success? ──NO──► NLLB-200
                    Output               │
                                    YES  ▼
                                    Output
```

### Language → Model Mapping

| Language | Code | IndicTrans2 | Seamless | NLLB | S2ST |
|----------|------|:-----------:|:--------:|:----:|:----:|
| Assamese | asm | ✅ | ✅ | ✅ | ❌ |
| Bengali | ben | ✅ | ✅ | ✅ | ✅ |
| Bodo | bod | ✅ (brx_Deva) | ❌ | ❌ | ❌ |
| Dogri | doi | ✅ | ❌ | ✅ | ❌ |
| Gujarati | guj | ✅ | ✅ | ✅ | ❌ |
| Hindi | hin | ✅ | ✅ | ✅ | ✅ |
| Kannada | kan | ✅ | ✅ | ✅ | ✅ |
| Kashmiri | kas | ✅ | ❌ | ✅ | ❌ |
| Konkani | kok | ❌ | ❌ | ✅ | ❌ |
| Maithili | mai | ✅ | ✅ | ✅ | ❌ |
| Malayalam | mal | ✅ | ✅ | ✅ | ❌ |
| Manipuri | mni | ✅ | ✅ | ✅ | ❌ |
| Marathi | mar | ✅ | ✅ | ✅ | ❌ |
| Nepali | nep | ✅ (npi_Deva) | ✅ (npi) | ✅ | ❌ |
| Odia | ory | ✅ | ✅ | ✅ | ❌ |
| Punjabi | pan | ✅ | ✅ | ✅ | ❌ |
| Sanskrit | san | ✅ | ❌ | ✅ | ❌ |
| Santhali | sat | ✅ | ✅ | ✅ | ❌ |
| Sindhi | snd | ✅ | ✅ | ✅ | ❌ |
| Tamil | tam | ✅ | ✅ | ✅ | ❌ |
| Telugu | tel | ✅ | ✅ | ✅ | ✅ |
| Urdu | urd | ✅ | ✅ | ✅ | ✅ |

---

## Component Architecture

### `pipeline/asr.py` — Speech Recognition
```
WAV (16kHz mono)
     │
     ▼
faster-whisper large-v3
• Hallucination prevention:
  - condition_on_previous_text=False
  - temperature=[0.0, 0.2, 0.4]
  - no_speech_threshold=0.6
  - compression_ratio_threshold=2.4
     │
     ▼
[{id, start, end, text, detected_lang}, ...]
```

### `pipeline/translator.py` — Translation
```
[texts], src_lang, tgt_lang
     │
     ▼
_load_indic_trans2(direction)
  └─ checks checkpoints/indictrans/<dir>/best/ first
  └─ falls back to models/indic_tr/<dir>/
     │
     ▼
GPU batch translate (single forward pass)
  num_beams=5, no_repeat_ngram_size=3, repetition_penalty=1.2
     │
     ▼
[{text, engine, score}, ...]
```

### `pipeline/tts.py` — Speech Synthesis
```
[{text, start, end, lang}, ...]
     │
     ├─► Parler-TTS Indic (primary)
     │   • "speaks slowly and deliberately"
     │   • Single model, all 22 langs
     │
     └─► MMS-TTS VITS (fallback)
         • length_scale=1.15
         • Low-pass filter 7500Hz
         • try/finally restores length_scale
     │
     ▼
[{audio_path, start, end, duration}, ...]
```

### `pipeline/video_processor.py` — Audio Assembly
```
TTS segments + original duration
     │
     ▼
assemble_dubbed_audio()
  For each segment:
  ├─ Place at exact original timestamp
  ├─ Speed up TTS to fit slot (max 1.4x)
  └─ Hard trim to slot, 10ms fade-in only
     │
     ▼
dubbed.wav (exact original duration)
     │
     ▼
replace_audio_in_video()
  ffmpeg: stretch to video duration, AAC 192k
     │
     ▼
output/<course>/<lang>/<course>_<lang>.mp4
```

---

## Checkpoint / Resume System

```
Job starts
     │
     ▼
JobCheckpoint(job_id) created
  └─ stored in checkpoints/jobs/<job_id>.json
     │
     ├─ ASR done → segments saved to checkpoint
     │
     ├─ Each translated segment → marked done in checkpoint
     │
     ├─ Crash / restart → resumes from last checkpoint
     │   (skips already-translated segments)
     │
     └─ Success → checkpoint cleared
```

---

## Output Structure

```
output/
└── <course_id>/
    ├── <lang_code>/
    │   ├── <course_id>_<lang>.mp4        ← dubbed video
    │   ├── <course_id>_<lang>.srt        ← subtitles (SRT)
    │   ├── <course_id>_<lang>.vtt        ← subtitles (WebVTT)
    │   ├── <course_id>_<lang>_metadata.json
    │   ├── <course_id>_<lang>_qa_cert.docx   ← QA certificate
    │   ├── <course_id>_quiz_<lang>.docx       ← translated quiz
    │   └── <course_id>_quiz_<lang>.xlsx
    └── <course_id>_metadata_all.xlsx     ← all-language metadata
```

---

## Model Loading Strategy

All models use **lazy loading** — loaded only on first use, not at startup:

```
DubbingPipeline.__init__()
  self._asr        = None   ← loaded on first transcribe call
  self._translator = None   ← loaded on first translate call
  self._tts        = None   ← loaded on first synthesize call

  self.video   = VideoProcessor()   ← no model, always ready
  self.glossary = GlossaryManager() ← lightweight, always ready
```

GPU memory is shared across all 22 languages — models stay loaded between languages in a batch run.

---

## Quality Scoring Pipeline

```
Translated segment
     │
     ├─► Heuristic score
     │   • Length ratio check
     │   • Transliteration detection
     │   • Empty output detection
     │
     ├─► ChrF score (character n-gram F-score)
     │
     └─► Back-translation score (optional, for QA reports)
          │
          ▼
     quality_summary:
       avg_score, pass_rate, avg_chrf,
       needs_review_count, failed_count,
       duration_ratio, duration_ratio_flag
```

---

## KB Tender Compliance Features

| Requirement | Implementation |
|-------------|---------------|
| 22 scheduled Indian languages | `ALL_22` in `lang_config.py` |
| Offline / data residency | All models run locally, no API calls |
| Content exclusion (PM/President speech) | `_EXCLUSION_PATTERNS` in `dubbing_pipeline.py` |
| Duration ratio check (>20% → approval) | `DURATION_RATIO_THRESHOLD = 1.20` |
| QA self-certification report | `generate_qa_report()` → `.docx` |
| Inception report (T0+15 days) | `generate_inception_report()` → `.docx` |
| Monthly submission reports | `generate_monthly_report()` → `.docx` |
| Correction & closure report | `generate_correction_report()` → `.docx` |
| Consolidated completion report | `generate_completion_report()` → `.docx` |
| Subtitles (SRT + VTT) | `subtitles.py` |
| Glossary enforcement | `glossary.py` injected at translate step |
| Metadata translation (title, desc, quiz) | `translate_metadata()`, `translate_quiz()` |

---

## Directory Structure

```
project/
├── pipeline/                   # Core inference
│   ├── asr.py                  # faster-whisper large-v3
│   ├── translator.py           # IndicTrans2 → Seamless → NLLB
│   ├── tts.py                  # Parler-TTS + MMS fallback
│   ├── dubbing_pipeline.py     # Orchestration + KB compliance
│   ├── video_processor.py      # Audio assembly + ffmpeg mux
│   ├── glossary.py             # Domain glossary injection
│   ├── lang_config.py          # Language codes + model routing
│   ├── quality.py              # Translation quality scoring
│   ├── subtitles.py            # SRT/VTT generation
│   └── lang_detect.py          # Per-segment language detection
│
├── ui/app.py                   # Gradio web UI
├── scripts/dub.py              # CLI entry point
│
├── models/                     # Downloaded weights (not in git)
│   ├── indic_asr/              # faster-whisper large-v3 (~3GB)
│   ├── indic_tr/               # IndicTrans2 base (~3.6GB total)
│   ├── indic_parler_tts/       # Parler-TTS Indic (~1.5GB)
│   ├── seamless/               # SeamlessM4Tv2 (~10GB)
│   ├── nllb/                   # NLLB-200 (~2.4GB)
│   └── mms/                    # MMS-TTS (~1.5GB)
│
├── checkpoints/
│   ├── indictrans/
│   │   ├── en_indic/best/      # Fine-tuned: English → Indic (ACTIVE)
│   │   ├── indic_en/best/      # Fine-tuned: Indic → English
│   │   └── indic_indic/best/   # Fine-tuned: Indic → Indic
│   └── jobs/                   # Runtime crash-resume checkpoints
│
├── glossary/                   # Domain term files
├── datasets/parallel/          # Parallel training data (not in git)
└── output/                     # All dubbed outputs
```
