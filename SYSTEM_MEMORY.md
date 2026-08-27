# MigotoAI Translation Engine — Complete System Memory
### Novac Technology Solutions Pvt. Ltd. — Immerz Division
### Contract: RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi Platform
### Last full read: 2026-08-24

---

## 1. What This System Is

End-to-end offline AI dubbing and translation pipeline for e-learning courses.
Translates English source videos into all 22 constitutionally scheduled Indian languages.
All models run locally — no internet, no API keys, no data leaves the system.
Deployed on: 4× NVIDIA A6000 (48GB each), 128GB RAM, Windows.
UI bound to: `172.23.198.15` (render machine IP), ports 7860–7870.

---

## 2. Complete File Inventory

### pipeline/ (core inference)
| File | Size | Purpose |
|---|---|---|
| `__init__.py` | 609 | Package exports — imports all modules |
| `asr.py` | 11,076 | ASR: faster-whisper large-v3 |
| `translator.py` | 55,240 | MT: IndicTrans2 → SeamlessM4T → NLLB-200 |
| `tts.py` | 62,410 | TTS: Parler-TTS → MMS standalone → XTTS-v2 |
| `dubbing_pipeline.py` | 73,756 | Orchestrator: 6-step pipeline + reports |
| `video_processor.py` | 25,556 | ffmpeg: audio extract, assembly, mux |
| `quality.py` | 10,954 | Quality scoring: heuristic + ChrF + back-translation |
| `subtitles.py` | 6,473 | SRT + VTT generation, burn, soft-embed |
| `glossary.py` | 6,044 | Per-language glossary enforcement |
| `lang_config.py` | 4,258 | All language code mappings |
| `lang_detect.py` | 3,651 | Per-segment language detection (lingua) |
| `llm_enhancer.py` | 6,942 | Optional LLM post-edit (sovereign-gated) |
| `logger.py` | 1,795 | JSON rotating log: pipeline.log + audit.log |
| `retry.py` | 3,335 | Retry decorator + JobCheckpoint crash-resume |
| `doc_extractor.py` | 4,203 | DOCX/PDF/TXT extraction + format-preserving translate |
| `cbp_uploader.py` | 6,454 | CBP portal upload |
| `sovereign_guard.py` | — | KB_SOVEREIGN_MODE enforcement |
| `sla_penalty.py` | — | SLA penalty calculator (tender §5.1B) |
| `ocr_sync.py` | — | Tesseract OCR sync verifier (tender §3.2) |
| `scorm_guard.py` | — | SCORM package detection + rejection (tender §3.1) |
| `correction_tracker.py` | — | Correction ticket lifecycle + defect liability tracker |

### finetune/
| File | Purpose |
|---|---|
| `finetune_indictrans.py` | IndicTrans2 full fine-tune v2 (all 22 langs, 5 epochs, early stop) |
| `finetune_seamless.py` | SeamlessM4T ASR + T2T fine-tune |
| `finetune_parler_tts.py` | Parler-TTS Large fine-tune on TTS audio data |
| `ds_zero3.json` | DeepSpeed ZeRO-3 config for multi-GPU fine-tuning |

### scripts/
| File | Purpose |
|---|---|
| `dub.py` | CLI entry point |
| `translate.py` | CLI text/audio/batch translation |
| `translation_memory.py` | Govt TM + human feedback manager |
| `eval_finetuned.py` | ChrF comparison: fine-tuned vs base IndicTrans2 |
| `fill_gap_langs.py` | Fetch parallel data for 8 gap languages from HuggingFace |
| `verify_datasets.py` | Deep integrity check of all 22 language datasets |
| `download_tts_data.py` | Download TTS audio data (FLEURS / Kathbath / IndicTTS) |
| `download_models.py` | Download all model weights including 22 standalone MMS VITS |
| `download_datasets.py` | Download parallel translation datasets |
| `check_gaps.py` | Verify 22-lang dataset coverage |
| `build_asr_index.py` | Build ASR fine-tune index |
| `test_pipeline.py` | Smoke test end-to-end |
| `clean_outputs.py` | Wipe output/ + checkpoints/jobs/ |
| `clean_and_run_all22.py` | Auto-clean then dub all 22 |
| `wipe_outputs.bat` | Windows batch wipe |

### ui/
| File | Purpose |
|---|---|
| `app.py` | Gradio 8-tab web UI, bound to 172.23.198.15 |
| `reviewer.py` | Human review + DOCX certificate export |

---

## 3. The 6-Step Pipeline

```
Input MP4/MP3/WAV
  │
  ▼ Step 1: Audio Extraction
  │   ffmpeg → 16kHz mono WAV
  │   Stale cache detection (re-extract if video newer than source.wav)
  │
  ▼ Step 1b: S2ST Fast-Path (Indic→Indic only)
  │   SeamlessM4T S2ST for hin/ben/kan/tel/urd pairs
  │   Success → mux + return (skips steps 2–5)
  │
  ▼ Step 2: ASR
  │   faster-whisper large-v3
  │   VAD filter, word timestamps, beam_size=4
  │   speech_pad_ms=200
  │   Hallucination guard: condition_on_previous_text=False
  │   Multi-temp fallback [0.0, 0.2, 0.4]
  │   Custom segment merger (min_words=6, min_dur=1.5s, max_dur=12s)
  │   tam/tel/mal/kan: longer windows (min_words=5, min_dur=2.0s, max_dur=15s)
  │   Nastaliq normalisation for urd/kas/snd
  │   _repair_asr_segments(): merges mid-sentence Whisper splits
  │   Exclusion check (§3.1): blocks PM speeches + YouTube content
  │
  ▼ Step 3: Translation
  │   TM lookup: exact HF → exact Govt → 85% fuzzy
  │   Token protection: __F__ (factual) + __NT__ (non-translatable) + __FMT__ (format)
  │   Engine routing (see Section 5)
  │   _naturalise(): dedup words, fix punctuation spacing
  │   _final_quality_check(): 10-rule gate
  │   Glossary applied last (never overwritten)
  │   Quality scoring per segment
  │   Low score → flagged for review (NOT silenced — gaps worse than imperfect TTS)
  │
  ▼ Step 4: TTS
  │   Parler-TTS Indic Large (fine-tuned checkpoint if present)
  │   → MMS standalone VITS per language (models/mms_standalone/<lang>/)
  │   tam/tel skip Parler → go direct to MMS VITS
  │   sat/kas/snd skip Parler → go direct to MMS VITS
  │   CUDA error recovery: reset engine, clear cache, retry
  │   VRAM freed between languages in multi-GPU mode
  │
  ▼ Step 5: Audio Assembly
  │   Segments placed at original timestamps
  │   Fit-to-slot: max 1.35× time-stretch, hard-trim if still over
  │   Duration ratio check: >1.20× → KB approval flag (§5.1B)
  │
  ▼ Step 6: Output
      SRT + VTT subtitles (video_duration param extends last subtitle)
      ffmpeg mux (dubbed audio → original video)
      Metadata JSON (quality, model versions, git hash, provenance)
      QA self-certification DOCX
      CBP portal upload (optional)

Output: output/<course_id>/<lang>/<course>_<lang>.mp4 + .srt + .vtt + _metadata.json
```

---

## 4. Language Code Reference (All 22)

| Code | Language | Script | IT2 flores200 | Primary Engine | TTS Engine |
|---|---|---|---|---|---|
| asm | Assamese | Bengali | asm_Beng | IndicTrans2 | MMS standalone |
| ben | Bengali | Bengali | ben_Beng | IndicTrans2 | MMS standalone |
| bod | Bodo | Devanagari | brx_Deva | IndicTrans2 | MMS standalone |
| doi | Dogri | Devanagari | doi_Deva | IndicTrans2 | MMS standalone (dgo) |
| guj | Gujarati | Gujarati | guj_Gujr | IndicTrans2 | MMS standalone |
| hin | Hindi | Devanagari | hin_Deva | IndicTrans2 | Parler-TTS |
| kan | Kannada | Kannada | kan_Knda | IndicTrans2 | MMS standalone (Parler skip) |
| kas | Kashmiri | Arabic | kas_Arab | NLLB-200 | MMS standalone |
| kok | Konkani | Devanagari | gom_Deva | NLLB-200 | MMS standalone |
| mai | Maithili | Devanagari | mai_Deva | IndicTrans2 | Parler-TTS |
| mal | Malayalam | Malayalam | mal_Mlym | IndicTrans2 | MMS standalone (Parler skip) |
| mar | Marathi | Devanagari | mar_Deva | IndicTrans2 | Parler-TTS |
| mni | Manipuri | Bengali | mni_Beng | SeamlessM4T (first) | MMS standalone |
| nep | Nepali | Devanagari | npi_Deva | IndicTrans2 | Parler-TTS |
| ory | Odia | Odia | ory_Orya | IndicTrans2 | MMS standalone |
| pan | Punjabi | Gurmukhi | pan_Guru | IndicTrans2 | Parler-TTS |
| san | Sanskrit | Devanagari | san_Deva | IndicTrans2 (pivot) | MMS standalone |
| sat | Santhali | Ol Chiki | sat_Olck | IndicTrans2 (pivot) | MMS standalone |
| snd | Sindhi | Arabic | snd_Arab | NLLB-200 | MMS standalone |
| tam | Tamil | Tamil | tam_Taml | IndicTrans2 | MMS standalone (Parler skip) |
| tel | Telugu | Telugu | tel_Telu | IndicTrans2 | MMS standalone (Parler skip) |
| urd | Urdu | Arabic | urd_Arab | IndicTrans2 | Parler-TTS |

---

## 5. Translation Engine Routing

### Routing logic in translator.py:

```python
_PIVOT_LANGS    = {"sat"}               # Hindi pivot via indic_indic
_NLLB_FIRST     = {"snd", "kas"}        # NLLB primary, Seamless second opinion
_SEAMLESS_FIRST = {"mni"}              # SeamlessM4T before IndicTrans2
```

**Full routing order:**
1. TM lookup (exact HF correction → exact Govt → 85% fuzzy) — if hit, skip all engines
2. Seamless-first: `mni` → SeamlessM4T
3. NLLB-first: `kas/snd` → NLLB → SeamlessM4T second opinion (pick higher score)
4. IndicTrans2 (primary for all other langs)
   - Via Hindi pivot for `sat` (src→hin→tgt)
5. SeamlessM4T fallback (if IndicTrans2 fails)
   - Score-based switch for pivot langs: if pivot score < 0.50 → try Seamless
6. NLLB-200 final fallback

**Post-translation pipeline (all engines):**
1. `_clean_unk()` — strip `<unk>` tokens
2. `_clean_mixed_lang()` — strip foreign-script word runs (pre-built Unicode range regexes)
3. Restore `__NT__` (non-translatable), `__F__` (factual), `__FMT__` (format) tokens
4. `_verify_factual_tokens()` — append missing numbers/dates at end
5. `_naturalise()` — dedup adjacent words, fix "word ," → "word,", collapse multi-punct
6. `_final_quality_check()` — 10 rules (see Section 6)
7. Glossary applied last

**Maithili drift guard:** Detects मैथिली-specific tokens (छथि/अछि/कयल/छत्हि) in Hindi output → retries via NLLB.

**Agglutinative language fix:** `tam/tel/mal/kan/hin/mar/ben/guj/pan/ory/asm/mai/nep/urd` → max_new_tokens=1024, no_repeat_ngram_size=0 (prevents blocking valid morphological suffixes).

---

## 6. Quality Scoring System

### Automated quality scoring (quality.py):

| Check | Penalty | What it catches |
|---|---|---|
| Length ratio < 0.3× or > 4× | −0.25 | Truncation or explosion |
| Source language leakage (< 50% native script) | −0.30 | Wrong script output |
| Repetition loop (4× identical consecutive words) | −0.35 | NMT hallucination |
| Untranslated (exact copy or >80% Latin for non-Latin target) | −0.35–0.40 | Engine failure |
| Too short (≥5 src words, <2 tgt words) | −0.30 | Drop |
| Transliteration detected (§3.2 compliance) | −0.35 | Latin rendering of Indic |
| Missing factual tokens (numbers/dates dropped) | −0.20 | Fact loss |
| Back-translation overlap < 0.25 | −0.15 | Semantic drift |

**Thresholds:**
- ≥ 0.55 → ✅ Pass
- 0.30–0.55 → ⚠️ Needs review (flagged)
- < 0.30 → ❌ Failed (flagged — NOT silenced, all go to TTS)

### Final quality check (10-rule gate in translator.py):
1. Non-empty output for non-empty source
2. Completeness: translated ≥ 20% source length
3. Grammar: sentence-initial capitalisation (English only)
4. Fluency: collapse 3+ identical punctuation
5. Consistency: all placeholder maps fully restored
6. Corruption: remove U+FFFD, null bytes
7. Placeholder-free: no `__NT__/__F__/__FMT__` artifacts
8. Mixed-lang: deferred (intentional Latin terms kept)
9. Formatting: normalise whitespace
10. Professional: strip `[UNK][PAD][BOS][EOS][MASK]`

---

## 7. TTS Engine Chain

```
Input: translated segment text + target language

Parler-TTS Indic Large
  Priority: checkpoints/parler_tts/best/ → models/indic_parler_tts_large/ → models/indic_parler_tts/
  Skip langs: sat, kas, snd, tam, tel
  Per-language prompts (_PARLER_DESCS): language-specific Indian voice descriptions
      ↓ fail or skip
MMS Standalone VITS
  Location: models/mms_standalone/<lang>/
  ALL 22 languages have individual VITS models
  doi → dgo subfolder (facebook/mms-tts-dgo)
  kas → urd-arabic proxy
      ↓ fail
Coqui XTTS-v2 (last resort, voice cloning optional)
  Supported: hin/ben/guj/mar/tam/tel/kan/mal/pan/urd
```

**CUDA recovery:** If TTS throws illegal-memory/CUDA error → `cuda.synchronize()` + `empty_cache()` + reload engine + retry.

---

## 8. Multi-GPU Architecture

```
Main process (GPU 0):
  - ASR runs ONCE → saved to _asr_shared/asr_cache.json
  - Seeded into each worker's JobCheckpoint

4 GPU Workers (spawn, not fork — Windows safe):
  GPU 0: langs [0, 4, 8, 12, 16, 20]  (round-robin)
  GPU 1: langs [1, 5, 9, 13, 17, 21]
  GPU 2: langs [2, 6, 10, 14, 18]
  GPU 3: langs [3, 7, 11, 15, 19]
  Each worker: translate → TTS → assemble → output
  VRAM freed between languages: cuda.empty_cache() + TTS engine unloaded

Optional TTS split (spare GPU):
  _worker_tts_split(): round-robin split TTS segments across primary + spare GPUs
  ~2× speedup when spare GPU available
```

---

## 9. Crash Recovery (retry.py)

`JobCheckpoint` class:
- Persists per-segment results to `checkpoints/jobs/<job_id>.json`
- Atomic write (write to `.tmp`, rename) — never corrupts on crash
- Thread-safe (instance-level lock)
- On restart: restores completed segments, skips re-translation
- Cleared on success, kept on failure for resume

`retry` decorator:
- Exponential backoff: delay × 2^(attempt-1)
- Default: 3 attempts, 2.0s base delay

---

## 10. Translation Memory (scripts/translation_memory.py)

**Storage:**
- `translation_memory/govt_tm.jsonl` — government-verified translations
- `translation_memory/human_feedback.jsonl` — human corrections (priority over govt TM)
- `translation_memory/correction_log.jsonl` — immutable audit trail

**Lookup priority:**
1. Exact match in human_feedback (highest trust)
2. Exact match in govt_tm
3. Fuzzy match ≥ 85% (SequenceMatcher) across both stores
4. ML engines

**Fine-tuning export:** Human corrections upweighted 5× (was 3× in v1) when exported as training pairs.

---

## 11. New Pipeline Modules (added after Aug 11)

### sovereign_guard.py
- `KB_SOVEREIGN_MODE=1` (default) blocks all foreign cloud LLM APIs (Groq/Gemini/OpenRouter)
- `assert_sovereign_allowed(provider)` raises PermissionError if blocked
- `sovereign_mode_enabled()` checks env var
- All LLM enhancer calls go through this guard

### sla_penalty.py
- Monthly target schedule: Month 1→50h, 2→55h, 3→100h, 4→125h, ...11→100h
- Penalty brackets:
  - Shortfall < 5% → 0%
  - 5–10% → 2% deduction
  - 10–20% → 4% deduction
  - >20% → 5% deduction
- `compute_sla(month, delivered_hours)` → full SLA result dict
- `format_sla_report(sla_rows)` → human-readable text table

### ocr_sync.py
- Tesseract OCR-based sync verifier (tender §3.2)
- Extracts one frame per segment via ffmpeg → OCR → compares audio_start vs text_appearance
- SYNC_THRESHOLD_S = 1.5s
- Degrades gracefully: if Tesseract not installed → timestamp-only sync check
- Results merged into quality_summary via `add_sync_flags_to_quality()`
- `verify_voiceover_sync()` adapter used by dubbing_pipeline

### scorm_guard.py
- Detects SCORM packages before processing (tender §3.1: Non-SCORM content only)
- Checks: .scorm extension, ZIP with imsmanifest.xml at root, SCORM namespace markers
- `assert_non_scorm(file_path)` raises ValueError if SCORM detected
- Conservative: flags imsmanifest.xml presence even if namespace unreadable

### correction_tracker.py
- Correction ticket lifecycle: open → in_progress → closed
- Storage: `translation_memory/correction_tickets.jsonl`
- 5-day correction deadline (tender §5.1B)
- Delay penalty: 0.5% per week overdue
- Generates Correction & Closure Report DOCX (Deliverable 4.5.iv)
- Defect liability tracker: 12-month post-acceptance window (SCC §7.1)
  - Storage: `translation_memory/defect_liability.jsonl`
- Weekly batch submission tracker (§4.3): 15–30 hours/week target
  - Storage: `translation_memory/weekly_batches.jsonl`

---

## 12. Fine-Tuning System

### finetune_indictrans.py v2 (key changes from v1)
1. All 22 langs in en_indic (was 12) — mni/sat/kas/snd/bod/doi now included
2. Per-language sampling weights by resource tier
3. Label smoothing: 0.1
4. Cosine LR schedule (was linear)
5. Curriculum: gold data first, synthetic mixed in later epochs
6. Quality filter: drops pairs where len(tgt)/len(src) < 0.3 or > 5.0
7. TM/HF upweight: 5× (was 3×)
8. 5 epochs with early stopping patience=2
9. Separate dev eval per language group
10. indic_indic: all 22×22 pairs
- `torch.compile()` on IndicTrans2 after loading (~20% speedup)
- GLOO backend (Windows compatible, not NCCL)

### finetune_parler_tts.py (new)
- Input: `datasets/tts/<lang>/train.jsonl` + `dev.jsonl`
- Format: `{"text": "...", "audio_path": "...", "lang": "hin"}`
- EnCodec/DAC audio → codec tokens on GPU
- Cosine LR, label smoothing 0.05, early stop patience=2, 5 epochs
- Per-lang weights: bod/doi/kok/san=3×, kas/mai/mni/sat/snd/hin=2×
- Saves to `checkpoints/parler_tts/best/` (auto-loaded by tts.py)

### Checkpoint issue (KNOWN)
- No mid-epoch recovery — crash during last epoch loses that epoch's work
- Only saves if dev_loss improves at end of epoch
- Fix needed: `accelerator.save_state()` every N steps

---

## 13. Datasets

### datasets/parallel/ (translation training)
- All 22 languages: train.jsonl + dev.jsonl + test.jsonl
- Format: `{"src": "...", "tgt": "...", "src_lang": "eng", "tgt_lang": "<lang>"}`
- Gap langs filled Aug 20: bod, doi, kok, san (via fill_gap_langs.py)
- Total size: ~1.2TB

### datasets/tts/ (TTS training)
- 14 languages present: asm, ben, guj, hin, kan, mal, mar, nep, ory, pan, snd, tam, tel, urd
- Format: `{"text": "...", "audio_path": "...", "lang": "hin"}`
- Sources: google/fleurs, ai4bharat/Kathbath, psk/indic-tts-966h

### datasets/asr/ (ASR fine-tune index)
- All 22 languages with dataset_info.json per language

---

## 14. Model Locations

| Model | Path | Size |
|---|---|---|
| faster-whisper large-v3 | models/indic_asr/ | ~3GB |
| IndicTrans2 en_indic | models/indic_tr/en_indic/ | ~1.2GB |
| IndicTrans2 indic_en | models/indic_tr/indic_en/ | ~1.2GB |
| IndicTrans2 indic_indic | models/indic_tr/indic_indic/ | ~1.2GB |
| Fine-tuned IT2 (en_indic) | checkpoints/indictrans/en_indic/best/ | ~1.2GB |
| Parler-TTS Indic Large | models/indic_parler_tts_large/ | ~3.6GB |
| Parler-TTS fine-tuned | checkpoints/parler_tts/best/ | ~3.6GB |
| SeamlessM4Tv2 | models/seamless/ | ~10GB |
| NLLB-200 | models/nllb/ | ~2.4GB |
| MMS standalone (×22) | models/mms_standalone/<lang>/ | ~100MB each |
| Coqui XTTS-v2 | models/xtts_v2/ | ~1.9GB |

---

## 15. Contract Compliance Hooks

| Tender Clause | Implementation |
|---|---|
| §3.1 Content exclusions | `_EXCLUSION_PATTERNS` (PM speeches + YouTube) + `scorm_guard.py` |
| §3.2 No transliteration | Script-range detection in `quality.py` |
| §3.2 Voiceover sync | `ocr_sync.py` (Tesseract, 1.5s threshold) |
| §4.2 CBP portal upload | `cbp_uploader.py` |
| §4.3 Weekly batches | `correction_tracker.py` weekly_batch tracker (15–30h/week) |
| §4.4 Monthly delivery | `sla_penalty.py` + monthly report generation |
| §4.5.iv Correction report | `correction_tracker.py` + `export_closure_report()` |
| §4.6 Completion report | `generate_completion_report()` in dubbing_pipeline |
| §5.1B Duration ratio | >1.20× → `duration_ratio_kb_approval_required: true` |
| §5.1B Correction deadline | 5-day ticket deadline, 0.5%/week penalty |
| SCC §7.1 Defect liability | 12-month defect tracker in `correction_tracker.py` |
| Data residency | `sovereign_guard.py` (KB_SOVEREIGN_MODE=1 default) |

---

## 16. UI Tabs (ui/app.py)

| Tab | What it does |
|---|---|
| 🎬 Dub Video / Audio | Upload MP4/MP3, select languages, run full pipeline. Quality scores Dataframe per language. Job semaphore: 1 job at a time. |
| 📄 Translate Document | DOCX (format-preserving), TXT, JSON quiz/metadata. PDF returns §3.1 error. |
| 📋 QA Certificate | Generate self-certification DOCX with SLA thresholds and penalty schedule. |
| 👤 Human Review | Bilingual segment grid, approve/correct/reject, export review certificate. |
| ⚙️ Settings | HF token, output folder, checkpoint/resume info. |
| 📅 Monthly Delivery | Track hours per month, export Month-wise Submission Report + Completion Report (.xlsx). |
| 📖 Glossary | Add/import/export standardised terminology glossary (.xlsx). |
| 📊 Live Logs | Real-time pipeline log stream (auto-refresh 3s). |

Server: `app.launch(server_name="172.23.198.15", server_port=<auto 7860-7870>)`

---

## 17. Infrastructure (4× A6000 Machine)

| Resource | Available | Used (inference) | Headroom |
|---|---|---|---|
| VRAM | 192GB (4×48GB) | ~46GB | ~146GB |
| RAM | 128GB | ~23GB | ~105GB |
| Storage needed | — | ~4TB NVMe | Check disk |

Monthly capacity: ~2,200 dubbed-hours/month (contract needs 125h peak).
Fine-tuning: ZeRO-3 fits on 4× A6000 (~20–25GB/GPU).
HDD vs NVMe for fine-tuning: ~6 hours per epoch difference on 1.2TB dataset.

---

## 18. Known Issues / Gaps

| Issue | Severity | Notes |
|---|---|---|
| No mid-epoch checkpoint in fine-tuning | High | Crash on last epoch = epoch lost. Fix: `accelerator.save_state()` |
| voice_clone.py absent | Medium | `VoiceCloner` import guarded with try/except in `__init__.py` |
| Source separation (demucs) not implemented | Medium | Background music stripped with narration — no M&E stem preserved |
| Speaker diarization not implemented | Low | Single-narrator courses fine; multi-speaker needs `pyannote.audio` |
| COMET QE scoring not implemented | Low | Custom heuristic used instead |
| LoRA adapter fine-tuning not implemented | Low | Full fine-tuning used, not parameter-efficient adapters |
| Tesseract may not be installed | Low | `ocr_sync.py` degrades gracefully to timestamp-only check |
| Windows ASR num_workers=1 | Info | >1 deadlocks on Windows (no fork) |

---

## 19. Key Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `KB_SOVEREIGN_MODE` | `1` | Block foreign LLM APIs (Groq/Gemini/OpenRouter) |
| `PIPELINE_GPU` | `0` | Which GPU this worker uses |
| `TTS_DEVICE` | auto | Override TTS device |
| `HF_TOKEN` | — | HuggingFace download token |
| `CBP_USERNAME` | — | CBP portal login |
| `CBP_PASSWORD` | — | CBP portal login |
| `GROQ_API_KEY` | — | Optional LLM post-edit (sovereign mode must be 0) |
| `GEMINI_API_KEY` | — | Optional LLM post-edit |
| `OPENROUTER_API_KEY` | — | Optional LLM post-edit |
| `NUMBA_DISABLE_JIT` | `1` | Prevent NumPy version crash on Numba import |
