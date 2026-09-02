"""
Maithili translation test — 10 water-cycle sentences.
Verifies: no crash, no Hindi drift, no Bodo drift, correct Devanagari script.
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("PIPELINE_GPU", "0")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline.translator import Translator, _HINDI_IN_MAI_RE, _BODO_IN_MAI_RE, _MAITHILI_DRIFT_RE

SENTENCES = [
    "The water cycle describes how water moves continuously between the Earth's surface and the atmosphere, which has no true starting point.",
    "But water on the surface heats up, turns into vapor, rises into the sky, flows into clouds, and falls back down as rain or snow.",
    "The sun heats up the water in oceans, rivers, and lakes, causing it to change from liquid to vapor and rise into the air.",
    "This process is called evaporation. Plants also release water vapor through a process called transpiration.",
    "As clouds become heavy with condensed water, the water falls back to Earth as precipitation.",
    "This can happen in various forms, such as rain, snow, sleet, or hail, depending on the temperature.",
    "Let's explore what happens to the precipitation once it rains.",
    "The water cycle is essential for refilling our freshwater supplies.",
    "It's a vital process that shapes our weather and climate patterns and helps move nutrients through ecosystems.",
    "By understanding the cycle, we can make better decisions about conserving and protecting the environment.",
]

def check(text):
    issues = []
    if not text.strip():
        return ["EMPTY"]
    # Must have Devanagari chars
    deva = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    if deva < 5:
        issues.append(f"LOW_DEVA:{deva}")
    # Must not be English passthrough
    latin = sum(1 for c in text if 'A' <= c <= 'z')
    if latin > len(text) * 0.4:
        issues.append("ENGLISH_PASSTHROUGH")
    if _HINDI_IN_MAI_RE.search(text):
        issues.append("HINDI_DRIFT")
    if len(_BODO_IN_MAI_RE.findall(text)) >= 2:
        issues.append("BODO_DRIFT")
    return issues

t = Translator()
print("\n" + "="*65)
print("  MAITHILI (mai) — TRANSLATION TEST")
print("="*65)

passed = failed = 0
for i, src in enumerate(SENTENCES):
    try:
        res = t.translate(src, "eng", "mai")
        out = res["text"]
        engine = res["engine"]
        score = res["score"]["score"]
        issues = check(out)
        status = "✅" if not issues else f"❌ {issues}"
        if issues:
            failed += 1
        else:
            passed += 1
        print(f"\nSeg {i} [{engine}] score={score:.2f} {status}")
        print(f"  ENG: {src[:80]}")
        print(f"  MAI: {out}")
    except Exception as e:
        failed += 1
        print(f"\nSeg {i} ❌ EXCEPTION: {e}")

print(f"\n{'='*65}")
print(f"  RESULT: {passed}/10 PASS  {failed}/10 FAIL")
print("="*65)
