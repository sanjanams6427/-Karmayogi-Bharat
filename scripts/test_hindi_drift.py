"""
Live drift test — runs IndicTrans2 en_indic directly on the 10 water-cycle
sentences and prints every translation. Checks for Bodo / Maithili markers.
No web server needed — imports the Translator directly.
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("PIPELINE_GPU", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline.translator import (
    Translator, _BODO_IN_HIN_RE, _MAITHILI_IN_HIN_RE, _MAITHILI_DRIFT_RE
)

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

BODO_MARKERS   = ["आरो", "खालामो", "गुदुं", "लैथोफोर", "मोनसे", "गोनां", "निफ्राय", "दैखौ", "जायनि", "फारि"]
MAITHILI_MARKERS = ["छैक", "होयत", "जानि", "लिअ", "बरखाक", "वर्षाकी", "किछु", "अछि", "छथि"]

print("=" * 70)
print("LOADING IndicTrans2 en_indic...")
print("=" * 70)

t = Translator()

print("\nRunning BATCH translation (all 10 sentences at once)...")
print("-" * 70)

results = t.translate_batch(
    [s for _, s in SENTENCES],
    src_lang="eng",
    tgt_lang="hin",
)

all_pass = True
for (seg_id, src), res in zip(SENTENCES, results):
    translated = res["text"]
    engine     = res["engine"]
    score      = res["score"]["score"]

    bodo_hits     = [m for m in BODO_MARKERS if m in translated]
    maithili_hits = [m for m in MAITHILI_MARKERS if m in translated]
    re_bodo       = bool(_BODO_IN_HIN_RE.search(translated))
    re_mai        = bool(_MAITHILI_IN_HIN_RE.search(translated))

    status = "✅ PASS"
    if bodo_hits or re_bodo:
        status = f"❌ BODO DRIFT: {bodo_hits}"
        all_pass = False
    elif maithili_hits or re_mai:
        status = f"❌ MAITHILI DRIFT: {maithili_hits}"
        all_pass = False

    print(f"\nSeg {seg_id} [{engine}] score={score:.2f} {status}")
    print(f"  SRC: {src}")
    print(f"  HIN: {translated}")

print("\n" + "=" * 70)
if all_pass:
    print("✅ ALL 10 SEGMENTS PASS — No Bodo or Maithili drift detected.")
else:
    print("❌ DRIFT DETECTED — see segments above.")
print("=" * 70)
