# Infrastructure Calculation — MigotoAI Translation Engine
### Pilot Device: 4× NVIDIA A6000 (48GB VRAM each) · 128GB RAM
### RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi

---

## 1. GPU Memory Budget — Per Model

### Model sizes (disk → VRAM when loaded in float16)

| Model | Disk | VRAM (fp16) | Notes |
|---|---|---|---|
| faster-whisper large-v3 | ~3.0 GB | ~3.0 GB | CT2 format, INT8 compute on GPU |
| IndicTrans2 en_indic | ~1.2 GB | ~2.4 GB | 1B params × 2 bytes fp16 |
| IndicTrans2 indic_en | ~1.2 GB | ~2.4 GB | |
| IndicTrans2 indic_indic | ~1.2 GB | ~2.4 GB | |
| SeamlessM4Tv2 | ~10.0 GB | ~10.0 GB | Already fp16 on HF |
| NLLB-200 | ~2.4 GB | ~2.4 GB | |
| Parler-TTS Indic Large | ~3.6 GB | ~3.6 GB | |
| MMS-TTS shared base | ~1.5 GB | ~1.5 GB | Adapter swaps are ~50MB each |
| Coqui XTTS-v2 | ~1.9 GB | ~1.9 GB | Last-resort / voice clone only |
| **Total all models** | **~26.0 GB** | **~29.6 GB** | |

---

## 2. How Models Are Distributed Across 4× A6000 (48GB each = 192GB total VRAM)

The pipeline runs in **multi-GPU parallel mode**: ASR runs once on GPU 0, then each GPU worker handles translate + TTS + assemble for its assigned language group.

### GPU 0 — Main process + shared models
| Component | VRAM |
|---|---|
| faster-whisper large-v3 (ASR — shared, runs once) | 3.0 GB |
| IndicTrans2 en_indic (translation primary) | 2.4 GB |
| Parler-TTS Indic Large (TTS primary) | 3.6 GB |
| MMS-TTS shared base (TTS fallback) | 1.5 GB |
| OS + CUDA context + PyTorch overhead | ~4.0 GB |
| **GPU 0 total** | **~14.5 GB / 48GB** |
| **Headroom** | **33.5 GB free** |

### GPU 1, 2, 3 — Language workers (each identical)
| Component | VRAM |
|---|---|
| IndicTrans2 en_indic (translation) | 2.4 GB |
| Parler-TTS Indic Large (TTS) | 3.6 GB |
| MMS-TTS shared base (TTS fallback) | 1.5 GB |
| CUDA context + PyTorch overhead | ~3.0 GB |
| **Per worker GPU total** | **~10.5 GB / 48GB** |
| **Headroom per worker** | **37.5 GB free** |

### Where does SeamlessM4T (10GB) go?
SeamlessM4T is loaded **on-demand** only when:
- IndicTrans2 fails quality gate (fallback translation)
- S2ST fast-path is attempted (Indic→Indic pairs only)

It loads on GPU 0 when needed, fits easily within the 33.5GB headroom. Not loaded by default — saves 10GB VRAM in typical English→Indic runs.

### Where does NLLB-200 (2.4GB) go?
Loaded on GPU 0 on-demand when SeamlessM4T also fails, or as primary for kas/snd/kok. Negligible VRAM cost.

### Summary: 4× A6000 is massively over-specced for the model load
**Total VRAM used at peak: ~46GB out of 192GB (24%)**
The 4× A6000 has ~146GB VRAM headroom. This means you could load all models on all 4 GPUs simultaneously with room to spare, which would eliminate any model load/unload latency entirely.

---

## 3. RAM Budget — 128GB System RAM

| Component | RAM Usage |
|---|---|
| OS + system services | ~8 GB |
| Python main process + pipeline objects | ~4 GB |
| ASR cache (segments JSON for 22 langs) | ~0.1 GB |
| Translation Memory in-memory (all 22 langs) | ~0.5 GB |
| Glossary data (22 × JSON) | ~0.05 GB |
| 4× worker processes (each ~2GB base) | ~8 GB |
| Audio buffers (WAV chunks, TTS output) | ~2 GB |
| Dataset access during fine-tuning (if concurrent) | ~20 GB |
| **Operating total (inference only)** | **~23 GB / 128GB** |
| **Headroom** | **~105 GB free** |

**Verdict:** 128GB RAM is more than sufficient. Inference uses ~23GB. Even with fine-tuning running concurrently on the same machine, you stay well under 128GB.

---

## 4. Throughput Calculation — What Can This Machine Actually Do?

### Per-language timing estimates (1 hour source video)

| Stage | Time estimate | Notes |
|---|---|---|
| Audio extraction | ~2 min | ffmpeg, CPU-bound |
| ASR (faster-whisper large-v3) | ~8–12 min | ~6–8× real-time on A6000 INT8 |
| Translation (IndicTrans2 batch) | ~3–5 min | GPU batch, 1B model on A6000 |
| TTS (Parler-TTS Large, ~600 segments) | ~15–25 min | Most time-intensive step |
| Audio assembly + ffmpeg mux | ~3 min | CPU-bound |
| **Total per language (1hr source)** | **~31–47 min** | |

### Multi-GPU parallel: 22 languages from 1 hour source video

- ASR runs **once** on GPU 0: ~10 min
- 22 languages distributed across 4 GPUs: ~5–6 langs per GPU
- Each GPU processes its ~6 languages **sequentially** (not simultaneously — one model set per GPU)
- Time per GPU for 6 languages: ~6 × 40 min avg = **~4 hours**
- **Total wall-clock for 22 languages from 1hr video: ~4–5 hours**

### Monthly throughput capacity

The KB tender peak month requires **125 output-hours** across 22 languages.

| Parameter | Value |
|---|---|
| Output hours required (peak month) | 125 hrs |
| Source hours (assuming ~1:1 ratio) | ~125 hrs source |
| Time to dub 1hr source × 22 languages | ~4–5 hrs wall-clock |
| Working hours per day (machine running) | 20 hrs (leaving 4hr for maintenance) |
| **Source hours processable per day** | **~4–5 hrs source × all 22 langs** |
| **Source hours processable per month (30 days)** | **~120–150 hrs source** |
| **Output hours per month (22 langs × 125hr src)** | Depends on how many langs per course |

### Realistic monthly delivery on this machine

The tender requires 125 **output hours** (dubbed audio delivered). If a typical course is 1 hour and needs 11 mandatory languages:

| Scenario | Calc | Result |
|---|---|---|
| 11 languages per course, 1hr course | 4 GPUs, ~2–3hr wall-clock | ~7–10 courses/day |
| 22 languages per course, 1hr course | 4 GPUs, ~4–5hr wall-clock | ~4–5 courses/day |
| Monthly capacity (22 langs, 20 working days) | 4–5 courses/day × 20 days | **80–100 courses × 22 langs** |
| Monthly output hours (100 courses × 1hr × 22 langs) | 100 × 22 = 2,200 lang-hours | **~2,200 dubbed hours/month** |

**The tender requires 125 output-hours/month. This machine can deliver ~2,200 dubbed-hours/month — 17× the peak requirement.** The pilot machine is over-provisioned for the contract volume by a large margin.

---

## 5. Storage Requirements

| Data | Size | Notes |
|---|---|---|
| All model weights | ~26 GB | One-time download |
| Fine-tuned checkpoints (3 directions) | ~4 GB | en_indic + indic_en + indic_indic |
| Training datasets (22 langs × train/dev/test) | ~1.2 TB | Already present in `datasets/parallel/` |
| ASR datasets (22 langs) | ~50 GB | `datasets/asr/` |
| Input courses (per batch) | ~50 GB | 50 × 1GB videos typical |
| Output per course (22 langs) | ~5–10 GB | MP4 + SRT + VTT + DOCX × 22 |
| Output per month (100 courses) | ~500 GB–1 TB | |
| Translation memory (JSONL) | < 1 GB | Grows over contract period |
| Logs + checkpoints | ~10 GB | Auto-cleared on success |
| **Total storage needed** | **~2–3 TB** | SSD recommended for model weights |

**Recommendation:** 4TB NVMe SSD for models + active jobs. Separate 8TB HDD for output archive and datasets.

---

## 6. Cloud Scale — When to Move Beyond the Pilot

The pilot machine handles the contract comfortably. Cloud becomes relevant in three scenarios:

### Scenario A — Scale to multiple concurrent clients / contracts

| Config | GPUs | VRAM | Monthly dubbed-hr capacity | Use case |
|---|---|---|---|---|
| Pilot (current) | 4× A6000 | 192 GB | ~2,200 hrs | 1 contract, all 22 langs |
| Medium scale | 8× A6000 or 4× H100 80GB | 320–320 GB | ~4,500 hrs | 2–3 contracts simultaneously |
| Large scale | 16× A100 80GB (2 nodes) | 1,280 GB | ~9,000 hrs | 5–8 contracts, 22 langs each |

### Scenario B — Cloud equivalent of the pilot machine

| Cloud Provider | Instance | GPUs | VRAM | Approx cost |
|---|---|---|---|---|
| AWS | `p3.8xlarge` | 4× V100 16GB | 64GB | ~$12/hr |
| AWS | `p4d.24xlarge` | 8× A100 40GB | 320GB | ~$32/hr |
| GCP | `a2-highgpu-4g` | 4× A100 40GB | 160GB | ~$16/hr |
| Azure | `NC96ads_A100_v4` | 4× A100 80GB | 320GB | ~$18/hr |
| **On-prem pilot** | **4× A6000** | **192GB** | **One-time ~₹25–30L** | **~₹0/hr after purchase** |

**For this contract:** On-prem is the right call. The machine cost amortises within 1–2 months of contract value, and data sovereignty requirements make on-prem the default choice anyway.

**For cloud (if needed):** Use spot/preemptible instances for batch processing (60–80% cheaper). The pipeline's checkpoint/resume system (`retry.py`) means a spot interruption never loses work — it resumes from the last completed segment.

### Scenario C — Fine-tuning at scale (separate from inference)

Fine-tuning IndicTrans2 1B with DeepSpeed ZeRO-3 on the 4× A6000:

| Parameter | Value |
|---|---|
| Model params | 1B |
| ZeRO-3 shards params across | 4 GPUs |
| Per-GPU param shard | ~250M params |
| Per-GPU VRAM for ZeRO-3 training | ~20–25 GB (params + grads + optimizer states / 4) |
| Available on A6000 | 48GB |
| **Verdict** | ✅ Fits comfortably — full fine-tune on pilot machine |
| Estimated fine-tune time (1 epoch, 22 langs) | ~8–12 hours |

---

## 7. Summary — Pilot Machine Assessment

| Dimension | Requirement | Pilot Machine | Verdict |
|---|---|---|---|
| VRAM (inference) | ~30–35 GB peak | 192 GB (4× 48GB) | ✅ 5× headroom |
| VRAM (fine-tuning ZeRO-3) | ~80–100 GB total | 192 GB | ✅ Fits |
| System RAM | ~25 GB | 128 GB | ✅ 5× headroom |
| Storage (models + data) | ~2–3 TB | Needs 4TB NVMe | ⚠️ Check disk |
| Monthly output capacity | 125 hrs (peak) | ~2,200 hrs/month | ✅ 17× over-provisioned |
| Data sovereignty | All on-prem | ✅ On-prem | ✅ Compliant |
| Fine-tuning capability | Full 1B model | ✅ ZeRO-3 fits | ✅ |

**The 4× A6000 + 128GB RAM pilot machine is more than sufficient for the entire contract volume. The only thing to verify is storage — you need at least 4TB NVMe SSD total (2TB for models+datasets, 2TB for active output).**

---

*Prepared for: Novac Technology Solutions Pvt. Ltd. — Immerz Division*
*Reference: RFB IN-KBL-543730-NC-RFB*
