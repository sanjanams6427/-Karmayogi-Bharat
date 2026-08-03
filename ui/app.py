"""
KB Translation System — Enterprise UI
Run: python ui/app.py
"""

import sys, os, json, time, threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from pipeline.lang_config import LANG_NAMES, ALL_22

SRC_LANGS = [("English", "eng"), ("Hindi", "hin")] + [
    (LANG_NAMES[c], c) for c in ALL_22 if c not in ("hin",)
]
TGT_LANGS = [(LANG_NAMES[c], c) for c in ALL_22]
KB_11     = ["asm","ben","guj","hin","kan","mal","mar","ory","pan","tam","tel"]
OUTPUT_DIR     = str(Path(__file__).parent.parent / "output")
ENV_PATH       = Path(__file__).parent.parent / ".env"
SAVE_DIR_FILE  = Path(__file__).parent.parent / ".output_dir"  # persists user choice

# Ensure default output dir always exists
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def _get_output_dir() -> str:
    if SAVE_DIR_FILE.exists():
        d = SAVE_DIR_FILE.read_text(encoding="utf-8").strip()
        if d:
            Path(d).mkdir(parents=True, exist_ok=True)
            return d
    return OUTPUT_DIR


def _set_output_dir(path: str) -> str:
    p = Path(path.strip())
    try:
        p.mkdir(parents=True, exist_ok=True)
        SAVE_DIR_FILE.write_text(str(p), encoding="utf-8")
        return f"✅ Output folder set to: {p}"
    except Exception as e:
        return f"❌ {e}"

_pipeline = None
_pipeline_lock = threading.Lock()
_pipeline_ready = threading.Event()
_pipeline_error = ""
_log_lines: list[str] = []
_log_lock  = threading.Lock()


def _append_log(msg: str):
    with _log_lock:
        _log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if len(_log_lines) > 200:
            _log_lines.pop(0)


def _get_log() -> str:
    with _log_lock:
        return "\n".join(_log_lines[-60:])


def _load_pipeline_bg():
    global _pipeline, _pipeline_error
    try:
        _append_log("Loading pipeline models in background (may take 1-2 min)...")
        from pipeline.dubbing_pipeline import DubbingPipeline
        _pipeline = DubbingPipeline()
        _append_log("✅ Pipeline ready — you can now submit jobs.")
    except Exception as e:
        _pipeline_error = str(e)
        _append_log(f"❌ Pipeline load failed: {e}")
    finally:
        _pipeline_ready.set()


# Start loading immediately when app.py is imported
_bg_thread = threading.Thread(target=_load_pipeline_bg, daemon=True)
_bg_thread.start()


def get_pipeline():
    if not _pipeline_ready.wait(timeout=300):
        raise RuntimeError("Pipeline failed to load within 5 minutes")
    if _pipeline_error:
        raise RuntimeError(f"Pipeline load error: {_pipeline_error}")
    return _pipeline


# ── API Keys helpers ──────────────────────────────────────────
def _load_env() -> dict:
    keys = {"HF_TOKEN": ""}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                k = k.strip()
                if k in keys:
                    keys[k] = v.strip()
    return keys


def _save_env(hf: str) -> str:
    lines = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.split("=")[0].strip() != "HF_TOKEN":
                lines.append(line)
    if hf:
        lines.append(f"HF_TOKEN={hf}")
        os.environ["HF_TOKEN"] = hf
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    global _pipeline
    with _pipeline_lock:
        _pipeline = None
    return "✅ HF Token saved. Pipeline will reload on next job."


def _save_outputs(files: list[str]) -> list[str]:
    """Return valid output paths — pipeline already saves to output_dir, no copy needed."""
    saved = []
    for f in files:
        if not f or not f.strip():
            continue
        src = Path(f)
        if src.exists() and src.is_file():
            saved.append(str(src))
    return saved


# ── Tab 1: Dub Video ─────────────────────────────────────────
def dub_file(file, src_lang, tgt_langs, voice_clone, ref_audio,
             progress=gr.Progress()):
    if file is None:
        return None, None, "❌ Please upload a file.", ""
    if not tgt_langs:
        return None, None, "❌ Select at least one target language.", ""

    pipeline  = get_pipeline()
    course_id = Path(file.name).stem
    # Always save to persistent output dir — never inside Gradio's temp folder
    out_dir   = os.path.join(_get_output_dir(), course_id)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ref_path  = ref_audio.name if ref_audio else None

    _append_log(f"Starting dub: {Path(file.name).name} → {tgt_langs}")
    results = {}
    total = len(tgt_langs)
    for i, tgt in enumerate(tgt_langs):
        progress((i / total) + (0.9 / total), desc=f"Dubbing → {LANG_NAMES[tgt]}")
        _append_log(f"Processing {LANG_NAMES[tgt]}...")
        r = pipeline.dub_video(file.name, src_lang, tgt, out_dir, course_id,
                               voice_clone=voice_clone, reference_audio=ref_path)
        results[tgt] = r
        status = "✅" if r.success else "❌"
        _append_log(f"{status} {LANG_NAMES[tgt]} done in {r.elapsed_s}s")

    progress(0.95, desc="Saving outputs...")
    output_files, log_lines, quality_lines = [], [], []
    for tgt, r in results.items():
        lang = LANG_NAMES[tgt]
        if r.success:
            out = r.output_video_path or r.output_audio_path
            output_files.append(out)
            # Include SRT/VTT subtitles (KB Financial Schedule)
            sub_dir = Path(out_dir) / tgt
            for sub in list(sub_dir.glob("*.srt")) + list(sub_dir.glob("*.vtt")):
                output_files.append(str(sub))
            qs = r.quality_summary
            log_lines.append(f"✅ {lang} → {Path(out).name}  ({r.elapsed_s}s)")
            quality_lines.append(
                f"{lang}: score={qs.get('avg_score','?')} | chrf={qs.get('avg_chrf','?')} | "
                f"pass={qs.get('pass_rate','?')} | "
                f"review_needed={qs.get('needs_review','?')}/{qs.get('total','?')} segs")
        else:
            log_lines.append(f"❌ {lang} → {r.error}")
    saved = _save_outputs(output_files)
    progress(1.0, desc="✅ Done")
    return (saved[0] if saved else None,
            saved or None,
            "\n".join(log_lines),
            "\n".join(quality_lines) or "No quality data")


# ── Tab 2: Translate Document ─────────────────────────────────
def _chunk_text(text: str, max_chars: int = 400) -> list[str]:
    """Split long text into chunks that fit within model token limits."""
    words, chunk, chunks = text.split(), [], []
    for word in words:
        chunk.append(word)
        if len(" ".join(chunk)) >= max_chars:
            chunks.append(" ".join(chunk))
            chunk = []
    if chunk:
        chunks.append(" ".join(chunk))
    return chunks or [text]


def _translate_plain_doc(file_path: str, src_lang: str, tgt_langs: list,
                         out_dir: str, course_id: str,
                         progress, pipeline) -> tuple[list, list]:
    """Extract text from PDF/DOCX/TXT, translate, save per-language .docx."""
    from pipeline.doc_extractor import extract_text
    from docx import Document as DocxDocument

    try:
        text = extract_text(file_path)
    except Exception as e:
        return [], [f"❌ Could not extract text: {e}"]

    # Split into paragraphs, then chunk any that are too long
    raw_paras = [p.strip() for p in text.splitlines() if p.strip()]
    paragraphs = []
    for p in raw_paras:
        paragraphs.extend(_chunk_text(p) if len(p) > 400 else [p])

    output_files, log_lines = [], []

    for i, tgt in enumerate(tgt_langs):
        progress((i + 1) / len(tgt_langs), desc=f"Translating → {LANG_NAMES[tgt]}")
        try:
            # translate_batch returns list of dicts: {"text": ..., "engine": ..., "score": ...}
            results = pipeline.translator.translate_batch(paragraphs, src_lang, tgt)
            translated_paras = [r.get("text", paragraphs[j]) for j, r in enumerate(results)]
        except Exception as e:
            log_lines.append(f"❌ {LANG_NAMES[tgt]}: {e}")
            continue

        out_path = os.path.join(out_dir, f"{course_id}_{tgt}.docx")
        doc = DocxDocument()
        for para in translated_paras:
            doc.add_paragraph(para)
        doc.save(out_path)
        output_files.append(out_path)
        log_lines.append(f"✅ {LANG_NAMES[tgt]} → {Path(out_path).name}")

    return output_files, log_lines


def translate_doc(file, src_lang, tgt_langs, doc_type, course_title,
                  progress=gr.Progress()):
    if file is None:
        return None, "❌ Please upload a file."
    if not tgt_langs:
        return None, "❌ Select at least one target language."

    pipeline  = get_pipeline()
    course_id = Path(file.name).stem
    out_dir   = os.path.join(_get_output_dir(), course_id)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    suffix = Path(file.name).suffix.lower()

    # ── Plain document (PDF / DOCX / TXT) ──
    if suffix in (".pdf", ".docx", ".doc", ".txt"):
        output_files, log_lines = _translate_plain_doc(
            file.name, src_lang, tgt_langs, out_dir, course_id, progress, pipeline)
        return _save_outputs(output_files) or None, "\n".join(log_lines)

    # ── JSON paths (existing behaviour) ──
    output_files, log_lines = [], []

    if doc_type == "Quiz (Word .docx)":
        try:
            quiz = json.loads(Path(file.name).read_text(encoding="utf-8"))
        except Exception as e:
            return None, f"❌ Could not parse quiz JSON: {e}"
        for i, tgt in enumerate(tgt_langs):
            progress((i+1)/len(tgt_langs), desc=f"Quiz → {LANG_NAMES[tgt]}")
            out_path = os.path.join(out_dir, f"{course_id}_quiz_{tgt}.docx")
            try:
                pipeline.export_quiz_docx(quiz, src_lang, tgt, out_path, course_title)
                output_files.append(out_path)
                log_lines.append(f"✅ {LANG_NAMES[tgt]} quiz → {Path(out_path).name}")
            except Exception as e:
                log_lines.append(f"❌ {LANG_NAMES[tgt]}: {e}")
    else:
        try:
            metadata = json.loads(Path(file.name).read_text(encoding="utf-8"))
        except Exception as e:
            return None, f"❌ Could not parse metadata JSON: {e}"
        out_path = os.path.join(out_dir, f"{course_id}_metadata.xlsx")
        try:
            pipeline.export_metadata_xlsx(metadata, src_lang, tgt_langs, out_path)
            output_files.append(out_path)
            log_lines.append(f"✅ Metadata Excel → {Path(out_path).name}")
        except Exception as e:
            log_lines.append(f"❌ {e}")

    return _save_outputs(output_files) or None, "\n".join(log_lines)


# ── Tab 3: Full Course Batch ──────────────────────────────────
def process_course(video_file, meta_file, quiz_file, src_lang, tgt_langs,
                   course_id, voice_clone, upload_cbp, progress=gr.Progress()):
    if video_file is None:
        return None, "❌ Please upload a video/audio file."
    if not tgt_langs:
        return None, "❌ Select at least one target language."

    pipeline = get_pipeline()
    cid      = course_id or Path(video_file.name).stem
    out_dir  = os.path.join(_get_output_dir(), cid)

    metadata = None
    if meta_file:
        try:
            metadata = json.loads(Path(meta_file.name).read_text(encoding="utf-8"))
        except Exception:
            pass

    quiz = None
    if quiz_file:
        try:
            quiz = json.loads(Path(quiz_file.name).read_text(encoding="utf-8"))
        except Exception:
            pass

    progress(0.1, desc="Starting pipeline...")
    _append_log(f"Full course batch: {cid} → {tgt_langs}")
    summary = pipeline.process_course_full(
        video_file.name, src_lang, tgt_langs, out_dir, cid,
        metadata=metadata, quiz=quiz,
        voice_clone=voice_clone, upload_to_cbp=upload_cbp,
    )

    all_files = []
    for tgt, info in summary["dubbing"].items():
        if info.get("output"):
            all_files.append(info["output"])
        # Include SRT/VTT subtitles (KB Financial Schedule)
        sub_dir = Path(out_dir) / tgt
        for sub in list(sub_dir.glob("*.srt")) + list(sub_dir.glob("*.vtt")):
            all_files.append(str(sub))
    for p in summary.get("quiz_docx", {}).values():
        all_files.append(p)
    for p in summary.get("qa_reports", {}).values():
        all_files.append(p)
    if summary.get("metadata_xlsx", {}).get("all"):
        all_files.append(summary["metadata_xlsx"]["all"])

    return _save_outputs(all_files) or None, json.dumps(summary, indent=2, default=str)


# ── Tab 4: QA Report ─────────────────────────────────────────
def gen_qa(course_id, tgt_lang, src_lang, input_file, output_file, reviewer):
    from pipeline.dubbing_pipeline import DubbingResult
    if not course_id or not input_file:
        return None, "❌ Course ID and input file are required."
    pipeline = get_pipeline()
    out_dir  = os.path.join(_get_output_dir(), course_id)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    dummy = DubbingResult(
        source_lang=src_lang, target_lang=tgt_lang,
        input_path=input_file.name,
        output_video_path=output_file.name if output_file else "",
        success=True,
    )
    qa_path = os.path.join(out_dir, f"{course_id}_{tgt_lang}_qa_cert.docx")
    try:
        pipeline.generate_qa_report(course_id, tgt_lang, dummy, qa_path, reviewer)
        return qa_path, f"✅ QA report → {Path(qa_path).name}"
    except Exception as e:
        return None, f"❌ {e}"


# ── Build UI ──────────────────────────────────────────────────
def build_ui():
    src_choices = list(SRC_LANGS)
    tgt_choices = list(TGT_LANGS)
    env         = _load_env()

    with gr.Blocks(title="KB Translation System") as app:

        def _pipeline_status():
            if _pipeline_ready.is_set():
                return "✅ Pipeline ready" if not _pipeline_error else f"❌ {_pipeline_error}"
            return "⏳ Loading models in background..."

        gr.Markdown(
            "# 🇮🇳 KB Translation & Dubbing System\n"
            "**iGOT Karmayogi — 22 Indian Languages** | "
            "IndicTrans2 · faster-whisper · MMS-TTS"
        )
        status_bar = gr.Textbox(value=_pipeline_status, every=3,
                                label="Pipeline Status", interactive=False, lines=1)

        # ── Tab 1: Dub ────────────────────────────────────────
        with gr.Tab("🎬 Dub Video / Audio"):
            with gr.Row():
                with gr.Column(scale=2):
                    t1_file  = gr.File(label="Upload MP4 / MP3 / WAV",
                                       file_types=[".mp4",".mp3",".wav",".flac"])
                    t1_src   = gr.Dropdown(src_choices, value="eng", label="Source Language")
                    t1_tgt   = gr.CheckboxGroup(tgt_choices, value=["hin","pan"],
                                                label="Target Languages")
                    with gr.Row():
                        gr.Button("KB 11", size="sm").click(
                            lambda: KB_11, outputs=[t1_tgt])
                        gr.Button("All 22", size="sm").click(
                            lambda: [c for _,c in tgt_choices], outputs=[t1_tgt])
                        gr.Button("Clear", size="sm").click(
                            lambda: [], outputs=[t1_tgt])
                    t1_clone = gr.Checkbox(label="🎙️ Voice Cloning (Tier 2)", value=False)
                    t1_ref   = gr.File(label="Reference Speaker Audio",
                                       file_types=[".wav",".mp3"], visible=False)
                    t1_clone.change(lambda v: gr.update(visible=v), t1_clone, t1_ref)
                    t1_btn   = gr.Button("🚀 Start Dubbing", variant="primary")

                with gr.Column(scale=2):
                    t1_preview = gr.Video(label="Preview (first language)")
                    t1_dl      = gr.Files(label="Download All Outputs")
                    t1_log     = gr.Textbox(label="Status", lines=6)
                    t1_quality = gr.Textbox(label="Quality Scores", lines=5)

            t1_btn.click(dub_file,
                         inputs=[t1_file, t1_src, t1_tgt, t1_clone, t1_ref],
                         outputs=[t1_preview, t1_dl, t1_log, t1_quality])

        # ── Tab 2: Document ───────────────────────────────────
        with gr.Tab("📄 Translate Document"):
            with gr.Row():
                with gr.Column(scale=2):
                    t2_file  = gr.File(label="Upload Document (PDF / DOCX / TXT / JSON)",
                                       file_types=[".json", ".pdf", ".docx", ".doc", ".txt"])
                    t2_type  = gr.Radio(["Quiz (Word .docx)", "Metadata (Excel .xlsx)"],
                                        value="Quiz (Word .docx)", label="Document Type")
                    t2_src   = gr.Dropdown(src_choices, value="eng", label="Source Language")
                    t2_tgt   = gr.CheckboxGroup(tgt_choices, value=["hin","pan"],
                                                label="Target Languages")
                    t2_title = gr.Textbox(label="Course Title (optional)")
                    t2_btn   = gr.Button("🚀 Translate", variant="primary")
                with gr.Column(scale=2):
                    t2_dl  = gr.Files(label="Download Outputs")
                    t2_log = gr.Textbox(label="Log", lines=8)
            t2_btn.click(translate_doc,
                         inputs=[t2_file, t2_src, t2_tgt, t2_type, t2_title],
                         outputs=[t2_dl, t2_log])

        # ── Tab 3: Full Course ────────────────────────────────
        with gr.Tab("📦 Full Course Batch"):
            with gr.Row():
                with gr.Column(scale=2):
                    t3_video = gr.File(label="Video / Audio",
                                       file_types=[".mp4",".mp3",".wav"])
                    t3_meta  = gr.File(label="Metadata JSON (optional)",
                                       file_types=[".json"])
                    t3_quiz  = gr.File(label="Quiz JSON (optional)",
                                       file_types=[".json"])
                    t3_id    = gr.Textbox(label="Course ID", placeholder="KB_COURSE_001")
                    t3_src   = gr.Dropdown(src_choices, value="eng", label="Source Language")
                    t3_tgt   = gr.CheckboxGroup(tgt_choices, value=KB_11,
                                                label="Target Languages")
                    with gr.Row():
                        t3_clone = gr.Checkbox(label="Voice Cloning", value=False)
                        t3_cbp   = gr.Checkbox(label="Upload to CBP Portal", value=False)
                    t3_btn   = gr.Button("🚀 Process Full Course", variant="primary")
                with gr.Column(scale=2):
                    t3_dl  = gr.Files(label="Download All Outputs")
                    t3_log = gr.Textbox(label="Summary JSON", lines=20)
            t3_btn.click(process_course,
                         inputs=[t3_video, t3_meta, t3_quiz, t3_src, t3_tgt,
                                 t3_id, t3_clone, t3_cbp],
                         outputs=[t3_dl, t3_log])

        # ── Tab 4: QA Report ──────────────────────────────────
        with gr.Tab("📋 QA Report"):
            with gr.Row():
                with gr.Column(scale=2):
                    t4_id       = gr.Textbox(label="Course ID")
                    t4_src      = gr.Dropdown(src_choices, value="eng", label="Source Language")
                    t4_tgt      = gr.Dropdown(tgt_choices, value="hin", label="Target Language")
                    t4_input    = gr.File(label="Original Input File")
                    t4_output   = gr.File(label="Dubbed Output File (optional)")
                    t4_reviewer = gr.Textbox(label="Reviewer Name",
                                             value="Translation Agency QA Lead")
                    t4_btn      = gr.Button("📋 Generate QA Certificate", variant="primary")
                with gr.Column(scale=2):
                    t4_dl  = gr.File(label="Download QA Report (.docx)")
                    t4_log = gr.Textbox(label="Status", lines=4)
            t4_btn.click(gen_qa,
                         inputs=[t4_id, t4_tgt, t4_src, t4_input, t4_output, t4_reviewer],
                         outputs=[t4_dl, t4_log])

        # ── Tab 5: Settings ───────────────────────────────────
        with gr.Tab("⚙️ Settings"):
            with gr.Row():
                with gr.Column():
                    hf_key   = gr.Textbox(label="HuggingFace Token (HF_TOKEN)",
                                          value=env.get("HF_TOKEN",""),
                                          type="password", placeholder="hf_...")
                    save_btn    = gr.Button("💾 Save Token", variant="primary")
                    save_status = gr.Textbox(label="Status", lines=2, interactive=False)
                    gr.Markdown("---")
                    out_dir_box = gr.Textbox(
                        label="📂 Output Save Folder",
                        value=_get_output_dir(),
                        placeholder=r"e.g. D:\KB_Outputs",
                        info="All dubbed files, docs and QA reports are saved here."
                    )
                    with gr.Row():
                        dir_save_btn = gr.Button("💾 Set Folder", variant="primary")
                        open_btn     = gr.Button("📂 Open Folder")
                    dir_status = gr.Textbox(label="", lines=1, interactive=False)
                with gr.Column():
                    gr.Markdown(
                        "### Quality Scoring\n"
                        "Every segment scored 0–1 automatically:\n"
                        "- **≥ 0.55** → Pass\n"
                        "- **0.30–0.55** → Needs human review\n"
                        "- **< 0.30** → Failed\n\n"
                        "### Checkpoint / Resume\n"
                        "If a job crashes, re-run with same input — "
                        "completed segments restore from disk automatically.\n"
                    )
            save_btn.click(_save_env, inputs=[hf_key], outputs=[save_status])
            dir_save_btn.click(_set_output_dir, inputs=[out_dir_box], outputs=[dir_status])
            open_btn.click(lambda: (os.startfile(_get_output_dir()), "✅ Folder opened")[1], outputs=[dir_status])

        # ── Tab 6: Live Logs ──────────────────────────────────
        with gr.Tab("📊 Live Logs"):
            gr.Markdown("Real-time pipeline logs. Refresh to update.")
            log_box     = gr.Textbox(label="Pipeline Log", lines=30, interactive=False)
            refresh_btn = gr.Button("🔄 Refresh Logs")
            refresh_btn.click(_get_log, outputs=[log_box])

    return app


if __name__ == "__main__":
    import socket
    def _free_port(preferred=7860):
        for port in range(preferred, preferred + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        return 0  # let Gradio pick
    port = _free_port(7860)
    app = build_ui()
    print(f"Starting on http://localhost:{port}")
    app.launch(
        server_name="0.0.0.0",
        server_port=port or None,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(primary_hue="indigo"),
    )
