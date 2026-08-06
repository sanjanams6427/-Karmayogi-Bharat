import os
os.environ["HF_HOME"] = "E:\\Manick_AI_ML\\models"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_TOKEN"] = "<your_new_hf_token_here>"

from huggingface_hub import snapshot_download, login
login(token=os.environ["HF_TOKEN"], add_to_git_credential=False)
print("HuggingFace login successful")

models = [
    ("ai4bharat/indictrans2-en-indic-1B",        "IndicTrans2 En->Indic"),
    ("ai4bharat/indictrans2-indic-en-1B",        "IndicTrans2 Indic->En"),
    ("ai4bharat/indictrans2-indic-indic-1B",     "IndicTrans2 Indic->Indic"),
    ("facebook/seamless-m4t-v2-large",           "SeamlessM4T v2 Large"),
    # Large Parler-TTS — kept separate for comparison before replacing mini
    ("ai4bharat/indic-parler-tts-pretrained",    "Indic Parler-TTS LARGE"),
]

# Mini stays at:  models/indic_parler_tts/          (current, used by pipeline)
# Large saved to: models/indic_parler_tts_large/    (new, for comparison)
PARLER_LARGE_DIR = "E:\\Manick_AI_ML\\project\\models\\indic_parler_tts_large"

for repo_id, name in models:
    print(f"\n{'='*50}")
    print(f"Downloading: {name}")
    print(f"Repo: {repo_id}")
    print(f"{'='*50}")
    local_dir = (
        PARLER_LARGE_DIR
        if repo_id == "ai4bharat/indic-parler-tts-pretrained"
        else f"E:\\Manick_AI_ML\\models\\{repo_id.replace('/', '--')}"
    )
    try:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
        )
        print(f"DONE: {name} -> {path}")
    except Exception as e:
        print(f"FAILED: {name} -> {e}")

print("\nAll downloads complete!")
print(f"\nParler-TTS MINI : models/indic_parler_tts/        (pipeline currently uses this)")
print(f"Parler-TTS LARGE: models/indic_parler_tts_large/  (compare, then swap when ready)")
print("\nTo switch to LARGE after comparison:")
print("  rename models/indic_parler_tts       -> models/indic_parler_tts_mini_backup")
print("  rename models/indic_parler_tts_large -> models/indic_parler_tts")
