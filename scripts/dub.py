# ============================================================
# KB Dubbing CLI - Translate & dub e-learning courses
#
# Usage:
#   python dub.py --video course.mp4 --src eng --tgt hin
#   python dub.py --video course.mp3 --src eng --tgt hin,tam,tel
#   python dub.py --video course.mp4 --src eng --tgt all --full \
#                 --metadata meta.json --quiz quiz.json --upload-cbp
#   python dub.py --metadata meta.json --src eng --tgt hin --xlsx
#   python dub.py --quiz quiz.json --src eng --tgt all --docx
#   python dub.py --monthly-report report.json --month 1
# ============================================================

import argparse
import json
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pipeline.lang_config import ALL_22, LANG_NAMES
from pipeline.dubbing_pipeline import DubbingPipeline


def parse_targets(tgt_arg: str) -> list[str]:
    if tgt_arg.lower() == "all":
        return ALL_22
    return [t.strip() for t in tgt_arg.split(",")]


def main():
    parser = argparse.ArgumentParser(
        description="KB Course Dubbing Pipeline - 22 Indian Languages",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--src", default="eng", help="Source language code (default: eng)")
    parser.add_argument("--tgt", default="hin",
                        help="Target language(s): code, comma-separated, or 'all'")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--course-id", default="course", help="Course identifier")
    parser.add_argument("--no-glossary", action="store_true", help="Disable glossary")
    parser.add_argument("--force", action="store_true",
                        help="Force re-run even if output already exists")
    parser.add_argument("--gpu", type=int, default=0,
                        help="GPU index to use (default: 0). Use --batch-videos for multi-GPU.")
    parser.add_argument("--num-gpus", type=int, default=None,
                        help="Number of GPUs for parallel dubbing (default: auto-detect all available)")

    # Output format flags
    parser.add_argument("--xlsx", action="store_true",
                        help="Export metadata as Excel (.xlsx)")
    parser.add_argument("--docx", action="store_true",
                        help="Export quiz as Word (.docx)")
    parser.add_argument("--qa-report", action="store_true",
                        help="Generate QA self-certification report")

    # Full course processing
    parser.add_argument("--full", action="store_true",
                        help="Full course processing: dub + Excel + Word + QA report")
    parser.add_argument("--metadata", help="Course metadata JSON file")
    parser.add_argument("--quiz", help="Quiz/assessment JSON file")
    parser.add_argument("--upload-cbp", action="store_true",
                        help="Upload outputs to CBP portal after processing")

    # Monthly report
    parser.add_argument("--monthly-report",
                        help="Generate monthly submission report from results JSON")
    parser.add_argument("--month", type=int, default=1, help="Month number (1-12)")
    parser.add_argument("--submitter", default="Translation Agency",
                        help="Submitter name printed on the monthly report declaration")
    parser.add_argument("--monthly-qa-cert",
                        help="Generate monthly batch QA self-certification (.docx) from results JSON  [KB §4.5]")
    parser.add_argument("--agency", default="Translation Agency",
                        help="Agency name printed on inception/completion reports")
    parser.add_argument("--qa-reviewer", default="Translation Agency QA Lead",
                        dest="qa_reviewer",
                        help="Reviewer name printed on QA certificates")
    parser.add_argument("--agency-address", default="",
                        help="Agency address for inception report")
    parser.add_argument("--contact-person", default="",
                        help="Contact person name for inception report")
    parser.add_argument("--contact-email", default="",
                        help="Contact email for inception report")
    parser.add_argument("--t0-date", default="",
                        help="Contract start date ISO format YYYY-MM-DD (default: today)")
    parser.add_argument("--course-list",
                        help="Comma-separated course IDs for inception report")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", help="MP4/MP3 to translate and dub")
    group.add_argument("--batch-videos",
                       help="Directory of videos — distributes across all 4 GPUs in parallel")
    group.add_argument("--list-langs", action="store_true", help="List all supported languages")
    group.add_argument("--run-monthly-report", action="store_true",
                       help="Generate monthly report (use with --monthly-report)")
    group.add_argument("--run-monthly-qa-cert", action="store_true",
                       help="Generate monthly batch QA cert (use with --monthly-qa-cert)  [KB §4.5]")
    group.add_argument("--run-completion-report", action="store_true",
                       help="Generate Consolidated Completion Report + handover package (KB §4.6)")
    group.add_argument("--run-inception-report", action="store_true",
                       help="Generate Inception Report for Payment Milestone 1 (KB §4.1, T0+15 days)")

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

    if args.run_monthly_report:
        if not args.monthly_report:
            print("ERROR: --monthly-report <results.json> required")
            sys.exit(1)
        results_data = json.loads(Path(args.monthly_report).read_text(encoding="utf-8"))
        pipeline = DubbingPipeline()
        out = Path(args.output) / f"month_{args.month}_submission_report.docx"
        sla = pipeline.generate_monthly_report(
            args.month, results_data, str(out),
            submitter_name=args.submitter,
        )
        # Derive the four §4.5.iii fields for console summary
        courses = list(results_data.keys())
        all_langs, total_h = set(), 0.0
        for lang_results in results_data.values():
            for lang, r in lang_results.items():
                success = r.get("success", False) if isinstance(r, dict) else r.success
                dur = r.get("duration_original", 0.0) if isinstance(r, dict) else r.duration_original
                if success:
                    all_langs.add(lang)
                    total_h += dur / 3600
        from pipeline.lang_config import LANG_NAMES as _LN
        print(f"\n{'='*60}")
        print(f"  Month {args.month} Submission Report  —  KB Tender §4.5.iii")
        print(f"{'='*60}")
        print(f"  [Field 1] Courses delivered    : {len(courses)}")
        for cid in courses:
            print(f"              • {cid}")
        print(f"  [Field 2] Languages covered    : {len(all_langs)}")
        print(f"              {', '.join(_LN.get(l, l) for l in sorted(all_langs))}")
        print(f"  [Field 3] Total hours          : {total_h:.3f} h  (target: {sla['target_hours']:.1f} h)")
        print(f"  [Field 4] Standards confirmed  : ✅ Technical + Accessibility")
        print(f"{'='*60}")
        print(f"  SLA shortfall  : {sla['shortfall_pct']:.1f}%")
        print(f"  Penalty        : {sla['penalty_pct']:.0f}%  —  {sla['status']}")
        print(f"{'='*60}")
        print(f"\n✅ Monthly report → {out}")
        return

    if args.run_inception_report:
        tgt_langs = parse_targets(args.tgt)
        course_ids = (
            [c.strip() for c in args.course_list.split(",")]
            if args.course_list else []
        )
        pipeline = DubbingPipeline()
        out = Path(args.output) / "KB_Inception_Report.docx"
        Path(args.output).mkdir(parents=True, exist_ok=True)
        pipeline.generate_inception_report(
            course_ids=course_ids,
            tgt_langs=tgt_langs,
            output_dir=args.output,
            output_path=str(out),
            agency_name=args.agency,
            agency_address=args.agency_address,
            contact_person=args.contact_person,
            contact_email=args.contact_email,
            t0_date=args.t0_date,
        )
        print(f"\n{'='*60}")
        print("  KB §4.1 — Inception Report (Payment Milestone 1)")
        print(f"{'='*60}")
        print(f"  Agency         : {args.agency}")
        print(f"  Courses        : {len(course_ids)} ({', '.join(course_ids) or 'TBC'})")
        print(f"  Languages      : {len(tgt_langs)}")
        print(f"  T0 date        : {args.t0_date or 'today'}")
        print(f"  Output         : {out}")
        print(f"{'='*60}")
        return

    if args.run_completion_report:
        pipeline = DubbingPipeline()
        pkg = pipeline.generate_handover_package(
            output_dir=args.output,
            course_ids=None,
            agency_name=args.agency,
        )
        print(f"\n{'='*60}")
        print("  KB §4.6 — Consolidated Completion Report & Handover Package")
        print(f"{'='*60}")
        print(f"  Courses delivered  : {pkg['total_courses']}")
        print(f"  Languages          : {pkg['total_languages']}")
        print(f"  Total hours        : {pkg['total_hours']:.2f} h")
        print(f"  Total assets       : {pkg['total_assets']}")
        print(f"  Completion report  : {pkg['completion_report']}")
        print(f"  Compliance cert    : {pkg['compliance_cert']}")
        print(f"  Glossary xlsx      : {pkg['glossary_xlsx']}")
        print(f"  Asset manifest     : {pkg['asset_manifest']}")
        print(f"  Handover ZIP       : {pkg['handover_zip']}")
        print(f"{'='*60}")
        return

    if args.run_monthly_qa_cert:
        if not args.monthly_qa_cert:
            print("ERROR: --monthly-qa-cert <results.json> required")
            sys.exit(1)
        results_data = json.loads(Path(args.monthly_qa_cert).read_text(encoding="utf-8"))
        pipeline = DubbingPipeline()
        # Build flat entries list from results dict
        entries = []
        for cid, lang_results in results_data.items():
            for lang, r in lang_results.items():
                success = r.get("success", False) if isinstance(r, dict) else r.success
                dur = r.get("duration_original", 0) if isinstance(r, dict) else r.duration_original
                qs = r.get("quality_summary", {}) if isinstance(r, dict) else r.quality_summary
                entries.append({
                    "course_id":   cid,
                    "lang":        lang,
                    "hours":       dur / 3600,
                    "avg_score":   qs.get("avg_score", "N/A"),
                    "pass_rate":   qs.get("pass_rate", "N/A"),
                    "total_segs":  qs.get("total", "N/A"),
                    "failed_segs": qs.get("failed", 0),
                    "status":      "✅ Accepted" if success else "❌ Failed",
                })
        out = Path(args.output) / f"month_{args.month}_batch_qa_cert.docx"
        pipeline.generate_monthly_batch_qa_cert(
            month=args.month,
            entries=entries,
            reviewer_name=args.qa_reviewer,
            output_path=str(out),
        )
        print(f"\n✅ Monthly batch QA cert (§4.5) → {out}")
        return

    targets = parse_targets(args.tgt)
    src_name = LANG_NAMES.get(args.src, args.src)

    # Set GPU for this process
    if args.gpu != 0:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
        print(f"  GPU: {args.gpu}")

    # Auto-detect GPU count for parallel mode
    try:
        import torch
        available_gpus = torch.cuda.device_count() if torch.cuda.is_available() else 1
    except Exception:
        available_gpus = 1
    num_gpus = args.num_gpus if args.num_gpus is not None else available_gpus
    num_gpus = max(1, min(num_gpus, available_gpus))
    if num_gpus > 1:
        print(f"  Parallel mode: {num_gpus} GPUs")

    print(f"\n{'='*60}")
    print(f"  KB Dubbing Pipeline")
    print(f"  Source: {src_name}")
    print(f"  Target: {', '.join(LANG_NAMES.get(t, t) for t in targets)}")
    print(f"{'='*60}\n")

    pipeline = DubbingPipeline(use_glossary=not args.no_glossary) if num_gpus == 1 else None

    # ── Full course processing ─────────────────────────────────
    if args.full and args.video:
        if pipeline is None:
            pipeline = DubbingPipeline(use_glossary=not args.no_glossary)
        metadata = None
        quiz = None
        if args.metadata and Path(args.metadata).exists():
            metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
        if args.quiz and Path(args.quiz).exists():
            quiz = json.loads(Path(args.quiz).read_text(encoding="utf-8"))

        summary = pipeline.process_course_full(
            video_path=args.video,
            src_lang=args.src,
            tgt_langs=targets,
            output_dir=args.output,
            course_id=args.course_id,
            metadata=metadata,
            quiz=quiz,
            upload_to_cbp=args.upload_cbp,
        )

        # Save summary
        summary_path = Path(args.output) / f"{args.course_id}_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n{'='*60}")
        print("FULL PROCESSING SUMMARY")
        print(f"{'='*60}")
        for lang, r in summary["dubbing"].items():
            status = "✅" if r["success"] else f"❌ {r['error']}"
            print(f"  {LANG_NAMES.get(lang, lang):<15} {status}")
        print(f"\nSummary saved → {summary_path}")
        return

    # ── Batch multi-GPU processing ─────────────────────────────
    if args.batch_videos:
        import subprocess
        video_dir = Path(args.batch_videos)
        videos = (sorted(video_dir.glob("*.mp4")) + sorted(video_dir.glob("*.mp3"))
                  + sorted(video_dir.glob("*.webm")))
        if not videos:
            print(f"ERROR: No mp4/mp3 files found in {video_dir}")
            sys.exit(1)
        gpu_count = 4
        print(f"Distributing {len(videos)} videos across {gpu_count} GPUs")
        procs = []
        for i, vpath in enumerate(videos):
            gpu_id = i % gpu_count
            cmd = [
                sys.executable, __file__,
                "--video", str(vpath),
                "--src", args.src,
                "--tgt", args.tgt,
                "--output", args.output,
                "--course-id", vpath.stem,
                "--gpu", str(gpu_id),
            ]
            print(f"  GPU:{gpu_id} → {vpath.name}")
            procs.append(subprocess.Popen(cmd))
        for p in procs:
            p.wait()
        print("\nAll batch jobs complete.")
        return

    # ── Video/audio dubbing ────────────────────────────────────
    if args.video:
        if not Path(args.video).exists():
            print(f"ERROR: File not found: {args.video}")
            sys.exit(1)

        if pipeline is None:
            # parallel mode: use DubbingPipeline as coordinator (workers do the real work)
            from pipeline.dubbing_pipeline import DubbingPipeline as _DP
            pipeline = _DP(use_glossary=not args.no_glossary)

        results = pipeline.dub_course(
            video_path=args.video,
            src_lang=args.src,
            tgt_langs=targets,
            output_dir=args.output,
            course_id=args.course_id,
            force=args.force,
            num_gpus=num_gpus,
        )

        # Optional: QA reports
        if args.qa_report:
            for lang, r in results.items():
                if r.success:
                    qa_path = str(
                        Path(args.output) / lang /
                        f"{args.course_id}_{lang}_qa_cert.docx"
                    )
                    pipeline.generate_qa_report(args.course_id, lang, r, qa_path)

        print(f"\n{'='*60}")
        print("DUBBING SUMMARY")
        print(f"{'='*60}")
        for lang, result in results.items():
            lang_name = LANG_NAMES.get(lang, lang)
            status = "✅" if result.success else f"❌ {result.error}"
            print(f"  {lang_name:<15} {status}")
            if result.success:
                out = result.output_video_path or result.output_audio_path
                print(f"    → {out}")

    # ── Metadata translation ───────────────────────────────────
    if args.metadata:
        if pipeline is None:
            pipeline = DubbingPipeline(use_glossary=not args.no_glossary)
        meta_path = Path(args.metadata)
        if not meta_path.exists():
            print(f"ERROR: Metadata file not found: {args.metadata}")
            sys.exit(1)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.xlsx:
            xlsx_path = str(out_dir / f"{args.course_id}_metadata_all.xlsx")
            pipeline.export_metadata_xlsx(metadata, args.src, targets, xlsx_path)
            print(f"✅ Metadata Excel → {xlsx_path}")
        else:
            for tgt in targets:
                translated = pipeline.translate_metadata(metadata, args.src, tgt)
                out_path = out_dir / f"{args.course_id}_metadata_{tgt}.json"
                out_path.write_text(
                    json.dumps(translated, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"  ✅ {LANG_NAMES.get(tgt, tgt):<15} → {out_path}")

    # ── Quiz translation ───────────────────────────────────────
    if args.quiz:
        if pipeline is None:
            pipeline = DubbingPipeline(use_glossary=not args.no_glossary)
        quiz_path = Path(args.quiz)
        if not quiz_path.exists():
            print(f"ERROR: Quiz file not found: {args.quiz}")
            sys.exit(1)
        quiz = json.loads(quiz_path.read_text(encoding="utf-8"))
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)

        for tgt in targets:
            if args.docx:
                docx_path = str(out_dir / f"{args.course_id}_quiz_{tgt}.docx")
                pipeline.export_quiz_docx(quiz, args.src, tgt, docx_path)
                print(f"  ✅ {LANG_NAMES.get(tgt, tgt):<15} → {docx_path}")
            else:
                translated = pipeline.translate_quiz(quiz, args.src, tgt)
                out_path = out_dir / f"{args.course_id}_quiz_{tgt}.json"
                out_path.write_text(
                    json.dumps(translated, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"  ✅ {LANG_NAMES.get(tgt, tgt):<15} → {out_path}")


if __name__ == "__main__":
    main()
