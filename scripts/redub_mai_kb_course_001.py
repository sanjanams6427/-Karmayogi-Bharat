"""
Re-dub KB_COURSE_001 Maithili using the existing ASR checkpoint.
The source video is not available, so we translate + TTS + assemble
directly from the checkpoint's 91 segments.
"""
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("PIPELINE_GPU", "0")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pathlib import Path
from pipeline.translator import Translator
from pipeline.tts import TTSEngine
from pipeline.video_processor import VideoProcessor
from pipeline.quality import review_summary
from pipeline.subtitles import generate_subtitles
from pipeline.lang_config import LANG_NAMES

COURSE_ID = "KB_COURSE_001"
TGT_LANG  = "mai"
CKPT_PATH = Path(ROOT) / "checkpoints" / "jobs" / "191fb0962631.json"
OUT_DIR   = Path(ROOT) / "output" / COURSE_ID / TGT_LANG

# Load ASR segments from checkpoint
ckpt = json.loads(CKPT_PATH.read_text(encoding="utf-8"))
segments = ckpt["meta"]["segments"]
duration = ckpt["meta"]["duration"]
print(f"Loaded {len(segments)} segments, duration={duration:.1f}s")

# Step 1: Translate all segments
print("\n[1/4] Translating to Maithili...")
t0 = time.time()
translator = Translator()
texts = [s["text"] for s in segments]
results = translator.translate_batch(texts, src_lang="eng", tgt_lang="mai")
print(f"  Done in {time.time()-t0:.1f}s")

translated_segments = []
for seg, res in zip(segments, results):
    translated_segments.append({
        **seg,
        "src_text": seg["text"],
        "text": res["text"],
        "engine": res["engine"],
        "enhanced": False,
        "quality": res["score"],
    })

scores = [r["score"] for r in results]
summary = review_summary(scores)
print(f"  avg_score={summary['avg_score']} pass_rate={summary['pass_rate']} "
      f"needs_review={summary['needs_review']}/{summary['total']}")

# Step 2: TTS
print("\n[2/4] Synthesising TTS...")
OUT_DIR.mkdir(parents=True, exist_ok=True)
tts_dir = str(OUT_DIR / "tmp" / "tts_segments")
tts = TTSEngine()
tts_segments = tts.synthesize_segments(translated_segments, TGT_LANG, tts_dir)
print(f"  TTS done: {len(tts_segments)} segments")

# Step 3: Assemble audio
print("\n[3/4] Assembling dubbed audio...")
video = VideoProcessor()
dubbed_wav = str(OUT_DIR / "tmp" / "dubbed.wav")
Path(dubbed_wav).parent.mkdir(parents=True, exist_ok=True)
video.assemble_dubbed_audio(tts_segments, duration, dubbed_wav)

# Step 4: Export MP3 + subtitles + metadata (no source video = audio-only output)
print("\n[4/4] Writing outputs...")
out_mp3 = str(OUT_DIR / f"{COURSE_ID}_{TGT_LANG}.mp3")
video.convert_audio(dubbed_wav, out_mp3)
print(f"  MP3 → {out_mp3}")

sub_paths = generate_subtitles(
    translated_segments, str(OUT_DIR), COURSE_ID, TGT_LANG,
    video_duration=duration)
print(f"  SRT → {sub_paths.get('srt')}")
print(f"  VTT → {sub_paths.get('vtt')}")

# Save metadata
import platform
meta = {
    "course_id": COURSE_ID,
    "source_lang": "eng",
    "target_lang": TGT_LANG,
    "target_lang_name": LANG_NAMES.get(TGT_LANG, TGT_LANG),
    "duration_original_s": duration,
    "duration_output_s": 0.0,
    "segment_count": len(segments),
    "quality_summary": summary,
    "transcript": segments,
    "translations": translated_segments,
    "provenance": {
        "host": platform.node(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "contract": "RFB IN-KBL-543730-NC-RFB",
        "note": "re-dubbed after regex fix — source video unavailable, audio-only output",
    },
}
meta_path = OUT_DIR / f"{COURSE_ID}_{TGT_LANG}_metadata.json"
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"  Metadata → {meta_path}")

print(f"\n✅ Done. avg_score={summary['avg_score']} pass_rate={summary['pass_rate']}")
