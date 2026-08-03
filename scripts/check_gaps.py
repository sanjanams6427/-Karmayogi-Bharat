import json, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ALL_22 = [
    "asm","ben","guj","hin","kan","mal","mar","ory","pan","tam","tel",
    "bod","doi","kas","kok","mni","mai","nep","san","sat","snd","urd",
]

LANG_NAMES = {
    "asm":"Assamese","ben":"Bengali","guj":"Gujarati","hin":"Hindi",
    "kan":"Kannada","mal":"Malayalam","mar":"Marathi","ory":"Odia",
    "pan":"Punjabi","tam":"Tamil","tel":"Telugu","bod":"Bodo",
    "doi":"Dogri","kas":"Kashmiri","kok":"Konkani","mni":"Manipuri",
    "mai":"Maithili","nep":"Nepali","san":"Sanskrit","sat":"Santhali",
    "snd":"Sindhi","urd":"Urdu",
}

PARALLEL_DIR = Path("datasets/parallel")
AUDIO_DIR    = Path("datasets/audio")

def count_lines(p):
    try:
        return sum(1 for _ in open(p, encoding="utf-8"))
    except:
        return 0

# Map lang code -> folder name used on disk per source
FLEURS_DIRS = {
    "asm":"assamese","ben":"bengali","guj":"gujarati","hin":"hindi",
    "kan":"kannada","mal":"malayalam","mar":"marathi","ory":"odia",
    "pan":"punjabi","tam":"tamil","tel":"telugu","urd":"urdu",
    "nep":"nepali","mai":"maithili",
}
CV_DIRS = {
    "hin":"hindi","mar":"marathi","tam":"tamil","urd":"urdu","san":"sanskrit",
}
# IndicSUPERB and Shrutilipi are shared datasets (not per-lang folders)
# Kathbath covers all 22 when downloaded
SHARED_SOURCES = {
    "indicsuper": AUDIO_DIR / "indicsuper",
    "shrutilipi": AUDIO_DIR / "shrutilipi",
    "indic_tts":  AUDIO_DIR / "indic_tts",
}
# Which shared source covers which gap languages
SHARED_COVERAGE = {
    "indicsuper": set(ALL_22),
    "shrutilipi": {"doi","kas","kok","mni","sat","snd","asm","ben","guj",
                   "hin","kan","mal","mar","ory","pan","tam","tel"},
    "indic_tts":  {"asm","ben","guj","hin","kan","mal","mar","ory","pan","tam","tel"},
}

def is_arrow_dataset(path):
    """True if path contains a valid HuggingFace Arrow dataset."""
    if not path.exists():
        return False
    # DatasetDict or split subfolders: search recursively
    return any(path.rglob("*.arrow"))

def check_audio_dir(lang):
    found = []

    # FLEURS — per-language folder by name
    fleurs_dir = AUDIO_DIR / "fleurs" / FLEURS_DIRS.get(lang, "")
    if is_arrow_dataset(fleurs_dir):
        arrows = list(fleurs_dir.rglob("*.arrow"))
        found.append(f"FLEURS({len(arrows)}shards)")

    # Common Voice — per-language folder by name
    cv_dir = AUDIO_DIR / "common_voice" / CV_DIRS.get(lang, "")
    if is_arrow_dataset(cv_dir):
        arrows = list(cv_dir.rglob("*.arrow"))
        found.append(f"CommonVoice({len(arrows)}shards)")

    # Bodo ASR — only for bod
    if lang == "bod":
        bodo_dir = AUDIO_DIR / "bodo_asr"
        if is_arrow_dataset(bodo_dir):
            arrows = list(bodo_dir.rglob("*.arrow"))
            found.append(f"BodoASR({len(arrows)}shards)")

    # Shared sources — check if downloaded and covers this lang
    for src_name, src_path in SHARED_SOURCES.items():
        if lang in SHARED_COVERAGE.get(src_name, set()):
            if is_arrow_dataset(src_path):
                found.append(f"{src_name}(shared)")

    return found

print("\n" + "="*70)
print("  DATASET GAP CHECK — ALL 22 LANGUAGES")
print("="*70)

# ── Parallel Text ──────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print("  PARALLEL TEXT  (datasets/parallel/<lang>/)")
print(f"{'─'*70}")
print(f"  {'Lang':<5} {'Name':<12} {'Train':>10} {'Dev':>8} {'Test':>8}  Status")
print(f"  {'─'*60}")

text_gaps = []
for lang in ALL_22:
    d   = PARALLEL_DIR / lang
    tr  = count_lines(d / "train.jsonl")
    dv  = count_lines(d / "dev.jsonl")
    te  = count_lines(d / "test.jsonl")
    name = LANG_NAMES[lang]

    if tr == 0 and dv == 0:
        status = "❌ FULLY MISSING"
        text_gaps.append((lang, "fully_missing"))
    elif tr == 0:
        status = "⚠  NO TRAIN"
        text_gaps.append((lang, "no_train"))
    elif dv == 0:
        status = "⚠  NO DEV"
        text_gaps.append((lang, "no_dev"))
    else:
        status = "✅ OK"

    # flag old odi/dog folder names still present
    old_key = "odi" if lang == "ory" else ("dog" if lang == "doi" else None)
    if old_key and (PARALLEL_DIR / old_key).exists():
        status += f"  [OLD FOLDER '{old_key}' EXISTS — rename to '{lang}']"

    print(f"  {lang:<5} {name:<12} {tr:>10,} {dv:>8,} {te:>8,}  {status}")

# ── Audio ──────────────────────────────────────────────────────────────
print(f"\n{'─'*70}")
print("  AUDIO  (datasets/audio/<source>/<lang>/)")
print(f"{'─'*70}")
print(f"  {'Lang':<5} {'Name':<12}  Sources found")
print(f"  {'─'*55}")

audio_gaps = []
for lang in ALL_22:
    sources = check_audio_dir(lang)
    name = LANG_NAMES[lang]
    if sources:
        print(f"  {lang:<5} {name:<12}  ✅ {', '.join(sources)}")
    else:
        print(f"  {lang:<5} {name:<12}  ❌ NO AUDIO DATA")
        audio_gaps.append(lang)

# ── Old folder names ───────────────────────────────────────────────────
print(f"\n{'─'*70}")
print("  FOLDER NAME CHECK (odi→ory, dog→doi)")
print(f"{'─'*70}")
for old, new in [("odi","ory"), ("dog","doi")]:
    old_path = PARALLEL_DIR / old
    new_path = PARALLEL_DIR / new
    if old_path.exists() and not new_path.exists():
        print(f"  ⚠  '{old}' folder exists but '{new}' missing — needs rename")
    elif old_path.exists() and new_path.exists():
        print(f"  ⚠  BOTH '{old}' and '{new}' exist — delete old '{old}'")
    else:
        print(f"  ✅ '{new}' folder OK")

# ── Summary ────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print("  SUMMARY")
print(f"{'='*70}")

fully_missing = [l for l,s in text_gaps if s == "fully_missing"]
no_train      = [l for l,s in text_gaps if s == "no_train"]
no_dev        = [l for l,s in text_gaps if s == "no_dev"]

print(f"  Text — fully missing : {len(fully_missing):>2}  {fully_missing}")
print(f"  Text — no train      : {len(no_train):>2}  {no_train}")
print(f"  Text — no dev        : {len(no_dev):>2}  {no_dev}")
print(f"  Audio — no data      : {len(audio_gaps):>2}  {audio_gaps}")

ok_text  = 22 - len(text_gaps)
ok_audio = 22 - len(audio_gaps)
print(f"\n  Text  coverage : {ok_text}/22 languages")
print(f"  Audio coverage : {ok_audio}/22 languages")

if fully_missing or no_train:
    print(f"\n  ACTION NEEDED:")
    if fully_missing:
        print(f"    Run: python prepare_dataset.py   (will fetch FLORES-200 for gap langs)")
    if audio_gaps:
        print(f"    Run: python download_datasets.py (will fetch Kathbath/FLEURS audio)")
print("="*70 + "\n")
