#!/usr/bin/env python3
"""
Download and verify models for KB Translation System.

Usage:
    python scripts/download_models.py              # Download missing models
    python scripts/download_models.py --verify     # Check existing models (no download)
    python scripts/download_models.py --force      # Re-download everything
    python scripts/download_models.py --list       # Just list expected models

Models are saved to the ./models/ directory relative to project root.
Total download size: ~25GB
"""
import os
import sys
import argparse
import json
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# ── Model definitions ────────────────────────────────────────────────────────
# Format: (repo_id, local_subdir, name, required_files)
# required_files: list of files that MUST exist for model to be valid
MODELS = [
    # Translation models
    (
        "ai4bharat/indictrans2-en-indic-1B",
        "indic_tr/en_indic",
        "IndicTrans2 En→Indic",
        ["config.json", "model.safetensors"],
    ),
    (
        "ai4bharat/indictrans2-indic-en-1B",
        "indic_tr/indic_en",
        "IndicTrans2 Indic→En",
        ["config.json", "model.safetensors"],
    ),
    (
        "ai4bharat/indictrans2-indic-indic-1B",
        "indic_tr/indic_indic",
        "IndicTrans2 Indic→Indic",
        ["config.json", "model.safetensors"],
    ),
    (
        "facebook/seamless-m4t-v2-large",
        "seamless",
        "SeamlessM4T v2 Large",
        ["config.json", "model.safetensors"],
    ),
    
    # TTS - Parler
    (
        "ai4bharat/indic-parler-tts-pretrained",
        "indic_parler_tts_large",
        "Indic Parler-TTS Large",
        ["config.json", "model.safetensors"],
    ),
    
    # TTS - MMS standalone VITS (main languages)
    ("facebook/mms-tts-hin", "mms_standalone/hin", "MMS-TTS Hindi", ["config.json"]),
    ("facebook/mms-tts-ben", "mms_standalone/ben", "MMS-TTS Bengali", ["config.json"]),
    ("facebook/mms-tts-tam", "mms_standalone/tam", "MMS-TTS Tamil", ["config.json"]),
    ("facebook/mms-tts-tel", "mms_standalone/tel", "MMS-TTS Telugu", ["config.json"]),
    ("facebook/mms-tts-kan", "mms_standalone/kan", "MMS-TTS Kannada", ["config.json"]),
    ("facebook/mms-tts-mal", "mms_standalone/mal", "MMS-TTS Malayalam", ["config.json"]),
    ("facebook/mms-tts-mar", "mms_standalone/mar", "MMS-TTS Marathi", ["config.json"]),
    ("facebook/mms-tts-guj", "mms_standalone/guj", "MMS-TTS Gujarati", ["config.json"]),
    ("facebook/mms-tts-pan", "mms_standalone/pan", "MMS-TTS Punjabi", ["config.json"]),
    ("facebook/mms-tts-ory", "mms_standalone/ory", "MMS-TTS Odia", ["config.json"]),
    ("facebook/mms-tts-asm", "mms_standalone/asm", "MMS-TTS Assamese", ["config.json"]),
    
    # TTS - MMS standalone VITS (gap languages)
    ("facebook/mms-tts-dgo", "mms_standalone/dgo", "MMS-TTS Dogri", ["config.json"]),
    ("facebook/mms-tts-bod", "mms_standalone/bod", "MMS-TTS Bodo/Tibetan", ["config.json"]),
    ("facebook/mms-tts-urd-script_arabic", "mms_standalone/urd", "MMS-TTS Urdu", ["config.json"]),
    ("facebook/mms-tts-kok", "mms_standalone/kok", "MMS-TTS Konkani", ["config.json"]),
    ("facebook/mms-tts-mni-mtei", "mms_standalone/mni", "MMS-TTS Manipuri", ["config.json"]),
    ("facebook/mms-tts-npi", "mms_standalone/nep", "MMS-TTS Nepali", ["config.json"]),
    ("facebook/mms-tts-mai", "mms_standalone/mai", "MMS-TTS Maithili", ["config.json"]),
    ("facebook/mms-tts-san", "mms_standalone/san", "MMS-TTS Sanskrit", ["config.json"]),
    ("facebook/mms-tts-sat", "mms_standalone/sat", "MMS-TTS Santhali", ["config.json"]),
    ("facebook/mms-tts-snd-script_devanagari", "mms_standalone/snd", "MMS-TTS Sindhi", ["config.json"]),
]


def get_dir_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def verify_model(local_dir: Path, required_files: list[str]) -> tuple[bool, list[str]]:
    """
    Verify a model directory has all required files.
    Returns (is_valid, missing_files).
    """
    if not local_dir.exists():
        return False, ["directory missing"]
    
    missing = []
    for fname in required_files:
        fpath = local_dir / fname
        # Also check for .bin variant if .safetensors missing
        if not fpath.exists():
            if fname.endswith(".safetensors"):
                bin_variant = fname.replace(".safetensors", ".bin")
                if not (local_dir / bin_variant).exists():
                    # Check for pytorch_model.bin as another variant
                    if not (local_dir / "pytorch_model.bin").exists():
                        missing.append(fname)
            else:
                missing.append(fname)
    
    return len(missing) == 0, missing


def verify_all_models() -> dict:
    """Verify all models and return status dict."""
    results = {
        "valid": [],
        "invalid": [],
        "missing": [],
        "total_size": 0,
    }
    
    print(f"\n{'═'*65}")
    print("MODEL VERIFICATION")
    print(f"{'═'*65}")
    print(f"Models directory: {MODELS_DIR}\n")
    
    for repo_id, local_subdir, name, required_files in MODELS:
        local_dir = MODELS_DIR / local_subdir
        is_valid, missing = verify_model(local_dir, required_files)
        size = get_dir_size(local_dir)
        
        if not local_dir.exists():
            status = "❌ MISSING"
            results["missing"].append((name, local_subdir))
        elif is_valid:
            status = f"✅ OK ({format_size(size)})"
            results["valid"].append((name, local_subdir, size))
            results["total_size"] += size
        else:
            status = f"⚠️  INCOMPLETE (missing: {', '.join(missing)})"
            results["invalid"].append((name, local_subdir, missing))
        
        print(f"{name:.<45} {status}")
    
    print(f"\n{'─'*65}")
    print(f"Total: {len(results['valid'])} valid, {len(results['invalid'])} incomplete, {len(results['missing'])} missing")
    print(f"Total size: {format_size(results['total_size'])}")
    
    return results


def list_models():
    """Just list expected models without checking."""
    print(f"\n{'═'*65}")
    print("EXPECTED MODELS")
    print(f"{'═'*65}")
    print(f"Models directory: {MODELS_DIR}\n")
    
    print("Translation Models:")
    for repo_id, local_subdir, name, _ in MODELS[:4]:
        print(f"  • {name}")
        print(f"    Path: models/{local_subdir}")
        print(f"    Repo: {repo_id}")
    
    print("\nTTS Models:")
    for repo_id, local_subdir, name, _ in MODELS[4:]:
        print(f"  • {name}")
        print(f"    Path: models/{local_subdir}")
    
    print(f"\nTotal: {len(MODELS)} models")


def download_models(force: bool = False):
    """Download models (main function)."""
    # Load .env if present
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass
    
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
    
    print(f"Models will be saved to: {MODELS_DIR}")
    if force:
        print("⚠️  Force mode: re-downloading ALL models\n")
    else:
        print("Skipping existing valid models. Use --force to re-download.\n")
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    failed = []
    skipped = 0
    downloaded = 0
    
    for repo_id, local_subdir, name, required_files in MODELS:
        local_dir = MODELS_DIR / local_subdir
        print(f"{'─'*60}")
        print(f"📦 {name}")
        print(f"   Repo:  {repo_id}")
        print(f"   Path:  {local_dir}")
        
        # Check if already valid (unless force)
        if not force:
            is_valid, missing = verify_model(local_dir, required_files)
            if is_valid:
                size = get_dir_size(local_dir)
                print(f"   ⏭️  Already exists ({format_size(size)}), skipping")
                skipped += 1
                continue
            elif local_dir.exists() and missing:
                print(f"   ⚠️  Incomplete (missing: {', '.join(missing)}), re-downloading...")
        
        try:
            # Remove incomplete directory if exists
            if local_dir.exists():
                import shutil
                shutil.rmtree(local_dir)
            
            snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
                local_dir_use_symlinks=False,
            )
            size = get_dir_size(local_dir)
            print(f"   ✅ Done ({format_size(size)})")
            downloaded += 1
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            failed.append((name, str(e)))
    
    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print("DOWNLOAD COMPLETE")
    print(f"{'═'*60}")
    print(f"Downloaded: {downloaded}, Skipped: {skipped}, Failed: {len(failed)}")
    print(f"Models directory: {MODELS_DIR}")
    print("")
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
        print("✅ All models ready!")
    
    print("\nNext steps:")
    print("  1. Run the UI:  python ui/app.py")
    print("  2. Or use CLI:  python scripts/dub.py --help")


def main():
    parser = argparse.ArgumentParser(
        description="Download and verify KB Translation System models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_models.py              # Download missing models
  python scripts/download_models.py --verify     # Check existing models
  python scripts/download_models.py --force      # Re-download everything
  python scripts/download_models.py --list       # List expected models
        """
    )
    parser.add_argument(
        "--verify", "-v",
        action="store_true",
        help="Only verify existing models (no download)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-download of all models"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List expected models and paths"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_models()
    elif args.verify:
        results = verify_all_models()
        
        # Exit with error code if models are missing/invalid
        if results["missing"] or results["invalid"]:
            print("\n💡 Run without --verify to download missing/incomplete models:")
            print("   python scripts/download_models.py")
            sys.exit(1)
        else:
            print("\n✅ All models verified successfully!")
    else:
        download_models(force=args.force)


if __name__ == "__main__":
    main()
