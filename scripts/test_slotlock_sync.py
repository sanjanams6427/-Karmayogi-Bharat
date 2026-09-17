"""
Verify slot-locked sync in VideoProcessor.assemble_dubbed_audio:
 - every segment is anchored at its ORIGINAL start time (no drift)
 - a segment longer than its slot is compressed / clipped, not pushed forward
 - later segments do NOT drift even when an earlier one overruns

Uses synthetic sine-wave WAVs — no TTS/GPU models required.

Run:  venv\\Scripts\\python.exe scripts\\test_slotlock_sync.py
"""
import sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.video_processor import VideoProcessor

SR = 44100
failures = []


def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        failures.append(name)


def make_wav(path, dur_s):
    t = np.linspace(0, dur_s, int(dur_s * SR), endpoint=False)
    sf.write(path, (0.3 * np.sin(2 * np.pi * 150 * t)).astype(np.float32), SR)


tmp = Path(tempfile.mkdtemp())

# Segment 0: slot 0-5s, audio 4s (fits). Segment 1: slot 5-10s, audio 8s
# (overruns its 5s slot). Segment 2: slot 10-15s, audio 3s.
# In the OLD push-forward design, seg1's overrun would push seg2 later (drift).
# In slot-locked, seg2 MUST still start at 10s.
segs = []
for i, (start, end, dur) in enumerate([(0, 5, 4.0), (5, 10, 8.0), (10, 15, 3.0)]):
    ap = tmp / f"seg_{i}.wav"
    make_wav(ap, dur)
    segs.append({"id": i, "start": float(start), "end": float(end),
                 "audio_path": str(ap)})

vp = VideoProcessor()
out_wav = str(tmp / "assembled.wav")
vp.assemble_dubbed_audio(segs, original_duration=15.0, output_wav=out_wav, sample_rate=SR)

# Each segment's placed_start must equal its original start (within 1ms).
for i, seg in enumerate(segs):
    ps = seg.get("placed_start")
    expected = float(seg["start"])
    check(f"seg {i} anchored at original start ({expected}s)",
          ps is not None and abs(ps - expected) < 0.001,
          f"placed_start={ps}")

# seg2 must NOT have drifted past 10s despite seg1 overrun.
check("seg 2 did not drift (starts at 10s, not later)",
      abs(segs[2]["placed_start"] - 10.0) < 0.001,
      f"placed_start={segs[2]['placed_start']}")

# seg1 must not overlap seg2's start (no double voice).
check("seg 1 clipped so it does not overlap seg 2",
      segs[1]["placed_end"] <= 10.0 + 0.001,
      f"seg1 placed_end={segs[1]['placed_end']}")

# Output duration must match original (no timeline growth).
info = sf.info(out_wav)
check("output duration ~= original video duration (no growth)",
      abs(info.duration - 15.0) < 0.2, f"dur={info.duration:.2f}s")

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED")
sys.exit(0)
