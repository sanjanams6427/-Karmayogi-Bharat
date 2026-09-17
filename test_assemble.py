import numpy as np, soundfile as sf, os, tempfile, sys
sys.path.insert(0, r"C:\dataset\-Karmayogi-Bharat")
from pipeline.video_processor import VideoProcessor

SR = 44100
tmp = tempfile.mkdtemp()

def mk(path, dur):
    n = int(dur*SR)
    # simple tone so it's not silent
    t = np.linspace(0, dur, n, endpoint=False)
    sf.write(path, (0.2*np.sin(2*np.pi*220*t)).astype(np.float32), SR)
    return path

# Segments: some fit, some massively overrun, and one that starts PAST the
# original duration+buffer (the crash trigger from the real run).
segs = [
    {"start": 0.0,  "end": 5.0,  "audio_path": mk(os.path.join(tmp,"a.wav"), 12.0)},  # 12s into 5s slot
    {"start": 5.0,  "end": 10.0, "audio_path": mk(os.path.join(tmp,"b.wav"), 3.0)},   # fits
    {"start": 10.0, "end": 12.0, "audio_path": mk(os.path.join(tmp,"c.wav"), 40.0)},  # 40s into 2s slot
    {"start": 60.0, "end": 62.0, "audio_path": mk(os.path.join(tmp,"d.wav"), 80.0)},  # huge overrun near end
]
original_duration = 62.0

vp = VideoProcessor.__new__(VideoProcessor)  # skip heavy __init__
out = os.path.join(tmp, "dubbed.wav")
try:
    vp.assemble_dubbed_audio(segs, original_duration, out)
    wav, sr = sf.read(out)
    total_dur = len(wav)/sr
    # Sum of input audio content should be preserved (no hard cutoff):
    # after 1.35x max speedup, min possible = sum(dur)/1.35
    in_dur = 12+3+40+80
    print(f"OK  output_dur={total_dur:.2f}s  input_speech={in_dur}s  "
          f"min_expected(after1.35x)={in_dur/1.35:.2f}s")
    # No crash = crash bug fixed. Output should be >= most of the speech.
    assert total_dur >= in_dur/1.35 - 2, "speech appears trimmed!"
    print("PASS: no crash, speech length preserved (no hard cutoff)")
except Exception as e:
    import traceback; traceback.print_exc()
    print("FAIL:", e)
