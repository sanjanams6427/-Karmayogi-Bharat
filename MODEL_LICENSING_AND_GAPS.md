# Model Licensing & Open-Source Gap Analysis
**Project:** KB Translation System — 22 Indian Languages
**Tender:** iGOT Karmayogi | RFB IN-KBL-543730-NC-RFB
**Document Purpose:** Honest assessment of every model used, its license status, and risks for a Government of India deployment.

---

## 1. Complete Model Inventory

| # | Model | HuggingFace Repo | Role in Pipeline | License | Commercial Use? |
|---|-------|-----------------|-----------------|---------|----------------|
| 1 | faster-whisper large-v3 | `Systran/faster-whisper-large-v3` | ASR — transcription of all 22 langs | MIT | ✅ Yes |
| 2 | IndicTrans2 en→indic (1B) | `ai4bharat/indictrans2-en-indic-1B` | Translation: English → 22 Indian langs | MIT | ✅ Yes |
| 3 | IndicTrans2 indic→en (1B) | `ai4bharat/indictrans2-indic-en-1B` | Translation: Indian → English | MIT | ✅ Yes |
| 4 | IndicTrans2 indic→indic (1B) | `ai4bharat/indictrans2-indic-indic-1B` | Translation: Indian → Indian | MIT | ✅ Yes |
| 5 | SeamlessM4Tv2 Large | `facebook/seamless-m4t-v2-large` | Translation fallback + S2ST | CC-BY-NC 4.0 | ❌ **NO** |
| 6 | NLLB-200 (3.3B distilled) | `facebook/nllb-200-distilled-3.3B` | Translation last-resort fallback | CC-BY-NC 4.0 | ❌ **NO** |
| 7 | Indic Parler-TTS Large | `ai4bharat/indic-parler-tts-pretrained` | TTS primary — Hindi/Marathi/Nepali/Maithili/Sanskrit | MIT | ✅ Yes |
| 8 | Indic Parler-TTS Mini | `ai4bharat/indic-parler-tts` | TTS fallback for above | MIT | ✅ Yes |
| 9 | MMS-TTS (22 standalone VITS) | `facebook/mms-tts-*` | TTS for all 22 langs (fallback chain) | CC-BY-NC 4.0 | ❌ **NO** |
| 10 | Flan-T5 Large | `google/flan-t5-large` | Text encoder for Parler-TTS description tokenizer | Apache 2.0 | ✅ Yes |
| 11 | Coqui XTTS-v2 | `coqui/XTTS-v2` | Voice cloning (KB Tier 2 feature) | Coqui Public Model License | ⚠️ **Restricted** |

---

## 2. Non-Commercial Models — Detail & Risk

### 2.1 SeamlessM4Tv2 Large — `CC-BY-NC 4.0`
**Used for:**
- Translation fallback for Manipuri (mni), Santhali (sat) — IndicTrans2 pivot quality is poor for these
- Primary for Kashmiri (kas), Sindhi (snd), Konkani (kok) when NLLB also fails
- Speech-to-Speech (S2ST) for Hindi↔Bengali↔Kannada↔Telugu↔Urdu pairs
- Score-based second opinion against IndicTrans2 for all 22 langs

**Why we can't just remove it:**
- Manipuri and Santhali have no other working translation path. IndicTrans2 routes them via Hindi pivot which produces poor quality. NLLB-200 coverage for these two is also weak. SeamlessM4T is the only model that handles them with acceptable quality.
- S2ST (speech-to-speech) is a unique capability of SeamlessM4T. No open-source alternative exists that does direct Indic speech-to-speech translation without going through ASR+MT+TTS.
- The score-based second opinion (comparing SeamlessM4T vs IndicTrans2 output and picking the better one) meaningfully improves quality for low-resource languages. Removing it degrades output quality for ~8 of the 22 languages.

**License risk for GoI:** CC-BY-NC 4.0 explicitly prohibits "commercial purposes." A government tender with payment is legally a commercial transaction. Meta has not issued a government/public-sector exemption for this model.

---

### 2.2 NLLB-200 Distilled 3.3B — `CC-BY-NC 4.0`
**Used for:**
- Primary translation engine for Kashmiri (kas), Sindhi (snd), Konkani (kok) — IndicTrans2 produces Hindi/garbage for these
- Final fallback for all 22 languages when IndicTrans2 and SeamlessM4T both fail
- Drift correction: when IndicTrans2 produces Maithili output for Hindi target (or vice versa), NLLB is called as a corrective retry

**Why we can't just remove it:**
- Kashmiri, Sindhi, and Konkani have no viable open-source alternative. IndicTrans2 does not reliably produce correct output for these three languages — it drifts to Hindi or produces transliterated garbage. NLLB-200 is the only model in the open-source ecosystem that covers all three with reasonable quality.
- The NLLB-200 MIT-licensed variant (`facebook/nllb-200-distilled-600M`) exists but is significantly weaker — it fails on longer sentences and produces more hallucinations for low-resource Indic languages.
- Removing NLLB entirely means kas/snd/kok have no translation path at all. These are 3 of the 22 scheduled languages required by the tender.

**License risk for GoI:** Same as SeamlessM4T — CC-BY-NC 4.0, no government exemption from Meta.

---

### 2.3 MMS-TTS (facebook/mms-tts-*) — `CC-BY-NC 4.0`
**Used for:**
- TTS for all 22 languages as the primary or fallback engine
- Primary TTS for: Tamil, Telugu, Kannada, Malayalam, Bengali, Assamese, Manipuri, Punjabi, Odia, Gujarati, Urdu, Kashmiri (22 standalone VITS models)
- Fallback TTS when Parler-TTS fails for any language

**Why we can't just remove it:**
- Parler-TTS Indic Large only reliably produces natural speech for Devanagari-script languages (Hindi, Marathi, Nepali, Maithili, Sanskrit). For Dravidian scripts (Tamil, Telugu, Kannada, Malayalam) and Bengali-family scripts, Parler produces near-silence or very low amplitude output — it was not trained on these scripts.
- There is no open-source, commercially-licensed TTS model that covers all 22 Indian scheduled languages. This is the single biggest gap in the Indian NLP open-source ecosystem.
- The only alternatives are:
  - **Coqui XTTS-v2** — covers ~10 Indian languages but has its own restrictive license (see below)
  - **IIT Madras TTS** — covers Tamil/Telugu/Hindi but not all 22, and the license for commercial use is unclear
  - **Vakyansh/IITB** — covers some languages but models are not production-ready and have no clear commercial license
  - **Google Cloud TTS / Azure TTS** — commercial APIs, require internet, violate the offline requirement of this tender

**License risk for GoI:** CC-BY-NC 4.0 on all 22 MMS-TTS models. This is the highest-risk item because MMS-TTS is used in the critical path for the majority of the 22 languages.

---

### 2.4 Coqui XTTS-v2 — `Coqui Public Model License 1.0`
**Used for:**
- Voice cloning feature (KB Tier 2 pricing)
- Last-resort TTS fallback for 10 languages (hin/ben/guj/mar/tam/tel/kan/mal/pan/urd)

**License terms:** The Coqui Public Model License allows use "for research and personal use only." Commercial use requires a separate paid license from Coqui AI. Coqui AI the company shut down in January 2024 — it is currently unclear who holds the commercial licensing rights or whether new commercial licenses can be obtained.

**Risk:** Voice cloning is a Tier 2 deliverable. If this feature is demonstrated or deployed under the tender, it may constitute commercial use of a model with no available commercial license path (company is defunct).

---

## 3. Summary Risk Table

| Model | License | Risk Level | Affects Languages | Can Be Replaced? |
|-------|---------|-----------|------------------|-----------------|
| SeamlessM4Tv2 | CC-BY-NC 4.0 | 🔴 HIGH | mni, sat, kas, snd, kok + S2ST | Partially — mni/sat have no good alternative |
| NLLB-200 3.3B | CC-BY-NC 4.0 | 🔴 HIGH | kas, snd, kok (primary) + all 22 (fallback) | No — kas/snd/kok have no alternative |
| MMS-TTS (×22) | CC-BY-NC 4.0 | 🔴 CRITICAL | All 22 languages (TTS) | No — no open-source commercial alternative covers all 22 |
| Coqui XTTS-v2 | Coqui PML 1.0 | 🟠 MEDIUM | Voice cloning (Tier 2) | Partially — can be disabled for Tier 1 |

---

## 4. What Is Fully Open-Source & Commercial-Safe

These models are MIT or Apache 2.0 licensed and safe for government commercial deployment:

| Model | License | Role |
|-------|---------|------|
| faster-whisper large-v3 | MIT | ASR — all 22 languages |
| IndicTrans2 (all 3 directions) | MIT | Translation — primary engine |
| Indic Parler-TTS Large | MIT | TTS — Devanagari languages (hin/mar/nep/mai/san) |
| Indic Parler-TTS Mini | MIT | TTS fallback |
| Flan-T5 Large | Apache 2.0 | Parler text encoder |

**Honest assessment:** The MIT-licensed stack alone covers ASR for all 22 languages and translation for ~17 of 22 languages adequately. It covers TTS well only for 5 Devanagari-script languages. The remaining 17 languages have degraded or no TTS without MMS-TTS.

---

## 5. Gaps With No Current Open-Source Solution

These are genuine ecosystem gaps — not a project design choice:

### Gap 1: TTS for non-Devanagari Indian languages (CRITICAL)
There is no MIT/Apache-licensed TTS model that covers Tamil, Telugu, Kannada, Malayalam, Bengali, Assamese, Punjabi, Gujarati, Odia, Urdu, Kashmiri, Sindhi, Santhali, Manipuri, Konkani, Dogri, or Bodo with production-quality speech synthesis. The entire Indian TTS open-source ecosystem (Vakyansh, IIT Madras, AI4Bharat) either has unclear commercial licensing or does not cover all 22 languages.

### Gap 2: Translation for Kashmiri, Sindhi, Konkani
IndicTrans2 (MIT) does not produce reliable output for these three languages — it drifts to Hindi. NLLB-200 (CC-BY-NC) is the only model that handles them. No MIT/Apache alternative exists for these three languages.

### Gap 3: Manipuri and Santhali translation quality
IndicTrans2 handles these via Hindi pivot with poor quality. SeamlessM4T (CC-BY-NC) is the only model that handles them directly. No MIT/Apache alternative exists.

### Gap 4: Speech-to-Speech translation
SeamlessM4T is the only open-source model capable of direct speech-to-speech translation between Indian languages. No MIT/Apache alternative exists.

---

## 6. Recommended Actions for GoI Compliance

1. **Seek a government/public-sector license from Meta** for SeamlessM4T and NLLB-200. Meta has issued such licenses for research institutions before. A formal request citing the public interest nature of iGOT Karmayogi is the most practical path.

2. **Commission AI4Bharat or C-DAC to develop MIT-licensed TTS models** for the 17 non-Devanagari languages. This is a gap that affects every Indian government NLP project, not just this one. A funded model development effort would resolve it permanently.

3. **For Tier 1 delivery:** Disable voice cloning (Coqui XTTS-v2) entirely. It is a Tier 2 feature and its license situation is unresolvable (company defunct).

4. **Document the gap formally in the tender submission.** The tender requires 22 languages. The honest position is: 5 languages have fully open-source TTS, 17 do not. This should be disclosed rather than hidden.

5. **Evaluate NLLB-200 600M (MIT)** as a replacement for NLLB-200 3.3B (CC-BY-NC) for the fallback path. Quality will be lower but it removes the license risk for the fallback chain. kas/snd/kok primary translation still has no MIT alternative.

---

*Document generated from codebase analysis of pipeline/tts.py, pipeline/translator.py, pipeline/asr.py, scripts/download_models.py*
*Last updated: based on current project state*
