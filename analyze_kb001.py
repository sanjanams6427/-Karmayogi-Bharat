import json, subprocess, os, sys

BASE = r"C:\dataset\-Karmayogi-Bharat\output\KB_COURSE_001"
CID = "KB_COURSE_001"

LANGS = ["hin","ben","tam","tel","kan","mal","mar","guj","pan","ory","asm",
         "urd","nep","mai","doi","bod","mni","sat","san","kok","snd","kas"]

def ffprobe_json(path):
    try:
        out = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_format","-show_streams", path],
            capture_output=True, text=True, timeout=120)
        return json.loads(out.stdout)
    except Exception as e:
        return {"_error": str(e)}

def audio_stats(path):
    """Return mean/max volume via ffmpeg volumedetect + silence duration."""
    try:
        out = subprocess.run(
            ["ffmpeg","-i",path,"-af","volumedetect","-f","null","-"],
            capture_output=True, text=True, timeout=180)
        txt = out.stderr
        mean = maxv = None
        for line in txt.splitlines():
            if "mean_volume:" in line:
                mean = line.split("mean_volume:")[1].strip()
            if "max_volume:" in line:
                maxv = line.split("max_volume:")[1].strip()
        return mean, maxv
    except Exception as e:
        return None, f"err:{e}"

def silence_seconds(path):
    """Total seconds of silence (below -50dB, >0.5s runs)."""
    try:
        out = subprocess.run(
            ["ffmpeg","-i",path,"-af","silencedetect=noise=-50dB:d=0.5","-f","null","-"],
            capture_output=True, text=True, timeout=180)
        total = 0.0
        for line in out.stderr.splitlines():
            if "silence_duration:" in line:
                total += float(line.split("silence_duration:")[1].strip())
        return round(total,2)
    except Exception as e:
        return f"err:{e}"

rows = []
print(f"{'lang':5} {'mp4?':5} {'mp3?':5} {'v_dur':8} {'a_dur':8} {'mp3_dur':8} "
      f"{'mean_dB':9} {'max_dB':8} {'silence_s':9} {'segs':5} {'pass':5} {'review':6} {'safety':7}")
print("-"*110)

summary = {}
for lang in LANGS:
    d = os.path.join(BASE, lang)
    mp4 = os.path.join(d, f"{CID}_{lang}.mp4")
    mp3 = os.path.join(d, f"{CID}_{lang}.mp3")
    meta = os.path.join(d, f"{CID}_{lang}_metadata.json")

    row = {"lang": lang}
    row["mp4_exists"] = os.path.exists(mp4)
    row["mp3_exists"] = os.path.exists(mp3)

    v_dur = a_dur = mp3_dur = None
    has_audio_in_mp4 = False
    if row["mp4_exists"]:
        pj = ffprobe_json(mp4)
        for s in pj.get("streams", []):
            if s.get("codec_type")=="video" and v_dur is None:
                v_dur = float(s.get("duration") or pj.get("format",{}).get("duration") or 0)
            if s.get("codec_type")=="audio":
                has_audio_in_mp4 = True
                a_dur = float(s.get("duration") or pj.get("format",{}).get("duration") or 0)
    if row["mp3_exists"]:
        pj = ffprobe_json(mp3)
        mp3_dur = float(pj.get("format",{}).get("duration") or 0)

    mean_db, max_db = (audio_stats(mp3) if row["mp3_exists"] else (None,None))
    sil = silence_seconds(mp3) if row["mp3_exists"] else None

    segs = passr = review = safety = None
    if os.path.exists(meta):
        try:
            m = json.load(open(meta, encoding="utf-8"))
            qs = m.get("quality_summary",{})
            segs = m.get("segment_count")
            passr = qs.get("pass_rate")
            review = qs.get("needs_review")
            safety = qs.get("content_safety_pass")
        except Exception as e:
            segs = f"err:{e}"

    row.update(dict(v_dur=v_dur,a_dur=a_dur,mp3_dur=mp3_dur,mean_db=mean_db,
                    max_db=max_db,silence=sil,segs=segs,passr=passr,
                    review=review,safety=safety,has_audio_in_mp4=has_audio_in_mp4))
    summary[lang]=row

    def f(x,w=8):
        if x is None: return " "*w
        if isinstance(x,float): return f"{x:<{w}.2f}"
        return f"{str(x):<{w}}"
    print(f"{lang:5} {str(row['mp4_exists']):5} {str(row['mp3_exists']):5} "
          f"{f(v_dur)} {f(a_dur)} {f(mp3_dur)} {f(mean_db,9)} {f(max_db)} "
          f"{f(sil,9)} {f(segs,5)} {f(passr,5)} {f(review,6)} {f(safety,7)}")

json.dump(summary, open(os.path.join(BASE,"_analysis_summary.json"),"w"), indent=2, default=str)
print("\nSaved: _analysis_summary.json")
