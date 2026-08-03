import os
os.environ["HF_HOME"] = "E:\\Manick_AI_ML\\models"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_TOKEN"] = "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"

from huggingface_hub import snapshot_download, login
login(token=os.environ["HF_TOKEN"], add_to_git_credential=False)
print("HuggingFace login successful")

models = [
    ("ai4bharat/indictrans2-en-indic-1B",   "IndicTrans2 En->Indic"),
    ("ai4bharat/indictrans2-indic-en-1B",   "IndicTrans2 Indic->En"),
    ("ai4bharat/indictrans2-indic-indic-1B","IndicTrans2 Indic->Indic"),
    ("facebook/seamless-m4t-v2-large",      "SeamlessM4T v2 Large"),
]

for repo_id, name in models:
    print(f"\n{'='*50}")
    print(f"Downloading: {name}")
    print(f"Repo: {repo_id}")
    print(f"{'='*50}")
    try:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=f"E:\\Manick_AI_ML\\models\\{repo_id.replace('/', '--')}",
            local_dir_use_symlinks=False,
        )
        print(f"DONE: {name} -> {path}")
    except Exception as e:
        print(f"FAILED: {name} -> {e}")

print("\nAll downloads complete!")
