"""
Download standalone VITS models for mni, kok, kas into models/mms_standalone/.
mni -> facebook/mms-tts-ben  (Bengali script = Manipuri script)
kok -> facebook/mms-tts-mar  (Devanagari = Konkani script)
kas -> facebook/mms-tts-urd-script_arabic  (Nastaliq = Kashmiri script)
"""
import os, sys
from pathlib import Path
from huggingface_hub import hf_hub_download

BASE = Path(__file__).parent.parent / "models" / "mms_standalone"
FILES = ["config.json", "model.safetensors", "pytorch_model.bin",
         "vocab.json", "tokenizer_config.json", "special_tokens_map.json", "README.md"]

TARGETS = [
    ("mni", "facebook/mms-tts-ben"),
    ("kok", "facebook/mms-tts-mar"),
    ("kas", "facebook/mms-tts-urd-script_arabic"),
]

for lang, repo in TARGETS:
    dest = BASE / lang
    dest.mkdir(parents=True, exist_ok=True)
    print(f"\n--- {lang} <- {repo} ---", flush=True)
    for fname in FILES:
        try:
            p = hf_hub_download(repo, filename=fname, local_dir=str(dest))
            print(f"  OK  {fname}", flush=True)
        except Exception as e:
            msg = str(e)
            if "404" in msg or "not found" in msg.lower() or "does not exist" in msg.lower():
                print(f"  --  {fname} (not in repo)", flush=True)
            else:
                print(f"  ERR {fname}: {msg[:100]}", flush=True)
    # verify model file present
    sf = dest / "model.safetensors"
    pt = dest / "pytorch_model.bin"
    if sf.exists():
        print(f"  => model.safetensors {sf.stat().st_size//1024//1024}MB", flush=True)
    elif pt.exists():
        print(f"  => pytorch_model.bin {pt.stat().st_size//1024//1024}MB", flush=True)
    else:
        print(f"  => WARNING: no model weights found!", flush=True)

print("\nDone.", flush=True)
