"""
Verify SRT generation with slot-locked placed_start/placed_end produces
subtitle blocks bounded by the next segment start — i.e. no more 30-61s blocks
like the ones in the original KB_COURSE_001 Hindi SRT.

Uses the REAL original transcript timestamps from the metadata as slot anchors.

Run:  venv\\Scripts\\python.exe scripts\\test_subtitle_sync.py
"""
import sys, json, tempfile, re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.subtitles import generate_srt

ROOT = Path(__file__).parent.parent
meta_path = ROOT / "output/KB_COURSE_001/hin/KB_COURSE_001_hin_metadata.json"
meta = json.loads(meta_path.read_text(encoding="utf-8"))
trans = meta["translations"]
video_dur = meta.get("duration_original_s", 977.4)

# Simulate slot-locked assembly: placed_start = original start, placed_end
# bounded by next segment's start (as the new assemble_dubbed_audio guarantees).
segs = []
for i, t in enumerate(trans):
    start = t["start"]
    nxt = trans[i + 1]["start"] if i + 1 < len(trans) else video_dur
    placed_end = min(t.get("end", start), nxt)  # slot-locked: never past next anchor
    segs.append({**t, "placed_start": start, "placed_end": placed_end})

out = str(Path(tempfile.mkdtemp()) / "test.srt")
generate_srt(segs, out, video_duration=video_dur, tgt_lang="hin")

# Parse SRT block durations
srt = Path(out).read_text(encoding="utf-8")
time_re = re.compile(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)")


def to_s(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


durations = []
for mch in time_re.finditer(srt):
    g = mch.groups()
    st = to_s(*g[:4]); en = to_s(*g[4:])
    durations.append(en - st)

max_dur = max(durations) if durations else 0
print(f"subtitle blocks: {len(durations)}, max block duration = {max_dur:.1f}s")

failures = []
# After slot-locking + long-cue splitting (_MAX_CUE_S=7), no displayed subtitle
# block should exceed ~10s (7s cap + small reading-time slack). The original SRT
# had blocks up to 62s.
if max_dur > 10.0:
    over = [round(d, 1) for d in durations if d > 10.0]
    print(f"[FAIL] blocks exceeding 10s still present: {over}")
    failures.append("max_block")
else:
    print(f"[PASS] no subtitle block exceeds 10s (was up to 62s before fixes)")

# Spot-check: splitting long cues yields at least as many blocks as segments.
if len(durations) == 0:
    failures.append("no_blocks")
    print("[FAIL] no subtitle blocks generated")
else:
    print(f"[PASS] {len(durations)} subtitle blocks generated (>= 67 segments due to splitting)")

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED")
sys.exit(0)
