import json, subprocess, os, re

BASE = r"C:\dataset\-Karmayogi-Bharat\output\KB_COURSE_001"
CID = "KB_COURSE_001"
LANGS = ["hin","ben","tam","tel","kan","mal","mar","guj","pan","ory","asm",
         "urd","nep","mai","doi","bod","mni","sat","san","kok","snd","kas"]

MAX_SPEED = 1.35
GAP_GUARD = 0.040
EXTEND    = 0.300   # 300ms extension before trim

def wav_dur(path):
    try:
        out = subprocess.run(["ffprobe","-v","quiet","-show_entries",
            "format=duration","-of","csv=p=0", path],
            capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return None

def parse_srt(path):
    """Return list of (idx, start_s, end_s, nlines, nchars)."""
    txt = open(path, encoding="utf-8-sig").read()
    blocks = re.split(r"\n\s*\n", txt.strip())
    segs = []
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) < 2: continue
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m: continue
        h1,m1,s1,ms1,h2,m2,s2,ms2 = map(int, m.groups())
        start = h1*3600+m1*60+s1+ms1/1000
        end   = h2*3600+m2*60+s2+ms2/1000
        text = " ".join(lines[2:])
        segs.append((int(lines[0]), start, end, len(lines)-2, len(text)))
    return segs

print(f"{'lang':5} {'segs':5} {'sped>1.2':9} {'TRIMMED':8} {'big_gap':8} {'worst_ratio':12} {'verdict'}")
print("-"*80)

report = {}
for lang in LANGS:
    d = os.path.join(BASE, lang)
    srt = os.path.join(d, f"{CID}_{lang}.srt")
    segdir = os.path.join(d, "tmp", "tts_segments")
    if not os.path.exists(srt) or not os.path.isdir(segdir):
        print(f"{lang:5}  -- missing srt or tts_segments --")
        continue

    srt_segs = parse_srt(srt)
    # map available wav files by segment index
    wavs = {}
    for f in os.listdir(segdir):
        m = re.match(r"seg_(\d+)\.wav", f)
        if m:
            wavs[int(m.group(1))] = os.path.join(segdir, f)

    sped = trimmed = big_gap = 0
    worst = 0.0
    details = []
    n = len(srt_segs)
    for k, (idx, start, end, nl, nc) in enumerate(srt_segs):
        # SRT idx is 1-based sequential; tts seg files use original segment ids.
        # Align by order: kth srt block <-> kth available wav (sorted).
        pass

    # Better: align by sorted wav index order to sorted srt order
    wav_keys = sorted(wavs.keys())
    for k in range(min(len(wav_keys), n)):
        idx, start, end, nl, nc = srt_segs[k]
        wpath = wavs[wav_keys[k]]
        wd = wav_dur(wpath)
        if wd is None: continue
        slot = end - start
        # available room = to next segment start - guard (approx via next srt start)
        if k+1 < n:
            gap_avail = srt_segs[k+1][1] - start - GAP_GUARD
        else:
            gap_avail = slot + 60
        hard_limit = max(gap_avail, slot)
        # replicate pipeline decision
        if wd <= hard_limit:
            pass  # fits
        else:
            ratio = wd / hard_limit
            worst = max(worst, ratio)
            if ratio > 1.2:
                sped += 1
            after_speed = wd / min(ratio, MAX_SPEED)
            if after_speed > hard_limit + EXTEND:
                trimmed += 1
                details.append((k, round(wd,2), round(hard_limit,2), round(ratio,2)))
        # detect big internal silence: slot much larger than audio => dead air
        if slot - wd > 3.0:
            big_gap += 1

    verdict = "OK"
    if trimmed > 0: verdict = f"CUTOFF x{trimmed}"
    elif sped > 3: verdict = f"RUSHED x{sped}"
    elif big_gap > 5: verdict = f"GAPS x{big_gap}"

    report[lang] = dict(segs=len(wav_keys), sped=sped, trimmed=trimmed,
                        big_gap=big_gap, worst=round(worst,2),
                        verdict=verdict, details=details[:8])
    print(f"{lang:5} {len(wav_keys):<5} {sped:<9} {trimmed:<8} {big_gap:<8} "
          f"{worst:<12.2f} {verdict}")

json.dump(report, open(os.path.join(BASE,"_segment_defects.json"),"w"),
          indent=2, default=str)
print("\nSaved _segment_defects.json")
