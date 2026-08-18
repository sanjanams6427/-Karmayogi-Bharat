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
    # ── MMS-TTS standalone VITS — 11 mandatory languages ──────────────────────
    ("facebook/mms-tts-tam",                     "MMS-TTS Tamil"),
    ("facebook/mms-tts-tel",                     "MMS-TTS Telugu"),
    ("facebook/mms-tts-hin",                     "MMS-TTS Hindi"),
    ("facebook/mms-tts-kan",                     "MMS-TTS Kannada"),
    ("facebook/mms-tts-mal",                     "MMS-TTS Malayalam"),
    ("facebook/mms-tts-ben",                     "MMS-TTS Bengali"),
    ("facebook/mms-tts-mar",                     "MMS-TTS Marathi"),
    ("facebook/mms-tts-guj",                     "MMS-TTS Gujarati"),
    ("facebook/mms-tts-pan",                     "MMS-TTS Punjabi"),
    ("facebook/mms-tts-ory",                     "MMS-TTS Odia"),
    ("facebook/mms-tts-asm",                     "MMS-TTS Assamese"),
    # ── gap languages ──────────────────────────────────────────────────────
    ("facebook/mms-tts-dgo",                     "MMS-TTS Dogri standalone VITS"),
    ("facebook/mms-tts-bod",                     "MMS-TTS Bodo standalone VITS"),
    ("facebook/mms-tts-urd-script_arabic",       "MMS-TTS Kashmiri (urd-arabic proxy)"),
    ("facebook/mms-tts-kok",                     "MMS-TTS Konkani"),
    ("facebook/mms-tts-mni-mtei",                "MMS-TTS Manipuri"),
    # ── remaining 6 standalone VITS (urd/nep/mai/san/sat/snd) ─────────────────
    ("facebook/mms-tts-urd-script_arabic",       "MMS-TTS Urdu"),
    ("facebook/mms-tts-npi",                     "MMS-TTS Nepali"),
    ("facebook/mms-tts-mai",                     "MMS-TTS Maithili"),
    ("facebook/mms-tts-san",                     "MMS-TTS Sanskrit"),
    ("facebook/mms-tts-sat",                     "MMS-TTS Santhali"),
    ("facebook/mms-tts-snd-script_devanagari",   "MMS-TTS Sindhi"),
]

# Mini stays at:  models/indic_parler_tts/          (current, used by pipeline)
# Large saved to: models/indic_parler_tts_large/    (new, for comparison)
PARLER_LARGE_DIR  = "E:\\Manick_AI_ML\\project\\models\\indic_parler_tts_large"
MMS_STANDALONE_DIR = "E:\\Manick_AI_ML\\project\\models\\mms_standalone"

# repo_id -> local path overrides (anything not listed uses default HF cache path)
_PATH_OVERRIDES = {
    "ai4bharat/indic-parler-tts-pretrained": PARLER_LARGE_DIR,
    "facebook/mms-tts-tam":              f"{MMS_STANDALONE_DIR}\\tam",
    "facebook/mms-tts-tel":              f"{MMS_STANDALONE_DIR}\\tel",
    "facebook/mms-tts-hin":              f"{MMS_STANDALONE_DIR}\\hin",
    "facebook/mms-tts-kan":              f"{MMS_STANDALONE_DIR}\\kan",
    "facebook/mms-tts-mal":              f"{MMS_STANDALONE_DIR}\\mal",
    "facebook/mms-tts-ben":              f"{MMS_STANDALONE_DIR}\\ben",
    "facebook/mms-tts-mar":              f"{MMS_STANDALONE_DIR}\\mar",
    "facebook/mms-tts-guj":              f"{MMS_STANDALONE_DIR}\\guj",
    "facebook/mms-tts-pan":              f"{MMS_STANDALONE_DIR}\\pan",
    "facebook/mms-tts-ory":              f"{MMS_STANDALONE_DIR}\\ory",
    "facebook/mms-tts-asm":              f"{MMS_STANDALONE_DIR}\\asm",
    "facebook/mms-tts-dgo":              f"{MMS_STANDALONE_DIR}\\dgo",
    "facebook/mms-tts-bod":              f"{MMS_STANDALONE_DIR}\\bod",
    "facebook/mms-tts-urd-script_arabic": f"{MMS_STANDALONE_DIR}\\kas",
    "facebook/mms-tts-kok":              f"{MMS_STANDALONE_DIR}\\kok",
    "facebook/mms-tts-mni-mtei":         f"{MMS_STANDALONE_DIR}\\mni",
    "facebook/mms-tts-urd-script_arabic": f"{MMS_STANDALONE_DIR}\\urd",
    "facebook/mms-tts-npi":              f"{MMS_STANDALONE_DIR}\\nep",
    "facebook/mms-tts-mai":              f"{MMS_STANDALONE_DIR}\\mai",
    "facebook/mms-tts-san":              f"{MMS_STANDALONE_DIR}\\san",
    "facebook/mms-tts-sat":              f"{MMS_STANDALONE_DIR}\\sat",
    "facebook/mms-tts-snd-script_devanagari": f"{MMS_STANDALONE_DIR}\\snd",
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
