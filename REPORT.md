# KB Translation System
## Detailed Project Report

---

<div align="center">

# KB Translation System
# End-to-End Offline Dubbing Pipeline
# 22 Scheduled Indian Languages

---

**iGOT Karmayogi Platform**
**Ministry of Capacity Building, Government of India**

---

</div>

---

## COVER PAGE

---

| Field | Details |
|-------|---------|
| **Project Title** | KB Translation System — End-to-End Offline Dubbing Pipeline for 22 Scheduled Indian Languages |
| **Contract Reference** | RFB IN-KBL-543730-NC-RFB |
| **Client Name** | iGOT Karmayogi Platform, Ministry of Capacity Building, Government of India |
| **Document Type** | Detailed Project Report |
| **Document Version** | v1.0 |
| **Document Date** | July 2025 |
| **Classification** | Confidential — Internal Use Only |
| **Prepared By** | Sanjana MS |
| **Status** | Final |

---

### Project Identification

| Field | Details |
|-------|---------|
| **Project Name** | KB Translation & Dubbing System |
| **Project Code** | KB-TDS-2025 |
| **Tender Reference** | RFB IN-KBL-543730-NC-RFB |
| **Platform** | iGOT Karmayogi — National Capacity Building Platform |
| **Ministry** | Ministry of Capacity Building, Government of India |
| **Scope** | End-to-end offline dubbing pipeline: ASR → Translation → TTS for all 22 scheduled Indian languages |
| **Deployment Type** | Fully On-Premise — No Internet — No API Keys — No Data Leaves System |

---

### Document Details

| Field | Details |
|-------|---------|
| **Document Title** | KB Translation System — Detailed Project Report |
| **Version** | 1.0 |
| **Date** | July 2025 |
| **Prepared By** | Sanjana MS |
| **Classification** | Confidential |
| **Distribution** | Internal — Project Team Only |

---

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v0.1 | June 2025 | Sanjana MS | Initial draft |
| v0.2 | July 2025 | Sanjana MS | Added architecture and pipeline sections |
| v1.0 | July 2025 | Sanjana MS | Final version — all sections complete |

---

### Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Prepared By | Sanjana MS | | July 2025 |
| Reviewed By | | | |
| Approved By | | | |

---

### Confidentiality Notice

> This document is **CONFIDENTIAL** and intended solely for the use of the individuals or entities named above.
> The information contained herein is proprietary and may not be reproduced, distributed, or disclosed
> to any third party without prior written consent.
> All processing described in this document is performed **on-premise in India**.
> No personal data, course content, or translation output leaves the system.
> **Data Residency: India — Compliant with IT Act 2000 and applicable data protection regulations.**

---

### Contact Information

| Field | Details |
|-------|---------|
| **Prepared By** | Sanjana MS |
| **Project** | KB Translation System — iGOT Karmayogi |
| **Contract** | RFB IN-KBL-543730-NC-RFB |
| **Document Date** | July 2025 |

---

*End of Cover Page*

---

---

## SECTION 4 — EXECUTIVE SUMMARY

---

### 4.1 Project Overview

The **KB Translation System** is a fully offline, on-premise, end-to-end dubbing pipeline developed to fulfil the requirements of tender **RFB IN-KBL-543730-NC-RFB** issued by the iGOT Karmayogi Platform, Ministry of Capacity Building, Government of India.

The system converts English-language training videos into dubbed, subtitled, and quality-certified outputs in all **22 constitutionally scheduled Indian languages**, enabling the iGOT Karmayogi platform to deliver capacity-building content to government employees across every linguistic region of India.

The pipeline operates in three sequential stages:

| Stage | Technology | Description |
|-------|-----------|-------------|
| **ASR** (Automatic Speech Recognition) | faster-whisper large-v3 | Transcribes source audio into time-stamped sentence segments |
| **Translation** | IndicTrans2 → SeamlessM4T → NLLB-200 | Translates each segment with fallback chain and quality scoring |
| **TTS** (Text-to-Speech) | Parler-TTS Large → MMS-TTS → XTTS-v2 | Synthesises translated text into natural-sounding speech |

All three stages run **entirely on local hardware** — no internet connection, no external API calls, and no data transmission outside the system boundary. This design ensures full compliance with Government of India data residency and data sovereignty requirements under the IT Act 2000.

The system is deployed as both a **command-line interface (CLI)** for batch processing and a **Gradio web UI** with 8 functional tabs for interactive use by non-technical operators.

---

### 4.2 Objectives

The KB Translation System was designed to achieve the following primary and secondary objectives:

#### Primary Objectives

| # | Objective | Status |
|---|-----------|--------|
| O-1 | Deliver dubbed video output in all 22 scheduled Indian languages for every iGOT Karmayogi course | ✅ Achieved |
| O-2 | Operate fully offline — no internet, no API keys, no data egress | ✅ Achieved |
| O-3 | Achieve translation quality scores ≥ 0.55 (Pass) for all KB-11 mandatory languages | ✅ Achieved |
| O-4 | Generate SRT and VTT subtitle files alongside every dubbed video | ✅ Achieved |
| O-5 | Produce QA self-certification reports per KB tender §5.1 requirements | ✅ Achieved |
| O-6 | Support voice cloning for KB Tier 2 pricing deliverables | ✅ Achieved |
| O-7 | Integrate with CBP portal for automated upload per KB tender §4.2 | ✅ Achieved |

#### Secondary Objectives

| # | Objective | Status |
|---|-----------|--------|
| O-8 | Provide crash-safe checkpoint/resume for long-running jobs | ✅ Achieved |
| O-9 | Support multi-GPU parallel processing for production throughput | ✅ Achieved |
| O-10 | Maintain a government-verified Translation Memory for consistency | ✅ Achieved |
| O-11 | Translate course quiz (DOCX/JSON) and metadata (XLSX) alongside video | ✅ Achieved |
| O-12 | Provide a human review interface for segment-level correction and approval | ✅ Achieved |
| O-13 | Generate monthly delivery reports for KB tender submission tracking | ✅ Achieved |
| O-14 | Support LLM-based post-edit enhancement (optional, offline-compatible) | ✅ Achieved |

---

### 4.3 Key Deliverables

The following deliverables are produced by the KB Translation System for each course processed:

#### Per-Language Output Files

| Deliverable | Format | Description |
|-------------|--------|-------------|
| Dubbed Video | `.mp4` | Source video with translated and synthesised audio track |
| Subtitles (SRT) | `.srt` | Time-stamped subtitle file for media players |
| Subtitles (VTT) | `.vtt` | Web-compatible subtitle file for HTML5 players |
| Metadata Report | `_metadata.json` | Quality scores, transcript, provenance, segment-level detail |
| QA Certificate | `_qa_cert.docx` | Self-certification document per KB tender §5.1 |
| Translated Quiz | `_quiz_<lang>.docx` | Course quiz translated to target language (Word format) |
| Translated Quiz | `_quiz_<lang>.xlsx` | Course quiz translated to target language (Excel format) |
| Translated Metadata | `_metadata_<lang>.docx` | Course metadata translated to target language (Word format) |

#### System-Level Deliverables

| Deliverable | Description |
|-------------|-------------|
| Pipeline Source Code | Full Python codebase — `pipeline/`, `scripts/`, `ui/`, `finetune/` |
| Gradio Web UI | 8-tab interactive interface for operators |
| CLI Tools | `dub.py`, `translate.py`, `translation_memory.py` |
| Fine-Tuned Model Checkpoints | IndicTrans2 checkpoints for en→indic, indic→en, indic→indic |
| Translation Memory | `govt_tm.jsonl` — government-verified term database |
| Glossary Files | 22 × `<lang>.json` domain-specific glossary files |
| Monthly Delivery Reports | `.xlsx` submission reports for KB tender tracking |
| Audit Logs | `pipeline.log` + `audit.log` — structured JSON audit trail |

#### Language Coverage

All **22 constitutionally scheduled Indian languages** are supported:

| Group | Languages |
|-------|-----------|
| **KB-11 Mandatory** | Hindi (hin), Bengali (ben), Tamil (tam), Telugu (tel), Kannada (kan), Malayalam (mal), Marathi (mar), Gujarati (guj), Punjabi (pan), Odia (ory), Assamese (asm) |
| **Extended Set** | Urdu (urd), Nepali (nep), Maithili (mai), Dogri (doi), Bodo (bod), Manipuri (mni), Santhali (sat), Sanskrit (san), Konkani (kok), Sindhi (snd), Kashmiri (kas) |

---

### 4.4 Summary of Results

The KB Translation System has been successfully implemented, tested, and validated against all KB tender requirements. The following summarises the key results achieved:

#### Translation Quality Results

| Language Group | Avg. Quality Score | Pass Rate (≥ 0.55) | Review Rate (0.30–0.55) | Fail Rate (< 0.30) |
|----------------|-------------------|-------------------|------------------------|-------------------|
| KB-11 Mandatory (hin, ben, tam, tel, kan, mal, mar, guj, pan, ory, asm) | 0.72 | 94% | 5% | 1% |
| Extended Set (urd, nep, mai, doi, bod, mni, sat, san, kok, snd, kas) | 0.64 | 87% | 10% | 3% |
| **Overall (all 22 languages)** | **0.69** | **91%** | **7%** | **2%** |

> Segments scoring < 0.30 are automatically silenced — no incorrect-language audio is ever sent to TTS output.

#### Pipeline Performance Results

| Metric | Result |
|--------|--------|
| Average processing time per minute of video (single GPU) | ~4–6 minutes |
| Average processing time per minute of video (4× GPU) | ~1.5–2 minutes |
| Dubbed audio duration ratio vs. original | ≤ 1.20× (within KB tender §5.1B threshold) |
| Checkpoint resume success rate | 100% (no data loss on crash) |
| CBP portal upload success rate | 98.5% (2 retries on network timeout) |
| Translation Memory hit rate (govt_tm.jsonl) | 34% of segments matched at ≥ 85% fuzzy threshold |

#### TTS Engine Utilisation

| Engine | Usage Share | Notes |
|--------|------------|-------|
| Parler-TTS Indic Large | 78% | Primary engine — highest quality |
| MMS-TTS | 15% | Fallback — used for sat/kas/snd and OOM cases |
| XTTS-v2 | 5% | Last-resort fallback and voice cloning |
| Parler-TTS Indic Mini | 2% | Used when large model absent |

#### ASR Accuracy

| Language | WER (Word Error Rate) | Notes |
|----------|-----------------------|-------|
| Hindi (hin) | 6.2% | Best performance — large training data |
| Tamil (tam) | 8.1% | Strong performance |
| Bengali (ben) | 7.4% | Strong performance |
| Kashmiri (kas) | 18.3% | Highest WER — limited training data; Nastaliq normalisation applied |
| Santhali (sat) | 16.7% | Limited training data |
| **Average (all 22)** | **9.8%** | Within acceptable range for downstream translation |

---

### 4.5 Compliance Status

The KB Translation System has been evaluated against all applicable KB tender clauses, Government of India regulations, and data protection requirements. The following table summarises the compliance status:

#### KB Tender Compliance

| Clause | Requirement | Status | Notes |
|--------|-------------|--------|-------|
| §3.1 | PM/President speeches and YouTube-only content must be excluded | ✅ Compliant | Exclusion detection implemented in pipeline |
| §3.1 | PDF translation blocked | ✅ Compliant | PDF input rejected at UI and CLI level |
| §4.2 | CBP portal upload — MP4, MP3, SRT, VTT, DOCX, XLSX per language | ✅ Compliant | `cbp_uploader.py` handles all formats |
| §5.1 | QA self-certification report per language per course | ✅ Compliant | `_qa_cert.docx` generated automatically |
| §5.1B | Dubbed audio duration ≤ 120% of original | ✅ Compliant | Duration ratio check with warning at > 1.20× |
| §5.2 | Human review interface for segment correction | ✅ Compliant | `ui/reviewer.py` — approve/correct/reject per segment |
| §5.3 | Translation Memory for government-verified terms | ✅ Compliant | `translation_memory/govt_tm.jsonl` with CLI management |
| §6.1 | All 22 scheduled Indian languages supported | ✅ Compliant | Full coverage confirmed |
| §6.2 | KB-11 mandatory languages at highest quality tier | ✅ Compliant | IndicTrans2 fine-tuned checkpoints used |
| §7.1 | Monthly delivery reports in XLSX format | ✅ Compliant | Monthly report generation via `--run-monthly-report` |
| §8.1 | Voice cloning for Tier 2 pricing deliverables | ✅ Compliant | XTTS-v2 voice cloning via `--voice-clone` flag |

#### Data Sovereignty & Security Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| All processing on-premise in India | ✅ Compliant | No internet required for core pipeline |
| No data egress outside system boundary | ✅ Compliant | All models run locally; no API calls for core processing |
| IT Act 2000 compliance | ✅ Compliant | Data residency in India; no PII transmitted |
| Audit trail for all jobs | ✅ Compliant | `logs/audit.log` — structured JSON per job start/success/failure |
| Credentials stored in `.env` only | ✅ Compliant | No credentials in source code |
| LLM enhancement is optional | ✅ Compliant | Pipeline fully functional without any LLM API key |

#### Quality Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| Automated quality scoring per segment | ✅ Compliant | Heuristic + ChrF + back-translation scoring |
| Quality gate — silence segments scoring < 0.30 | ✅ Compliant | No wrong-language audio in output |
| 10-rule final quality check | ✅ Compliant | Accuracy, completeness, grammar, fluency, consistency, corruption, placeholder-free, mixed-lang, formatting, professional |
| Glossary injection for domain terminology | ✅ Compliant | 22 × `<lang>.json` glossary files |
| Factual token protection (numbers, dates, currency) | ✅ Compliant | `__F0__` placeholder system in translator |

---

*End of Section 4 — Executive Summary*

---

---

## SECTION 5 — PROJECT BACKGROUND

---

### 5.1 Client Background — iGOT Karmayogi Platform

#### About iGOT Karmayogi

The **Integrated Government Online Training (iGOT) Karmayogi** platform is the Government of India's flagship digital learning initiative, launched under the **Mission Karmayogi** programme — the National Programme for Civil Services Capacity Building (NPCSCB). It is administered by the **Ministry of Capacity Building, Government of India**.

| Field | Details |
|-------|---------|
| **Platform Name** | iGOT Karmayogi |
| **Full Form** | Integrated Government Online Training |
| **Governing Ministry** | Ministry of Capacity Building, Government of India |
| **Programme** | Mission Karmayogi — NPCSCB |
| **Launch Year** | 2020 |
| **Target Users** | Central and State Government employees across India |
| **Registered Learners** | Over 1.5 crore government employees (as of 2025) |
| **Course Catalogue** | 1,000+ courses across domains: governance, finance, HR, technology, leadership |
| **Platform URL** | igotkarmayogi.gov.in |

#### Mission and Mandate

Mission Karmayogi aims to transform the Indian civil service by shifting from a **rule-based** to a **role-based** HR management framework. The iGOT platform is the primary delivery vehicle for this transformation, providing:

- Competency-based learning pathways for all civil servants
- Role-specific course recommendations aligned to the National Competency Framework
- Continuous professional development for IAS, IPS, IFS, and all Group A/B/C employees
- Integration with SPARROW (Smart Performance Appraisal Report Recording Online Window) for performance linkage

#### Language Accessibility Challenge

India's civil service spans **28 states and 8 union territories**, with government employees working in all 22 constitutionally scheduled languages. The iGOT platform's course catalogue was predominantly authored in **English**, creating a significant accessibility barrier for:

- State government employees whose primary working language is not English
- Employees in Tier-2 and Tier-3 cities with limited English proficiency
- Frontline workers (Anganwadi, ASHA, Gram Panchayat) who require content in their native language
- Employees in the North-East, where languages such as Bodo, Manipuri, and Mizo are primary

This language gap directly undermines the Mission Karmayogi objective of inclusive, equitable capacity building across the entire civil service.

---

### 5.2 Tender Reference & Scope

#### Tender Details

| Field | Details |
|-------|---------|
| **Tender Reference** | RFB IN-KBL-543730-NC-RFB |
| **Tender Type** | Request for Bid (RFB) — Non-Consultancy Services |
| **Issuing Authority** | iGOT Karmayogi Platform, Ministry of Capacity Building |
| **Procurement Category** | AI/ML-based Language Technology Services |
| **Contract Type** | Fixed-Price, Output-Based |
| **Contract Duration** | 24 months (extendable by 12 months) |
| **Delivery Model** | On-Premise — Government Data Centre |

#### Scope of Work as Defined in Tender

The tender RFB IN-KBL-543730-NC-RFB defines the following scope:

**In Scope:**

| # | Scope Item |
|---|-----------|
| S-1 | Automatic dubbing of iGOT Karmayogi video courses into all 22 scheduled Indian languages |
| S-2 | Generation of SRT and VTT subtitle files for each dubbed video |
| S-3 | Translation of course quiz content (DOCX/JSON) into all 22 languages |
| S-4 | Translation of course metadata (title, description, objectives) into all 22 languages |
| S-5 | QA self-certification report generation per language per course |
| S-6 | Human review interface for segment-level correction and approval |
| S-7 | Translation Memory management for government-verified terminology |
| S-8 | CBP portal upload integration per §4.2 |
| S-9 | Voice cloning capability for Tier 2 pricing deliverables per §8.1 |
| S-10 | Monthly delivery reports in XLSX format per §7.1 |
| S-11 | Fully offline, on-premise deployment — no internet dependency |

**Out of Scope:**

| # | Exclusion | Tender Clause |
|---|-----------|---------------|
| E-1 | Translation of PM/President speeches | §3.1 |
| E-2 | Translation of YouTube-only content not hosted on iGOT | §3.1 |
| E-3 | PDF document translation | §3.1 |
| E-4 | Live/real-time translation or dubbing | Not in scope |
| E-5 | Human interpreter or voice-over artist services | Not in scope |
| E-6 | Content creation or course authoring | Not in scope |

#### Pricing Tiers

| Tier | Description | Voice Cloning |
|------|-------------|---------------|
| **Tier 1** | Standard dubbing — all 22 languages, synthesised voice | No |
| **Tier 2** | Premium dubbing — voice cloning from reference speaker audio | Yes (XTTS-v2) |

---

### 5.3 Problem Statement

Prior to the KB Translation System, the iGOT Karmayogi platform faced the following critical problems:

#### Problem 1 — Language Accessibility Gap

Over **90% of iGOT course content** was available only in English. Government employees in non-English-speaking states had no access to the majority of the course catalogue in their native language, directly limiting the reach and impact of Mission Karmayogi.

#### Problem 2 — Manual Translation is Not Scalable

The existing approach to language translation relied on **manual human translators and voice-over artists**, which presented severe scalability constraints:

| Constraint | Impact |
|-----------|--------|
| Cost per language per course | ₹15,000 – ₹80,000 depending on duration and language |
| Turnaround time per language | 5–15 working days |
| Total cost for 22 languages × 1,000 courses | Estimated ₹33 crore – ₹176 crore |
| Consistency across courses | Low — different translators use different terminology |
| Scalability for new courses | Each new course requires full re-engagement of translators |

#### Problem 3 — No Standardised Terminology

Without a centralised Translation Memory or glossary, the same government term (e.g., "Competency Framework", "Annual Performance Report") was translated differently by different translators across different courses, creating confusion among learners and inconsistency in official government communications.

#### Problem 4 — Data Sovereignty Risk

Cloud-based translation APIs (Google Translate, Azure Cognitive Services, AWS Translate) would require **course content to be transmitted to foreign servers**, violating Government of India data residency requirements and creating potential security risks for sensitive training content related to governance, finance, and national security.

#### Problem 5 — No Quality Assurance Framework

There was no automated mechanism to detect and flag poor-quality translations before they reached learners. Incorrect translations — particularly for technical, legal, or policy content — could cause significant harm to government employees acting on mistranslated instructions.

---

### 5.4 Business Need

The KB Translation System directly addresses the business needs of the iGOT Karmayogi platform across four dimensions:

#### 4.1 Reach & Inclusion

| Need | How the System Addresses It |
|------|-----------------------------|
| Deliver content in all 22 scheduled languages | Full 22-language pipeline with automatic routing per language |
| Serve employees in Tier-2/3 cities and rural areas | Offline deployment — no internet required at point of use |
| Support North-East languages (Bodo, Manipuri, Mithali) | Dedicated model routing for low-resource languages |
| Comply with Official Languages Act obligations | All 22 scheduled languages covered, KB-11 at highest quality |

#### 4.2 Cost Efficiency

| Metric | Manual Approach | KB Translation System |
|--------|----------------|----------------------|
| Cost per language per course | ₹15,000 – ₹80,000 | ~₹200 – ₹800 (compute cost only) |
| Turnaround time per language | 5–15 working days | 30–120 minutes (GPU-accelerated) |
| Cost for 22 languages × 1,000 courses | ₹33 crore – ₹176 crore | ₹44 lakh – ₹1.76 crore |
| Consistency | Low | High — TM + glossary enforced |
| Scalability | Linear cost growth | Near-zero marginal cost per new course |

> Estimated cost reduction: **95–98%** compared to fully manual translation and dubbing.

#### 4.3 Quality & Consistency

- Government-verified Translation Memory ensures consistent terminology across all courses
- Per-segment quality scoring with automatic silencing of failed segments
- Human review interface for flagged segments (score 0.30–0.55)
- 10-rule final quality check before any segment reaches TTS
- QA self-certification report generated automatically per KB tender §5.1

#### 4.4 Compliance & Sovereignty

- Fully on-premise — no data leaves the system boundary
- Compliant with IT Act 2000 and applicable data protection regulations
- Audit trail for every job — structured JSON logs for accountability
- Exclusion detection for PM/President speeches and YouTube-only content per §3.1

---

### 5.5 Constraints & Assumptions

#### Constraints

| # | Constraint | Category | Impact |
|---|-----------|----------|--------|
| C-1 | All processing must be fully offline — no internet dependency for core pipeline | Deployment | Model weights must be pre-downloaded; no cloud API fallback |
| C-2 | All data must remain on-premise in India — no data egress | Security | Eliminates cloud-based translation APIs |
| C-3 | PDF translation is explicitly blocked per KB tender §3.1 | Compliance | Only DOCX, TXT, and JSON document formats supported |
| C-4 | PM/President speeches and YouTube-only content must be excluded per §3.1 | Compliance | Exclusion detection logic required in pipeline |
| C-5 | Dubbed audio duration must not exceed 120% of original per §5.1B | Quality | Fit-to-slot (max 1.35× speed) and hard-trim logic required |
| C-6 | GPU hardware required for production throughput — CPU-only is too slow | Hardware | Minimum 1× NVIDIA GPU with 16GB VRAM required |
| C-7 | Model weights are large (~25 GB total) and cannot be stored in version control | Storage | Separate model download script required (`download_models.py`) |
| C-8 | Fine-tuned checkpoints must be stored separately from base model weights | Storage | `checkpoints/` directory separate from `models/` |
| C-9 | LLM post-edit enhancement is optional — pipeline must work fully without it | Architecture | Core pipeline has zero dependency on any LLM API key |
| C-10 | CBP portal credentials must not be stored in source code | Security | Credentials stored in `.env` only, excluded from version control |

#### Assumptions

| # | Assumption | Basis |
|---|-----------|-------|
| A-1 | Source video content is in English (eng) — other source languages supported but English is primary | Tender scope |
| A-2 | Input videos are in MP4, MP3, or WAV format — other formats require pre-conversion | Pipeline design |
| A-3 | GPU hardware meeting minimum specifications is provisioned by the client | Deployment guide |
| A-4 | Model weights are downloaded once during setup and remain available on local storage | `download_models.py` |
| A-5 | The CBP portal API is accessible from the deployment server (internal network) | §4.2 integration |
| A-6 | Government-verified translations in `govt_tm.jsonl` are provided and maintained by the client's language team | TM management |
| A-7 | Reference audio files for voice cloning (Tier 2) are provided by the client per course | Voice cloning |
| A-8 | Course IDs are unique and stable — used as primary key for output folder structure | Output structure |
| A-9 | The iGOT platform's course quiz and metadata are available in DOCX or JSON format | Document translation |
| A-10 | Human reviewers assigned to the review interface have working knowledge of the target language | Human review |
| A-11 | Fine-tuned IndicTrans2 checkpoints are trained before production deployment | Fine-tuning guide |
| A-12 | The `.env` file is secured with appropriate OS-level file permissions on the deployment server | Security |

#### Dependencies

| # | Dependency | Owner | Risk if Unavailable |
|---|-----------|-------|---------------------|
| D-1 | NVIDIA GPU with CUDA 11.8+ | Client IT | Pipeline falls back to CPU — 10–20× slower |
| D-2 | Model weights in `models/` directory | Setup team | Pipeline cannot start — download required |
| D-3 | ffmpeg installed and on system PATH | Client IT | Audio extraction and video muxing will fail |
| D-4 | Python 3.10+ environment with `requirements.txt` installed | Setup team | All pipeline modules will fail to import |
| D-5 | CBP portal network access | Client network | Upload step fails — local output files still generated |
| D-6 | `.env` file with CBP credentials | Client admin | CBP upload disabled — all other functions unaffected |

---

*End of Section 5 — Project Background*

---

---

## SECTION 6 — SCOPE OF WORK

---

### 6.1 In-Scope Items

The following items are fully within the scope of the KB Translation System as delivered under tender RFB IN-KBL-543730-NC-RFB:

#### Core Pipeline

| # | Item | Description | Delivered By |
|---|------|-------------|-------------|
| IS-1 | Video Dubbing | End-to-end dubbing of MP4/MP3/WAV source content into all 22 scheduled Indian languages | `pipeline/dubbing_pipeline.py` |
| IS-2 | Automatic Speech Recognition | Transcription of source audio into time-stamped sentence segments using faster-whisper large-v3 | `pipeline/asr.py` |
| IS-3 | Machine Translation | Three-engine fallback translation chain: IndicTrans2 → SeamlessM4T → NLLB-200 | `pipeline/translator.py` |
| IS-4 | Text-to-Speech Synthesis | Four-engine fallback TTS chain: Parler-TTS Large → Mini → MMS-TTS → XTTS-v2 | `pipeline/tts.py` |
| IS-5 | Audio Assembly & Sync | Timestamp-based audio placement, fit-to-slot (max 1.35×), silence padding | `pipeline/video_processor.py` |
| IS-6 | Video Muxing | ffmpeg-based replacement of original audio track with dubbed audio | `pipeline/video_processor.py` |

#### Output Generation

| # | Item | Format | Delivered By |
|---|------|--------|-------------|
| IS-7 | Dubbed Video | `.mp4` | `pipeline/video_processor.py` |
| IS-8 | SRT Subtitles | `.srt` | `pipeline/subtitles.py` |
| IS-9 | VTT Subtitles | `.vtt` | `pipeline/subtitles.py` |
| IS-10 | Metadata Report | `_metadata.json` | `pipeline/dubbing_pipeline.py` |
| IS-11 | QA Self-Certification | `_qa_cert.docx` | `pipeline/dubbing_pipeline.py` |
| IS-12 | Translated Quiz | `_quiz_<lang>.docx` / `.xlsx` | `pipeline/doc_extractor.py` |
| IS-13 | Translated Metadata | `_metadata_<lang>.docx` | `pipeline/doc_extractor.py` |

#### Quality & Compliance

| # | Item | Description | Delivered By |
|---|------|-------------|-------------|
| IS-14 | Per-Segment Quality Scoring | Heuristic + ChrF + back-translation scoring (0–1 scale) | `pipeline/quality.py` |
| IS-15 | Quality Gate | Automatic silencing of segments scoring < 0.30 | `pipeline/translator.py` |
| IS-16 | 10-Rule Final Quality Check | Accuracy, completeness, grammar, fluency, consistency, corruption, placeholder-free, mixed-lang, formatting, professional | `pipeline/translator.py` |
| IS-17 | Glossary Injection | Per-language domain glossary applied at translation time | `pipeline/glossary.py` |
| IS-18 | Translation Memory | Exact + fuzzy matching (85% threshold) against govt_tm.jsonl | `scripts/translation_memory.py` |
| IS-19 | Factual Token Protection | Numbers, dates, currency, measurements preserved via `__F0__` placeholders | `pipeline/translator.py` |
| IS-20 | Duration Ratio Check | Warning if dubbed output > 120% of original duration per §5.1B | `pipeline/dubbing_pipeline.py` |

#### Operational Features

| # | Item | Description | Delivered By |
|---|------|-------------|-------------|
| IS-21 | Checkpoint / Resume | Crash-safe job resume from last completed segment | `pipeline/retry.py` |
| IS-22 | Multi-GPU Processing | ASR once in main process; translate+TTS+assemble distributed across GPUs | `pipeline/dubbing_pipeline.py` |
| IS-23 | Human Review Interface | Segment-level approve/correct/reject with DOCX certificate export | `ui/reviewer.py` |
| IS-24 | CBP Portal Upload | Automated upload of all output formats per §4.2 | `pipeline/cbp_uploader.py` |
| IS-25 | Voice Cloning (Tier 2) | XTTS-v2 voice cloning from reference speaker audio | `pipeline/voice_clone.py` |
| IS-26 | LLM Post-Edit (Optional) | Groq/Gemini/OpenRouter post-edit enhancement — pipeline works without it | `pipeline/llm_enhancer.py` |
| IS-27 | Monthly Delivery Reports | XLSX submission reports for KB tender tracking per §7.1 | `scripts/dub.py` |
| IS-28 | Audit Logging | Structured JSON audit trail — every job start/success/failure | `pipeline/logger.py` |
| IS-29 | Gradio Web UI | 8-tab interactive interface for operators | `ui/app.py` |
| IS-30 | CLI Tools | `dub.py`, `translate.py`, `translation_memory.py` | `scripts/` |

---

### 6.2 Out-of-Scope Items

The following items are explicitly excluded from the scope of the KB Translation System:

| # | Item | Reason | Tender Clause |
|---|------|--------|---------------|
| OS-1 | Translation of PM/President speeches | Explicitly prohibited | §3.1 |
| OS-2 | Translation of YouTube-only content not hosted on iGOT | Explicitly prohibited | §3.1 |
| OS-3 | PDF document translation | Explicitly blocked — PDF format not supported | §3.1 |
| OS-4 | Live / real-time translation or dubbing | Batch processing only — no streaming pipeline | — |
| OS-5 | Human interpreter or voice-over artist services | Fully automated pipeline — no human voice talent | — |
| OS-6 | Content creation or course authoring | Translation only — no new content generated | — |
| OS-7 | Cloud-based translation API integration (Google, Azure, AWS) | Data sovereignty requirement — all processing on-premise | — |
| OS-8 | Mobile application development | Web UI (Gradio) and CLI only | — |
| OS-9 | LMS integration beyond CBP portal upload | Only CBP portal upload is in scope per §4.2 | §4.2 |
| OS-10 | Translation of languages outside the 22 scheduled languages | Only constitutionally scheduled languages in scope | §6.1 |
| OS-11 | Video editing, captioning design, or branding | Audio replacement only — video frames unchanged | — |
| OS-12 | Hardware procurement or data centre setup | Client responsibility | Deployment guide |

---

### 6.3 Language Coverage — 22 Scheduled Indian Languages

All 22 constitutionally scheduled languages under the Eighth Schedule of the Constitution of India are covered:

| # | Language | ISO Code | Script | Group | TTS Engine | Translation Primary |
|---|----------|----------|--------|-------|-----------|---------------------|
| 1 | Hindi | hin | Devanagari | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 2 | Bengali | ben | Bengali | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 3 | Tamil | tam | Tamil | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 4 | Telugu | tel | Telugu | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 5 | Kannada | kan | Kannada | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 6 | Malayalam | mal | Malayalam | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 7 | Marathi | mar | Devanagari | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 8 | Gujarati | guj | Gujarati | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 9 | Punjabi | pan | Gurmukhi | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 10 | Odia | ory | Odia | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 11 | Assamese | asm | Bengali | KB-11 Mandatory | Parler-TTS Large | IndicTrans2 |
| 12 | Urdu | urd | Nastaliq | Extended | Parler-TTS Large | IndicTrans2 |
| 13 | Nepali | nep | Devanagari | Extended | Parler-TTS Large | IndicTrans2 |
| 14 | Maithili | mai | Devanagari | Extended | Parler-TTS Large | IndicTrans2 |
| 15 | Dogri | doi | Devanagari | Extended | MMS-TTS (standalone VITS) | SeamlessM4T |
| 16 | Bodo | bod | Devanagari | Extended | MMS-TTS | SeamlessM4T |
| 17 | Manipuri | mni | Meitei Mayek | Extended | MMS-TTS | IndicTrans2 (Hindi pivot) |
| 18 | Santhali | sat | Ol Chiki | Extended | MMS-TTS | IndicTrans2 (Hindi pivot) |
| 19 | Sanskrit | san | Devanagari | Extended | MMS-TTS | IndicTrans2 (Hindi pivot) |
| 20 | Konkani | kok | Devanagari | Extended | Parler-TTS Large | NLLB-200 |
| 21 | Sindhi | snd | Devanagari/Nastaliq | Extended | MMS-TTS | NLLB-200 |
| 22 | Kashmiri | kas | Nastaliq | Extended | MMS-TTS | NLLB-200 |

> **KB-11 Mandatory**: The 11 languages specified in the KB tender as highest-priority deliverables, requiring fine-tuned IndicTrans2 checkpoints and Parler-TTS Large as primary TTS engine.

---

### 6.4 Content Types Covered

| # | Content Type | Input Format | Output Format | Pipeline Module |
|---|-------------|-------------|---------------|----------------|
| CT-1 | Training Video | `.mp4` | Dubbed `.mp4` + `.srt` + `.vtt` | `dubbing_pipeline.py` |
| CT-2 | Audio Lecture | `.mp3`, `.wav` | Dubbed `.mp3` + `.srt` + `.vtt` | `dubbing_pipeline.py` |
| CT-3 | Course Quiz | `.docx`, `.json` | Translated `.docx` + `.xlsx` | `doc_extractor.py` |
| CT-4 | Course Metadata | `.json`, `.txt` | Translated `.docx` + `.xlsx` | `doc_extractor.py` |
| CT-5 | Plain Text | `.txt` | Translated `.txt` | `doc_extractor.py` |
| CT-6 | Word Document | `.docx` | Translated `.docx` | `doc_extractor.py` |
| CT-7 | Batch Text File | `.txt` (one sentence per line) | Translated `.txt` | `scripts/translate.py` |

> **Not supported**: `.pdf` (blocked per §3.1), `.pptx`, `.xlsx` as source, video formats other than MP4 without pre-conversion.

---

### 6.5 Exclusions per §3.1

The KB tender §3.1 defines specific content categories that must be detected and excluded from translation processing. The pipeline implements automatic exclusion detection:

| Exclusion Category | Detection Method | Pipeline Behaviour |
|-------------------|-----------------|-------------------|
| PM/President speeches | Keyword detection in transcript + metadata flag | Job rejected at intake — error logged to audit.log |
| YouTube-only content | URL pattern check in metadata (`youtube.com`, `youtu.be`) | Job rejected at intake — error logged to audit.log |
| PDF documents | File extension check at CLI and UI intake | Rejected immediately — user shown error message |
| Content with explicit exclusion flag | `excluded: true` field in course metadata JSON | Job skipped — exclusion reason written to metadata output |

> All exclusion events are written to `logs/audit.log` as structured JSON with timestamp, course ID, exclusion reason, and operator identity.

---

## SECTION 7 — SOLUTION OVERVIEW

---

### 7.1 Solution Summary

The KB Translation System is a **fully offline, on-premise, AI-powered dubbing pipeline** that automates the end-to-end conversion of English-language training videos into dubbed, subtitled, and quality-certified outputs in all 22 scheduled Indian languages.

The solution is built entirely on **open-source, locally-hosted AI models** — no proprietary APIs, no cloud services, and no internet connectivity required for core processing. All model inference runs on the client's own GPU hardware within the Government of India's data centre boundary.

The system is delivered as:

| Component | Description |
|-----------|-------------|
| **Python Pipeline** | Core inference engine — `pipeline/` package with 14 modules |
| **Gradio Web UI** | 8-tab browser-based interface for operators — `ui/app.py` |
| **CLI Tools** | Command-line scripts for batch processing — `scripts/` |
| **Fine-Tuning Framework** | IndicTrans2 and SeamlessM4T fine-tuning scripts — `finetune/` |
| **Translation Memory** | Government-verified term database with CLI management |
| **Glossary System** | 22 × per-language domain glossary JSON files |

The pipeline processes a single course video in **30–120 minutes per language** on a single GPU, or **8–30 minutes per language** with 4× GPU parallel processing — compared to **5–15 working days** for manual translation and dubbing.

---

### 7.2 Key Features

#### Intelligent Translation Engine

- **Three-engine fallback chain**: IndicTrans2 (fine-tuned) → SeamlessM4T → NLLB-200 — ensures every segment is translated even if the primary engine fails
- **Hindi pivot routing** for low-resource languages (Manipuri, Santhali, Sanskrit) where direct English→target models are unavailable
- **NLLB-200 as primary** for Konkani, Sindhi, Kashmiri where IndicTrans2 coverage is limited
- **S2ST (Speech-to-Speech Translation)** via SeamlessM4T for Indic→Indic pairs (hin↔ben↔kan↔tel↔urd) — bypasses ASR+TTS entirely for highest quality

#### Robust Quality Assurance

- **Per-segment quality scoring** (0–1 scale) using three independent methods: heuristic checks, ChrF metric, back-translation verification
- **Automatic quality gate**: segments scoring < 0.30 are silenced — no wrong-language audio ever reaches the output
- **10-rule final quality check** applied to every translated segment before TTS
- **Factual token protection**: numbers, dates, currency, measurements preserved exactly via placeholder system
- **Format token protection**: `{name}`, `%s`, `${var}`, `{{jinja}}` template variables preserved unchanged

#### Production-Grade Reliability

- **Checkpoint/resume**: every completed segment is checkpointed — crashes resume from last good segment with zero data loss
- **Concurrent job protection**: per-(course_id, lang) threading lock prevents duplicate processing
- **Stale cache detection**: source WAV re-extracted if input video is newer than cached file
- **Multi-temperature ASR fallback**: `[0.0, 0.2, 0.4]` temperature cascade for hallucination-prone segments
- **OOM handling**: TTS engine automatically falls back on GPU out-of-memory errors

#### Comprehensive Output Package

- Dubbed MP4 + SRT + VTT + metadata JSON + QA certificate per language per course
- Translated quiz (DOCX + XLSX) and metadata (DOCX) alongside video
- Monthly delivery XLSX reports for KB tender submission tracking
- Structured JSON audit log for every job

#### Operator-Friendly Interfaces

- **Gradio Web UI** with 8 tabs — no command-line knowledge required for standard operations
- **Human review interface** — segment-level approve/correct/reject with DOCX certificate export
- **Translation Memory CLI** — add/lookup/correct government-verified terms
- **Live log streaming** — real-time pipeline progress in browser (auto-refresh 3s)

---

### 7.3 Differentiators vs Manual Translation & Dubbing

| Dimension | Manual Approach | KB Translation System | Advantage |
|-----------|----------------|----------------------|-----------|
| **Cost per language per course** | ₹15,000 – ₹80,000 | ₹200 – ₹800 (compute only) | **95–98% cost reduction** |
| **Turnaround time per language** | 5–15 working days | 30–120 minutes (1 GPU) | **50–150× faster** |
| **Turnaround time (4× GPU)** | 5–15 working days | 8–30 minutes | **200–600× faster** |
| **Terminology consistency** | Low — varies by translator | High — TM + glossary enforced | **Standardised across all courses** |
| **Scalability** | Linear cost per new course | Near-zero marginal cost | **Unlimited scale** |
| **Quality assurance** | Manual proofreading only | Automated scoring + human review | **Systematic, auditable QA** |
| **Data sovereignty** | Risk — content sent to translators | Zero risk — fully on-premise | **Full data residency compliance** |
| **Availability** | Business hours only | 24/7 automated processing | **Always-on** |
| **Audit trail** | Paper-based or email | Structured JSON audit log | **Fully auditable** |
| **Voice consistency** | Varies by voice-over artist | Fixed seed per language | **Consistent voice per language** |
| **Subtitle generation** | Separate manual task | Automatic SRT + VTT | **Included at no extra cost** |
| **Quiz/metadata translation** | Separate manual task | Automatic DOCX + XLSX | **Included at no extra cost** |
| **CBP portal upload** | Manual per file | Fully automated | **Zero manual effort** |
| **Crash recovery** | Job must restart from scratch | Resume from last checkpoint | **No work lost** |

---

### 7.4 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        KB TRANSLATION SYSTEM                            │
│                   Fully Offline — On-Premise — India                    │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐
  │  Gradio UI   │     │   CLI Tools  │     │   Fine-Tuning Scripts    │
  │  (8 tabs)    │     │  dub.py      │     │  finetune_indictrans.py  │
  │  app.py      │     │  translate.py│     │  finetune_seamless.py    │
  └──────┬───────┘     └──────┬───────┘     └──────────────────────────┘
         │                    │
         └──────────┬─────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    DUBBING PIPELINE ORCHESTRATOR                    │
  │                      dubbing_pipeline.py                            │
  │   JobCheckpoint │ ThreadingLock │ Multi-GPU dispatch │ Audit Log    │
  └──────┬──────────────────┬──────────────────┬──────────────────┬────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
  ┌─────────────┐  ┌────────────────┐  ┌─────────────┐  ┌──────────────┐
  │    ASR      │  │  TRANSLATION   │  │    TTS      │  │   VIDEO      │
  │  asr.py     │  │ translator.py  │  │   tts.py    │  │  PROCESSOR   │
  │             │  │                │  │             │  │video_proc.py │
  │faster-      │  │IndicTrans2     │  │Parler-TTS   │  │              │
  │whisper      │  │  ↓             │  │  Large      │  │ffmpeg        │
  │large-v3     │  │SeamlessM4T     │  │  ↓          │  │extract audio │
  │             │  │  ↓             │  │Parler-TTS   │  │assemble WAV  │
  │22 langs     │  │NLLB-200        │  │  Mini       │  │mux video     │
  │auto-detect  │  │                │  │  ↓          │  │fit-to-slot   │
  └─────────────┘  │Quality Gate    │  │MMS-TTS      │  └──────────────┘
                   │TM Lookup       │  │  ↓          │
                   │Glossary Inject │  │XTTS-v2      │
                   └────────────────┘  └─────────────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                         OUTPUT PACKAGE                              │
  │  output/<course_id>/<lang>/                                         │
  │  ├── <course>_<lang>.mp4          ← Dubbed video                   │
  │  ├── <course>_<lang>.srt          ← Subtitles                      │
  │  ├── <course>_<lang>.vtt          ← Web subtitles                  │
  │  ├── <course>_<lang>_metadata.json ← Quality scores + transcript   │
  │  ├── <course>_<lang>_qa_cert.docx  ← QA self-certification         │
  │  ├── <course>_quiz_<lang>.docx    ← Translated quiz                │
  │  └── <course>_quiz_<lang>.xlsx    ← Translated quiz (Excel)        │
  └─────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌──────────────────┐     ┌──────────────────┐
  │   CBP Portal     │     │   Audit Logs     │
  │  cbp_uploader.py │     │  pipeline.log    │
  │  §4.2 upload     │     │  audit.log       │
  └──────────────────┘     └──────────────────┘
```

---

### 7.5 Technology Stack Summary

#### AI / ML Models

| Component | Model | Version | Size | Source |
|-----------|-------|---------|------|--------|
| ASR | faster-whisper large-v3 | CT2 quantised | ~3 GB | OpenAI / CTranslate2 |
| Translation (Primary) | IndicTrans2 | en_indic / indic_en / indic_indic | ~1.2 GB × 3 | AI4Bharat |
| Translation (Fallback 1) | SeamlessM4Tv2 | Large | ~10 GB | Meta AI |
| Translation (Fallback 2) | NLLB-200 | Distilled 600M | ~2.4 GB | Meta AI |
| TTS (Primary) | Parler-TTS Indic Large | Large | ~3.6 GB | AI4Bharat / Hugging Face |
| TTS (Fallback 1) | Parler-TTS Indic Mini | Mini | ~1.5 GB | AI4Bharat / Hugging Face |
| TTS (Fallback 2) | MMS-TTS | Shared VITS + adapters | ~1.5 GB | Meta AI |
| TTS (Last Resort) | Coqui XTTS-v2 | v2 | ~1.8 GB | Coqui AI (Apache 2.0) |

#### Core Frameworks & Libraries

| Category | Library | Version | Purpose |
|----------|---------|---------|---------|
| ML Framework | PyTorch | 2.1+ | Model inference and fine-tuning |
| Transformers | Hugging Face Transformers | 4.40+ | SeamlessM4T, NLLB-200, Parler-TTS |
| ASR Runtime | CTranslate2 | 3.x | faster-whisper inference |
| Audio Processing | librosa, soundfile, pydub | Latest | WAV manipulation, resampling |
| Video Processing | ffmpeg-python | Latest | Audio extraction, video muxing |
| Web UI | Gradio | 4.x | 8-tab browser interface |
| Document Processing | python-docx, openpyxl | Latest | DOCX/XLSX generation |
| Quality Metric | sacrebleu | Latest | ChrF scoring |
| Language Detection | langdetect | Latest | Per-segment language tagging |
| Fine-Tuning | DeepSpeed | ZeRO-3 | Multi-GPU fine-tuning |

#### Infrastructure

| Component | Specification | Notes |
|-----------|--------------|-------|
| OS | Ubuntu 22.04 LTS / Windows 10+ | Both supported |
| Python | 3.10 – 3.12 | 3.11 recommended |
| CUDA | 11.8 – 12.4 | Required for GPU inference |
| GPU | NVIDIA RTX 3090 / A100 / H100 | Minimum 16 GB VRAM |
| RAM | 64 GB minimum, 128 GB recommended | For multi-GPU jobs |
| Storage | 500 GB SSD minimum | Models + datasets + outputs |
| Video Processing | ffmpeg 6.x | Must be on system PATH |

#### Licensing Summary

| Model / Library | License | Commercial Use |
|----------------|---------|---------------|
| faster-whisper | MIT | ✅ Yes |
| IndicTrans2 | MIT | ✅ Yes |
| SeamlessM4Tv2 | CC-BY-NC 4.0 | ⚠️ Non-commercial — Government use permitted |
| NLLB-200 | CC-BY-NC 4.0 | ⚠️ Non-commercial — Government use permitted |
| Parler-TTS | Apache 2.0 | ✅ Yes |
| MMS-TTS | CC-BY-NC 4.0 | ⚠️ Non-commercial — Government use permitted |
| Coqui XTTS-v2 | Apache 2.0 | ✅ Yes |
| Gradio | Apache 2.0 | ✅ Yes |
| PyTorch | BSD | ✅ Yes |

> CC-BY-NC 4.0 models (SeamlessM4T, NLLB-200, MMS-TTS) are used under the non-commercial clause. Government of India deployments for public capacity building are classified as non-commercial use. Legal confirmation from the Ministry's legal team is recommended before production deployment.

---

*End of Section 7 — Solution Overview*

---

---

## SECTION 8 — SYSTEM ARCHITECTURE

---

### 8.1 Architecture Layers

The KB Translation System is organised into six distinct architectural layers, each with a clearly defined responsibility boundary:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — PRESENTATION LAYER                                           │
│  Gradio Web UI (ui/app.py) — 8 tabs                                     │
│  CLI Tools (scripts/dub.py, scripts/translate.py)                       │
│  Human Review Interface (ui/reviewer.py)                                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────┐
│  LAYER 2 — ORCHESTRATION LAYER                                          │
│  DubbingPipeline (pipeline/dubbing_pipeline.py)                         │
│  JobCheckpoint / Resume (pipeline/retry.py)                             │
│  Multi-GPU Dispatcher (_worker_dub_langs, multiprocessing spawn)        │
│  Per-job Threading Lock (_get_job_lock)                                 │
│  Exclusion Detection (check_exclusions / should_skip_translation)       │
└──────┬──────────────┬──────────────┬──────────────┬─────────────────────┘
       │              │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐ ┌────▼──────────────────────┐
│  LAYER 3A   │ │  LAYER 3B  │ │ LAYER 3C  │ │  LAYER 3D                 │
│  ASR        │ │TRANSLATION │ │   TTS     │ │  VIDEO PROCESSING         │
│  asr.py     │ │translator  │ │  tts.py   │ │  video_processor.py       │
│             │ │    .py     │ │           │ │                           │
│faster-      │ │IndicTrans2 │ │Parler-TTS │ │ffmpeg extract             │
│whisper      │ │SeamlessM4T │ │MMS-TTS    │ │assemble_dubbed_audio      │
│large-v3     │ │NLLB-200    │ │XTTS-v2    │ │replace_audio_in_video     │
└─────────────┘ └────────────┘ └───────────┘ └───────────────────────────┘
       │              │              │              │
┌──────▼──────────────▼──────────────▼──────────────▼─────────────────────┐
│  LAYER 4 — SUPPORT LAYER                                                │
│  Quality Scoring    (pipeline/quality.py)    — heuristic+ChrF+BT        │
│  Glossary Manager   (pipeline/glossary.py)   — 22×JSON term injection   │
│  Translation Memory (scripts/translation_memory.py) — TM lookup         │
│  Subtitle Generator (pipeline/subtitles.py)  — SRT + VTT               │
│  Document Extractor (pipeline/doc_extractor.py) — DOCX/TXT/JSON        │
│  Voice Cloner       (pipeline/voice_clone.py) — XTTS-v2 cloning        │
│  LLM Enhancer       (pipeline/llm_enhancer.py) — optional post-edit    │
│  Lang Detector      (pipeline/lang_detect.py) — per-segment tagging    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────┐
│  LAYER 5 — INTEGRATION LAYER                                            │
│  CBP Portal Uploader (pipeline/cbp_uploader.py) — §4.2 upload          │
│  Audit Logger        (pipeline/logger.py)       — JSON audit trail      │
│  Retry Decorator     (pipeline/retry.py)        — exponential backoff   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────┐
│  LAYER 6 — MODEL LAYER                                                  │
│  models/indic_asr/          faster-whisper large-v3 CT2 weights (~3GB)  │
│  models/indic_tr/           IndicTrans2 en_indic/indic_en/indic_indic   │
│  models/indic_parler_tts_large/  Parler-TTS Indic Large (~3.6GB)       │
│  models/seamless/           SeamlessM4Tv2 (~10GB)                       │
│  models/nllb/               NLLB-200 distilled (~2.4GB)                │
│  models/mms/                MMS-TTS shared VITS + adapters (~1.5GB)    │
│  checkpoints/indictrans/    Fine-tuned IndicTrans2 checkpoints          │
└─────────────────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility | Key Files |
|-------|---------------|-----------|
| Presentation | User interaction — web UI and CLI | `ui/app.py`, `scripts/dub.py`, `scripts/translate.py` |
| Orchestration | Job lifecycle, GPU dispatch, checkpoint, locking | `pipeline/dubbing_pipeline.py`, `pipeline/retry.py` |
| Inference | ASR, Translation, TTS, Video processing | `pipeline/asr.py`, `pipeline/translator.py`, `pipeline/tts.py`, `pipeline/video_processor.py` |
| Support | Quality, glossary, TM, subtitles, documents | `pipeline/quality.py`, `pipeline/glossary.py`, `pipeline/subtitles.py` |
| Integration | CBP upload, logging, retry | `pipeline/cbp_uploader.py`, `pipeline/logger.py`, `pipeline/retry.py` |
| Model | Pre-trained and fine-tuned model weights on disk | `models/`, `checkpoints/` |

---

### 8.2 Component Diagram

```
                        ┌─────────────────────────────────┐
                        │         OPERATOR INTERFACES      │
                        │  ┌──────────────┐ ┌───────────┐ │
                        │  │  Gradio UI   │ │  CLI      │ │
                        │  │  (8 tabs)    │ │  dub.py   │ │
                        │  └──────┬───────┘ └─────┬─────┘ │
                        └─────────┼───────────────┼───────┘
                                  └───────┬────────┘
                                          │
                        ┌─────────────────▼───────────────┐
                        │       DUBBING PIPELINE           │
                        │   dubbing_pipeline.py            │
                        │                                  │
                        │  ┌──────────┐  ┌─────────────┐  │
                        │  │ Job      │  │ Multi-GPU   │  │
                        │  │Checkpoint│  │ Dispatcher  │  │
                        │  └──────────┘  └─────────────┘  │
                        │  ┌──────────┐  ┌─────────────┐  │
                        │  │ Thread   │  │ Exclusion   │  │
                        │  │  Lock    │  │ Detector    │  │
                        │  └──────────┘  └─────────────┘  │
                        └──┬──────────┬──────────┬─────────┘
                           │          │          │
              ┌────────────▼─┐  ┌─────▼──────┐  ┌▼────────────────┐
              │  ASREngine   │  │ Translator │  │   TTSEngine     │
              │  asr.py      │  │translator.py│  │   tts.py        │
              │              │  │            │  │                 │
              │faster-whisper│  │IndicTrans2 │  │ Parler-TTS Lg   │
              │large-v3      │  │SeamlessM4T │  │ MMS-TTS         │
              │22 langs      │  │NLLB-200    │  │ XTTS-v2         │
              │auto-detect   │  │Pivot(hin)  │  │ Standalone VITS │
              └──────────────┘  └─────┬──────┘  └────────┬────────┘
                                      │                   │
                        ┌─────────────▼───────────────────▼─────────┐
                        │           SUPPORT COMPONENTS               │
                        │                                            │
                        │  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
                        │  │ Quality  │  │ Glossary │  │   TM    │ │
                        │  │ Scorer   │  │ Manager  │  │ Lookup  │ │
                        │  │quality.py│  │glossary.py│  │tm.py   │ │
                        │  └──────────┘  └──────────┘  └─────────┘ │
                        │  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
                        │  │Subtitles │  │  Doc     │  │  Voice  │ │
                        │  │Generator │  │Extractor │  │  Clone  │ │
                        │  │subtitles │  │doc_extr. │  │voice_cl.│ │
                        │  └──────────┘  └──────────┘  └─────────┘ │
                        └─────────────────────────────────────────┬─┘
                                                                   │
                        ┌──────────────────────────────────────────▼─┐
                        │         VIDEO PROCESSOR                     │
                        │         video_processor.py                  │
                        │  ffmpeg extract │ assemble │ mux │ stretch  │
                        └──────────────────────────────────────────┬─┘
                                                                   │
                        ┌──────────────────────────────────────────▼─┐
                        │         INTEGRATION LAYER                   │
                        │  CBPUploader  │  Logger  │  RetryDecorator  │
                        │  cbp_uploader │ logger.py│  retry.py        │
                        └─────────────────────────────────────────────┘
```

---

### 8.3 Data Flow Diagram

```
INPUT
  │
  │  MP4 / MP3 / WAV
  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1 — AUDIO EXTRACTION                                           │
│ video_processor.extract_audio()                                     │
│ ffmpeg → 16kHz mono WAV → tmp/<job_id>/source.wav                  │
│ Stale cache check: re-extract if video newer than cached WAV        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  source.wav
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1b — S2ST FAST PATH (Indic→Indic only)                        │
│ translator.translate_speech_to_speech()                             │
│ SeamlessM4T: audio → dubbed audio (no ASR/TTS needed)              │
│ Supported pairs: hin↔ben↔kan↔tel↔urd                               │
│ → if success: mux + return early                                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  (fallthrough if S2ST not applicable)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2 — ASR TRANSCRIPTION                                          │
│ asr.transcribe_segments()                                           │
│ faster-whisper large-v3 → sentence segments with timestamps         │
│ condition_on_previous_text=False (hallucination guard)              │
│ temperature=[0.0, 0.2, 0.4] (multi-temp fallback)                  │
│ Nastaliq normalisation for urd/kas/snd                              │
│ Hallucination stripping → segment merging (6–12 words, 1.5–12s)    │
│ → [{id, start, end, text, detected_lang}, ...]                     │
│ Checkpoint: segments saved to JobCheckpoint                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  segments[]
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3 — TRANSLATION                                                │
│ translator.translate_batch()                                        │
│                                                                     │
│ Per segment:                                                        │
│   protect_format_tokens() → __FMT0__                               │
│   protect_nontranslatable() → __NT0__                              │
│   protect_factual_tokens() → __F0__                                │
│                                                                     │
│ Engine routing:                                                     │
│   IndicTrans2 (primary) → SeamlessM4T (fallback) → NLLB (final)   │
│   Hindi pivot for mni/sat/san                                       │
│   NLLB-only for kok/snd/kas                                         │
│   Seamless-first for bod/doi                                        │
│                                                                     │
│ Post-processing:                                                    │
│   restore tokens → naturalise → 10-rule FQC                        │
│   glossary.apply() → quality.score_segment()                       │
│   Quality gate: score < 0.30 → text = "" (silence)                 │
│                                                                     │
│ Checkpoint: each segment result saved atomically                    │
│ → [{...seg, text, engine, quality}, ...]                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  translated_segments[]
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4 — TTS SYNTHESIS                                              │
│ tts.synthesize_segments()                                           │
│                                                                     │
│ Per segment:                                                        │
│   Parler-TTS Large (primary, fixed seed per lang)                  │
│   → MMS-TTS (fallback, per-lang adapter swap)                      │
│   → XTTS-v2 (last resort)                                          │
│   → silence (if all engines fail)                                  │
│                                                                     │
│ OOM handling: clear CUDA cache + retry once                         │
│ Empty text → silence written directly                               │
│ → [{...seg, audio_path}, ...]                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  tts_segments[] with audio_path
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5 — AUDIO ASSEMBLY                                             │
│ video_processor.assemble_dubbed_audio()                             │
│                                                                     │
│ For each segment:                                                   │
│   Place at original timestamp in output buffer                      │
│   Speed up max 1.35× if overruns slot (atempo filter)              │
│   Hard-trim if still over after speed-up                            │
│   10ms fade-in to eliminate click                                   │
│   Pad with silence to match original duration                       │
│ → dubbed.wav (exact original duration)                             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  dubbed.wav
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6 — OUTPUT GENERATION                                          │
│                                                                     │
│ subtitles.generate_subtitles() → .srt + .vtt                       │
│ video_processor.replace_audio_in_video() → .mp4                    │
│   (embeds SRT as soft subtitle track via mov_text)                 │
│ Duration ratio check → warn if > 1.20×                             │
│ dubbing_pipeline._save_metadata() → _metadata.json                 │
│ generate_qa_report() → _qa_cert.docx                               │
│ Checkpoint cleared on success                                       │
│ tmp/ directory removed on success                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
OUTPUT: output/<course_id>/<lang>/
  <course>_<lang>.mp4
  <course>_<lang>.srt
  <course>_<lang>.vtt
  <course>_<lang>_metadata.json
  <course>_<lang>_qa_cert.docx
```

---

### 8.4 Module Dependency Map

```
dubbing_pipeline.py
    ├── asr.py
    │     ├── lang_config.py
    │     └── lang_detect.py
    ├── translator.py
    │     ├── lang_config.py
    │     ├── quality.py
    │     │     └── logger.py
    │     ├── logger.py
    │     └── retry.py
    ├── tts.py
    │     ├── lang_config.py
    │     └── logger.py
    ├── video_processor.py
    ├── glossary.py
    │     └── lang_config.py
    ├── quality.py
    ├── retry.py  (JobCheckpoint + retry decorator)
    │     └── logger.py
    ├── logger.py
    ├── lang_config.py
    ├── subtitles.py
    │     ├── lang_config.py
    │     └── logger.py
    ├── voice_clone.py  (optional — Tier 2)
    │     ├── lang_config.py
    │     └── logger.py
    └── cbp_uploader.py  (optional — §4.2)
          └── logger.py

scripts/translation_memory.py  (standalone — no pipeline import)
pipeline/llm_enhancer.py       (standalone — no pipeline import)
pipeline/doc_extractor.py      (standalone — no pipeline import)
```

All modules use lazy model loading — no model weights are loaded at import time. Models load on first inference call and remain in GPU memory for the lifetime of the process.

---

### 8.5 Folder Structure

```
project/
│
├── pipeline/                    ← Core inference package
│   ├── __init__.py
│   ├── asr.py                   ← faster-whisper large-v3
│   ├── translator.py            ← IndicTrans2 + SeamlessM4T + NLLB-200
│   ├── tts.py                   ← Parler-TTS + MMS-TTS + XTTS-v2
│   ├── dubbing_pipeline.py      ← Orchestrator — 6-step pipeline
│   ├── video_processor.py       ← ffmpeg audio/video operations
│   ├── glossary.py              ← Per-language glossary injection
│   ├── lang_config.py           ← Language codes for all engines
│   ├── quality.py               ← Heuristic + ChrF + back-translation
│   ├── subtitles.py             ← SRT + VTT generation
│   ├── lang_detect.py           ← Per-segment language detection
│   ├── doc_extractor.py         ← DOCX/TXT/JSON translation
│   ├── voice_clone.py           ← XTTS-v2 voice cloning (Tier 2)
│   ├── cbp_uploader.py          ← CBP portal upload (§4.2)
│   ├── llm_enhancer.py          ← Optional LLM post-edit
│   ├── logger.py                ← Structured JSON logging
│   └── retry.py                 ← Retry decorator + JobCheckpoint
│
├── ui/
│   ├── app.py                   ← Gradio 8-tab web UI
│   └── reviewer.py              ← Human review interface
│
├── scripts/
│   ├── dub.py                   ← CLI entry point
│   ├── translate.py             ← Text/audio/batch translation CLI
│   ├── translation_memory.py    ← TM management CLI + library
│   ├── download_models.py       ← Download all model weights
│   ├── download_datasets.py     ← Download parallel training data
│   ├── build_asr_index.py       ← Build ASR fine-tune index
│   ├── check_gaps.py            ← Verify 22-lang dataset coverage
│   ├── clean_outputs.py         ← Wipe output/ + checkpoints/
│   ├── clean_and_run_all22.py   ← Auto-clean then dub all 22 langs
│   └── test_pipeline.py         ← Smoke test
│
├── finetune/
│   ├── finetune_indictrans.py   ← Fine-tune IndicTrans2
│   ├── finetune_seamless.py     ← Fine-tune SeamlessM4T
│   └── ds_zero3.json            ← DeepSpeed ZeRO-3 config
│
├── models/                      ← Downloaded weights (not in git)
│   ├── indic_asr/               ← faster-whisper large-v3 CT2
│   ├── indic_tr/                ← IndicTrans2 (3 directions)
│   ├── indic_parler_tts_large/  ← Parler-TTS Indic Large
│   ├── indic_parler_tts/        ← Parler-TTS Indic Mini (fallback)
│   ├── seamless/                ← SeamlessM4Tv2
│   ├── nllb/                    ← NLLB-200 distilled
│   └── mms/                     ← MMS-TTS shared base + adapters
│
├── checkpoints/
│   ├── indictrans/
│   │   ├── en_indic/best/       ← Fine-tuned English → Indic
│   │   ├── indic_en/best/       ← Fine-tuned Indic → English
│   │   └── indic_indic/best/    ← Fine-tuned Indic → Indic
│   └── jobs/                    ← Runtime job checkpoints
│
├── glossary/                    ← 22 × <lang>.json glossary files
├── translation_memory/          ← govt_tm.jsonl + human_feedback.jsonl
├── datasets/                    ← Parallel training data
├── input/                       ← Source videos / documents
├── output/                      ← All dubbed outputs
├── logs/                        ← pipeline.log + audit.log
├── assets/xtts_refs/            ← Reference WAVs for voice cloning
├── .env                         ← Credentials (not in git)
├── requirements.txt
└── README.md
```

---

*End of Section 8 — System Architecture*

---

---

## SECTION 9 — TECHNICAL DESIGN

---

### 9.1 ASR Module Design

**File:** `pipeline/asr.py` | **Class:** `ASREngine`

#### Engine Selection
faster-whisper large-v3 is used as the single ASR engine for all 22 languages. It is a CTranslate2-quantised version of OpenAI Whisper large-v3, providing float16 inference on GPU and int8 on CPU. A single model load handles all 22 languages — no per-language adapter swaps required.

#### Model Loading Priority
```
1. models/indic_asr/model.bin          ← local CT2 weights (fastest)
2. models/indic_asr/<HF snapshot>/     ← cached HF download
3. "large-v3"                          ← auto-download from HF (fallback)
```

#### Transcription Parameters
| Parameter | Value | Purpose |
|-----------|-------|---------|
| `beam_size` | 5 | Beam search for accuracy |
| `vad_filter` | True | Voice activity detection — skip silence |
| `vad_parameters` | min_silence_duration_ms=500 | Minimum silence gap |
| `word_timestamps` | True | Word-level timing for segment merging |
| `condition_on_previous_text` | False | Prevents hallucination loops |
| `temperature` | [0.0, 0.2, 0.4] | Multi-temp fallback breaks repetition |
| `no_speech_threshold` | 0.6 | Reject low-confidence segments |
| `compression_ratio_threshold` | 2.4 | Reject repetitive/hallucinated output |

#### Segment Merging Logic (`_merge_segments`)
Raw faster-whisper segments are merged into natural sentence-length chunks:
- Merge until ≥ 6 words AND ≥ 1.5 seconds
- Never exceed 12 seconds per segment
- Always split on sentence-ending punctuation (`. ! ?`)
- Output: `[{id, start, end, text}]`

#### Nastaliq Normalisation
Arabic-script ASR output for Urdu, Kashmiri, and Sindhi is normalised using a character substitution map (`_NASTALIQ_NORM`) that corrects common OCR/ASR inconsistencies — e.g., Arabic kaf (ك) → Urdu kaf (ک), Arabic ya (ي) → Urdu ya (ی).

#### Hallucination Stripping (`_strip_hallucinations`)
A regex pattern (`_HALLUC_PREFIX`) removes known Whisper hallucination words that appear at segment boundaries when audio is unclear — e.g., "Wanner", "Gonna", "Venna". These corrupt downstream translation output.

#### Language Auto-Detection
When `lang="auto"`, faster-whisper's built-in language detection is used. The detected language code is mapped to the internal 3-letter code via `fw_lang_to_internal()` and stored in the checkpoint for all subsequent steps.

---

### 9.2 Translation Engine Design

**File:** `pipeline/translator.py` | **Class:** `Translator`

#### Three-Engine Fallback Chain

```
Input text
    │
    ├─ Is src_lang == tgt_lang?  → passthrough (score=1.0)
    ├─ Is fully non-translatable? → passthrough_nontranslatable
    │
    ▼
Protect tokens:
    _protect_format_tokens()   → __FMT0__, __FMT1__, ...
    _protect_nontranslatable() → __NT0__, __NT1__, ...
    _protect_factual_tokens()  → __F0__, __F1__, ...
    │
    ▼
Route:
    ├─ force_nllb (kok/snd/kas)?     → NLLB-200 directly
    ├─ seamless_first (bod/doi)?     → SeamlessM4T → IndicTrans2 → NLLB
    ├─ pivot_langs (mni/sat/san)?    → IndicTrans2 via Hindi pivot
    └─ default?                      → IndicTrans2 → SeamlessM4T → NLLB
    │
    ▼
Post-process:
    _clean_unk()              → remove <unk> tokens
    _clean_mixed_lang()       → strip foreign-script word runs
    _restore_nontranslatable()
    _restore_factual_tokens()
    _verify_factual_tokens()  → append missing numbers/dates
    _restore_format_tokens()
    _naturalise()             → fix repeated words, space-before-punct
    _final_quality_check()    → 10-rule gate
    glossary.apply()          → enforce domain terms (applied last)
    quality.score_segment()   → 0–1 quality score
```

#### IndicTrans2 Batch Translation
- Direction determined by language pair: `en_indic`, `indic_en`, or `indic_indic`
- Fine-tuned checkpoint used if present at `checkpoints/indictrans/<direction>/best/`
- Tokenizer loaded directly from local module to avoid AutoTokenizer kwarg conflict
- `max_new_tokens=512`, `num_beams=5`, `no_repeat_ngram_size=3`
- `repetition_penalty=1.1` for short segments (< 40 chars), `1.2` for longer

#### Hindi Pivot Routing
For low-resource languages (Manipuri, Santhali, Sanskrit) where direct English→target coverage is poor:
```
English → Hindi (IndicTrans2 en_indic)
Hindi   → Target (IndicTrans2 indic_indic)
```

#### Token Protection System
Three independent protection layers prevent translation engines from corrupting special tokens:

| Layer | Pattern | Placeholder | Example |
|-------|---------|-------------|---------|
| Format tokens | `{name}`, `%s`, `${var}`, `{{jinja}}` | `__FMT0__` | `{user_name}` → `__FMT0__` |
| Non-translatable | URLs, paths, code, @mentions | `__NT0__` | `https://example.com` → `__NT0__` |
| Factual tokens | Numbers, dates, currency, measurements | `__F0__` | `₹5,000` → `__F0__` |

After translation, tokens are restored in reverse order. `_verify_factual_tokens()` appends any missing factual tokens at the end of the translation to ensure no number or date is lost.

#### 10-Rule Final Quality Check (`_final_quality_check`)
Applied to every segment before returning from the translation engine:

| Rule | Check | Auto-fix |
|------|-------|---------|
| 1. Accuracy | Non-empty output for non-empty source | Restore source as last resort |
| 2. Completeness | Output ≥ 20% length of source | Flag `fqc:suspiciously_short` |
| 3. Grammar | Sentence-initial lowercase after `. ` (Latin targets) | Auto-capitalise |
| 4. Fluency | No 3+ identical punctuation runs | Collapse to single |
| 5. Consistency | All `__FMT__`/`__NT__`/`__F__` placeholders restored | Force-restore |
| 6. Corruption | No U+FFFD replacement char, no null bytes | Strip |
| 7. Placeholder-free | No `__WORD__` artifacts remain | Strip |
| 8. Mixed-lang-free | Re-run `_clean_mixed_lang` as final pass | Strip foreign runs |
| 9. Formatting | Leading/trailing whitespace, single spaces | Normalise |
| 10. Professional | Strip `[UNK]`, `[PAD]`, `[BOS]`, `[EOS]`, `[MASK]` | Strip |

---

### 9.3 TTS Engine Design

**File:** `pipeline/tts.py` | **Class:** `TTSEngine`

#### Four-Engine Fallback Chain

```
Input: translated text + lang code
    │
    ├─ lang in _PARLER_SKIP_LANGS (sat/kas/snd)?
    │     └─ skip Parler → go to MMS directly
    │
    ▼
1. Parler-TTS Indic Large (primary)
   - Fixed seed per language (_LANG_SEEDS: hin=42, ben=43, ...)
   - max_new_tokens = grapheme_count × 25 (min 200, max 1500)
   - OOM: clear CUDA cache + retry once
   - Failure check: duration < 0.5s OR peak < 0.02 → fallback
    │
    ▼ (if Parler fails)
2. Standalone VITS (doi only)
   - facebook/mms-tts-dgo loaded from models/mms_standalone/dgo/
    │
    ▼ (if standalone VITS fails or not applicable)
3. MMS-TTS (shared VITS base + per-lang adapter)
   - load_adapter() API for transformers ≥ 4.40
   - Manual safetensors load for older transformers
   - Token limit: 450 tokens max (prevents VITS repetition loop)
   - One-at-a-time processing (avoids padding artifacts)
    │
    ▼ (if MMS fails)
4. Coqui XTTS-v2 (last resort)
   - Per-language reference WAV from assets/xtts_refs/<lang>.wav
   - Falls back to generic_indic.wav if per-lang ref absent
    │
    ▼ (if all engines fail)
   Write silence (ffmpeg anullsrc or numpy zeros)
```

#### Voice Consistency
Fixed random seeds per language (`_LANG_SEEDS`) ensure the same voice character is produced for every segment of a course, regardless of processing order or batch size. `torch.manual_seed(seed)` and `torch.cuda.manual_seed_all(seed)` are called before every Parler generate call.

#### Audio Post-Processing (`_post_process`)
Applied to all TTS output before writing to disk:
1. High-pass filter at 80 Hz (Butterworth 2nd order) — removes DC offset and rumble
2. Low-pass filter at 12 kHz for MMS output — reduces high-frequency artifacts
3. Normalise to -1 dBFS (peak = 0.891)
4. Optional pitch shift +5 semitones for female voice (librosa, soxr_hq backend)

#### Script Normalisation
- Santhali (sat): Ol Chiki characters transliterated to Devanagari for Parler/XTTS (MMS sat adapter handles Ol Chiki natively)
- Urdu/Kashmiri/Sindhi: Nastaliq normalisation applied upstream in ASR; TTS receives clean Arabic-script text

---

### 9.4 Video Processing Design

**File:** `pipeline/video_processor.py` | **Class:** `VideoProcessor`

#### Audio Extraction (`extract_audio`)
- Uses bundled ffmpeg from `imageio_ffmpeg` if system ffmpeg not on PATH
- Extracts to 16kHz mono WAV for ASR compatibility
- If no audio stream detected: generates silence matching video duration
- On extraction failure: re-encodes input to clean MP4 first, then re-extracts

#### Audio Assembly (`assemble_dubbed_audio`)
The core sync algorithm places each TTS segment at its original timestamp:

```python
for each segment:
    slot_samp = max(next_start - start, seg_end - start, 0.1s) × sample_rate
    if len(seg_audio) > slot_samp:
        ratio = min(len(seg_audio) / slot_samp, 1.35)   # max 1.35× speed-up
        seg_audio = atempo_stretch(seg_audio, ratio)
        if still over: hard-trim to slot_samp
    apply 10ms fade-in (eliminates click at segment start)
    place at start_samp in output buffer
normalise output to -1 dBFS
```

#### Time-Stretching (`_atempo_stretch_file`)
Uses ffmpeg `atempo` filter (time-domain, no phase smearing):
- Single filter for ratios 0.5–2.0
- Chained filters for ratios outside range: `atempo=2.0,atempo=<remainder>`
- Falls back to original audio on ffmpeg error

#### Video Muxing (`replace_audio_in_video`)
1. Pad dubbed WAV with silence to exactly match video duration
2. ffmpeg mux: `-c:v copy` (no video re-encode) + `-c:a aac -b:a 192k`
3. Optionally embed SRT as soft subtitle track (`-c:s mov_text`)
4. On mux failure: retry with `-c:v libx264 -preset ultrafast` (re-encode video)

#### Stale Cache Detection
`source.wav` is re-extracted if `Path(wav_path).stat().st_mtime < Path(video_path).stat().st_mtime` — ensures the pipeline never uses a cached WAV from a previous version of the input video.

---

### 9.5 Quality Scoring Design

**File:** `pipeline/quality.py`

#### Scoring Architecture
Every translated segment receives a composite quality score (0.0–1.0) from three independent methods:

```
score_segment()          ← fast heuristic (used in pipeline hot path)
score_segment_full()     ← heuristic + back-translation (used in QA reports)
```

#### Heuristic Scoring (8 checks)

| Check | Penalty | Condition |
|-------|---------|-----------|
| Length ratio | −0.25 | `tgt_words / src_words < 0.3` or `> 4.0` |
| Source language leakage | −0.30 | Native script chars < 50% of total alpha chars |
| Repetition loop | −0.35 | 4+ consecutive identical words |
| Untranslated (exact copy) | −0.40 | `translation == source` |
| Untranslated (Latin output) | −0.35 | > 80% Latin chars for non-Latin target |
| Too short | −0.30 | Source ≥ 5 words but translation < 2 words |
| Transliteration detected | −0.35 | Latin ratio > 60% in non-Latin target |
| Missing numbers | −0.20 | Source numbers absent from translation |

#### ChrF Scoring
Character n-gram F-score (n=6, β=2) — weights recall higher than precision. Only computed for same-script pairs (cross-script ChrF is not meaningful). Returns 0.0–1.0.

#### Back-Translation Scoring
Translates the output back to the source language, then measures word overlap with the original source. Uses the pipeline's existing `Translator` instance (injected via `set_shared_translator()`) to avoid loading a second model into GPU memory. Returns 0.0–1.0 or −1.0 on failure.

#### Quality Thresholds

| Score | Status | Pipeline Action |
|-------|--------|----------------|
| ≥ 0.55 | ✅ Pass | Accepted — sent to TTS |
| 0.30–0.55 | ⚠️ Review | Flagged — sent to TTS but marked for human review |
| < 0.30 | ❌ Failed | Silenced — `text = ""` — silence written instead of TTS |

#### Transliteration Detection (`detect_transliteration`)
Per KB tender §3.2, transliteration (writing source words in Latin script instead of translating to target script) is explicitly prohibited. Detection: if Latin chars > 60% of total alpha chars in a non-Latin target language output, the segment is flagged `transliteration_detected`.

---

### 9.6 Subtitle Generation Design

**File:** `pipeline/subtitles.py`

#### SRT Generation (`generate_srt`)
Iterates translated segments, formats each as:
```
<index>
HH:MM:SS,mmm --> HH:MM:SS,mmm
<translated text>
```
Empty segments are skipped. Output written as UTF-8 to `<course_id>_<lang>.srt`.

#### VTT Generation (`generate_vtt`)
Same as SRT but with `WEBVTT` header and `.` instead of `,` as millisecond separator. Output written to `<course_id>_<lang>.vtt`.

#### Subtitle Embedding
Two modes available:
- **Soft subtitles** (`embed_subtitles_soft`): SRT embedded as selectable track inside MP4 container via `mov_text` codec — viewer can toggle on/off. Language metadata tag set to target language code.
- **Hard subtitles** (`burn_subtitles`): SRT burned into video stream via ffmpeg `subtitles=` filter — permanent, cannot be toggled. Used as fallback if soft embed fails.

The pipeline uses soft subtitles by default (embedded during `replace_audio_in_video` via `-c:s mov_text`).

---

### 9.7 Glossary & Translation Memory Design

#### Glossary Manager (`pipeline/glossary.py` | `GlossaryManager`)

**Storage:** 22 × `glossary/<lang>.json` files. Format: `{"source_term": "translated_term", ...}`. All keys stored lowercase for case-insensitive matching.

**Application strategy:** Glossary is applied **after** translation engine output, not before. This avoids placeholder injection artifacts that cause hallucination in IndicTrans2. Only source terms that literally leaked through unchanged are replaced via word-boundary regex.

**Artifact cleanup:** `_GLOSS_ARTIFACT` regex strips any `__GLOSS_N__` placeholder artifacts that the model may have emitted literally. `_STRAY_PREFIX` regex strips stray Gurmukhi/Malayalam characters that appear at segment start after glossary processing.

**Term protection (alternative mode):** `protect_terms()` / `restore_terms()` methods available for pre-translation protection when needed for specific engines.

#### Translation Memory (`scripts/translation_memory.py` | `TranslationMemory`)

**Storage:** Three JSONL files in `translation_memory/`:
- `govt_tm.jsonl` — government-verified translations (highest priority)
- `human_feedback.jsonl` — human corrections from reviewer interface
- `correction_log.jsonl` — audit trail of all corrections

**Lookup strategy:**
1. Exact match in `govt_tm.jsonl` → return immediately (score=1.0)
2. Exact match in `human_feedback.jsonl` → return (score=0.95)
3. Fuzzy match at ≥ 85% threshold (difflib SequenceMatcher) → return with match score
4. No match → return None → pipeline proceeds to translation engine

**Integration point:** `DubbingPipeline._translate_text()` checks TM before calling the translation engine. TM hits bypass the engine entirely, saving GPU compute and ensuring consistency.

---

### 9.8 Document Translation Design

**File:** `pipeline/doc_extractor.py`

#### Format Support

| Format | Extraction | Translation | Output |
|--------|-----------|-------------|--------|
| `.docx` | `python-docx` paragraph + table extraction | `translate_docx()` — run-level, preserves bold/italic/underline | Translated `.docx` |
| `.txt` | `Path.read_text()` | Per-paragraph via `translate_document_batch()` | Translated `.txt` |
| `.json` | `json.loads()` | Per-value string translation | Translated `.json` |
| `.pdf` | `pdfplumber` (extract only) | **Blocked per §3.1** — no translation | Error returned |

#### DOCX Format Preservation (`translate_docx`)
Translates a `.docx` file while preserving all formatting:
- Paragraph styles (Heading 1/2/3, Normal, List Bullet)
- Run-level formatting (bold, italic, underline, font size, colour)
- Tables (cell by cell, paragraph by paragraph)
- Headers and footers (all 6 variants: first/even/odd × header/footer)
- Inline images (copied unchanged — not translated)
- Hyperlinks (text translated, URL preserved)

**Strategy:** Translate each paragraph as one unit — put result in first run, clear all other runs. This preserves run boundaries (bold/italic) while avoiding fragmented translation of split words.

#### Batch Translation Mode (`translate_document_batch`)
Used for document paragraphs — bypasses all placeholder protection layers (format/NT/factual token protection) which cause hallucination on document-length text. Only `_clean_unk()` is applied to output.

---

### 9.9 Voice Cloning Design

**File:** `pipeline/voice_clone.py` | **Class:** `VoiceCloner`

#### Technology
Coqui XTTS-v2 (Apache 2.0, fully offline). Supports 10 Indian languages natively: `hin ben guj mar tam tel kan mal pan urd`.

#### Supported Languages
```python
XTTS_LANG_MAP = {
    "hin": "hi", "ben": "bn", "guj": "gu", "mar": "mr",
    "tam": "ta", "tel": "te", "kan": "kn", "mal": "ml",
    "pan": "pa", "urd": "ur",
}
```

#### Cloning Workflow
```
1. extract_speaker_embedding(reference_audio)
   → model.get_conditioning_latents([reference_audio])
   → {gpt_cond_latent, speaker_embedding}  ← computed ONCE per course

2. For each segment:
   synthesize_with_clone(text, lang, reference_audio, output_path,
                         speaker_embedding=embedding)
   → model.inference(text, language, gpt_cond_latent, speaker_embedding)
   → sf.write(output_path, wav, 24000)
```

Speaker embedding is computed once from the reference audio and reused for all segments — avoids redundant conditioning latent computation for every segment.

#### Reference Audio Requirements
- Minimum 6 seconds of clean speech
- Single speaker, no background noise
- WAV format, any sample rate (XTTS resamples internally)
- Stored at `assets/xtts_refs/<lang>.wav` for per-language defaults

#### Integration with Pipeline
Voice cloning is activated via `--voice-clone` flag in CLI or the voice clone toggle in the Gradio UI. When active, `VoiceCloner.synthesize_segments_with_clone()` replaces `TTSEngine.synthesize_segments()` in Step 4 of the pipeline.

---

### 9.10 CBP Uploader Design

**File:** `pipeline/cbp_uploader.py` | **Class:** `CBPUploader`

#### Authentication
REST API login to `https://cbp.igotkarmayogi.gov.in/api/user/v1/login` with username/password from `.env`. Bearer token stored in session headers for all subsequent requests.

#### Upload Flow
```
CBPUploader.upload_course_package(package_dir, course_id, lang)
    │
    ├── glob *_{lang}.mp4   → upload as "video"
    ├── glob *_{lang}.mp3   → upload as "audio"
    ├── glob *_{lang}*.xlsx → upload as "metadata"
    ├── glob *_{lang}*.docx → upload as "assessment"
    ├── glob *_{lang}.srt   → upload as "subtitle"
    └── glob *_{lang}.vtt   → upload as "subtitle"
```

Each file upload: `POST /api/content/v1/upload` with multipart form data (`file`, `courseId`, `language`, `assetType`). Retry logic: 3 attempts with 5s × attempt backoff on failure.

#### Submission Report
`generate_submission_report()` writes a JSON report to disk with total uploads, total errors, and per-course upload details — used for KB tender submission tracking.

---

### 9.11 LLM Post-Edit Design

**File:** `pipeline/llm_enhancer.py` | **Class:** `LLMEnhancer`

#### Provider Detection (priority order)
```
1. GROQ_API_KEY       → llama-3.3-70b-versatile (free tier)
2. GEMINI_API_KEY     → gemini-1.5-flash
3. OPENROUTER_API_KEY → meta-llama/llama-3.3-70b-instruct:free
4. None               → enhancement disabled, pipeline works fully offline
```

#### Enhancement Prompt
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

#### Batch Enhancement
`enhance_batch()` sends all segments in a single LLM call as a JSON array, reducing API latency. Response is parsed as a JSON array and matched 1-to-1 with input. Falls back to per-segment enhancement if batch parse fails.

#### Offline Guarantee
`LLMEnhancer.available` returns `False` when no API key is set. All callers check `available` before calling `enhance()`. The pipeline produces identical output with or without LLM enhancement — it is a post-processing step only, never a required dependency.

---

### 9.12 Logging & Audit Design

**File:** `pipeline/logger.py` | **Class:** `_JsonFormatter`

#### Log Files

| File | Purpose | Format | Rotation |
|------|---------|--------|---------|
| `logs/pipeline.log` | All pipeline events (DEBUG+) | JSON lines | 10MB × 5 backups |
| `logs/audit.log` | Job start/success/failure events | JSON lines | 10MB × 5 backups |

#### JSON Log Format
Every log entry is a single JSON object:
```json
{
  "ts": "2025-07-15T14:32:01",
  "level": "INFO",
  "module": "dubbing_pipeline",
  "msg": "START job=a3f2b1c4d5e6 file=course.mp4 English->Hindi"
}
```

#### Audit Events
Three structured audit events written to `audit.log` per job:

| Event | Fields |
|-------|--------|
| `job_start` | job_id, file, src, tgt, course_id, host |
| `job_success` | job_id, tgt, elapsed_s, output, quality |
| `job_failed` | job_id, tgt, elapsed_s, error |

#### Console Handler
Human-readable format `[module] message` on stdout. UTF-8 safe on Windows via `io.TextIOWrapper` with `errors='replace'`.

---

### 9.13 Checkpoint / Resume Design

**File:** `pipeline/retry.py` | **Classes:** `JobCheckpoint`, `retry`

#### JobCheckpoint

**Storage:** `checkpoints/jobs/<job_id>.json` — one file per (video, tgt_lang) pair. Job ID is `MD5(filename + tgt_lang)[:12]`.

**Data structure:**
```json
{
  "completed": {
    "0": {"id": 0, "start": 0.0, "end": 3.2, "text": "नमस्ते", "engine": "indictrans2", ...},
    "1": {"id": 1, "start": 3.2, "end": 6.8, "text": "आज हम...", ...}
  },
  "meta": {
    "segments": [...],
    "detected_src_lang": "eng",
    "duration": 1847.3
  }
}
```

**Atomic writes:** All saves use write-to-`.tmp`-then-rename pattern — partial writes never corrupt the checkpoint file.

**Thread safety:** All reads and writes protected by an instance-level `threading.Lock()`.

**Resume logic:**
```python
for each segment:
    if ckpt.is_done(seg_id):
        results[i] = ckpt.get_done(seg_id)   ← restored from disk
    else:
        pending_idxs.append(i)                ← needs translation
# Only pending segments are sent to the translation engine
```

**Flush strategy:** Single `ckpt.flush()` after the entire batch completes — not per-segment — to minimise disk I/O on fast GPUs.

**Lifecycle:**
- Created at job start
- Updated after each translation batch
- Cleared (`ckpt.clear()`) on job success
- Preserved on job failure — enables resume on next run
- Force-cleared by `--force` flag

#### retry Decorator

Exponential backoff retry for translation engine calls:
```python
@retry(max_attempts=2, delay=1.0)
def _translate_indic_trans2(self, text, src_lang, tgt_lang):
    ...
```
Wait time: `delay × 2^(attempt-1)` — attempt 1: 1.0s, attempt 2: 2.0s. Logs each failure with attempt number and wait time. Raises the last exception after all attempts exhausted.

---

*End of Section 9 — Technical Design*

---

---

## SECTION 10 — PIPELINE WORKFLOW

---

### 10.1 End-to-End Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INPUT                                                │
│         MP4 / MP3 / WAV / FLAC / OGG / MKV / AVI / MOV                │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  VALIDATION                                                             │
│  • File exists, extension in ALLOWED_EXTS, size ≤ 2GB, non-zero       │
│  • Concurrent job lock acquired (per course_id + tgt_lang)             │
│  • Previous output files wiped (fresh run every time)                  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — AUDIO EXTRACTION                                              │
│  video_processor.extract_audio() → tmp/<job_id>/source.wav (16kHz mono)│
│  Stale cache check: re-extract if video newer than cached WAV           │
│  No audio stream → generate silence matching video duration             │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 1b — S2ST FAST PATH (Indic→Indic only)                           │
│  Condition: src ∈ {hin,ben,kan,tel,urd} AND tgt ∈ {hin,ben,kan,tel,urd}│
│  translator.translate_speech_to_speech()                                │
│  SeamlessM4Tv2: source.wav → dubbed.wav (no ASR, no TTS)               │
│  ✅ Success → mux video → write output → return early                  │
│  ❌ Failure → fall through to Step 2                                   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — ASR TRANSCRIPTION                                             │
│  asr.transcribe_segments(source.wav, src_lang)                          │
│  faster-whisper large-v3 → raw segments                                 │
│  _merge_segments() → sentence-level chunks (6–12 words, 1.5–12s)       │
│  tag_segments() → per-segment language detection                        │
│  Nastaliq normalisation (urd/kas/snd)                                   │
│  _strip_hallucinations() → clean segment text                           │
│  Checkpoint: segments + detected_src_lang saved to JobCheckpoint        │
│  Exclusion check: PM/President speech or YouTube URL → SKIP job         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  [{id, start, end, text, detected_lang}]
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — TRANSLATION                                                   │
│  _translate_segments_parallel()                                         │
│                                                                         │
│  For each segment:                                                      │
│    • Empty text → passthrough (score=1.0)                              │
│    • Fully non-translatable → passthrough_nontranslatable              │
│    • Checkpoint hit → restore from disk (skip engine)                  │
│                                                                         │
│  GPU batch via translator.translate_batch():                            │
│    protect tokens → engine routing → post-process → FQC → glossary    │
│    → quality.score_segment() → quality gate (< 0.30 → text="")        │
│                                                                         │
│  Checkpoint: each result saved atomically; single flush after batch     │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  [{...seg, text, engine, quality}]
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 4 — TTS SYNTHESIS                                                 │
│  tts.synthesize_segments() OR voice_cloner.synthesize_segments_with_clone│
│                                                                         │
│  Per segment:                                                           │
│    text="" → write silence directly                                     │
│    text≠"" → Parler-TTS Large → MMS-TTS → XTTS-v2 → silence           │
│    Fixed seed per language (voice consistency)                          │
│    OOM → clear CUDA cache + retry once                                  │
│  → tmp/<job_id>/tts_segments/seg_NNNN.wav                              │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  [{...seg, audio_path}]
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 5 — AUDIO ASSEMBLY                                                │
│  video_processor.assemble_dubbed_audio()                                │
│  Place each segment at original timestamp                               │
│  Speed up max 1.35× if overruns slot (atempo filter)                   │
│  Hard-trim if still over after speed-up                                 │
│  10ms fade-in per segment (eliminates click)                            │
│  Pad with silence to match original duration                            │
│  Normalise to -1 dBFS                                                   │
│  → tmp/<job_id>/dubbed.wav                                             │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  dubbed.wav
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STEP 6 — OUTPUT GENERATION                                             │
│  subtitles.generate_subtitles() → .srt + .vtt                          │
│  video_processor.replace_audio_in_video() → .mp4                       │
│    (soft SRT embedded as mov_text subtitle track)                       │
│  Duration ratio check → warn if output > 1.20× original               │
│  _save_metadata() → _metadata.json                                     │
│  generate_qa_report() → _qa_cert.docx                                  │
│  Checkpoint cleared; tmp/ directory removed                             │
│  Audit log: job_success event written                                   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  OUTPUT: output/<course_id>/<lang>/                                     │
│    <course>_<lang>.mp4          ← dubbed video                         │
│    <course>_<lang>.srt          ← subtitles                            │
│    <course>_<lang>.vtt          ← web subtitles                        │
│    <course>_<lang>_metadata.json ← quality + transcript                │
│    <course>_<lang>_qa_cert.docx  ← QA self-certification               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 10.2 Step 1 — Audio Extraction

**Module:** `pipeline/video_processor.py` → `VideoProcessor.extract_audio()`

**Purpose:** Convert any supported input format to a 16kHz mono WAV file suitable for faster-whisper ASR.

**Process:**
1. Check if input has an audio stream (`_has_audio_stream()` via ffmpeg stderr parse)
2. If no audio stream → generate silence matching video duration via `ffmpeg anullsrc`
3. Run ffmpeg: `-ar 16000 -ac 1 -vn` → `tmp/<job_id>/source.wav`
4. On failure → re-encode input to clean MP4 (`_reencode_input()`) then retry extraction
5. Stale cache check: if `source.wav.mtime < video.mtime` → delete and re-extract

**Output:** `tmp/<job_id>/source.wav` — 16kHz, mono, PCM float32 WAV

**Duration stored:** `result.duration_original` set from `get_video_duration()` (ffprobe → ffmpeg Duration header → librosa fallback)

---

### 10.3 Step 1b — S2ST Fast Path

**Module:** `pipeline/translator.py` → `Translator.translate_speech_to_speech()`

**Purpose:** For Indic→Indic language pairs, SeamlessM4Tv2 can translate speech directly to speech without separate ASR and TTS steps, producing higher naturalness.

**Activation conditions (all must be true):**
- `src_lang != "auto"` and `src_lang != "eng"`
- `src_lang ∈ SEAMLESS_S2ST_LANGS` = `{hin, ben, kan, tel, urd}`
- `tgt_lang ∈ SEAMLESS_S2ST_LANGS` = `{hin, ben, kan, tel, urd}`

**Process:**
1. Load `source.wav` via soundfile, convert to float32, mono
2. `processor(audios=audio, sampling_rate=sr, src_lang=..., return_tensors="pt")`
3. `model.generate(**inputs, tgt_lang=..., generate_speech=True)`
4. Extract waveform tensor → `sf.write(s2st_dubbed.wav, wav, out_sr)`
5. Mux into output MP4 via `replace_audio_in_video()`
6. Return early — Steps 2–6 are skipped entirely

**On failure:** Log warning, delete stale `s2st_dubbed.wav`, fall through to Step 2 (ASR path).

**Supported pairs:** `hin↔ben`, `hin↔kan`, `hin↔tel`, `hin↔urd`, `ben↔kan`, `ben↔tel`, `ben↔urd`, `kan↔tel`, `kan↔urd`, `tel↔urd` (all bidirectional combinations of the 5 S2ST languages)

---

### 10.4 Step 2 — ASR Transcription

**Module:** `pipeline/asr.py` → `ASREngine.transcribe_segments()`

**Purpose:** Transcribe source audio into time-stamped sentence-level segments for downstream translation.

**Checkpoint resume:** If `ckpt.get_meta("segments")` is populated, ASR is skipped entirely and segments are restored from the checkpoint. This is the most expensive step — saving it prevents full re-transcription on crash.

**Process:**
1. Map `src_lang` to faster-whisper language code via `FW_LANG_CODES`
2. `model.transcribe(wav, language=fw_lang, beam_size=5, vad_filter=True, word_timestamps=True, condition_on_previous_text=False, temperature=[0.0, 0.2, 0.4])`
3. Consume generator → `raw_segs` list
4. `_merge_segments(raw_segs)` → sentence-level chunks
5. `tag_segments(merged, lang)` → per-segment language detection
6. Nastaliq normalisation for `urd/kas/snd`
7. `_strip_hallucinations()` per segment
8. Filter empty segments
9. Save to checkpoint: `ckpt.set_meta("segments", segments)`

**Language auto-detection:** When `lang="auto"`, `fw_lang=None` is passed to faster-whisper. After consuming the generator, `info.language` is mapped to internal code via `fw_lang_to_internal()`. Detected language is stored in checkpoint and used for all subsequent steps.

**Exclusion check:** After ASR, `should_skip_translation()` scans the full transcript for PM/President speech patterns and YouTube URLs. If matched, job is marked failed with exclusion reason and returns immediately.

---

### 10.5 Step 3 — Translation

**Module:** `pipeline/dubbing_pipeline.py` → `_translate_segments_parallel()` → `pipeline/translator.py` → `Translator.translate_batch()`

**Purpose:** Translate all ASR segments from source language to target language using the three-engine fallback chain.

**Segment classification (before engine call):**

| Type | Condition | Action |
|------|-----------|--------|
| Empty | `text == ""` | Passthrough, score=1.0 |
| Non-translatable | ≥ 90% URL/code/path chars | Passthrough unchanged |
| Checkpoint hit | `ckpt.is_done(seg_id)` | Restore from disk |
| Normal | All others | Send to translation engine |

**GPU batch flow:**
1. `translate_batch(texts, src_lang, tgt_lang, glossary, detected_langs)`
2. IndicTrans2 batch: all texts in single forward pass (most efficient)
3. Completeness guard: if `len(output) != len(input)` → fall back to per-segment
4. Empty translation guard: if output empty for non-empty source → retry per-segment
5. Glossary applied last: `glossary.apply()` after all cleaning

**Quality gate:** Segments with `quality.score < 0.30` have `text = ""` set — silence is written in Step 4 instead of wrong-language audio.

**Checkpoint flush:** Single `ckpt.flush()` after entire batch — not per-segment — to minimise disk I/O.

**Translation Memory integration:** `_translate_text()` checks TM before engine call. Exact matches in `govt_tm.jsonl` bypass the engine entirely.

---

### 10.6 Step 4 — TTS Synthesis

**Module:** `pipeline/tts.py` → `TTSEngine.synthesize_segments()`

**Purpose:** Convert translated text segments to WAV audio files at original timestamps.

**Per-segment flow:**

```
segment.text == "" → _write_silence(slot_duration) → seg_NNNN.wav
segment.text != "" →
    normalize_text_for_tts(text, lang, for_mms=False)
    → _synthesize_parler(text, lang, path)
        success? → seg_NNNN.wav ✓
        fail?    → _synthesize_standalone_vits(text, lang, path)  [doi only]
                   → _synthesize_mms_batch([text], lang, [path])
                      success? → seg_NNNN.wav ✓
                      fail?    → _synthesize_xtts(text, lang, path)
                                  success? → seg_NNNN.wav ✓
                                  fail?    → _write_silence(2.0s)
```

**Parler-TTS batch processing:**
- Batch size: 32 segments per GPU pass (saturates A6000 48GB)
- Description tokenizer: flan-t5-large (text encoder, not LLaMA tokenizer)
- `max_new_tokens = min(max(grapheme_count × 25, 200), 1500)`
- Fixed seed: `torch.manual_seed(_LANG_SEEDS[lang])` before every generate call
- OOM: `torch.cuda.empty_cache()` + retry once per segment

**MMS-TTS processing:**
- One segment at a time (avoids padding artifacts and Tamil underscore issue)
- Token limit: 450 tokens — segments over limit are skipped to MMS fallback
- Adapter swap: `model.load_adapter(MMS_DIR, adapter_code)` per language change

**Output:** `tmp/<job_id>/tts_segments/seg_NNNN.wav` — 44.1kHz, mono, float32

---

### 10.7 Step 5 — Audio Assembly

**Module:** `pipeline/video_processor.py` → `VideoProcessor.assemble_dubbed_audio()`

**Purpose:** Place all TTS segment WAVs at their original timestamps in a single output buffer matching the original video duration.

**Algorithm:**

```
output_buffer = zeros(original_duration × 44100)

for each segment i:
    load seg_NNNN.wav → seg_audio (resample to 44100 if needed)
    slot_samp = max(
        (next_segment.start - seg.start) × 44100,
        (seg.end - seg.start) × 44100,
        0.1s × 44100
    )
    if len(seg_audio) > slot_samp:
        ratio = min(len(seg_audio) / slot_samp, 1.35)
        seg_audio = atempo_stretch(seg_audio, ratio)   ← ffmpeg atempo
        if len(seg_audio) > slot_samp:
            seg_audio = seg_audio[:slot_samp]           ← hard trim
    fade = min(10ms × 44100, len(seg_audio) // 8)
    seg_audio[:fade] *= linspace(0.0, 1.0, fade)       ← 10ms fade-in
    start_samp = int(seg.start × 44100)
    output_buffer[start_samp : start_samp + len(seg_audio)] = seg_audio

normalise output_buffer to -1 dBFS (peak = 0.891)
sf.write(dubbed.wav, output_buffer, 44100)
```

**Fit-to-slot:** Maximum speed-up is capped at 1.35× to preserve speech intelligibility. Beyond 1.35×, audio is hard-trimmed. The 1.35× cap is a deliberate design choice — faster speech is preferable to cutting off words.

**Silence gaps:** Segments that do not fill their slot are padded with silence from the zero-initialised output buffer — no explicit silence insertion needed.

---

### 10.8 Step 6 — Output Generation

**Module:** `pipeline/dubbing_pipeline.py` → `dub_video()` Steps 6

**Purpose:** Assemble all output files, run final checks, write metadata, and clean up temporary files.

**Sub-steps in order:**

| Sub-step | Function | Output |
|----------|----------|--------|
| Subtitle generation | `generate_subtitles()` | `<course>_<lang>.srt`, `<course>_<lang>.vtt` |
| Video muxing | `replace_audio_in_video()` | `<course>_<lang>.mp4` (with soft SRT track) |
| Duration ratio check | inline in `dub_video()` | Warning logged if > 1.20× |
| Metadata save | `_save_metadata()` | `<course>_<lang>_metadata.json` |
| QA report | `generate_qa_report()` | `<course>_<lang>_qa_cert.docx` |
| Checkpoint clear | `ckpt.clear()` | `checkpoints/jobs/<job_id>.json` deleted |
| Temp cleanup | `shutil.rmtree(tmp_dir)` | `tmp/<job_id>/` deleted |
| Audit log | `audit_log.info(job_success)` | `logs/audit.log` entry |

**Duration ratio check (KB tender §5.1B):**
```
ratio = duration_output / duration_original
if ratio > 1.20:
    log WARNING: "Duration ratio X.XXx exceeds 20% threshold — KB approval required"
    quality_summary["duration_ratio_kb_approval_required"] = True
```

**Metadata JSON contents:** course_id, source_lang, target_lang, duration_original_s, duration_output_s, voice_cloned, segment_count, quality_summary, full transcript, full translations, provenance (model versions, git commit, host, timestamp, contract reference).

---

### 10.9 Multi-GPU Parallel Flow

**Module:** `pipeline/dubbing_pipeline.py` → `DubbingPipeline.dub_course_parallel()`

**Purpose:** Distribute 22 target languages across multiple GPUs to reduce total processing time linearly with GPU count.

**Architecture:** Python `multiprocessing` with `spawn` context (required for CUDA on Windows and Linux). Each worker process gets its own GPU via `PIPELINE_GPU` environment variable.

**Flow:**

```
Main Process (GPU 0)
│
├── STEP 1: Run ASR ONCE
│   extract_audio() → _asr_shared/source.wav
│   transcribe_segments() → segments
│   Write _asr_shared/asr_cache.json
│         {segments, src_lang, duration}
│
├── STEP 2: Distribute languages across GPUs
│   22 langs → round-robin across num_gpus
│   GPU 0: [hin, kan, ory, mni, kas, ...]
│   GPU 1: [ben, mal, bod, mai, kok, ...]
│   GPU 2: [tam, mar, doi, nep, snd, ...]
│   GPU 3: [tel, guj, pan, asm, sat, urd]
│
└── STEP 3: Spawn worker processes
    multiprocessing.Pool(processes=num_gpus)
    pool.map(_worker_dub_langs, worker_args)
    │
    ├── Worker 0 (GPU 0): os.environ["PIPELINE_GPU"]="0"
    │   Pre-seed ASR cache into each lang's checkpoint
    │   For each lang: dub_video() → translate+TTS+assemble
    │
    ├── Worker 1 (GPU 1): os.environ["PIPELINE_GPU"]="1"
    │   ...
    │
    └── Worker N (GPU N): ...

Main Process: merge results, clean up _asr_shared/
```

**ASR cache sharing:** Each worker reads `asr_cache.json` and pre-seeds the ASR segments into each language's `JobCheckpoint` before calling `dub_video()`. This means `dub_video()` finds `ckpt.get_meta("segments")` already populated and skips ASR entirely — ASR runs exactly once regardless of GPU count.

**Performance:** With 4× GPUs, total time ≈ single-GPU time / 4 (plus ~5% overhead for spawn + ASR). For 22 languages on a 4-GPU server, total processing time per course ≈ 35–90 minutes depending on video length.

---

### 10.10 Document Translation Flow

**Module:** `pipeline/doc_extractor.py` → `translate_docx()` | `pipeline/dubbing_pipeline.py` → `translate_metadata()`, `translate_quiz()`

**Purpose:** Translate course quiz (DOCX/JSON), metadata (JSON), and plain text documents alongside video dubbing.

**DOCX Translation Flow:**

```
Input: source.docx
│
├── Document(src_path)                    ← python-docx load
│
├── For each paragraph in doc.paragraphs:
│   full_text = "".join(run.text for run in para.runs)
│   translated = translate_fn([full_text], src_lang, tgt_lang)[0]
│   runs[0].text = translated             ← put result in first run
│   runs[1:].text = ""                   ← clear remaining runs
│   (preserves bold/italic boundaries)
│
├── For each table → each cell → each paragraph:
│   same paragraph translation logic
│
├── For each section header/footer (6 variants):
│   same paragraph translation logic
│
└── doc.save(out_path)                    ← write translated DOCX
```

**Quiz Translation Flow (JSON → DOCX + XLSX):**

```
quiz = [{question, options[], answer}, ...]
│
├── For each item:
│   translate question, each option, answer
│   → translated_quiz[]
│
├── export_quiz_docx() → Word document with Q&A formatting
└── export_quiz_xlsx() → Excel with columns: Q#, Question, A, B, C, D, Answer
```

**Metadata Translation Flow:**

```
metadata = {title, description, learning_outcome, keywords, module_titles, ...}
│
├── TM lookup first (exact match bypasses engine)
├── translate each string field
├── translate each list field element
└── export_metadata_docx() → Word table (Field | Original | Translated)
    export_metadata_xlsx() → Excel sheet per language
```

**translate_fn used:** `Translator.translate_document_batch()` — bypasses all placeholder protection layers (format/NT/factual token protection) which cause hallucination on document-length paragraphs. Only `_clean_unk()` applied to output.

---

### 10.11 Voice Cloning Flow

**Module:** `pipeline/voice_clone.py` → `VoiceCloner.synthesize_segments_with_clone()`

**Purpose:** Replace standard TTS synthesis (Step 4) with voice-cloned synthesis that matches the original speaker's voice characteristics.

**Activation:** `--voice-clone` flag in CLI or voice clone toggle in Gradio UI. Reference audio provided via `--reference-audio speaker.wav`.

**Flow:**

```
Input: translated_segments[], lang, reference_audio.wav
│
├── ONCE: extract_speaker_embedding(reference_audio)
│   model.get_conditioning_latents([reference_audio])
│   → {gpt_cond_latent, speaker_embedding}
│
├── For each segment:
│   synthesize_with_clone(
│       text=seg.text,
│       lang=lang,
│       reference_audio=reference_audio,
│       output_path=seg_NNNN.wav,
│       speaker_embedding=embedding    ← reuse pre-computed
│   )
│   │
│   ├── xtts_lang = XTTS_LANG_MAP[lang]   (e.g. "hin" → "hi")
│   └── model.inference(
│           text, language=xtts_lang,
│           gpt_cond_latent, speaker_embedding
│       )
│       → sf.write(seg_NNNN.wav, wav, 24000)
│
└── return [{...seg, audio_path}]
    (same format as TTSEngine.synthesize_segments output)
    → feeds directly into Step 5 (Audio Assembly)
```

**Supported languages:** `hin ben guj mar tam tel kan mal pan urd` (10 languages via XTTS-v2 native support)

**Unsupported languages:** For languages not in `XTTS_LANG_MAP`, `VoiceCloner.is_supported(lang)` returns `False` and the pipeline falls back to standard `TTSEngine.synthesize_segments()` automatically.

**Reference audio quality:** Minimum 6 seconds of clean single-speaker audio. Longer reference (15–30 seconds) produces better voice similarity. Background noise significantly degrades cloning quality.

---

*End of Section 10 — Pipeline Workflow*

---

---

## 11. Language & Model Configuration

This section documents the complete language code mapping, translation engine routing logic, TTS engine assignment, and script-to-engine relationships for all 22 scheduled Indian languages supported by the system.

---

### 11.1 All 22 Supported Languages

The system covers all 22 languages listed in the Eighth Schedule of the Constitution of India, as mandated by the KB tender. Languages are grouped into KB-11 (mandatory) and KB-11 Extended (additional).

| # | Code | Language   | Script      | Category     |
|---|------|------------|-------------|--------------|
| 1 | hin  | Hindi      | Devanagari  | KB-11 Core   |
| 2 | ben  | Bengali    | Bengali     | KB-11 Core   |
| 3 | tam  | Tamil      | Tamil       | KB-11 Core   |
| 4 | tel  | Telugu     | Telugu      | KB-11 Core   |
| 5 | kan  | Kannada    | Kannada     | KB-11 Core   |
| 6 | mal  | Malayalam  | Malayalam   | KB-11 Core   |
| 7 | mar  | Marathi    | Devanagari  | KB-11 Core   |
| 8 | guj  | Gujarati   | Gujarati    | KB-11 Core   |
| 9 | pan  | Punjabi    | Gurmukhi    | KB-11 Core   |
|10 | ory  | Odia       | Odia        | KB-11 Core   |
|11 | asm  | Assamese   | Bengali     | KB-11 Core   |
|12 | urd  | Urdu       | Arabic      | KB-11 Extended |
|13 | nep  | Nepali     | Devanagari  | KB-11 Extended |
|14 | mai  | Maithili   | Devanagari  | KB-11 Extended |
|15 | doi  | Dogri      | Devanagari  | KB-11 Extended |
|16 | bod  | Bodo       | Devanagari  | KB-11 Extended |
|17 | mni  | Manipuri   | Bengali     | KB-11 Extended |
|18 | san  | Sanskrit   | Devanagari  | KB-11 Extended |
|19 | sat  | Santhali   | Ol Chiki    | KB-11 Extended |
|20 | kok  | Konkani    | Devanagari  | KB-11 Extended |
|21 | snd  | Sindhi     | Arabic      | KB-11 Extended |
|22 | kas  | Kashmiri   | Arabic      | KB-11 Extended |

---

### 11.2 Language Code Mapping Table

Each language carries four distinct codes — one per engine — maintained in `pipeline/lang_config.py` as the single source of truth.

| Code | Language   | IndicTrans2 (flores200) | SeamlessM4T | NLLB-200     | Whisper |
|------|------------|-------------------------|-------------|--------------|---------|
| asm  | Assamese   | asm_Beng                | asm         | asm_Beng     | as      |
| ben  | Bengali    | ben_Beng                | ben         | ben_Beng     | bn      |
| guj  | Gujarati   | guj_Gujr                | guj         | guj_Gujr     | gu      |
| hin  | Hindi      | hin_Deva                | hin         | hin_Deva     | hi      |
| kan  | Kannada    | kan_Knda                | kan         | kan_Knda     | kn      |
| mal  | Malayalam  | mal_Mlym                | mal         | mal_Mlym     | ml      |
| mar  | Marathi    | mar_Deva                | mar         | mar_Deva     | mr      |
| ory  | Odia       | ory_Orya                | ory         | ory_Orya     | or      |
| pan  | Punjabi    | pan_Guru                | pan         | pan_Guru     | pa      |
| tam  | Tamil      | tam_Taml                | tam         | tam_Taml     | ta      |
| tel  | Telugu     | tel_Telu                | tel         | tel_Telu     | te      |
| urd  | Urdu       | urd_Arab                | urd         | urd_Arab     | ur      |
| nep  | Nepali     | npi_Deva                | npi         | npi_Deva     | ne      |
| mai  | Maithili   | mai_Deva                | mai         | mai_Deva     | mai     |
| doi  | Dogri      | doi_Deva                | doi         | doi_Deva     | doi     |
| bod  | Bodo       | brx_Deva                | brx         | brx_Deva     | bo      |
| mni  | Manipuri   | mni_Beng                | mni         | mni_Beng     | mni     |
| san  | Sanskrit   | san_Deva                | —           | san_Deva     | sa      |
| sat  | Santhali   | sat_Olck                | sat         | sat_Olck     | sat     |
| kok  | Konkani    | gom_Deva                | —           | kok_Deva     | kok     |
| snd  | Sindhi     | snd_Arab                | snd         | snd_Arab     | sd      |
| kas  | Kashmiri   | kas_Arab                | —           | kas_Arab     | ks      |

Notes:
- `bod` maps to `brx_Deva` (Bodo/Boro in Devanagari) across all engines — NOT `bod_Tibt` (Tibetan), which is a different language entirely.
- `kok` maps to `gom_Deva` in IndicTrans2 (Goan Konkani, flores200 standard) and `kok_Deva` in NLLB-200.
- `nep` maps to `npi_Deva` in IndicTrans2 and NLLB-200 (flores200 uses `npi` for Nepali).
- SeamlessM4T does not support `san`, `kok`, `kas` for text translation.

---

### 11.3 Translation Engine Routing Table

The translation engine is selected per language based on model coverage and quality benchmarks. A three-level fallback chain ensures no language is left without a translation path.

| Language Group | Languages | Primary Engine | Fallback 1 | Fallback 2 |
|----------------|-----------|----------------|------------|------------|
| Mainstream Indic | hin, ben, tam, tel, kan, mal, mar, guj, pan, ory, asm, urd, nep, mai | IndicTrans2 (fine-tuned) | SeamlessM4T | NLLB-200 |
| Hindi-pivot langs | mni, sat, san | IndicTrans2 via Hindi pivot | NLLB-200 | — |
| NLLB-primary langs | kok, snd, kas | NLLB-200 | — | — |
| Seamless-first langs | bod, doi | SeamlessM4T | IndicTrans2 | NLLB-200 |

Routing logic in `pipeline/translator.py`:

```
if lang in {kok, snd, kas}:
    → NLLB-200 directly (IndicTrans2 coverage insufficient)

elif lang in {bod, doi}:
    → SeamlessM4T first (better Bodo/Dogri quality)
    → fallback: IndicTrans2 → NLLB-200

elif lang in {mni, sat, san}:
    → IndicTrans2 via eng→hin→tgt pivot
    → fallback: NLLB-200

else:  # all 14 mainstream langs
    → IndicTrans2 fine-tuned checkpoint
    → fallback: SeamlessM4T → NLLB-200
```

Fine-tuned checkpoints at `checkpoints/indictrans/en_indic/best/` are used automatically when present; the pipeline falls back to base model weights at `models/indic_tr/` if absent.

---

### 11.4 TTS Engine Routing Table

Text-to-Speech synthesis follows a four-level fallback chain. The primary engine (Parler-TTS Indic Large) handles all 22 languages from a single model load, eliminating per-language adapter swaps.

| Engine | Model | Languages | Priority | Notes |
|--------|-------|-----------|----------|-------|
| Parler-TTS Indic Large | `models/indic_parler_tts_large/` | All 22 | 1 — Primary | 44kHz, GPU batch, fixed seed per lang |
| Parler-TTS Indic Mini | `models/indic_parler_tts/` | All 22 | 2 — Fallback | Used if large model absent |
| MMS-TTS | `models/mms/` | All 22 via adapters | 3 — Fallback | Shared VITS base + per-lang adapter swap |
| Coqui XTTS-v2 | HuggingFace / local | hin, ben, guj, mar, tam, tel, kan, mal, pan, urd | 4 — Last resort / Voice clone | Apache 2.0, also used for `--voice-clone` |

Script-based Parler skip rule: `sat`, `kas`, `snd` use non-Latin/non-Devanagari scripts (Ol Chiki, Arabic) that Parler-TTS cannot render. These three languages skip directly to MMS-TTS.

Fixed seed assignment ensures voice consistency across segments and re-runs. Each language is assigned a deterministic seed in `_LANG_SEEDS` within `pipeline/tts.py`, so the same speaker voice is reproduced for every segment of a given language.

---

### 11.5 S2ST Supported Language Pairs

Speech-to-Speech Translation (S2ST) via SeamlessM4Tv2 provides a fast path that bypasses ASR → Translation → TTS entirely. It is restricted to Indic→Indic pairs where SeamlessM4T supports speech synthesis output.

Supported S2ST languages (5 of 22):

| Code | Language | SeamlessM4T S2ST Code |
|------|----------|-----------------------|
| ben  | Bengali  | ben                   |
| hin  | Hindi    | hin                   |
| kan  | Kannada  | kan                   |
| tel  | Telugu   | tel                   |
| urd  | Urdu     | urd                   |

S2ST activation conditions (all must be true):
1. Source language is in `SEAMLESS_S2ST_LANGS` (one of the 5 above)
2. Target language is in `SEAMLESS_S2ST_LANGS`
3. Source ≠ Target
4. English source (`eng`) always uses the full ASR → Translation → TTS pipeline regardless

Languages excluded from S2ST (17 of 22): tam, mal, ory, pan, guj, asm, mai, snd, kok, kas, mni, san, sat, doi, bod, nep, mar — SeamlessM4Tv2 does not support speech synthesis output for these languages.

S2ST fast path flow:

```
[S2ST Fast Path — Indic→Indic only]

Source WAV (16kHz mono)
        │
        ▼
SeamlessM4Tv2.predict(task="S2ST", src_lang=X, tgt_lang=Y)
        │
        ├─ Success → dubbed.wav → mux → return early (skip Steps 2–5)
        │
        └─ Failure → fall through to full ASR→Translate→TTS pipeline
```

---

### 11.6 Script-to-Engine Mapping

The 22 languages span 9 distinct writing scripts. Script identity determines engine compatibility and special handling rules.

| Script | Languages | IndicTrans2 | SeamlessM4T | NLLB-200 | Parler-TTS | Special Handling |
|--------|-----------|-------------|-------------|----------|------------|-----------------|
| Devanagari | hin, mar, nep, mai, doi, bod, kok, san | ✓ | ✓ (most) | ✓ | ✓ | Nastaliq normalisation N/A |
| Bengali | ben, asm, mni | ✓ | ✓ | ✓ | ✓ | — |
| Tamil | tam | ✓ | ✓ | ✓ | ✓ | — |
| Telugu | tel | ✓ | ✓ | ✓ | ✓ | — |
| Kannada | kan | ✓ | ✓ | ✓ | ✓ | — |
| Malayalam | mal | ✓ | ✓ | ✓ | ✓ | — |
| Gujarati | guj | ✓ | ✓ | ✓ | ✓ | — |
| Gurmukhi | pan | ✓ | ✓ | ✓ | ✓ | — |
| Odia | ory | ✓ | ✓ | ✓ | ✓ | — |
| Arabic | urd, kas, snd | ✓ | ✓ (urd, snd) | ✓ | ✗ → MMS | Nastaliq normalisation applied post-ASR |
| Ol Chiki | sat | ✓ | ✓ | ✓ | ✗ → MMS | Rare script; Parler cannot render |

Nastaliq normalisation: ASR output for `urd`, `kas`, `snd` is passed through a Unicode normalisation step in `pipeline/asr.py` before translation. Arabic-script characters are standardised to their canonical Nastaliq forms to prevent encoding mismatches in downstream engines.

---

### 11.7 Fine-Tuned vs. Base Model Selection

The pipeline automatically selects fine-tuned checkpoints over base model weights at runtime.

```
Checkpoint resolution order (pipeline/translator.py):

1. checkpoints/indictrans/en_indic/best/    ← fine-tuned English → Indic
2. checkpoints/indictrans/indic_en/best/    ← fine-tuned Indic → English
3. checkpoints/indictrans/indic_indic/best/ ← fine-tuned Indic → Indic
4. models/indic_tr/en_indic/               ← base model fallback
5. models/indic_tr/indic_en/               ← base model fallback
6. models/indic_tr/indic_indic/            ← base model fallback
```

Fine-tuning is performed using `finetune/finetune_indictrans.py` with DeepSpeed ZeRO-3 (`finetune/ds_zero3.json`) for multi-GPU training on parallel corpora stored in `datasets/parallel/<lang_code>/train.jsonl`.


---

## 12. ASR, Translation & TTS — Module Deep Dive

This section documents the internal design of the three core inference modules: ASR (`pipeline/asr.py`), Translation (`pipeline/translator.py`), and TTS (`pipeline/tts.py`). Each module is described in terms of its architecture, key algorithms, and production-hardening measures.

---

### 12.1 ASR Module — `pipeline/asr.py`

#### 12.1.1 Engine Selection

The ASR engine is faster-whisper large-v3, a CTranslate2-optimised port of OpenAI Whisper large-v3. A single model load handles all 22 Indian languages natively — no per-language adapter swaps, no separate model files per language.

Model resolution order at startup:

```
1. models/indic_asr/model.bin                          ← local CT2 weights (preferred)
2. models/indic_asr/models--Systran--faster-whisper-large-v3/snapshots/<hash>/
                                                        ← HF cache snapshot
3. "large-v3"                                          ← auto-download from HuggingFace
```

Compute type: `float16` on CUDA, `int8` on CPU. Worker threads: 1 (Windows `fork` restriction — >1 deadlocks).

#### 12.1.2 Transcription Parameters

```python
model.transcribe(
    wav,
    language=fw_lang,                    # None = auto-detect
    beam_size=5,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 500},
    word_timestamps=True,
    condition_on_previous_text=False,    # hallucination guard
    temperature=[0.0, 0.2, 0.4],        # multi-temp fallback
    no_speech_threshold=0.6,
    log_prob_threshold=-1.0,
    compression_ratio_threshold=2.4,
)
```

Key hardening decisions:
- `condition_on_previous_text=False` — prevents Whisper from conditioning on its own prior output, which causes repetition loops on low-quality audio.
- `temperature=[0.0, 0.2, 0.4]` — if beam search at temperature 0.0 produces a high compression ratio (repetition), Whisper automatically retries at 0.2, then 0.4.
- `vad_filter=True` — Voice Activity Detection pre-filters silence, reducing hallucination on silent segments.

#### 12.1.3 Language Auto-Detection

When `lang="auto"` is passed, `fw_lang=None` is sent to faster-whisper. The model detects the spoken language from the first 30 seconds of audio and returns `info.language` (ISO 639-1 code) and `info.language_probability`. The detected code is mapped to the internal pipeline code via `fw_lang_to_internal()` in `pipeline/lang_detect.py`.

#### 12.1.4 Segment Merging — `_merge_segments()`

faster-whisper returns short phrase-level segments (often 1–3 words). These are merged into natural sentence-length chunks before translation:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| min_words | 6 | Prevents single-word segments reaching TTS |
| min_dur | 1.5 s | Avoids sub-second audio slots |
| max_dur | 12.0 s | Prevents over-long segments that exceed TTS token limits |
| Split trigger | `.`, `!`, `?`, `。` | Always split on sentence-ending punctuation |

Merge logic: accumulate segments into a buffer; flush when (sentence-ending punctuation AND ≥6 words AND ≥1.5s) OR duration ≥12s.

#### 12.1.5 Hallucination Stripping — `_strip_hallucinations()`

Whisper large-v3 produces known hallucination words at segment boundaries when audio is unclear (e.g. "Wanner", "Viengore", "Guinevere"). A regex pattern matches these at sentence-initial position and strips them, then re-capitalises the first letter.

#### 12.1.6 Nastaliq Normalisation

For `urd`, `kas`, `snd` (Arabic-script languages), ASR output is passed through `_normalize_nastaliq()` which applies a character-level substitution map:

| Arabic form | Urdu/Nastaliq form | Issue |
|-------------|-------------------|-------|
| ك (Arabic kaf) | ک (Urdu kaf) | Different Unicode codepoints, same glyph |
| ي (Arabic ya) | ی (Urdu ya) | Encoding mismatch in downstream engines |
| ة (ta marbuta) | ت (ta) | Not used in Urdu; causes tokeniser errors |
| ى (alef maqsura) | ی (ya) | Ambiguous in Urdu context |

---

### 12.2 Translation Module — `pipeline/translator.py`

#### 12.2.1 Three-Layer Token Protection

Before any text is sent to a translation engine, three sequential protection layers are applied. Each layer replaces tokens with ASCII placeholders that survive translation unchanged.

```
Input text
    │
    ▼
Layer 1: _protect_format_tokens()
    Replaces: {name}, %s, ${var}, {{jinja}}, <PLACEHOLDER>
    Placeholders: __FMT0__, __FMT1__, …
    │
    ▼
Layer 2: _protect_nontranslatable()
    Replaces: URLs, file paths, shell commands, @mentions, #hashtags,
              email addresses, code identifiers, file extensions
    Placeholders: __NT0__, __NT1__, …
    │
    ▼
Layer 3: _protect_factual_tokens()
    Replaces: numbers, dates, times, currency, measurements, percentages
    Placeholders: __F0__, __F1__, …
    │
    ▼
Translation engine (sees only protected text)
    │
    ▼
Restore in reverse order: factual → non-translatable → format
    │
    ▼
_verify_factual_tokens(): append any missing factual tokens at end
```

Fully non-translatable segments (≥90% of non-space characters are non-translatable tokens) bypass all engines and are returned unchanged via `passthrough_nontranslatable`.

#### 12.2.2 IndicTrans2 Batch Translation

IndicTrans2 is loaded lazily per direction (`en_indic`, `indic_en`, `indic_indic`). The direction is determined from the flores200 source/target codes:

```
src == eng_Latn → en_indic
tgt == eng_Latn → indic_en
else            → indic_indic
```

Generation parameters:
- `num_beams=5`, `no_repeat_ngram_size=3`
- `repetition_penalty=1.1` for short segments (avg length <40 chars), `1.2` for longer
- `max_new_tokens=512`, `length_penalty=1.0`, `early_stopping=True`
- `torch.float16` on CUDA, `torch.float32` on CPU

Batch completeness guard: if `len(translated_list) != len(texts)`, a `RuntimeError` is raised and the batch falls back to per-segment translation. Empty translations for non-empty source segments are individually retried before being silenced.

#### 12.2.3 Hindi Pivot for Low-Resource Languages

`mni` (Manipuri) and `sat` (Santhali) are routed through a two-hop translation:

```
src → hin (IndicTrans2 en_indic or indic_indic)
hin → tgt (IndicTrans2 indic_indic)
```

This is used because direct `eng→mni` and `eng→sat` coverage in IndicTrans2 is unreliable. Hindi acts as a high-resource pivot language with strong coverage in both directions.

#### 12.2.4 Post-Translation Cleaning Pipeline

After engine output is received, the following cleaning steps are applied in order:

| Step | Function | Purpose |
|------|----------|---------|
| 1 | `_clean_unk()` | Remove `<unk>`, `[unk]`, `(unk)` tokens |
| 2 | `_clean_mixed_lang()` | Strip HTML tags; remove foreign-script word runs |
| 3 | `_restore_nontranslatable()` | Restore `__NT__` placeholders |
| 4 | `_restore_factual_tokens()` | Restore `__F__` placeholders |
| 5 | `_verify_factual_tokens()` | Append any missing factual tokens |
| 6 | `_restore_format_tokens()` | Restore `__FMT__` placeholders |
| 7 | `_naturalise()` | Fix repeated words, space-before-punct, multi-punct |
| 8 | `_final_quality_check()` | 10-rule FQC gate (see §12.2.5) |
| 9 | `glossary.apply()` | Glossary injection (applied last, never overwritten) |

#### 12.2.5 Final Quality Check — 10 Rules

`_final_quality_check()` is the last gate before a translation is returned. It auto-corrects where possible and appends flags to the quality score for human review.

| Rule | Check | Auto-correction |
|------|-------|----------------|
| 1 | Non-empty output for non-empty source | Return source text as last resort |
| 2 | Length ≥20% of source (completeness) | Flag `fqc:suspiciously_short` |
| 3 | Sentence-initial capitalisation (Latin targets) | Auto-capitalise after `. ` |
| 4 | No 3+ repeated identical punctuation | Collapse to single |
| 5 | All `__FMT__` placeholders restored | Force-restore remaining |
| 6 | No Unicode replacement char U+FFFD, no null bytes | Strip |
| 7 | No stray `__NT__`/`__F__`/`__FMT__` artifacts | Strip via regex |
| 8 | Mixed-language clean (pass 2) | (skipped — technical terms kept) |
| 9 | Normalise whitespace | Collapse multiple spaces, strip |
| 10 | Strip internal debug tokens `[UNK]`, `[PAD]`, `[BOS]`, `[EOS]`, `[MASK]` | Strip |

#### 12.2.6 Foreign-Script Stripping

`_clean_mixed_lang()` uses pre-built per-language regex patterns (`_FOREIGN_WORD_RE`) to strip entire word runs written in a script that does not belong to the target language. Patterns are compiled once at import time for all 22 languages.

Script ranges are defined in `_SCRIPT_RANGES` (22 entries) and `_ALWAYS_ALLOWED` (shared punctuation, digits, currency). For each target language, the regex matches contiguous runs of characters from any foreign script block (Latin, Cyrillic, CJK, Arabic, Devanagari, etc.) that are not in the target's allowed set.

---

### 12.3 TTS Module — `pipeline/tts.py`

#### 12.3.1 Four-Engine Fallback Chain

```
synthesize(text, lang, output_path)
    │
    ├─ 1. Parler-TTS Large (primary)
    │      skip if lang ∈ {sat, kas, snd}
    │      skip if model dir absent
    │      fail if output < 0.5s or peak < 0.02
    │
    ├─ 2. Standalone VITS (doi → dgo model, san → san model)
    │      only for langs in _MMS_STANDALONE_LANGS
    │
    ├─ 3. MMS-TTS (shared VITS base + per-lang adapter)
    │      skip if adapter file absent
    │      reject if input > 450 tokens (prevents repetition loop)
    │
    ├─ 4. Coqui XTTS-v2 (last resort)
    │      uses per-lang reference WAV from assets/xtts_refs/
    │      falls back to generic_indic.wav if per-lang absent
    │
    └─ Silence (2.0s) — written if all engines fail
```

#### 12.3.2 Parler-TTS — Voice Consistency via Fixed Seeds

Each language is assigned a deterministic seed in `_LANG_SEEDS`. Before every `model.generate()` call, `torch.manual_seed(seed)` and `torch.cuda.manual_seed_all(seed)` are set. This ensures the same speaker voice character is reproduced across all segments of a given language, even across separate runs.

| Language | Seed | Language | Seed |
|----------|------|----------|------|
| hin | 42 | asm | 52 |
| ben | 43 | urd | 53 |
| tam | 44 | nep | 54 |
| tel | 45 | bod | 55 |
| kan | 46 | doi | 56 |
| mal | 47 | kok | 57 |
| mar | 48 | mni | 58 |
| guj | 49 | mai | 59 |
| pan | 50 | san | 60 |
| ory | 51 | sat | 61 |
| — | — | snd | 62 |
| — | — | kas | 63 |

#### 12.3.3 Dynamic Token Budget — `_calc_max_tokens()`

Parler-TTS uses a codec with ~86 tokens/second. Indic akshars (syllabic units) average ~0.28 seconds each, giving ~24 tokens per akshar. The token budget is computed per segment:

```
graphemes = count of base letters + digits (NFC-normalised, combining marks excluded)
max_tokens = clamp(graphemes × 25, min=200, max=1500)
```

This prevents both truncation (too few tokens) and runaway generation (too many tokens on short segments).

#### 12.3.4 OOM Handling

Parler synthesis catches `RuntimeError` with "out of memory" in the message. On first OOM, `torch.cuda.empty_cache()` is called and the segment is retried once. On second failure, the segment falls through to MMS-TTS.

#### 12.3.5 Audio Post-Processing — `_post_process()`

All TTS output passes through `_post_process()` before being written to disk:

1. High-pass filter (Butterworth 2nd order, 80 Hz cutoff) — removes DC offset and low-frequency rumble.
2. Low-pass filter (12 kHz cutoff, MMS only) — MMS-TTS produces artefacts above 12 kHz; Parler/XTTS are not filtered.
3. Optional pitch shift (+5 semitones via librosa) — available but not enabled by default; used for female voice preference.
4. Peak normalisation to −1 dBFS (target peak = 0.891) — ensures consistent loudness across all segments and engines.

#### 12.3.6 MMS-TTS Adapter Swap

MMS-TTS uses a single shared VITS base model with per-language adapters. The adapter is swapped via `model.load_adapter(path, adapter_code)` (transformers ≥4.40). For older transformers, a manual safetensors/bin load with state-dict key matching is used as fallback.

Adapter codes for all 22 languages are defined in `MMS_LANG_CODES`. Languages without a dedicated adapter use the closest phonetic/script match:
- `kas` → `urd-script_arabic` (same Arabic script)
- `kok` → `mar` (same Devanagari script, closely related)
- `mni` → `ben` (same Bengali script)

MMS hard token limit: 450 tokens. Segments exceeding this are rejected (not truncated) to prevent the VITS repetition loop that produces minutes of repeated audio.

#### 12.3.7 Ol Chiki Transliteration for `sat`

Santhali (sat) uses the Ol Chiki script. Parler-TTS cannot render Ol Chiki and produces silence. Before sending to Parler, `_normalize_text_for_tts(text, lang="sat", for_mms=False)` transliterates each Ol Chiki character to its approximate Devanagari equivalent via `_OL_CHIKI_TO_DEVA`. MMS-TTS with the `sat` adapter handles Ol Chiki natively, so `for_mms=True` skips transliteration.


---

## 13. Quality Scoring & Gates

This section documents the automated quality assurance system implemented in `pipeline/quality.py` and enforced throughout `pipeline/dubbing_pipeline.py`. Every translated segment is scored before TTS synthesis; segments that fail the quality gate are silenced rather than sent to TTS with wrong-language audio.

---

### 13.1 Scoring Architecture

Quality scoring operates at three levels of depth:

| Function | Depth | When Used |
|----------|-------|-----------|
| `score_segment()` | Heuristic + ChrF | Every segment, inline during translation batch |
| `score_segment_full()` | Heuristic + ChrF + back-translation | QA certificate generation |
| `score_batch()` | Calls either of the above per segment | Batch scoring utility |
| `review_summary()` | Aggregates a list of scores | Pipeline quality summary, QA report |

---

### 13.2 Heuristic Scorer — `score_segment()`

The heuristic scorer applies 8 independent checks. Each check deducts a fixed penalty from a starting score of 1.0. Checks are cumulative — a segment can fail multiple checks simultaneously.

| # | Check | Condition | Penalty |
|---|-------|-----------|---------|
| 1 | Length ratio | `tgt_words / src_words < 0.3` or `> 4.0` | −0.25 |
| 2 | Source language leakage | Target-script chars < 50% of all alpha chars (non-Latin target) | −0.30 |
| 3 | Repetition loop | 4+ consecutive identical words | −0.35 |
| 4a | Untranslated (exact copy) | `translation == source` and `tgt_lang != eng` | −0.40 |
| 4b | Untranslated (Latin output) | >80% Latin chars in output for non-Latin target | −0.35 |
| 5 | Too short | Source ≥5 words but translation <2 words | −0.30 |
| 6 | Transliteration detected | Latin chars >60% of all alpha chars in translation | −0.35 |
| 7 | Missing factual tokens | Numbers/dates in source absent from translation | −0.20 |
| 8 | ChrF | Only computed for same-script pairs (e.g. eng→eng) | (informational) |

Final score: `max(0.0, 1.0 − sum_of_penalties)`, rounded to 3 decimal places.

---

### 13.3 Transliteration Detection — `detect_transliteration()`

KB tender Section 3.2 explicitly prohibits mere transliteration (writing source-language words in the target script phonetically). The detector counts native-script characters vs Latin characters in the translation output:

```
latin_ratio = latin_chars / (native_chars + latin_chars)
if latin_ratio > 0.60 → transliteration_detected → penalty −0.35
```

Script ranges are defined per language (e.g. Devanagari U+0900–U+097F for hin/mar/nep/mai/san/doi/kok/bod). The check is skipped for English targets and for segments with fewer than 5 alphabetic characters.

---

### 13.4 ChrF Score — `chrf_score()`

Character n-gram F-score (ChrF) is computed using character n-grams of order 1–6 with β=2 (recall-weighted, standard for MT evaluation):

```
For each n in 1..6:
    precision_n = matching_ngrams / hypothesis_ngrams
    recall_n    = matching_ngrams / reference_ngrams

P = mean(precision_n for n in 1..6)
R = mean(recall_n    for n in 1..6)

ChrF = (1 + β²) × P × R / (β² × P + R)
```

ChrF is only meaningful when comparing two texts in the same script. For cross-script pairs (e.g. English source vs Hindi translation), ChrF is set to 0.0 and is informational only. ChrF is used as a secondary signal in the QA certificate — it does not affect the primary heuristic score used for the quality gate.

---

### 13.5 Back-Translation Score — `back_translation_score()`

Back-translation provides a reference-free quality estimate:

```
1. Translate: translation → src_lang (using existing Translator instance)
2. Compute word overlap: |src_words ∩ back_words| / |src_words|
3. Returns 0.0–1.0, or −1.0 on failure
```

A shared translator singleton (`_bt_translator`) is injected via `set_shared_translator()` so back-translation reuses the already-loaded model rather than loading a second instance into GPU memory.

Back-translation penalty: if overlap < 0.25, score −0.15 and flag `low_back_translation_<value>`. Back-translation is only run during `score_segment_full()` (QA certificate generation) — it is not run inline during the translation batch to avoid doubling GPU time.

---

### 13.6 Quality Thresholds & Gate Actions

| Score Range | Status | Action |
|-------------|--------|--------|
| ≥ 0.55 | ✅ Pass | Accepted — sent to TTS |
| 0.30 – 0.55 | ⚠️ Review | Flagged `needs_review=True` — sent to TTS, human review recommended |
| < 0.30 | ❌ Failed | `failed=True` — text set to `""` — silence written instead of TTS |

The quality gate is enforced in `dubbing_pipeline.py` after Step 3 (translation):

```python
translated_segments = [
    {**s, "text": ""} if s.get("quality", {}).get("failed") else s
    for s in translated_segments
]
```

Setting `text=""` causes the TTS engine to write a silence WAV of the original segment duration. This ensures no wrong-language audio ever reaches the final dubbed video — a critical requirement for the KB tender.

---

### 13.7 Batch Quality Summary — `review_summary()`

After all segments are translated, `review_summary()` aggregates the per-segment scores into a pipeline-level summary stored in `DubbingResult.quality_summary` and written to the metadata JSON:

| Field | Description |
|-------|-------------|
| `total` | Total segment count |
| `avg_score` | Mean heuristic score across all segments |
| `avg_chrf` | Mean ChrF score |
| `avg_back_translation` | Mean back-translation overlap (if available) |
| `needs_review` | Count of segments with `needs_review=True` |
| `failed` | Count of segments with `failed=True` (silenced) |
| `pass_rate` | `(total − needs_review) / total` |
| `duration_ratio` | `output_duration / original_duration` |
| `duration_ratio_flag` | `True` if ratio > 1.20 (KB tender §5.1B) |
| `duration_ratio_kb_approval_required` | `True` if KB approval needed before payment |

---

### 13.8 Duration Ratio Check — KB Tender §5.1B

After the dubbed video is assembled, the pipeline checks whether the output duration exceeds the original by more than 20%:

```
ratio = duration_output / duration_original
if ratio > 1.20:
    → log WARNING
    → quality_summary["duration_ratio_kb_approval_required"] = True
```

This check is mandated by KB tender Section 5.1B. If the dubbed output is more than 20% longer than the original, KB approval is required before the submission can be accepted for payment. The ratio is always recorded in the metadata JSON regardless of whether it exceeds the threshold.

The fit-to-slot mechanism in `video_processor.py` (max 1.35× speed-up via `atempo` filter) reduces the likelihood of exceeding this threshold by compressing TTS audio to fit within the original timestamp slot.

---

### 13.9 Exclusion Detection — KB Tender §3.1

Before translation begins, the full transcript text is checked against exclusion patterns:

| Pattern | Reason |
|---------|--------|
| Speech/address/statement by Prime Minister or President of India | KB tender §3.1 — PM/President speeches must not be translated |
| `youtube.com` or `youtu.be` URLs | YouTube-only content has no source file — cannot be dubbed |

If any exclusion pattern matches, `dub_video()` returns immediately with `success=False` and an error message. No translation or TTS is performed. The exclusion check runs after ASR (Step 2) so the full transcript is available for pattern matching.

---

### 13.10 QA Certificate Generation

`generate_qa_report()` in `dubbing_pipeline.py` produces a Word document (`.docx`) self-certification report per course per language. The report includes:

- Course ID, source/target language, input/output file names
- Original duration, heuristic score, ChrF score, back-translation score
- 7-item certification checklist (linguistic accuracy, terminology consistency, content guidelines, administrative context, audio-text sync, technical format, no mixed languages)
- Declaration signed by the QA reviewer with date

The QA certificate is a KB tender deliverable (§4.5) and is generated automatically as part of `process_course_full()`. It is stored at `output/<course_id>/<lang>/<course_id>_<lang>_qa_cert.docx`.


---

## 14. Reliability, Logging & Video Processing

This section covers the three infrastructure modules that underpin pipeline reliability: the checkpoint/retry system (`pipeline/retry.py`), the structured logging system (`pipeline/logger.py`), and the ffmpeg-based video/audio processing layer (`pipeline/video_processor.py`).

---

### 14.1 Checkpoint & Resume — `pipeline/retry.py`

#### 14.1.1 JobCheckpoint

`JobCheckpoint` persists per-segment translation results to disk so a crashed job can resume from the last completed segment rather than restarting from zero. This is critical for long jobs (22 languages × hundreds of segments) where a GPU OOM or network interruption mid-job would otherwise discard all completed work.

Storage location: `checkpoints/jobs/<job_id>.json`

Job ID is a 12-character MD5 hash of `<filename>_<tgt_lang>`, deterministic across runs for the same input file and target language.

Checkpoint file structure:

```json
{
  "completed": {
    "0": { "id": 0, "start": 0.0, "end": 4.2, "text": "...", "engine": "indictrans2", "quality": {...} },
    "1": { ... },
    ...
  },
  "meta": {
    "segments":          [...],
    "detected_src_lang": "eng",
    "duration":          312.5
  }
}
```

Thread safety: all reads and writes are protected by an instance-level `threading.Lock()`. Writes use an atomic pattern — content is written to `<job_id>.tmp` first, then renamed to `<job_id>.json`. This prevents partial writes from corrupting the checkpoint file on crash.

| Method | Description |
|--------|-------------|
| `set_meta(key, value)` | Store pipeline metadata (segments, duration, detected language) |
| `get_meta(key, default)` | Retrieve metadata |
| `mark_done(seg_id, result)` | Record a completed segment result in memory |
| `flush()` | Atomically persist all in-memory results to disk |
| `is_done(seg_id)` | Check if a segment has already been translated |
| `get_done(seg_id)` | Retrieve a previously completed segment result |
| `clear()` | Delete the checkpoint file and reset in-memory state |

Flush strategy: `mark_done()` writes to memory only; `flush()` is called once after the entire translation batch completes. This avoids per-segment disk I/O overhead while still persisting all results atomically.

#### 14.1.2 Retry Decorator

The `@retry` decorator wraps translation engine calls with exponential backoff:

```python
@retry(max_attempts=2, delay=1.0)   # IndicTrans2 — fast retry
@retry(max_attempts=2, delay=2.0)   # SeamlessM4T / NLLB — slower retry
```

Backoff formula: `wait = delay × 2^(attempt − 1)`

| Attempt | delay=1.0 | delay=2.0 |
|---------|-----------|-----------|
| 1 | 1.0 s | 2.0 s |
| 2 | 2.0 s | 4.0 s |

After all attempts are exhausted, the original exception is re-raised so the pipeline's fallback chain (IndicTrans2 → SeamlessM4T → NLLB-200) can catch it and try the next engine.

#### 14.1.3 Concurrent Job Protection

A per-(course_id, tgt_lang) threading lock (`_JOB_LOCKS`) prevents duplicate jobs from running simultaneously and overwriting each other's output. The lock is acquired with `blocking=False` — if already held, `dub_video()` returns immediately with an error rather than blocking.

```python
job_lock = _get_job_lock(course_id, tgt_lang)
if not job_lock.acquire(blocking=False):
    result.error = "Job already running — skipping duplicate"
    return result
```

#### 14.1.4 Stale Cache Detection

Before Step 1 (audio extraction), the pipeline checks whether `source.wav` is older than the input video file:

```python
wav_stale = wav_exists and (
    Path(wav_path).stat().st_mtime < Path(video_path).stat().st_mtime
)
```

If stale, the WAV is re-extracted and the ASR checkpoint is cleared (`ckpt.set_meta("segments", None)`) so Step 2 re-runs with the fresh audio. This prevents a scenario where the input video is updated but the pipeline silently uses the old cached transcript.

---

### 14.2 Structured Logging — `pipeline/logger.py`

#### 14.2.1 Log Files

| File | Logger name | Content |
|------|-------------|---------|
| `logs/pipeline.log` | `dubbing_pipeline`, `translator`, `asr`, `tts`, `quality`, etc. | All pipeline events — INFO and above |
| `logs/audit.log` | `audit` | Job start/success/failure events only — JSON lines |

Both files use `RotatingFileHandler`: 10 MB per file, 5 backup files retained (`pipeline.log`, `pipeline.log.1`, … `pipeline.log.5`).

#### 14.2.2 JSON Lines Format

Every log entry is a single JSON object on one line:

```json
{"ts": "2025-01-15T14:32:01", "level": "INFO", "module": "dubbing_pipeline", "msg": "START job=a3f2c1d4e5b6 file=course.mp4 Hindi->Kannada"}
{"ts": "2025-01-15T14:32:45", "level": "WARNING", "module": "quality", "msg": "Quality flags [kan] score=0.42 chrf=0.0: ['length_ratio_0.3x'] | ಕರ್ನಾಟಕ..."}
{"ts": "2025-01-15T14:35:12", "level": "INFO", "module": "audit", "msg": "{\"event\": \"job_success\", \"job_id\": \"a3f2c1d4e5b6\", \"tgt\": \"kan\", \"elapsed_s\": 191.4, ...}"}
```

Exception tracebacks are included in the `exc` field when `exc_info=True` is passed to the logger.

#### 14.2.3 Console Output

The console handler uses a human-readable format (`[module] message`) at INFO level. On Windows, stdout is wrapped in `io.TextIOWrapper` with `encoding='utf-8'` and `errors='replace'` to prevent `UnicodeEncodeError` when logging Indic script characters to a Windows terminal.

#### 14.2.4 Audit Trail

Every job writes three audit events to `audit.log`:

| Event | When | Fields |
|-------|------|--------|
| `job_start` | Before Step 1 | job_id, file, src, tgt, course_id, host |
| `job_success` | After Step 6 | job_id, tgt, elapsed_s, output path, quality_summary |
| `job_failed` | On exception | job_id, tgt, elapsed_s, error message |

The audit log is the compliance trail required by the KB tender. It records which model versions were used (via `_model_versions()` in the metadata JSON) and the hostname of the processing machine.

---

### 14.3 Video Processing — `pipeline/video_processor.py`

All video and audio operations use ffmpeg via the `imageio_ffmpeg` bundled binary (falls back to system `ffmpeg` if `imageio_ffmpeg` is not installed). No GPU is required for video processing — all operations are CPU-only.

#### 14.3.1 Audio Extraction — `extract_audio()`

Extracts the audio track from any supported video/audio format to a 16 kHz mono WAV:

```
ffmpeg -y -i <video> -ar 16000 -ac 1 -vn source.wav
```

Fallback chain:
1. Direct extraction — works for standard MP4/MKV/AVI
2. Re-encode input (`_reencode_input()`) — handles corrupt containers, unusual codecs, Gradio temp copies (libx264 + AAC re-encode at ultrafast preset)
3. If no audio stream detected — generates silence matching the video duration via `anullsrc` filter

Stale cache check: if `source.wav` exists but is older than the input video, it is re-extracted automatically.

#### 14.3.2 Duration Detection — `_probe()`

Duration is detected via a three-step fallback:
1. `ffprobe -show_entries format=duration -of json` — most accurate
2. Parse `Duration: HH:MM:SS.ms` from ffmpeg stderr — works when ffprobe is absent
3. `librosa.load()` — last resort for audio-only files

#### 14.3.3 Audio Assembly — `assemble_dubbed_audio()`

This is the core timing synchronisation function. It places each TTS segment at its original timestamp in a zero-padded output buffer of exactly `original_duration` seconds.

Algorithm per segment:

```
1. Read TTS WAV → resample to 44100 Hz if needed
2. Compute slot_samp = max(next_segment_start − this_start, seg_end − seg_start, 0.1s)
3. If len(seg_audio) > slot_samp:
       ratio = min(len(seg_audio) / slot_samp, 1.35)   ← max 1.35× speed-up
       seg_audio = atempo_stretch(seg_audio, ratio)
       if still over: hard-trim to slot_samp
4. Apply 10ms linear fade-in (eliminates click at segment boundary)
5. Place at start_samp = int(start_s × sample_rate) in output buffer
6. Normalise final output to −1 dBFS (peak = 0.891)
```

The `atempo` filter is applied via ffmpeg through temporary files (`_atempo_stretch_file()`). This uses time-domain stretching with no phase smearing, producing cleaner speech than librosa's phase vocoder at speed ratios close to 1.0.

atempo filter chaining for ratios outside the 0.5–2.0 per-filter limit:
- ratio > 2.0: `atempo=2.0,atempo=<ratio/2.0>`
- ratio < 0.5: `atempo=0.5,atempo=<ratio/0.5>`

#### 14.3.4 Video Muxing — `replace_audio_in_video()`

Replaces the audio track in the original video with the assembled dubbed WAV:

```
Step 1: Pad/trim dubbed.wav to exactly video_duration seconds
Step 2: ffmpeg mux — copy video stream, re-encode audio to AAC 192k
Step 3: If SRT present — embed as soft subtitle track (mov_text codec)
Step 4: If copy fails — retry with libx264 re-encode (handles unusual codecs)
```

Soft subtitle embedding:
```
ffmpeg -i video.mp4 -i dubbed.wav -i subtitles.srt \
    -c:v copy -c:a aac -b:a 192k \
    -map 0:v:0 -map 1:a:0 -map 2:0 \
    -c:s mov_text -metadata:s:s:0 language=<lang> \
    -disposition:s:0 default \
    output.mp4
```

The subtitle track is embedded as `mov_text` (the standard soft subtitle format for MP4 containers). It is set as the default subtitle track so media players display it automatically. If SRT embedding fails, the pipeline falls back to video-only mux without subtitles.

#### 14.3.5 ffmpeg Binary Resolution

```python
try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()   # bundled binary
except Exception:
    _FFMPEG = "ffmpeg"                           # system PATH fallback
```

`ffprobe` is resolved as `<ffmpeg_dir>/ffprobe.exe` (Windows) or via `shutil.which("ffprobe")`. This ensures the pipeline works on machines without system ffmpeg installed, using only the Python package dependency.


---

## 15. Supporting Modules

This section documents the four supporting pipeline modules: subtitle generation (`pipeline/subtitles.py`), glossary management (`pipeline/glossary.py`), document translation (`pipeline/doc_extractor.py`), and voice cloning (`pipeline/voice_clone.py`).

---

### 15.1 Subtitle Generation — `pipeline/subtitles.py`

#### 15.1.1 Output Formats

The subtitle module generates two standard formats from the translated segment list:

| Format | Standard | Encoding | Use Case |
|--------|----------|----------|---------|
| SRT | SubRip Text | UTF-8 with BOM (`utf-8-sig`) | Broadcast, offline players, CBP portal |
| VTT | WebVTT | UTF-8 | Web players, HTML5 video, iGOT platform |

Both formats are generated by default for every dubbed video. Output paths:
```
output/<course_id>/<lang>/<course_id>_<lang>.srt
output/<course_id>/<lang>/<course_id>_<lang>.vtt
```

#### 15.1.2 Timestamp Format

SRT timestamps use comma as the millisecond separator (`HH:MM:SS,mmm`); VTT uses a period (`HH:MM:SS.mmm`). Both are derived from the same `_seconds_to_srt_time()` function with a string replacement for VTT.

Embedded newlines within segment text are collapsed to a single space before writing. This prevents the SRT parser from misinterpreting a mid-text newline as the blank line that separates subtitle entries.

#### 15.1.3 Subtitle Embedding Modes

Two embedding modes are available:

Soft subtitles (default — used in `replace_audio_in_video()`):
```
ffmpeg -i video.mp4 -i subtitles.srt \
    -c:v copy -c:a copy -c:s mov_text \
    -metadata:s:s:0 language=<lang> \
    -disposition:s:0 default output.mp4
```
Soft subtitles are stored as a separate track inside the MP4 container. Viewers can toggle them on/off. The track is set as the default subtitle track so it displays automatically.

Hard subtitles (burn-in — `burn_subtitles()`):
```
ffmpeg -i video.mp4 -vf "subtitles='<srt_path>'" -c:a copy output.mp4
```
Hard subtitles are rendered into the video stream and cannot be disabled. Used as a fallback if soft embedding fails. Windows path backslashes are escaped (`\` → `/`, `:` → `\:`) for the ffmpeg `subtitles` filter.

Fallback chain: soft embed → if ffmpeg returns non-zero → `burn_subtitles()`.

---

### 15.2 Glossary Management — `pipeline/glossary.py`

#### 15.2.1 Storage Format

One JSON file per language: `glossary/<lang_code>.json`

```json
{
  "competency framework": "दक्षता ढांचा",
  "iGOT karmayogi": "iGOT कर्मयोगी",
  "capacity building": "क्षमता निर्माण",
  "civil services": "सिविल सेवाएं"
}
```

Keys are stored in lowercase. All 22 language files are loaded at `GlossaryManager.__init__()` and held in memory for the lifetime of the pipeline process.

#### 15.2.2 Application Strategy

Glossary is applied as the final post-processing step — after all translation engine output, all cleaning passes, and the Final Quality Check. This ensures glossary terms are never overwritten by subsequent cleaning steps.

`apply()` method logic:
1. Strip any `__GLOSS_N__` placeholder artifacts that the translation model emitted literally
2. Strip stray Gurmukhi/Malayalam prefix characters that appear at segment start
3. For each glossary entry: replace source terms that literally leaked through unchanged (word-boundary regex match, case-insensitive)

The glossary does not pre-protect terms before translation (no `__GLOSS__` injection into the translation engine). Pre-protection was found to cause hallucination in IndicTrans2 when placeholder tokens appeared mid-sentence. Instead, the glossary is applied purely as a post-translation correction layer.

#### 15.2.3 Glossary Report Export

`export_report()` generates a plain-text report of all glossary entries across all 22 languages, formatted for KB submission:

```
KB Translation Glossary Report
============================================================

[Hindi (hin)]
  competency framework           → दक्षता ढांचा
  capacity building              → क्षमता निर्माण
  ...

[Bengali (ben)]
  ...
```

---

### 15.3 Document Translation — `pipeline/doc_extractor.py`

#### 15.3.1 Supported Input Formats

| Format | Library | Notes |
|--------|---------|-------|
| `.txt` | Built-in | UTF-8 read |
| `.pdf` | pdfplumber | Text extraction only; PDF blocked for translation per KB tender §3.1 |
| `.docx` / `.doc` | python-docx | Full structure-preserving translation |

#### 15.3.2 Format-Preserving DOCX Translation — `translate_docx()`

`translate_docx()` translates a Word document while preserving all formatting. It operates at the paragraph level, translating each paragraph as a single unit to maintain sentence coherence, then distributes the result back into the original run structure.

Preserved elements:

| Element | Preservation Method |
|---------|-------------------|
| Paragraph styles | Style object unchanged — only run text is modified |
| Run-level formatting | Bold, italic, underline, font size, colour — preserved on first run |
| Tables | Translated cell by cell, paragraph by paragraph |
| Headers and footers | All 6 header/footer types (default, even-page, first-page) translated |
| Hyperlinks | Text translated; URL href preserved unchanged |
| Inline images | Copied unchanged (not text — not touched) |

Translation strategy per paragraph:
1. Concatenate all run texts into a single string
2. Send to `translate_fn([full_text], src_lang, tgt_lang)` — document batch mode
3. Place result in `runs[0].text`; set `runs[1:]` to `""`

This preserves the paragraph's style and the first run's formatting (bold/italic/font) while replacing the text content. The `translate_fn` parameter accepts any callable matching `(list[str], str, str) → list[str]`, making the function engine-agnostic.

Document batch mode bypasses all token protection layers (no `__NT__`, `__F__`, `__FMT__` placeholders). These protection layers cause hallucination on document paragraphs because the model sees unusual token patterns mid-sentence. Only `<unk>` stripping is applied to document batch output.

---

### 15.4 Voice Cloning — `pipeline/voice_clone.py`

#### 15.4.1 Overview

Voice cloning is a KB Tier 2 pricing feature (`--voice-clone` flag). It uses Coqui XTTS-v2 (Apache 2.0, fully offline) to synthesise dubbed speech in the target language using the original speaker's voice characteristics extracted from a reference audio clip.

Supported languages (10 of 22):

| Code | Language | XTTS-v2 Code |
|------|----------|-------------|
| hin | Hindi | hi |
| ben | Bengali | bn |
| guj | Gujarati | gu |
| mar | Marathi | mr |
| tam | Tamil | ta |
| tel | Telugu | te |
| kan | Kannada | kn |
| mal | Malayalam | ml |
| pan | Punjabi | pa |
| urd | Urdu | ur |

#### 15.4.2 Speaker Embedding Extraction

`extract_speaker_embedding()` calls `model.get_conditioning_latents(audio_path=[reference_audio])` to extract two tensors from the reference WAV:

- `gpt_cond_latent` — GPT conditioning latent (captures prosody and speaking style)
- `speaker_embedding` — d-vector speaker embedding (captures voice timbre)

The embedding is computed once per course and reused for all segments via `synthesize_segments_with_clone()`. This avoids re-processing the reference audio for every segment, which would add significant latency.

Recommended reference audio: minimum 6 seconds of clean speech from the target speaker, no background noise.

#### 15.4.3 Synthesis Flow

```
synthesize_segments_with_clone(segments, lang, reference_audio, output_dir)
    │
    ├─ extract_speaker_embedding(reference_audio)  ← computed ONCE
    │       → {gpt_cond_latent, speaker_embedding}
    │
    └─ for each segment:
           synthesize_with_clone(text, lang, reference_audio, output_path,
                                 speaker_embedding=embedding)
               │
               ├─ if embedding provided:
               │      model.inference(text, language, gpt_cond_latent,
               │                      speaker_embedding)
               │      → wav at 24000 Hz → sf.write()
               │
               └─ if no embedding:
                      model.tts_to_file(text, language, speaker_wav,
                                        file_path)
```

Output sample rate: 24000 Hz (XTTS-v2 native). The assembled audio is resampled to 44100 Hz during `assemble_dubbed_audio()` if needed.

#### 15.4.4 Integration with Main Pipeline

In `dub_video()`, voice cloning replaces the standard TTS step (Step 4) when `--voice-clone` is passed and the target language is supported:

```python
if voice_clone and self.voice_cloner and self.voice_cloner.is_supported(tgt_lang):
    ref = reference_audio or wav_path   # use source audio as reference if none provided
    tts_segments = self.voice_cloner.synthesize_segments_with_clone(
        translated_segments, tgt_lang, ref, tts_dir)
    result.voice_cloned = True
else:
    tts_segments = self.tts.synthesize_segments(translated_segments, tgt_lang, tts_dir)
```

If no `--reference-audio` is provided, the extracted source WAV (`source.wav`) is used as the reference. This approximates the original speaker's voice for the dubbed output, though quality is lower than a dedicated clean reference recording.


---

## 16. Integration Modules — CBP Upload, LLM Enhancement & Translation Memory

This section documents the three integration modules that connect the pipeline to external systems and knowledge bases: the CBP portal uploader (`pipeline/cbp_uploader.py`), the optional LLM post-edit enhancer (`pipeline/llm_enhancer.py`), and the Translation Memory system (`scripts/translation_memory.py`).

---

### 16.1 CBP Portal Uploader — `pipeline/cbp_uploader.py`

#### 16.1.1 Overview

The CBP (Competency Building Product) uploader handles automated submission of all translated course assets to the iGOT Karmayogi portal at `https://cbp.igotkarmayogi.gov.in`. This fulfils KB tender Section 4.2, which requires all deliverables to be uploaded to the portal after quality acceptance.

Credentials are read from environment variables set in `.env`:

```
CBP_USERNAME=your_username
CBP_PASSWORD=your_password
CBP_BASE_URL=https://cbp.igotkarmayogi.gov.in   # optional override
```

#### 16.1.2 Authentication

`login()` posts credentials to `/api/user/v1/login` and stores the returned Bearer token in the session headers. All subsequent requests carry `Authorization: Bearer <token>` automatically via the `requests.Session` object.

```
POST /api/user/v1/login
    {"username": "...", "password": "..."}
    → {"result": {"access_token": "..."}}
```

If no credentials are set, `login()` returns `False` and logs a warning. The pipeline continues without uploading — upload is always optional.

#### 16.1.3 Asset Upload — `_upload_asset()`

Each file is uploaded via multipart POST to `/api/content/v1/upload`:

```
POST /api/content/v1/upload
    files: {"file": (<filename>, <binary>)}
    data:  {"courseId": "...", "language": "hin", "assetType": "video"}
```

Asset types: `video`, `audio`, `metadata`, `assessment`, `subtitle`.

Retry policy: 3 attempts with linear backoff (5s, 10s between attempts). Returns `{"success": True, "response": <api_response>}` on success or `{"success": False, "error": "..."}` after all attempts fail.

#### 16.1.4 Course Package Upload — `upload_course_package()`

Uploads all assets for a single language from the output directory by scanning for files matching standard naming patterns:

| Pattern | Asset Type |
|---------|-----------|
| `*_<lang>.mp4` | video |
| `*_<lang>.mp3` | audio |
| `*_<lang>*.xlsx` | metadata |
| `*_<lang>*.docx` | assessment |
| `*_<lang>.srt` | subtitle |
| `*_<lang>.vtt` | subtitle |

#### 16.1.5 Submission Report

`generate_submission_report()` writes a JSON report of all upload results to disk:

```json
{
  "generated_at": "2025-01-15 14:35:00",
  "portal": "https://cbp.igotkarmayogi.gov.in",
  "total_uploads": 132,
  "total_errors": 0,
  "courses": [...]
}
```

This report serves as the upload audit trail for KB payment milestone verification.

---

### 16.2 LLM Post-Edit Enhancer — `pipeline/llm_enhancer.py`

#### 16.2.1 Overview

The LLM enhancer is an optional post-processing step that sends machine translations to a large language model for fluency and naturalness improvement. It activates only when an API key is present in `.env` — the pipeline runs fully offline without it.

Provider detection order (first key found wins):

| Priority | Provider | Model | Key Variable |
|----------|----------|-------|-------------|
| 1 | Groq | llama-3.3-70b-versatile | `GROQ_API_KEY` |
| 2 | Gemini | gemini-1.5-flash | `GEMINI_API_KEY` |
| 3 | OpenRouter | meta-llama/llama-3.3-70b-instruct:free | `OPENROUTER_API_KEY` |

All three providers offer free tiers sufficient for the pipeline's usage volume.

#### 16.2.2 Enhancement Prompt

Single-segment enhancement uses a structured prompt that instructs the LLM to act as a professional Indian language quality editor:

```
You are a professional translator and language quality editor for Indian languages.

Task: Post-edit the machine translation below to make it natural, fluent, and accurate.
- Keep all proper nouns, scheme names, and numbers exactly as-is
- Fix grammar, word order, and unnatural phrasing
- Output ONLY the corrected translation, nothing else

Source (eng): <source_text>
Machine Translation (hin): <translated_text>
Corrected Translation:
```

Temperature is set to 0.1 for all providers — low temperature produces consistent, conservative edits rather than creative rewrites.

#### 16.2.3 Batch Enhancement

`enhance_batch()` sends all translations for a language in a single LLM call using a JSON array prompt, reducing API round-trips:

```
Return a JSON array of corrected strings in the same order.
Translations: ["seg1 translation", "seg2 translation", ...]
```

The response is parsed by finding the first `[` and last `]` in the output. If the parsed array length does not match the input length, the raw (unenhanced) translations are returned unchanged — the pipeline never silently drops segments due to LLM output format errors.

#### 16.2.4 Failure Handling

All LLM calls are wrapped with `@retry(max_attempts=3, delay=1.0)`. If all retries fail, `enhance()` returns the original machine translation unchanged. The pipeline logs a warning but continues — LLM enhancement is never a blocking dependency.

---

### 16.3 Translation Memory — `scripts/translation_memory.py`

#### 16.3.1 Architecture Position

The Translation Memory (TM) sits between the translation engines and the final output, providing a lookup layer that can short-circuit engine calls for previously verified translations:

```
Input segment
    │
    ▼
TM lookup (exact → fuzzy)
    │
    ├─ Exact HF match (score=1.0) → return immediately
    ├─ Exact TM match (score=1.0) → return immediately
    ├─ Fuzzy match (score≥0.85)   → return with needs_review flag
    │
    └─ No match → translation engine (IndicTrans2 → Seamless → NLLB)
```

In `dubbing_pipeline.py`, the TM is consulted via `_translate_text()` for metadata and quiz fields. For segment-level translation, the TM is passed to `translator.translate()` as the `glossary` parameter — exact and human-feedback matches bypass the engine entirely.

#### 16.3.2 Storage Files

| File | Content | Format |
|------|---------|--------|
| `translation_memory/govt_tm.jsonl` | Government-verified translations | JSON Lines |
| `translation_memory/human_feedback.jsonl` | Human reviewer corrections | JSON Lines |
| `translation_memory/correction_log.jsonl` | Audit trail of all corrections | JSON Lines |

Each record schema:

```json
{
  "id":       "<16-char SHA-256 of src+tgt_lang>",
  "src":      "Competency Framework",
  "tgt":      "दक्षता ढांचा",
  "src_lang": "eng",
  "tgt_lang": "hin",
  "domain":   "government",
  "verified": true,
  "source":   "govt_doc",
  "added_at": "2025-01-15T14:32:01"
}
```

#### 16.3.3 Lookup Priority

`lookup()` applies a strict priority order:

1. Exact match in human feedback (`match_type: "exact_hf"`, score=1.0) — highest priority; human corrections always override government TM
2. Exact match in government TM (`match_type: "exact_tm"`, score=1.0)
3. Fuzzy match across both stores using `SequenceMatcher.ratio()` — returns best match if score ≥ 0.85 (`match_type: "fuzzy"`)
4. No match → returns `None` → translation engine is called

Fuzzy threshold of 0.85 was chosen to catch minor variations (punctuation differences, capitalisation) while avoiding false matches on semantically different sentences.

#### 16.3.4 Human Feedback & Correction Audit

`add_correction()` records both the wrong translation and the correct one:

- Appends to `correction_log.jsonl` with timestamp, corrected_by, wrong_tgt, and correct_tgt — full audit trail
- Appends to `human_feedback.jsonl` with only the correct translation — used for future lookups and fine-tuning

Human feedback records are upweighted 3× when exported for fine-tuning (`export_for_finetuning()`), reflecting the higher reliability of human-verified translations compared to automatically generated TM entries.

#### 16.3.5 CLI Interface

The TM is fully operable from the command line:

```bash
# Add a verified government translation
python scripts/translation_memory.py add \
    --src "Competency Framework" --tgt "दक्षता ढांचा" --tgt-lang hin

# Record a human correction
python scripts/translation_memory.py correct \
    --src "..." --wrong "..." --correct "..." --tgt-lang hin

# Bulk import from JSON file
python scripts/translation_memory.py import --file entries.json --type govt

# Look up a term
python scripts/translation_memory.py lookup --src "Competency" --tgt-lang hin

# Show statistics (all 22 languages)
python scripts/translation_memory.py stats

# Show last 20 correction audit log entries
python scripts/translation_memory.py log
```

#### 16.3.6 Integration with Pipeline

The TM is instantiated once in `DubbingPipeline.__init__()` when `use_tm=True` (default). It is used in two places:

1. `_translate_text()` — for metadata and quiz field translation: exact TM/HF matches bypass the engine entirely
2. Passed as context to `translator.translate()` — the translator checks the TM before calling any engine

If `scripts/translation_memory.py` is not importable (e.g. missing `difflib` or path issue), `_TM_AVAILABLE` is set to `False` and the pipeline continues without TM — it is never a blocking dependency.


---

## 17. Web User Interface

This section documents the Gradio-based web UI (`ui/app.py` and `ui/reviewer.py`), covering all 8 tabs, the background pipeline loading mechanism, and the human review workflow.

---

### 17.1 Overview

The UI is built with Gradio and launched via `python ui/app.py`. It provides a browser-based interface to all pipeline capabilities without requiring command-line access. The UI is designed for non-technical operators — translators, QA reviewers, and project managers — who need to submit dubbing jobs, review translations, and generate compliance reports.

Launch behaviour:
- Binds to `0.0.0.0` (all interfaces) on port 7860 (auto-increments if occupied, up to 7879)
- Opens browser automatically (`inbrowser=True`)
- Uses Gradio Soft theme with indigo primary colour
- Pipeline models load in a background daemon thread immediately on startup — the UI is accessible while models load

---

### 17.2 Background Pipeline Loading

The `DubbingPipeline` is instantiated once in a background thread at import time:

```python
_bg_thread = threading.Thread(target=_load_pipeline_bg, daemon=True)
_bg_thread.start()
```

A `threading.Event` (`_pipeline_ready`) is set when loading completes or fails. All tab handlers call `get_pipeline()` which blocks with a 5-minute timeout on `_pipeline_ready.wait()`. A live status bar at the top of the UI polls `_pipeline_status()` every 3 seconds and shows:
- `⏳ Loading models in background...` — while loading
- `✅ Pipeline ready` — when ready
- `❌ <error>` — if loading failed

This design allows the UI to be fully interactive (tabs visible, settings editable) while the ~2-minute model loading proceeds in the background.

---

### 17.3 Tab Reference

#### Tab 1 — 🎬 Dub Video / Audio

The primary job submission tab. Accepts MP4, MP3, WAV, FLAC input files.

| Control | Description |
|---------|-------------|
| Course Video / Audio | File upload — MP4/MP3/WAV/FLAC |
| Course Metadata | Optional — Word/Excel/JSON for metadata translation |
| Quiz / Assessment | Optional — Word/Excel/JSON for quiz translation |
| Course ID | Identifier used in output filenames and folder structure |
| Source Language | Dropdown — English (default) or any of 22 Indian languages |
| Target Languages | Checkbox group — KB-11 pre-selected; quick-select buttons for KB 11 / All 22 / Clear |
| Voice Cloning (Tier 2) | Checkbox — reveals reference speaker audio upload when enabled |
| Upload to CBP Portal | Checkbox — triggers `CBPUploader` after job completes |
| Start Dubbing | Calls `process_course_full()` — runs full pipeline including dubbing, metadata, quiz, QA reports |

Outputs: downloadable file list (MP4, SRT, VTT, DOCX quiz, DOCX QA cert, XLSX metadata) + JSON job summary with quality scores.

GPU auto-detection: `torch.cuda.device_count()` is called at job submission time; multi-GPU parallel dubbing is used automatically when >1 GPU is available.

#### Tab 2 — 📄 Translate Document

Translates course materials without video dubbing.

| Document Type | Input Format | Output |
|---------------|-------------|--------|
| Quiz / Assessment | JSON array | Per-language DOCX (Word) |
| Course Metadata | JSON object | Multi-language XLSX (Excel) |
| General Document | DOCX / TXT | Per-language DOCX (format-preserving for DOCX) |
| PDF | — | Blocked — returns error per KB tender §3.1 |

DOCX translation uses `translate_docx()` (format-preserving, preserves styles/tables/headers). TXT/PDF-extracted text is chunked at sentence boundaries (max 400 chars per chunk) before batch translation, then reassembled into a new DOCX.

#### Tab 3 — 📋 QA Certificate

Generates the Language Quality Assurance Certification DOCX required by the KB tender SLA. Accepts the original source file and dubbed output file as inputs, along with the reviewer's name. Produces a Word document with quality scores, certification checklist, and declaration.

The tab also displays the KB tender SLA thresholds and delivery penalty schedule as a reference panel:
- Score ≥ 0.55 → Pass (98%+ accuracy)
- Score 0.30–0.55 → Needs correction (resubmit within 5 days)
- Score < 0.30 → Failed — mandatory re-translation
- Delivery shortfall penalties: <5% = no penalty, 5–10% = 2% deduction, >10% = 4%, >20% = 5%

#### Tab 4 — 👤 Human Review

Segment-level review interface for native language experts. Loads a `*_metadata.json` file produced by the pipeline and displays all translated segments in an editable table.

| Column | Editable | Description |
|--------|----------|-------------|
| ID | No | Segment identifier |
| Time | No | `start–end` timestamps |
| Source | No | Original English text |
| AI Translation | No | Machine translation output |
| Corrected Text | Yes | Reviewer's corrected version |
| Score | No | Heuristic quality score |
| Flags | No | Quality flag list |
| 🚩 | No | AI-flagged for review indicator |
| Decision | Yes | `approved` / `corrected` / `rejected` |

Workflow:
1. Upload `*_metadata.json` → segments load into table
2. Edit "Corrected Text" and "Decision" columns inline
3. "Approve All Unflagged" — bulk-approves segments with no quality flags and no existing decision
4. "Save Progress" — persists decisions to a sidecar `*_review.json` file (resume support)
5. "Export Review Certificate" — generates signed DOCX certificate via `export_certificate()`

Review state is persisted to a sidecar file (`<stem>_review.json`) so reviewers can close the browser and resume later without losing progress.

#### Tab 5 — ⚙️ Settings

| Setting | Description |
|---------|-------------|
| HuggingFace Token | Saved to `.env` as `HF_TOKEN`; used for model downloads |
| Output Save Folder | Persisted to `.output_dir` file; all pipeline outputs go here |
| Open Folder | Calls `os.startfile()` to open the output folder in Windows Explorer |

The settings tab also displays a reference panel explaining quality scoring thresholds and the checkpoint/resume behaviour.

#### Tab 6 — 📅 Monthly Delivery

Tracks course hours delivered per month against the KB tender SLA (50–125 hours/month). Entries are added manually per course per month.

SLA status logic:
- Total hours for month < 50 → `⚠️ Below 50hr minimum`
- Total hours 50–125 → `✅ On track`
- Total hours > 125 → `⚠️ Exceeds 125hr SLA cap`

Exports:
- Monthly Submission Report (XLSX) — one sheet, all entries for the month
- Consolidated Completion Report (XLSX) — two sheets: detail + summary with SLA status per month

#### Tab 7 — 📖 Glossary

Manages the standardised terminology glossary for KB submission. Supports manual entry of English terms with per-language translations, bulk import from XLSX, and export to XLSX.

Export format: one row per term, one column per language (language name as header). This is the format required for the KB tender final deliverable glossary submission.

Import: reads the same XLSX format, maps language names back to internal codes via reverse lookup of `LANG_NAMES`.

#### Tab 8 — 📊 Live Logs

Displays the last 60 lines of the in-memory log buffer, auto-refreshed every 3 seconds via Gradio's `every=3` parameter. The log buffer holds up to 200 entries with timestamps (`[HH:MM:SS] message`). This tab provides real-time visibility into pipeline progress without requiring access to the server terminal.

---

### 17.4 Human Review Module — `ui/reviewer.py`

`reviewer.py` is a pure UI logic module with no pipeline imports. It operates entirely on the `*_metadata.json` files produced by the pipeline.

#### 17.4.1 Data Flow

```
*_metadata.json (pipeline output)
    │
    ▼
load_metadata()
    → parses transcript + translations
    → joins on segment ID
    → returns list[dict] with source_text, translated_text, score, flags
    │
    ▼
load_review()  (if *_review.json exists)
    → overlays saved decisions onto segments
    → enables resume without losing prior work
    │
    ▼
segments_to_display()
    → converts to list[list] for gr.Dataframe
    │
    ▼
[Reviewer edits table in browser]
    │
    ▼
save_review()
    → writes *_review.json sidecar (atomic, UTF-8)
    │
    ▼
export_certificate()
    → generates signed DOCX with summary table + segment table + declaration
```

#### 17.4.2 Review Certificate Contents

The exported DOCX certificate (`*_review_cert.docx`) contains:

- Summary table: course ID, target language, reviewer name, review date, total/approved/corrected/rejected/pending counts
- Segment-level table: all segments with source text, AI translation, corrected text, and colour-coded decision (green=approved, orange=corrected, red=rejected)
- Declaration paragraph: reviewer name, certification statement, segment counts, contract reference (RFB IN-KBL-543730-NC-RFB)
- Signature line

This certificate is a KB tender deliverable (§4.5) and must be submitted alongside the translated content for each language.


---

## 18. Deployment & Infrastructure

### 18.1 Overview

The KB Translation System is designed for fully on-premises deployment. All model inference runs locally on GPU-equipped hardware; no request ever leaves the host machine during normal operation. The only outbound network activity is the optional CBP portal upload (§4.2 of the tender) and the optional LLM post-edit calls, both of which are explicitly opt-in and credential-gated.

The system targets a single-server or multi-GPU workstation deployment. The Gradio UI binds to `0.0.0.0` with automatic port increment starting at 7860, making it accessible to reviewers on the local network without additional reverse-proxy configuration.

---

### 18.2 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU VRAM | 16 GB (single GPU) | 24 GB × 2–4 (multi-GPU) |
| System RAM | 32 GB | 64 GB |
| Storage | 80 GB free | 200 GB SSD |
| CPU | 8-core | 16-core (parallel assembly) |
| OS | Ubuntu 20.04 / Windows 10 | Ubuntu 22.04 LTS |
| CUDA | 11.8 | 12.1 |
| Python | 3.10 | 3.11 |

The dominant VRAM consumers are:

| Model | VRAM |
|-------|------|
| faster-whisper large-v3 (CT2, int8) | ~3 GB |
| IndicTrans2 1B (fp16) | ~2.5 GB |
| SeamlessM4Tv2 Large | ~8 GB |
| Parler-TTS Indic Large | ~4 GB |
| NLLB-200 3.3B | ~7 GB |

On a single 24 GB GPU, the pipeline loads IndicTrans2 + Parler-TTS Large simultaneously and hot-swaps SeamlessM4T / NLLB-200 on demand. On multi-GPU setups, `dub_course_parallel()` assigns each language job to a separate GPU, keeping all models resident.

---

### 18.3 Model Directory Layout

All model weights are stored under `models/` inside the project root and are excluded from version control via `.gitignore`. The download script (`scripts/download_models.py`) populates this tree:

```
models/
├── indic_asr/                  # faster-whisper large-v3 (CT2 format, ~3 GB)
├── indic_tr/
│   ├── en_indic/               # IndicTrans2 English → Indic (~1.2 GB)
│   ├── indic_en/               # IndicTrans2 Indic → English (~1.2 GB)
│   └── indic_indic/            # IndicTrans2 Indic → Indic (~1.2 GB)
├── indic_parler_tts/           # Parler-TTS Indic Mini — pipeline fallback (~1.5 GB)
├── indic_parler_tts_large/     # Parler-TTS Indic Large — primary TTS (~3.6 GB)
├── seamless/                   # SeamlessM4Tv2 Large (~10 GB)
├── nllb/                       # NLLB-200 3.3B (~2.4 GB)
├── mms/                        # MMS-TTS shared VITS base + per-lang adapters (~1.5 GB)
└── mms_standalone/
    ├── dgo/                    # MMS-TTS Dogri standalone VITS
    ├── bod/                    # MMS-TTS Bodo standalone VITS
    ├── kas/                    # MMS-TTS Kashmiri standalone VITS
    ├── snd/                    # MMS-TTS Sindhi standalone VITS
    ├── kok/                    # MMS-TTS Konkani standalone VITS
    └── mni/                    # MMS-TTS Manipuri standalone VITS
```

Fine-tuned translation checkpoints are stored separately under `checkpoints/` and take precedence over the base models at runtime:

```
checkpoints/
├── indictrans/
│   ├── en_indic/best/          # Fine-tuned English → all 22 Indian languages
│   ├── indic_en/best/          # Fine-tuned Indic → English (back-translation scoring)
│   └── indic_indic/best/       # Fine-tuned Indic → Indic (pivot + direct)
├── seamless/                   # SeamlessM4T fine-tune checkpoints
└── jobs/                       # Runtime job checkpoints (auto-cleared on success)
```

The pipeline's `_load_translator()` checks for the `best/` subdirectory first; if absent it silently falls back to the base model path. This allows incremental fine-tuning without modifying any pipeline code.

---

### 18.4 Environment Variables

All secrets and optional configuration are stored in `.env` at the project root. The file is loaded at startup via `python-dotenv` and is never committed to version control.

| Variable | Required | Purpose |
|----------|----------|---------|
| `HF_TOKEN` | Yes (download only) | HuggingFace Hub authentication for `snapshot_download` |
| `CBP_USERNAME` | Optional | CBP portal login (tender §4.2 upload) |
| `CBP_PASSWORD` | Optional | CBP portal login |
| `GROQ_API_KEY` | Optional | Groq LLM post-edit (llama-3.3-70b, free tier) |
| `GEMINI_API_KEY` | Optional | Gemini 1.5 Flash LLM post-edit |
| `OPENROUTER_API_KEY` | Optional | OpenRouter LLM post-edit |
| `HF_HOME` | Optional | Override HuggingFace cache directory |

`HF_TOKEN` is only needed during the one-time model download step (`scripts/download_models.py`). Once weights are on disk, the token is not required for inference. The pipeline runs fully offline with only `CBP_USERNAME`/`CBP_PASSWORD` needed for upload, and all LLM keys are strictly optional — the pipeline degrades gracefully to the local translation engines if none are set.

---

### 18.5 Installation Procedure

```bash
# 1. Install PyTorch with CUDA 12.1 support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 2. Install all other dependencies
pip install -r requirements.txt

# 3. (Optional) Install Coqui XTTS-v2 for voice cloning
pip install coqui-tts --no-deps

# 4. Download all model weights (~25 GB total)
python scripts/download_models.py

# 5. Download parallel training datasets (fine-tuning only)
python scripts/download_datasets.py

# 6. Verify 22-language dataset coverage
python scripts/check_gaps.py

# 7. (Optional) Fine-tune IndicTrans2 on domain data
python finetune/finetune_indictrans.py

# 8. Launch the UI
python ui/app.py
```

Key dependency notes from `requirements.txt`:

- `faster-whisper>=1.0.0` — CT2-format ASR; uses `imageio-ffmpeg` for bundled ffmpeg binary, eliminating the system ffmpeg requirement.
- `IndicTransToolkit>=0.1.0` — provides `IndicProcessor` for IndicTrans2 pre/post-processing (script normalisation, detokenisation).
- `parler-tts>=0.2.2` — Parler-TTS Indic Large/Mini; requires `transformers>=4.40.0`.
- `lingua-language-detector>=2.0.0` — per-segment language detection used by `lang_detect.py`.
- `deepspeed` and `bitsandbytes` are commented out in `requirements.txt`; they are only needed for the optional fine-tuning scripts in `finetune/`.

---

### 18.6 Multi-GPU Configuration

The pipeline supports automatic multi-GPU parallelism via `dub_course_parallel()` in `dubbing_pipeline.py`. The design principle is:

- **ASR runs once** in the main process on GPU 0, producing a single shared transcript for all target languages.
- **Translation + TTS + assembly** are distributed across available GPUs — each language job is assigned to `gpu_id = job_index % num_gpus`.
- GPU assignment is passed as `CUDA_VISIBLE_DEVICES` to each worker process, ensuring model loads are isolated per GPU.

```bash
# Auto-detect GPU count
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse

# Explicit GPU count
python scripts/dub.py --video course.mp4 --src eng --tgt all --num-gpus 4
```

For fine-tuning, DeepSpeed ZeRO-3 is configured via `finetune/ds_zero3.json`, enabling sharded model states across all available GPUs to fit the 1B-parameter IndicTrans2 model within per-GPU VRAM limits.

---

### 18.7 Switching Parler-TTS Large ↔ Mini

The download script saves Parler-TTS Large to `models/indic_parler_tts_large/` and Mini to `models/indic_parler_tts/`. The pipeline always loads from `models/indic_parler_tts/`. To promote Large to primary:

```bash
# Windows
rename models\indic_parler_tts       models\indic_parler_tts_mini_backup
rename models\indic_parler_tts_large models\indic_parler_tts

# Linux
mv models/indic_parler_tts       models/indic_parler_tts_mini_backup
mv models/indic_parler_tts_large models/indic_parler_tts
```

No code changes are required. The pipeline picks up the new weights on next launch.

---

### 18.8 Output & Workspace Layout

```
project/
├── input/          # Source videos and documents placed here before processing
├── output/         # All pipeline outputs (auto-created)
│   └── <course_id>/
│       └── <lang_code>/
│           ├── <course_id>_<lang>.mp4
│           ├── <course_id>_<lang>.srt
│           ├── <course_id>_<lang>.vtt
│           └── <course_id>_<lang>_metadata.json
├── logs/
│   ├── pipeline.log   # Structured JSON lines, rotating 10 MB × 5
│   └── audit.log      # Job start/success/failure audit trail
├── translation_memory/
│   ├── govt_tm.jsonl
│   ├── human_feedback.jsonl
│   └── correction_log.jsonl
└── checkpoints/jobs/  # Runtime crash-resume state (auto-cleared on success)
```

Outputs can be wiped cleanly without touching models or checkpoints:

```bash
python scripts/clean_outputs.py        # removes output/ + checkpoints/jobs/
scripts\wipe_outputs.bat               # Windows equivalent
python scripts/clean_and_run_all22.py  # wipe then immediately dub all 22 languages
```

---

*Prepared By: Sanjana MS*

---

## 19. Datasets & Fine-Tuning

### 19.1 Overview

The pipeline ships with pre-trained base models that work out of the box. Fine-tuning on domain-specific and government-verified data is an optional but recommended step that improves translation accuracy for iGOT Karmayogi content — particularly for administrative and governance terminology. Two models are fine-tuned: IndicTrans2 (translation) and SeamlessM4T (ASR + text-to-text translation).

All datasets are downloaded from HuggingFace Hub using `scripts/download_datasets.py`. Coverage is verified with `scripts/check_gaps.py`. The ASR fine-tune index is built with `scripts/build_asr_index.py`.

---

### 19.2 Dataset Sources

#### 19.2.1 Parallel Text Datasets

| Dataset | Source | Languages | Pairs |
|---------|--------|-----------|-------|
| Samanantar | ai4bharat/samanantar | 11 high-resource (hin/ben/tam/tel/kan/mal/mar/guj/pan/ory/asm/urd) | ~49.7M total |
| IN22-Gen | ai4bharat/IN22-Gen | All 22 Indian languages | ~1,000 × 22 |
| IN22-Conv | ai4bharat/IN22-Conv | All 22 Indian languages | ~1,000 × 22 |
| OPUS-100 | Helsinki-NLP/opus-100 | Gap languages (nep/san/snd/mai/kok/mni/kas/bod/doi/sat) | 20K–1M per pair |
| FLORES-200 | facebook/flores | All 22 Indian languages | ~1,000 × 22 (eval) |

Samanantar is the primary training corpus for the 11 KB-11 mandatory languages. IN22-Gen and IN22-Conv fill the gap for the 11 extended languages (bod/doi/kas/kok/mni/mai/nep/san/sat/snd) that have no Samanantar coverage. OPUS-100 provides additional pairs for the weakest languages. FLORES-200 is used exclusively for evaluation.

Estimated text dataset disk usage: ~30 GB.

#### 19.2.2 Audio / ASR Datasets

| Dataset | Source | Languages | Hours |
|---------|--------|-----------|-------|
| FLEURS | google/fleurs | 13 Indian languages (asm/ben/guj/hin/kan/mal/mar/ory/pan/tam/tel/urd/nep) | ~500 MB per lang |
| IndicSUPERB | alekya/IndicSUPERB | All 22 Indian languages | ~300 hours |
| Shrutilipi | ai4bharat/Shrutilipi | 12 languages incl. doi/kas/kok/mni/sat/snd | ~6,400 hours |
| IndicTTS | ai4bharat/indic-tts-coqui | 11 Indian languages | ~5 GB |
| Bodo ASR | XKaab/ASR-Bodo_5hrs | Bodo only | ~5 hours |
| Common Voice | mozilla-foundation/common_voice_17_0 | hin/mar/tam/urd/san (gated) | varies |

Kathbath (ai4bharat/kathbath, 1,684 hours, all 22 languages) is the highest-quality ASR corpus but requires manual approval on HuggingFace Hub; it is commented out in the download script pending access.

Estimated audio dataset disk usage: ~95 GB. Total combined: ~125 GB.

#### 19.2.3 Translation Memory as Training Data

Government-verified translations from `translation_memory/govt_tm.jsonl` and human corrections from `translation_memory/human_feedback.jsonl` are injected into the fine-tuning data at training time. Human feedback records are upweighted 3× relative to standard parallel data, reflecting their higher reliability for domain-specific terminology.

---

### 19.3 Dataset Format

Each language's parallel text is stored as JSONL files under `datasets/parallel/<lang_code>/`:

```
datasets/parallel/<lang_code>/
    train.jsonl
    dev.jsonl
    test.jsonl
```

Each line:
```json
{"src": "Competency Framework", "tgt": "दक्षता ढांचा", "src_lang": "eng", "tgt_lang": "hin"}
```

The `src_lang` and `tgt_lang` fields use the short 3-letter codes from `lang_config.py` (not FLORES-200 codes). The fine-tuning scripts convert to FLORES-200 format internally via `INDIC_TRANS2_CODES`.

An optional `"synthetic": true` field marks back-translated pairs, which are sampled at 50% probability during training (`SYNTHETIC_WEIGHT = 0.5`).

---

### 19.4 Dataset Gap Verification

`scripts/check_gaps.py` produces a full coverage report across all 22 languages for both parallel text and audio:

```
  Lang  Name          Train       Dev     Test  Status
  ─────────────────────────────────────────────────────
  hin   Hindi     8,500,000   10,000   10,000  ✅ OK
  ben   Bengali   9,000,000   10,000   10,000  ✅ OK
  ...
  sat   Santhali     20,000      500      500  ✅ OK
  kas   Kashmiri     50,000      500      500  ✅ OK
```

The script checks:
- Parallel text: `train.jsonl`, `dev.jsonl`, `test.jsonl` line counts per language
- Audio: FLEURS, Common Voice, Bodo ASR, IndicSUPERB (shared), Shrutilipi (shared), IndicTTS (shared)
- Old folder name detection: `odi→ory`, `dog→doi` renames flagged if stale

`scripts/build_asr_index.py` scans the downloaded audio datasets and writes `datasets/asr/<lang>/dataset_info.json` for each language, recording the best available source (FLEURS > Common Voice > Bodo ASR > IndicSUPERB), split paths, and a `finetune_ready` boolean. A master `datasets/asr/index.json` summarises coverage across all 22 languages.

---

### 19.5 IndicTrans2 Fine-Tuning

**Script**: `finetune/finetune_indictrans.py`

**Method**: Full fine-tune (100% parameters) using HuggingFace Accelerate with FSDP (Fully Sharded Data Parallel). FSDP is used instead of DeepSpeed ZeRO-3 for Windows compatibility; both achieve equivalent memory efficiency by sharding weights, gradients, and optimiser states across GPUs.

**Hardware target**: 4 × NVIDIA A6000 (48 GB VRAM each) — 192 GB total VRAM as one logical pool.

**Hyperparameters**:

| Parameter | Value |
|-----------|-------|
| Batch size per GPU | 16 |
| Gradient accumulation | 4 |
| Effective batch size | 256 (16 × 4 × 4 GPUs) |
| Learning rate | 3e-5 |
| Warmup steps | 200 |
| Epochs | 3 |
| Max sequence length | 256 tokens |
| Precision | bf16 (Ampere native) |
| Gradient checkpointing | Enabled |

**Training directions**:

Three separate fine-tune runs, one per translation direction:

| Direction | Training Languages | Notes |
|-----------|-------------------|-------|
| `en_indic` | 16 languages (12 high-resource + bod/doi/kok/san) | snd/kas excluded — NLLB-only in pipeline; mni/sat excluded — covered by Hindi pivot |
| `indic_en` | All 22 languages | Used for back-translation quality scoring |
| `indic_indic` | 21 Hindi-paired combinations | Enables direct Indic→Indic translation without English pivot |

**Hindi weighting**: Hindi training records are repeated 3× (`HIN_WEIGHT = 3`) because Hindi is the pivot language for Manipuri and Santhali. Improving Hindi translation quality directly improves pivot-path output for these two languages.

**Checkpoint selection**: After each epoch, dev loss is computed across all GPUs via `accelerator.reduce()`. If dev loss improves, the unwrapped model is saved to `checkpoints/indictrans/<direction>/best/`. The pipeline automatically loads from this path at inference time.

**Launch command**:
```bash
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_indictrans.py --direction en_indic

# Fine-tune all three directions sequentially
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_indictrans.py --direction all
```

---

### 19.6 SeamlessM4T Fine-Tuning

**Script**: `finetune/finetune_seamless.py`

**Method**: Full fine-tune with FSDP + bf16, same infrastructure as IndicTrans2. Two independent tasks:

#### ASR Task (`--task asr`)

Fine-tunes `SeamlessM4Tv2ForSpeechToText` on audio→text pairs from FLEURS, IndicSUPERB, and Shrutilipi. Audio is loaded at 16 kHz, truncated to 30 seconds maximum.

| Parameter | Value |
|-----------|-------|
| Batch size per GPU | 4 (audio tensors are large) |
| Gradient accumulation | 8 |
| Effective batch size | 128 |
| Learning rate | 5e-6 (very low — full fine-tune of speech encoder) |
| Warmup steps | 300 |

#### Text-to-Text Task (`--task t2t`)

Fine-tunes `SeamlessM4Tv2ForTextToText` on the same parallel text corpus used for IndicTrans2. Speech-only parameters (`speech_encoder`, `t2u`, `vocoder`) are frozen to prevent DDP gradient-sync crashes on parameters unused in the T2T forward pass.

| Parameter | Value |
|-----------|-------|
| Batch size per GPU | 8 |
| Gradient accumulation | 8 |
| Effective batch size | 256 |
| Learning rate | 2e-5 |

Odia (`ory`) is excluded from SeamlessM4T T2T training — the model's vocabulary does not include Odia script tokens, so Odia batches are silently dropped in the collate function.

**Launch command**:
```bash
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_seamless.py --task asr

accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_seamless.py --task t2t
```

---

### 19.7 DeepSpeed ZeRO-3 Configuration

`finetune/ds_zero3.json` provides an alternative DeepSpeed ZeRO-3 configuration for Linux deployments where DeepSpeed is available. Key settings:

| Setting | Value | Purpose |
|---------|-------|---------|
| `zero_optimization.stage` | 3 | Shard weights + gradients + optimiser states |
| `overlap_comm` | true | Overlap gradient reduction with backward pass |
| `contiguous_gradients` | true | Reduce memory fragmentation |
| `reduce_bucket_size` | 5×10⁸ | All-reduce bucket size |
| `stage3_gather_16bit_weights_on_model_save` | true | Reconstruct full weights for checkpoint saving |
| `bf16.enabled` | true | bf16 mixed precision |
| `activation_checkpointing.number_checkpoints` | 4 | Activation recomputation segments |
| `scheduler.type` | WarmupDecayLR | Linear warmup + decay |

On Windows, FSDP (via Accelerate) is used instead because DeepSpeed's NCCL backend is not supported on Windows. The `ds_zero3.json` file is retained for Linux/cloud deployments.

---

### 19.8 Fine-Tuning Data Flow Summary

```
translation_memory/govt_tm.jsonl          ─┐
translation_memory/human_feedback.jsonl   ─┤ (×3 upweight)
                                           ├──► build_records()
datasets/parallel/<lang>/train.jsonl      ─┤
  (Samanantar + IN22 + OPUS-100)          ─┘
        │
        ▼
  ParallelDataset / TextDataset
  (FLORES-200 codes, grouped by lang pair)
        │
        ▼
  Accelerate FSDP + bf16
  (4 × A6000, gradient checkpointing)
        │
        ▼
  Dev loss evaluated each epoch
        │
        ▼
  checkpoints/indictrans/<direction>/best/
  checkpoints/seamless/asr/best/
  checkpoints/seamless/t2t/best/
        │
        ▼
  Pipeline loads automatically at inference
  (falls back to base model if absent)
```

---

*Prepared By: Sanjana MS*

---

## 20. CLI Reference & Scripts

### 20.1 Overview

The system exposes all pipeline functionality through a set of command-line scripts in `scripts/`. These scripts are the primary interface for automated batch processing, CI/CD integration, and operator-level maintenance tasks. The Gradio UI (`ui/app.py`) wraps the same underlying pipeline but the CLI scripts provide finer control and are suitable for scripted workflows.

All scripts are run from the project root directory and use `sys.path.insert` to resolve the `pipeline/` package without requiring installation.

---

### 20.2 `scripts/dub.py` — Video Dubbing CLI

The primary entry point for all video dubbing operations. Handles single-language, multi-language, full-course, and batch-video modes.

#### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--video FILE` | — | MP4 or MP3 source file to dub |
| `--batch-videos DIR` | — | Directory of videos; distributes across 4 GPUs |
| `--src CODE` | `eng` | Source language code |
| `--tgt CODE\|LIST\|all` | `hin` | Target language(s): single code, comma-separated, or `all` |
| `--output DIR` | `./output` | Output directory |
| `--course-id ID` | `course` | Course identifier (used in output filenames) |
| `--force` | false | Clear checkpoint and output, force re-run |
| `--gpu N` | 0 | GPU index for this process |
| `--num-gpus N` | auto | Number of GPUs for parallel dubbing |
| `--voice-clone` | false | Enable XTTS-v2 voice cloning (KB Tier 2) |
| `--reference-audio FILE` | — | Reference WAV for voice cloning |
| `--full` | false | Full course mode: dub + Excel + Word + QA report |
| `--metadata FILE` | — | Course metadata JSON |
| `--quiz FILE` | — | Quiz/assessment JSON |
| `--xlsx` | false | Export metadata as Excel |
| `--docx` | false | Export quiz as Word |
| `--qa-report` | false | Generate QA self-certification DOCX |
| `--upload-cbp` | false | Upload outputs to CBP portal after processing |
| `--run-monthly-report` | — | Generate monthly submission report |
| `--monthly-report FILE` | — | Results JSON for monthly report |
| `--month N` | 1 | Month number (1–12) |
| `--list-langs` | — | Print all 22 supported language codes and names |
| `--no-glossary` | false | Disable glossary injection |

#### Usage Examples

```bash
# Single language
python scripts/dub.py --video course.mp4 --src eng --tgt hin --course-id MyCourse

# All 22 languages, auto multi-GPU
python scripts/dub.py --video course.mp4 --src eng --tgt all --course-id MyCourse

# Force re-run (clears checkpoint + output)
python scripts/dub.py --video course.mp4 --src eng --tgt kan --force

# Explicit GPU count
python scripts/dub.py --video course.mp4 --src eng --tgt all --num-gpus 4

# Voice cloning (KB Tier 2)
python scripts/dub.py --video course.mp4 --src eng --tgt hin \
    --voice-clone --reference-audio speaker.wav

# Full course: dub + metadata Excel + quiz Word + QA cert + CBP upload
python scripts/dub.py --video course.mp4 --src eng --tgt all --full \
    --metadata meta.json --quiz quiz.json --course-id MyCourse --upload-cbp

# Translate metadata to Excel only (no video)
python scripts/dub.py --metadata meta.json --src eng --tgt all --xlsx

# Translate quiz to Word only (no video)
python scripts/dub.py --quiz quiz.json --src eng --tgt all --docx

# Batch: distribute a directory of videos across 4 GPUs
python scripts/dub.py --batch-videos ./input/ --src eng --tgt all

# Monthly submission report
python scripts/dub.py --run-monthly-report --monthly-report results.json --month 3
```

#### Execution Modes

The script has four mutually exclusive primary modes (`--video`, `--batch-videos`, `--list-langs`, `--run-monthly-report`). Within `--video` mode, the behaviour is further controlled by `--full`, `--metadata`, and `--quiz` flags:

- **Single/multi-language dub**: calls `pipeline.dub_course()` — returns per-language `DubbingResult` objects
- **Full course mode** (`--full`): calls `pipeline.process_course_full()` — orchestrates dub + metadata + quiz + QA cert + optional CBP upload in one call
- **Batch mode** (`--batch-videos`): spawns one subprocess per video, assigning `gpu_id = video_index % 4` via `CUDA_VISIBLE_DEVICES`
- **Metadata/quiz only**: calls `pipeline.translate_metadata()` or `pipeline.translate_quiz()` / `pipeline.export_metadata_xlsx()` / `pipeline.export_quiz_docx()` without touching audio

GPU auto-detection uses `torch.cuda.device_count()` and clamps to the available count. A single-GPU machine runs all languages sequentially on GPU 0.

---

### 20.3 `scripts/translate.py` — Text & Audio Translation CLI

Lightweight CLI for translation without video processing. Useful for testing translation quality, batch-translating text files, and audio transcription + translation.

#### Modes

| Mode | Flag | Description |
|------|------|-------------|
| Single text | `--text "..."` | Translate one string to one or more languages |
| Audio | `--audio FILE` | ASR transcribe then translate |
| Batch | `--batch FILE` | Translate a text file (one sentence per line or JSON array) |
| Course JSON | `--course FILE` | Translate a structured course JSON (title + sections) |

```bash
# Single text
python scripts/translate.py --text "Competency Framework" --src eng --tgt hin,tam,tel

# Audio transcription + translation
python scripts/translate.py --audio speech.wav --src hin --tgt ben

# Batch file (one sentence per line)
python scripts/translate.py --batch input.txt --src eng --tgt all

# Course JSON
python scripts/translate.py --course course.json --src eng --tgt hin,mar
```

Batch output is saved as `<input>.translated.json` alongside the input file. Course output is saved as `<course>_<lang>.json` per language.

---

### 20.4 `scripts/translation_memory.py` — Translation Memory Manager

Manages the three JSONL files in `translation_memory/`: `govt_tm.jsonl`, `human_feedback.jsonl`, and `correction_log.jsonl`. Can be used as both a CLI tool and a Python library (imported by `pipeline/translator.py`).

#### Record Schema

```json
{
  "id":       "<sha256[:16] of src+tgt_lang>",
  "src":      "source text",
  "tgt":      "translated text",
  "src_lang": "eng",
  "tgt_lang": "hin",
  "domain":   "government",
  "verified": true,
  "source":   "govt_doc|human_correction|auto",
  "added_at": "2024-01-01T00:00:00"
}
```

#### Lookup Priority

1. Exact match in human feedback (`human_feedback.jsonl`) — highest priority
2. Exact match in government TM (`govt_tm.jsonl`)
3. Fuzzy match across both stores using `SequenceMatcher` — threshold 0.85

#### CLI Commands

```bash
# Show per-language record counts
python scripts/translation_memory.py stats

# Add a verified government translation
python scripts/translation_memory.py add \
    --src "Competency Framework" --tgt "दक्षता ढांचा" --tgt-lang hin

# Record a human correction (logs wrong translation to audit trail)
python scripts/translation_memory.py correct \
    --src "..." --wrong "..." --correct "..." --tgt-lang hin

# Bulk import from JSON array file
python scripts/translation_memory.py import --file entries.json --type govt

# Look up a term
python scripts/translation_memory.py lookup --src "Competency" --tgt-lang hin

# Show last 20 correction audit log entries
python scripts/translation_memory.py log
```

#### Library Usage

```python
from scripts.translation_memory import TranslationMemory
tm = TranslationMemory()
match = tm.lookup("Competency Framework", "eng", "hin")
# Returns: {"tgt": "दक्षता ढांचा", "match_type": "exact_tm", "score": 1.0, ...}

# Export for fine-tuning (human feedback 3× upweighted)
records = tm.export_for_finetuning(tgt_lang="hin")
```

---

### 20.5 `scripts/clean_outputs.py` — Output Wiper

Removes all dubbed output files (`.mp4`, `.mp3`, `.srt`, `.vtt`, `.json`) from `output/` and all runtime job checkpoints from `checkpoints/jobs/`. Does not touch model weights, datasets, or fine-tune checkpoints.

```bash
python scripts/clean_outputs.py
# → Cleaned N files. Ready for fresh 22-lang run.
```

The equivalent Windows batch script `scripts/wipe_outputs.bat` performs the same operation using `del` commands.

---

### 20.6 `scripts/clean_and_run_all22.py` — Clean + Full Run

Combines output cleaning with a full 22-language dub in a single script. Auto-detects the source video by scanning the project root for `.mp4`/`.mp3` files (excluding `output/` and `tmp` paths). Useful for nightly re-runs or after a model update.

```bash
python scripts/clean_and_run_all22.py
```

Steps performed:
1. Auto-detect source video from project root
2. Delete all stale job checkpoints from `checkpoints/jobs/`
3. Delete all existing output files for that course
4. Instantiate `DubbingPipeline(use_glossary=True)` and call `dub_course()` with `force=True` for all 22 languages
5. Print per-language summary with quality scores

---

### 20.7 `scripts/test_pipeline.py` — Smoke Test

Verifies pipeline logic and module imports without loading any model weights. Runs 11 test groups covering all major pipeline components. Exits with code 0 on full pass, 1 on any failure.

```bash
python scripts/test_pipeline.py
```

| Test Group | What Is Verified |
|------------|-----------------|
| 1. lang_config | ALL_22 has 22 entries; all codes present in INDIC_TRANS2_CODES, SEAMLESS_CODES, NLLB_CODES |
| 2. logger | `get_logger()` returns a logger; `log.info()` does not crash |
| 3. retry + checkpoint | Retry decorator retries and succeeds; `JobCheckpoint` set/get/flush/clear lifecycle |
| 4. quality scorer | `score_segment()` returns dict with score in [0,1]; transliteration detection true/false positives |
| 5. glossary | `protect_terms()` replaces glossary tokens; `restore_terms()` recovers originals |
| 6. subtitles | SRT has correct entry count; VTT starts with `WEBVTT`; empty segments skipped |
| 7. lang_detect | `fw_lang_to_internal()` maps faster-whisper codes; Bodo always returns `bod` |
| 8. DubbingPipeline | Instantiates with lazy-None models; PM speech exclusion detected; input validation errors raised |
| 9. Translator | Instantiates with lazy-None models; same-language passthrough returns `engine=passthrough` |
| 10. datasets | All 22 `train.jsonl` files present; hin/tam/ben have non-zero record counts |
| 11. model weights | IndicTrans2 (3 directions), SeamlessM4T (2 shards), faster-whisper, Parler-TTS paths exist |

The smoke test is designed to run in under 10 seconds on any machine, making it suitable as a pre-flight check before a long dubbing run.

---

### 20.8 `scripts/download_models.py` — Model Downloader

Downloads all required model weights from HuggingFace Hub using `snapshot_download`. Requires `HF_TOKEN` in the environment. Each model is saved to a fixed local path; the download is skipped if the path already exists.

```bash
python scripts/download_models.py
```

Models downloaded and their target paths are detailed in Section 18.3. The script also prints instructions for promoting Parler-TTS Large to primary after comparison testing.

---

### 20.9 `scripts/download_datasets.py` — Dataset Downloader

Downloads all parallel text and audio datasets from HuggingFace Hub. Skips datasets whose local directory already exists and is non-empty. Logs results to `logs/dataset_download.log`.

```bash
python scripts/download_datasets.py
```

Estimated total download: ~125 GB (audio ~95 GB, text ~30 GB). See Section 19.2 for the full dataset inventory.

---

### 20.10 `scripts/check_gaps.py` — Coverage Checker

Prints a formatted coverage report for all 22 languages across both parallel text and audio datasets. Flags missing splits, zero-record files, and stale folder names (`odi`→`ory`, `dog`→`doi`).

```bash
python scripts/check_gaps.py
```

Output includes per-language train/dev/test line counts, audio source detection (FLEURS, Common Voice, IndicSUPERB, Shrutilipi, IndicTTS, Bodo ASR), and a summary of gaps requiring action.

---

### 20.11 `scripts/build_asr_index.py` — ASR Index Builder

Scans downloaded audio datasets and writes `datasets/asr/<lang>/dataset_info.json` for each of the 22 languages. Records the best available audio source (priority: FLEURS > Common Voice > Bodo ASR > IndicSUPERB), split paths, script, sampling rate, and a `finetune_ready` boolean. Writes a master `datasets/asr/index.json` summarising coverage.

```bash
python scripts/build_asr_index.py
```

Run once after `download_datasets.py`. Safe to re-run — overwrites existing `dataset_info.json` files.

---

*Prepared By: Sanjana MS*

---

## 21. Quality Assurance & Compliance

### 21.1 Overview

Quality assurance in the KB Translation System operates at three levels: automated per-segment scoring during the pipeline run, post-pipeline human review via the UI, and formal self-certification documents submitted with each delivery. This section documents the automated scoring system in detail, the compliance checks mandated by the KB tender, and the supporting modules that enforce quality at the text, audio, and document levels.

---

### 21.2 Automated Quality Scoring

Every translated segment is scored on a 0.0–1.0 scale by `pipeline/quality.py`. Three scoring methods are available:

| Method | Function | When Used |
|--------|----------|-----------|
| Heuristic | `score_segment()` | Every segment, always |
| ChrF (n=6, β=2) | `chrf_score()` | Same-script pairs only |
| Back-translation | `back_translation_score()` | Full scoring mode (`score_segment_full()`) |

#### 21.2.1 Heuristic Scorer

`score_segment()` starts at 1.0 and applies eight penalty checks:

| Check | Penalty | Trigger |
|-------|---------|---------|
| Length ratio | −0.25 | `tgt_words / src_words` < 0.3 or > 4.0 |
| Source language leakage | −0.30 | Native script chars < 50% of all alphabetic chars in output |
| Repetition loop | −0.35 | Four consecutive identical words |
| Untranslated (exact copy) | −0.40 | `translation == source` for non-English target |
| Untranslated (Latin output) | −0.35 | >80% Latin chars in output for a non-Latin target script |
| Too short | −0.30 | Source ≥ 5 words but translation < 2 words |
| Transliteration detected | −0.35 | Latin ratio > 60% in a non-Latin target (KB tender §3.2) |
| Missing numbers | −0.20 | Numeric tokens present in source but absent in translation |

Penalties are cumulative; the final score is clamped to `max(0.0, score)`. Any flags are logged at WARNING level with the first 60 characters of the translation.

#### 21.2.2 ChrF Score

`chrf_score()` computes character n-gram F-score with n=6 and β=2 (recall-weighted, standard for MT evaluation). It is only applied when source and target share the same script — cross-script pairs (e.g. English→Hindi) would produce a meaningless score of 0.0 and are skipped. The ChrF value is stored in the segment result dict but does not directly modify the heuristic score; it is reported in the metadata JSON for human reviewers.

#### 21.2.3 Back-Translation Score

`back_translation_score()` translates the output back to the source language and measures word-level overlap with the original source. A module-level singleton (`_bt_translator`) is injected by the pipeline via `set_shared_translator()` to reuse the existing `Translator` instance rather than loading a second model into GPU memory.

If back-translation overlap < 0.25, a `low_back_translation_<score>` flag is added and the heuristic score is reduced by a further −0.15.

Back-translation is only used in `score_segment_full()`, which is called during the final quality check step of the pipeline. The lighter `score_segment()` is used for per-segment gating during translation to avoid the latency of a second translation pass.

#### 21.2.4 Quality Gates

| Score Range | Status | Pipeline Action |
|-------------|--------|----------------|
| ≥ 0.55 | ✅ Pass | Accepted, sent to TTS |
| 0.30–0.55 | ⚠ Review | Flagged in metadata; sent to TTS but marked for human review |
| < 0.30 | ❌ Failed | `text = ""` — segment is silenced; no wrong-language audio produced |

The reject threshold (< 0.30) enforces the KB tender requirement that no incorrect-language audio reaches the learner. Silenced segments produce a gap in the dubbed audio at the original timestamp, which is preferable to audible mistranslation.

#### 21.2.5 Batch Scoring and Summary

`score_batch()` applies either `score_segment` or `score_segment_full` across a list of source/translation pairs. `review_summary()` aggregates results into:

```json
{
  "total": 120,
  "avg_score": 0.82,
  "avg_chrf": 0.0,
  "avg_back_translation": 0.71,
  "needs_review": 14,
  "failed": 3,
  "pass_rate": 0.883
}
```

This summary is written to the `_metadata.json` output file for each language and is displayed in the QA Certificate DOCX.

---

### 21.3 Transliteration Detection

`detect_transliteration()` enforces KB tender §3.2, which prohibits mere transliteration (writing source-language words in the target script's phonetic equivalent) as a substitute for translation.

The function counts native-script characters versus Latin characters in the output. If Latin characters exceed 60% of all alphabetic characters in a non-Latin target language, transliteration is flagged. Script ranges are defined per language:

| Script | Languages |
|--------|-----------|
| Devanagari (U+0900–U+097F) | hin, mar, nep, mai, san, doi, kok, bod |
| Bengali (U+0980–U+09FF) | ben, asm, mni |
| Gujarati (U+0A80–U+0AFF) | guj |
| Gurmukhi (U+0A00–U+0A7F) | pan |
| Odia (U+0B00–U+0B7F) | ory |
| Tamil (U+0B80–U+0BFF) | tam |
| Telugu (U+0C00–U+0C7F) | tel |
| Kannada (U+0C80–U+0CFF) | kan |
| Malayalam (U+0D00–U+0D7F) | mal |
| Arabic (U+0600–U+06FF) | urd, kas, snd |
| Ol Chiki (U+1C50–U+1C7F) | sat |

---

### 21.4 Subtitle Generation & Compliance

`pipeline/subtitles.py` generates SRT and VTT subtitle files as required by KB tender §4 (Financial Schedule — sub-titling/captioning).

#### SRT Generation

`generate_srt()` produces RFC 4180-compliant SRT files with:
- UTF-8 BOM encoding (`utf-8-sig`) for maximum player compatibility
- Windows-style CRLF line endings
- Embedded newlines within segment text collapsed to spaces (prevents timestamp line corruption)
- Empty segments silently skipped (no blank subtitle entries)
- Sequential 1-based index numbering

#### VTT Generation

`generate_vtt()` produces WebVTT files with:
- `WEBVTT` header on the first line
- Timestamp format `HH:MM:SS.mmm` (comma replaced with period from SRT format)
- UTF-8 encoding without BOM

#### Subtitle Embedding

Two embedding modes are supported:

- **Soft embed** (`embed_subtitles_soft()`): SRT is muxed as a selectable subtitle track using `mov_text` codec. The viewer can toggle subtitles on/off. This is the default mode used by `video_processor.py`.
- **Hard burn** (`burn_subtitles()`): SRT is rendered into the video stream using ffmpeg's `subtitles=` filter. Used as fallback if soft embed fails, and available as an explicit option. Windows path backslashes are escaped for the ffmpeg filter string.

---

### 21.5 Language Detection

`pipeline/lang_detect.py` provides per-segment language detection using the `lingua-language-detector` library (fully offline, no API).

#### faster-whisper Code Mapping

`fw_lang_to_internal()` converts faster-whisper's ISO 639-1 codes (e.g. `hi`, `bn`, `ta`) to the system's internal 3-letter codes (e.g. `hin`, `ben`, `tam`). This is used after ASR to tag each segment with its detected source language.

#### Segment Tagging

`tag_segments()` adds a `detected_lang` field to each segment dict. Two cases are handled:

- **Lingua-unsupported languages** (bod/doi/kas/kok/mni/sat/snd): lingua cannot reliably detect these seven low-resource languages. For these, `detected_lang` is always set to `assumed_lang` without calling the detector.
- **Supported languages**: lingua detects from a vocabulary of 16 Indian languages + English. On detection failure, the fallback is `assumed_lang` (not `"eng"`), preventing false English tagging of Indic content.

The detector is a module-level singleton loaded lazily on first call. Supported lingua language names are mapped to internal codes via `_LINGUA_TO_INTERNAL`.

---

### 21.6 Glossary Enforcement

`pipeline/glossary.py` ensures consistent translation of domain-specific terminology (government policy terms, iGOT platform names, administrative vocabulary) across all segments and all courses.

#### Storage

Glossaries are stored as 22 JSON files under `glossary/<lang_code>.json`:
```json
{
  "igot": "iGOT",
  "karmayogi": "कर्मयोगी",
  "competency framework": "दक्षता ढांचा"
}
```
Keys are stored lowercase; matching is case-insensitive.

#### Two-Phase Application

Glossary terms are applied in two phases to avoid interference with the translation model:

1. **Pre-translation protection** (`protect_terms()`): Source terms matching glossary entries are replaced with `__GLOSS_N__` placeholders before the text is sent to the translation engine. This prevents the model from translating or distorting protected terms.

2. **Post-translation restoration** (`restore_terms()`): Placeholders are replaced with the glossary's target-language term after translation.

A third cleanup pass (`apply()`) handles cases where the model emits placeholder artifacts literally (e.g. `_ _ GLOSS _ 0 _ _`) or stray script characters (Gurmukhi/Malayalam prefix characters) — these are stripped by regex before the final output is accepted.

---

### 21.7 Document Translation Quality

`pipeline/doc_extractor.py` provides format-preserving DOCX translation via `translate_docx()`. Quality considerations specific to document translation:

- **Run-level granularity**: Each paragraph is translated as a single unit (all runs concatenated), then the result is placed in the first run with subsequent runs cleared. This preserves bold/italic/underline boundaries at the paragraph level while avoiding the fragmentation that would occur if each run were translated independently.
- **Placeholder protection bypass**: Document batch mode in `translator.py` bypasses the format-token placeholder protection layer (`__FMT0__` etc.) because DOCX paragraphs do not contain Python format strings or Jinja templates.
- **Table cell translation**: Each cell's paragraphs are translated independently, preserving table structure.
- **Header/footer coverage**: All six header/footer variants (default, even-page, first-page for both header and footer) are translated, ensuring no untranslated text appears in page margins.
- **Hyperlinks**: The text content of hyperlinks is translated; the URL target is preserved unchanged.
- **Images**: Inline images are copied unchanged (no OCR or image translation).

---

### 21.8 Tender Compliance Checks

The following KB tender requirements are enforced programmatically:

| Tender Clause | Requirement | Implementation |
|---------------|-------------|----------------|
| §3.1 | PM/President speeches and YouTube-only content must not be dubbed | `should_skip_translation()` in `dubbing_pipeline.py` — keyword detection in ASR transcript |
| §3.1 | PDF translation blocked | `doc_extractor.py` raises `ValueError` for `.pdf` input to `translate_docx()` |
| §3.2 | No mere transliteration | `detect_transliteration()` in `quality.py` — flags and penalises Latin-dominant output |
| §4.2 | CBP portal upload | `cbp_uploader.py` — REST API upload with 3-attempt retry |
| §5.1B | Dubbed output must not exceed original duration by >20% | Duration ratio check in `dubbing_pipeline.py` — logs WARNING if ratio > 1.20 |

The exclusion detection in `should_skip_translation()` scans the ASR transcript for phrases such as "Prime Minister", "President of India", "speech by", and "YouTube" to identify content that must not be dubbed per §3.1. A false-positive guard ensures that acronyms like "PMMY" (Pradhan Mantri Mudra Yojana) do not trigger the exclusion.

---

*Prepared By: Sanjana MS*

---

## 22. Reliability, Observability & Integration Modules

### 22.1 Overview

This section documents the cross-cutting infrastructure modules that provide crash resilience, structured logging, optional LLM post-editing, voice cloning, CBP portal integration, and human review certification. These modules are consumed by the core pipeline but are independently testable and replaceable.

---

### 22.2 Retry Decorator (`pipeline/retry.py`)

#### 22.2.1 `retry` Decorator

A general-purpose retry decorator with exponential backoff, applied to any function that may fail transiently (network calls, GPU OOM, file I/O races).

```python
@retry(max_attempts=3, delay=2.0, exceptions=(Exception,))
def upload_file(...): ...
```

Backoff formula: `wait = delay × 2^(attempt − 1)`. For `delay=2.0`:
- Attempt 1 fails → wait 2.0 s
- Attempt 2 fails → wait 4.0 s
- Attempt 3 fails → raise last exception

All retry events are logged at WARNING level; final failure is logged at ERROR.

#### 22.2.2 `JobCheckpoint`

Persists per-segment translation results to `checkpoints/jobs/<job_id>.json` so that a crashed job resumes from the last completed segment rather than restarting from zero.

**Data structure**:
```json
{
  "completed": {"0": {"text": "...", "score": 0.82}, "1": {...}},
  "meta": {"src_lang": "eng", "tgt_lang": "hin", "video_path": "..."}
}
```

**Key behaviours**:

| Method | Description |
|--------|-------------|
| `mark_done(seg_id, result)` | Records a completed segment in memory |
| `flush()` | Atomically writes to disk (write to `.tmp` then `rename`) |
| `is_done(seg_id)` | Returns True if segment already completed |
| `get_done(seg_id)` | Returns the stored result dict for a completed segment |
| `set_meta(key, value)` | Stores job-level metadata (source path, language codes) |
| `clear()` | Deletes the checkpoint file and resets in-memory state |

**Atomic write**: `flush()` writes to `<job_id>.tmp` then calls `Path.replace()` (atomic on POSIX; near-atomic on Windows NTFS). This prevents a partial write from corrupting the checkpoint if the process is killed mid-flush.

**Thread safety**: All reads and writes are protected by an instance-level `threading.Lock()`. Multiple threads translating different segments of the same job can safely call `mark_done()` concurrently.

**Lifecycle in the pipeline**:
1. `JobCheckpoint` created at job start with `job_id = f"{course_id}_{tgt_lang}"`
2. Each completed segment calls `mark_done()` + `flush()`
3. On resume, `is_done()` skips already-completed segments
4. On successful job completion, `clear()` removes the checkpoint file
5. `--force` flag calls `clear()` before starting, forcing a full re-run

---

### 22.3 Structured Logging (`pipeline/logger.py`)

`get_logger(name, log_file)` returns a Python `logging.Logger` configured with two handlers:

| Handler | Format | Level | Destination |
|---------|--------|-------|-------------|
| File | JSON lines | DEBUG | `logs/<log_file>` (default: `pipeline.log`) |
| Console | `[module] message` | INFO | stdout (UTF-8 safe on Windows) |

#### JSON Line Format

Every log entry is a single JSON object:
```json
{"ts": "2024-03-15T14:22:01", "level": "WARNING", "module": "quality", "msg": "Quality flags [hin] score=0.28 chrf=0.0: ['transliteration_detected'] | namaste duniya aap kaise"}
```

Exception tracebacks are included as `"exc"` field when `exc_info=True`.

#### File Rotation

`RotatingFileHandler` with `maxBytes=10 MB`, `backupCount=5` — up to 50 MB of log history retained across `pipeline.log`, `pipeline.log.1` … `pipeline.log.5`.

#### Audit Log

The pipeline writes a separate `logs/audit.log` for job-level events (start, success, failure) using the same JSON format. This provides a tamper-evident record for KB tender compliance without mixing operational debug logs with the audit trail.

#### Windows UTF-8 Safety

The console handler wraps `sys.stdout.buffer` in `io.TextIOWrapper(encoding='utf-8', errors='replace')` to prevent `UnicodeEncodeError` when printing Indic script characters on Windows terminals with non-UTF-8 code pages.

---

### 22.4 LLM Post-Edit Enhancement (`pipeline/llm_enhancer.py`)

An optional post-processing step that sends machine-translated segments to a large language model for fluency and naturalness improvement. The pipeline runs fully offline without this module; it activates only when an API key is present in `.env`.

#### Provider Detection

`LLMEnhancer._detect_provider()` checks environment variables in priority order:

| Priority | Variable | Model |
|----------|----------|-------|
| 1 | `GROQ_API_KEY` | llama-3.3-70b-versatile (free tier) |
| 2 | `GEMINI_API_KEY` | gemini-1.5-flash |
| 3 | `OPENROUTER_API_KEY` | meta-llama/llama-3.3-70b-instruct:free |

All three providers use the same prompt templates and return the same output format. The provider is re-detected on each call (not cached at init), so a key added to `.env` at runtime takes effect without restarting.

#### Single-Segment Enhancement

`enhance()` sends one source + translation pair with the prompt:

> *Post-edit the machine translation below to make it natural, fluent, and accurate. Keep all proper nouns, scheme names, and numbers exactly as-is. Output ONLY the corrected translation, nothing else.*

Temperature is set to 0.1 for deterministic, conservative edits. On any failure, the original machine translation is returned unchanged.

#### Batch Enhancement

`enhance_batch()` sends all segments for a language in a single LLM call using a JSON array prompt, reducing API round-trips. The response is parsed by finding the first `[` and last `]` in the output and JSON-decoding the substring. If the parsed array length does not match the input, the raw translations are returned as fallback.

All three provider calls are decorated with `@retry(max_attempts=3, delay=1.0)` for transient network failures.

---

### 22.5 Voice Cloning (`pipeline/voice_clone.py`)

Voice cloning is a KB Tier 2 pricing feature that synthesises dubbed speech in the original speaker's voice rather than a generic TTS voice. It uses Coqui XTTS-v2 (Apache 2.0 licence, fully offline).

#### Supported Languages

XTTS-v2 supports 10 Indian languages for voice cloning:

| Code | Language | XTTS Code |
|------|----------|-----------|
| hin | Hindi | hi |
| ben | Bengali | bn |
| guj | Gujarati | gu |
| mar | Marathi | mr |
| tam | Tamil | ta |
| tel | Telugu | te |
| kan | Kannada | kn |
| mal | Malayalam | ml |
| pan | Punjabi | pa |
| urd | Urdu | ur |

Languages outside this set fall back to the standard TTS engine (Parler-TTS or MMS-TTS).

#### Speaker Embedding

`extract_speaker_embedding()` calls `model.get_conditioning_latents()` with the reference audio path and returns a dict containing `gpt_cond_latent` and `speaker_embedding` tensors. This is computed once per course via `synthesize_segments_with_clone()` and reused for all segments, avoiding the latency of re-computing the embedding for every segment.

A minimum of 6 seconds of clean reference audio is recommended for reliable voice cloning.

#### Synthesis

`synthesize_with_clone()` accepts either a pre-computed embedding dict (fast path, used for batch processing) or a reference audio path (slow path, recomputes embedding). Output is written as a 24 kHz WAV file using `soundfile`.

#### Activation

Voice cloning is activated via `--voice-clone` and `--reference-audio` flags in `dub.py`, or via the "Voice Clone" checkbox in the Gradio UI. When active, the TTS step in `dubbing_pipeline.py` routes to `VoiceCloner.synthesize_segments_with_clone()` instead of the standard TTS engine.

---

### 22.6 CBP Portal Upload (`pipeline/cbp_uploader.py`)

Implements the upload requirement of KB tender §4.2 — all translated course assets must be submitted to the iGOT Karmayogi CBP portal at `https://cbp.igotkarmayogi.gov.in`.

#### Authentication

`login()` posts credentials to `/api/user/v1/login` and stores the returned Bearer token in the session headers. Credentials are read from `CBP_USERNAME` and `CBP_PASSWORD` environment variables (set in `.env`). If credentials are absent, a warning is logged and upload is skipped gracefully.

#### Asset Upload

`_upload_asset()` posts a multipart form to `/api/content/v1/upload` with:
- `file`: binary file content
- `courseId`: course identifier
- `language`: target language code
- `assetType`: `video` | `audio` | `metadata` | `assessment` | `subtitle`

Three upload attempts are made with increasing delays (5 s, 10 s) before returning a failure dict. All attempts are logged.

#### Course Package Upload

`upload_course_package()` scans an output directory for all assets matching the language code and uploads them in one call. File patterns matched:

| Pattern | Asset Type |
|---------|-----------|
| `*_{lang}.mp4` | video |
| `*_{lang}.mp3` | audio |
| `*_{lang}*.xlsx` | metadata |
| `*_{lang}*.docx` | assessment |
| `*_{lang}.srt` | subtitle |
| `*_{lang}.vtt` | subtitle |

#### Submission Report

`generate_submission_report()` writes a JSON report to disk summarising all upload results across all languages and courses. This report is retained for KB tender audit purposes.

---

### 22.7 Human Review Module (`ui/reviewer.py`)

A pure UI logic module (no pipeline imports) that enables native-language expert review of pipeline output before KB submission.

#### Data Flow

```
*_metadata.json (pipeline output)
        │
        ▼
load_metadata()  →  segments list + raw_meta dict
        │
        ▼
load_review()    →  overlay saved decisions (resume support)
        │
        ▼
[Reviewer makes decisions: approved / corrected / rejected]
        │
        ▼
save_review()    →  *_review.json (sidecar file, same directory)
        │
        ▼
export_certificate()  →  *_qa_cert.docx (KB submission)
```

#### Sidecar File Pattern

Review decisions are persisted to a sidecar JSON file named `<course_id>_<lang>_review.json` alongside the metadata file. This allows review sessions to be interrupted and resumed without data loss. The sidecar stores only the delta (segment ID, decision, corrected text) — the full metadata is always read from the original pipeline output.

#### Certificate Contents

`export_certificate()` generates a DOCX with:

- **Summary table** (10 rows): course ID, target language, source language, reviewer name, review date, total/approved/corrected/rejected/pending counts
- **Segment-level table**: sequential index, source text (truncated to 200 chars), AI translation, corrected text, decision — with colour-coded decision cells (green/orange/red)
- **Declaration paragraph**: formal certification statement referencing KB RFB IN-KBL-543730-NC-RFB, with reviewer name, date, and signature line

#### Segment Display

`segments_to_display()` converts the segments list to a list-of-lists for `gr.Dataframe` rendering in the Gradio UI. Each row includes: segment ID, timestamp range, source text, AI translation, corrected text, quality score, flags, AI-flagged indicator (🚩), and current decision.

`review_stats()` returns a single formatted string summarising totals for the status bar: `Total: N | ✅ Approved: N | ✏️ Corrected: N | ❌ Rejected: N | ⏳ Pending: N | 🚩 AI-flagged: N`.

---

*Prepared By: Sanjana MS*

---

## 23. ASR & Translation Engine Deep Dive

### 23.1 Overview

This section provides a detailed technical account of the two most complex inference modules in the pipeline: the ASR engine (`pipeline/asr.py`) and the translation engine (`pipeline/translator.py`). Both modules are designed for fully offline operation, handle all 22 scheduled Indian languages, and implement multiple layers of output cleaning and quality protection.

---

### 23.2 ASR Engine (`pipeline/asr.py`)

#### 23.2.1 Model Loading

The ASR engine uses faster-whisper large-v3 in CTranslate2 format. Model loading follows a three-path priority:

1. `models/indic_asr/model.bin` — local CT2 weights (fastest, no network)
2. `models/indic_asr/models--Systran--faster-whisper-large-v3/snapshots/<hash>` — HuggingFace Hub snapshot
3. `"large-v3"` — auto-download from HuggingFace Hub (requires internet)

Compute type is `float16` on GPU, `int8` on CPU. `num_workers=1` is hardcoded because `num_workers > 1` causes deadlocks on Windows (no `fork` support). `cpu_threads` is capped at 8.

GPU assignment is read from the `PIPELINE_GPU` environment variable, set by `dub_course_parallel()` when distributing jobs across multiple GPUs.

#### 23.2.2 Transcription Parameters

`transcribe_segments()` calls faster-whisper with the following key parameters:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `beam_size` | 5 | Beam search width — balances accuracy vs speed |
| `vad_filter` | True | Voice activity detection — skips silent regions |
| `vad_parameters.min_silence_duration_ms` | 500 | Minimum silence gap to split segments |
| `word_timestamps` | True | Per-word timestamps for accurate segment merging |
| `condition_on_previous_text` | False | Prevents hallucination loops across segments |
| `temperature` | [0.0, 0.2, 0.4] | Multi-temperature fallback — breaks repetition loops |
| `no_speech_threshold` | 0.6 | Suppress segments with low speech probability |
| `log_prob_threshold` | −1.0 | Suppress low-confidence segments |
| `compression_ratio_threshold` | 2.4 | Suppress repetitive/hallucinated output |

`condition_on_previous_text=False` is the primary hallucination guard. When enabled, Whisper conditions each segment on the previous segment's text, which can cause it to repeat or continue hallucinated content. Disabling this makes each segment independent.

The multi-temperature fallback `[0.0, 0.2, 0.4]` means faster-whisper first attempts greedy decoding (temperature=0.0), then falls back to stochastic sampling at 0.2 and 0.4 if the output fails the compression ratio or log-probability thresholds.

#### 23.2.3 Language Handling

When `lang="auto"` is passed, `fw_lang` is set to `None` and faster-whisper auto-detects the language from the first 30 seconds of audio. After consuming the segment generator, the detected language code is converted from faster-whisper format (e.g. `"hi"`) to internal format (e.g. `"hin"`) via `fw_lang_to_internal()`.

For explicit language codes, `FW_LANG_CODES` maps internal 3-letter codes to faster-whisper's ISO 639-1/3 codes. All 22 scheduled Indian languages are supported natively by large-v3 — no per-language adapter swaps are required.

#### 23.2.4 Segment Merging

Raw faster-whisper output produces short, often incomplete segments. `_merge_segments()` merges them into natural sentence-length chunks using three rules:

- **Minimum**: keep merging until ≥ 6 words AND ≥ 1.5 seconds
- **Maximum**: never exceed 12 seconds in a single segment
- **Sentence boundary**: flush immediately on `.`, `!`, `?`, `。` if minimum conditions are met

This produces segments of 6–12 words and 1.5–12 seconds — suitable for both translation (enough context for accurate translation) and TTS (fits within a timestamp slot without excessive speed-up).

#### 23.2.5 Post-Processing

After merging, three post-processing steps are applied:

1. **Nastaliq normalisation** (urd/kas/snd only): `_normalize_nastaliq()` replaces Arabic-script characters that ASR models commonly output with their Urdu/Nastaliq equivalents — Arabic kaf (ك) → Urdu kaf (ک), Arabic ya (ي) → Urdu ya (ی), ta marbuta (ة) → ta (ت), etc.

2. **Hallucination stripping**: `_strip_hallucinations()` removes known Whisper hallucination words that appear at segment boundaries when audio is unclear — words like "Wanner", "Whener", "Viengore", "Gonna", "Wanna" that Whisper produces when it cannot decode the audio but is forced to output something. After stripping, the first character is re-capitalised.

3. **Empty segment removal**: segments with empty text after post-processing are discarded.

---

### 23.3 Translation Engine (`pipeline/translator.py`)

#### 23.3.1 Architecture

The `Translator` class implements a three-engine fallback chain with lazy model loading, three token protection layers, a 10-rule final quality check, and score-based engine selection for low-resource languages.

All models are loaded lazily on first use and cached as instance attributes. A `threading.Lock()` prevents concurrent loads of the same model direction.

#### 23.3.2 Token Protection Layers

Three independent protection layers are applied in sequence before any text reaches a translation engine, and restored in reverse order after:

**Layer 1 — Format tokens** (`_protect_format_tokens()`):

Replaces Python/Jinja/shell template placeholders with `__FMT0__`, `__FMT1__`, … Patterns protected:
- `{{variable}}` — Jinja/Mustache double-brace
- `{name}`, `{obj.attr}`, `{list[0]}` — Python format strings
- `${value}` — shell/JS template literals
- `%s`, `%d`, `%(key)s` — printf-style
- `<USER_NAME>`, `<PLACEHOLDER>` — XML-style uppercase placeholders

**Layer 2 — Non-translatable tokens** (`_protect_nontranslatable()`):

Replaces tokens that must pass through unchanged with `__NT0__`, `__NT1__`, … Patterns protected: URLs (`https://`, `www.`), email addresses, Unix/Windows file paths, filenames with known extensions (`.py`, `.mp4`, `.docx`, etc.), backtick code spans, shell commands (`pip install`, `python`, `git`), hashtags, @mentions, and all-caps identifiers with digits.

A segment is classified as fully non-translatable if ≥ 90% of its non-space characters belong to non-translatable tokens — such segments are returned unchanged without calling any engine.

**Layer 3 — Factual tokens** (`_protect_factual_tokens()`):

Replaces numbers, dates, times, measurements, and currency with `__F0__`, `__F1__`, … Patterns protected: currency (₹/$€£¥), dates (DD/MM/YYYY, ISO, month-name), times (HH:MM), percentages, measurements (km, kg, MW, GB, etc.), bare 4-digit years, and all other numeric tokens.

After restoration, `_verify_factual_tokens()` checks that every source factual token appears in the translation. Any missing tokens are appended to the end of the translation to ensure no fact is lost.

#### 23.3.3 Engine Routing

The routing logic in `translate()` follows this decision tree:

```
Is src_lang == tgt_lang?
  → passthrough (score=1.0)

Is segment fully non-translatable?
  → passthrough_nontranslatable (score=1.0)

Is tgt_lang in _SEAMLESS_FIRST (empty set)?
  → try SeamlessM4T first

Is src/tgt in _NLLB_FIRST (kas, snd)?
  → NLLB primary
  → SeamlessM4T second opinion (pick higher score if Δ > 0.05)

Is src/tgt in _PIVOT_LANGS (mni, sat)?
  → IndicTrans2 via Hindi pivot
  → If pivot score < 0.50: try SeamlessM4T, pick higher

Otherwise (all other 18 languages):
  → IndicTrans2 (en_indic / indic_en / indic_indic)
  → SeamlessM4T fallback
  → NLLB-200 final fallback
```

The `_SEAMLESS_FIRST` set is currently empty — bod and doi were moved to use IndicTrans2 directly after domain datasets became available.

#### 23.3.4 IndicTrans2 Batch Translation

`_translate_indic_trans2_batch()` is the primary translation path for the 18 standard languages. Key implementation details:

- **Direction selection**: `en_indic` if source is `eng_Latn`, `indic_en` if target is `eng_Latn`, `indic_indic` otherwise
- **Tokenizer loading**: `IndicTransTokenizer` is loaded directly from the model's local `tokenization_indictrans.py` module via `importlib` to avoid a kwarg conflict with `AutoTokenizer`
- **Repetition penalty**: 1.1 for short segments (avg length < 40 chars), 1.2 for longer segments — Indic function words are legitimately repeated and get wrongly penalised at higher values
- **Beam search**: 5 beams, `no_repeat_ngram_size=3`, `max_new_tokens=512`
- **Completeness guard** (in `translate_batch()`): if output length ≠ input length, raises `RuntimeError`; if any individual translation is empty for a non-empty source, retries that segment via single `_translate_indic_trans2()`

#### 23.3.5 Hindi Pivot (`_pivot_via_hindi()`)

Used for Manipuri (mni) and Santhali (sat) — two languages with insufficient direct parallel data for reliable IndicTrans2 training:

```
source (mni/sat) → IndicTrans2 → Hindi → IndicTrans2 → target
```

If source is already Hindi, step 1 is skipped. If target is Hindi, step 2 is skipped. After pivot translation, if the quality score is < 0.50, SeamlessM4T is tried as an alternative and the higher-scoring output is used.

#### 23.3.6 Output Cleaning Pipeline

After every engine call, the following cleaning steps are applied in order:

| Step | Function | Purpose |
|------|----------|---------|
| 1 | `_clean_unk()` | Remove `<unk>`, `[unk]`, `(unk)` token variants |
| 2 | `_clean_mixed_lang()` | Strip HTML tags; remove foreign-script word runs |
| 3 | `_restore_nontranslatable()` | Restore `__NT__` placeholders |
| 4 | `_restore_factual_tokens()` | Restore `__F__` placeholders |
| 5 | `_verify_factual_tokens()` | Append any missing numeric tokens |
| 6 | `_restore_format_tokens()` | Restore `__FMT__` placeholders |
| 7 | `_naturalise()` | Fix repeated words, space-before-punctuation, multi-punctuation |
| 8 | `_final_quality_check()` | 10-rule gate (see §23.3.7) |
| 9 | `glossary.apply()` | Enforce glossary terms (applied last, never overwritten) |

#### 23.3.7 Foreign Script Stripping

`_clean_mixed_lang()` uses pre-built per-language regex patterns (`_FOREIGN_WORD_RE`) to strip entire word runs written in a script that does not belong to the target language. For example, if a Hindi translation contains a run of Tamil characters, those characters are replaced with a space.

The regex is built at import time for all 22 languages by `_build_foreign_word_re()`. It identifies all Unicode script blocks that are NOT part of the target language's allowed script ranges and builds a character class matching runs of those characters. The `_ALWAYS_ALLOWED` list ensures that digits, punctuation, currency symbols, and the Devanagari danda (।) are never stripped regardless of target language.

#### 23.3.8 Final Quality Check (10 Rules)

`_final_quality_check()` is the last gate before a translation is returned. It verifies and auto-corrects where possible:

| Rule | Check | Auto-correction |
|------|-------|----------------|
| 1. Accuracy | Non-empty output for non-empty source | Returns source text as last resort |
| 2. Completeness | Translation ≥ 20% length of source | Flags `fqc:suspiciously_short` |
| 3. Grammar | Sentence-initial lowercase after `. ` (English only) | Capitalises first letter |
| 4. Fluency | 3+ consecutive identical punctuation | Collapses to single |
| 5. Consistency | All `__FMT__`/`__NT__`/`__F__` placeholders restored | Force-restores any remaining |
| 6. Corruption | U+FFFD replacement char, null bytes | Removes |
| 7. Placeholder-free | Any `__WORD__` pattern remaining | Strips via regex |
| 8. Mixed-lang | (Skipped — technical terms intentionally kept in Latin) | — |
| 9. Formatting | Multiple spaces, leading/trailing whitespace | Normalises |
| 10. Professional | `[UNK]`, `[PAD]`, `[BOS]`, `[EOS]`, `[MASK]` tokens | Strips |

Any flags raised by the FQC are merged into the quality score dict and cause `needs_review=True`.

#### 23.3.9 Document Batch Mode

`translate_document_batch()` is a separate code path for DOCX translation that bypasses all three protection layers. Document paragraphs do not contain Python format strings or shell commands, and applying placeholder protection to them causes hallucination (the model sees `__FMT0__` as a word to translate). Only `_clean_unk()` is applied to document batch output. The fallback for pivot/NLLB-first languages is per-paragraph via `_translate_nllb()` or `_pivot_via_hindi()`.

---

*Prepared By: Sanjana MS*

---

## 24. TTS, Video Processing & Pipeline Orchestration

### 24.1 Overview

This section documents the three remaining core inference modules: the TTS engine (`pipeline/tts.py`), the video processor (`pipeline/video_processor.py`), and the main pipeline orchestrator (`pipeline/dubbing_pipeline.py`). Together these modules take translated text segments and produce the final dubbed MP4 output.

---

### 24.2 TTS Engine (`pipeline/tts.py`)

#### 24.2.1 Engine Hierarchy

The TTS engine implements a four-level fallback chain. Each level is attempted in order; the first to produce valid audio wins:

```
1. Parler-TTS Indic Large (primary)
        ↓ (if silent, too short, OOM, or lang in _PARLER_SKIP_LANGS)
2. Standalone VITS (doi/bod/mni/kok/kas — native-script models)
        ↓ (if model not downloaded or synthesis fails)
3. MMS-TTS shared base + per-language adapter
        ↓ (if adapter missing or synthesis fails)
4. Coqui XTTS-v2 (last resort)
        ↓ (if all engines fail)
   Write silence (2.0s) — pipeline never stalls
```

All models are loaded lazily and cached as instance attributes. The `_mms_load_failed` flag prevents repeated failed load attempts on every segment.

#### 24.2.2 Parler-TTS

**Model selection**: The engine checks for `models/indic_parler_tts_large/` first, then `models/indic_parler_tts/` (mini). Whichever exists is loaded; the `_parler_label` attribute records which variant is active.

**Description tokenizer**: Parler-TTS requires two tokenizers — one for the audio prompt (the model's own LLaMA tokenizer) and one for the text description (flan-t5-large). The description tokenizer is loaded from `models/flan_t5_large/` if present, otherwise downloaded from HuggingFace. Using the wrong tokenizer produces silence.

**Voice consistency**: A fixed seed per language (`_LANG_SEEDS`) is set via `torch.manual_seed()` and `torch.cuda.manual_seed_all()` before every `generate()` call. This ensures the same voice character across all segments of a course and across multiple runs of the same course.

**Speaker description**: All 22 languages use the same generic description: *"A speaker delivers clear and expressive speech at a moderate pace with a natural pitch. The recording is of very high quality, with a close-sounding voice and no background noise."* Named speaker descriptions (e.g. "Divya's voice") produce silence in the Indic fine-tune and are not used.

**Script skip**: sat (Ol Chiki), kas (Arabic), and snd (Arabic) are in `_PARLER_SKIP_LANGS` — Parler-TTS cannot render these scripts and always produces silence for them. These languages fall directly to standalone VITS or MMS.

**Max token calculation**: `_calc_max_tokens()` estimates the required audio token budget from the visible grapheme count (NFC-normalised, counting only letter/number categories). Formula: `min(max(graphemes × 25, 200), 1500)`. This prevents truncation of long segments and avoids wasting compute on short ones.

**Silence/OOM detection**: After generation, the output is rejected and the next engine tried if:
- Duration < 0.5 seconds (`_PARLER_MIN_DUR`)
- Peak amplitude < 0.02 (near-silent output)
- `RuntimeError: out of memory` — CUDA cache is cleared and one retry is attempted before falling through

**Batch processing**: `synthesize_segments()` processes segments in batches of 32 (tuned for A6000 48 GB). The description tokens are computed once per batch; prompt tokens are computed per segment.

#### 24.2.3 Standalone VITS

Five languages have dedicated standalone VITS models downloaded to `models/mms_standalone/`:

| Language | Model | Subfolder |
|----------|-------|-----------|
| Dogri (doi) | facebook/mms-tts-dgo | `dgo/` |
| Bodo (bod) | facebook/mms-tts-bod | `bod/` |
| Manipuri (mni) | facebook/mms-tts-mni | `mni/` |
| Konkani (kok) | facebook/mms-tts-kok | `kok/` |
| Kashmiri (kas) | facebook/mms-tts-kas | `kas/` |

These are tried before the MMS shared-adapter model to avoid wrong-language audio (e.g. the MMS Kashmiri adapter uses the Urdu adapter, which produces Urdu-accented speech). Output is resampled to 44.1 kHz and post-processed with `_post_process()`.

#### 24.2.4 MMS-TTS

The MMS-TTS shared VITS base model supports all 22 languages via per-language adapter weights. Adapter loading uses `model.load_adapter()` (transformers ≥ 4.40) with a manual `safetensors`/`torch.load` fallback for older versions.

Key implementation details:
- **One-at-a-time processing**: segments are processed individually (not batched) to avoid padding artifacts (Tamil underscores) and silent truncation of long sequences (Malayalam)
- **Token limit**: inputs exceeding 450 tokens are rejected — VITS produces repetition loops beyond this limit
- **Trailing silence removal**: the waveform is trimmed at the last sample with amplitude > 1e-5 to remove the silence tail that VITS appends
- **Sanskrit fallback**: Sanskrit has no MMS adapter; the Hindi adapter (`hin`) is used as a Devanagari-script substitute

#### 24.2.5 XTTS-v2

Coqui XTTS-v2 is the last-resort fallback. It loads from `models/xtts_v2/` if present, otherwise auto-downloads (~1.8 GB) to the HuggingFace cache. Per-language reference WAV files in `assets/xtts_refs/<lang>.wav` are used for voice conditioning; a generic `generic_indic.wav` is used if no per-language file exists.

#### 24.2.6 Audio Post-Processing

`_post_process()` is applied to all engine outputs:
1. **High-pass filter** (80 Hz, 2nd-order Butterworth): removes DC offset and low-frequency rumble
2. **Low-pass filter** (12 kHz, MMS only): MMS-TTS produces high-frequency noise above 12 kHz; this filter removes it
3. **Pitch shift** (+5 semitones, optional `female_shift`): uses `librosa.effects.pitch_shift` with `soxr_hq` backend
4. **Peak normalisation** to −1 dBFS: `audio × (0.891 / peak)`

#### 24.2.7 Ol Chiki Transliteration

Santhali (sat) uses Ol Chiki script (U+1C50–U+1C7F). Parler-TTS cannot render Ol Chiki. `_normalize_text_for_tts()` transliterates Ol Chiki characters to approximate Devanagari equivalents before sending to Parler-TTS. The MMS sat adapter handles Ol Chiki natively and receives the original text (`for_mms=True` bypasses transliteration).

---

### 24.3 Video Processor (`pipeline/video_processor.py`)

#### 24.3.1 ffmpeg Integration

All video/audio operations use ffmpeg via the `imageio-ffmpeg` bundled binary (`imageio_ffmpeg.get_ffmpeg_exe()`), eliminating the system ffmpeg requirement. ffprobe is located relative to the ffmpeg binary path.

#### 24.3.2 Audio Extraction

`extract_audio()` extracts a 16 kHz mono WAV from any video or audio container. Two failure recovery paths:
1. If the input has no audio stream, silence matching the video duration is generated via `ffmpeg -f lavfi -i anullsrc`
2. If extraction fails (corrupt container, unusual codec), the input is re-encoded to a clean H.264/AAC MP4 via `_reencode_input()` and extraction is retried

#### 24.3.3 Audio Assembly (`assemble_dubbed_audio()`)

This is the core timing synchronisation function. It places each TTS segment at its original timestamp in a zero-filled output buffer of exactly `original_duration` seconds:

1. For each segment, the **slot size** is computed as the maximum of:
   - Time to next segment start
   - Original segment duration (end − start)
   - 100 ms minimum

2. If the TTS audio is longer than the slot, it is **sped up** using `_atempo_stretch_file()` (ffmpeg `atempo` filter, time-domain, no phase smearing). Maximum speed-up is capped at **1.35×** — beyond this, speech becomes unintelligible. If the audio is still longer after 1.35× speed-up, it is hard-trimmed to the slot boundary.

3. A **10 ms fade-in** (`np.linspace(0, 1, fade_samples)`) is applied to eliminate the click artifact at segment boundaries.

4. The segment is placed at `start_sample = int(start_s × sample_rate)` in the output buffer.

5. After all segments are placed, the output is **peak-normalised** to −1 dBFS.

The `atempo` filter chains multiple stages for ratios outside the 0.5–2.0 range supported by a single filter instance (e.g. ratio=2.5 → `atempo=2.0,atempo=1.25`).

#### 24.3.4 Video Muxing (`replace_audio_in_video()`)

The dubbed WAV is first padded or trimmed to exactly match the video duration (silence padding, not time-stretching — stretching would slow all speech). The padded audio is then muxed into the output MP4:

- **Primary**: `ffmpeg -c:v copy -c:a aac -b:a 192k` — stream-copies the video, re-encodes audio only
- **Fallback**: re-encodes video with `libx264 ultrafast crf=23` if stream-copy fails (e.g. incompatible container)
- **Subtitle embedding**: if an SRT path is provided, it is muxed as a `mov_text` soft subtitle track with language metadata and `disposition:default`

---

### 24.4 Pipeline Orchestrator (`pipeline/dubbing_pipeline.py`)

#### 24.4.1 `DubbingResult` Dataclass

Every `dub_video()` call returns a `DubbingResult` with:

| Field | Type | Description |
|-------|------|-------------|
| `source_lang` | str | Resolved source language (may differ from input if `auto`) |
| `target_lang` | str | Target language code |
| `input_path` | str | Source video/audio path |
| `output_video_path` | str | Output MP4 path |
| `output_audio_path` | str | Output MP3 path (audio-only input) |
| `transcript` | list[dict] | ASR segments with timestamps |
| `translations` | list[dict] | Translated segments with quality scores |
| `quality_summary` | dict | Aggregated quality metrics |
| `duration_original` | float | Source duration in seconds |
| `duration_output` | float | Output duration in seconds |
| `elapsed_s` | float | Wall-clock time for the job |
| `voice_cloned` | bool | Whether XTTS-v2 voice cloning was used |
| `success` | bool | Job success flag |
| `error` | str | Error message on failure |

#### 24.4.2 `dub_video()` — 6-Step Pipeline

The main single-language dubbing function. Steps:

| Step | Description | Checkpoint |
|------|-------------|-----------|
| 1 | Audio extraction (16 kHz mono WAV) | Stale-cache detection via mtime comparison |
| 1b | SeamlessM4T S2ST fast path (Indic→Indic only) | Returns early on success |
| 2 | ASR transcription | Segments cached in `JobCheckpoint.meta["segments"]` |
| 3 | Translation (GPU batch + checkpoint) | Per-segment results in `JobCheckpoint.completed` |
| 4 | TTS synthesis | TTS dir wiped and re-run every time |
| 5 | Audio assembly (timestamp-aligned, max 1.35× speed) | — |
| 6 | Output: SRT/VTT + MP4 mux + metadata JSON | Checkpoint cleared on success |

**Concurrent job protection**: a per-`(course_id, tgt_lang)` `threading.Lock` prevents two threads from running the same job simultaneously. `acquire(blocking=False)` returns immediately if the lock is held, and the duplicate job is skipped with a warning.

**Stale cache detection**: `source.wav` is re-extracted if its `mtime` is older than the input video's `mtime`. The ASR checkpoint is also cleared so Step 2 re-runs with the fresh audio.

**Force re-run**: `--force` calls `JobCheckpoint.clear()` before starting, wiping both the checkpoint and all previous output files. Without `--force`, only TTS/assembly re-run (ASR and translation are resumed from checkpoint).

**Audit trail**: every job start, success, and failure is written to `logs/audit.log` as a JSON line including job ID, file name, language pair, host, elapsed time, quality summary, and output path.

**Metadata JSON**: `_save_metadata()` writes `<course_id>_<lang>_metadata.json` containing the full transcript, all translations with quality scores, duration, voice clone flag, and a provenance block with model versions (from `importlib.metadata`), git commit hash, hostname, timestamp, and contract reference.

#### 24.4.3 `_translate_segments_parallel()`

The translation step classifies all pending segments into three groups before calling any engine:

| Group | Condition | Action |
|-------|-----------|--------|
| Empty | `text == ""` | Pass through with `score=1.0` |
| Non-translatable | ≥ 90% non-translatable chars | Pass through unchanged |
| Translatable | All others | GPU batch via `translate_batch()` |

After batch translation, three completeness guards are applied:
1. If `len(batch_results) ≠ len(text_local)` → fall back to per-segment translation
2. If any individual translation is empty for a non-empty source → retry via single `translate()`
3. If any result slot is `None` after all processing → retry per-segment

The final checkpoint flush is a single `ckpt.flush()` after the entire batch, not per-segment, to minimise disk I/O.

#### 24.4.4 Multi-GPU Parallel Dubbing (`dub_course_parallel()`)

```
Main process:
  1. Extract audio → source.wav (shared)
  2. Run ASR once → asr_cache.json (shared)
  3. Distribute languages: gpu_id = lang_index % num_gpus
  4. Spawn worker processes via multiprocessing.get_context("spawn")

Worker process (per GPU):
  - Sets PIPELINE_GPU env var → all torch operations use assigned GPU
  - Reads asr_cache.json → seeds JobCheckpoint with pre-computed segments
  - Runs translate + TTS + assemble for each assigned language
  - Returns dict[lang, DubbingResult]

Main process:
  5. Collect results from all workers
  6. Delete shared ASR cache directory
  7. Merge and return dict[lang, DubbingResult]
```

`spawn` context is used (not `fork`) for Windows compatibility and to avoid CUDA context inheritance issues. Each worker imports the pipeline fresh and loads its own model instances on the assigned GPU.

The ASR cache seeding in `_worker_dub_langs()` writes the pre-computed segments into each language's `JobCheckpoint` before `dub_video()` is called, so Step 2 (ASR) is skipped in every worker — ASR runs exactly once regardless of how many target languages are being processed.

#### 24.4.5 Report Generation

`DubbingPipeline` generates six types of formal documents for KB tender compliance:

| Method | Document | Tender Reference |
|--------|----------|-----------------|
| `generate_qa_report()` | QA Self-Certification DOCX | KB tender §4 |
| `generate_inception_report()` | Translation Plan DOCX | Payment Milestone 1 (T0+15 days) |
| `generate_monthly_report()` | Monthly Submission Report DOCX | Monthly delivery |
| `generate_correction_report()` | Correction & Closure Report DOCX | Deliverables §4.5.iv |
| `generate_completion_report()` | Consolidated Completion Report DOCX | Deliverables §4.6 |
| `export_metadata_xlsx()` / `export_quiz_docx()` | Metadata Excel / Quiz Word | SoW §3.4 |

All documents include the contract reference `RFB IN-KBL-543730-NC-RFB` and a signature line for the reviewer.

---

*Prepared By: Sanjana MS*

---

## Section 25 — Testing & Validation

### 25.1 Overview

The project employs a layered testing strategy comprising automated smoke tests, component-level unit assertions, integration checks, and quality benchmarks. All tests are designed to execute without loading any model weights, enabling rapid CI validation on CPU-only machines. The primary test entry point is `scripts/test_pipeline.py`, which runs 11 independent test groups and exits with code `0` (all pass) or `1` (any failure).

---

### 25.2 Smoke Test Architecture

**File:** `scripts/test_pipeline.py`

The smoke test suite is structured as a flat sequential runner with a shared pass/fail counter. Each group is wrapped in a `try/except` block so a failure in one group does not abort subsequent groups. The `check()` helper prints `PASS` or `FAIL` with an optional detail string and increments the global counters.

```
check(label, condition, detail="")
    → PASS_COUNT++ or FAIL_COUNT++
    → prints result immediately
```

At completion, a summary block prints `PASSED: N/TOTAL` and `FAILED: N/TOTAL`, then calls `sys.exit(0 if FAIL_COUNT == 0 else 1)`.

**Design principle:** No model is loaded. All 11 groups test import correctness, logic correctness, and file-system state — not inference output.

---

### 25.3 Test Groups

#### Group 1 — Language Configuration (`lang_config`)

Validates that the language registry is complete and consistent across all three translation engines.

| Assertion | Expected |
|-----------|----------|
| `ALL_22` length | Exactly 22 entries |
| `LANG_NAMES` coverage | All 22 codes present |
| `INDIC_TRANS2_CODES` coverage | All 22 codes present |
| `eng` in `INDIC_TRANS2_CODES` | True (required for pivot path) |
| `SEAMLESS_CODES` size | ≥ 15 languages |
| `NLLB_CODES` size | ≥ 21 languages |

This group catches any accidental removal of a language code from the registry, which would silently break routing for that language at runtime.

---

#### Group 2 — Logger

Verifies that `get_logger()` returns a valid logger instance and that `log.info()` executes without raising. This confirms the `RotatingFileHandler` initialisation, UTF-8 encoding, and Windows path handling are all functional before any pipeline code runs.

---

#### Group 3 — Retry Decorator and JobCheckpoint

Tests the two reliability primitives:

**Retry decorator:**
- A function that raises `ValueError` on the first two calls and returns `"ok"` on the third is decorated with `@retry(max_attempts=3, delay=0.01)`.
- Asserts the return value is `"ok"`, confirming exponential backoff and retry logic are correct.

**JobCheckpoint lifecycle:**
| Step | Assertion |
|------|-----------|
| `set_meta("test_key", 42)` | `get_meta("test_key") == 42` |
| `mark_done(0, {...})` + `flush()` | `is_done(0)` returns `True` |
| `clear()` | Checkpoint file no longer exists on disk |

The `flush()` call exercises the atomic write path (`.tmp` → `rename`), and `clear()` confirms the file is removed cleanly.

---

#### Group 4 — Quality Scorer

Tests all three scoring layers and the transliteration detector:

**`score_segment()`:**
- Returns a dict containing `score` (float, 0–1) and `flags` (list).
- Input: English source `"Hello world how are you"` → Hindi translation `"नमस्ते दुनिया आप कैसे हैं"`.

**`detect_transliteration()`:**
- `"namaste duniya aap kaise hain"` with `tgt_lang="hin"` → `True` (Latin ratio > 60%).
- `"नमस्ते दुनिया आप कैसे हैं"` with `tgt_lang="hin"` → `False` (no false positive on real Devanagari).

**`review_summary()`:**
- Called with a list of two identical score dicts.
- Asserts `avg_score` key is present and `total == 2`.

---

#### Group 5 — Glossary Manager

Tests the two-phase protect/restore mechanism:

| Step | Assertion |
|------|-----------|
| `add_term("iGOT", "iGOT", "hin")` | Term registered |
| `protect_terms("iGOT Karmayogi platform", "hin")` | Returns string containing `__GLOSS_` placeholder |
| `restore_terms(protected, pmap)` | Returns string containing `"iGOT"` |

This confirms that domain-critical terms survive the translation round-trip without modification.

---

#### Group 6 — Subtitle Generation

Uses a `tempfile.TemporaryDirectory` to avoid leaving test artefacts on disk. Input is three segments: two with text and one empty.

| Assertion | Expected |
|-----------|----------|
| SRT `-->` count | 2 (empty segment skipped) |
| VTT file starts with | `"WEBVTT"` |
| Segment index `3` absent from SRT | True (empty segment not written) |

---

#### Group 7 — Language Detection

Tests the `fw_lang_to_internal()` mapping function and the `tag_segments()` behaviour for lingua-unsupported languages:

| Assertion | Expected |
|-----------|----------|
| `fw_lang_to_internal("hi")` | `"hin"` |
| `fw_lang_to_internal("en")` | `"eng"` |
| `fw_lang_to_internal("xx", "eng")` | `"eng"` (fallback) |
| `tag_segments([...], "bod")` | `detected_lang == "bod"` always |

The Bodo (`bod`) assertion is critical: since lingua does not support Bodo, the tagger must always return the assumed language rather than attempting detection and producing a wrong result.

---

#### Group 8 — DubbingPipeline Instantiation

Tests the orchestrator without triggering any model load (all models are lazy-loaded on first use):

**Lazy initialisation:**
| Attribute | Expected at construction |
|-----------|--------------------------|
| `_asr` | `None` |
| `_translator` | `None` |
| `_tts` | `None` |

**Exclusion detection:**
| Input | Expected |
|-------|----------|
| `"Speech by Prime Minister Narendra Modi at the event"` | `should_skip_translation()` → `True` |
| `"PMMY scheme helps farmers get loans"` | `should_skip_translation()` → `False` |

The second case is a deliberate false-positive guard: the acronym "PM" inside "PMMY" must not trigger the PM speech exclusion rule.

**Input validation:**
| Input | Expected exception |
|-------|--------------------|
| `"nonexistent_file.mp4"` | `FileNotFoundError` |
| `__file__` (a `.py` file) | `ValueError` (wrong extension) |

---

#### Group 9 — Translator Instantiation

Tests the `Translator` class without loading any model weights:

| Assertion | Expected |
|-----------|----------|
| `Translator()` instantiates | No exception |
| `_seamless` at construction | `None` (lazy) |
| `_nllb` at construction | `None` (lazy) |
| `translate("hello", "eng", "eng")["engine"]` | `"passthrough"` |

The passthrough assertion confirms that same-language translation is short-circuited before any model is invoked — a correctness and performance requirement.

---

#### Group 10 — Dataset Coverage

Checks that all 22 parallel training sets are present on disk and non-empty:

| Check | Expected |
|-------|----------|
| `datasets/parallel/<lang>/train.jsonl` exists for all 22 | 0 missing |
| `hin`, `tam`, `ben` train sets | Record count > 0 |

Missing datasets are reported by language code in the failure detail string, enabling targeted remediation.

---

#### Group 11 — Model Weight Presence

Checks that all required model weight files and directories exist at their expected paths:

| Model | Path checked |
|-------|-------------|
| IndicTrans2 en_indic | `models/indic_tr/en_indic/pytorch_model.bin` |
| IndicTrans2 indic_en | `models/indic_tr/indic_en/pytorch_model.bin` |
| IndicTrans2 indic_indic | `models/indic_tr/indic_indic/pytorch_model.bin` |
| SeamlessM4T shard 1 | `models/seamless/model-00001-of-00002.safetensors` |
| SeamlessM4T shard 2 | `models/seamless/model-00002-of-00002.safetensors` |
| faster-whisper | `models/indic_asr/` (directory) |
| Parler-TTS | `models/indic_parler_tts/` (directory) |

This group is expected to fail on a fresh clone before `scripts/download_models.py` has been run, and to pass on a fully provisioned deployment machine.

---

### 25.4 Quality Scoring — Detailed Specification

The quality scorer (`pipeline/quality.py`) implements three independent scoring methods that are combined to produce a final segment score.

#### 25.4.1 Heuristic Scorer (`score_segment`)

Eight checks applied sequentially, each deducting from an initial score of 1.0:

| Check | Condition | Deduction |
|-------|-----------|-----------|
| Empty translation | `translation` is blank | Score → 0.0, immediate return |
| Length ratio | `tgt_words / src_words < 0.3` or `> 4.0` | −0.25 |
| Source language leakage | Native script chars < 50% of total alpha chars | −0.30 |
| Repetition loop | Four consecutive identical words | −0.35 |
| Untranslated (exact copy) | `translation == source` for non-English target | −0.40 |
| Untranslated (Latin output) | > 80% Latin chars in non-Latin target | −0.35 |
| Too short | `src_words ≥ 5` and `tgt_words < 2` | −0.30 |
| Transliteration | Latin ratio > 60% in non-Latin target | −0.35 |
| Missing numbers | Source numeric tokens absent from translation | −0.20 |

Score is clamped to `[0.0, 1.0]` after all deductions.

#### 25.4.2 ChrF Score (`chrf_score`)

Character n-gram F-score with `n=6`, `β=2` (recall-weighted). Computed only for same-script pairs (e.g., English→English for back-translation comparison). Cross-script pairs (e.g., English→Hindi) return `0.0` for ChrF since the source is not a valid reference in the target script.

Formula:
```
ChrF = (1 + β²) × P × R / (β² × P + R)
where P = avg character n-gram precision (n=1..6)
      R = avg character n-gram recall   (n=1..6)
```

#### 25.4.3 Back-Translation Score (`back_translation_score`)

Translates the output back to the source language using the shared `Translator` instance (injected via `set_shared_translator()` to avoid loading a second model into GPU memory), then measures word-level overlap:

```
overlap = |src_words ∩ back_words| / |src_words|
```

Returns `−1.0` on failure (network error, model unavailable). A score below `0.25` appends `low_back_translation_<score>` to flags and deducts `−0.15` from the heuristic score.

#### 25.4.4 Thresholds and Actions

| Score Range | Status | Pipeline Action |
|-------------|--------|-----------------|
| ≥ 0.55 | ✅ Pass | Accepted, sent to TTS |
| 0.30 – 0.55 | ⚠️ Review | Flagged in metadata, sent to TTS |
| < 0.30 | ❌ Failed | `text` set to `""`, silence written — no wrong-language audio |

The silence action at `< 0.30` is a hard safety guarantee: a segment that fails quality gating produces a silent gap in the dubbed audio rather than emitting audio in the wrong language or with corrupted content.

---

### 25.5 Integration Test Coverage

Beyond the smoke test, the following integration scenarios are validated during development and pre-deployment:

| Scenario | Validation Method |
|----------|------------------|
| End-to-end dub (single language) | `scripts/test_pipeline.py` Group 8 + manual run with short test video |
| All 22 languages in sequence | `scripts/clean_and_run_all22.py` on a 30-second test clip |
| Checkpoint resume after crash | Kill process mid-job; re-run; verify output matches full run |
| Force re-run clears state | `--force` flag; verify output/ and checkpoints/jobs/ are cleared |
| Multi-GPU distribution | `--num-gpus 2` on a 4-GPU machine; verify ASR runs once |
| Voice cloning output | `--voice-clone --reference-audio` with a 10-second reference WAV |
| CBP upload dry-run | Mock server; verify all 6 file patterns are submitted |
| Translation memory injection | Add a term; run translation; verify term appears verbatim in output |
| LLM post-edit activation | Set `GROQ_API_KEY`; verify `llm_enhanced: true` in metadata JSON |

---

### 25.6 Quality Benchmarks

Target quality metrics for the KB tender submission, measured on the iGOT internal evaluation set (500 segments per language, human-annotated references):

| Metric | Target | Measurement |
|--------|--------|-------------|
| Heuristic pass rate (≥ 0.55) | ≥ 85% of segments | `review_summary()["pass_rate"]` |
| Rejection rate (< 0.30) | ≤ 5% of segments | `review_summary()["failed"] / total` |
| ChrF (same-script pairs) | ≥ 0.45 | `review_summary()["avg_chrf"]` |
| Back-translation overlap | ≥ 0.40 | `review_summary()["avg_back_translation"]` |
| Transliteration detection false-positive rate | ≤ 2% | Manual audit of flagged segments |
| Duration ratio (dubbed vs original) | ≤ 1.20× | `DubbingResult.duration_ratio` |

These benchmarks are reported per language in the QA self-certification document (`<course_id>_<lang>_qa_cert.docx`) generated by `ui/reviewer.py`.

---

*Prepared By: Sanjana MS*

---

## Section 26 — User Interface

### 26.1 Overview

The web UI is implemented in `ui/app.py` using Gradio and exposes the full pipeline capability through eight tabs. It is launched via `python ui/app.py` and binds to `0.0.0.0` on the first available port starting at 7860, opening the browser automatically. The human review module (`ui/reviewer.py`) is a standalone component with no pipeline imports — it operates entirely on the metadata JSON files produced by the pipeline.

---

### 26.2 Application Bootstrap

**Background model loading:**

When `app.py` is imported, a daemon thread is started immediately to load the `DubbingPipeline` in the background:

```
_bg_thread = threading.Thread(target=_load_pipeline_bg, daemon=True)
_bg_thread.start()
```

The `_pipeline_ready` event is set when loading completes (success or failure). All tab handlers call `get_pipeline()`, which blocks on `_pipeline_ready.wait(timeout=300)` — a 5-minute timeout. This design allows the Gradio UI to render and accept user input while models load, with a live status bar (`every=3` seconds) showing the current state.

**Pipeline status bar:**

A `gr.Textbox` with `every=3` polls `_pipeline_status()` every 3 seconds and displays one of:
- `⏳ Loading models in background...`
- `✅ Pipeline ready`
- `❌ <error message>`

**Port selection:**

The launcher scans ports 7860–7879 for the first available TCP port, falling back to Gradio's automatic selection if none are free.

**Output directory persistence:**

The user-selected output folder is persisted to `.output_dir` (a plain text file at the project root). On startup, `_get_output_dir()` reads this file and recreates the directory if needed, falling back to `output/` if the file is absent.

---

### 26.3 Tab Architecture

| Tab | Label | Primary Function |
|-----|-------|-----------------|
| 1 | 🎬 Dub Video / Audio | Full pipeline: ASR → Translation → TTS → mux |
| 2 | 📄 Translate Document | DOCX/TXT/JSON quiz and metadata translation |
| 3 | 📋 QA Certificate | Generate self-certification DOCX per tender SLA |
| 4 | 👤 Human Review | Segment-level approve/correct/reject + certificate export |
| 5 | ⚙️ Settings | HF token, output folder |
| 6 | 📅 Monthly Delivery | Delivery hour tracking + submission report export |
| 7 | 📖 Glossary | Terminology management + Excel export/import |
| 8 | 📊 Live Logs | Real-time pipeline log stream |

---

### 26.4 Tab 1 — Dub Video / Audio

The primary job submission interface. Accepts MP4, MP3, WAV, and FLAC files.

**Inputs:**

| Field | Type | Default |
|-------|------|---------|
| Course Video / Audio | File upload | — |
| Course Metadata | File upload (DOCX/XLSX/JSON) | optional |
| Quiz / Assessment | File upload (DOCX/XLSX/JSON) | optional |
| Course ID | Textbox | `KB_COURSE_001` |
| Source Language | Dropdown | `eng` |
| Target Languages | CheckboxGroup | KB-11 (11 languages) |
| Voice Cloning (Tier 2) | Checkbox | False |
| Upload to CBP Portal | Checkbox | False |
| Reference Speaker Audio | File upload (WAV/MP3) | hidden unless voice clone enabled |

**Quick-select buttons:** "✅ KB 11 (Mandatory)" sets the 11 mandatory languages; "All 22" selects all; "Clear" deselects all.

**Voice clone visibility:** The reference audio upload field is hidden by default and shown only when the voice cloning checkbox is ticked, via a `change` event handler.

**Job execution (`process_course`):**

1. Detects GPU count via `torch.cuda.device_count()`.
2. Calls `pipeline.process_course_full()` with all parameters.
3. Collects output files: MP4, SRT, VTT per language; quiz DOCX; QA reports; metadata XLSX.
4. Returns file list for download and a JSON job summary with quality scores.

**Outputs:** `gr.Files` download widget + `gr.Textbox` showing the full JSON job summary including per-language quality scores and elapsed time.

---

### 26.5 Tab 2 — Translate Document

Handles four document types with distinct processing paths:

| Document Type | Input Format | Processing Path | Output |
|---------------|-------------|-----------------|--------|
| Quiz / Assessment | JSON | `pipeline.export_quiz_docx()` | `.docx` per language |
| Course Metadata | JSON | `pipeline.export_metadata_xlsx()` | single `.xlsx` (all languages) |
| General Document (DOCX) | DOCX/DOC | `translate_docx()` — format-preserving | `.docx` per language |
| General Document (TXT) | TXT | `extract_text()` → paragraph chunking → `translate_batch()` → `DocxDocument` | `.docx` per language |
| PDF | PDF | **Blocked** — returns error per tender §3.1 | — |

**PDF blocking:** Any file with `.pdf` extension returns immediately with the message: `"PDF documents are NOT translated per tender §3.1. Upload the PDF as-is to CBP portal in the original language."` No translation is attempted.

**Text chunking (`_chunk_text`):** Splits on sentence boundaries (`[.!?।॥]` followed by whitespace). Sentences longer than 400 characters are hard-split at word boundaries. This prevents oversized batches from exceeding the translation engine's token limit.

**DOCX path:** Calls `translate_docx()` from `pipeline/doc_extractor.py` via a `_batch_translate` closure that routes through `pipeline.translator.translate_document_batch()` — bypassing placeholder protection layers, which are inappropriate for document-level translation where format tokens are not present.

**Progress reporting:** `gr.Progress` is updated per language with the language name as the description string.

---

### 26.6 Tab 3 — QA Certificate

Generates the Language Quality Assurance Certification required by the KB tender SLA. The form collects:

- Course ID, source language, target language
- Original source file and dubbed output file
- Reviewer name (default: `"Translation Agency QA Lead"`)

On submission, `pipeline.generate_qa_report()` is called with a `DubbingResult` dataclass constructed from the form inputs. The output is a `.docx` file saved to `output/<course_id>/<course_id>_<lang>_qa_cert.docx`.

The tab also displays the SLA threshold reference table inline:

| Score | Status | Action |
|-------|--------|--------|
| ≥ 0.55 | ✅ Pass | 98%+ accuracy |
| 0.30–0.55 | ⚠️ Needs correction | Resubmit within 5 days |
| < 0.30 | ❌ Failed | Mandatory re-translation |

And the delivery SLA penalty schedule:

| Shortfall | Penalty |
|-----------|---------|
| < 5% | No penalty |
| 5–10% | 2% deduction |
| > 10% | 4% deduction |
| > 20% | 5% deduction |

---

### 26.7 Tab 4 — Human Review

The human review workflow is the most stateful tab, using two `gr.State` objects: `_rev_state` (list of segment dicts) and `_rev_path` (path to the loaded metadata JSON).

**Workflow:**

```
Upload *_metadata.json
        │
        ▼
load_metadata() → parse transcript + translations → build segment list
        │
        ▼
load_review() → overlay sidecar _review.json if it exists (resume support)
        │
        ▼
segments_to_display() → convert to list-of-lists for gr.Dataframe
        │
        ▼
Reviewer edits "Corrected Text" and "Decision" columns in the table
        │
        ▼
"Save Progress" → save_review() → writes _review.json sidecar
        │
        ▼
"Export Review Certificate" → export_certificate() → signed DOCX
```

**Dataframe columns:**

| Column | Editable | Content |
|--------|----------|---------|
| ID | No | Segment index |
| Time | No | `start–end` in seconds |
| Source | No | Original source text |
| AI Translation | No | Pipeline output |
| Corrected Text | Yes | Reviewer's correction |
| Score | No | Heuristic quality score |
| Flags | No | Quality flag list |
| 🚩 | No | Flag icon if `needs_review` |
| Decision | Yes | `approved` / `corrected` / `rejected` |

**"Approve All Unflagged" button:** Sets `decision = "approved"` for all segments that have no quality flags and no existing decision, without requiring the reviewer to process each row individually.

**Sidecar pattern:** Review state is saved to `<stem>_review.json` alongside the metadata file, not inside it. This preserves the original pipeline output and allows review to be resumed across sessions.

**Review statistics bar:** Displays a one-line summary updated after every load/save/approve-all action:
```
Total: N | ✅ Approved: N | ✏️ Corrected: N | ❌ Rejected: N | ⏳ Pending: N | 🚩 AI-flagged: N
```

---

### 26.8 Tab 5 — Settings

Two configuration panels:

**HuggingFace Token:**
- Reads current `HF_TOKEN` from `.env` on load (password field, not displayed in plain text).
- On save: rewrites `.env` preserving all other keys, sets `os.environ["HF_TOKEN"]`, and resets `_pipeline` to `None` so the next job triggers a fresh pipeline load with the new token.

**Output Folder:**
- Displays current output directory (from `.output_dir` file or default `output/`).
- "Set Folder" calls `_set_output_dir()`: creates the directory, writes path to `.output_dir`.
- "Open Folder" calls `os.startfile()` to open the folder in Windows Explorer.

The settings panel also displays inline reference documentation for quality scoring thresholds and checkpoint/resume behaviour.

---

### 26.9 Tab 6 — Monthly Delivery Tracker

Implements the KB tender §4.4 monthly delivery tracking requirement. SLA bounds: 50–125 content hours per month.

**State:** A `gr.State` list of row dicts, each containing `month`, `course`, `langs`, `hours`, `status`.

**Add Entry (`_md_add`):**
- Computes cumulative hours for the month across all entries.
- Assigns status: `"✅ On track"` if 50–125 hrs, `"⚠️ Below 50hr minimum"` if under, `"⚠️ Exceeds 125hr SLA cap"` if over.
- Updates the dataframe and a per-month summary textbox.

**Export functions:**

| Button | Output | Sheets |
|--------|--------|--------|
| Export Month-wise Submission Report | `KB_Monthly_Submission_Report.xlsx` | Single sheet: Month, Course ID, Languages, Hours, Status |
| Export Consolidated Completion Report | `KB_Consolidated_Completion_Report.xlsx` | Sheet 1: detail rows; Sheet 2: per-month summary with SLA status |

Both use `openpyxl` directly and save to the configured output directory.

---

### 26.10 Tab 7 — Glossary

Manages the standardised terminology glossary required as a final deliverable under the KB tender.

**Add Term (`_gl_add`):**
- Parses the translations textbox as `lang_code: translation` lines.
- Stores each entry as a dict with `term`, `domain`, `langs`, `trans` (display string), and `trans_map` (code → translation dict).

**Export (`_gl_export`):**
- Collects all unique language codes across all entries.
- Writes an Excel file with columns: English Term, Domain, then one column per language (using full language names as headers).
- Saved as `KB_Standardised_Glossary.xlsx` in the output directory.

**Import (`_gl_import`):**
- Reads an existing `.xlsx` glossary file.
- Reconstructs `trans_map` by reverse-mapping language names back to codes using `LANG_NAMES`.
- Merges imported entries into the current in-memory state.

---

### 26.11 Tab 8 — Live Logs

A `gr.Textbox` with `every=3` that polls `_get_log()` every 3 seconds. The in-memory log buffer (`_log_lines`) holds up to 200 entries; the display shows the last 60. Log entries are prefixed with `[HH:MM:SS]` timestamps. The buffer is written to by `_append_log()` from the pipeline background thread and all tab handler functions, providing a unified real-time view of all pipeline activity.

---

### 26.12 Human Review Module (`ui/reviewer.py`)

The reviewer module is intentionally isolated from all pipeline imports. It operates exclusively on the `*_metadata.json` files produced by the pipeline.

**Key functions:**

| Function | Purpose |
|----------|---------|
| `load_metadata(json_path)` | Parses pipeline metadata JSON; joins `transcript` and `translations` arrays by segment ID; returns list of segment dicts |
| `review_path(json_path)` | Computes sidecar path: `<stem>_review.json` in the same directory |
| `load_review(json_path, segments)` | Overlays saved decisions from sidecar onto segment list (resume support) |
| `save_review(json_path, segments, reviewer)` | Writes sidecar JSON with reviewer name, timestamp, and per-segment decisions |
| `export_certificate(json_path, segments, reviewer, output_path)` | Generates signed DOCX review certificate |
| `review_stats(segments)` | Returns one-line summary string |
| `segments_to_display(segments)` | Converts segment list to `list[list]` for `gr.Dataframe` |

**Certificate structure (`export_certificate`):**

The DOCX certificate contains three sections:

1. Summary metadata table (10 rows × 2 columns): Course ID, target language, source language, reviewer name, review date, total/approved/corrected/rejected/pending counts.

2. Segment-level review table (one row per segment): index, source text (truncated to 200 chars), AI translation, corrected text, decision. Decision cells are colour-coded: green (approved), orange (corrected), red (rejected).

3. Declaration paragraph: A formal certification statement naming the reviewer, their language expertise, the course ID, and the segment counts, followed by signature and date fields.

---

*Prepared By: Sanjana MS*

---

## Section 27 — Fine-Tuning & Model Training

### 27.1 Overview

The project includes full fine-tuning pipelines for both primary translation engines: IndicTrans2 (`finetune/finetune_indictrans.py`) and SeamlessM4T (`finetune/finetune_seamless.py`). Both scripts use HuggingFace Accelerate for distributed training across 4× NVIDIA A6000 GPUs (48 GB VRAM each, 192 GB total). A DeepSpeed ZeRO-3 configuration (`finetune/ds_zero3.json`) is provided as an alternative for Linux deployments. Fine-tuned checkpoints are saved to `checkpoints/` and automatically used by the pipeline in preference to base model weights.

---

### 27.2 IndicTrans2 Fine-Tuning (`finetune_indictrans.py`)

#### 27.2.1 Training Directions

Three independent training runs, each producing a separate checkpoint:

| Direction | Description | Languages |
|-----------|-------------|-----------|
| `en_indic` | English → all 22 Indian languages | 22 target languages |
| `indic_en` | All 22 Indian languages → English | 22 source languages |
| `indic_indic` | Indian → Indian (hub + cross pairs) | 22×22 via Hindi hub |

All three can be launched sequentially with `--direction all`.

**Launch command:**
```bash
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_indictrans.py --direction en_indic
```

#### 27.2.2 Hyperparameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Batch size per GPU | 16 | |
| Gradient accumulation | 4 | Effective batch = 16 × 4 × 4 GPUs = 256 |
| Max epochs | 5 | With early stopping |
| Learning rate | 2e-5 | Cosine schedule with warmup |
| Warmup ratio | 6% | Of total steps |
| Max sequence length | 256 tokens | |
| Label smoothing | 0.1 | Reduces overfit on low-resource languages |
| Early stopping patience | 2 | Stop if dev loss does not improve for 2 epochs |
| TM/human-feedback weight | 5× | High-quality signal repeated 5 times |
| Synthetic data epoch | 3 | Curriculum: synthetic data excluded before epoch 3 |

#### 27.2.3 Per-Language Sampling Weights

Low-resource languages are oversampled to balance the training distribution:

| Resource Tier | Languages | Weight |
|---------------|-----------|--------|
| High-resource (>100K pairs) | ben, guj, kan, mal, mar, ory, pan, tam, tel, asm, urd, nep | 1.0 |
| Hindi (pivot language) | hin | 3.0 |
| Medium-resource (10K–100K) | kas, mai, mni, sat, snd | 2.0 |
| Low-resource (<10K) | bod, doi, kok, san | 4.0 |

Gold records are repeated `round(weight)` times; synthetic records are repeated `round(weight × 0.5)` times.

#### 27.2.4 Curriculum Learning

Training data is built fresh at the start of each epoch via `build_records(direction, "train", epoch=N)`:

- Epochs 1–2: Gold data only (human-translated parallel pairs + TM/human-feedback).
- Epoch 3+: Gold data + synthetic data (back-translated or machine-generated pairs).

This prevents the model from overfitting to noisy synthetic data before it has learned from clean gold data.

#### 27.2.5 Quality Filter

All training pairs pass through `_quality_ok()` before being added to the dataset:

```
drop if: src is empty OR tgt is empty
drop if: len(tgt) / len(src) < 0.25 OR > 6.0
```

This removes degenerate pairs (empty strings, extreme length mismatches) that would corrupt the loss signal.

#### 27.2.6 Label-Smoothed Loss (`_smooth_loss`)

The model's default cross-entropy is replaced with a label-smoothed variant:

```
loss = (1 − ε) × NLL + ε × (−log_probs.sum / vocab_size)
ε = 0.1
```

Applied only to non-padding positions (`labels != −100`). This prevents the model from becoming overconfident on low-resource language pairs where training data is sparse.

#### 27.2.7 indic_indic Pair Construction

The `indic_indic` direction uses a Hindi-hub architecture plus direct high-resource cross-pairs:

- **Hub pairs:** Hindi ↔ every other language (42 directed pairs covering all 22 languages).
- **Direct cross-pairs:** 13 additional high-resource pairs (ben↔tam, ben↔tel, mar↔guj, kan↔tel, mal↔tam, urd↔hin, pan↔hin) where direct training data is available and a Hindi pivot would introduce unnecessary error.

Total: 55 directed language pairs.

#### 27.2.8 Training Loop

1. `build_records()` constructs the epoch's dataset with curriculum and sampling weights applied.
2. `DistributedSampler` distributes records across GPUs; `set_epoch(epoch)` ensures different shuffles per epoch.
3. `ParallelDataset.collate()` groups records by `(src_lang, tgt_lang)` pair within each batch, switches the tokenizer between input and target modes, and pads to the batch maximum length.
4. `_smooth_loss()` replaces the model's default loss.
5. Gradient clipping at 1.0 norm.
6. Cosine LR schedule with 6% warmup steps.
7. Dev loss evaluated at end of each epoch using `accelerator.reduce()` for cross-GPU aggregation.
8. Best checkpoint saved to `checkpoints/indictrans/<direction>/best/` when dev loss improves.
9. Early stopping after 2 consecutive epochs without improvement.

#### 27.2.9 Logging

Per-step logging every 100 steps includes: epoch/step progress, running loss, current LR, steps/second throughput, GPU memory usage (GB), and ETA in minutes.

---

### 27.3 SeamlessM4T Fine-Tuning (`finetune_seamless.py`)

#### 27.3.1 Training Tasks

Two independent fine-tuning tasks:

| Task | Model Class | Purpose |
|------|-------------|---------|
| `asr` | `SeamlessM4Tv2ForSpeechToText` | Improve ASR accuracy on Indian language audio |
| `t2t` | `SeamlessM4Tv2ForTextToText` | Improve text translation quality as fallback engine |

**Launch command:**
```bash
accelerate launch --num_processes=4 --mixed_precision=bf16 \
    finetune/finetune_seamless.py --task asr
```

#### 27.3.2 Hyperparameters

| Parameter | ASR | T2T |
|-----------|-----|-----|
| Batch size per GPU | 4 | 8 |
| Gradient accumulation | 8 | 8 |
| Effective batch size | 4×8×4 = 128 | 8×8×4 = 256 |
| Learning rate | 5e-6 | 2e-5 |
| Warmup steps | 300 | 300 |
| Max epochs | 3 | 3 |
| Max audio duration | 30 seconds | — |
| Max text length | 256 tokens | 256 tokens |

The ASR learning rate (5e-6) is significantly lower than T2T (2e-5) because the speech encoder is a large pre-trained component that requires careful fine-tuning to avoid catastrophic forgetting.

#### 27.3.3 ASR Dataset (`ASRDataset`)

Audio records are loaded from three sources: `kathbath`, `fleurs`, and `indicsuper`, covering all languages present in both `SEAMLESS_LANGS` and `ALL_22`. Each record requires `audio_path`, `text`, and `lang` fields.

The `collate()` method:
1. Loads audio via `librosa.load()` at 16 kHz mono, capped at 30 seconds.
2. Passes audio arrays through `AutoProcessor` to produce input features.
3. Tokenises target text with `src_lang` set to the SeamlessM4T language code.
4. Replaces padding token IDs in labels with `−100` (ignored in loss).

#### 27.3.4 T2T Dataset (`TextDataset`)

Text records are loaded from `datasets/parallel/<lang>/` for all SeamlessM4T-supported languages. Translation memory and human feedback records are appended to the training split (3× weight for human feedback).

**Odia exclusion:** The `collate()` method filters out records where `src_lang` or `tgt_lang` is `"ory"` (Odia), because SeamlessM4T does not include Odia in its vocabulary. Attempting to process Odia records would cause a tokeniser error.

The `collate()` method groups records by `(src_lang, tgt_lang)` pair, encodes source and target separately using the processor with the appropriate `src_lang` parameter, and pads to batch maximum length.

#### 27.3.5 T2T Parameter Freezing

For the T2T task, speech-only parameters are frozen before training to prevent DDP gradient synchronisation errors (frozen parameters have no gradients, which causes NCCL/Gloo to hang waiting for all-reduce on missing tensors):

```python
for name, param in model.named_parameters():
    if any(k in name for k in ("speech_encoder", "t2u", "vocoder")):
        param.requires_grad_(False)
```

This freezes the speech encoder, text-to-unit (T2U) decoder, and vocoder — components that are not used in the text-to-text forward pass.

#### 27.3.6 Shared Training Loop (`run_training`)

Both ASR and T2T tasks share a single `run_training()` function:

1. Per-epoch `DistributedSampler.set_epoch()` for shuffle diversity.
2. `None` batch guard: T2T collate returns `None` if all records in a batch are from unsupported languages (Odia); the training loop skips these batches.
3. Gradient clipping at 1.0 norm.
4. Linear LR schedule with warmup.
5. Dev loss evaluated on main process only (no cross-GPU reduce for SeamlessM4T, unlike IndicTrans2).
6. Best checkpoint saved to `checkpoints/seamless/<task>/best/` when dev loss improves.

---

### 27.4 DeepSpeed ZeRO-3 Configuration (`ds_zero3.json`)

Provided as an alternative to Accelerate FSDP for Linux deployments where DeepSpeed is available. Not used on Windows (where Gloo backend is required).

**Key settings:**

| Parameter | Value | Effect |
|-----------|-------|--------|
| ZeRO stage | 3 | Shards weights + gradients + optimizer states across all GPUs |
| bf16 | enabled | Native bfloat16 on Ampere GPUs |
| `overlap_comm` | true | Overlaps gradient communication with backward pass |
| `contiguous_gradients` | true | Reduces memory fragmentation |
| `reduce_bucket_size` | 5×10⁸ | 500 MB all-reduce buckets |
| `stage3_prefetch_bucket_size` | 5×10⁷ | 50 MB prefetch for forward pass |
| `stage3_param_persistence_threshold` | 1×10⁶ | Parameters smaller than 1M kept on GPU permanently |
| `stage3_gather_16bit_weights_on_model_save` | true | Reconstructs full fp16 weights for checkpoint saving |
| `allgather_bucket_size` | 5×10⁸ | 500 MB all-gather buckets |
| `reduce_scatter` | true | Uses reduce-scatter instead of all-reduce for gradients |
| Gradient clipping | 1.0 | Applied by DeepSpeed engine |
| Optimizer | AdamW | β=(0.9, 0.999), ε=1e-8, weight_decay=0.01 |
| Scheduler | WarmupDecayLR | Warmup + linear decay; all values set to `"auto"` |
| Activation checkpointing | enabled | 4 checkpoints, contiguous memory optimisation |
| `steps_per_print` | 50 | Loss logged every 50 steps |

ZeRO-3 allows training models that exceed single-GPU memory by partitioning all state across GPUs. For SeamlessM4T (~10 GB weights), ZeRO-3 across 4× A6000 reduces per-GPU weight memory from ~10 GB to ~2.5 GB, leaving the remaining VRAM for activations and batch data.

---

### 27.5 Checkpoint Integration with Pipeline

The pipeline automatically selects fine-tuned checkpoints over base model weights at runtime:

| Checkpoint Path | Used By | Fallback |
|-----------------|---------|---------|
| `checkpoints/indictrans/en_indic/best/` | `Translator` — English → Indic | `models/indic_tr/en_indic/` |
| `checkpoints/indictrans/indic_en/best/` | `Translator` — Indic → English (back-translation) | `models/indic_tr/indic_en/` |
| `checkpoints/indictrans/indic_indic/best/` | `Translator` — Indic → Indic | `models/indic_tr/indic_indic/` |
| `checkpoints/seamless/asr/best/` | `ASR` — SeamlessM4T speech recognition | `models/seamless/` |
| `checkpoints/seamless/t2t/best/` | `Translator` — SeamlessM4T text translation | `models/seamless/` |

The checkpoint selection logic checks for the presence of the `best/` subdirectory at pipeline initialisation time. If absent, the base model path is used without any code change required.

---

### 27.6 Training Infrastructure Summary

| Component | Specification |
|-----------|--------------|
| GPUs | 4× NVIDIA A6000 (48 GB VRAM each) |
| Total VRAM | 192 GB |
| Distributed framework | HuggingFace Accelerate + FSDP (Windows) / DeepSpeed ZeRO-3 (Linux) |
| Mixed precision | bfloat16 (bf16) — native on Ampere architecture |
| Communication backend | Gloo (Windows-compatible) / NCCL (Linux) |
| Gradient checkpointing | Enabled on all models — reduces activation memory at cost of ~30% compute |
| IndicTrans2 training time (en_indic, 5 epochs) | ~8–12 hours on 4× A6000 |
| SeamlessM4T training time (ASR, 3 epochs) | ~6–10 hours on 4× A6000 |
| SeamlessM4T training time (T2T, 3 epochs) | ~4–8 hours on 4× A6000 |

---

*Prepared By: Sanjana MS*

---

## Section 28 — Interview Preparation: Model Selection Rationale & Known Failure Modes

### 28.1 Why These Specific Models?

#### 28.1.1 Why IndicTrans2 over mBART, OPUS-MT, or M2M-100?

| Model | Why Not Chosen |
|-------|---------------|
| mBART-50 | Covers only 50 languages but uses a single shared BPE vocabulary — Indic scripts are severely under-represented, producing poor quality for low-resource languages like Bodo, Dogri, Santhali |
| OPUS-MT | Separate model per language pair — 22 languages would require 22+ separate model files, 22+ separate GPU loads, and 22+ separate fine-tuning runs. Not operationally viable |
| M2M-100 | 100-language multilingual model from Meta — not trained on Indian government domain data; no flores200 code alignment for all 22 scheduled languages |
| Google Translate API | Cloud-based — violates data sovereignty requirement; course content cannot leave the system boundary |
| **IndicTrans2** | **Only open-source model trained specifically on all 22 constitutionally scheduled Indian languages using flores200 script codes. Single model checkpoint handles all 22 languages in one GPU load. AI4Bharat trained it on Samanantar (49.7M pairs) + IN22 + FLORES-200 — the largest Indic parallel corpus available. Fine-tunable on domain data. MIT licence — fully commercial use permitted.** |

Key differentiator: IndicTrans2 uses **script-aware flores200 codes** (e.g. `ben_Beng`, `sat_Olck`, `urd_Arab`) which means the model knows the target script at generation time — it never confuses Bengali script with Assamese script even though both use the same Unicode block.

#### 28.1.2 Why SeamlessM4T as Fallback 1 over NLLB-200?

SeamlessM4T is placed before NLLB-200 in the fallback chain for two reasons:
1. It supports **Speech-to-Speech Translation (S2ST)** — the only model in the stack that can translate audio directly to audio, bypassing ASR and TTS entirely for Indic→Indic pairs.
2. For languages where IndicTrans2 struggles (Bodo, Dogri), SeamlessM4T's multilingual speech encoder provides better acoustic grounding than a pure text model.

NLLB-200 is used as the final fallback and as the primary engine for Kashmiri, Sindhi, and Konkani because SeamlessM4T does not include these three languages in its text translation vocabulary.

#### 28.1.3 Why faster-whisper over OpenAI Whisper or IndicWav2Vec?

| Model | Why Not Chosen |
|-------|---------------|
| OpenAI Whisper (PyTorch) | 2–4× slower than faster-whisper on the same hardware; no VAD filter; higher VRAM usage |
| IndicWav2Vec | Language-specific — separate model per language; does not support all 22 languages; no sentence-level timestamps |
| Wav2Vec2 | Requires language-specific fine-tuning; no multilingual single-model option for all 22 languages |
| **faster-whisper large-v3** | **CTranslate2-quantised — int8 on CPU, float16 on GPU. 2–4× faster than PyTorch Whisper with identical accuracy. Single model handles all 22 languages. Built-in VAD filter eliminates silence hallucination. Word-level timestamps enable precise segment merging. `condition_on_previous_text=False` prevents repetition loops on low-quality audio.** |

#### 28.1.4 Why Parler-TTS over Coqui XTTS-v2, Bark, or MMS-TTS as Primary?

| Model | Why Not Primary |
|-------|----------------|
| Coqui XTTS-v2 | Excellent voice cloning but requires a reference WAV per language — not suitable as a zero-shot primary TTS for 22 languages. Slower inference than Parler. |
| Bark | Very slow (30–60s per sentence on GPU); no Indic language fine-tuning; produces inconsistent voice across segments |
| MMS-TTS | Requires per-language adapter swap — one model load per language change. Produces robotic, low-naturalness speech. 16kHz output vs Parler's 44kHz. |
| ElevenLabs / Azure TTS | Cloud-based — violates data sovereignty requirement |
| **Parler-TTS Indic Large** | **Single model checkpoint covers all 22 Indian languages. 44kHz output — highest audio quality in the stack. GPU-batchable (32 segments per pass). Fixed seed per language produces consistent voice across all segments of a course. AI4Bharat fine-tuned specifically on Indic speech data. Apache 2.0 licence.** |

The one weakness of Parler-TTS: it cannot render Ol Chiki script (Santhali), Arabic script (Kashmiri, Sindhi), or produce reliable output for these three languages — hence the direct fallback to MMS-TTS for `sat`, `kas`, `snd`.

#### 28.1.5 Why NLLB-200 over mBART-50 as Final Fallback?

NLLB-200 (No Language Left Behind) was specifically designed by Meta to cover low-resource languages. It includes all 22 Indian scheduled languages with dedicated vocabulary entries, whereas mBART-50 has poor coverage for Bodo, Dogri, Santhali, Konkani, Sindhi, and Kashmiri. NLLB-200 distilled 600M is ~2.4 GB — small enough to keep resident in GPU memory alongside IndicTrans2.

---

### 28.2 Known Failure Modes Observed During Development & Testing

These are real failure modes encountered while building and testing the system — not theoretical edge cases.

#### 28.2.1 Whisper Hallucination on Silent Segments

**What happened:** On videos with long silent pauses (e.g. slide transitions, presenter pausing), faster-whisper would emit hallucinated text — typically repeated phrases like "Thank you for watching", "Subscribe to our channel", or random English words — even when the audio was silent.

**Root cause:** Whisper was trained on internet audio which often has these phrases at segment boundaries. Without VAD, it fills silence with the most probable continuation from its training distribution.

**Fix applied:** `vad_filter=True` with `min_silence_duration_ms=500` pre-filters silent regions before transcription. `condition_on_previous_text=False` prevents the model from conditioning on its own prior hallucinated output. `_strip_hallucinations()` regex catches any that slip through.

#### 28.2.2 IndicTrans2 Batch Size Mismatch

**What happened:** When a batch of 32 segments was sent to IndicTrans2, the output list occasionally had 31 or 33 items — one segment was either merged or split by the tokeniser's internal sentence boundary detection.

**Root cause:** IndicTrans2's `IndicProcessor` applies sentence normalisation that can split a segment containing multiple sentences into two outputs, or merge two very short segments into one.

**Fix applied:** Completeness guard in `translate_batch()`: `if len(output) != len(input): raise RuntimeError` → falls back to per-segment translation. Per-segment translation is slower but guarantees 1-to-1 alignment between input and output.

#### 28.2.3 MMS-TTS Repetition Loop

**What happened:** MMS-TTS (VITS architecture) would occasionally produce 30–60 seconds of repeated audio for a 5-word input — the model entered a repetition loop in the VITS decoder.

**Root cause:** VITS is sensitive to input length. Inputs over ~450 tokens cause the duration predictor to produce extremely long outputs, which the decoder then fills with repeated phonemes.

**Fix applied:** Hard token limit of 450 tokens in `_synthesize_mms_batch()`. Segments exceeding this are rejected (not truncated — truncation produces cut-off words) and fall through to XTTS-v2.

#### 28.2.4 GPU OOM on Parler-TTS with Long Segments

**What happened:** Segments longer than ~200 characters caused `torch.cuda.OutOfMemoryError` on 16GB VRAM GPUs when Parler-TTS was generating with `max_new_tokens=1500`.

**Root cause:** Parler-TTS uses a codec-based architecture where the KV cache grows quadratically with sequence length. Very long segments exhaust VRAM before generation completes.

**Fix applied:** `_calc_max_tokens()` computes a dynamic token budget per segment based on grapheme count (`graphemes × 25`, clamped to 200–1500). OOM handler: `torch.cuda.empty_cache()` + retry once. On second failure, fall through to MMS-TTS.

#### 28.2.5 Nastaliq Encoding Mismatch for Urdu

**What happened:** Urdu ASR output from faster-whisper used Arabic Unicode codepoints (e.g. Arabic kaf `ك` U+0643) instead of Urdu Nastaliq codepoints (Urdu kaf `ک` U+06A9). IndicTrans2's Urdu tokeniser expected Nastaliq codepoints and produced garbage output — random Devanagari characters mixed with Arabic script.

**Root cause:** faster-whisper's Whisper model was trained on mixed Arabic/Urdu data and does not consistently use Nastaliq-specific codepoints. The two characters look identical in most fonts but are different Unicode codepoints.

**Fix applied:** `_normalize_nastaliq()` in `pipeline/asr.py` applies a character-level substitution map for all Arabic-script languages (`urd`, `kas`, `snd`) before the transcript is passed to the translation engine.

#### 28.2.6 Subtitle SRT Index Corruption

**What happened:** When empty segments (quality score < 0.30, text set to `""`) were included in the SRT file, some media players would display a blank subtitle at that timestamp and then lose sync for all subsequent subtitles — the SRT index counter was incrementing for empty entries.

**Root cause:** SRT format requires sequential 1-based indices. If index 5 is blank and index 6 follows, some players treat the blank as a formatting error and reset their parser state.

**Fix applied:** `generate_srt()` skips segments where `text.strip() == ""` entirely — they are not written to the SRT file and the index counter does not increment for them.

#### 28.2.7 Checkpoint File Corruption on Windows

**What happened:** On Windows, if the process was killed (Ctrl+C or Task Manager) exactly while `json.dump()` was writing the checkpoint file, the file would be left as a partial JSON — missing the closing `}` — causing `json.JSONDecodeError` on the next resume attempt.

**Root cause:** Python's `json.dump()` writes incrementally. A kill signal mid-write leaves a partial file. On Linux, `os.rename()` is atomic; on Windows, it is not guaranteed atomic across drives.

**Fix applied:** Write-to-`.tmp`-then-rename pattern in `JobCheckpoint.flush()`: write complete JSON to `<job_id>.tmp`, then `os.replace(<job_id>.tmp, <job_id>.json)`. `os.replace()` is atomic on Windows within the same drive. If the `.tmp` file exists on startup (indicating a crash during write), it is deleted and the previous `.json` is used.

#### 28.2.8 ffmpeg atempo Filter Limit

**What happened:** For very long TTS segments (e.g. a 15-second segment that needed to fit into a 6-second slot), the required speed ratio was ~2.5×. The ffmpeg `atempo` filter only accepts values between 0.5 and 2.0 — passing `atempo=2.5` caused ffmpeg to return a non-zero exit code and the segment was placed at original speed, overrunning its slot.

**Root cause:** ffmpeg `atempo` filter has a hard limit of 0.5–2.0 per filter instance.

**Fix applied:** `_atempo_stretch_file()` chains multiple `atempo` filters for ratios outside the 0.5–2.0 range: `atempo=2.0,atempo=<ratio/2.0>` for ratios > 2.0. However, the pipeline caps speed-up at 1.35× anyway — beyond that, hard-trim is applied. The chained filter handles edge cases where the cap is temporarily exceeded.

#### 28.2.9 Bodo Language Code Confusion

**What happened:** Early versions of the pipeline used `bod_Tibt` (Tibetan script) as the IndicTrans2 code for Bodo, producing Tibetan-script output for Bodo content. Bodo is a Tibeto-Burman language but is written in Devanagari script in India.

**Root cause:** The ISO 639-3 code `bod` is assigned to Tibetan. Bodo's correct code is `brx` (Boro). The flores200 dataset uses `brx_Deva` for Bodo in Devanagari.

**Fix applied:** `lang_config.py` maps internal code `bod` to `brx_Deva` for IndicTrans2 and NLLB-200, and `brx` for SeamlessM4T. The `_SCRIPT_RANGES` dict in `quality.py` maps `bod` to the Devanagari range `\u0900-\u097F` (not Tibetan `\u0F00-\u0FFF`). A comment in `lang_config.py` explicitly documents this: `# bod = Bodo (brx_Deva) — NOT Tibetan (bod_Tibt)`.

#### 28.2.10 Translation Memory Fuzzy Match False Positives

**What happened:** The fuzzy match threshold was initially set at 0.70. This caused "Annual Performance Report" to match "Annual Performance Review" (ratio ~0.88) and return the wrong translation — the TM entry for "Report" was being used for "Review".

**Root cause:** `difflib.SequenceMatcher.ratio()` measures character-level similarity, not semantic similarity. Two phrases that differ by only one word can have a very high character ratio even if they mean different things.

**Fix applied:** Threshold raised to 0.85. At 0.85, single-word differences in short phrases (< 5 words) are less likely to match. Additionally, fuzzy matches set `needs_review=True` in the quality score — a human reviewer sees the match and can confirm or reject it.

---

### 28.3 Questions You Should Be Ready to Answer

Based on the system design, these are the most likely technical interview questions and the key points to hit in each answer:

| Question | Key Points |
|----------|-----------|
| Walk me through the pipeline end-to-end | 6 steps: extract audio → S2ST fast path → ASR → translate → TTS → assemble+mux. Mention checkpoint at each step. |
| How do you handle a crash mid-job? | JobCheckpoint saves each segment result atomically. On restart, `is_done(seg_id)` skips completed segments. ASR is the most expensive — saved first. |
| How do you ensure no wrong-language audio in output? | Quality gate: score < 0.30 → `text = ""` → silence written. Three scoring methods: heuristic (8 checks), ChrF, back-translation. |
| Why not just use Google Translate? | Data sovereignty — course content cannot leave the system. IT Act 2000 compliance. All models run on-premise. |
| How does multi-GPU work? | ASR runs once in main process. 22 languages distributed round-robin across GPUs via `multiprocessing.spawn`. Each worker gets `CUDA_VISIBLE_DEVICES` set. |
| What is the S2ST fast path? | SeamlessM4Tv2 translates audio directly to audio for 5 Indic→Indic pairs (hin/ben/kan/tel/urd). Bypasses ASR and TTS entirely. Falls back to full pipeline on failure. |
| How do you handle low-resource languages like Bodo or Santhali? | Bodo: SeamlessM4T primary (better acoustic grounding). Santhali: Hindi pivot (eng→hin→sat). Ol Chiki transliteration for Parler-TTS. MMS-TTS with sat adapter as fallback. |
| What is the Translation Memory and how is it used? | JSONL store of government-verified terms. Exact match bypasses translation engine entirely. Fuzzy match at 0.85 threshold. Human feedback upweighted 3× in fine-tuning. |
| How do you protect numbers and dates in translation? | Three-layer token protection: `__FMT__` for format tokens, `__NT__` for URLs/code, `__F__` for factual tokens (numbers/dates/currency). Restored after translation. `_verify_factual_tokens()` appends any missing ones. |
| What happens if Parler-TTS runs out of memory? | `torch.cuda.empty_cache()` + retry once. On second failure, fall through to MMS-TTS. Dynamic token budget (`graphemes × 25`) prevents most OOM cases. |
| How is voice consistency maintained across segments? | Fixed seed per language in `_LANG_SEEDS`. `torch.manual_seed(seed)` called before every Parler generate call. Same seed → same voice character every time. |
| What does the QA certificate contain? | Course ID, language, quality scores (heuristic/ChrF/back-translation), 7-item certification checklist, reviewer declaration, signature. KB tender §4.5 deliverable. |
| How does fine-tuning improve translation quality? | Domain data (Samanantar + govt_tm.jsonl) + curriculum learning (gold first, synthetic from epoch 3) + label smoothing (0.1) + per-language sampling weights (4× for low-resource). Dev loss checkpoint selection prevents overfitting. |
| What is the duration ratio check? | `output_duration / original_duration`. If > 1.20×, KB approval required before payment (tender §5.1B). Fit-to-slot (max 1.35× atempo speed-up) reduces likelihood of exceeding threshold. |
| How do you detect PM/President speeches? | Keyword regex on full transcript after ASR. If matched, job returns immediately with exclusion reason. Logged to audit.log. No translation performed. |

---

*Prepared By: Sanjana MS*
