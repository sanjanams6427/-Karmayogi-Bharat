import os, sys
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

from huggingface_hub import snapshot_download

BASE = r"E:\Manick_AI_ML\project\models\mms_standalone"
MODELS = [
    ("facebook/mms-tts-kas", "kas"),
    ("facebook/mms-tts-snd", "snd"),
    ("facebook/mms-tts-kok", "kok"),
    ("facebook/mms-tts-mni", "mni"),
]

for repo_id, folder in MODELS:
    dst = os.path.join(BASE, folder)
    if os.path.exists(os.path.join(dst, "model.safetensors")) or \
       os.path.exists(os.path.join(dst, "pytorch_model.bin")):
        print(f"SKIP (already exists): {folder}")
        sys.stdout.flush()
        continue
    print(f"Downloading {repo_id} -> {dst}")
    sys.stdout.flush()
    try:
        snapshot_download(repo_id=repo_id, local_dir=dst, local_dir_use_symlinks=False)
        print(f"  OK: {folder}")
    except Exception as e:
        print(f"  FAILED: {repo_id}: {e}")
    sys.stdout.flush()

print("Done.")
