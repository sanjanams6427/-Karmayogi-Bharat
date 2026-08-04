# KB Translation System — 22 Indian Languages
**iGOT Karmayogi | RFB IN-KBL-543730-NC-RFB**

End-to-end offline dubbing pipeline: ASR → Translation → TTS for all 22 scheduled Indian languages.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the UI
python ui/app.py

# CLI — dub a single language
python scripts/dub.py --video course.mp4 --src eng --tgt kan --course-id MyCourse --output output

# CLI — dub all 22 languages
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse --output output

# Force re-run (ignore existing output)
python scripts/dub.py --video course.mp4 --src eng --tgt kan --force
```

---

## Project Structure

```
project/
├── pipeline/                   # ★ Core inference — all changes made here
│   ├── asr.py                  # ASR: faster-whisper large-v3
│   ├── translator.py           # Translation: IndicTrans2 → Seamless → NLLB
│   ├── tts.py                  # TTS: Parler-TTS + MMS fallback
│   ├── dubbing_pipeline.py     # End-to-end orchestration
│   ├── video_processor.py      # Audio assembly + video muxing
│   ├── glossary.py             # Glossary injection
│   ├── lang_config.py          # Language codes & model routing
│   ├── quality.py              # Translation quality scoring
│   ├── subtitles.py            # SRT/VTT generation
│   └── lang_detect.py          # Per-segment language detection
│
├── ui/
│   └── app.py                  # ★ Gradio web UI
│
├── scripts/
│   ├── dub.py                  # ★ CLI entry point
│   ├── clean_outputs.py        # Wipe outputs + checkpoints
│   ├── clean_and_run_all22.py  # Auto-clean + run all 22 langs
│   ├── wipe_outputs.bat        # Windows batch wipe
│   ├── download_models.py      # Download all model weights
│   ├── download_datasets.py    # Download all datasets
│   ├── build_asr_index.py      # Build ASR fine-tune index
│   ├── check_gaps.py           # Verify 22-lang dataset coverage
│   └── test_pipeline.py        # Smoke test
│
├── finetune/
│   ├── finetune_indictrans.py  # Fine-tune IndicTrans2
│   └── finetune_seamless.py    # Fine-tune SeamlessM4T
│
├── datasets/
│   ├── asr/                    # Fine-tuning ASR index (22 langs)
│   └── parallel/               # Parallel text per language
│
├── models/                     # Downloaded weights (not in git — too large)
│   ├── indic_tr/               # IndicTrans2 (en_indic / indic_en / indic_indic)
│   ├── indic_parler_tts/       # Parler-TTS Indic
│   ├── seamless/               # SeamlessM4Tv2
│   ├── nllb/                   # NLLB-200
│   ├── mms/                    # MMS-TTS (per-lang adapters)
│   ├── indic_asr/              # faster-whisper large-v3
│   └── whisper/
│
├── checkpoints/
│   ├── indictrans/             # ★ Fine-tuned IndicTrans2 checkpoints
│   │   ├── en_indic/best/      #   English → Indic (USED BY PIPELINE)
│   │   ├── indic_en/best/      #   Indic → English
│   │   └── indic_indic/best/   #   Indic → Indic
│   └── jobs/                   # Runtime job checkpoints (auto-cleared)
│
├── glossary/                   # Domain glossary files
├── output/                     # ★ All dubbed outputs saved here
│   └── <course_name>/
│       └── <lang_code>/
│           ├── <course>_<lang>.mp4
│           ├── <course>_<lang>.srt
│           ├── <course>_<lang>.vtt
│           └── <course>_<lang>_metadata.json
│
├── .env                        # HF_TOKEN (not in git)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ★ Files Changed — What & Why

### `pipeline/lang_config.py`
- Added `SEAMLESS_S2ST_LANGS` — only 5 Indian langs support S2ST speech output (ben, hin, kan, tel, urd). Prevents pipeline from attempting S2ST on unsupported langs (tam, mal etc.)
- Added `mni`, `sat` to `SEAMLESS_CODES` — gives them Seamless fallback
- Fixed `nep` Seamless code to `npi` (correct code)

### `pipeline/translator.py`
- **Fine-tuned checkpoint auto-loading** — checks `checkpoints/indictrans/<direction>/best/` first, falls back to `models/indic_tr/` if not found
- Improved beam search: `num_beams=5`, `no_repeat_ngram_size=3`, `repetition_penalty=1.2`
- Fixed `kok` routing — only Konkani forced to NLLB (Nepali now uses IndicTrans2 correctly)
- `SEAMLESS_S2ST_LANGS` gate in `translate_speech_to_speech` — prevents wasted ~1.5min model load on unsupported langs

### `pipeline/tts.py`
- All 22 Parler-TTS speaker descriptions updated to say **"speaks slowly and deliberately"** — fixes rushed/robotic output across all languages
- MMS `length_scale=1.15` — VITS speaks ~15% slower, clearer syllables
- MMS `length_scale` wrapped in `try/finally` — always restored even on exception
- Low-pass filter at 7500 Hz in `_post_process` — reduces MMS harshness/shrillness
- `_PARLER_SKIP_LANGS` cleared to empty set — Parler tries all langs, MMS is fallback only

### `pipeline/video_processor.py`
- `assemble_dubbed_audio` — rewritten: places each segment at exact original timestamp, speeds up TTS to fit slot (max **1.4x**, was 2.0x), hard trims to slot, direct assignment not additive mixing
- Fade-out removed — was causing audible dips before each next word. Only 10ms fade-in kept
- `replace_audio_in_video` — stretches dubbed audio to exact video duration before muxing, added `-shortest`, encodes AAC 192k

### `pipeline/dubbing_pipeline.py`
- `force=True` now **deletes existing output files** before re-running — fixes "old file displayed" bug
- `check_already_translated` skip checks file size >500KB — won't skip silent/corrupt outputs
- S2ST gate uses `SEAMLESS_S2ST_LANGS` instead of `SEAMLESS_CODES`
- Added `force: bool = False` param to `dub_video` and `dub_course`

### `pipeline/asr.py`
- Hallucination fixes: `condition_on_previous_text=False`, `temperature=[0.0, 0.2, 0.4]`, `no_speech_threshold=0.6`, `compression_ratio_threshold=2.4`

### `pipeline/glossary.py`
- `_GLOSS_ARTIFACT` regex fixed for chained patterns
- `_STRAY_PREFIX` regex extended for Malayalam + Tamil mixed prefixes

### `ui/app.py`
- Output always saved to persistent `output/` folder — never Gradio temp (fixes files disappearing on restart)
- `_get_output_dir()` creates folder if missing
- `_save_outputs()` simplified — no unnecessary `shutil.copy2`
- `out_dir` explicitly `mkdir` before pipeline starts

### `scripts/dub.py`
- Added `--force` flag passed through to `dub_course`

---

## Pipeline Flow

```
Input MP4/MP3
     │
     ▼
[ASR] faster-whisper large-v3
     │  → 22-lang segments with timestamps
     ▼
[TRANSLATE] IndicTrans2 (fine-tuned) → Seamless → NLLB
     │  → translated segments, quality scored
     ▼
[TTS] Parler-TTS Indic → MMS-TTS fallback
     │  → per-segment WAV files
     ▼
[ASSEMBLE] place at original timestamps, fit-to-slot (max 1.4x)
     │  → dubbed.wav (exact original duration)
     ▼
[MUX] ffmpeg replace audio in video
     │  → output/<course>/<lang>/<course>_<lang>.mp4
     ▼
[SUBTITLES] SRT + VTT generated
```

---

## Translation Engine Routing

| Language | Primary | Fallback 1 | Fallback 2 |
|----------|---------|------------|------------|
| hin, ben, tam, tel, kan, mal, mar, guj, pan, ory, asm, urd, nep, mai, doi, kas, mni, san, sat, snd, bod | IndicTrans2 (fine-tuned) | SeamlessM4T | NLLB-200 |
| kok (Konkani) | NLLB-200 | — | — |
| bod, doi, kas, kok, mni, sat, snd (low-resource) | IndicTrans2 via Hindi pivot | NLLB-200 | — |

## S2ST (Speech-to-Speech) — Seamless only
Supported Indian langs: **hin, ben, kan, tel, urd** only.
All others use ASR → Translate → TTS pipeline.

---

## Models Required (download separately)

```bash
python scripts/download_models.py
```

## Datasets (not in git — too large)

Parallel training data (~1.5GB total) is excluded from git. To rebuild:

```bash
# Download all 22-language parallel datasets
python scripts/download_datasets.py

# Verify 22-lang coverage
python scripts/check_gaps.py
```

Or copy from shared storage into:
```
datasets/parallel/<lang_code>/train.jsonl   # 50-77MB per language
datasets/parallel/<lang_code>/dev.jsonl
datasets/parallel/<lang_code>/test.jsonl
```

| Model | Path | Size |
|-------|------|------|
| faster-whisper large-v3 | models/indic_asr/ | ~3GB |
| IndicTrans2 en_indic | models/indic_tr/en_indic/ | ~1.2GB |
| IndicTrans2 indic_en | models/indic_tr/indic_en/ | ~1.2GB |
| IndicTrans2 indic_indic | models/indic_tr/indic_indic/ | ~1.2GB |
| Parler-TTS Indic | models/indic_parler_tts/ | ~1.5GB |
| SeamlessM4Tv2 | models/seamless/ | ~10GB |
| NLLB-200 | models/nllb/ | ~2.4GB |
| MMS-TTS | models/mms/ | ~1.5GB |

---

## Fine-Tuned Checkpoints

The pipeline **automatically uses fine-tuned checkpoints** if present:
```
checkpoints/indictrans/en_indic/best/    ← used for English → all Indian langs
checkpoints/indictrans/indic_en/best/    ← used for Indian → English
checkpoints/indictrans/indic_indic/best/ ← used for Indian → Indian
```
If a checkpoint folder doesn't exist, falls back to base model in `models/indic_tr/`.

---

## Output Structure

Every successful dub produces:
```
output/<course_id>/<lang_code>/
    <course_id>_<lang>.mp4       ← dubbed video
    <course_id>_<lang>.srt       ← subtitles
    <course_id>_<lang>.vtt       ← web subtitles
    <course_id>_<lang>_metadata.json  ← quality scores + transcript
```
