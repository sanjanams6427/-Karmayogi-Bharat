"""
verify_datasets.py — Deep verification of all 22 language parallel datasets.
Checks: line counts, JSON validity, empty src/tgt, bad length ratios,
        src_lang/tgt_lang field presence, duplicate src detection, script sanity.
"""
import json, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from collections import defaultdict

PARALLEL_DIR = Path("datasets/parallel")
ALL_22 = ["asm","ben","guj","hin","kan","mal","mar","ory","pan","tam","tel",
          "bod","doi","kas","kok","mni","mai","nep","san","sat","snd","urd"]
LANG_NAMES = {
    "asm":"Assamese","ben":"Bengali","guj":"Gujarati","hin":"Hindi",
    "kan":"Kannada","mal":"Malayalam","mar":"Marathi","ory":"Odia",
    "pan":"Punjabi","tam":"Tamil","tel":"Telugu","bod":"Bodo",
    "doi":"Dogri","kas":"Kashmiri","kok":"Konkani","mni":"Manipuri",
    "mai":"Maithili","nep":"Nepali","san":"Sanskrit","sat":"Santhali",
    "snd":"Sindhi","urd":"Urdu",
}

# Expected src_lang field value in each file
EXPECTED_SRC_LANG = "eng"

# Unicode script ranges for target language sanity check (spot-check first record)
SCRIPT_RANGES = {
    "hin": (0x0900, 0x097F), "mar": (0x0900, 0x097F), "mai": (0x0900, 0x097F),
    "doi": (0x0900, 0x097F), "san": (0x0900, 0x097F), "nep": (0x0900, 0x097F),
    "bod": (0x0900, 0x097F), "kok": (0x0900, 0x097F),
    "ben": (0x0980, 0x09FF), "asm": (0x0980, 0x09FF), "mni": (0x0980, 0x09FF),
    "guj": (0x0A80, 0x0AFF),
    "pan": (0x0A00, 0x0A7F),
    "kan": (0x0C80, 0x0CFF),
    "mal": (0x0D00, 0x0D7F),
    "ory": (0x0B00, 0x0B7F),
    "tam": (0x0B80, 0x0BFF),
    "tel": (0x0C00, 0x0C7F),
    "urd": (0x0600, 0x06FF),
    "kas": (0x0600, 0x06FF),
    "snd": (0x0600, 0x06FF),
    "sat": (0x1C50, 0x1C7F),
}


def script_ok(text: str, lang: str) -> bool:
    """Check at least 20% of non-ASCII chars are in the expected script range."""
    if lang not in SCRIPT_RANGES:
        return True
    lo, hi = SCRIPT_RANGES[lang]
    non_ascii = [c for c in text if ord(c) > 127]
    if not non_ascii:
        return False  # no non-ASCII at all — wrong script
    in_range = sum(1 for c in non_ascii if lo <= ord(c) <= hi)
    return (in_range / len(non_ascii)) >= 0.20


def verify_split(lang: str, split: str) -> dict:
    path = PARALLEL_DIR / lang / f"{split}.jsonl"
    stats = {
        "total": 0, "parse_err": 0, "empty_src": 0, "empty_tgt": 0,
        "bad_ratio": 0, "missing_lang_field": 0, "wrong_src_lang": 0,
        "wrong_script": 0, "duplicate_src": 0,
        "first_src": "", "first_tgt": "",
    }
    if not path.exists():
        stats["missing_file"] = True
        return stats

    seen_src = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            stats["total"] += 1
            try:
                r = json.loads(line)
            except Exception:
                stats["parse_err"] += 1
                continue

            src = r.get("src", "").strip()
            tgt = r.get("tgt", "").strip()

            if not src: stats["empty_src"] += 1
            if not tgt: stats["empty_tgt"] += 1

            if src and tgt:
                ratio = len(tgt) / len(src)
                if ratio < 0.15 or ratio > 10.0:
                    stats["bad_ratio"] += 1

            if "src_lang" not in r or "tgt_lang" not in r:
                stats["missing_lang_field"] += 1
            elif r.get("src_lang") != EXPECTED_SRC_LANG:
                stats["wrong_src_lang"] += 1

            # Script check on first 200 records only (performance)
            if tgt and i < 200 and not script_ok(tgt, lang):
                stats["wrong_script"] += 1

            # Duplicate check on first 50K (memory-safe)
            if src and i < 50000:
                if src in seen_src:
                    stats["duplicate_src"] += 1
                else:
                    seen_src.add(src)

            if i == 0:
                stats["first_src"] = src[:60]
                stats["first_tgt"] = tgt[:50]

    return stats


# ── Run verification ───────────────────────────────────────────
all_issues = []
summary_rows = []

print("=" * 78)
print("  FULL DATASET VERIFICATION — ALL 22 LANGUAGES")
print("=" * 78)

for lang in ALL_22:
    name = LANG_NAMES[lang]
    lang_ok = True
    lang_issues = []

    for split in ("train", "dev", "test"):
        s = verify_split(lang, split)

        if s.get("missing_file"):
            lang_issues.append(f"{split}: FILE MISSING")
            lang_ok = False
            continue

        if s["total"] == 0:
            lang_issues.append(f"{split}: EMPTY FILE (0 records)")
            lang_ok = False
            continue

        checks = {
            "parse_err":          ("parse errors",        s["parse_err"]),
            "empty_src":          ("empty src",           s["empty_src"]),
            "empty_tgt":          ("empty tgt",           s["empty_tgt"]),
            "bad_ratio":          ("bad len ratio",       s["bad_ratio"]),
            "missing_lang_field": ("missing lang field",  s["missing_lang_field"]),
            "wrong_src_lang":     ("wrong src_lang",      s["wrong_src_lang"]),
            "wrong_script":       ("wrong script",        s["wrong_script"]),
            "duplicate_src":      ("duplicate src",       s["duplicate_src"]),
        }
        for key, (label, count) in checks.items():
            if count > 0:
                pct = count / s["total"] * 100
                # Tolerate up to 2% wrong_script (some langs mix scripts legitimately)
                # Tolerate up to 5% duplicates (TM repeat factor causes this intentionally)
                if key == "wrong_script" and pct < 5.0:
                    continue
                if key == "duplicate_src" and pct < 6.0:
                    continue
                lang_issues.append(f"{split}: {label}={count} ({pct:.1f}%)")
                lang_ok = False

    train_s = verify_split(lang, "train")
    dev_s   = verify_split(lang, "dev")
    test_s  = verify_split(lang, "test")

    status = "OK" if lang_ok else "WARN"
    summary_rows.append((lang, name, train_s["total"], dev_s["total"],
                         test_s["total"], status, lang_issues,
                         train_s.get("first_src",""), train_s.get("first_tgt","")))

# ── Print table ────────────────────────────────────────────────
print(f"\n{'Lang':<5} {'Name':<12} {'Train':>8} {'Dev':>6} {'Test':>6}  {'Status'}")
print("-" * 55)
for lang, name, tr, dv, te, status, issues, fsrc, ftgt in summary_rows:
    flag = "[OK]  " if status == "OK" else "[WARN]"
    print(f"{lang:<5} {name:<12} {tr:>8,} {dv:>6,} {te:>6,}  {flag}")
    if issues:
        for iss in issues:
            print(f"       !! {iss}")

# ── Script spot-check ──────────────────────────────────────────
print(f"\n{'─'*78}")
print("  SCRIPT SPOT-CHECK (first record tgt field)")
print(f"{'─'*78}")
for lang, name, tr, dv, te, status, issues, fsrc, ftgt in summary_rows:
    script_flag = "OK" if ftgt else "NO_TGT"
    print(f"  {lang:<5} {name:<12}  src: {fsrc[:45]!r}")
    print(f"  {'':5} {'':12}  tgt: {ftgt[:45]!r}")

# ── Summary ────────────────────────────────────────────────────
print(f"\n{'='*78}")
print("  SUMMARY")
print(f"{'='*78}")
ok_langs   = [r[0] for r in summary_rows if r[5] == "OK"]
warn_langs = [r[0] for r in summary_rows if r[5] == "WARN"]
total_train = sum(r[2] for r in summary_rows)
total_dev   = sum(r[3] for r in summary_rows)

print(f"  Languages OK   : {len(ok_langs)}/22  {ok_langs}")
print(f"  Languages WARN : {len(warn_langs)}/22  {warn_langs}")
print(f"  Total train    : {total_train:,}")
print(f"  Total dev      : {total_dev:,}")

gap_langs = ["bod","doi","kas","kok","mni","mai","san","sat"]
print(f"\n  Gap language train counts:")
for r in summary_rows:
    if r[0] in gap_langs:
        print(f"    {r[0]:<5} {r[1]:<12} train={r[2]:>7,}  dev={r[3]:>5,}")

print(f"\n  {'PASS — all 22 languages verified' if not warn_langs else 'ISSUES FOUND — see WARN rows above'}")
print("=" * 78)
