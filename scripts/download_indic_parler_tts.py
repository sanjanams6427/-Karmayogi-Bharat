"""
Download ai4bharat/indic-parler-tts — the proper large model trained on all 22 Indian languages.
This replaces the mini checkpoint which has poor Tamil/some language coverage.
"""
import os, sys
sys.path.insert(0, r'e:\Manick_AI_ML\project')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from pathlib import Path
from huggingface_hub import snapshot_download

DEST = Path(r'e:\Manick_AI_ML\project\models\indic_parler_tts')
DEST.mkdir(parents=True, exist_ok=True)

print("Downloading ai4bharat/indic-parler-tts (large, ~3GB)...")
print("This is the proper model with human-quality voice for all 22 Indian languages.")
print()

try:
    snapshot_download(
        repo_id="ai4bharat/indic-parler-tts",
        local_dir=str(DEST),
        local_dir_use_symlinks=False,
        ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
    )
    print(f"\nDone. Model saved to: {DEST}")
except Exception as e:
    print(f"Download failed: {e}")
    print()
    print("If you have HF_TOKEN set in .env, make sure it's loaded:")
    print("  set HF_TOKEN=hf_your_token_here")
    print("  python scripts/download_models.py")
