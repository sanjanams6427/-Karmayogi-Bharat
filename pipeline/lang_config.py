# ============================================================
# Language Configuration & Model Routing for all 22 languages
# ============================================================

# IndicTrans2 language codes (flores200 format)
INDIC_TRANS2_CODES = {
    "asm": "asm_Beng",   # Assamese
    "ben": "ben_Beng",   # Bengali
    "guj": "guj_Gujr",   # Gujarati
    "hin": "hin_Deva",   # Hindi
    "kan": "kan_Knda",   # Kannada
    "mal": "mal_Mlym",   # Malayalam
    "mar": "mar_Deva",   # Marathi
    "ory": "ory_Orya",   # Odia
    "pan": "pan_Guru",   # Punjabi
    "tam": "tam_Taml",   # Tamil
    "tel": "tel_Telu",   # Telugu
    "bod": "brx_Deva",   # Bodo  (flores200: brx_Deva — Devanagari, NOT Tibetan bod_Tibt)
    "doi": "doi_Deva",   # Dogri
    "kas": "kas_Arab",   # Kashmiri
    "kok": "gom_Deva",   # Konkani — IndicTrans2 uses gom_Deva (Goan Konkani / flores200)
    "mni": "mni_Beng",   # Manipuri
    "mai": "mai_Deva",   # Maithili
    "nep": "npi_Deva",   # Nepali — flores200 code is npi not nep
    "san": "san_Deva",   # Sanskrit
    "sat": "sat_Olck",   # Santhali
    "snd": "snd_Arab",   # Sindhi
    "urd": "urd_Arab",   # Urdu
    "eng": "eng_Latn",   # English (pivot)
}

# SeamlessM4T language codes (text translation — broader support)
SEAMLESS_CODES = {
    "eng": "eng",
    "ben": "ben", "guj": "guj", "hin": "hin", "kan": "kan",
    "mal": "mal", "mar": "mar", "ory": "ory", "pan": "pan",
    "tam": "tam", "tel": "tel", "urd": "urd", "nep": "npi",
    "mai": "mai", "snd": "snd", "asm": "asm", "mni": "mni",
    "sat": "sat",
    # bod (Bodo/Boro) — SeamlessM4T supports brx (Bodo) text translation
    "bod": "brx",
    # doi (Dogri) — SeamlessM4T supports doi text translation
    "doi": "doi",
}

# SeamlessM4T S2ST — speech OUTPUT supported langs only (subset of SEAMLESS_CODES)
# Source: SeamlessM4Tv2 model card — only these Indian langs support speech synthesis output
# tam/mal/ory/pan/guj/asm/mai/snd NOT supported for S2ST speech output
# S2ST only applies for Indic→Indic pairs — English source always uses ASR→Translate→TTS
SEAMLESS_S2ST_LANGS = {
    "ben": "ben", "hin": "hin", "kan": "kan",
    "tel": "tel", "urd": "urd",
}

# NLLB-200 language codes
NLLB_CODES = {
    "eng": "eng_Latn",
    "asm": "asm_Beng", "ben": "ben_Beng", "guj": "guj_Gujr",
    "hin": "hin_Deva", "kan": "kan_Knda", "mal": "mal_Mlym",
    "mar": "mar_Deva", "ory": "ory_Orya", "pan": "pan_Guru",
    "tam": "tam_Taml", "tel": "tel_Telu", "urd": "urd_Arab",
    "nep": "npi_Deva", "mai": "mai_Deva", "snd": "snd_Arab",
    "kas": "kas_Arab", "kok": "kok_Deva", "mni": "mni_Beng",
    "san": "san_Deva", "sat": "sat_Olck", "doi": "doi_Deva",
    "bod": "brx_Deva",  # Bodo — NLLB uses brx_Deva (Bodo/Boro in Devanagari), NOT bod_Tibt (Tibetan)
}

# IndicWhisper language codes
INDIC_WHISPER_CODES = {
    "asm": "as", "ben": "bn", "guj": "gu", "hin": "hi",
    "kan": "kn", "mal": "ml", "mar": "mr", "ory": "or",
    "pan": "pa", "tam": "ta", "tel": "te", "urd": "ur",
    "nep": "ne", "mai": "mai", "snd": "sd", "kas": "ks",
    "kok": "kok", "mni": "mni", "san": "sa", "bod": "bo",
    "sat": "sat", "doi": "doi",
}

# Human-readable names
LANG_NAMES = {
    "asm": "Assamese",  "ben": "Bengali",   "guj": "Gujarati",
    "hin": "Hindi",     "kan": "Kannada",   "mal": "Malayalam",
    "mar": "Marathi",   "ory": "Odia",      "pan": "Punjabi",
    "tam": "Tamil",     "tel": "Telugu",    "bod": "Bodo",
    "doi": "Dogri",     "kas": "Kashmiri",  "kok": "Konkani",
    "mni": "Manipuri",  "mai": "Maithili",  "nep": "Nepali",
    "san": "Sanskrit",  "sat": "Santhali",  "snd": "Sindhi",
    "urd": "Urdu",      "eng": "English",
}

ALL_22 = [
    "asm","ben","guj","hin","kan","mal","mar","ory","pan","tam","tel",
    "bod","doi","kas","kok","mni","mai","nep","san","sat","snd","urd",
]

# ASR: faster-whisper large-v3 handles all 22 languages natively.
# TTS: Indic Parler-TTS handles all 22 languages with a single model load.
# No MMS models needed — removed to eliminate per-language adapter swap overhead.
