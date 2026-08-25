#!/usr/bin/env python3
"""
Download all required models for KB Translation System.

Usage:
    1. Set HF_TOKEN in your .env file or environment
    2. Run: python scripts/download_models.py

Models are saved to the ./models/ directory relative to project root.
Total download size: ~25GB
"""
import os
import sys
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# Load .env if present
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# Disable symlinks warning on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Check for HF token
HF_TOKEN = os.environ.get("HF_TOKEN", "")
if not HF_TOKEN:
    print("ERROR: HF_TOKEN not set.")
    print("Please set it in your .env file or environment:")
    print("  export HF_TOKEN=hf_xxx  # Linux/Mac")
    print("  set HF_TOKEN=hf_xxx     # Windows CMD")
    print("  $env:HF_TOKEN='hf_xxx'  # Windows PowerShell")
    sys.exit(1)

from huggingface_hub import snapshot_download, login

# Login to HuggingFace
try:
    login(token=HF_TOKEN, add_to_git_credential=False)
    print("✓ HuggingFace login successful\n")
except Exception as e:
    print(f"✗ HuggingFace login failed: {e}")
    sys.exit(1)

# ── Model definitions ────────────────────────────────────────────────────────
MODELS = [
    # Translation models
    ("ai4bharat/indictrans2-en-indic-1B",        "indic_tr/en_indic",       "IndicTrans2 En→Indic"),
    ("ai4bharat/indictrans2-indic-en-1B",        "indic_tr/indic_en",       "IndicTrans2 Indic→En"),
    ("ai4bharat/indictrans2-indic-indic-1B",     "indic_tr/indic_indic",    "IndicTrans2 Indic→Indic"),
    ("facebook/seamless-m4t-v2-large",           "seamless",                "SeamlessM4T v2 Large"),
    
    # TTS - Parler
    ("ai4bharat/indic-parler-tts-pretrained",    "indic_parler_tts_large",  "Indic Parler-TTS Large"),
    
    # TTS - MMS standalone VITS (main languages)
    ("facebook/mms-tts-hin",                     "mms_standalone/hin",      "MMS-TTS Hindi"),
    ("facebook/mms-tts-ben",                     "mms_standalone/ben",      "MMS-TTS Bengali"),
    ("facebook/mms-tts-tam",                     "mms_standalone/tam",      "MMS-TTS Tamil"),
    ("facebook/mms-tts-tel",                     "mms_standalone/tel",      "MMS-TTS Telugu"),
    ("facebook/mms-tts-kan",                     "mms_standalone/kan",      "MMS-TTS Kannada"),
    ("facebook/mms-tts-mal",                     "mms_standalone/mal",      "MMS-TTS Malayalam"),
    ("facebook/mms-tts-mar",                     "mms_standalone/mar",      "MMS-TTS Marathi"),
    ("facebook/mms-tts-guj",                     "mms_standalone/guj",      "MMS-TTS Gujarati"),
    ("facebook/mms-tts-pan",                     "mms_standalone/pan",      "MMS-TTS Punjabi"),
    ("facebook/mms-tts-ory",                     "mms_standalone/ory",      "MMS-TTS Odia"),
    ("facebook/mms-tts-asm",                     "mms_standalone/asm",      "MMS-TTS Assamese"),
    
    # TTS - MMS standalone VITS (gap languages)
    ("facebook/mms-tts-dgo",                     "mms_standalone/dgo",      "MMS-TTS Dogri"),
    ("facebook/mms-tts-bod",                     "mms_standalone/bod",      "MMS-TTS Bodo/Tibetan"),
    ("facebook/mms-tts-urd-script_arabic",       "mms_standalone/urd",      "MMS-TTS Urdu"),
    ("facebook/mms-tts-kok",                     "mms_standalone/kok",      "MMS-TTS Konkani"),
    ("facebook/mms-tts-mni-mtei",                "mms_standalone/mni",      "MMS-TTS Manipuri"),
    ("facebook/mms-tts-npi",                     "mms_standalone/nep",      "MMS-TTS Nepali"),
    ("facebook/mms-tts-mai",                     "mms_standalone/mai",      "MMS-TTS Maithili"),
    ("facebook/mms-tts-san",                     "mms_standalone/san",      "MMS-TTS Sanskrit"),
    ("facebook/mms-tts-sat",                     "mms_standalone/sat",      "MMS-TTS Santhali"),
    ("facebook/mms-tts-snd-script_devanagari",   "mms_standalone/snd",      "MMS-TTS Sindhi"),
]

# ── Download ─────────────────────────────────────────────────────────────────
print(f"Models will be saved to: {MODELS_DIR}\n")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

failed = []
for repo_id, local_subdir, name in MODELS:
    local_dir = MODELS_DIR / local_subdir
    print(f"{'─'*60}")
    print(f"📦 {name}")
    print(f"   Repo:  {repo_id}")
    print(f"   Path:  {local_dir}")
    
    if local_dir.exists() and any(local_dir.iterdir()):
        print(f"   ⏭️  Already exists, skipping")
        continue
    
    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
        )
        print(f"   ✅ Done")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        failed.append((name, str(e)))

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'═'*60}")
print("DOWNLOAD COMPLETE")
print(f"{'═'*60}")
print(f"Models directory: {MODELS_DIR}")
print(f"")
print("Directory structure:")
print("  models/")
print("  ├── indic_tr/               # IndicTrans2 translation models")
print("  │   ├── en_indic/")
print("  │   ├── indic_en/")
print("  │   └── indic_indic/")
print("  ├── seamless/               # SeamlessM4T (S2ST + fallback)")
print("  ├── indic_parler_tts_large/ # Primary TTS")
print("  └── mms_standalone/         # MMS-TTS fallback (22 languages)")
print("      ├── hin/  ben/  tam/  tel/  kan/  mal/")
print("      ├── mar/  guj/  pan/  ory/  asm/")
print("      └── dgo/  bod/  urd/  kok/  mni/  ...")
print("")

if failed:
    print(f"⚠️  {len(failed)} downloads failed:")
    for name, err in failed:
        print(f"   - {name}: {err}")
    print("\nRe-run this script to retry failed downloads.")
else:
    print("✅ All models downloaded successfully!")

print("\nNext steps:")
print("  1. Run the UI:  python ui/app.py")
print("  2. Or use CLI:  python scripts/dub.py --help")
