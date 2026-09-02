"""
Full 22-language translation test — same 10 water-cycle sentences.
Prints every translation, flags any wrong-language contamination.
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

ALL_LANGS = [
    ("hin", "Hindi"),
    ("ben", "Bengali"),
    ("tam", "Tamil"),
    ("tel", "Telugu"),
    ("kan", "Kannada"),
    ("mal", "Malayalam"),
    ("mar", "Marathi"),
    ("guj", "Gujarati"),
    ("pan", "Punjabi"),
    ("ory", "Odia"),
    ("asm", "Assamese"),
    ("urd", "Urdu"),
    ("nep", "Nepali"),
    ("mai", "Maithili"),
    ("doi", "Dogri"),
    ("bod", "Bodo"),
    ("san", "Sanskrit"),
    ("kok", "Konkani"),
    ("mni", "Manipuri"),
    ("sat", "Santhali"),
    ("kas", "Kashmiri"),
    ("snd", "Sindhi"),
]

# Wrong-language contamination markers
BODO_MARKERS     = ["आरो", "खालामो", "गुदुं", "लैथोफोर", "मोनसे", "गोनां", "निफ्राय", "दैखौ"]
MAITHILI_MARKERS = ["छैक", "होयत", "जानि", "लिअ", "बरखाक", "वर्षाकी", "किछु"]
HINDI_MARKERS    = ["है।", "हैं।", "होता है", "करता है", "जाता है", "होती है"]

SCRIPT_RANGES = {
    "hin": (0x0900, 0x097F), "mar": (0x0900, 0x097F), "mai": (0x0900, 0x097F),
    "doi": (0x0900, 0x097F), "san": (0x0900, 0x097F), "nep": (0x0900, 0x097F),
    "bod": (0x0900, 0x097F), "kok": (0x0900, 0x097F),
    "ben": (0x0980, 0x09FF), "asm": (0x0980, 0x09FF), "mni": (0x0980, 0x09FF),
    "guj": (0x0A80, 0x0AFF), "pan": (0x0A00, 0x0A7F),
    "kan": (0x0C80, 0x0CFF), "mal": (0x0D00, 0x0D7F),
    "ory": (0x0B00, 0x0B7F), "tam": (0x0B80, 0x0BFF), "tel": (0x0C00, 0x0C7F),
    "urd": (0x0600, 0x06FF), "kas": (0x0600, 0x06FF), "snd": (0x0600, 0x06FF),
    "sat": (0x1C50, 0x1C7F),
}

def script_ratio(text, lo, hi):
    chars = [c for c in text if c not in ' \n\t।॥,.!?;:']
    if not chars: return 0.0
    in_script = sum(1 for c in chars if lo <= ord(c) <= hi)
    return in_script / len(chars)

def check_output(lang, text):
    issues = []
    if not text.strip():
        return ["EMPTY_OUTPUT"]
    # Bodo/Maithili contamination in Devanagari-script langs
    if lang in ("hin", "mar", "mai", "nep", "doi", "san", "kok"):
        for m in BODO_MARKERS:
            if m in text: issues.append(f"BODO_MARKER:{m}")
        for m in MAITHILI_MARKERS:
            if m in text: issues.append(f"MAI_MARKER:{m}")
    # Hindi leaking into non-Hindi Devanagari langs
    if lang in ("nep", "doi", "san", "kok", "bod"):
        for m in HINDI_MARKERS:
            if m in text: issues.append(f"HINDI_LEAK:{m}")
    # Script ratio check — at least 40% chars should be in target script
    if lang in SCRIPT_RANGES:
        lo, hi = SCRIPT_RANGES[lang]
        ratio = script_ratio(text, lo, hi)
        if ratio < 0.30 and lang not in ("sat",):  # sat may use Bengali script
            issues.append(f"LOW_SCRIPT_RATIO:{ratio:.0%}")
    return issues

srcs = [s for _, s in SENTENCES]
t = Translator()

summary = {}
print("\n" + "="*70)
print("  ALL 22 LANGUAGES — TRANSLATION TEST")
print("="*70)

for lang, label in ALL_LANGS:
    print(f"\n{'─'*70}")
    print(f"  [{lang.upper()}] {label}")
    print(f"{'─'*70}")
    try:
        results = t.translate_batch(srcs, src_lang="eng", tgt_lang=lang)
        lang_pass = True
        seg_results = []
        for (seg_id, src), res in zip(SENTENCES, results):
            out    = res["text"]
            engine = res["engine"]
            score  = res["score"]["score"]
            issues = check_output(lang, out)
            if issues: lang_pass = False
            seg_results.append((seg_id, src, out, engine, score, issues))
            status = "✅" if not issues else f"❌ {issues}"
            print(f"  Seg {seg_id} [{engine}] {status}")
            print(f"    ENG: {src[:70]}")
            print(f"    {lang.upper()}: {out}")
        summary[lang] = ("PASS" if lang_pass else "FAIL", label)
    except Exception as e:
        print(f"  ❌ EXCEPTION: {e}")
        summary[lang] = ("ERROR", label)

# Final summary table
print("\n\n" + "="*70)
print("  FINAL SUMMARY — ALL 22 LANGUAGES")
print("="*70)
passed = failed = errors = 0
for lang, (status, label) in summary.items():
    icon = "✅" if status == "PASS" else ("❌" if status == "FAIL" else "💥")
    print(f"  {icon} [{lang.upper():4}] {label:15} — {status}")
    if status == "PASS": passed += 1
    elif status == "FAIL": failed += 1
    else: errors += 1
print(f"\n  PASSED: {passed}/22   FAILED: {failed}/22   ERRORS: {errors}/22")
print("="*70)
