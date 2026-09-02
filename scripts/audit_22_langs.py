"""
Production-readiness audit for all 22 language outputs of KB_COURSE_001.
Reads metadata JSON + SRT for each language and prints a pass/fail table.

Usage:
    python scripts/audit_22_langs.py
    python scripts/audit_22_langs.py --course-id KB_COURSE_001
"""
import json, re, sys, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "output"

ALL_LANGS = [
    "asm", "ben", "bod", "doi", "guj", "hin", "kan", "kas", "kok",
    "mai", "mal", "mar", "mni", "nep", "ory", "pan", "san", "sat",
    "snd", "tam", "tel", "urd",
]

LANG_NAMES = {
    "asm": "Assamese",   "ben": "Bengali",    "bod": "Bodo",
    "doi": "Dogri",      "guj": "Gujarati",   "hin": "Hindi",
    "kan": "Kannada",    "kas": "Kashmiri",   "kok": "Konkani",
    "mai": "Maithili",   "mal": "Malayalam",  "mar": "Marathi",
    "mni": "Manipuri",   "nep": "Nepali",     "ory": "Odia",
    "pan": "Punjabi",    "san": "Sanskrit",   "sat": "Santhali",
    "snd": "Sindhi",     "tam": "Tamil",      "tel": "Telugu",
    "urd": "Urdu",
}

# Maithili morphemes that must not appear in Hindi output
_MAI_IN_HIN = re.compile(
    r'समयमे|किछु|खिचयबाक|कक्षमे|आब माननीय|छे\.|^छे\s|होयत|जानि|लिअ|बरखाक|छैक'
)
# Bodo morphemes that must not appear in Hindi output
_BOD_IN_HIN = re.compile(r'खालामो|ओंखार|गुदुं|आरो|निफ्राय|सोलाय|बिथिं|फारि|गेजेर|लांओ')


def check_srt(srt_path: Path) -> dict:
    """Basic SRT sanity: non-empty, has timestamps, no obvious corruption."""
    issues = []
    if not srt_path.exists():
        return {"ok": False, "issues": ["SRT file missing"]}
    text = srt_path.read_text(encoding="utf-8", errors="replace")
    if len(text.strip()) < 50:
        issues.append("SRT suspiciously short (<50 chars)")
    if "-->" not in text:
        issues.append("SRT has no timestamps")
    if "\uFFFD" in text:
        issues.append("SRT contains replacement chars (encoding corruption)")
    return {"ok": len(issues) == 0, "issues": issues}


def audit_lang(course_dir: Path, lang: str) -> dict:
    lang_dir = course_dir / lang
    meta_path = lang_dir / f"{course_dir.name}_{lang}_metadata.json"
    srt_path  = lang_dir / f"{course_dir.name}_{lang}.srt"
    mp4_path  = lang_dir / f"{course_dir.name}_{lang}.mp4"

    result = {
        "lang": lang,
        "name": LANG_NAMES.get(lang, lang),
        "status": "PASS",
        "issues": [],
        "warnings": [],
        "needs_review_segs": [],
        "failed_segs": [],
        "drift_segs": [],
        "avg_score": None,
        "engine": None,
        "files_present": False,
    }

    # File presence check
    missing = [f.name for f in [meta_path, srt_path, mp4_path] if not f.exists()]
    if missing:
        result["status"] = "FAIL"
        result["issues"].append(f"Missing files: {missing}")
        return result
    result["files_present"] = True

    # SRT check
    srt_check = check_srt(srt_path)
    if not srt_check["ok"]:
        result["status"] = "FAIL"
        result["issues"].extend(srt_check["issues"])

    # Metadata check
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        result["status"] = "FAIL"
        result["issues"].append(f"Metadata JSON parse error: {e}")
        return result

    qs = meta.get("quality_summary", {})
    result["avg_score"] = qs.get("avg_score")
    result["duration_ratio"] = qs.get("duration_ratio", 1.0)

    # Duration ratio check (KB tender §5.1B — warn if >20% longer)
    if result["duration_ratio"] and result["duration_ratio"] > 1.20:
        result["status"] = "WARN"
        result["warnings"].append(f"Duration ratio {result['duration_ratio']:.2f}x > 1.20 (KB §5.1B)")

    # Needs-review segments
    translations = meta.get("translations", [])
    engines_used = set()
    for seg in translations:
        q = seg.get("quality", {})
        engines_used.add(seg.get("engine", "unknown"))
        seg_id = seg.get("id")
        if q.get("failed"):
            result["failed_segs"].append(seg_id)
            result["status"] = "FAIL"
        elif q.get("needs_review"):
            result["needs_review_segs"].append({
                "id": seg_id,
                "flags": q.get("flags", []),
                "text_preview": seg.get("text", "")[:80],
            })
            if result["status"] == "PASS":
                result["status"] = "WARN"

        # Drift detection for Hindi
        if lang == "hin":
            tgt_text = seg.get("text", "")
            if _MAI_IN_HIN.search(tgt_text):
                result["drift_segs"].append({"id": seg_id, "type": "maithili", "text": tgt_text[:80]})
                result["status"] = "FAIL"
                if "Maithili drift in Hindi output" not in result["issues"]:
                    result["issues"].append("Maithili drift in Hindi output")
            if _BOD_IN_HIN.search(tgt_text):
                result["drift_segs"].append({"id": seg_id, "type": "bodo", "text": tgt_text[:80]})
                result["status"] = "FAIL"
                if "Bodo drift in Hindi output" not in result["issues"]:
                    result["issues"].append("Bodo drift in Hindi output")

    result["engine"] = ", ".join(sorted(engines_used - {"unknown"})) or "unknown"

    if result["failed_segs"]:
        result["issues"].append(f"Failed segments: {result['failed_segs']}")

    return result


def _safe(s: str) -> str:
    """Encode to ASCII for Windows console, replacing non-ASCII with '?'."""
    return s.encode("ascii", errors="replace").decode("ascii")


def print_report(results: list[dict], course_id: str):
    PASS  = "\033[92mPASS\033[0m"
    WARN  = "\033[93mWARN\033[0m"
    FAIL  = "\033[91mFAIL\033[0m"
    STATUS_MAP = {"PASS": PASS, "WARN": WARN, "FAIL": FAIL}

    print(f"\n{'='*72}")
    print(f"  KB Production Readiness Audit — {course_id}")
    print(f"{'='*72}")
    print(f"  {'Lang':<6} {'Name':<12} {'Status':<8} {'Score':<7} {'Ratio':<7} {'Engine':<16} Notes")
    print(f"  {'-'*66}")

    pass_count = warn_count = fail_count = 0
    for r in results:
        status_str = STATUS_MAP.get(r["status"], r["status"])
        score_str  = f"{r['avg_score']:.3f}" if r["avg_score"] is not None else "N/A"
        ratio_str  = f"{r['duration_ratio']:.2f}x" if r.get("duration_ratio") else "N/A"
        engine_str = (r["engine"] or "")[:16]
        notes = []
        if r["needs_review_segs"]:
            notes.append(f"{len(r['needs_review_segs'])} needs_review")
        if r["drift_segs"]:
            notes.append(f"{len(r['drift_segs'])} drift")
        if r["issues"]:
            notes.extend(r["issues"][:2])
        notes_str = "; ".join(notes)[:50]
        print(f"  {r['lang']:<6} {r['name']:<12} {status_str:<17} {score_str:<7} {ratio_str:<7} {engine_str:<16} {notes_str}")
        if r["status"] == "PASS":   pass_count += 1
        elif r["status"] == "WARN": warn_count += 1
        else:                       fail_count += 1

    print(f"\n  Summary: {pass_count} PASS  {warn_count} WARN  {fail_count} FAIL  (of {len(results)} languages)")

    # Detail section for non-PASS
    non_pass = [r for r in results if r["status"] != "PASS"]
    if non_pass:
        print(f"\n{'='*72}")
        print("  DETAIL — Languages requiring attention")
        print(f"{'='*72}")
        for r in non_pass:
            print(f"\n  [{r['status']}] {r['lang']} ({r['name']})")
            for issue in r["issues"]:
                print(f"    ISSUE  : {issue}")
            for warn in r["warnings"]:
                print(f"    WARN   : {warn}")
            for seg in r["needs_review_segs"]:
                print(f"    REVIEW : seg {seg['id']} flags={seg['flags']}")
                print(f"             \"{_safe(seg['text_preview'])}\"")
            for seg in r["drift_segs"]:
                print(f"    DRIFT  : seg {seg['id']} type={seg['type']}")
                print(f"             \"{_safe(seg['text'])}\"")
    print(f"\n{'='*72}\n")
    return fail_count == 0


def main():
    parser = argparse.ArgumentParser(description="Audit 22-language KB output")
    parser.add_argument("--course-id", default="KB_COURSE_001")
    parser.add_argument("--output-dir", default=str(OUTPUT))
    args = parser.parse_args()

    course_dir = Path(args.output_dir) / args.course_id
    if not course_dir.exists():
        print(f"ERROR: Course directory not found: {course_dir}")
        sys.exit(1)

    results = [audit_lang(course_dir, lang) for lang in ALL_LANGS]
    ok = print_report(results, args.course_id)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
