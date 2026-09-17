"""
Regression test for the quality gate: it MUST flag wrong-language and
untranslated output as failed. Uses the exact bad segments observed in
KB_COURSE_001 hin/pan metadata (avg_score was falsely 1.0).

Run:  python scripts/test_quality_wronglang.py
Exit code 0 = all assertions passed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.quality import score_segment, detect_wrong_language

failures = []


def check(name, cond):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}")
    if not cond:
        failures.append(name)


# ── Real Maithili-drift segments from KB_COURSE_001 hin metadata ─────────────
# These were emitted for a HINDI target but are actually Maithili.
MAITHILI_HIN = {
    33: "कार्रवाईक लेल नैतिक सोच आ मूल्य आ नीतिशास्त्रक परिचय अछि।",
    45: "स्वयं जलरोधक पृथक डिब्बासभ नहि छथि।",
    52: "एकर एकटा हिस्सा एहन सेहो अछि जकर आविष्कार आ सृजन करबाक चाही।",
    1:  "हम विनीत साहू छी, हम आईआईटी कानपुर में दर्शनशास्त्र पढ़ाते हैं",
}
SRC_HIN = "placeholder english source sentence for length ratio"

for sid, bad in MAITHILI_HIN.items():
    is_wrong, reason = detect_wrong_language(bad, "hin")
    check(f"hin seg {sid}: detect_wrong_language flags Maithili", is_wrong)
    res = score_segment(SRC_HIN, bad, "eng", "hin")
    check(f"hin seg {sid}: score_segment marks failed", res["failed"] is True)
    check(f"hin seg {sid}: has wrong_language flag",
          any(f.startswith("wrong_language") for f in res["flags"]))

# ── Correct Hindi must NOT be flagged (no false positives) ───────────────────
GOOD_HIN = {
    0:  "नमस्कार। आज हम यहाँ नैतिकता के बारे में बात करने आए हैं।",
    2:  "तो मुझे दर्शन के साथ शुरू करते हैं।",
    39: "और कभी-कभी कोई सोच सकता है कि सिद्धांत और दर्शन की दुनिया आपसे बहुत दूर है।",
    54: "यह कुछ ऐसा है जो हम एक साथ बनाते हैं।",
}
for sid, good in GOOD_HIN.items():
    is_wrong, reason = detect_wrong_language(good, "hin")
    check(f"hin seg {sid}: correct Hindi NOT flagged (reason={reason})", not is_wrong)
    res = score_segment(SRC_HIN, good, "eng", "hin")
    check(f"hin seg {sid}: correct Hindi not failed", res["failed"] is False)

# ── When the TARGET is Maithili, the same text must be accepted ──────────────
is_wrong, _ = detect_wrong_language(MAITHILI_HIN[33], "mai")
check("mai target: Maithili text NOT flagged as wrong", not is_wrong)

# ── Punjabi seg 21: untranslated English must fail ───────────────────────────
PAN_ENGLISH = "Let's now look at some details of the ceremony."
res = score_segment(PAN_ENGLISH, PAN_ENGLISH, "eng", "pan")
check("pan seg 21: untranslated English marked failed", res["failed"] is True)

# ── Empty output must fail ───────────────────────────────────────────────────
res = score_segment("some source", "", "eng", "pan")
check("empty translation marked failed", res["failed"] is True)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED")
sys.exit(0)
