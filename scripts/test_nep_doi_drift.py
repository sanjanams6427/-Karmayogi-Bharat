"""
Live drift test for Nepali (nep) and Dogri (doi) — same 10 water-cycle sentences.
Checks for wrong-language contamination in both outputs.
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("PIPELINE_GPU", "0")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline.translator import Translator

SENTENCES = [
    (0, "The water cycle describes how water moves continuously between the Earth's surface and the atmosphere, which has no true starting point."),
    (1, "But water on the surface heats up, turns into vapor, rises into the sky, flows into clouds, and falls back down as rain or snow."),
    (2, "The sun heats up the water in oceans, rivers, and lakes, causing it to change from liquid to vapor and rise into the air."),
    (3, "This process is called evaporation. Plants also release water vapor through a process called transpiration."),
    (4, "As clouds become heavy with condensed water, the water falls back to Earth as precipitation."),
    (5, "This can happen in various forms, such as rain, snow, sleet, or hail, depending on the temperature."),
    (6, "Let's explore what happens to the precipitation once it rains."),
    (7, "The water cycle is essential for refilling our freshwater supplies."),
    (8, "It's a vital process that shapes our weather and climate patterns and helps move nutrients through ecosystems."),
    (9, "By understanding the cycle, we can make better decisions about conserving and protecting the environment."),
]

# Known bad markers for each language
BODO_MARKERS    = ["आरो", "खालामो", "गुदुं", "लैथोफोर", "मोनसे", "गोनां", "निफ्राय", "दैखौ", "जायनि"]
MAITHILI_MARKERS = ["छैक", "होयत", "जानि", "लिअ", "बरखाक", "वर्षाकी", "किछु", "अछि"]
HINDI_MARKERS   = ["है।", "हैं।", "होता है", "करता है", "जाता है"]  # Hindi leaking into nep/doi

def check(lang, text):
    issues = []
    if lang in ("nep", "doi"):
        hits = [m for m in HINDI_MARKERS if m in text]
        if hits: issues.append(f"HINDI_LEAK:{hits}")
        hits = [m for m in BODO_MARKERS if m in text]
        if hits: issues.append(f"BODO:{hits}")
        hits = [m for m in MAITHILI_MARKERS if m in text]
        if hits: issues.append(f"MAITHILI:{hits}")
    return issues

t = Translator()
srcs = [s for _, s in SENTENCES]

for lang, label in [("nep", "NEPALI"), ("doi", "DOGRI")]:
    print(f"\n{'='*70}")
    print(f"  {label} ({lang}) — 10 segments")
    print(f"{'='*70}")
    results = t.translate_batch(srcs, src_lang="eng", tgt_lang=lang)
    all_pass = True
    for (seg_id, src), res in zip(SENTENCES, results):
        out    = res["text"]
        engine = res["engine"]
        score  = res["score"]["score"]
        issues = check(lang, out)
        status = "✅ PASS" if not issues else f"❌ {' | '.join(issues)}"
        if issues: all_pass = False
        print(f"\nSeg {seg_id} [{engine}] score={score:.2f} {status}")
        print(f"  ENG: {src[:80]}")
        print(f"  {label[:3]}: {out}")
    print(f"\n{'='*70}")
    print(f"{'✅ ALL PASS' if all_pass else '❌ ISSUES FOUND'} — {label}")
    print(f"{'='*70}")
