# KB Translation System — Project Report
**iGOT Karmayogi | RFB IN-KBL-543730-NC-RFB**

---

## 1. Executive Summary

The KB Translation System is a fully offline, end-to-end AI dubbing pipeline built for the iGOT Karmayogi platform under tender RFB IN-KBL-543730-NC-RFB. It automates the translation and dubbing of government training content into all 22 constitutionally scheduled Indian languages using a three-stage pipeline: Automatic Speech Recognition (ASR) → Neural Machine Translation → Text-to-Speech (TTS).

All models run locally on-premise. No internet connection, no external API keys, and no data leaves the system — satisfying the Government of India's data sovereignty and offline deployment requirements.

---

## 2. Problem Statement

| Challenge | Detail |
|-----------|--------|
| Scale | 1,105 hours of iGOT content × 22 languages = 24,310 dubbed hours required |
| Cost | Manual dubbing costs ₹5,000–₹15,000/min per language — prohibitive at scale |
| Data Sovereignty | Government content cannot be sent to external APIs (OpenAI, Google, AWS) |
| Offline Requirement | Deployment in low-connectivity government data centres |
| Quality SLA | KB tender §5.1B mandates 98% linguistic accuracy with self-certification QA reports |
| Exclusions | PM/President speeches and YouTube-only content blocked per KB tender §3.1 |

---

## 3. System Architecture

```
Input MP4 / MP3 / WAV / DOCX / PDF
        │
        ▼
[STEP 1]  Audio Extraction — ffmpeg → 16kHz mono WAV
          Stale cache detection (re-extract if input newer than cached WAV)
        │
        ▼
[STEP 1b] SeamlessM4T S2ST Fast Path (Indic→Indic pairs only)
          hin ↔ ben ↔ kan ↔ tel ↔ urd
          → if successful: mux + return early (skips ASR+TTS)
        │
        ▼
[STEP 2]  ASR — faster-whisper large-v3
          Sentence-level segments with timestamps
          Auto language detection (lang="auto")
          Hallucination guard: condition_on_previous_text=False
          Multi-temperature fallback [0.0, 0.2, 0.4]
          ASR segment repair (merge mid-sentence splits)
        │
        ▼
[STEP 3]  Translation — IndicTrans2 GPU batch → SeamlessM4T → NLLB-200
          Factual token protection (__F0__ placeholders)
          Format token protection (__FMT0__ placeholders)
          Non-translatable passthrough (URLs, code, paths)
          Glossary injection + quality scoring per segment
          Wrong-language drift guards (Maithili/Bodo/Hindi)
          Final quality check (10 rules)
        │
        ▼
[STEP 4]  TTS — Parler-TTS Large → MMS-TTS (standalone VITS)
          Per-segment WAV files
          Voice cloning via XTTS-v2 (optional, KB Tier 2)
          RNG pinned once per video for consistent voice identity
        │
        ▼
[STEP 5]  Audio Assembly
          Place at original timestamps
          Fit-to-slot (max 1.35× speed)
          dubbed.wav (exact original duration, padded with silence)
        │
        ▼
[STEP 6]  Output
          SRT + VTT subtitles generated
          ffmpeg mux: replace audio in video
          Duration ratio check (KB tender §5.1B — warn if >20% longer)
          Metadata JSON with quality scores + transcript + provenance
        │
        ▼
output/<course_id>/<lang>/<course>_<lang>.mp4 + .srt + .vtt + _metadata.json
```

---

## 4. Project Structure

```
project/
├── pipeline/                      # Core inference — all model logic
│   ├── asr.py                     # ASR: faster-whisper large-v3
│   ├── translator.py              # Translation: IndicTrans2 → SeamlessM4T → NLLB-200
│   ├── tts.py                     # TTS: Parler-TTS Large → MMS-TTS → XTTS-v2
│   ├── dubbing_pipeline.py        # End-to-end orchestration, 6-step pipeline, multi-GPU
│   ├── video_processor.py         # ffmpeg audio extraction, assembly, video muxing
│   ├── glossary.py                # Per-language glossary injection (22 × JSON files)
│   ├── lang_config.py             # Language codes for all 3 engines + S2ST langs
│   ├── quality.py                 # Heuristic + ChrF + back-translation quality scoring
│   ├── subtitles.py               # SRT + VTT subtitle generation
│   ├── lang_detect.py             # Per-segment language detection + tagging
│   ├── doc_extractor.py           # DOCX/PDF/TXT extraction + format-preserving translation
│   ├── voice_clone.py             # Voice cloning: Coqui XTTS-v2
│   ├── cbp_uploader.py            # CBP portal upload (KB tender §4.2)
│   ├── llm_enhancer.py            # LLM post-edit (Groq/Gemini/OpenRouter — optional)
│   ├── logger.py                  # Structured JSON logging (pipeline.log + audit.log)
│   └── retry.py                   # Retry decorator + JobCheckpoint (crash-safe resume)
│
├── ui/
│   ├── app.py                     # Gradio web UI — 8 tabs
│   └── reviewer.py                # Human review + DOCX certificate export
│
├── scripts/
│   ├── dub.py                     # CLI entry point — video dubbing + reports
│   ├── translate.py               # CLI text/audio/batch/course translation
│   ├── translation_memory.py      # Govt TM + human feedback manager
│   ├── download_models.py         # Download all model weights to models/
│   ├── download_datasets.py       # Download parallel training data to datasets/
│   └── test_pipeline.py           # Smoke test — runs a short dub end-to-end
│
├── finetune/
│   ├── finetune_indictrans.py     # Fine-tune IndicTrans2 on parallel data
│   ├── finetune_seamless.py       # Fine-tune SeamlessM4T
│   └── ds_zero3.json              # DeepSpeed ZeRO-3 config for multi-GPU fine-tuning
│
├── glossary/                      # 22 × <lang>.json domain glossary files
├── models/                        # Downloaded weights (not in git)
├── datasets/                      # ASR + parallel training data (22 langs)
├── checkpoints/                   # Fine-tuned model checkpoints
├── translation_memory/            # govt_tm.jsonl + human_feedback.jsonl
├── input/                         # Source videos / documents
├── output/                        # All dubbed outputs
└── logs/                          # pipeline.log + audit.log
```


---

## 5. AI Models

### 5.1 ASR — Automatic Speech Recognition

| Property | Detail |
|----------|--------|
| Model | faster-whisper large-v3 (CTranslate2 optimised) |
| Path | `models/indic_asr/` |
| Size | ~3 GB |
| Languages | All 22 scheduled Indian languages + auto-detect |
| Features | Sentence-level timestamps, hallucination guard, multi-temperature fallback |

**Hallucination guards:**
- `condition_on_previous_text=False` — prevents context bleed between segments
- Multi-temperature fallback: `[0.0, 0.2, 0.4]` — retries with higher temperature if output is suspicious
- Nastaliq normalisation for Urdu/Kashmiri/Sindhi Arabic-script ASR output
- ASR segment repair: merges mid-sentence splits using virama detection, dangling preposition detection, and 200ms gap threshold

### 5.2 Translation Engines

| Engine | Model | Path | Size | Primary Use |
|--------|-------|------|------|-------------|
| IndicTrans2 | AI4Bharat en_indic / indic_en / indic_indic | `models/indic_tr/` | ~1.2 GB × 3 | Primary for 16 languages |
| SeamlessM4Tv2 | facebook/seamless-m4t-v2-large | `models/seamless/` | ~10 GB | Fallback + S2ST |
| NLLB-200 | facebook/nllb-200-distilled-600M | `models/nllb/` | ~2.4 GB | Final fallback + kas/snd/kok primary |

**Translation Engine Routing:**

| Language Group | Primary | Fallback 1 | Fallback 2 |
|----------------|---------|------------|------------|
| hin, ben, tam, tel, kan, mal, mar, guj, pan, ory, asm, urd, nep, mai, doi, bod | IndicTrans2 (fine-tuned) | SeamlessM4T | NLLB-200 |
| mni | SeamlessM4T (primary) | IndicTrans2 pivot | NLLB-200 |
| sat | IndicTrans2 via Hindi pivot | NLLB-200 | — |
| san | IndicTrans2 | NLLB-200 | — |
| kok, snd, kas | NLLB-200 (primary) | SeamlessM4T | — |

**S2ST (Speech-to-Speech):** SeamlessM4T only, Indic→Indic pairs: `hin ↔ ben ↔ kan ↔ tel ↔ urd`

**Token Protection System:**
- `__F0__` placeholders — numbers, dates, currency, measurements (factual tokens)
- `__FMT0__` placeholders — `{name}`, `%s`, `${var}`, `{{jinja}}` (format tokens)
- `__NT0__` placeholders — URLs, code, file paths, @mentions (non-translatable tokens)
- Final quality check (10 rules): accuracy, completeness, grammar, fluency, consistency, corruption, placeholder-free, mixed-lang, formatting, professional

**Wrong-Language Drift Guards:**
- Maithili drift in Hindi output: detected via exclusive verb markers (अछि/छथि/करैत), retried via NLLB
- Bodo drift in Maithili output: detected via Bodo-exclusive morphemes (लांओ/खालामो), retried via NLLB
- Hindi drift in Bodo output: detected via Hindi verb markers (है/होता/करता), retried via NLLB
- Subject-drop guard for Hindi: structural check for transitive verb without nominative subject

### 5.3 TTS Engines

| Engine | Languages | Notes |
|--------|-----------|-------|
| Parler-TTS Indic Large | hin, mar, nep, mai, san (primary) | 44kHz, GPU batch, fixed seed per lang |
| Parler-TTS Indic Mini | Same 5 langs (fallback) | Used if large model absent |
| MMS-TTS standalone VITS | All 22 via per-lang models | `models/mms_standalone/<lang>/` |
| MMS-TTS adapter | All 22 via shared base + adapters | `models/mms/adapter.<lang>.safetensors` |
| Coqui XTTS-v2 | hin/ben/tam/tel/kan/mal/mar/guj/pan/urd | Last-resort fallback + voice cloning |

**TTS Routing Logic:**
- Dravidian langs (tam/tel/kan/mal): MMS-VITS primary — Parler amplitude too low without dedicated fine-tune
- Bengali-script family (ben/asm/mni): MMS-VITS primary
- Arabic-script family (urd/kas): MMS-VITS primary
- Devanagari family (hin/mar/nep/mai/san): Parler-TTS Indic Large primary

**Voice Consistency:**
- Single fixed RNG seed (42) pinned once before primer warmup — identical voice throughout entire video
- Parler text encoder pre-computed once per video — reused for all segments (no voice drift)
- VITS RNG state pinned after warmup — natural RNG advance across all chunks (no per-segment reset)
- Batch size 4 for Parler — segments sorted by token length to minimise padding waste

---

## 6. Language Coverage

All 22 constitutionally scheduled Indian languages:

| Code | Language | Script | Translation Engine | TTS Engine |
|------|----------|--------|--------------------|------------|
| asm | Assamese | Bengali | IndicTrans2 | MMS-VITS |
| ben | Bengali | Bengali | IndicTrans2 | MMS-VITS |
| bod | Bodo | Devanagari (brx_Deva) | IndicTrans2 | MMS-VITS |
| doi | Dogri | Devanagari | IndicTrans2 | MMS-VITS |
| guj | Gujarati | Gujarati | IndicTrans2 | MMS-VITS |
| hin | Hindi | Devanagari | IndicTrans2 | Parler-TTS Large |
| kan | Kannada | Kannada | IndicTrans2 | MMS-VITS |
| kas | Kashmiri | Arabic (Nastaliq) | NLLB-200 | MMS-VITS |
| kok | Konkani | Devanagari (gom_Deva) | NLLB-200 | MMS-VITS |
| mai | Maithili | Devanagari | IndicTrans2 | Parler-TTS Large |
| mal | Malayalam | Malayalam | IndicTrans2 | MMS-VITS |
| mar | Marathi | Devanagari | IndicTrans2 | Parler-TTS Large |
| mni | Manipuri | Bengali | SeamlessM4T | MMS-VITS |
| nep | Nepali | Devanagari | IndicTrans2 | Parler-TTS Large |
| ory | Odia | Odia | IndicTrans2 | MMS-VITS |
| pan | Punjabi | Gurmukhi | IndicTrans2 | MMS-VITS |
| san | Sanskrit | Devanagari | IndicTrans2 | Parler-TTS Large |
| sat | Santhali | Ol Chiki | IndicTrans2 pivot | MMS-VITS |
| snd | Sindhi | Arabic | NLLB-200 | MMS-VITS |
| tam | Tamil | Tamil | IndicTrans2 | MMS-VITS |
| tel | Telugu | Telugu | IndicTrans2 | MMS-VITS |
| urd | Urdu | Arabic (Nastaliq) | IndicTrans2 | MMS-VITS |


---

## 7. Quality Scoring System

Every translated segment is scored 0–1 automatically using three methods:

### 7.1 Scoring Methods

| Method | Description |
|--------|-------------|
| Heuristic | Length ratio, source language leakage, repetition loops, untranslated detection, transliteration detection, factual token preservation |
| ChrF | Character n-gram F-score (β=2, n=6) — works well for Indic scripts |
| Back-translation | Translate output back to source, measure word overlap |

### 7.2 Quality Thresholds

| Score | Status | Action |
|-------|--------|--------|
| ≥ 0.55 | ✅ Pass | Accepted |
| 0.30–0.55 | ⚠️ Review | Flagged for human review |
| < 0.30 | ❌ Failed | Flagged — segment still sent to TTS (silence is worse than imperfect translation) |

### 7.3 Heuristic Checks (8 rules)

1. Length ratio — flag if translated length < 0.3× or > 4× source
2. Source language leakage — flag if native script chars < 35% of total alpha chars
3. Repetition loop — flag if 4+ consecutive identical words
4. Untranslated — flag if output is exact copy of source or >80% Latin for non-Latin target
5. Too short — flag if source ≥ 5 words but translation < 2 words
6. Transliteration detection — flag if Latin chars > 60% of total alpha (KB tender §3.2)
7. Factual token preservation — flag if numbers/dates/currency missing from translation
8. ChrF — computed for same-script pairs only

### 7.4 Final Quality Check (10 rules)

Applied as a final gate before returning any translation:

1. Accuracy — non-empty output for non-empty source
2. Completeness — translated length ≥ 35% of source (Devanagari) or 20% (other scripts)
3. Grammar — sentence-initial capitalisation (Latin targets)
4. Fluency — collapse 3+ identical punctuation runs
5. Consistency — all placeholder tokens restored
6. Corruption-free — no U+FFFD replacement chars, no null bytes
7. Placeholder-free — no `__NTn__` / `__Fn__` / `__FMTn__` artifacts
8. Mixed-lang-free — re-run foreign script stripping
9. Formatting — normalise whitespace
10. Professional — strip debug/internal tokens (UNK, PAD, BOS, EOS, MASK)

---

## 8. Key Pipeline Features

### 8.1 Reliability & Safety

| Feature | Detail |
|---------|--------|
| Checkpoint/resume | Crashes mid-job resume from last completed segment — no restart from zero |
| Force re-run | `--force` clears both output files and ASR/translation checkpoint |
| Concurrent job protection | Per-(course_id, lang) threading lock prevents duplicate jobs |
| Input validation | File existence, format check (9 allowed extensions), 2GB size limit |
| Stale cache detection | source.wav re-extracted if input video is newer than cached WAV |
| Audit trail | Every job start/success/failure written to `logs/audit.log` as JSON |

### 8.2 Translation Safety

| Feature | Detail |
|---------|--------|
| Factual token protection | Numbers, dates, currency, measurements preserved via `__F0__` placeholders |
| Non-translatable passthrough | URLs, code, file paths, @mentions passed through unchanged |
| Format token protection | `{name}`, `%s`, `${var}`, `{{jinja}}` preserved via `__FMT0__` placeholders |
| Completeness guard | Empty translation for non-empty source triggers per-segment retry, then source fallback |
| Exclusion detection | PM/President speeches and YouTube-only content blocked per KB tender §3.1 |

### 8.3 Audio Quality

| Feature | Detail |
|---------|--------|
| Fit-to-slot | TTS audio sped up max 1.35× to fit original timestamp slot; hard-trimmed if still over |
| Duration ratio check | Warns if dubbed output >20% longer than original (KB tender §5.1B) |
| Post-processing | High-pass filter at 80Hz, low-pass at 9500Hz (MMS), normalise to -3 dBFS |
| Leading silence trim | Strips 100–300ms garbled preamble from Parler-TTS output |
| Voice consistency | Single RNG seed pinned once per video — identical voice throughout |

### 8.4 Multi-GPU Support

```
ASR runs ONCE in main process (shared across all workers)
         │
         ▼
Round-robin distribute target languages across N GPUs
GPU 0: [asm, kan, mai, pan, sat, urd]
GPU 1: [ben, kas, mal, san, snd]
GPU 2: [bod, kok, mar, tam, tel]
GPU 3: [doi, guj, hin, mni, nep, ory]
         │
         ▼
Each worker: translate + TTS + assemble (independent)
         │
         ▼
Merge results
```

---

## 9. Web UI — 8 Tabs

| Tab | Purpose |
|-----|---------|
| 🎬 Dub Video / Audio | Upload MP4/MP3, select languages, run full pipeline |
| 📄 Translate Document | Translate DOCX/TXT/JSON quiz & metadata (PDF blocked per §3.1) |
| 📋 QA Certificate | Generate self-certification report (.docx) |
| 👤 Human Review | Approve/correct/reject segments, export review certificate |
| ⚙️ Settings | HF token, output folder |
| 📅 Monthly Delivery | Track hours delivered, export submission reports (.xlsx) |
| 📖 Glossary | Build & export standardised terminology glossary (.xlsx) |
| 📊 Live Logs | Real-time pipeline log stream (auto-refresh 3s) |

---

## 10. CLI Reference

```bash
# Dub video — single language
python scripts/dub.py --video course.mp4 --src eng --tgt hin --course-id MyCourse

# Dub video — all 22 languages
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse

# Force re-run (clears checkpoint + output)
python scripts/dub.py --video course.mp4 --src eng --tgt hin --force

# Multi-GPU parallel dubbing
python scripts/dub.py --video course.mp4 --src eng --tgt all --num-gpus 4

# Voice cloning (KB Tier 2)
python scripts/dub.py --video course.mp4 --src eng --tgt hin --voice-clone --reference-audio spk.wav

# Full course: dub + metadata + quiz + QA report + CBP upload
python scripts/dub.py --video course.mp4 --src eng --tgt all --full \
    --metadata meta.json --quiz quiz.json --course-id MyCourse --upload-cbp

# Text translation
python scripts/translate.py --text "Hello" --src eng --tgt hin
python scripts/translate.py --batch input.txt --src eng --tgt all
python scripts/translate.py --audio speech.wav --src hin --tgt ben

# Translation memory
python scripts/translation_memory.py add --src "Competency Framework" --tgt "दक्षता ढांचा" --tgt-lang hin
python scripts/translation_memory.py stats
python scripts/translation_memory.py lookup --src "Competency" --tgt-lang hin

# Generate monthly submission report
python scripts/dub.py --run-monthly-report --monthly-report results.json --month 3
```

---

## 11. Translation Memory

Government-verified translations and human corrections stored in `translation_memory/` and automatically injected into the pipeline via exact + fuzzy matching (85% threshold).

| File | Purpose |
|------|---------|
| `govt_tm.jsonl` | Government-verified translations |
| `human_feedback.jsonl` | Human corrections from reviewer UI |
| `correction_log.jsonl` | Audit log of all corrections |

---

## 12. Fine-Tuning

### 12.1 IndicTrans2 Fine-Tuning

```bash
# Fine-tune all 3 directions
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_indictrans.py --direction en_indic
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_indictrans.py --direction indic_en
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_indictrans.py --direction indic_indic
```

Checkpoints saved to `checkpoints/indictrans/<direction>/best/` — picked up automatically by the pipeline.

### 12.2 SeamlessM4T Fine-Tuning

```bash
accelerate launch --num_processes=4 --mixed_precision=bf16 finetune/finetune_seamless.py
```

### 12.3 Dataset Structure

Each language requires:
```
datasets/parallel/<lang_code>/train.jsonl
datasets/parallel/<lang_code>/dev.jsonl
datasets/parallel/<lang_code>/test.jsonl
```
Each line: `{"src": "...", "tgt": "...", "src_lang": "eng", "tgt_lang": "<lang>"}`

### 12.4 DeepSpeed ZeRO-3

`finetune/ds_zero3.json` — for large-scale multi-GPU fine-tuning. Requires `accelerate config` once before launching.

---

## 13. Output Structure

```
output/<course_id>/<lang_code>/
    <course_id>_<lang>.mp4              ← dubbed video
    <course_id>_<lang>.srt              ← subtitles (SRT)
    <course_id>_<lang>.vtt              ← web subtitles (VTT)
    <course_id>_<lang>_metadata.json    ← quality scores + transcript + provenance
    <course_id>_<lang>_qa_cert.docx     ← QA self-certification (KB tender)
    <course_id>_quiz_<lang>.docx        ← translated quiz (Word)
    <course_id>_quiz_<lang>.xlsx        ← translated quiz (Excel)
    <course_id>_metadata_<lang>.docx    ← translated metadata (Word)
```

### Metadata JSON Schema

```json
{
  "course_id": "MyCourse",
  "source_lang": "eng",
  "target_lang": "hin",
  "target_lang_name": "Hindi",
  "duration_original_s": 120.5,
  "duration_output_s": 118.3,
  "segment_count": 42,
  "quality_summary": {
    "total": 42,
    "avg_score": 0.82,
    "avg_chrf": 0.61,
    "avg_back_translation": 0.74,
    "needs_review": 3,
    "failed": 0,
    "pass_rate": 0.929,
    "duration_ratio": 0.981,
    "duration_ratio_flag": false
  },
  "transcript": [...],
  "translations": [...],
  "provenance": {
    "model_versions": {...},
    "host": "server-name",
    "generated_at": "2025-01-01T12:00:00",
    "contract": "RFB IN-KBL-543730-NC-RFB"
  }
}
```

---

## 14. Models & Storage Requirements

| Model | Path | Size |
|-------|------|------|
| faster-whisper large-v3 | `models/indic_asr/` | ~3 GB |
| IndicTrans2 en_indic | `models/indic_tr/en_indic/` | ~1.2 GB |
| IndicTrans2 indic_en | `models/indic_tr/indic_en/` | ~1.2 GB |
| IndicTrans2 indic_indic | `models/indic_tr/indic_indic/` | ~1.2 GB |
| Parler-TTS Indic Large | `models/indic_parler_tts_large/` | ~3.6 GB |
| Parler-TTS Indic Mini | `models/indic_parler_tts/` | ~1.5 GB |
| SeamlessM4Tv2 | `models/seamless/` | ~10 GB |
| NLLB-200 | `models/nllb/` | ~2.4 GB |
| MMS-TTS standalone VITS | `models/mms_standalone/` | ~0.1 GB × 18 langs |
| Flan-T5 Large (Parler text encoder) | `models/flan_t5_large/` | ~0.8 GB |
| **Total** | | **~28 GB** |

```bash
# Download all models
python scripts/download_models.py

# Download datasets
python scripts/download_datasets.py

# Verify 22-lang coverage
python scripts/check_gaps.py
```

---

## 15. Dependencies

```
# Core
torch (CUDA 12.1)
transformers>=4.40.0
accelerate>=0.26.0
safetensors>=0.4.0
sentencepiece>=0.1.99

# ASR
faster-whisper>=1.0.0

# Translation
IndicTransToolkit>=0.1.0

# TTS
parler-tts>=0.2.2

# Audio
soundfile>=0.12.1
librosa>=0.10.0
scipy>=1.11.0
numpy>=1.24.0
resampy>=0.4.2

# Video
imageio-ffmpeg>=0.4.9

# UI
gradio>=4.0.0

# Documents
python-docx>=1.1.0
openpyxl>=3.1.0
pdfplumber>=0.10.0

# Language detection
lingua-language-detector>=2.0.0

# Utilities
python-dotenv>=1.0.0
huggingface_hub>=0.20.0
requests>=2.31.0
datasets>=2.18.0
```

---

## 16. KB Tender Compliance

| Requirement | Implementation |
|-------------|----------------|
| §3.1 — Content exclusions | PM/President speech patterns + YouTube URL detection block translation |
| §3.2 — No transliteration | Transliteration detection in quality scorer; score penalty -0.35 |
| §4.2 — CBP portal upload | `pipeline/cbp_uploader.py` — auto-upload MP4/MP3/SRT/VTT/DOCX/XLSX |
| §5.1B — Duration ratio | Warn if dubbed output >20% longer; flag in metadata JSON |
| §5.1B — 98% accuracy SLA | Heuristic + ChrF + back-translation scoring; QA self-certification DOCX |
| SoW 3.4 — Output formats | MP4, MP3, SRT, VTT, DOCX (quiz + metadata), XLSX (quiz + metadata) |
| Deliverables 4.5.iv | Correction & Closure Report generator (`generate_correction_report`) |
| Deliverables 4.6 | Consolidated Completion Report generator (`generate_completion_report`) |
| Payment Milestone 1 | Inception Report generator (`generate_inception_report`) |
| Data residency | All models run on-premise; no data leaves the system |

### KB Tier 2 — Voice Cloning

```bash
python scripts/dub.py --video course.mp4 --src eng --tgt hin \
    --voice-clone --reference-audio speaker.wav
```

Supported: `hin ben guj mar tam tel kan mal pan urd`
Engine: Coqui XTTS-v2 (Apache 2.0, fully offline)

### CBP Portal Upload

```bash
# Set in .env
CBP_USERNAME=your_username
CBP_PASSWORD=your_password

# Upload after dubbing
python scripts/dub.py --video course.mp4 --src eng --tgt all --full --upload-cbp
```

---

## 17. Optional LLM Post-Edit Enhancement

Set any one key in `.env` to activate — pipeline works fully offline without it:

```
GROQ_API_KEY=gsk_...        # free tier, llama-3.3-70b
GEMINI_API_KEY=AIza...      # gemini-1.5-flash
OPENROUTER_API_KEY=sk-...   # meta-llama/llama-3.3-70b-instruct:free
```

---

## 18. Logging & Audit

| Log File | Content |
|----------|---------|
| `logs/pipeline.log` | Structured JSON — all pipeline events, quality scores, errors |
| `logs/audit.log` | Job start / success / failure events with timestamps and host |

Every audit entry includes: `event`, `job_id`, `file`, `src`, `tgt`, `course_id`, `host`, `elapsed_s`, `output`, `quality`.

---

## 19. Quick Start

```bash
# 1. Install PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download models (~28 GB)
python scripts/download_models.py

# 4. Run the UI
python ui/app.py

# 5. CLI — dub a single language
python scripts/dub.py --video course.mp4 --src eng --tgt hin --course-id MyCourse --output output

# 6. CLI — dub all 22 languages (4 GPUs)
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse --num-gpus 4

# 7. Smoke test
python scripts/test_pipeline.py
```

---

## 20. Contract Summary

| Item | Detail |
|------|--------|
| Contract | RFB IN-KBL-543730-NC-RFB |
| Client | iGOT Karmayogi, Government of India |
| Scope | 1,105 hours × 22 languages = 24,310 dubbed hours |
| Duration | 11 months |
| Delivery | Monthly batches (50–125 hours/month) |
| Quality SLA | 98% linguistic accuracy per KB tender §5.1B |
| Data Residency | 100% on-premise, no external API calls |
| Output Formats | MP4, MP3, SRT, VTT, DOCX, XLSX per language per course |
| Portal | CBP portal (cbp.igotkarmayogi.gov.in) — auto-upload after dubbing |

---

*Report generated from source code analysis of KB Translation System v1.0*
*Contract: RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi*

---

## 21. Hardware & Software Requirements

### 21.1 Hardware — Actual System Used

#### Workstation

| Component | Specification |
|-----------|---------------|
| **Manufacturer** | Dell Inc. (Board: 01G0M6) |
| **OS** | Microsoft Windows 11 Pro for Workstations (Build 22631) |
| **CPU** | Intel Xeon w9-3495X |
| **CPU Cores** | 56 physical cores / 112 logical threads |
| **CPU Base Clock** | 1896 MHz (boost-capable) |
| **RAM** | 128 GB DDR5 (2 × 64 GB @ 4800 MT/s, Samsung) |

#### GPU Configuration — 4 × NVIDIA RTX A6000

| Property | Per GPU | Total (4 GPUs) |
|----------|---------|----------------|
| **Model** | NVIDIA RTX A6000 | — |
| **VRAM** | 48 GB GDDR6 (49,140 MiB) | 192 GB |
| **CUDA Compute Capability** | 8.6 (Ampere) | — |
| **Driver Version** | 596.72 | — |
| **PCIe** | Gen 1 × 16 | — |
| **GPU 0 UUID** | GPU-ca8e8d61-9d5e-b0b4-0839-216b73c211aa | — |
| **GPU 1 UUID** | GPU-c9c51932-d9e8-3217-fdcf-b8dd1f48256c | — |
| **GPU 2 UUID** | GPU-96be531b-fe3d-bb8a-f85d-88589eabc655 | — |
| **GPU 3 UUID** | GPU-a7afed18-c60b-bad9-7211-fbdc62441cc2 | — |

#### Storage

| Drive | Model | Capacity | Type |
|-------|-------|----------|------|
| Primary (OS + Models) | Kioxia NVMe KXG80ZN84T09 | 4 TB | NVMe SSD |
| Secondary NVMe | Kioxia NVMe KXG80ZN84T09 | 4 TB | NVMe SSD |
| HDD 1 | Seagate ST12000NM002J-2TY133 | 12 TB | SATA HDD |
| HDD 2 | Seagate ST12000NM002J-2TY133 | 12 TB | SATA HDD |
| HDD 3 | Seagate ST12000NM002J-2TY133 | 12 TB | SATA HDD |
| HDD 4 | Seagate ST12000NM002J-2TY133 | 12 TB | SATA HDD |
| HDD 5 | Seagate ST12000NM002J-2TY133 | ~12 TB | SATA HDD |
| **Total Storage** | | **~80 TB** | |

**Storage allocation:**
- NVMe SSD: OS, Python environment, model weights (~28 GB), active job temp files
- HDD array: input videos, output dubbed files, datasets, checkpoints, logs

---

### 21.2 Software — Actual Installed Versions

#### Operating System & Runtime

| Software | Version |
|----------|---------|
| OS | Windows 11 Pro for Workstations 10.0.22631 |
| Python | 3.11.15 |
| NVIDIA Driver | 596.72 |
| CUDA Toolkit | 12.4 (via PyTorch cu124 build) |

#### Core Deep Learning

| Package | Version | Role |
|---------|---------|------|
| torch | 2.6.0+cu124 | GPU tensor ops, model inference |
| transformers | 4.46.1 | IndicTrans2, SeamlessM4T, NLLB-200, MMS-TTS, Parler-TTS |
| accelerate | 1.14.0 | Multi-GPU training + inference |
| safetensors | 0.8.0 | Fast model weight loading |
| sentencepiece | 0.2.2 | Tokenisation for IndicTrans2 / NLLB |
| ctranslate2 | 4.8.1 | CTranslate2 backend for faster-whisper |

#### ASR

| Package | Version | Role |
|---------|---------|------|
| faster-whisper | 1.2.1 | ASR engine (CTranslate2-optimised Whisper large-v3) |

#### Translation

| Package | Version | Role |
|---------|---------|------|
| indictranstoolkit | 1.1.1 | IndicTrans2 pre/post-processing (IndicProcessor) |

#### TTS

| Package | Version | Role |
|---------|---------|------|
| parler_tts | 0.2.2 | Parler-TTS Indic Large/Mini inference |

#### Audio Processing

| Package | Version | Role |
|---------|---------|------|
| soundfile | 0.14.0 | WAV read/write (libsndfile backend) |
| librosa | 0.11.0 | Audio resampling, pitch shift |
| scipy | 1.17.1 | Butterworth filters (high-pass/low-pass post-processing) |
| numpy | 1.26.4 | Array ops, audio assembly |
| imageio-ffmpeg | 0.6.0 | ffmpeg binary for audio extraction + video muxing |

#### UI & Documents

| Package | Version | Role |
|---------|---------|------|
| gradio | 6.20.0 | Web UI (8-tab interface) |
| python-docx | 1.2.0 | QA cert, quiz, metadata Word export |
| openpyxl | 3.1.5 | Quiz + metadata Excel export |
| pdfplumber | 0.11.10 | PDF text extraction |

#### Utilities

| Package | Version | Role |
|---------|---------|------|
| huggingface_hub | 0.36.2 | Model download + HF token auth |
| lingua-language-detector | 2.2.0 | Per-segment language detection |
| python-dotenv | 1.2.2 | `.env` config loading |

---

### 21.3 GPU VRAM Usage by Pipeline Stage

| Stage | Model(s) Loaded | VRAM per GPU |
|-------|----------------|--------------|
| ASR | faster-whisper large-v3 | ~3 GB |
| Translation | IndicTrans2 (fp16) | ~2.5 GB |
| Translation | SeamlessM4T (fp16) | ~5 GB |
| Translation | NLLB-200 (fp16) | ~1.5 GB |
| TTS | Parler-TTS Indic Large (fp16) | ~4 GB |
| TTS | MMS standalone VITS (fp32) | ~0.5 GB |
| **Peak (all loaded)** | IndicTrans2 + Parler + SeamlessM4T | ~12 GB |
| **Available per GPU** | RTX A6000 | **48 GB** |
| **Headroom** | | ~36 GB free |

The 48 GB VRAM per GPU provides substantial headroom — all models for a single language fit comfortably in one GPU with room for large batch sizes.

---

### 21.4 Multi-GPU Utilisation

With 4 × RTX A6000 (192 GB total VRAM):

```
GPU 0 — ASR (shared, runs once) + Language bucket A
GPU 1 — Language bucket B
GPU 2 — Language bucket C
GPU 3 — Language bucket D
```

22 languages distributed round-robin across 4 GPUs → each GPU processes ~5–6 languages sequentially. ASR runs once on GPU 0 in the main process; the resulting segments are cached to disk and shared to all 4 workers, eliminating 3× redundant transcription.

**Effective throughput:** ~4× speedup over single-GPU for all-22-language dubbing jobs.

---

### 21.5 Minimum Requirements (for deployment on other systems)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | 1 × 24 GB VRAM (RTX 3090 / A5000) | 4 × 48 GB (RTX A6000) |
| RAM | 32 GB | 128 GB |
| CPU | 8 cores | 32+ cores |
| NVMe SSD | 500 GB (OS + models) | 4 TB |
| HDD | 2 TB (outputs) | 12 TB+ |
| OS | Windows 10 / Ubuntu 20.04 | Windows 11 Pro for Workstations |
| Python | 3.10+ | 3.11.x |
| CUDA | 11.8+ | 12.4 |
| NVIDIA Driver | 520+ | 596.72 |

> **Note:** The pipeline runs on a single GPU — multi-GPU is optional for throughput. All 22 languages can be dubbed sequentially on a single RTX 3090 (24 GB); the 4-GPU setup reduces wall-clock time from ~22 hours to ~6 hours for a 1-hour source video across all 22 languages.

---

## Table of Contents

1. Executive Summary
2. Problem Statement
3. System Architecture
4. Project Structure
5. AI Models (ASR / Translation / TTS)
6. Language Coverage
7. Quality Scoring System
8. Key Pipeline Features
9. Web UI — 8 Tabs
10. CLI Reference
11. Translation Memory
12. Fine-Tuning
13. Output Structure
14. Models & Storage Requirements
15. Dependencies
16. KB Tender Compliance
17. Optional LLM Post-Edit Enhancement
18. Logging & Audit
19. Quick Start
20. Contract Summary
21. Hardware & Software Requirements
22. Segment Data Schema (Inter-Module Data Flow)
23. Module Deep-Dives
24. Glossary System
25. Language Detection Module
26. Checkpoint / Resume Internals
27. Document Translation Flow
28. Subtitle Generation
29. Video Processor
30. CBP Portal Uploader
31. LLM Enhancer
32. Logger
33. Error Handling & Fallback Chains
34. Known Limitations
35. Environment Configuration (.env)
36. Actual Tested Output (Real Run)

---

## 22. Segment Data Schema — Inter-Module Data Flow

This is the core data structure passed between all pipeline modules. Understanding this dict is essential for reading the code.

### 22.1 ASR Output Segment (after `asr.py`)

```python
{
    "id": 0,                        # sequential segment index
    "start": 0.06,                  # start timestamp (seconds)
    "end": 4.32,                    # end timestamp (seconds)
    "text": "Welcome to the...",    # transcribed text
    "detected_lang": "eng"          # language detected by lingua (or assumed_lang)
}
```

### 22.2 Translated Segment (after `translator.py`)

All ASR fields preserved, plus:

```python
{
    "id": 0,
    "start": 0.06,
    "end": 4.32,
    "text": "பி. என். பிரதான் மந்திரி...",  # translated text (replaces source)
    "detected_lang": "eng",
    "engine": "indictrans2",               # which engine produced this translation
    "enhanced": false,                     # True if LLM post-edit was applied
    "quality": {
        "score": 1.0,                      # heuristic score 0.0–1.0
        "chrf": 0.0,                       # ChrF score (0 for cross-script pairs)
        "flags": [],                       # list of quality flag strings
        "needs_review": false,             # score < 0.55
        "failed": false                    # score < 0.30
    }
}
```

### 22.3 TTS Output Segment (after `tts.py`)

All translated fields preserved, plus:

```python
{
    ...all translated segment fields...,
    "audio_path": "output/hin/tmp/<job_id>/tts_segments/seg_0000.wav"
}
```

### 22.4 Assembled Result (`DubbingResult` dataclass)

```python
@dataclass
class DubbingResult:
    source_lang:       str          # "eng"
    target_lang:       str          # "tam"
    input_path:        str          # path to source video
    output_video_path: str          # path to dubbed MP4
    output_audio_path: str          # path to dubbed MP3 (audio-only input)
    transcript:        list[dict]   # ASR segments
    translations:      list[dict]   # translated + quality-scored segments
    quality_summary:   dict         # aggregated quality stats
    duration_original: float        # source video duration (seconds)
    duration_output:   float        # dubbed video duration (seconds)
    elapsed_s:         float        # total wall-clock time
    success:           bool
    error:             str
```

---

## 23. Module Deep-Dives

### 23.1 `asr.py` — ASR Engine

- Loads `faster-whisper large-v3` from `models/indic_asr/` using CTranslate2
- `transcribe_segments(wav_path, src_lang)` → `list[dict]`
- `src_lang="auto"` triggers automatic language detection; resolved lang stored in `detected_lang` of first segment
- Hallucination stripping: `_strip_hallucinations()` removes ँ/ं prefix artifacts from checkpoint-restored segments
- Segment repair: `_repair_asr_segments()` merges mid-sentence splits using:
  - Latin: first word starts lowercase or is punctuation-only
  - Indic: first char is a virama (mid-akshar continuation)
  - Dangling preposition/conjunction at end of previous segment
  - Gap < 200ms with no sentence-ending punctuation

### 23.2 `translator.py` — Translation Engine

**Public API:**
- `translate(text, src_lang, tgt_lang, glossary, detected_lang)` → `dict` — single segment
- `translate_batch(texts, src_lang, tgt_lang, glossary, detected_langs)` → `list[dict]` — GPU batch
- `translate_text(text, src_lang, tgt_lang)` → `str` — convenience wrapper
- `translate_document_batch(texts, src_lang, tgt_lang)` → `list[str]` — document mode
- `translate_speech_to_speech(audio_path, src_lang, tgt_lang, output_path)` → `bool` — S2ST

**Routing decision tree (per segment):**
```
Is src == tgt?          → passthrough
Is text non-translatable? → passthrough_nontranslatable
Is tgt in SEAMLESS_FIRST? → SeamlessM4T first, then IndicTrans2 score-based
Is tgt in NLLB_FIRST?   → NLLB-200 first, then SeamlessM4T score-based
Is tgt in PIVOT_LANGS?  → IndicTrans2 via Hindi pivot
Otherwise               → IndicTrans2 GPU batch
                          → SeamlessM4T fallback
                          → NLLB-200 final fallback
```

### 23.3 `tts.py` — TTS Engine

**Public API:**
- `synthesize(text, lang, output_path)` → `str` — single segment
- `synthesize_segments(segments, lang, output_dir)` → `list[dict]` — full video batch

**Internal synthesis chain per segment:**
```
lang in _PARLER_SKIP_LANGS?
  No  → Parler-TTS batch (4 segs/pass) → single retry → split-half retry → MMS fallback
  Yes → standalone VITS → MMS adapter → silence (last resort)
```

**Audio post-processing pipeline (every segment):**
1. High-pass Butterworth filter at 80 Hz (removes DC/rumble)
2. For Devanagari langs: mild low-pass blend at 8 kHz (removes Parler hiss)
3. For MMS langs: low-pass at 9500 Hz (removes VITS consonant harshness)
4. Trailing silence trim (threshold 0.001 for MMS)
5. Normalise to -3 dBFS (0.708 peak) — iOS AAC headroom

### 23.4 `video_processor.py` — Video Processor

**Public API:**
- `extract_audio(video_path, output_wav, sample_rate=16000)` → `str`
- `assemble_dubbed_audio(segments, original_duration, output_wav)` → `str`
- `replace_audio_in_video(video_path, audio_path, output_path)` → `str`
- `get_video_duration(video_path)` → `float`
- `stretch_audio_to_duration(audio_path, target_duration, output_path)` → `str`

**Assembly fit-to-slot strategy (priority order):**
1. TTS fits within original slot → place as-is
2. TTS overflows into silence gap before next speech → allow, no speed change
3. TTS would overlap next speech → speed up via atempo (max 1.35×)
4. Still over after 1.35× → extend limit by 300ms
5. Still over → trim with 250ms fade-out (last resort)

**Comfort noise:** Pink noise at 0.002 amplitude fills silence gaps — prevents jarring dead silence between segments. Speech mask built from placed audio positions (not raw TTS lengths).

**BGM mixing:** Optional background music ducked to 40% volume during speech, 18% in silence gaps. 50ms fade-in/out at segment edges.

---

## 24. Glossary System

### 24.1 File Format

Each language has `glossary/<lang>.json`:
```json
{
  "competency framework": "दक्षता ढांचा",
  "iGOT": "iGOT",
  "karmayogi": "कर्मयोगी",
  "learning outcome": "सीखने का परिणाम"
}
```
Keys are lowercase source terms. Values are the approved target translations.

### 24.2 How Injection Works

Glossary is applied **after** translation as a post-processing step — not before. This avoids placeholder corruption inside the translation model.

```
translate(text) → raw_translation
glossary.apply(text, src_lang, tgt_lang, raw_translation)
  → strip __GLOSS__ artifacts
  → strip stray Gurmukhi/Malayalam prefix chars
  → word-boundary regex replace: source terms that leaked through unchanged
  → return cleaned translation
```

The `protect_terms()` / `restore_terms()` methods exist for pre-translation protection but are not used in the main pipeline — post-translation application is more reliable.

### 24.3 Managing Glossary via CLI

```bash
# Add a term
python scripts/translate.py --add-glossary "Competency" "दक्षता" hin

# Export full glossary report
python scripts/translate.py --export-glossary glossary_report.txt

# Via UI: Glossary tab → add/edit/export
```

---

## 25. Language Detection Module (`lang_detect.py`)

### 25.1 Purpose

Adds `detected_lang` to every ASR segment so the translator can route mixed-language content correctly. Primarily useful for Indic-source videos where a speaker may switch between languages mid-sentence.

### 25.2 How It Works

```python
tag_segments(segments, assumed_lang) → list[dict]
```

- Uses `lingua-language-detector` (offline, no API)
- Supports 16 of the 22 languages (bod/doi/kas/kok/mni/sat/snd not supported by lingua)
- For unsupported langs: always returns `assumed_lang` — no detection attempted
- For Devanagari-family langs (hin/mar/nep/mai/san/kok): always returns `assumed_lang` — lingua confuses these constantly since they share the same script
- For other supported langs: runs detection, falls back to `assumed_lang` on failure

### 25.3 How `detected_lang` Feeds Translation Routing

In `dubbing_pipeline.py`:
```python
# Only use detected_lang for Indic source — not for English source
# (Lingua misdetects English ASR as Hindi/Bodo/Maithili)
effective_detected = detected_langs if src_lang != "eng" else None
batch_results = translator.translate_batch(
    texts, src_lang, tgt_lang,
    detected_langs=effective_detected
)
```

In `translator.py`:
```python
# detected_lang overrides src_lang for routing ONLY for Indic source
if detected_lang and src_lang != "eng" and detected_lang != src_lang:
    src_lang = detected_lang  # reroute to correct IndicTrans2 direction
```

---

## 26. Checkpoint / Resume Internals (`retry.py`)

### 26.1 `JobCheckpoint` — What It Stores

File: `checkpoints/jobs/<job_id>.json`

```json
{
  "completed": {
    "0": { ...translated_segment_dict... },
    "1": { ...translated_segment_dict... }
  },
  "meta": {
    "segments": [ ...asr_segments... ],
    "detected_src_lang": "eng",
    "duration": 356.35
  }
}
```

- `completed`: keyed by segment `id` (string) — every successfully translated segment
- `meta.segments`: full ASR output — so ASR never re-runs on resume
- `meta.detected_src_lang`: resolved source language
- `meta.duration`: original video duration

### 26.2 Resume Flow

```
Job starts → load checkpoint
  meta.segments exists? → skip ASR (Step 2), use cached segments
  For each segment:
    ckpt.is_done(seg_id)? → use cached translation (skip Step 3 for this seg)
    else → translate → ckpt.mark_done(seg_id, result)
  ckpt.flush() → atomic write (tmp → rename, never corrupts)
  TTS always re-runs (fast, no checkpoint needed)
  On success → ckpt.clear() (delete checkpoint file)
```

### 26.3 Atomic Write

```python
tmp = self.path.with_suffix(".tmp")
tmp.write_text(json.dumps(self._data, ...))
tmp.replace(self.path)   # atomic on NTFS/ext4 — partial writes never corrupt
```

### 26.4 `retry` Decorator

```python
@retry(max_attempts=2, delay=1.0)
def _translate_indic_trans2(self, text, src_lang, tgt_lang):
    ...
```

Exponential backoff: attempt 1 → wait 1s → attempt 2 → wait 2s → raise.
Used on all three translation engine calls.

---

## 27. Document Translation Flow (`doc_extractor.py`)

### 27.1 Supported Formats

| Format | Support | Notes |
|--------|---------|-------|
| `.docx` | ✅ Full | Format-preserving: styles, tables, headers/footers, runs |
| `.txt` | ✅ Plain text | UTF-8 read |
| `.pdf` | ❌ Blocked | KB tender §3.1 — upload original PDF to CBP as-is |
| `.doc` | ✅ Via python-docx | Best-effort |

### 27.2 `translate_docx()` — Format-Preserving Translation

Preserves:
- Paragraph styles (Heading 1/2/3, Normal, List, etc.)
- Run-level formatting (bold, italic, underline, font size/colour)
- Tables (cell by cell)
- Headers and footers (all 6 variants: first/even/odd × header/footer)
- Inline images (copied unchanged — not translated)
- Hyperlinks (text translated, URL preserved)

**How it works:**
```
For each paragraph:
  Collect all runs → join into full_text
  translate_fn([full_text], src_lang, tgt_lang) → [translated]
  Put result in runs[0].text
  Clear runs[1:].text  ← preserves bold/italic on first run
For each table cell:
  Same paragraph-level translation
For each header/footer section:
  Same paragraph + table translation
```

### 27.3 CLI Usage

```bash
# Translate a DOCX
python scripts/translate.py --doc input/report.docx --src eng --tgt hin

# Translate to all 22 languages
python scripts/translate.py --doc input/report.docx --src eng --tgt all
```

---

## 28. Subtitle Generation (`subtitles.py`)

### 28.1 SRT / VTT Generation

```python
generate_subtitles(segments, output_dir, course_id, tgt_lang,
                   formats=["srt","vtt"], video_duration=0.0)
```

**Timing adjustment logic:**
- End time extended to cover reading time: `max(1.5s, len(text) / 17.0 chars/sec)`
- End clamped to `next_start - 40ms` so subtitles never overlap
- Last segment end extended to `video_duration`

**Text wrapping:**
- Max 42 chars per line (fits 2 lines of Devanagari on 1080p)
- Recursive split at word boundaries, closest to midpoint
- Never breaks mid-word or mid-akshar

**Cleanup:**
- Strips leading punctuation artifacts (`)`, `]`, `,`, `.`, `।`)
- Per-language fixup table (`_SUB_FIXUPS`) for known MT artifacts
  - Hindi: "पसीना आना" → "वाष्पोत्सर्जन" (transpiration correction)
  - Hindi: removes stray "कम" between comma-separated items

### 28.2 Subtitle Embedding Options

```python
# Soft subtitles (selectable track, not burned in) — default
embed_subtitles_soft(video_path, srt_path, output_path, lang="tam")

# Hard subtitles (burned into video pixels)
burn_subtitles(video_path, srt_path, output_path)
```

The pipeline uses soft subtitles by default — the SRT/VTT files are delivered as separate files alongside the MP4.

---

## 29. CBP Portal Uploader (`cbp_uploader.py`)

### 29.1 Authentication

```python
uploader = CBPUploader()  # reads CBP_USERNAME, CBP_PASSWORD from env
uploader.login()           # POST /api/user/v1/login → Bearer token
```

Credentials never logged — only `type(e).__name__` on error, never the exception message.

### 29.2 Upload Flow

```python
uploader.upload_course_package(
    package_dir="output/KB_COURSE_001/tam",
    course_id="KB_COURSE_001",
    lang="tam"
)
```

Scans for files matching these patterns and uploads each:

| Pattern | Asset Type |
|---------|-----------|
| `*_tam.mp4` | video |
| `*_tam.mp3` | audio |
| `*_tam*.xlsx` | metadata |
| `*_tam*.docx` | assessment |
| `*_tam.srt` | subtitle |
| `*_tam.vtt` | subtitle |

Upload endpoint: `POST /api/content/v1/upload` with multipart form data.
Retry: 3 attempts with 5s/10s/15s backoff.

### 29.3 Submission Report

```python
uploader.generate_submission_report(upload_results, "reports/cbp_submission.json")
```

Generates a JSON report with total uploads, errors, and per-course details for KB records.

---

## 30. LLM Enhancer (`llm_enhancer.py`)

### 30.1 When It Activates

Only when one of these keys is set in `.env`:
```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
OPENROUTER_API_KEY=sk-...
```
If none set: `LLMEnhancer.available = False` — pipeline runs fully offline, no change in behaviour.

### 30.2 Provider Priority

`groq` → `gemini` → `openrouter` (first key found wins)

### 30.3 Models Used

| Provider | Model |
|----------|-------|
| Groq | `llama-3.3-70b-versatile` |
| Gemini | `gemini-1.5-flash` |
| OpenRouter | `meta-llama/llama-3.3-70b-instruct:free` |

### 30.4 Timeout Guards

- Single segment: 45s hard cap — never stalls pipeline
- Batch: 90s hard cap
- On timeout: returns raw machine translation unchanged

### 30.5 Prompt

```
You are a professional translator and language quality editor for Indian languages.
Task: Post-edit the machine translation below to make it natural, fluent, and accurate.
- Keep all proper nouns, scheme names, and numbers exactly as-is
- Fix grammar, word order, and unnatural phrasing
- Output ONLY the corrected translation, nothing else

Source ({src_lang}): {source}
Machine Translation ({tgt_lang}): {translation}
Corrected Translation:
```

---

## 31. Logger (`logger.py`)

### 31.1 Log Format

Every log entry is a JSON line:
```json
{"ts": "2025-01-01T12:00:00", "level": "INFO", "module": "dubbing_pipeline", "msg": "START job=abc123 file=course.mp4 eng->tam"}
```

### 31.2 Configuration

- File handler: `logs/pipeline.log` — rotating, 10 MB per file, 5 backups
- Console handler: human-readable `[module] message` format, UTF-8 safe on Windows
- Both handlers active simultaneously

### 31.3 Audit Log

`logs/audit.log` — separate file, same JSON format, only job-level events:

```json
{"ts": "...", "level": "INFO", "module": "audit", "msg": "{\"event\": \"job_start\", \"job_id\": \"abc123\", \"file\": \"course.mp4\", \"src\": \"eng\", \"tgt\": \"tam\", \"course_id\": \"KB_COURSE_001\", \"host\": \"NTSCHNCC0004911\"}"}
{"ts": "...", "level": "INFO", "module": "audit", "msg": "{\"event\": \"job_success\", \"job_id\": \"abc123\", \"tgt\": \"tam\", \"elapsed_s\": 412.3, \"output\": \"output/KB_COURSE_001/tam/KB_COURSE_001_tam.mp4\", \"quality\": {...}}"}
```

---

## 32. Error Handling & Fallback Chains

### 32.1 Translation Fallback Chain

```
IndicTrans2 fails
    → SeamlessM4T
        → NLLB-200
            → RuntimeError("All translation engines failed")
                → batch: per-segment retry
                    → source text as last resort (better than silence)
```

Empty translation for non-empty source:
```
batch returns "" for segment i
    → per-segment retry via translate()
        → still "" → use source text
            → flag: "translation_failed_source_fallback"
            → needs_review: True, failed: True
```

### 32.2 TTS Fallback Chain

```
Parler-TTS attempt 1 fails
    → Parler-TTS attempt 2
        → Parler single synthesis
            → Parler split-half synthesis
                → MMS standalone VITS
                    → MMS adapter
                        → write silence (duration = original slot)
```

CUDA OOM during TTS:
```
RuntimeError("out of memory" or "illegal memory")
    → torch.cuda.synchronize() + empty_cache()
    → self._tts = None  (force reload)
    → retry TTS with MMS fallback
```

### 32.3 Audio Assembly Fallback

```
segment audio_path missing or unreadable
    → loaded[i] = None
    → placed_end[i] = start_samp (no audio placed)
    → silence gap in output at that timestamp
```

### 32.4 Video Mux Fallback

```
ffmpeg mux fails (ret != 0)
    → re-encode input video (libx264 ultrafast)
    → retry mux with re-encoded input
        → RuntimeError("replace_audio_in_video failed")
```

---

## 33. Known Limitations

| Limitation | Detail | Workaround |
|------------|--------|------------|
| Santhali (sat) TTS quality | Ol Chiki script has no Parler training data; MMS sat adapter is low-resource | MMS-VITS sat adapter used; quality acceptable for government content |
| Sindhi (snd) TTS | No standalone VITS model downloaded; falls to MMS adapter | MMS urd-script_arabic adapter used as proxy |
| Kashmiri (kas) TTS | No standalone VITS; MMS urd-script_arabic adapter used | Acceptable for Nastaliq script |
| Parler amplitude for Dravidian | Parler-TTS Indic Large produces near-silence for tam/tel/kan/mal without dedicated fine-tune | MMS-VITS used as primary for these 4 languages |
| Konkani (kok) translation | IndicTrans2 uses gom_Deva (Goan Konkani) which drifts to Goan dialect | NLLB-200 used as primary for kok |
| Bodo/Maithili/Hindi script collision | All three use Devanagari — script-level stripping cannot distinguish them | Morpheme-level drift guards (regex) detect and retry via NLLB |
| SeamlessM4T S2ST limited pairs | Only hin/ben/kan/tel/urd support speech output | Other Indic pairs fall back to full ASR→Translate→TTS |
| PDF translation blocked | KB tender §3.1 prohibits PDF translation | Upload original PDF to CBP portal directly |
| Voice cloning (XTTS-v2) | Requires `coqui-tts --no-deps` separate install to avoid conflicts | Install separately; pipeline works without it |
| LLM enhancement requires internet | Groq/Gemini/OpenRouter are external APIs | Optional — pipeline fully offline without any API key |
| Windows path length limit | Long course IDs + deep output paths can hit 260-char limit | Use short course IDs; enable long path support in Windows registry |

---

## 34. Environment Configuration (`.env`)

File location: `project/.env`

```bash
# HuggingFace token — required for model download only
# Not needed for inference (all models already downloaded locally)
HF_TOKEN="hf_..."

# CBP Portal credentials (KB tender §4.2)
CBP_USERNAME=your_username
CBP_PASSWORD=your_password
CBP_BASE_URL=https://cbp.igotkarmayogi.gov.in   # optional override

# Optional LLM post-edit (any one key activates enhancement)
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
OPENROUTER_API_KEY=sk-...

# GPU override (set by pipeline automatically for multi-GPU workers)
# Do not set manually unless debugging a specific GPU
PIPELINE_GPU=0

# TTS device override (optional)
TTS_DEVICE=cuda:0
```

**Current `.env` on this system:**
```
HF_TOKEN="hf_YPgcuGng..."   # HuggingFace token (model download)
```
No CBP credentials or LLM keys set — pipeline runs fully offline.

---

## 35. Actual Tested Output — Real Production Run

### 35.1 Test Video

| Property | Value |
|----------|-------|
| File | `input/PNB-Pradhan Mantri Mudra Yojana.mp4` |
| Course ID | `KB_COURSE_001` |
| Source Language | English |
| Target Language | Tamil (tam) |
| Output | `output/tam/KB_COURSE_001_tam.mp4` |

### 35.2 Real Metadata from Production Run

```json
{
  "course_id": "KB_COURSE_001",
  "source_lang": "eng",
  "target_lang": "tam",
  "target_lang_name": "Tamil",
  "duration_output_s": 356.35,
  "voice_cloned": false,
  "segment_count": 36,
  "quality_summary": {
    "total": 36,
    "avg_score": 1.0,
    "avg_chrf": 0.0,
    "needs_review": 0,
    "failed": 0,
    "pass_rate": 1.0
  },
  "provenance": {
    "model_versions": {
      "faster-whisper": "1.2.1",
      "transformers": "4.46.1",
      "parler-tts": "0.2.2",
      "torch": "2.6.0+cu124",
      "soundfile": "0.14.0",
      "git_commit": "5afb328b"
    },
    "host": "NTSCHNCC0004911",
    "generated_at": "2026-08-18T11:59:49",
    "contract": "RFB IN-KBL-543730-NC-RFB"
  }
}
```

### 35.3 Sample Transcript → Translation (English → Tamil)

| Seg | Start | End | English (ASR) | Tamil (IndicTrans2) |
|-----|-------|-----|---------------|---------------------|
| 0 | 0.06s | 4.32s | Welcome to the presentation on PNB Pradhan Mantri Mudra Yojana Scheme. | பி. என். பிரதான் மந்திரி முத்ரா யோஜனா திட்டம் பற்றிய விளக்கக்காட்சிக்கு வரவேற்கிறோம். |
| 5 | 67.24s | 72.56s | Shishu loans cover amounts up to ₹50,000. | சிஷு கடன்கள் ₹50,000 வரை காப்பீடு அளிக்கின்றன. |
| 25 | 279.62s | 281.48s | Not more than 14 working days. | 14 வேலை நாட்களுக்கு மிகாமல் இருக்க வேண்டும். |
| 35 | 351.03s | 356.35s | For detailed information, please refer to the official scheme circular available on our official website. | விவரங்களுக்கு, எங்கள் அதிகாரப்பூர்வ இணையதளத்தில் கிடைக்கும் அதிகாரப்பூர்வ திட்ட சுற்றறிக்கையைப் பார்க்கவும். |

All 36 segments: engine = `indictrans2`, score = 1.0, needs_review = false, failed = false.

### 35.4 Other Tested Outputs

| Course | Languages Dubbed | Output Location |
|--------|-----------------|-----------------|
| KB_COURSE_001 | asm, ben, guj, hin, kan, kas, mal, mar, mni, nep, ory, pan, tam, tel, urd (15 langs) | `output/KB_COURSE_001/<lang>/` |
| Fine_Tuning_Initiative_Report | asm, ben, guj, hin, kan, kas, mal, mar, mni, ory, pan, tam, tel, urd (14 langs) | `output/Fine_Tuning_Initiative_Report/` |
| ARD-KRAHEJA-AET-ENG | tam, tel | `output/ARD-KRAHEJA-AET-ENG/` |

---

*Report last updated: based on source code + live system analysis*
*System: Dell Xeon w9-3495X | 4 × RTX A6000 | 128 GB DDR5 | Windows 11 Pro for Workstations*
*Contract: RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi, Government of India*
