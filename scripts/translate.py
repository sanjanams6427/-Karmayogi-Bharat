# ============================================================
# KB Translation Pipeline - Main Entry Point
# Usage:
#   python translate.py --text "Hello" --src eng --tgt hin
#   python translate.py --audio speech.wav --src hin --tgt ben
#   python translate.py --batch input.txt --src eng --tgt all
#   python translate.py --batch input.txt --src eng --tgt hin,tam,tel
# ============================================================

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows console UTF-8 fix for Indic scripts
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from pipeline.lang_config import ALL_22, LANG_NAMES
from pipeline.translator import Translator
from pipeline.asr import ASREngine


def parse_targets(tgt_arg: str) -> list:
    if tgt_arg.lower() == "all":
        return ALL_22
    return [t.strip() for t in tgt_arg.split(",")]


def run_text(args, translator: Translator):
    targets = parse_targets(args.tgt)
    results = {}
    for tgt in targets:
        t0 = time.time()
        result = translator.translate(args.text, args.src, tgt)
        elapsed = time.time() - t0
        translated = result["text"]
        results[tgt] = {"lang": LANG_NAMES[tgt], "text": translated, "time_s": round(elapsed, 2)}
        print(f"  [{LANG_NAMES[tgt]:12s}] {translated}")
    return results


def run_audio(args, asr: ASREngine, translator: Translator):
    print(f"[ASR] Transcribing {args.audio} ({LANG_NAMES.get(args.src, args.src)})...")
    source_text = asr.transcribe_file(args.audio, args.src)
    print(f"[ASR] Transcript: {source_text}\n")

    targets = parse_targets(args.tgt)
    results = {"transcript": source_text, "translations": {}}
    for tgt in targets:
        translated = translator.translate(source_text, args.src, tgt)["text"]
        results["translations"][tgt] = {"lang": LANG_NAMES[tgt], "text": translated}
        print(f"  [{LANG_NAMES[tgt]:12s}] {translated}")
    return results


def run_batch(args, translator: Translator):
    """
    Input file: one sentence per line (or JSON array).
    Output: JSON file with all translations.
    """
    input_path = Path(args.batch)
    if not input_path.exists():
        print(f"ERROR: File not found: {args.batch}")
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8").strip()
    # Support JSON array or plain text (one line per sentence)
    if content.startswith("["):
        sentences = json.loads(content)
    else:
        sentences = [line.strip() for line in content.splitlines() if line.strip()]

    targets = parse_targets(args.tgt)
    print(f"[BATCH] {len(sentences)} sentences → {len(targets)} languages")

    output = []
    for i, sentence in enumerate(sentences, 1):
        row = {"id": i, "source": sentence, "translations": {}}
        for tgt in targets:
            try:
                row["translations"][tgt] = translator.translate(sentence, args.src, tgt)
            except Exception as e:
                row["translations"][tgt] = f"ERROR: {e}"
        output.append(row)
        print(f"  [{i}/{len(sentences)}] done")

    out_path = input_path.with_suffix(".translated.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[BATCH] Saved → {out_path}")
    return output


def run_course(args, translator: Translator):
    """
    Translate a full course JSON file.
    Expected format: {"title": "...", "sections": [{"heading": "...", "content": "..."}]}
    """
    course_path = Path(args.course)
    course = json.loads(course_path.read_text(encoding="utf-8"))
    targets = parse_targets(args.tgt)

    all_outputs = {}
    for tgt in targets:
        lang_name = LANG_NAMES[tgt]
        print(f"\n[COURSE] Translating to {lang_name}...")
        translated_course = {
            "language": lang_name,
            "lang_code": tgt,
            "title": translator.translate(course.get("title", ""), args.src, tgt)["text"],
            "sections": [],
        }
        for section in course.get("sections", []):
            translated_course["sections"].append({
                "heading": translator.translate(section.get("heading", ""), args.src, tgt)["text"],
                "content": translator.translate(section.get("content", ""), args.src, tgt)["text"],
            })
        all_outputs[tgt] = translated_course

        out_path = course_path.parent / f"{course_path.stem}_{tgt}.json"
        out_path.write_text(
            json.dumps(translated_course, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Saved → {out_path}")

    return all_outputs


def main():
    parser = argparse.ArgumentParser(
        description="KB Translation Pipeline - 22 Indian Languages",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--src", default="eng", help="Source language code (default: eng)")
    parser.add_argument("--tgt", default="hin",
                        help="Target language code, comma-separated, or 'all'")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text",   help="Translate a single text string")
    group.add_argument("--audio",  help="Transcribe audio file then translate")
    group.add_argument("--batch",  help="Translate a text file (one sentence per line)")
    group.add_argument("--course", help="Translate a course JSON file")
    group.add_argument("--list-langs", action="store_true", help="List all supported languages")

    args = parser.parse_args()

    if args.list_langs:
        print("\nSupported Languages:")
        print(f"  {'Code':<6} {'Name'}")
        print(f"  {'-'*20}")
        for code, name in LANG_NAMES.items():
            marker = " ★" if code in ALL_22 else ""
            print(f"  {code:<6} {name}{marker}")
        print("\n★ = one of the 22 KB tender languages")
        return

    translator = Translator()
    asr = ASREngine() if args.audio else None

    print(f"\n{'='*60}")
    print(f"  KB Translation Pipeline")
    print(f"  Source: {LANG_NAMES.get(args.src, args.src)}")
    tgt_list = parse_targets(args.tgt)
    print(f"  Target: {', '.join(LANG_NAMES.get(t, t) for t in tgt_list)}")
    print(f"{'='*60}\n")

    if args.text:
        run_text(args, translator)
    elif args.audio:
        run_audio(args, asr, translator)
    elif args.batch:
        run_batch(args, translator)
    elif args.course:
        run_course(args, translator)


if __name__ == "__main__":
    main()
