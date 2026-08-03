"""
Clean all existing dubbed outputs + stale checkpoints, then re-run all 22 languages.
Uses fine-tuned IndicTrans2 checkpoint automatically (translator.py now prefers it).
"""
import sys, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

OUTPUT_BASE = pathlib.Path(__file__).parent.parent / "output"
CKPT_DIR    = pathlib.Path(__file__).parent.parent / "checkpoints" / "jobs"
VIDEO       = None   # auto-detect below

# ── 1. Find source video ──────────────────────────────────────────────────────
candidates = list(OUTPUT_BASE.parent.rglob("*.mp4")) + list(OUTPUT_BASE.parent.rglob("*.mp3"))
# exclude output dir itself
candidates = [f for f in candidates if "output" not in str(f) and "tmp" not in str(f)]
if not candidates:
    print("ERROR: No source video found. Pass VIDEO path manually.")
    sys.exit(1)
VIDEO = candidates[0]
print(f"Source video: {VIDEO}")

# ── 2. Delete all stale job checkpoints ──────────────────────────────────────
deleted_ckpt = 0
if CKPT_DIR.exists():
    for f in CKPT_DIR.glob("*.json"):
        f.unlink()
        deleted_ckpt += 1
print(f"Deleted {deleted_ckpt} stale job checkpoints")

# ── 3. Delete all existing dubbed outputs (mp4/mp3/srt/vtt/json) ─────────────
EXTS = {".mp4", ".mp3", ".srt", ".vtt", ".json"}
deleted_out = 0
course_dir = OUTPUT_BASE / VIDEO.stem
if course_dir.exists():
    for f in course_dir.rglob("*"):
        if f.is_file() and f.suffix in EXTS and "tmp" not in str(f):
            f.unlink()
            deleted_out += 1
# also clean flat output dir
for f in OUTPUT_BASE.glob(f"{VIDEO.stem}_*"):
    if f.is_file() and f.suffix in EXTS:
        f.unlink()
        deleted_out += 1
print(f"Deleted {deleted_out} old output files")

# ── 4. Run pipeline for all 22 languages ─────────────────────────────────────
from pipeline.dubbing_pipeline import DubbingPipeline
from pipeline.lang_config import ALL_22, LANG_NAMES

pipeline = DubbingPipeline(use_glossary=True)
results  = pipeline.dub_course(
    video_path  = str(VIDEO),
    src_lang    = "eng",
    tgt_langs   = ALL_22,
    output_dir  = str(OUTPUT_BASE / VIDEO.stem),
    course_id   = VIDEO.stem,
    force       = True,
)

# ── 5. Summary ────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("ALL-22 DUBBING SUMMARY")
print(f"{'='*60}")
ok, fail = 0, 0
for lang, r in results.items():
    status = "OK" if r.success else f"FAIL: {r.error[:50]}"
    out    = pathlib.Path(r.output_video_path or r.output_audio_path or "").name
    q      = r.quality_summary.get("avg_score", "?")
    print(f"  {LANG_NAMES.get(lang,lang):<14} [{lang}]  {status}  q={q}  {out}")
    if r.success: ok += 1
    else:         fail += 1
print(f"\n  {ok}/22 succeeded, {fail} failed")
