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
    # Standalone VITS models for gap languages (no shared-adapter coverage)
    ("facebook/mms-tts-dgo",                     "MMS-TTS Dogri standalone VITS"),
    ("facebook/mms-tts-bod",                     "MMS-TTS Bodo standalone VITS"),
    # Note: facebook/mms-tts-san does NOT exist on HuggingFace
    # Weak language standalone VITS — best available script match
    # kas: no facebook/mms-tts-kas — use urd-script_arabic (Nastaliq, same script)
    ("facebook/mms-tts-urd-script_arabic",       "MMS-TTS Kashmiri (urd-arabic proxy)"),
    # kok: no facebook/mms-tts-kok — use mar (Devanagari, same script)
    ("facebook/mms-tts-mar",                     "MMS-TTS Konkani (mar proxy)"),
    # mni: no facebook/mms-tts-mni — use ben (Bengali script, same as Manipuri)
    ("facebook/mms-tts-ben",                     "MMS-TTS Manipuri (ben proxy)"),
]

# Mini stays at:  models/indic_parler_tts/          (current, used by pipeline)
# Large saved to: models/indic_parler_tts_large/    (new, for comparison)
PARLER_LARGE_DIR  = "E:\\Manick_AI_ML\\project\\models\\indic_parler_tts_large"
MMS_STANDALONE_DIR = "E:\\Manick_AI_ML\\project\\models\\mms_standalone"

# repo_id -> local path overrides (anything not listed uses default HF cache path)
_PATH_OVERRIDES = {
    "ai4bharat/indic-parler-tts-pretrained": PARLER_LARGE_DIR,
    "facebook/mms-tts-dgo": f"{MMS_STANDALONE_DIR}\\dgo",
    "facebook/mms-tts-bod": f"{MMS_STANDALONE_DIR}\\bod",
    "facebook/mms-tts-urd-script_arabic": f"{MMS_STANDALONE_DIR}\\kas",
    "facebook/mms-tts-mar": f"{MMS_STANDALONE_DIR}\\kok",
    "facebook/mms-tts-ben": f"{MMS_STANDALONE_DIR}\\mni",
}

for repo_id, name in models:
    print(f"\n{'='*50}")
    print(f"Downloading: {name}")
    print(f"Repo: {repo_id}")
    print(f"{'='*50}")
    local_dir = _PATH_OVERRIDES.get(
        repo_id,
        f"E:\\Manick_AI_ML\\models\\{repo_id.replace('/', '--')}"
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
print(f"MMS Dogri       : models/mms_standalone/dgo/      (standalone VITS for Dogri TTS)")
print(f"MMS Bodo        : models/mms_standalone/bod/      (standalone VITS for Bodo TTS)")
print(f"MMS Kashmiri    : models/mms_standalone/kas/      (urd-arabic proxy — Nastaliq script)")
print(f"MMS Konkani     : models/mms_standalone/kok/      (mar proxy — Devanagari script)")
print(f"MMS Manipuri    : models/mms_standalone/mni/      (ben proxy — Bengali script)")
print("\nTo switch to LARGE after comparison:")
print("  rename models/indic_parler_tts       -> models/indic_parler_tts_mini_backup")
print("  rename models/indic_parler_tts_large -> models/indic_parler_tts")
