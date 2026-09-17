import json, os, sys, subprocess, re
sys.path.insert(0, r"C:\dataset\-Karmayogi-Bharat")

BASE = r"C:\dataset\-Karmayogi-Bharat\output\KB_COURSE_001\hin"
meta = json.load(open(os.path.join(BASE,"KB_COURSE_001_hin_metadata.json"), encoding="utf-8"))
segs_meta = meta["ocr_sync"]["segments"]   # ordered id+start
segdir = os.path.join(BASE, "tmp", "tts_segments")

def wav_dur(p):
    o = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration",
        "-of","csv=p=0",p],capture_output=True,text=True).stdout.strip()
    return float(o) if o else 0.0

# wav index NNNN -> metadata position NNNN-1
wavs = {}
for f in os.listdir(segdir):
    m = re.match(r"seg_(\d+)\.wav", f)
    if m: wavs[int(m.group(1))-1] = os.path.join(segdir, f)

GAP_GUARD = 0.040
MAX_SPEED = 1.35
cursor = 0.0
print(f"{'pos':>3} {'orig_start':>10} {'placed':>8} {'audio_s':>8} {'slot_s':>7} {'gap_before':>10}")
total_gap = 0.0
prev_end = 0.0
n = len(segs_meta)
for pos in range(n):
    if pos not in wavs:
        continue
    start = segs_meta[pos]["start"]
    nxt = segs_meta[pos+1]["start"] if pos+1 < n else start+999
    slot = max(nxt - start, 0.1)
    wd = wav_dur(wavs[pos])
    # replicate new logic: speedup if audio>slot
    placed_len = wd
    if wd > slot:
        ratio = min(wd/slot, MAX_SPEED)
        placed_len = wd / ratio
    placed_start = max(start, cursor)
    gap_before = placed_start - prev_end
    if gap_before > 0: total_gap += gap_before
    print(f"{pos:>3} {start:>10.2f} {placed_start:>8.2f} {wd:>8.2f} {slot:>7.2f} {gap_before:>10.2f}")
    prev_end = placed_start + placed_len
    cursor = prev_end + GAP_GUARD

print(f"\nTotal inter-segment gap (silence): {total_gap:.1f}s  final_end={prev_end:.1f}s")
