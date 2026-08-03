import pathlib

base = pathlib.Path(__file__).parent.parent / "output"
ckpt = pathlib.Path(__file__).parent.parent / "checkpoints" / "jobs"

exts = {".mp4", ".mp3", ".srt", ".vtt", ".json"}
count = 0
for f in base.rglob("*"):
    if f.is_file() and f.suffix in exts and "tmp" not in str(f):
        f.unlink()
        count += 1

for f in ckpt.glob("*.json"):
    f.unlink()
    count += 1

print(f"Cleaned {count} files. Ready for fresh 22-lang run.")
