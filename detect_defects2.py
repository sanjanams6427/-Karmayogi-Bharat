import json, subprocess, os, re

BASE = r"C:\dataset\-Karmayogi-Bharat\output\KB_COURSE_001"
CID = "KB_COURSE_001"
LANGS = ["hin","ben","tam","tel","kan","mal","mar","guj","pan","ory","asm",
         "urd","nep","mai","doi","bod","mni","sat","san","kok","snd","kas"]

MAX_SPEED = 1.35
GAP_GUARD = 0.040
EXTEND    = 0.300

def wav_dur(path):
    try:
        out = subprocess.run(["ffprobe","-v","quiet","-show_entries",
            "format=duration","-of","csv=p=0", path],
            capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return None

print(f"{'lang':5} {'wavs':5} {'rushed':7} {'CUTOFF':7} {'worst_x':8} {'verdict'}")
print("-"*70)
report = {}
for lang in LANGS:
    d = os.path.join(BASE, lang)
    meta = os.path.join(d, f"{CID}_{lang}_metadata.json")
    segdir = os.path.join(d, "tmp", "tts_segments")
    if not os.path.isdir(segdir) or not os.path.exists(meta):
        print(f"{lang:5} -- no tts_segments (cleaned) --")
        continue
    m = json.load(open(meta, encoding="utf-8"))
    segs = m["ocr_sync"]["segments"]          # ordered, has id + start
    starts = [s["start"] for s in segs]
    n = len(segs)
    # wav index NNNN maps to metadata position (NNNN-1)
    wavs = {}
    for f in os.listdir(segdir):
        mm = re.match(r"seg_(\d+)\.wav", f)
        if mm: wavs[int(mm.group(1))-1] = os.path.join(segdir, f)

    rushed = cutoff = 0
    worst = 0.0
    details = []
    for pos in range(n):
        if pos not in wavs: continue
        wd = wav_dur(wavs[pos])
        if wd is None: continue
        start = starts[pos]
        nxt = starts[pos+1] if pos+1 < n else start + wd + 60
        gap_avail = nxt - start - GAP_GUARD
        slot = nxt - start   # slot to next speech
        hard_limit = max(gap_avail, slot)
        if wd > hard_limit:
            ratio = wd / hard_limit
            worst = max(worst, ratio)
            if ratio > 1.2: rushed += 1
            after = wd / min(ratio, MAX_SPEED)
            if after > hard_limit + EXTEND:
                cutoff += 1
                details.append(dict(pos=pos, id=segs[pos]["id"],
                    wav_s=round(wd,2), slot_s=round(hard_limit,2),
                    over_x=round(ratio,2)))
    verdict = f"CUTOFF x{cutoff}" if cutoff else (f"rushed x{rushed}" if rushed>2 else "OK")
    report[lang]=dict(wavs=len(wavs),rushed=rushed,cutoff=cutoff,
                      worst=round(worst,2),verdict=verdict,details=details)
    print(f"{lang:5} {len(wavs):<5} {rushed:<7} {cutoff:<7} {worst:<8.2f} {verdict}")

json.dump(report, open(os.path.join(BASE,"_segment_defects2.json"),"w"),
          indent=2, default=str)
print("\nSaved _segment_defects2.json")
