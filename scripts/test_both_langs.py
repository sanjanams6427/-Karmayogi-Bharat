"""
Combined pre-flight check for BOTH Hindi and Punjabi through the quality gate:
 - hin: Maithili drift must fail; correct Hindi must pass
 - pan: untranslated English must fail; correct Punjabi must pass

Run:  venv\\Scripts\\python.exe scripts\\test_both_langs.py
"""
import sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.quality import score_segment

SRC = "some english source sentence of reasonable length"
tests = [
    ("hin", "Maithili drift -> FAIL",
     "कार्रवाईक लेल नैतिक सोच आ मूल्य आ अछि।", True),
    ("hin", "correct Hindi -> pass",
     "यह कुछ ऐसा है जो हम एक साथ बनाते हैं।", False),
    ("pan", "untranslated English -> FAIL",
     "Let's now look at some details of the ceremony.", True),
    ("pan", "correct Punjabi -> pass",
     "ਮਾਣਯੋਗ ਮਹਿਮਾਨ ਦੀ ਕਾਰ ਮੁੱਖ ਗੇਟ ਤੋਂ ਰਾਸ਼ਟਰਪਤੀ ਭਵਨ ਵਿੱਚ ਦਾਖਲ ਹੁੰਦੀ ਹੈ।", False),
]

failures = []
for lang, name, text, expect_fail in tests:
    res = score_segment(SRC, text, "eng", lang)
    ok = res["failed"] == expect_fail
    print(f"[{'PASS' if ok else 'FAIL'}] {lang}: {name} "
          f"(failed={res['failed']}, score={res['score']}, flags={res['flags']})")
    if not ok:
        failures.append(f"{lang}:{name}")

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED — both hin and pan gate correctly")
sys.exit(0)
