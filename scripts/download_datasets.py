# ============================================
# KB Translation System
# Download ALL Datasets Script
# ============================================

import os
import sys
import time
import logging
from datasets import load_dataset
from huggingface_hub import snapshot_download
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/dataset_download.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# ============================================
# ALL 22 INDIAN LANGUAGE CODES
# ============================================

INDIC_LANG_CODES = [
    "asm",  # Assamese
    "ben",  # Bengali
    "bod",  # Bodo
    "doi",  # Dogri
    "guj",  # Gujarati
    "hin",  # Hindi
    "kan",  # Kannada
    "kas",  # Kashmiri
    "kok",  # Konkani
    "mai",  # Maithili
    "mal",  # Malayalam
    "mni",  # Manipuri
    "mar",  # Marathi
    "nep",  # Nepali
    "ory",  # Odia
    "pan",  # Punjabi
    "san",  # Sanskrit
    "sat",  # Santhali
    "snd",  # Sindhi
    "tam",  # Tamil
    "tel",  # Telugu
    "urd",  # Urdu
]

# ============================================
# AUDIO / SPEECH DATASETS
# ============================================

AUDIO_DATASETS = {

    # ----------------------------------------
    # Kathbath - 1684 hours, 22 Indian langs
    # Best: All 22 scheduled Indian languages
    # ----------------------------------------
    # kathbath is gated - requires manual approval at https://huggingface.co/datasets/ai4bharat/kathbath
    # "kathbath": { "repo_id": "ai4bharat/kathbath", ... },

    # ----------------------------------------
    # FLEURS - Google, 22 Indian languages
    # ----------------------------------------
    "fleurs_asm": {
        "repo_id":   "google/fleurs",
        "config":    "as_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/assamese",
        "size":      "~500MB",
        "languages": "Assamese"
    },
    "fleurs_ben": {
        "repo_id":   "google/fleurs",
        "config":    "bn_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/bengali",
        "size":      "~500MB",
        "languages": "Bengali"
    },
    "fleurs_guj": {
        "repo_id":   "google/fleurs",
        "config":    "gu_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/gujarati",
        "size":      "~500MB",
        "languages": "Gujarati"
    },
    "fleurs_hin": {
        "repo_id":   "google/fleurs",
        "config":    "hi_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/hindi",
        "size":      "~500MB",
        "languages": "Hindi"
    },
    "fleurs_kan": {
        "repo_id":   "google/fleurs",
        "config":    "kn_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/kannada",
        "size":      "~500MB",
        "languages": "Kannada"
    },
    "fleurs_mal": {
        "repo_id":   "google/fleurs",
        "config":    "ml_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/malayalam",
        "size":      "~500MB",
        "languages": "Malayalam"
    },
    "fleurs_mar": {
        "repo_id":   "google/fleurs",
        "config":    "mr_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/marathi",
        "size":      "~500MB",
        "languages": "Marathi"
    },
    "fleurs_ory": {
        "repo_id":   "google/fleurs",
        "config":    "or_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/odia",
        "size":      "~500MB",
        "languages": "Odia"
    },
    "fleurs_pan": {
        "repo_id":   "google/fleurs",
        "config":    "pa_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/punjabi",
        "size":      "~500MB",
        "languages": "Punjabi"
    },
    "fleurs_tam": {
        "repo_id":   "google/fleurs",
        "config":    "ta_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/tamil",
        "size":      "~500MB",
        "languages": "Tamil"
    },
    "fleurs_tel": {
        "repo_id":   "google/fleurs",
        "config":    "te_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/telugu",
        "size":      "~500MB",
        "languages": "Telugu"
    },
    "fleurs_urd": {
        "repo_id":   "google/fleurs",
        "config":    "ur_pk",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/urdu",
        "size":      "~500MB",
        "languages": "Urdu"
    },
    "fleurs_nep": {
        "repo_id":   "google/fleurs",
        "config":    "ne_np",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/nepali",
        "size":      "~500MB",
        "languages": "Nepali"
    },

    # ----------------------------------------
    # IndicSUPERB - 22 Indian languages
    # Correct repo: alekya/IndicSUPERB
    # ----------------------------------------
    "indicsuper": {
        "repo_id":   "alekya/IndicSUPERB",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/indicsuper",
        "size":      "~10GB",
        "hours":     "~300 hours",
        "languages": "All 22 Indian languages",
        "use_for":   "ASR evaluation benchmark"
    },

    # ----------------------------------------
    # Common Voice - Mozilla
    # GATED: requires HF token + accept terms at commonvoice.mozilla.org
    # All CV versions on HF Hub have no data files without authentication.
    # To enable: set HF_TOKEN env var, accept terms, then uncomment.
    # ----------------------------------------
    # "common_voice_hin": { "repo_id": "mozilla-foundation/common_voice_17_0", "config": "hi", "type": "huggingface", "local_dir": "./datasets/audio/common_voice/hindi", "size": "~2GB", "languages": "Hindi" },
    # "common_voice_tam": { "repo_id": "mozilla-foundation/common_voice_17_0", "config": "ta", "type": "huggingface", "local_dir": "./datasets/audio/common_voice/tamil", "size": "~2GB", "languages": "Tamil" },
    # "common_voice_mar": { "repo_id": "mozilla-foundation/common_voice_17_0", "config": "mr", "type": "huggingface", "local_dir": "./datasets/audio/common_voice/marathi", "size": "~1GB", "languages": "Marathi" },
    # "common_voice_urd": { "repo_id": "mozilla-foundation/common_voice_17_0", "config": "ur", "type": "huggingface", "local_dir": "./datasets/audio/common_voice/urdu", "size": "~1GB", "languages": "Urdu" },
    # "common_voice_san": { "repo_id": "mozilla-foundation/common_voice_17_0", "config": "sa", "type": "huggingface", "local_dir": "./datasets/audio/common_voice/sanskrit", "size": "~500MB", "languages": "Sanskrit" },

    # ----------------------------------------
    # Sanskrit - Common Voice (requires HF_TOKEN + accept terms)
    # ----------------------------------------
    "common_voice_san": {
        "repo_id":   "mozilla-foundation/common_voice_17_0",
        "config":    "sa",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/common_voice/sanskrit",
        "size":      "~500MB",
        "languages": "Sanskrit"
    },

    # ----------------------------------------
    # Bodo - SPRINGLab ASR (~1-2 hours, only public Bodo audio on HF)
    # ----------------------------------------
    "bodo_asr": {
        "repo_id":   "XKaab/ASR-Bodo_5hrs",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/bodo_asr",
        "size":      "~200MB",
        "hours":     "~1-2 hours",
        "languages": "Bodo"
    },

    # ----------------------------------------
    # FLEURS - gap languages missing from above
    # ----------------------------------------
    "fleurs_kan": {
        "repo_id":   "google/fleurs",
        "config":    "kn_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/kannada",
        "size":      "~500MB",
        "languages": "Kannada"
    },
    "fleurs_mai": {
        "repo_id":   "google/fleurs",
        "config":    "mi_in",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/fleurs/maithili",
        "size":      "~300MB",
        "languages": "Maithili"
    },

    # ----------------------------------------
    # AI4Bharat IndicTTS - TTS/dubbing audio
    # Covers: Hindi, Bengali, Gujarati, Kannada, Malayalam,
    #         Marathi, Odia, Punjabi, Tamil, Telugu, Assamese
    # ----------------------------------------
    "indic_tts": {
        "repo_id":   "ai4bharat/indic-tts-coqui",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/indic_tts",
        "size":      "~5GB",
        "languages": "11 Indian languages TTS",
        "use_for":   "TTS / audio dubbing"
    },

    # ----------------------------------------
    # AI4Bharat Shrutilipi - ASR for gap languages
    # Covers: Dogri, Kashmiri, Konkani, Manipuri, Santhali, Sindhi
    # ----------------------------------------
    "shrutilipi": {
        "repo_id":   "ai4bharat/Shrutilipi",
        "type":      "huggingface",
        "local_dir": "./datasets/audio/shrutilipi",
        "size":      "~6GB",
        "hours":     "~6400 hours across 12 languages",
        "languages": "Dogri, Kashmiri, Konkani, Manipuri, Santhali, Sindhi + others",
        "use_for":   "ASR training for gap languages"
    },

}

# ============================================
# TEXT / TRANSLATION DATASETS
# ============================================

TEXT_DATASETS = {

    # ----------------------------------------
    # Samanantar - 49.7M parallel sentences
    # 11 Indian languages paired with English
    # ----------------------------------------
    "samanantar_ben": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "bn",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/bengali",
        "size":      "~2GB",
        "pairs":     "~9M sentence pairs",
        "languages": "English-Bengali"
    },
    "samanantar_guj": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "gu",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/gujarati",
        "size":      "~1GB",
        "pairs":     "~3M sentence pairs",
        "languages": "English-Gujarati"
    },
    "samanantar_hin": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "hi",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/hindi",
        "size":      "~3GB",
        "pairs":     "~8.5M sentence pairs",
        "languages": "English-Hindi"
    },
    "samanantar_kan": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "kn",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/kannada",
        "size":      "~1GB",
        "pairs":     "~4M sentence pairs",
        "languages": "English-Kannada"
    },
    "samanantar_mal": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "ml",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/malayalam",
        "size":      "~1GB",
        "pairs":     "~5.5M sentence pairs",
        "languages": "English-Malayalam"
    },
    "samanantar_mar": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "mr",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/marathi",
        "size":      "~1GB",
        "pairs":     "~3.5M sentence pairs",
        "languages": "English-Marathi"
    },
    "samanantar_ory": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "or",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/odia",
        "size":      "~500MB",
        "pairs":     "~1M sentence pairs",
        "languages": "English-Odia"
    },
    "samanantar_pan": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "pa",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/punjabi",
        "size":      "~500MB",
        "pairs":     "~2M sentence pairs",
        "languages": "English-Punjabi"
    },
    "samanantar_tam": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "ta",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/tamil",
        "size":      "~2GB",
        "pairs":     "~6M sentence pairs",
        "languages": "English-Tamil"
    },
    "samanantar_tel": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "te",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/telugu",
        "size":      "~1GB",
        "pairs":     "~5M sentence pairs",
        "languages": "English-Telugu"
    },
    "samanantar_asm": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "as",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/assamese",
        "size":      "~200MB",
        "pairs":     "~0.5M sentence pairs",
        "languages": "English-Assamese"
    },
    "samanantar_urd": {
        "repo_id":   "ai4bharat/samanantar",
        "config":    "ur",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/samanantar/urdu",
        "size":      "~500MB",
        "pairs":     "~0.8M sentence pairs",
        "languages": "English-Urdu"
    },

    # ----------------------------------------
    # FLORES-200 - All 22 Indian languages
    # Evaluation benchmark
    # ----------------------------------------
    "flores_200": {
        "repo_id":   "facebook/flores",
        "config":    "all",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200",
        "size":      "~500MB",
        "languages": "All 22 Indian languages",
        "use_for":   "Evaluation benchmark"
    },

    # ----------------------------------------
    # PMIndia - repo pmindia/pmindia-v1 does NOT exist on Hub
    # Replaced with opus-100 extra Indian lang pairs
    # ----------------------------------------
    "opus100_as": { "repo_id": "Helsinki-NLP/opus-100", "config": "as-en", "type": "huggingface", "local_dir": "./datasets/parallel/pmindia", "size": "~50MB", "languages": "Assamese-English" },

    # ============================================================
    # PARALLEL TEXT — GAP LANGUAGES (no Samanantar coverage)
    # Source: IndicTrans2 IN22 benchmark (ai4bharat/IN22-Gen)
    # Covers all 22 languages with English parallel sentences
    # ============================================================
    "in22_gen": {
        "repo_id":   "ai4bharat/IN22-Gen",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/in22_gen",
        "size":      "~50MB",
        "pairs":     "~1000 sentences × 22 languages",
        "languages": "All 22 Indian languages (English parallel)",
        "use_for":   "Parallel text for Bodo, Dogri, Kashmiri, Konkani, Maithili, Manipuri, Nepali, Sanskrit, Santhali, Sindhi"
    },
    "in22_conv": {
        "repo_id":   "ai4bharat/IN22-Conv",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/in22_conv",
        "size":      "~50MB",
        "pairs":     "~1000 sentences × 22 languages",
        "languages": "All 22 Indian languages (English parallel)",
        "use_for":   "Conversational parallel text for gap languages"
    },

    # ----------------------------------------
    # OPUS-100 parallel pairs for gap languages
    # ----------------------------------------
    "opus100_nep": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-ne",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/nepali",
        "size":      "~50MB",
        "pairs":     "~1M sentence pairs",
        "languages": "English-Nepali"
    },
    "opus100_san": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-sa",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/sanskrit",
        "size":      "~20MB",
        "pairs":     "~100K sentence pairs",
        "languages": "English-Sanskrit"
    },
    "opus100_snd": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-sd",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/sindhi",
        "size":      "~20MB",
        "pairs":     "~100K sentence pairs",
        "languages": "English-Sindhi"
    },
    "opus100_mai": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-mai",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/maithili",
        "size":      "~10MB",
        "pairs":     "~50K sentence pairs",
        "languages": "English-Maithili"
    },
    "opus100_kok": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-kok",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/konkani",
        "size":      "~10MB",
        "pairs":     "~50K sentence pairs",
        "languages": "English-Konkani"
    },
    "opus100_mni": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-mni",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/manipuri",
        "size":      "~10MB",
        "pairs":     "~50K sentence pairs",
        "languages": "English-Manipuri"
    },
    "opus100_kas": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-ks",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/kashmiri",
        "size":      "~10MB",
        "pairs":     "~50K sentence pairs",
        "languages": "English-Kashmiri"
    },
    "opus100_bod": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-bo",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/bodo",
        "size":      "~5MB",
        "pairs":     "~20K sentence pairs",
        "languages": "English-Bodo"
    },
    "opus100_doi": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-doi",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/dogri",
        "size":      "~5MB",
        "pairs":     "~20K sentence pairs",
        "languages": "English-Dogri"
    },
    "opus100_sat": {
        "repo_id":   "Helsinki-NLP/opus-100",
        "config":    "en-sat",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/opus100/santhali",
        "size":      "~5MB",
        "pairs":     "~20K sentence pairs",
        "languages": "English-Santhali"
    },

    # ----------------------------------------
    # FLORES-200 individual configs for gap languages
    # Small but high-quality parallel eval sets
    # ----------------------------------------
    "flores_bod": {
        "repo_id":   "facebook/flores",
        "config":    "bod_Tibt",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/bodo",
        "size":      "~5MB",
        "languages": "Bodo parallel (FLORES-200)"
    },
    "flores_doi": {
        "repo_id":   "facebook/flores",
        "config":    "doi_Deva",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/dogri",
        "size":      "~5MB",
        "languages": "Dogri parallel (FLORES-200)"
    },
    "flores_kas": {
        "repo_id":   "facebook/flores",
        "config":    "kas_Arab",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/kashmiri",
        "size":      "~5MB",
        "languages": "Kashmiri parallel (FLORES-200)"
    },
    "flores_kok": {
        "repo_id":   "facebook/flores",
        "config":    "kok_Deva",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/konkani",
        "size":      "~5MB",
        "languages": "Konkani parallel (FLORES-200)"
    },
    "flores_mai": {
        "repo_id":   "facebook/flores",
        "config":    "mai_Deva",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/maithili",
        "size":      "~5MB",
        "languages": "Maithili parallel (FLORES-200)"
    },
    "flores_mni": {
        "repo_id":   "facebook/flores",
        "config":    "mni_Mtei",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/manipuri",
        "size":      "~5MB",
        "languages": "Manipuri parallel (FLORES-200)"
    },
    "flores_nep": {
        "repo_id":   "facebook/flores",
        "config":    "npi_Deva",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/nepali",
        "size":      "~5MB",
        "languages": "Nepali parallel (FLORES-200)"
    },
    "flores_san": {
        "repo_id":   "facebook/flores",
        "config":    "san_Deva",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/sanskrit",
        "size":      "~5MB",
        "languages": "Sanskrit parallel (FLORES-200)"
    },
    "flores_sat": {
        "repo_id":   "facebook/flores",
        "config":    "sat_Olck",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/santhali",
        "size":      "~5MB",
        "languages": "Santhali parallel (FLORES-200)"
    },
    "flores_snd": {
        "repo_id":   "facebook/flores",
        "config":    "snd_Arab",
        "type":      "huggingface",
        "local_dir": "./datasets/parallel/flores200/sindhi",
        "size":      "~5MB",
        "languages": "Sindhi parallel (FLORES-200)"
    },
}

# ============================================
# DOWNLOAD FUNCTIONS
# ============================================

def download_hf_dataset(name, config):
    local_dir = config["local_dir"]
    Path(local_dir).mkdir(parents=True, exist_ok=True)

    # Skip if already downloaded
    if os.path.exists(local_dir) and len(os.listdir(local_dir)) > 0:
        log.info(f"[OK] {name} already exists, skipping...")
        return True

    try:
        start = time.time()
        token = os.environ.get("HF_TOKEN")
        dataset_config = config.get("config", None)
        split = config.get("split", None)

        if split:
            # IndicCorpV2 style: languages are splits, save as DatasetDict
            from datasets import DatasetDict
            ds_split = load_dataset(config["repo_id"], dataset_config, split=split, token=token)
            ds = DatasetDict({"train": ds_split})
        elif dataset_config:
            ds = load_dataset(config["repo_id"], dataset_config, token=token)
        else:
            ds = load_dataset(config["repo_id"], token=token)

        ds.save_to_disk(local_dir)
        elapsed = time.time() - start
        log.info(f"[OK] {name} saved in {elapsed:.1f}s")
        return True

    except Exception as e:
        log.error(f"[FAIL] {name}: {e}")
        return False


def download_all_audio_datasets():
    log.info("\n" + "="*60)
    log.info("DOWNLOADING AUDIO DATASETS")
    log.info("="*60)

    results = {}
    for name, config in AUDIO_DATASETS.items():
        log.info(f"\nDownloading audio: {name}")
        log.info(f"Language: {config.get('languages','')}")
        log.info(f"Size: {config.get('size','')}")
        success = download_hf_dataset(name, config)
        results[name] = "[OK]" if success else "[FAIL]"

    return results


def download_all_text_datasets():
    log.info("\n" + "="*60)
    log.info("DOWNLOADING TEXT DATASETS")
    log.info("="*60)

    results = {}
    for name, config in TEXT_DATASETS.items():
        log.info(f"\nDownloading text: {name}")
        log.info(f"Language: {config.get('languages','')}")
        log.info(f"Size: {config.get('size','')}")
        success = download_hf_dataset(name, config)
        results[name] = "[OK]" if success else "[FAIL]"

    return results


def print_summary(audio_results, text_results):
    log.info("\n" + "="*60)
    log.info("DATASET DOWNLOAD SUMMARY")
    log.info("="*60)

    log.info("\nAUDIO DATASETS:")
    for name, status in audio_results.items():
        log.info(f"  {status} {name}")

    log.info("\nTEXT DATASETS:")
    for name, status in text_results.items():
        log.info(f"  {status} {name}")

    audio_ok = sum(1 for s in audio_results.values() if "[OK]" in s)
    text_ok  = sum(1 for s in text_results.values()  if "[OK]" in s)
    total    = len(audio_results) + len(text_results)
    total_ok = audio_ok + text_ok

    log.info(f"\nAudio: {audio_ok}/{len(audio_results)}")
    log.info(f"Text:  {text_ok}/{len(text_results)}")
    log.info(f"Total: {total_ok}/{total}")

    log.info("\nEstimated disk usage:")
    log.info("  Audio datasets: ~95GB  (added Shrutilipi, IndicTTS)")
    log.info("  Text datasets:  ~30GB  (parallel only: Samanantar, IN22, OPUS-100, FLORES-200)")
    log.info("  Total:          ~125GB")


if __name__ == "__main__":
    log.info("="*60)
    log.info("KB TRANSLATION SYSTEM - DATASET DOWNLOADER")
    log.info("="*60)
    log.info("Total audio datasets: " + str(len(AUDIO_DATASETS)))
    log.info("Total text datasets:  " + str(len(TEXT_DATASETS)))
    log.info("Estimated total size: ~125GB")
    log.info("="*60)

    audio_results = download_all_audio_datasets()
    text_results  = download_all_text_datasets()
    print_summary(audio_results, text_results)
