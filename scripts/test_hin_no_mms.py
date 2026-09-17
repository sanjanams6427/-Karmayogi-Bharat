"""
Verify the 'Parler-only for Hindi' policy: when Parler fails, Hindi must NOT
call any MMS engine — it writes silence instead. A non-Parler-only lang (e.g.
tam) must still use MMS. Uses monkeypatching so NO real models load.

Run:  venv\\Scripts\\python.exe scripts\\test_hin_no_mms.py
"""
import sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline import tts as tts_mod
from pipeline.tts import TTSEngine

SR = tts_mod.SR
failures = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        failures.append(name)

calls = {"mms_vits": 0, "mms_batch": 0, "silence": 0}

eng = TTSEngine()

# Force all Parler paths to FAIL so we exercise the fallback branch.
eng._synthesize_parler = lambda *a, **k: False

# Record any MMS usage.
def _fake_vits(text, lang, output_path, force_cpu=False):
    calls["mms_vits"] += 1
    sf.write(output_path, np.zeros(SR, dtype=np.float32), SR)  # pretend success
    return True
def _fake_mms_batch(texts, lang, paths):
    calls["mms_batch"] += 1
    for p in paths:
        sf.write(p, np.zeros(SR, dtype=np.float32), SR)
    return [True] * len(texts)
def _fake_silence(dur, output_path):
    calls["silence"] += 1
    sf.write(output_path, np.zeros(int(max(0.1, dur) * SR), dtype=np.float32), SR)

eng._synthesize_standalone_vits = _fake_vits
eng._synthesize_mms_batch = _fake_mms_batch
eng._write_silence = _fake_silence

tmp = Path(tempfile.mkdtemp())

# ── Hindi: Parler fails → must NOT touch MMS, must write silence ──
calls.update(mms_vits=0, mms_batch=0, silence=0)
out_hin = str(tmp / "hin.wav")
eng.synthesize("यह एक हिंदी वाक्य है।", "hin", out_hin)
check("hin: MMS VITS never called", calls["mms_vits"] == 0, f"calls={calls['mms_vits']}")
check("hin: MMS batch never called", calls["mms_batch"] == 0, f"calls={calls['mms_batch']}")
check("hin: silence written instead", calls["silence"] >= 1)

# ── Tamil (not Parler-only): Parler skip/fail → MMS SHOULD be used ──
calls.update(mms_vits=0, mms_batch=0, silence=0)
out_tam = str(tmp / "tam.wav")
eng.synthesize("இது ஒரு தமிழ் வாக்கியம்.", "tam", out_tam)
check("tam: MMS still used (VITS or batch called)",
      calls["mms_vits"] + calls["mms_batch"] >= 1,
      f"vits={calls['mms_vits']} batch={calls['mms_batch']}")

# ── Policy sanity: hin is in the Parler-only set, tam is not ──
check("hin in _PARLER_ONLY_LANGS", "hin" in TTSEngine._PARLER_ONLY_LANGS)
check("tam not in _PARLER_ONLY_LANGS", "tam" not in TTSEngine._PARLER_ONLY_LANGS)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED — Hindi never falls back to MMS; other langs still do")
sys.exit(0)
