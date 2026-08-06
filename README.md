# KB Translation System — 22 Indian Languages
**iGOT Karmayogi | RFB IN-KBL-543730-NC-RFB**

End-to-end offline dubbing pipeline: ASR → Translation → TTS for all 22 scheduled Indian languages.
All models run locally — no internet, no API keys, no data leaves the system.

---

## Quick Start

```bash
pip install -r requirements.txt

# Run the UI
python ui/app.py

# CLI — dub a single language
python scripts/dub.py --video course.mp4 --src eng --tgt kan --course-id MyCourse --output output

# CLI — dub all 22 languages
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse --output output

# Force re-run (clears checkpoint + output)
python scripts/dub.py --video course.mp4 --src eng --tgt kan --force
```

---

## Project Structure

```
project/
├── pipeline/                      # ★ Core inference — all model logic lives here
│   ├── __init__.py                # Package exports
│   ├── asr.py                     # ASR: faster-whisper large-v3, all 22 langs, auto-detect
│   ├── translator.py              # Translation: IndicTrans2 → SeamlessM4T → NLLB-200
│   ├── tts.py                     # TTS: Parler-TTS Large → MMS-TTS → XTTS-v2 fallback chain
│   ├── dubbing_pipeline.py        # End-to-end orchestration, 6-step pipeline, multi-GPU
│   ├── video_processor.py         # ffmpeg audio extraction, assembly, video muxing
│   ├── glossary.py                # Per-language glossary injection (22 × JSON files)
│   ├── lang_config.py             # Language codes for all 3 engines + S2ST langs
│   ├── quality.py                 # Heuristic + ChrF + back-translation quality scoring
│   ├── subtitles.py               # SRT + VTT subtitle generation
│   ├── lang_detect.py             # Per-segment language detection + tagging
│   ├── doc_extractor.py           # DOCX/PDF/TXT extraction + format-preserving translation
│   ├── voice_clone.py             # Voice cloning: Coqui XTTS-v2 (KB Tier 2 pricing)
│   ├── cbp_uploader.py            # CBP portal upload (KB tender §4.2)
│   ├── llm_enhancer.py            # LLM post-edit (Groq/Gemini/OpenRouter — optional)
│   ├── logger.py                  # Structured JSON logging (pipeline.log + audit.log)
│   └── retry.py                   # Retry decorator + JobCheckpoint (crash-safe resume)
│
├── ui/
│   ├── app.py                     # ★ Gradio web UI — 8 tabs
│   └── reviewer.py                # Human review + DOCX certificate export
│
├── scripts/
│   ├── dub.py                     # ★ CLI entry point — video dubbing + reports
│   ├── translate.py               # CLI text/audio/batch/course translation
│   ├── translation_memory.py      # Govt TM + human feedback manager (CLI + library)
│   ├── clean_outputs.py           # Wipe output/ + checkpoints/jobs/
│   ├── clean_and_run_all22.py     # Auto-clean then dub all 22 languages
│   ├── wipe_outputs.bat           # Windows batch wipe
│   ├── download_models.py         # Download all model weights to models/
│   ├── download_datasets.py       # Download parallel training data to datasets/
│   ├── build_asr_index.py         # Build ASR fine-tune index from datasets/asr/
│   ├── check_gaps.py              # Verify 22-lang dataset coverage
│   └── test_pipeline.py           # Smoke test — runs a short dub end-to-end
│
├── finetune/
│   ├── finetune_indictrans.py     # Fine-tune IndicTrans2 on parallel data
│   ├── finetune_seamless.py       # Fine-tune SeamlessM4T
│   └── ds_zero3.json              # DeepSpeed ZeRO-3 config for multi-GPU fine-tuning
│
├── datasets/
│   ├── asr/                       # ASR fine-tune index (22 langs)
│   └── parallel/                  # Parallel text: train/dev/test.jsonl per language
│
├── glossary/                      # 22 × <lang>.json domain glossary files
│
├── models/                        # Downloaded weights — not in git (too large)
│   ├── indic_tr/                  # IndicTrans2: en_indic / indic_en / indic_indic
│   ├── indic_parler_tts/          # Parler-TTS Indic mini (fallback)
│   ├── indic_parler_tts_large/    # Parler-TTS Indic large (★ primary TTS)
│   ├── seamless/                  # SeamlessM4Tv2 (~10GB)
│   ├── nllb/                      # NLLB-200 (~2.4GB)
│   ├── mms/                       # MMS-TTS shared base + per-lang adapters
│   ├── indic_asr/                 # faster-whisper large-v3 CT2 weights
│   └── whisper/                   # Whisper cache (auto-download fallback)
│
├── checkpoints/
│   ├── indictrans/
│   │   ├── en_indic/best/         # ★ Fine-tuned English → Indic (used by pipeline)
│   │   ├── indic_en/best/         # Fine-tuned Indic → English
│   │   └── indic_indic/best/      # Fine-tuned Indic → Indic
│   ├── jobs/                      # Runtime job checkpoints (auto-cleared on success)
│   └── seamless/                  # SeamlessM4T fine-tune checkpoints
│
├── translation_memory/            # govt_tm.jsonl + human_feedback.jsonl + correction_log.jsonl
├── input/                         # Source videos / documents
├── output/                        # ★ All dubbed outputs
│   └── <course_id>/
│       └── <lang_code>/
│           ├── <course>_<lang>.mp4
│           ├── <course>_<lang>.srt
│           ├── <course>_<lang>.vtt
│           └── <course>_<lang>_metadata.json
│
├── logs/
│   └── pipeline.log
├── assets/                        # Static assets (xtts_refs/ for voice cloning)
├── .env                           # HF_TOKEN, CBP_USERNAME, CBP_PASSWORD, LLM API keys
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Pipeline Flow

```
Input MP4 / MP3 / WAV
        │
        ▼
[STEP 1] Audio extraction — ffmpeg → 16kHz mono WAV
        │
        ▼
[STEP 1b] SeamlessM4T S2ST — Indic→Indic pairs only (hin/ben/kan/tel/urd)
        │  → if successful: mux + return early
        ▼
[STEP 2] ASR — faster-whisper large-v3
        │  → sentence-level segments with timestamps
        │  → auto language detection (lang="auto")
        │  → hallucination guard: condition_on_previous_text=False
        ▼
[STEP 3] Translation — IndicTrans2 GPU batch → SeamlessM4T → NLLB-200
        │  → factual token protection (numbers, dates, currency)
        │  → non-translatable passthrough (URLs, code, paths)
        │  → glossary injection + quality scoring per segment
        │  → quality gate: score < 0.30 → silence (no wrong-language audio)
        ▼
[STEP 4] TTS — Parler-TTS Large → MMS-TTS → XTTS-v2
        │  → per-segment WAV files
        │  → voice cloning via XTTS-v2 if --voice-clone (KB Tier 2)
        ▼
[STEP 5] Audio assembly — place at original timestamps, fit-to-slot (max 1.35x speed)
        │  → dubbed.wav (exact original duration, padded with silence)
        ▼
[STEP 6] Output
        │  → SRT + VTT subtitles generated
        │  → ffmpeg mux: replace audio in video
        │  → duration ratio check (KB tender §5.1B — warn if >20% longer)
        │  → metadata JSON with quality scores + transcript
        ▼
output/<course_id>/<lang>/<course>_<lang>.mp4 + .srt + .vtt + _metadata.json
```

---

## Translation Engine Routing

| Language | Primary | Fallback 1 | Fallback 2 |
|----------|---------|------------|------------|
| hin, ben, tam, tel, kan, mal, mar, guj, pan, ory, asm, urd, nep, mai, doi, bod | IndicTrans2 (fine-tuned) | SeamlessM4T | NLLB-200 |
| mni, sat, san | IndicTrans2 via Hindi pivot | NLLB-200 | — |
| kok, snd, kas | NLLB-200 (primary) | — | — |
| bod, doi | SeamlessM4T (primary) | IndicTrans2 | NLLB-200 |

**S2ST (Speech-to-Speech)** — SeamlessM4T only, Indic→Indic pairs:
`hin ↔ ben ↔ kan ↔ tel ↔ urd`

---

## TTS Engine Routing

| Engine | Languages | Notes |
|--------|-----------|-------|
| Parler-TTS Indic Large | All 22 (primary) | 44kHz, GPU batch, fixed seed per lang for voice consistency |
| Parler-TTS Indic Mini | All 22 (fallback) | Used if large model absent |
| MMS-TTS | All 22 via adapters | Shared VITS base + per-lang adapter swap |
| Standalone VITS (doi) | Dogri only | `facebook/mms-tts-dgo` — real Dogri model |
| Coqui XTTS-v2 | hin/ben/tam/tel/kan/mal/mar/guj/pan/urd | Last-resort fallback; also used for voice cloning |

Parler skips `sat/kas/snd` (cannot render those scripts) — falls directly to MMS.

---

## Models Required

```bash
python scripts/download_models.py
```

| Model | Path | Size |
|-------|------|------|
| faster-whisper large-v3 | models/indic_asr/ | ~3 GB |
| IndicTrans2 en_indic | models/indic_tr/en_indic/ | ~1.2 GB |
| IndicTrans2 indic_en | models/indic_tr/indic_en/ | ~1.2 GB |
| IndicTrans2 indic_indic | models/indic_tr/indic_indic/ | ~1.2 GB |
| Parler-TTS Indic Large | models/indic_parler_tts_large/ | ~3.6 GB |
| Parler-TTS Indic Mini | models/indic_parler_tts/ | ~1.5 GB |
| SeamlessM4Tv2 | models/seamless/ | ~10 GB |
| NLLB-200 | models/nllb/ | ~2.4 GB |
| MMS-TTS | models/mms/ | ~1.5 GB |

---

## Datasets

```bash
python scripts/download_datasets.py   # downloads to datasets/parallel/
python scripts/check_gaps.py          # verifies all 22 langs have train/dev/test
```

Each language needs:
```
datasets/parallel/<lang_code>/train.jsonl
datasets/parallel/<lang_code>/dev.jsonl
datasets/parallel/<lang_code>/test.jsonl
```
Each line: `{"src": "...", "tgt": "...", "src_lang": "eng", "tgt_lang": "<lang>"}`

---

## Fine-Tuned Checkpoints

The pipeline **automatically uses fine-tuned checkpoints** if present:
```
checkpoints/indictrans/en_indic/best/    ← English → all Indian langs
checkpoints/indictrans/indic_en/best/    ← Indian → English
checkpoints/indictrans/indic_indic/best/ ← Indian → Indian
```
Falls back to base model in `models/indic_tr/` if checkpoint folder is absent.

```bash
python finetune/finetune_indictrans.py
python finetune/finetune_seamless.py
```

---

## Translation Memory

Government-verified translations and human corrections stored in `translation_memory/` and automatically injected into the pipeline via exact + fuzzy matching (85% threshold).

```bash
# Add a verified government translation
python scripts/translation_memory.py add --src "Competency Framework" --tgt "दक्षता ढांचा" --tgt-lang hin

# Record a human correction
python scripts/translation_memory.py correct --src "..." --wrong "..." --correct "..." --tgt-lang hin

# Show stats
python scripts/translation_memory.py stats

# Look up a term
python scripts/translation_memory.py lookup --src "Competency" --tgt-lang hin
```

---

## LLM Post-Edit Enhancement (Optional)

Set any one key in `.env` to activate — pipeline works fully offline without it:

```
GROQ_API_KEY=gsk_...        # free tier, llama-3.3-70b
GEMINI_API_KEY=AIza...      # gemini-1.5-flash
OPENROUTER_API_KEY=sk-...   # meta-llama/llama-3.3-70b-instruct:free
```

---

## Voice Cloning — KB Tier 2 Pricing

```bash
python scripts/dub.py --video course.mp4 --src eng --tgt hin \
    --voice-clone --reference-audio speaker.wav
```

Supported languages: `hin ben guj mar tam tel kan mal pan urd`
Uses Coqui XTTS-v2 (Apache 2.0, fully offline).

---

## CBP Portal Upload — KB Tender §4.2

Set credentials in `.env`:
```
CBP_USERNAME=your_username
CBP_PASSWORD=your_password
```

```bash
# Upload automatically after dubbing
python scripts/dub.py --video course.mp4 --src eng --tgt all --full --upload-cbp
```

Uploads: MP4, MP3, SRT, VTT, DOCX (quiz), XLSX (metadata) per language.

---

## CLI Reference

```bash
# Dub video — single language
python scripts/dub.py --video course.mp4 --src eng --tgt hin --course-id MyCourse

# Dub video — all 22 languages
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse

# Force re-run (clears checkpoint + output)
python scripts/dub.py --video course.mp4 --src eng --tgt hin --force

# Multi-GPU parallel dubbing (auto-detects GPU count)
python scripts/dub.py --video course.mp4 --src eng --tgt all --num-gpus 4

# Voice cloning (KB Tier 2)
python scripts/dub.py --video course.mp4 --src eng --tgt hin --voice-clone --reference-audio spk.wav

# Translate metadata to Excel
python scripts/dub.py --metadata meta.json --src eng --tgt all --xlsx

# Translate quiz to Word
python scripts/dub.py --quiz quiz.json --src eng --tgt all --docx

# Full course: dub + metadata + quiz + QA report + CBP upload
python scripts/dub.py --video course.mp4 --src eng --tgt all --full \
    --metadata meta.json --quiz quiz.json --course-id MyCourse --upload-cbp

# Text/batch translation (no audio)
python scripts/translate.py --text "Hello" --src eng --tgt hin
python scripts/translate.py --batch input.txt --src eng --tgt all
python scripts/translate.py --audio speech.wav --src hin --tgt ben

# Generate monthly submission report
python scripts/dub.py --run-monthly-report --monthly-report results.json --month 3
```

---

## Output Structure

```
output/<course_id>/<lang_code>/
    <course_id>_<lang>.mp4              ← dubbed video
    <course_id>_<lang>.srt              ← subtitles
    <course_id>_<lang>.vtt              ← web subtitles
    <course_id>_<lang>_metadata.json    ← quality scores + transcript + provenance
    <course_id>_<lang>_qa_cert.docx     ← QA self-certification (KB tender)
    <course_id>_quiz_<lang>.docx        ← translated quiz (Word)
    <course_id>_quiz_<lang>.xlsx        ← translated quiz (Excel)
    <course_id>_metadata_<lang>.docx    ← translated metadata (Word)
```

---

## UI Tabs

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

## Quality Scoring

Every segment is scored 0–1 automatically using three methods:

| Score | Status | Action |
|-------|--------|--------|
| ≥ 0.55 | ✅ Pass | Accepted |
| 0.30–0.55 | ⚠️ Review | Flagged for human review |
| < 0.30 | ❌ Failed | Silenced — no wrong-language audio sent to TTS |

Scoring methods: heuristic (script check, length ratio, transliteration detection) + ChrF + back-translation.

---

## Key Pipeline Behaviours

- **Checkpoint/resume** — crashes mid-job resume from last completed segment automatically
- **Force re-run** — `--force` clears both output files and ASR/translation checkpoint
- **Multi-GPU** — ASR runs once in main process; translate+TTS+assemble distributed across GPUs
- **Hallucination guard** — `condition_on_previous_text=False`, multi-temperature fallback `[0.0, 0.2, 0.4]`
- **Factual token protection** — numbers, dates, currency, measurements preserved via `__F0__` placeholders
- **Non-translatable passthrough** — URLs, code, file paths, @mentions passed through unchanged
- **Format token protection** — `{name}`, `%s`, `${var}`, `{{jinja}}` preserved via `__FMT0__` placeholders
- **Final quality check (10 rules)** — accuracy, completeness, grammar, fluency, consistency, corruption, placeholder-free, mixed-lang, formatting, professional
- **Fit-to-slot** — TTS audio sped up max 1.35× to fit original timestamp slot; hard-trimmed if still over
- **Duration ratio check** — warns if dubbed output >20% longer than original (KB tender §5.1B)
- **Exclusion detection** — PM/President speeches and YouTube-only content blocked per KB tender §3.1
- **Nastaliq normalisation** — Arabic-script ASR output normalised for Urdu/Kashmiri/Sindhi
- **Stale cache detection** — source.wav re-extracted if input video is newer than cached WAV
- **Concurrent job protection** — per-(course_id, lang) threading lock prevents duplicate jobs
- **Audit trail** — every job start/success/failure written to `logs/audit.log` as JSON
