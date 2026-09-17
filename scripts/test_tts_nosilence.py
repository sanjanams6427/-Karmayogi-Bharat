"""
Lightweight logic tests for the TTS silence-prevention changes.
Does NOT load any TTS model — only checks the code contracts that guarantee
no full-slot silence and reliable long-segment splitting.

Run:  venv\\Scripts\\python.exe scripts\\test_tts_nosilence.py
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.tts import TTSEngine

failures = []


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        failures.append(name)


# 1. force_cpu fallback param exists on the VITS synthesiser
sig = inspect.signature(TTSEngine._synthesize_standalone_vits)
check("_synthesize_standalone_vits has force_cpu param", "force_cpu" in sig.parameters)
check("force_cpu defaults to False", sig.parameters["force_cpu"].default is False)

# 2. Long-split threshold lowered to prevent timeouts (was 45 → 30 → 22)
check("_PARLER_LONG_SPLIT_WORDS <= 22", TTSEngine._PARLER_LONG_SPLIT_WORDS <= 22)

# 3. The failed-idxs and skipped-lang fallback paths both call force_cpu retry
src = inspect.getsource(TTSEngine.synthesize_segments)
check("synthesize_segments has force_cpu=True last-resort retry (non-Parler-only langs)",
      src.count("force_cpu=True") >= 2)

# 4. Parler-only langs (Hindi) retry Parler and do NOT use MMS in the fallback.
#    The branch must reference _PARLER_ONLY_LANGS and retry via Parler helpers.
check("fallback branches on _PARLER_ONLY_LANGS",
      "_PARLER_ONLY_LANGS" in src)
check("Parler-only branch retries Parler (split/single), not MMS",
      "_synthesize_long_segment" in src and "_parler_generate_single" in src)

# 5. The non-Parler-only path still guards silence with a force_cpu retry
#    (force_cpu appears before that path's _write_silence). We check the LAST
#    force_cpu occurrence precedes the LAST tts_silent_failure (the non-Parler
#    branch is emitted after the Parler-only branch in the source).
last_force = src.rfind("force_cpu=True")
last_silent = src.rfind("tts_silent_failure")
check("force_cpu retry still guards silence in the MMS-eligible path",
      last_force != -1 and last_force < last_silent)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED")
sys.exit(0)
