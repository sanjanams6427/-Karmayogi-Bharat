import numpy as np, soundfile as sf, os, tempfile, sys
sys.path.insert(0, r"C:\dataset\-Karmayogi-Bharat")
from pipeline.video_processor import VideoProcessor

SR = 44100
tmp = tempfile.mkdtemp()
def mk(path, dur):
    n=int(dur*SR); t=np.linspace(0,dur,n,endpoint=False)
    sf.write(path,(0.2*np.sin(2*np.pi*220*t)).astype(np.float32),SR); return path

# Segments with LARGE original gaps but SHORT audio -> should be gap-capped.
# seg0: 0-5 slot, 3s audio. seg1 original start 30 (25s gap!) but only 3s audio.
# seg2 original start 60 (huge gap) 3s audio.
segs=[
 {"id":0,"start":0.0,"end":5.0,"audio_path":mk(os.path.join(tmp,"a.wav"),3.0)},
 {"id":1,"start":30.0,"end":35.0,"audio_path":mk(os.path.join(tmp,"b.wav"),3.0)},
 {"id":2,"start":60.0,"end":62.0,"audio_path":mk(os.path.join(tmp,"c.wav"),20.0)},  # long overrun
]
vp=VideoProcessor.__new__(VideoProcessor)
out=os.path.join(tmp,"d.wav")
vp.assemble_dubbed_audio(segs, 62.0, out)
wav,sr=sf.read(out); total=len(wav)/sr
print(f"output_dur={total:.2f}s (orig timeline was 62s)")
for s in segs:
    print(f" seg {s['id']}: placed_start={s.get('placed_start'):.2f}s placed_end={s.get('placed_end'):.2f}s")
# Assertions:
# 1. placed timings written back
assert all(s.get("placed_start") is not None for s in segs), "placed timings missing"
# 2. gap between seg0 end and seg1 start capped near 0.7s (not 25s)
gap01 = segs[1]["placed_start"] - segs[0]["placed_end"]
print(f" gap seg0->seg1 = {gap01:.2f}s (should be <=0.75)")
assert gap01 <= 0.75, f"gap not capped: {gap01}"
gap12 = segs[2]["placed_start"] - segs[1]["placed_end"]
print(f" gap seg1->seg2 = {gap12:.2f}s (should be <=0.75)")
assert gap12 <= 0.75, f"gap not capped: {gap12}"
# 3. no speech lost: total >= sum(audio)/1.35
assert total >= (3+3+20)/1.35 - 1, "speech trimmed"
print("PASS: gaps capped, placed timings written, no speech lost")
