"""
Verify XTTS-v2 routing:
 - When Coqui TTS / model absent: xtts_available()==False and _try_xtts()==False
   (so Parler is used — nothing breaks).
 - When XTTS is simulated-available: Hindi routes to XTTS first; a non-routed
   lang (tam) does NOT route to XTTS.

No real XTTS model loads — we monkeypatch availability + engine.

Run:  venv\\Scripts\\python.exe scripts\\test_xtts_routing.py
"""
import sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline import xtts_engine as xe
from pipeline.tts import TTSEngine, SR

failures = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        failures.append(name)

tmp = Path(tempfile.mkdtemp())

# 1. Current real state: TTS lib not installed → unavailable, graceful.
check("xtts_available() False when lib/model absent", xe.xtts_available() is False)

eng = TTSEngine()
out = str(tmp / "a.wav")
check("_try_xtts returns False when unavailable (Parler will be used)",
      eng._try_xtts("नमस्ते", "hin", out) is False)

# 2. Simulate XTTS available + a fake engine, verify Hindi routes to it.
orig_avail = xe.xtts_available
xe.xtts_available = lambda: True

class FakeXTTS:
    def __init__(self, *a, **k): self.calls = []
    def synthesize(self, text, lang, output_path):
        self.calls.append((text, lang))
        sf.write(output_path, np.zeros(SR, dtype=np.float32), SR)
        return True

fake = FakeXTTS()
eng2 = TTSEngine()
eng2._xtts_engine = fake  # inject
# Also patch the module-level engine class path used by _try_xtts's fresh build
xe.XTTSEngine = lambda *a, **k: fake

out_hin = str(tmp / "hin.wav")
routed_hin = eng2._try_xtts("यह हिंदी है।", "hin", out_hin)
check("hin routes to XTTS when available", routed_hin is True)
check("XTTS received the Hindi segment", any(l == "hin" for _, l in fake.calls))

# tam is not in XTTS_LANGS → must NOT route to XTTS
out_tam = str(tmp / "tam.wav")
routed_tam = eng2._try_xtts("தமிழ்", "tam", out_tam)
check("tam does NOT route to XTTS", routed_tam is False)

# restore
xe.xtts_available = orig_avail

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED — XTTS routes Hindi when available; falls back cleanly when not")
sys.exit(0)
