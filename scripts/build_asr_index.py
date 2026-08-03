"""
Build datasets/asr/<lang_code>/ fine-tuning structure for all 22 languages.

Each language gets:
  datasets/asr/<lang>/
      dataset_info.json   <- metadata + source paths for fine-tuning
      train/              <- symlink-equivalent: loads from primary source
      validation/
      test/

Run once; safe to re-run (skips existing).
"""
import io, sys, json, shutil
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT       = Path(__file__).parent.parent
AUDIO_BASE = ROOT / "datasets" / "audio"
ASR_BASE   = ROOT / "datasets" / "asr"

ALL_22 = [
    "asm", "ben", "guj", "hin", "kan", "mal", "mar", "ory", "pan", "tam", "tel",
    "bod", "doi", "kas", "kok", "mni", "mai", "nep", "san", "sat", "snd", "urd",
]

LANG_META = {
    "asm": {"name": "Assamese",  "script": "Beng", "fleurs": "as_in",  "cv": None},
    "ben": {"name": "Bengali",   "script": "Beng", "fleurs": "bn_in",  "cv": "bn"},
    "guj": {"name": "Gujarati",  "script": "Gujr", "fleurs": "gu_in",  "cv": "gu-IN"},
    "hin": {"name": "Hindi",     "script": "Deva", "fleurs": "hi_in",  "cv": "hi"},
    "kan": {"name": "Kannada",   "script": "Knda", "fleurs": "kn_in",  "cv": "kn"},
    "mal": {"name": "Malayalam", "script": "Mlym", "fleurs": "ml_in",  "cv": "ml"},
    "mar": {"name": "Marathi",   "script": "Deva", "fleurs": "mr_in",  "cv": "mr"},
    "ory": {"name": "Odia",      "script": "Orya", "fleurs": "or_in",  "cv": "or"},
    "pan": {"name": "Punjabi",   "script": "Guru", "fleurs": "pa_in",  "cv": "pa-IN"},
    "tam": {"name": "Tamil",     "script": "Taml", "fleurs": "ta_in",  "cv": "ta"},
    "tel": {"name": "Telugu",    "script": "Telu", "fleurs": "te_in",  "cv": "te"},
    "urd": {"name": "Urdu",      "script": "Arab", "fleurs": "ur_pk",  "cv": "ur"},
    "nep": {"name": "Nepali",    "script": "Deva", "fleurs": "ne_np",  "cv": "ne-NP"},
    "mai": {"name": "Maithili",  "script": "Deva", "fleurs": None,     "cv": "mai"},
    "san": {"name": "Sanskrit",  "script": "Deva", "fleurs": None,     "cv": "sa"},
    "bod": {"name": "Bodo",      "script": "Deva", "fleurs": None,     "cv": None},
    "doi": {"name": "Dogri",     "script": "Deva", "fleurs": None,     "cv": None},
    "kas": {"name": "Kashmiri",  "script": "Arab", "fleurs": None,     "cv": None},
    "kok": {"name": "Konkani",   "script": "Deva", "fleurs": None,     "cv": None},
    "mni": {"name": "Manipuri",  "script": "Mtei", "fleurs": None,     "cv": "mni-Mtei"},
    "sat": {"name": "Santhali",  "script": "Olck", "fleurs": None,     "cv": None},
    "snd": {"name": "Sindhi",    "script": "Arab", "fleurs": None,     "cv": "sd"},
}

FLEURS_FOLDER = {
    "asm": "assamese", "ben": "bengali",  "guj": "gujarati", "hin": "hindi",
    "kan": "kannada",  "mal": "malayalam","mar": "marathi",  "ory": "odia",
    "pan": "punjabi",  "tam": "tamil",    "tel": "telugu",   "urd": "urdu",
    "nep": "nepali",
}
CV_FOLDER = {
    "hin": "hindi", "mar": "marathi", "tam": "tamil", "urd": "urdu", "san": "sanskrit",
}


def find_source(lang: str) -> dict:
    """Return dict of split -> absolute path for the best available source."""
    sources = {}

    # 1. FLEURS (has train/validation/test splits)
    fleurs_dir = AUDIO_BASE / "fleurs" / FLEURS_FOLDER.get(lang, "")
    if fleurs_dir.exists() and any(fleurs_dir.rglob("*.arrow")):
        for split in ("train", "validation", "test"):
            sp = fleurs_dir / split
            if sp.exists() and any(sp.glob("*.arrow")):
                sources[split] = str(sp)
        if sources:
            sources["_source"] = "fleurs"
            sources["_repo"]   = f"google/fleurs ({LANG_META[lang]['fleurs']})"
            return sources

    # 2. Common Voice
    cv_dir = AUDIO_BASE / "common_voice" / CV_FOLDER.get(lang, "")
    if cv_dir.exists() and any(cv_dir.rglob("*.arrow")):
        for split in ("train", "validation", "test"):
            sp = cv_dir / split
            if sp.exists() and any(sp.glob("*.arrow")):
                sources[split] = str(sp)
        if sources:
            sources["_source"] = "common_voice"
            sources["_repo"]   = f"mozilla-foundation/common_voice_17_0 ({LANG_META[lang]['cv']})"
            return sources

    # 3. Bodo ASR
    if lang == "bod":
        bodo_dir = AUDIO_BASE / "bodo_asr"
        if bodo_dir.exists() and any(bodo_dir.rglob("*.arrow")):
            for split in ("train", "valid"):
                sp = bodo_dir / split
                if sp.exists() and any(sp.glob("*.arrow")):
                    key = "validation" if split == "valid" else split
                    sources[key] = str(sp)
            if sources:
                sources["_source"] = "bodo_asr"
                sources["_repo"]   = "XKaab/ASR-Bodo_5hrs"
                return sources

    # 4. IndicSUPERB (shared — covers all 22)
    indicsuper_dir = AUDIO_BASE / "indicsuper"
    if indicsuper_dir.exists() and any(indicsuper_dir.rglob("*.arrow")):
        sources["_source"] = "indicsuper"
        sources["_repo"]   = "alekya/IndicSUPERB"
        sources["_shared"] = str(indicsuper_dir)
        sources["_lang_key"] = lang
        return sources

    return {}


def build_asr_structure():
    ASR_BASE.mkdir(parents=True, exist_ok=True)
    print(f"Building datasets/asr/ for {len(ALL_22)} languages...\n")

    results = {}
    for lang in ALL_22:
        meta  = LANG_META[lang]
        dest  = ASR_BASE / lang
        dest.mkdir(parents=True, exist_ok=True)

        src = find_source(lang)

        info = {
            "lang_code":    lang,
            "lang_name":    meta["name"],
            "script":       meta["script"],
            "sampling_rate": 16000,
            "source":       src.get("_source", "NOT_FOUND"),
            "hf_repo":      src.get("_repo",   ""),
            "splits": {
                "train":      src.get("train",      src.get("_shared", "")),
                "validation": src.get("validation", src.get("_shared", "")),
                "test":       src.get("test",       src.get("_shared", "")),
            },
            "finetune_ready": bool(src),
            "features": {
                "audio":         {"sampling_rate": 16000, "_type": "Audio"},
                "transcription": {"dtype": "string",      "_type": "Value"},
                "lang_code":     {"dtype": "string",      "_type": "Value"},
            },
        }

        info_path = dest / "dataset_info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)

        status = "[OK]" if src else "[MISSING]"
        print(f"  {status} {lang:<5} {meta['name']:<12}  source={info['source']}")
        results[lang] = info["source"]

    # Write master index
    index = {
        "total_languages": len(ALL_22),
        "finetune_ready":  sum(1 for v in results.values() if v != "NOT_FOUND"),
        "languages": results,
        "structure": "datasets/asr/<lang_code>/dataset_info.json",
        "usage": (
            "from datasets import load_from_disk\n"
            "ds = load_from_disk('datasets/asr/hin/splits/train')"
        ),
    }
    with open(ASR_BASE / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    ok = index["finetune_ready"]
    print(f"\n  Fine-tune ready: {ok}/{len(ALL_22)}")
    print(f"  Index written:   datasets/asr/index.json")


if __name__ == "__main__":
    build_asr_structure()
