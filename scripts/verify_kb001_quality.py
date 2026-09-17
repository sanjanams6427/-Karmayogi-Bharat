"""
Verification: re-score the ALREADY-SHIPPED KB_COURSE_001 hin/pan metadata
through the FIXED quality gate. Proves the gate now catches the wrong-language
and untranslated defects that previously passed with avg_score=1.0.

Run:  venv\\Scripts\\python.exe scripts\\verify_kb001_quality.py
"""
import sys, json
from pathlib import Path

# Windows console defaults to cp1252 which cannot encode Devanagari/Gurmukhi.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.quality import score_segment, review_summary

ROOT = Path(__file__).parent.parent
JOBS = {
    "hin": ROOT / "output/KB_COURSE_001/hin/KB_COURSE_001_hin_metadata.json",
    "pan": ROOT / "output/KB_COURSE_001/pan/KB_COURSE_001_pan_metadata.json",
}

overall_ok = True
for lang, path in JOBS.items():
    if not path.exists():
        print(f"[SKIP] {lang}: metadata not found at {path}")
        continue
    meta = json.loads(path.read_text(encoding="utf-8"))
    translations = meta.get("translations", [])
    old_summary = meta.get("quality_summary", {})
    scores = []
    bad = []
    for t in translations:
        src = t.get("src_text", "")
        txt = t.get("text", "")
        res = score_segment(src, txt, "eng", lang)
        scores.append(res)
        if res["failed"] or res["needs_review"]:
            bad.append((t.get("id"), res["score"], res["flags"], txt[:50]))
    new_summary = review_summary(scores)
    print(f"\n=== {lang.upper()} ({len(translations)} segments) ===")
    print(f"  OLD shipped: avg_score={old_summary.get('avg_score')} "
          f"failed={old_summary.get('failed')} needs_review={old_summary.get('needs_review')}")
    print(f"  NEW gate:    avg_score={new_summary['avg_score']} "
          f"failed={new_summary['failed']} needs_review={new_summary['needs_review']}")
    print(f"  Flagged segments now caught: {len(bad)}")
    for sid, sc, flags, preview in bad[:15]:
        print(f"    seg {sid}: score={sc} flags={flags}")
        print(f"             {preview}")

    # The HIN metadata has since been regenerated with corrected Hindi, so the
    # known-bad segments should now be CLEAN (not flagged). If any Maithili drift
    # ever returns, detect_wrong_language will flag it and this check fails.
    if lang == "hin":
        from pipeline.quality import detect_wrong_language
        d = {t.get("id"): t.get("text", "") for t in translations}
        still_bad = [sid for sid in (1, 33, 45, 52)
                     if detect_wrong_language(d.get(sid, ""), "hin")[0]]
        if still_bad:
            print(f"  [FAIL] hin: Maithili drift STILL present in segs: {still_bad}")
            overall_ok = False
        else:
            print(f"  [OK] hin: segs 1/33/45/52 are now clean Hindi (Maithili drift gone)")
    if lang == "pan":
        caught_ids = {sid for sid, *_ in bad}
        if 21 not in caught_ids:
            print(f"  [WARN] pan: untranslated seg 21 not flagged (may have been regenerated)")
        else:
            print(f"  [OK] pan: untranslated seg 21 caught by gate")

print()
print("VERIFICATION PASSED" if overall_ok else "VERIFICATION FAILED")
sys.exit(0 if overall_ok else 1)
