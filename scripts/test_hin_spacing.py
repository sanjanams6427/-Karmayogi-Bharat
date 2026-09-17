"""
Verify _naturalise repairs the IndicTrans2 word-join artifacts seen in the
KB_COURSE_001 Hindi SRT (लेकिनैतिकता, विभिन्नैतिक, दार्शनिक्या/दार्शनिक्यों)
and translates the leftover English term 'axiology'.

Run:  venv\\Scripts\\python.exe scripts\\test_hin_spacing.py
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.translator import _naturalise

failures = []


def check(name, got, must_contain, must_not_contain=None):
    ok = must_contain in got
    if must_not_contain is not None:
        ok = ok and (must_not_contain not in got)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"        -> {got}")
    if not ok:
        failures.append(name)


cases = [
    ("लेकिनैतिकता",
     "आज हम यहाँ नैतिकता के बारे में बात करने आए हैं, लेकिनैतिकता के बारे में",
     "लेकिन नैतिकता", "लेकिनैतिकता"),
    ("विभिन्नैतिक",
     "दर्शन और विभिन्नैतिक अवधारणाओं के एक हिस्से के रूप में",
     "विभिन्न नैतिक", "विभिन्नैतिक"),
    ("दार्शनिक्या",
     "लेकिन दार्शनिक्या करते हैं और हमें दार्शनिकों की आवश्यकता क्यों है",
     "दार्शनिक क्या", "दार्शनिक्या"),
    ("दार्शनिक्यों",
     "दार्शनिक्यों? सबसे पहले, क्या हम दार्शनिक न होने में",
     "दार्शनिक क्यों", "दार्शनिक्यों"),
    ("axiology",
     "इसका एक हिस्सा है axiology जो मूल्यों का अध्ययन करता है",
     "मूल्यमीमांसा", "axiology"),
]

for name, inp, must, mustnot in cases:
    out = _naturalise(inp, "hin")
    check(name, out, must, mustnot)

clean = "यह कुछ ऐसा है जो हम एक साथ बनाते हैं।"
out = _naturalise(clean, "hin")
check("clean Hindi unchanged", out, "एक साथ बनाते हैं")

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED")
sys.exit(0)
