# KB Translation System — Interview Q&A Guide
**Project: iGOT Karmayogi | RFB IN-KBL-543730-NC-RFB**
**Role: AI/ML Engineer — Offline Dubbing Pipeline**

---

## SECTION 1: PROJECT OVERVIEW QUESTIONS

---

**Q1. Can you give a high-level overview of this project?**

This is a fully offline, end-to-end AI dubbing pipeline built for the Government of India's iGOT Karmayogi platform under tender RFB IN-KBL-543730-NC-RFB. The system automatically translates and dubs government training videos into all 22 constitutionally scheduled Indian languages using a 3-stage pipeline: ASR (speech recognition) → Neural Machine Translation → TTS (text-to-speech). The key constraint was 100% offline — no internet, no external APIs, no data leaving the system. We deployed on a Dell workstation with 4× NVIDIA RTX A6000 GPUs (48GB VRAM each), 128GB RAM, and Intel Xeon w9-3495X.

---

**Q2. What was the scale of this project?**

- 1,105 hours of iGOT training content
- 22 target languages = 24,310 dubbed hours total
- 11-month delivery window, monthly batches of 50–125 hours
- Quality SLA: 98% linguistic accuracy per KB tender §5.1B
- All processing on-premise — zero cloud dependency

---

**Q3. Why was offline deployment a hard requirement?**

Government of India data sovereignty rules prohibit sending training content to external APIs (OpenAI, Google, AWS). The content includes sensitive government training material. Additionally, deployment is in low-connectivity government data centres where internet access is unreliable. All ~28GB of model weights run locally on NVMe SSD.

---

**Q4. Walk me through the 6-step pipeline.**

1. **Audio Extraction** — ffmpeg extracts 16kHz mono WAV from MP4/MP3/WAV input. Stale cache detection re-extracts if source video is newer than cached WAV.
2. **S2ST Fast Path** — SeamlessM4T Speech-to-Speech for Indic→Indic pairs (hin/ben/kan/tel/urd only). If successful, skips ASR+TTS entirely and returns early.
3. **ASR** — faster-whisper large-v3 (CTranslate2 optimised) produces sentence-level segments with timestamps. Hallucination guard: `condition_on_previous_text=False`, multi-temperature fallback [0.0, 0.2, 0.4].
4. **Translation** — IndicTrans2 GPU batch → SeamlessM4T → NLLB-200 fallback chain. Factual token protection, glossary injection, quality scoring per segment.
5. **TTS** — Parler-TTS Indic Large → MMS standalone VITS → XTTS-v2 fallback. Per-segment WAV files placed at original timestamps, sped up max 1.35× to fit slot.
6. **Output** — SRT+VTT subtitles, ffmpeg mux to replace audio in video, metadata JSON with quality scores, duration ratio check.

---

## SECTION 2: TECHNICAL DEEP-DIVE QUESTIONS

---

**Q5. Why did you choose IndicTrans2 as the primary translation engine over SeamlessM4T?**

Three reasons:
1. IndicTrans2 is purpose-built for Indian languages by AI4Bharat — it has dedicated training data for all 22 scheduled languages including low-resource ones like Maithili, Dogri, Bodo.
2. It supports GPU batch inference natively — we process all segments in a single forward pass, which is critical for throughput on 1-hour videos with 200+ segments.
3. We fine-tuned it on government domain parallel data (iGOT-specific terminology), which SeamlessM4T doesn't support as easily.

SeamlessM4T is used as fallback and for S2ST (speech-to-speech) which IndicTrans2 doesn't support at all.

---

**Q6. How does the translation engine routing work?**

It's a decision tree per segment:

- `src == tgt` → passthrough (no translation)
- Fully non-translatable (URL/code/path) → passthrough unchanged
- `tgt in SEAMLESS_FIRST` (mni/Manipuri) → SeamlessM4T first, IndicTrans2 second opinion
- `tgt in NLLB_FIRST` (kas/snd/kok) → NLLB-200 primary, SeamlessM4T score-based second opinion
- `tgt in PIVOT_LANGS` (sat/Santhali) → IndicTrans2 via Hindi pivot (eng→hin→sat)
- Otherwise → IndicTrans2 GPU batch → SeamlessM4T fallback → NLLB-200 final fallback

For NLLB-first and Seamless-first langs, we run both engines and pick whichever scores higher (threshold: 0.05 margin).

---

**Q7. Explain the token protection system.**

We protect three categories of tokens before sending text to translation engines:

- `__F0__` placeholders — numbers, dates, currency (₹50,000), measurements, percentages. These are factual tokens that must never be altered or dropped. After translation, we verify every source factual token appears in the output and append missing ones.
- `__FMT0__` placeholders — format strings like `{name}`, `%s`, `${var}`, `{{jinja}}`. These are template variables in government content that must survive translation intact.
- `__NT0__` placeholders — URLs, file paths, code identifiers, @mentions. These are non-translatable and pass through unchanged.

The protection is applied right-to-left (to preserve offsets), and restoration is verified by a final quality check that flags any unreplaced placeholder artifacts.

---

**Q8. What is the quality scoring system and what thresholds do you use?**

Every translated segment gets a score 0–1 from three methods:

1. **Heuristic** (8 rules): length ratio, source language leakage (native script < 35% = fail), repetition loops (4+ identical consecutive words), untranslated detection, too-short check, transliteration detection (Latin > 60% for non-Latin target = -0.35 penalty), factual token preservation.
2. **ChrF** — character n-gram F-score (β=2, n=6). Works well for Indic scripts since they're morphologically rich.
3. **Back-translation** — translate output back to source, measure word overlap.

Thresholds:
- ≥ 0.55 → Pass (accepted)
- 0.30–0.55 → Review (flagged for human review, still goes to TTS)
- < 0.30 → Failed (flagged, still goes to TTS — silence is worse than imperfect translation)

Real production result on KB_COURSE_001 Tamil: avg_score = 1.0, pass_rate = 1.0, 36 segments, 0 failed.

---

**Q9. How does the checkpoint/resume system work?**

File: `checkpoints/jobs/<job_id>.json` (job_id = MD5 of filename+target_lang, first 12 chars).

Structure:
```json
{
  "completed": { "0": {...translated_seg...}, "1": {...} },
  "meta": { "segments": [...asr_output...], "detected_src_lang": "eng", "duration": 356.35 }
}
```

On resume: ASR is skipped (segments loaded from meta), already-translated segments are loaded from `completed`, only pending segments go to the translation engine. Writes are atomic — tmp file written then renamed, so partial writes never corrupt the checkpoint. On success, checkpoint is deleted. `--force` clears both output files and checkpoint so everything re-runs from scratch.

---

**Q10. How does multi-GPU parallelism work?**

ASR runs once in the main process (shared across all workers — eliminates 4× redundant transcription). The ASR output is cached to `_asr_shared/asr_cache.json`.

22 target languages are distributed round-robin across N GPUs:
- GPU 0: langs 0, 4, 8, 12, 16, 20
- GPU 1: langs 1, 5, 9, 13, 17, 21
- etc.

Each worker gets `PIPELINE_GPU=N` env var set before importing torch, so all CUDA allocations go to the assigned GPU. Workers run translate+TTS+assemble independently. Results are merged at the end. Effective ~4× speedup: a 1-hour video across all 22 languages takes ~6 hours on 4 GPUs vs ~22 hours on 1 GPU.

---

**Q11. How does the TTS engine routing work?**

Primary engine is Parler-TTS Indic Large (44kHz, GPU batch of 4 segments). But Parler has a known issue with Dravidian scripts — it produces near-silence for Tamil/Telugu/Kannada/Malayalam without dedicated fine-tuning. So:

- Dravidian langs (tam/tel/kan/mal) → MMS standalone VITS primary
- Bengali-script family (ben/asm/mni) → MMS standalone VITS primary
- Arabic-script family (urd/kas) → MMS standalone VITS primary
- Devanagari family (hin/mar/nep/mai/san) → Parler-TTS Indic Large primary

Fallback chain per segment: Parler attempt 1 → Parler attempt 2 → Parler split-half → MMS standalone VITS → MMS adapter → write silence.

Voice consistency: single RNG seed (42) pinned once before warmup — identical voice throughout entire video. Parler text encoder pre-computed once per video and reused for all segments.

---

**Q12. How does the audio assembly fit-to-slot work?**

Each TTS segment must fit within its original timestamp slot. Strategy (priority order):
1. TTS fits within slot → place as-is
2. TTS overflows into silence gap before next speech → allow, no speed change
3. TTS would overlap next speech → speed up via ffmpeg atempo (max 1.35×)
4. Still over after 1.35× → extend limit by 300ms
5. Still over → trim with 250ms fade-out (last resort)

Silence gaps are filled with pink noise at 0.002 amplitude — prevents jarring dead silence between segments. Audio post-processing: high-pass at 80Hz (removes DC/rumble), low-pass at 9500Hz for MMS (removes VITS consonant harshness), normalise to -3 dBFS.

---

## SECTION 3: CHALLENGES FACED

---

**Q13. What was the hardest technical challenge in this project?**

The Devanagari script collision problem. Hindi, Maithili, Bodo, Marathi, Nepali, Sanskrit, Dogri, Konkani all use the same Devanagari script. IndicTrans2 would sometimes output Maithili verb forms (अछि/छथि/करैत) in Hindi translations, or Hindi verb markers (है/होता/करता) in Maithili/Bodo output. Script-level stripping cannot distinguish them since they share the same Unicode block (U+0900–U+097F).

Solution: morpheme-level drift guards using regex patterns for language-exclusive verb markers. For Hindi output: detect 2+ Maithili-exclusive morphemes → retry via NLLB-200. For Maithili output: detect 3+ Hindi verb markers → retry via NLLB. For Bodo output: detect 2+ Hindi markers → retry via NLLB. This required deep linguistic research into each language's exclusive morphological patterns.

---

**Q14. What challenges did you face with ASR?**

Three main issues:

1. **Hallucination** — Whisper would sometimes repeat the same phrase in a loop or output garbage when `condition_on_previous_text=True`. Fixed by setting it to False and adding a multi-temperature fallback [0.0, 0.2, 0.4].

2. **Mid-sentence splits** — Whisper splits on breath pauses, not sentence boundaries. A sentence like "The scheme provides loans up to" would be split into two segments, breaking translation context. Fixed with `_repair_asr_segments()` which merges continuations detected via: lowercase first word (Latin), virama character (Indic mid-akshar), dangling preposition at end of previous segment, or gap < 200ms with no sentence-ending punctuation.

3. **Nastaliq normalisation** — Urdu/Kashmiri/Sindhi ASR output sometimes had Arabic-script artifacts from the checkpoint. Added normalisation pass for these scripts.

---

**Q15. What challenges did you face with TTS?**

1. **Parler amplitude issue for Dravidian** — Parler-TTS Indic Large produces near-silence for Tamil/Telugu/Kannada/Malayalam. Root cause: the model was trained primarily on Devanagari-family languages. Workaround: route all 4 Dravidian languages to MMS standalone VITS as primary.

2. **Voice drift** — Without pinning the RNG seed, each segment would have a slightly different voice. Fixed by pinning seed=42 once before the primer warmup call, and pre-computing the Parler text encoder embedding once per video.

3. **CUDA OOM during TTS** — On long videos with many segments, GPU memory would occasionally OOM. Fixed with: `torch.cuda.synchronize()` + `empty_cache()` + `self._tts = None` (force reload) + retry with MMS fallback.

4. **Leading silence in Parler output** — Parler-TTS sometimes generates 100–300ms of garbled audio at the start of each segment. Fixed by trimming leading silence below threshold 0.001.

---

**Q16. What challenges did you face with the translation quality?**

1. **Konkani dialect drift** — IndicTrans2 uses `gom_Deva` (Goan Konkani) which drifts to Goan dialect instead of standard Konkani. Fixed by routing Konkani to NLLB-200 as primary.

2. **Santhali (Ol Chiki script)** — IndicTrans2 has no direct English→Santhali model. Fixed with Hindi pivot: eng→hin→sat via IndicTrans2 indic_indic direction.

3. **Empty translations** — Batch translation would occasionally return empty string for a segment. Fixed with completeness guard: empty output for non-empty source triggers per-segment retry, then source text as absolute last resort (better to speak English than silence).

4. **Placeholder artifacts** — `__NT0__` or `__F0__` tokens would sometimes survive into the final translation if the engine hallucinated around them. Fixed with final quality check rule 7 which strips any `__WORD__` pattern artifacts.

---

**Q17. What was the most critical bug you fixed?**

The completeness violation bug in batch translation. When IndicTrans2 batch processed N segments, it would occasionally return N-1 results (dropping one segment silently). This caused an index misalignment — segment 5's translation would be assigned to segment 6, and so on for the rest of the video. The dubbed audio would be completely wrong from that point.

Fix: added a strict completeness guard after every batch call:
```python
if len(batch_results) != len(text_local):
    log.error(f"Completeness violation: sent {len(text_local)}, got {len(batch_results)}")
    # Fall back to per-segment translation for entire batch
```
Also added a final loop checking every result slot for None and retrying per-segment if found.

---

**Q18. What other critical bugs did you fix?**

1. **Stale WAV cache bug** — If a user replaced the source video with a new version, the pipeline would use the old cached `source.wav` and produce wrong output. Fixed with mtime comparison: re-extract if `source.wav.mtime < video.mtime`. Also clears ASR checkpoint so transcription re-runs.

2. **Concurrent job corruption** — Two UI requests for the same course+language would run simultaneously and overwrite each other's output files. Fixed with per-(course_id, lang) threading locks using `threading.Lock()`.

3. **Windows path length crash** — Long course IDs + deep output paths would hit Windows 260-char limit and crash with `FileNotFoundError`. Fixed by sanitising course IDs (max 64 chars, alphanumeric only) and documenting the Windows long path registry fix.

4. **IndicTrans2 tokenizer conflict** — `AutoTokenizer.from_pretrained()` passes `src_vocab_file` as a kwarg which clashes with `IndicTransTokenizer`'s positional `src_vocab_fp` parameter. Fixed by loading the tokenizer class directly from the model's local module via `importlib.util.spec_from_file_location`.

5. **SeamlessM4T S2ST return type change** — After a transformers version upgrade, `model.generate()` for S2ST started returning a `(waveform_tensor, sample_rate)` tuple instead of a `SeamlessM4TGenerationOutput` object. Fixed with: `if isinstance(out, tuple): wav_tensor, out_sr = out[0], out[1]`.

6. **Checkpoint atomic write** — Original implementation wrote JSON directly to the checkpoint file. If the process crashed mid-write, the checkpoint was corrupted and resume would fail. Fixed with tmp→rename pattern: write to `.tmp` file, then `tmp.replace(path)` which is atomic on NTFS/ext4.

---

## SECTION 4: ACCURACY & METRICS

---

**Q19. What accuracy scores did you achieve in production?**

Real production run on `KB_COURSE_001` (PNB Pradhan Mantri Mudra Yojana, English → Tamil):
- Segments: 36
- avg_score: **1.0** (heuristic)
- avg_chrf: 0.0 (cross-script pairs — ChrF requires same script)
- needs_review: 0
- failed: 0
- pass_rate: **1.0 (100%)**
- Engine used: IndicTrans2 for all 36 segments
- Duration: 356.35 seconds

The system was tested across 15 languages for KB_COURSE_001 and 14 languages for Fine_Tuning_Initiative_Report document translation.

---

**Q20. Why is avg_chrf 0.0 for Tamil?**

ChrF (character n-gram F-score) requires a reference translation to compare against. In our pipeline, we don't have human reference translations — we're generating them. The ChrF score is only meaningful for same-script pairs where we can do back-translation comparison. For English→Tamil (Latin→Tamil script), the character n-gram overlap is zero by definition since the scripts are completely different. The heuristic score and back-translation score are the meaningful metrics for cross-script pairs.

---

**Q21. How do you meet the 98% accuracy SLA from the KB tender?**

Three-layer approach:
1. **Automated scoring** — every segment scored 0–1, segments below 0.55 flagged for human review
2. **Human review UI** — reviewer.py provides approve/correct/reject per segment with DOCX certificate export
3. **Translation Memory** — government-verified translations stored in `govt_tm.jsonl`, injected via exact+fuzzy matching (85% threshold) before any model inference

The QA self-certification DOCX is auto-generated per course per language with checklist: linguistic accuracy, terminology consistency, no mixed languages, audio-text sync, technical format compliance.

---

## SECTION 5: ARCHITECTURE & DESIGN QUESTIONS

---

**Q22. Why did you use lazy model loading?**

Models total ~28GB. Loading all of them at startup would take 3–5 minutes and consume all VRAM before any work starts. With lazy loading, each model loads on first use. In multi-GPU mode, each worker only loads the models it needs for its assigned languages. Between languages, we call `self._tts = None` to unload the TTS engine and free ~4GB VRAM before the next language starts.

---

**Q23. How did you handle the document translation (DOCX) format preservation?**

Format-preserving translation in `doc_extractor.py`:
- Collect all runs in a paragraph → join into full_text → translate → put result in `runs[0].text` → clear `runs[1:].text`
- This preserves bold/italic/underline/font on the first run while replacing content
- Tables: cell-by-cell paragraph translation
- Headers/footers: all 6 variants (first/even/odd × header/footer)
- Inline images: copied unchanged
- Hyperlinks: text translated, URL preserved

PDF translation is blocked per KB tender §3.1 — original PDF uploaded to CBP portal as-is.

---

**Q24. How does the Translation Memory work?**

Three files in `translation_memory/`:
- `govt_tm.jsonl` — government-verified translations added via CLI
- `human_feedback.jsonl` — corrections from the human review UI
- `correction_log.jsonl` — audit log of all corrections

Lookup uses exact match first, then fuzzy match at 85% threshold (Levenshtein-based). TM is checked before any model inference in `_translate_text()`. If an exact hit from `govt_tm` or `human_feedback` is found, it's returned immediately without calling any translation engine. This ensures government-approved terminology is used consistently across all courses.

---

**Q25. How does the Gradio UI work?**

8-tab interface in `ui/app.py`:
1. Dub Video/Audio — upload MP4/MP3, select languages, run full pipeline with progress
2. Translate Document — DOCX/TXT/JSON translation (PDF blocked)
3. QA Certificate — generate self-certification DOCX
4. Human Review — approve/correct/reject segments, export review certificate
5. Settings — HF token, output folder
6. Monthly Delivery — track hours, export submission reports (.xlsx)
7. Glossary — build/export standardised terminology (.xlsx)
8. Live Logs — real-time pipeline.log stream (auto-refresh 3s)

The UI calls the same `DubbingPipeline` class as the CLI — no separate code path.

---

## SECTION 6: SYSTEM DESIGN & SCALABILITY

---

**Q26. How would you scale this to handle 10× the current load?**

Current bottleneck is TTS (Parler-TTS is sequential within a language). Options:
1. Add more RTX A6000 GPUs — pipeline already supports N-GPU via `--num-gpus`
2. TTS split across spare GPUs — `_synthesize_tts_split()` already implemented, distributes odd/even segments across primary + spare GPUs
3. Batch size increase for Parler — currently 4 segments/pass, can increase to 8 on 48GB VRAM
4. Quantise MMS-VITS to INT8 — currently fp32, could halve memory and increase throughput

For translation, IndicTrans2 batch is already the bottleneck-free path — it processes all segments in one forward pass.

---

**Q27. How do you ensure data sovereignty and audit compliance?**

- All models run on-premise — no network calls during inference
- `.env` has no external API keys set in production (only HF_TOKEN for model download, which is a one-time operation)
- Every job start/success/failure written to `logs/audit.log` as JSON with: event, job_id, file, src, tgt, course_id, host, elapsed_s, output, quality
- Metadata JSON per output includes provenance: model versions, git commit, host, generated_at, contract number
- CBP portal upload uses HTTPS with credentials from `.env` — credentials never logged

---

## SECTION 7: BEHAVIOURAL / SITUATIONAL QUESTIONS

---

**Q28. Tell me about a time you had to make a difficult technical trade-off.**

The quality gate decision. Originally, segments scoring below 0.30 were silenced — no audio sent to TTS. The reasoning was: don't send wrong-language audio to the viewer. But in practice, silencing created jarring gaps in the dubbed video that were more disruptive than imperfect translation. A 2-second silence in the middle of a sentence is worse than a slightly awkward translation.

Changed the behaviour: all segments go to TTS regardless of score. Low-score segments are flagged for human review in the metadata JSON and the review UI. The quality gate now informs the human reviewer rather than making autonomous decisions about what the viewer hears.

---

**Q29. How did you handle a situation where a model produced consistently wrong output for a specific language?**

Konkani (kok). IndicTrans2 uses the `gom_Deva` flores200 code for Konkani, which is Goan Konkani — a specific dialect. For standard Konkani content, it was producing Goan dialect-specific vocabulary that standard Konkani speakers found unnatural.

Diagnosis: checked the IndicTrans2 training data — it was trained on Goan Konkani parallel data from the Samanantar corpus. The model was doing exactly what it was trained to do, just not what we needed.

Fix: routed Konkani to NLLB-200 as primary engine. NLLB uses `kok_Deva` which is more neutral standard Konkani. Added a comment in the code explaining the routing decision so future maintainers understand why Konkani is in `_NLLB_FIRST`.

---

**Q30. What would you do differently if you rebuilt this project?**

1. **Streaming TTS** — currently we synthesise all segments then assemble. Streaming synthesis (synthesise segment N while assembling segment N-1) would reduce peak memory and improve latency for long videos.
2. **Separate ASR fine-tuning** — we fine-tuned IndicTrans2 but not faster-whisper. ASR errors propagate through the entire pipeline. Fine-tuning Whisper on government domain speech (iGOT lecture style) would improve ASR accuracy for domain-specific terms.
3. **Segment-level caching** — currently checkpoint stores translated segments but not TTS audio. If TTS crashes mid-video, all synthesis re-runs. Adding TTS segment cache would make resume faster.
4. **Better Santhali support** — the Hindi pivot for Santhali (eng→hin→sat) introduces two translation errors. A direct English→Santhali model would be better, but none exists offline currently.

---

## SECTION 8: QUICK-FIRE TECHNICAL QUESTIONS

---

**Q31. What is CTranslate2 and why did you use it for ASR?**

CTranslate2 is an optimised inference engine for transformer models. faster-whisper uses it to run Whisper large-v3 with INT8 quantisation on GPU. Compared to the original Whisper implementation, it's ~4× faster and uses ~2× less VRAM. On our RTX A6000, a 6-minute audio segment transcribes in ~8 seconds vs ~32 seconds with vanilla Whisper.

---

**Q32. What is DeepSpeed ZeRO-3 and when would you use it?**

ZeRO-3 (Zero Redundancy Optimizer stage 3) shards model parameters, gradients, and optimizer states across all GPUs — each GPU holds only 1/N of the model. Used for fine-tuning models too large to fit on a single GPU. Our `finetune/ds_zero3.json` config is for fine-tuning IndicTrans2 (~1.2GB per direction) across 4 GPUs with bf16 mixed precision. For inference we don't need ZeRO — models fit comfortably in 48GB VRAM.

---

**Q33. What is the flores200 language code format?**

flores200 codes are used by IndicTrans2 and NLLB-200. Format: `<iso639_3>_<script>`. Examples:
- `eng_Latn` — English, Latin script
- `hin_Deva` — Hindi, Devanagari script
- `tam_Taml` — Tamil, Tamil script
- `urd_Arab` — Urdu, Arabic script
- `ben_Beng` — Bengali, Bengali script

Our `lang_config.py` maps our short codes (hin, tam, etc.) to flores200 codes for each engine.

---

**Q34. What is the difference between SRT and VTT subtitle formats?**

Both are timed text formats. SRT (SubRip) is the older format — plain text with sequence numbers, timestamps (HH:MM:SS,mmm), and text. VTT (WebVTT) is the web standard — used by HTML5 `<video>` elements, supports CSS styling, positioning, and cue settings. We generate both: SRT for video players (VLC, media players) and VTT for web delivery on the iGOT portal.

---

**Q35. How does the CBP portal upload work?**

`cbp_uploader.py` authenticates via `POST /api/user/v1/login` → gets Bearer token. Then scans the output directory for files matching patterns (`*_tam.mp4`, `*_tam.srt`, etc.) and uploads each via `POST /api/content/v1/upload` with multipart form data. Retry: 3 attempts with 5s/10s/15s backoff. Credentials are read from `.env` and never logged — only `type(e).__name__` on error. Generates a JSON submission report for KB records.

---

## SECTION 9: NUMBERS TO REMEMBER

| Metric | Value |
|--------|-------|
| Languages supported | 22 (all scheduled Indian languages) |
| Total model size | ~28 GB |
| GPU setup | 4 × RTX A6000, 48GB VRAM each |
| Total VRAM | 192 GB |
| Peak VRAM per GPU | ~12 GB (all models loaded) |
| VRAM headroom | ~36 GB free per GPU |
| ASR model | faster-whisper large-v3, ~3GB |
| Translation primary | IndicTrans2, ~1.2GB × 3 directions |
| TTS primary | Parler-TTS Indic Large, ~3.6GB |
| Quality pass threshold | ≥ 0.55 |
| Quality review threshold | 0.30–0.55 |
| TM fuzzy match threshold | 85% |
| Max TTS speed-up | 1.35× |
| Duration ratio warning | >20% longer than original |
| Fit-to-slot gap threshold | 200ms |
| Batch size (Parler) | 4 segments/pass |
| Max tokens (IndicTrans2) | 768 (1024 for agglutinative langs) |
| Checkpoint flush | After entire batch (not per segment) |
| Audit log | Every job start/success/failure |
| Production pass rate | 100% (KB_COURSE_001, Tamil, 36 segs) |
| Contract scope | 1,105 hours × 22 langs = 24,310 hours |
| Delivery window | 11 months |
| Quality SLA | 98% linguistic accuracy |

---

*Prepared from source code analysis of KB Translation System v1.0*
*Contract: RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi, Government of India*


---

## SECTION 10: FINE-TUNING DEEP-DIVE

---

**Q36. Walk me through how you fine-tuned IndicTrans2.**

We fine-tuned all 3 directions: `en_indic` (English → all 22 Indian langs), `indic_en` (Indian → English), and `indic_indic` (Indian → Indian). The script is `finetune/finetune_indictrans.py` using HuggingFace Accelerate with gloo backend (Windows — no NCCL).

Key setup:
- 4 GPUs, bf16 mixed precision
- Batch size 8 per GPU, gradient accumulation 8 → effective batch = 256
- AdamW optimizer: lr=2e-5, weight_decay=0.01, betas=(0.9, 0.98), eps=1e-9
- Cosine LR schedule with 6% warmup steps
- 5 epochs max, early stopping patience=2 (stops if dev loss doesn't improve for 2 consecutive epochs)
- Label smoothing = 0.1 (reduces overfit on low-resource languages)

The pipeline automatically uses fine-tuned checkpoints if present at `checkpoints/indictrans/<direction>/best/`, falls back to base model in `models/indic_tr/` if absent.

---

**Q37. How did you handle the dataset imbalance across 22 languages?**

Per-language sampling weights based on resource tier:
- High-resource (>100K pairs): weight 1.0 — ben, guj, kan, mal, mar, ory, pan, tam, tel, asm, urd, nep
- Medium-resource (10K–100K): weight 2.0 — kas, mai, mni, sat, snd (oversample 2×)
- Low-resource (<10K): weight 4.0 — bod, doi, kok, san (oversample 4×)
- Hindi pivot: weight 3.0 — Hindi is the pivot language for mni/sat/san, so it gets extra weight

For synthetic data (back-translated pairs), we apply 0.5× on top of the language weight — synthetic data is lower quality than gold parallel data.

Translation Memory and human feedback records are repeated 5× (TM_WEIGHT=5) — these are the highest quality signal since they're government-verified.

---

**Q38. What is curriculum learning and how did you apply it here?**

Curriculum learning = train on easier/cleaner data first, introduce harder/noisier data later. We applied it to synthetic data:

- Epochs 1–2: only gold parallel data (human-translated, clean)
- Epoch 3+: gold + synthetic data mixed in

The reasoning: if the model sees noisy synthetic data from epoch 1, it can learn bad patterns early. Starting with clean gold data establishes a strong baseline, then synthetic data adds coverage for rare language pairs without corrupting the core quality.

Controlled by `SYNTHETIC_EPOCH = 3` — `build_records()` checks `epoch >= SYNTHETIC_EPOCH` before including synthetic records.

---

**Q39. Why did you disable gradient checkpointing?**

IndicTrans2 uses an old `_set_gradient_checkpointing` API that silently ignores `use_reentrant=False`. On bf16 multi-GPU training, this causes a CUDA unspecified launch failure — the model crashes mid-training with a cryptic CUDA error.

The fix was to disable gradient checkpointing entirely and compensate for the VRAM increase by halving batch size (16→8) and doubling gradient accumulation (4→8). Effective batch size stays the same (256), training dynamics are identical, but VRAM usage is higher per step. With 48GB VRAM per GPU, we had enough headroom to absorb this.

---

**Q40. How does the quality filter work in the dataset?**

`_quality_ok(src, tgt)` drops pairs where:
- Either string is empty
- `len(tgt) / len(src) < 0.25` — translation is suspiciously short (likely truncated or wrong pair)
- `len(tgt) / len(src) > 6.0` — translation is suspiciously long (likely misaligned pair)

This is a character-level ratio, not word-level, because Indic scripts are morphologically rich — a single Hindi word can be 3× longer in characters than its English equivalent. The 0.25–6.0 range was tuned empirically on the Samanantar corpus.

---

**Q41. How does the dev evaluation work across 22 languages?**

Dev loss is computed per epoch using `dev.jsonl` for each language. The loss is reduced across all GPUs using `accelerator.reduce(dev_loss_sum, reduction="mean")` so all processes agree on the same dev loss value.

Best checkpoint is saved when dev loss improves. Early stopping triggers after 2 consecutive epochs without improvement. This prevents overfitting on high-resource languages while still training long enough for low-resource ones.

One limitation: we use a single aggregate dev loss across all languages. A regression in Santhali (sat) could be masked by improvement in Hindi. Ideally we'd track per-language dev loss separately — this is noted as a future improvement.

---

**Q42. Why gloo backend instead of NCCL for distributed training?**

NCCL (NVIDIA Collective Communications Library) requires Linux — it doesn't work on Windows. Our training machine runs Windows 11 Pro for Workstations. gloo is the cross-platform backend that works on both Windows and Linux. Performance difference is minimal for our setup since the bottleneck is GPU compute, not inter-GPU communication bandwidth.

The Windows-specific env vars set at the top of the script:
```python
os.environ["MASTER_ADDR"] = "127.0.0.1"  # override Docker DNS
os.environ["TORCH_DISTRIBUTED_DEFAULT_BACKEND"] = "gloo"
os.environ["ACCELERATE_USE_FSDP"] = "false"
```

---

## SECTION 11: QUALITY SCORING INTERNALS

---

**Q43. Walk me through exactly how score_segment() works.**

`score_segment()` in `quality.py` starts at score=1.0 and subtracts penalties:

1. **Length ratio** — `tgt_words / src_words`. If < 0.3 or > 4.0: `-0.25`. Catches truncated or bloated translations.

2. **Source language leakage** — counts native script chars vs Latin chars. If native script < 35% of total alpha chars: `-0.30`. Threshold was raised from 0.5 to 0.35 because Hindi translations of technical content (iGOT, portal, module names) legitimately contain Latin brand names.

3. **Repetition loop** — if 4 consecutive identical words found: `-0.35`. Catches model hallucination loops.

4. **Untranslated** — if output == source exactly: `-0.40`. Also checks if output is >80% Latin for a non-Latin target: `-0.35`.

5. **Too short** — if source ≥ 5 words but translation < 2 words: `-0.30`.

6. **Transliteration** — if Latin chars > 60% of total alpha for non-Latin target: `-0.35`. KB tender §3.2 explicitly prohibits transliteration.

7. **Missing numbers** — extracts all digit sequences from source, checks they appear in translation. Missing numbers: `-0.20`.

8. **ChrF** — only computed for same-script pairs (e.g. English→English for back-translation). Cross-script pairs get chrf=0.0 since character n-gram overlap is zero by definition.

Final: `score = max(0.0, round(score, 3))`. Below 0.55 → needs_review. Below 0.30 → failed.

---

**Q44. Why is the source language leakage threshold 0.35 and not 0.5?**

Originally it was 0.5. In production, we found that valid Hindi translations of iGOT content were being flagged as "source language leakage" because the content contains many Latin brand names: "iGOT", "Karmayogi", "portal", "module", "CBP", "RTX". A sentence like "iGOT Karmayogi पोर्टल पर लॉगिन करें" has significant Latin content but is a perfectly valid Hindi translation.

Lowering to 0.35 means we only flag when Latin chars dominate by a large margin — which is the actual transliteration case where someone writes "Pradhan Mantri Mudra Yojana" in Latin instead of "प्रधान मंत्री मुद्रा योजना".

---

**Q45. What is back-translation scoring and when is it used?**

Back-translation: translate the output back to the source language, then measure word overlap with the original source.

Example: Source = "Shishu loans cover amounts up to ₹50,000"
→ Tamil translation → back-translate to English → "Shishu loans cover up to ₹50,000"
→ word overlap = 7/9 = 0.78

If back-translation overlap < 0.25: flag `low_back_translation`, subtract 0.15 from score.

It's used in `score_segment_full()` which is called for QA certificate generation (not during the main pipeline — too slow for real-time use). The main pipeline uses `score_segment()` (heuristic only) for speed.

The back-translator reuses the existing `Translator` instance via `set_shared_translator()` — avoids loading a second model into GPU memory.

---

## SECTION 12: FOLLOW-UP DEPTH ANSWERS

---

**Q46. Why 200ms gap threshold for ASR segment repair?**

Natural English sentence pauses are 300–500ms. A 200ms gap means the speaker barely paused — almost certainly a mid-sentence breath, not a sentence boundary. We tested 400ms first but it was merging adjacent complete sentences in English educational content (lecturer pauses between sentences for emphasis). 200ms safely catches only genuine mid-sentence Whisper splits without merging intentional sentence boundaries.

---

**Q47. Why beam size 5 for Devanagari but 3 for other scripts?**

Devanagari languages (Hindi, Marathi, Nepali, Maithili, Sanskrit) are morphologically complex — verbs inflect for gender, number, tense, aspect, and the postposition system creates many valid surface forms for the same meaning. More beams = better coverage of inflected forms = higher quality output. The cost is ~1.5× slower inference per segment, which is acceptable since Devanagari languages are the highest-priority languages for this government project.

Dravidian languages (Tamil, Telugu, Kannada, Malayalam) use beam size 4 — also agglutinative but the MMS-VITS TTS path means translation quality matters slightly less than for Parler-TTS languages.

---

**Q48. Why repetition penalty 1.3 for Devanagari?**

Devanagari MT tends to repeat postpositions (का/के/की — "of/for/belonging to") and conjunctions (और — "and") in a loop. This is a known IndicTrans2 artifact on longer segments. Repetition penalty 1.3 suppresses the probability of generating a token that already appeared recently. 1.1 (used for other scripts) wasn't enough to stop the loops; 1.5 was too aggressive and caused the model to avoid legitimate repeated words.

---

**Q49. Why max_new_tokens=1024 for agglutinative languages but 768 for others?**

Agglutinative languages (Tamil, Telugu, Kannada, Malayalam, Hindi, Marathi, Bengali, Gujarati, Punjabi, Odia, Assamese, Maithili, Nepali, Urdu, Bodo) build complex words by stacking morphemes. A single English word like "democratisation" can become a 15-character Tamil word. The translated output can be significantly longer in character count than the source. 768 tokens would truncate long segments for these languages. 1024 gives enough headroom for the longest government training content segments.

---

**Q50. What happens if all three translation engines fail?**

```python
raise RuntimeError(f"All translation engines failed: {src_name} → {tgt_name}")
```

This propagates up to `_translate_segments_parallel()` which catches it per-segment:
```python
batch_results.append({
    "text": t,  # source text as last resort
    "engine": "failed",
    "score": {"score": 0.0, "flags": ["translation_error"],
              "needs_review": True, "failed": True}
})
```

The source text (English) is used as absolute last resort — better to speak English than silence. The segment is flagged `failed=True` and `needs_review=True` in the metadata JSON. The QA report will show this segment as failed, and the human reviewer can provide a manual translation via the review UI.

---

**Q51. How does the `torch.compile` optimisation work and why is it conditional?**

```python
try:
    model = torch.compile(model, mode="reduce-overhead", fullgraph=False)
except Exception:
    pass
```

`torch.compile` (PyTorch 2.0+) uses TorchDynamo to JIT-compile the model's forward pass into optimised CUDA kernels. `mode="reduce-overhead"` minimises Python overhead on repeated calls — ideal for inference where the same model runs hundreds of times. Gives ~20% speedup on repeated forward passes.

It's wrapped in try/except because: (1) it requires PyTorch ≥ 2.0, (2) on Windows, TorchDynamo has known issues with some model architectures, (3) `fullgraph=False` allows fallback to eager mode for unsupported ops. If compile fails, the model runs in standard eager mode — no crash, just no speedup.

---

**Q52. How does the `no_repeat_ngram_size=0` for agglutinative languages work?**

`no_repeat_ngram_size=N` prevents the model from generating any N-gram that already appeared in the output. For agglutinative languages, this is set to 0 (disabled) because legitimate repetition is common — postpositions, case markers, and verb suffixes repeat naturally in grammatically correct sentences. Setting it to 3 (as for non-agglutinative languages) would prevent the model from generating grammatically required repeated morphemes, producing broken output.

---

## SECTION 13: SCENARIO-BASED QUESTIONS

---

**Q53. A new language needs to be added. What's the process?**

1. Add the language code to `lang_config.py` — flores200 code for IndicTrans2, Seamless code, NLLB code
2. Create `glossary/<lang>.json` with domain terminology
3. Add dataset: `datasets/parallel/<lang>/train.jsonl`, `dev.jsonl`, `test.jsonl`
4. Add ASR dataset index: `datasets/asr/<lang>/`
5. Download MMS-TTS adapter or standalone VITS model for the language
6. Add to `_SCRIPT_RANGES` in `quality.py` and `translator.py` for script-level checks
7. Add to `_LANG_WEIGHTS` in `finetune_indictrans.py` with appropriate resource tier weight
8. Run `scripts/check_gaps.py` to verify coverage
9. Run `scripts/test_pipeline.py` to smoke test end-to-end

---

**Q54. The pipeline crashes mid-job on segment 150 of 200. What happens?**

1. The checkpoint at `checkpoints/jobs/<job_id>.json` has segments 0–149 saved (each marked done after translation)
2. On restart (without `--force`), the pipeline loads the checkpoint
3. ASR is skipped — segments loaded from `meta.segments` in checkpoint
4. Segments 0–149 are loaded from `completed` dict — no re-translation
5. Only segments 150–199 go to the translation engine
6. TTS always re-runs (no TTS checkpoint) — but TTS is fast (~2s/segment)
7. Assembly and output generation run normally
8. On success, checkpoint is deleted

The user sees no difference in output — the resume is transparent.

---

**Q55. A government reviewer says the Hindi translation of "Competency Framework" is wrong. How do you fix it permanently?**

```bash
python scripts/translation_memory.py add \
    --src "Competency Framework" \
    --tgt "दक्षता ढांचा" \
    --tgt-lang hin
```

This adds the entry to `translation_memory/govt_tm.jsonl`. From that point, every future translation of "Competency Framework" to Hindi will use "दक्षता ढांचा" — the TM lookup happens before any model inference in `_translate_text()`. The exact match bypasses IndicTrans2 entirely.

For fuzzy matches (85% threshold), similar phrases like "Competency Frameworks" or "the Competency Framework" will also get the TM translation injected.

---

## SECTION 14: THINGS THAT COULD STILL TRIP YOU UP — WITH ANSWERS

---

**Q56. Show me the actual output metadata JSON structure.**

From `output/tam/KB_COURSE_001_tam_metadata.json` (real production file):
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

---

**Q57. What does the retry decorator do exactly?**

```python
@retry(max_attempts=2, delay=1.0)
def _translate_indic_trans2(self, text, src_lang, tgt_lang):
    ...
```

Exponential backoff: attempt 1 fails → wait 1s → attempt 2 fails → wait 2s → raise the last exception. The `delay * (2 ** (attempt - 1))` formula gives: 1s, 2s, 4s for max_attempts=3. For translation engines we use max_attempts=2 (one retry) — translation failures are usually transient CUDA errors that resolve on retry, not permanent failures.

---

**Q58. What is the job_id and how is it generated?**

```python
key = f"{Path(video_path).name}_{tgt_lang}"
return hashlib.md5(key.encode()).hexdigest()[:12]
```

MD5 of `filename_targetlang`, first 12 hex chars. Example: `course.mp4_tam` → `bf2aa395e29c`. This is deterministic — the same video+language always gets the same job_id, so the checkpoint is always found on resume. It's based on filename only (not full path) so moving the file doesn't break resume.

---

**Q59. What is the `_sanitize_id` function and why is it needed?**

```python
return re.sub(r"[^\w\-]", "_", value)[:64]
```

Strips path separators (`/`, `\`) and shell-special characters from user-supplied course IDs. Without this, a malicious or accidental course_id like `../../etc/passwd` could write output files outside the intended output directory (path traversal). The 64-char limit prevents Windows path length issues.

---

**Q60. What is TF32 and why did you enable it?**

```python
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
```

TF32 (TensorFloat-32) is a numeric format on Ampere GPUs (RTX A6000 = Ampere). It uses 10-bit mantissa (vs 23-bit for fp32) but the same 8-bit exponent. For matrix multiplications, TF32 gives ~2× throughput vs fp32 with negligible accuracy loss for inference. It's disabled by default in PyTorch for reproducibility. We enable it because we're doing inference, not training where exact reproducibility matters.

---

## FINAL CHECKLIST — READ THESE FILES ONCE BEFORE INTERVIEW

| File | What to know |
|------|-------------|
| `pipeline/retry.py` | Atomic write pattern, exponential backoff formula |
| `pipeline/quality.py` | All 8 heuristic rules, exact penalty values, ChrF formula |
| `pipeline/dubbing_pipeline.py` | 6-step pipeline, completeness guard, multi-GPU distribution |
| `pipeline/translator.py` | Routing decision tree, drift guards, token protection |
| `finetune/finetune_indictrans.py` | Hyperparams, curriculum, sampling weights, early stopping |
| `output/tam/KB_COURSE_001_tam_metadata.json` | Real production output — know every field |
| `checkpoints/jobs/bf2aa395e29c.json` | Real checkpoint — know the structure |

---

*Updated with fine-tuning deep-dive, quality scoring internals, follow-up depth answers, and scenario-based questions*
*Total: 60 questions across 14 sections*
