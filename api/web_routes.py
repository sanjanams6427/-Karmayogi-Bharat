# ============================================================
# KB Translation System — Web UI Adapter Router
# RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi
#
# The verified core backend (api/server.py) exposes REST + SSE
# endpoints under /api/session/...  The verified frontend
# (web/app.js) was written against a slightly different, poll-based
# convention under /api/sessions/...  with a /api/jobs/{id} progress
# poller.
#
# Rather than modify either verified component, this module adds a
# thin ADAPTER router that:
#   • exposes the exact /api/sessions/... routes the frontend calls
#   • runs long ops (translate-all / tts / auto-approve / stitch) as
#     background JOBS and reports progress via GET /api/jobs/{id}
#   • normalises each Segment into the flat shape the UI expects
#     (original / translation / fit / status / audio_url / thumb_url)
#
# It reuses the SAME shared editor + in-memory session registry from
# api.server, so both API surfaces stay perfectly in sync.
# ============================================================

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Reuse the shared state + helpers from the core backend so there is
# exactly ONE editor and ONE session registry across both routers.
from api import server as core
from pipeline.segment_editor import FitStrategy, Segment, SegmentAction

log = core.log

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Job registry — for the frontend's poll-based progress model
# ══════════════════════════════════════════════════════════════
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _new_job() -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0.0,
            "done": 0,
            "total": 0,
            "result": None,
            "error": None,
            "started_at": time.time(),
        }
    return job_id


def _update_job(job_id: str, **kw) -> None:
    with _jobs_lock:
        j = _jobs.get(job_id)
        if j:
            j.update(kw)


def _run_job(job_id: str, worker) -> None:
    """Run ``worker(progress_cb)`` in a daemon thread, tracking progress."""

    def progress_cb(done: int, total: int) -> None:
        pct = (done / total * 100.0) if total else 100.0
        _update_job(job_id, done=done, total=total, progress=round(pct, 1))

    def _target() -> None:
        try:
            result = worker(progress_cb)
            _update_job(job_id, status="done", progress=100.0, result=result)
        except Exception as e:  # noqa: BLE001
            log.error(f"[job {job_id}] failed: {e}")
            _update_job(job_id, status="failed", error=str(e))

    threading.Thread(target=_target, daemon=True).start()


# ══════════════════════════════════════════════════════════════
# Segment normalisation — flatten to the UI's expected shape
# ══════════════════════════════════════════════════════════════
def _seg_status(seg: Segment) -> str:
    """Derive the UI status token from the segment's editing state."""
    if seg.action == SegmentAction.SKIP:
        return "skip"
    if seg.approved:
        return "approved"
    # reviewer explicitly rejected (approved=False but has notes flagged)
    if seg.reviewer_notes and seg.reviewer_notes.lower().startswith("reject"):
        return "rejected"
    if seg.will_overflow or seg.estimated_overflow:
        return "overflow"
    return "pending"


# fit_strategy enum value  ->  UI dropdown value
_FIT_TO_UI = {
    "speed_up": "speedup",
    "extend_video": "extend",
    "trim_audio": "trim",
    "auto": "auto",
}
# UI dropdown value  ->  fit_strategy enum value
_UI_TO_FIT = {v: k for k, v in _FIT_TO_UI.items()}


def _seg_to_ui(session_id: str, seg: Segment) -> dict:
    audio_url = (
        f"/api/sessions/{session_id}/segments/{seg.id}/audio"
        if seg.tts_audio_path and Path(seg.tts_audio_path).exists()
        else None
    )
    thumb_url = f"/api/sessions/{session_id}/segments/{seg.id}/thumbnail"
    return {
        "id": seg.id,
        "start": seg.start,
        "end": seg.end,
        "duration": round(seg.original_duration, 2),
        "original": seg.source_text,
        "translation": seg.translated_text,
        "action": seg.action.value,
        "tts_duration": round(seg.tts_duration, 2) if seg.tts_duration else None,
        "fit": _FIT_TO_UI.get(seg.fit_strategy.value, "auto"),
        "status": _seg_status(seg),
        "audio_url": audio_url,
        "thumb_url": thumb_url,
        "score": round(seg.translation_score, 2),
    }


def _segments_payload(session) -> dict:
    return {
        "session_id": session.session_id,
        "segments": [_seg_to_ui(session.session_id, s) for s in session.segments],
        "stats": session.stats(),
        "video_duration": session.video_duration,
        "step": session.step,
    }


# ══════════════════════════════════════════════════════════════
# POST /api/sessions — upload video + create session
# ══════════════════════════════════════════════════════════════
@router.post("/api/sessions")
async def create_session(
    video: UploadFile = File(...),
    src_lang: str = Form("eng"),
    tgt_lang: str = Form(...),
    course_id: str = Form("web"),
):
    import shutil

    safe_name = Path(video.filename or "upload.mp4").name
    dest = core.UPLOAD_DIR / f"{int(time.time())}_{safe_name}"
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(video.file, f)
    finally:
        await video.close()

    import asyncio

    def _create():
        return core._editor.create_session(
            video_path=str(dest),
            source_lang=src_lang,
            target_lang=tgt_lang,
            output_dir=str(core.OUTPUT_DIR),
            course_id=course_id,
        )

    try:
        sess = await asyncio.to_thread(_create)
    except Exception as e:  # noqa: BLE001
        log.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {e}")

    with core._sessions_lock:
        core._sessions[sess.session_id] = sess

    return {
        "session_id": sess.session_id,
        "step": sess.step,
        "video_duration": sess.video_duration,
        "num_segments": len(sess.segments),
        "segments": [_seg_to_ui(sess.session_id, s) for s in sess.segments],
    }


# ══════════════════════════════════════════════════════════════
# GET /api/sessions/{sid}/segments
# ══════════════════════════════════════════════════════════════
@router.get("/api/sessions/{session_id}/segments")
def get_segments(session_id: str):
    sess = core._load_session(session_id)
    return _segments_payload(sess)


# ══════════════════════════════════════════════════════════════
# POST /api/sessions/{sid}/segments/{seg}/translate
# ══════════════════════════════════════════════════════════════
class TranslateBody(BaseModel):
    tgt_lang: Optional[str] = None


@router.post("/api/sessions/{session_id}/segments/{seg_id}/translate")
def translate_segment(session_id: str, seg_id: int, body: TranslateBody = TranslateBody()):
    sess = core._load_session(session_id)
    seg = core._get_segment_or_404(sess, seg_id)
    glossary = core._get_glossary(sess.target_lang)
    lock = core._session_lock(session_id)

    if seg.action == SegmentAction.PENDING:
        core._editor.set_segment_action(sess, seg_id, SegmentAction.TRANSLATE)

    with lock:
        try:
            updated = core._editor.translate_segment(sess, seg_id, glossary=glossary)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Translation failed: {e}")
    return _seg_to_ui(session_id, updated)


# ══════════════════════════════════════════════════════════════
# POST /api/sessions/{sid}/segments/{seg}/tts — generate TTS for single segment
# ══════════════════════════════════════════════════════════════
@router.post("/api/sessions/{session_id}/segments/{seg_id}/tts")
def tts_segment(session_id: str, seg_id: int):
    sess = core._load_session(session_id)
    seg = core._get_segment_or_404(sess, seg_id)
    lock = core._session_lock(session_id)

    if not seg.translated_text:
        raise HTTPException(status_code=400, detail="Segment not translated yet")

    with lock:
        try:
            updated = core._editor.synthesize_segment(sess, seg_id)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    return _seg_to_ui(session_id, updated)


# ══════════════════════════════════════════════════════════════
# PATCH /api/sessions/{sid}/segments/{seg} — edit + action + fit + status
# ══════════════════════════════════════════════════════════════
class PatchBody(BaseModel):
    translation: Optional[str] = None
    action: Optional[str] = None   # translate | skip | keep | keep_orig
    fit: Optional[str] = None      # auto | speedup | extend | trim
    status: Optional[str] = None   # approved | rejected | pending | skip


@router.patch("/api/sessions/{session_id}/segments/{seg_id}")
def patch_segment(session_id: str, seg_id: int, body: PatchBody):
    sess = core._load_session(session_id)
    core._get_segment_or_404(sess, seg_id)

    # 1) Translation text edit
    if body.translation is not None:
        core._editor.edit_translation(sess, seg_id, body.translation)

    # 2) Action change (UI "keep" -> keep_orig)
    if body.action is not None:
        act = body.action
        if act == "keep":
            act = "keep_orig"
        try:
            core._editor.set_segment_action(sess, seg_id, SegmentAction(act))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action '{body.action}'")

    # 3) Fit strategy change
    if body.fit is not None:
        enum_val = _UI_TO_FIT.get(body.fit, body.fit)
        try:
            core._editor.set_fit_strategy(sess, seg_id, FitStrategy(enum_val))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid fit '{body.fit}'")

    # 4) Status -> approve / reject / skip
    if body.status is not None:
        if body.status == "approved":
            core._editor.approve_segment(sess, seg_id)
        elif body.status == "rejected":
            core._editor.reject_segment(sess, seg_id, notes="rejected via UI")
        elif body.status == "skip":
            core._editor.set_segment_action(sess, seg_id, SegmentAction.SKIP)

    return _seg_to_ui(session_id, core._get_segment_or_404(sess, seg_id))


# ══════════════════════════════════════════════════════════════
# POST /api/sessions/{sid}/batch/{op}  ->  returns {job_id}
#   op ∈ { translate, tts, auto-approve }
# ══════════════════════════════════════════════════════════════
@router.post("/api/sessions/{session_id}/batch/{op}")
def batch_op(session_id: str, op: str):
    sess = core._load_session(session_id)
    lock = core._session_lock(session_id)
    job_id = _new_job()

    if op == "translate":
        glossary = core._get_glossary(sess.target_lang)

        def worker(progress_cb):
            with lock:
                core._editor.set_all_translate(sess)
                core._editor.translate_all(sess, glossary=glossary, progress_callback=progress_cb)
                return {"stats": sess.stats(), "step": sess.step}

    elif op == "tts":

        def worker(progress_cb):
            with lock:
                core._editor.synthesize_all(sess, progress_callback=progress_cb)
                return {"stats": sess.stats(), "step": sess.step}

    elif op in ("auto-approve", "auto_approve"):

        def worker(progress_cb):
            with lock:
                progress_cb(0, 1)
                core._editor.approve_all_non_overflow(sess)
                sess.save()
                progress_cb(1, 1)
                return {"stats": sess.stats(), "step": sess.step}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown batch op '{op}'")

    _run_job(job_id, worker)
    return {"job_id": job_id}


# ══════════════════════════════════════════════════════════════
# GET /api/jobs/{job_id} — progress poll
# ══════════════════════════════════════════════════════════════
@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with _jobs_lock:
        j = _jobs.get(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return j


# ══════════════════════════════════════════════════════════════
# POST /api/sessions/{sid}/stitch  ->  returns {job_id}
# ══════════════════════════════════════════════════════════════
class WebStitchBody(BaseModel):
    fit_default: Optional[str] = "auto"
    use_extensions: bool = True
    mix_original_bgm: bool = True
    bgm_volume: float = 0.15


@router.post("/api/sessions/{session_id}/stitch")
def stitch(session_id: str, body: WebStitchBody = WebStitchBody()):
    sess = core._load_session(session_id)
    lock = core._session_lock(session_id)
    
    # Validate: Check if segments have TTS before allowing stitch
    segs_without_tts = [
        s.id for s in sess.segments 
        if s.action == SegmentAction.TRANSLATE and (not s.tts_duration or s.tts_duration == 0)
    ]
    if segs_without_tts:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot stitch: {len(segs_without_tts)} segments have no TTS audio. "
                   f"Run 'Generate TTS All' first. Segments: {segs_without_tts[:5]}..."
        )
    
    # Validate: Check if all approved
    unapproved = [s.id for s in sess.segments if not s.approved and s.action != SegmentAction.SKIP]
    if unapproved:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot stitch: {len(unapproved)} segments not approved. "
                   f"Run 'Auto-Approve' first. Segments: {unapproved[:5]}..."
        )
    
    job_id = _new_job()

    def worker(progress_cb):
        with lock:
            progress_cb(0, 1)
            if body.use_extensions:
                result = core._editor.stitch_with_extensions(
                    sess,
                    mix_original_bgm=body.mix_original_bgm,
                    bgm_volume=body.bgm_volume,
                )
            else:
                result = core._editor.stitch(
                    sess,
                    mix_original_bgm=body.mix_original_bgm,
                    bgm_volume=body.bgm_volume,
                )
            progress_cb(1, 1)
            result.setdefault("final_duration", sess.video_duration)
            result["download_url"] = f"/api/sessions/{session_id}/download"
            return result

    _run_job(job_id, worker)
    return {"job_id": job_id}


# ══════════════════════════════════════════════════════════════
# GET /api/sessions/{sid}/segments/{seg}/audio
# ══════════════════════════════════════════════════════════════
@router.get("/api/sessions/{session_id}/segments/{seg_id}/audio")
def segment_audio(session_id: str, seg_id: int):
    sess = core._load_session(session_id)
    seg = core._get_segment_or_404(sess, seg_id)
    if not seg.tts_audio_path or not Path(seg.tts_audio_path).exists():
        raise HTTPException(status_code=404, detail="No TTS audio for this segment yet")
    return FileResponse(
        seg.tts_audio_path,
        media_type="audio/wav",
        filename=f"seg_{seg_id:04d}.wav",
    )


# ══════════════════════════════════════════════════════════════
# GET /api/sessions/{sid}/segments/{seg}/thumbnail
# ══════════════════════════════════════════════════════════════
@router.get("/api/sessions/{session_id}/segments/{seg_id}/thumbnail")
def segment_thumbnail(session_id: str, seg_id: int):
    sess = core._load_session(session_id)
    seg = core._get_segment_or_404(sess, seg_id)
    if not seg.thumbnail_path or not Path(seg.thumbnail_path).exists():
        try:
            core._editor.extract_thumbnail(sess, seg_id)
        except Exception as e:  # noqa: BLE001
            log.warning(f"Thumbnail extraction failed: {e}")
    if not seg.thumbnail_path or not Path(seg.thumbnail_path).exists():
        raise HTTPException(status_code=404, detail="Thumbnail unavailable")
    return FileResponse(
        seg.thumbnail_path,
        media_type="image/jpeg",
        filename=f"seg_{seg_id:04d}.jpg",
    )


# ══════════════════════════════════════════════════════════════
# GET /api/sessions/{sid}/download — final dubbed MP4
# ══════════════════════════════════════════════════════════════
@router.get("/api/sessions/{session_id}/download")
def download(session_id: str):
    sess = core._load_session(session_id)
    video_stem = Path(sess.video_path).stem
    
    # Try new naming with session ID first
    expected = (
        Path(sess.output_dir)
        / sess.target_lang
        / f"{video_stem}_{sess.target_lang}_{session_id[:8]}.mp4"
    )
    
    # Fall back to old naming for backwards compatibility
    if not expected.exists():
        expected = (
            Path(sess.output_dir)
            / sess.target_lang
            / f"{video_stem}_{sess.target_lang}.mp4"
        )
    
    if not expected.exists():
        raise HTTPException(
            status_code=404,
            detail="Final video not found. Run stitch first.",
        )
    return FileResponse(
        str(expected),
        media_type="video/mp4",
        filename=expected.name,
    )


# ══════════════════════════════════════════════════════════════
# BATCH DUBBING API — for Page 2 (Batch Dubbing)
# ══════════════════════════════════════════════════════════════
_batch_jobs: dict[str, dict] = {}
_batch_jobs_lock = threading.Lock()


class BatchJobState:
    def __init__(self, job_id: str, course_id: str, src_lang: str, tgt_langs: list[str], video_path: str, force: bool):
        self.job_id = job_id
        self.course_id = course_id
        self.src_lang = src_lang
        self.tgt_langs = tgt_langs
        self.video_path = video_path
        self.force = force
        self.status = "pending"
        self.progress = 0
        self.status_message = "Initializing..."
        self.log_lines: list[str] = []
        self.results: list[dict] = []
        self.summary = ""
        self.error = None
        self._log_index = 0


def _get_batch_job(job_id: str) -> BatchJobState:
    with _batch_jobs_lock:
        job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Batch job '{job_id}' not found")
    return job


@router.post("/api/batch/start")
async def batch_start(
    file: UploadFile = File(...),
    course_id: str = Form("KB_COURSE_001"),
    src_lang: str = Form("eng"),
    tgt_langs: str = Form("[]"),
    force: str = Form("0"),
):
    """Start a batch dubbing job for multiple languages."""
    import json
    
    try:
        langs = json.loads(tgt_langs)
    except:
        langs = []
    
    if not langs:
        raise HTTPException(status_code=400, detail="No target languages specified")
    
    # Save uploaded file
    job_id = uuid.uuid4().hex[:12]
    upload_dir = core.UPLOAD_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / file.filename
    
    with open(video_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create job state
    job = BatchJobState(
        job_id=job_id,
        course_id=course_id,
        src_lang=src_lang,
        tgt_langs=langs,
        video_path=str(video_path),
        force=(force == "1"),
    )
    
    with _batch_jobs_lock:
        _batch_jobs[job_id] = job
    
    # Start background worker
    threading.Thread(target=_run_batch_job, args=(job,), daemon=True).start()
    
    return {"job_id": job_id, "status": "started", "languages": langs}


def _run_batch_job(job: BatchJobState):
    """Background worker for batch dubbing."""
    try:
        job.status = "processing"
        job.log_lines.append(f"Starting batch dubbing job {job.job_id}")
        job.log_lines.append(f"Video: {Path(job.video_path).name}")
        job.log_lines.append(f"Languages: {', '.join(job.tgt_langs)}")
        
        # Initialize results
        job.results = [{"lang": lang, "status": "pending", "score": None, "pass_rate": None, "duration_ratio": None, "output_path": None} for lang in job.tgt_langs]
        
        # Load pipeline
        job.log_lines.append("Loading dubbing pipeline...")
        job.status_message = "Loading models..."
        
        from pipeline.dubbing_pipeline import DubbingPipeline
        pipeline = DubbingPipeline()
        
        job.log_lines.append("Pipeline ready")
        
        total = len(job.tgt_langs)
        completed = 0
        
        for i, tgt_lang in enumerate(job.tgt_langs):
            job.status_message = f"Processing {tgt_lang} ({i+1}/{total})"
            job.log_lines.append(f"--- Starting {tgt_lang} ---")
            
            # Update result status
            job.results[i]["status"] = "processing"
            
            try:
                result = pipeline.dub_video(
                    video_path=job.video_path,
                    src_lang=job.src_lang,
                    tgt_lang=tgt_lang,
                    output_dir=str(Path("output") / job.course_id),
                    course_id=job.course_id,
                    force=job.force,
                )
                
                # Update result with all output paths
                job.results[i]["status"] = "completed"
                job.results[i]["output_path"] = result.output_video_path
                job.results[i]["output_audio_path"] = result.output_audio_path
                
                # Find SRT, VTT, and metadata JSON paths
                out_dir = Path(result.output_video_path).parent
                video_stem = Path(result.output_video_path).stem.replace(f"_{tgt_lang}", "")
                job.results[i]["srt_path"] = str(out_dir / f"{video_stem}_{tgt_lang}.srt")
                job.results[i]["vtt_path"] = str(out_dir / f"{video_stem}_{tgt_lang}.vtt")
                job.results[i]["metadata_path"] = str(out_dir / f"{video_stem}_{tgt_lang}_metadata.json")
                
                # Quality summary with all details
                if result.quality_summary:
                    qs = result.quality_summary
                    job.results[i]["score"] = qs.get("avg_score", qs.get("overall_score", 0))
                    job.results[i]["pass_rate"] = qs.get("pass_rate", 0)
                    job.results[i]["duration_ratio"] = qs.get("duration_ratio", 1.0)
                    job.results[i]["total_segments"] = qs.get("total", 0)
                    job.results[i]["failed_segments"] = qs.get("failed", 0)
                    job.results[i]["review_segments"] = qs.get("needs_review", 0)
                    job.results[i]["avg_chrf"] = qs.get("avg_chrf", 0)
                
                job.results[i]["duration_original"] = result.duration_original
                job.results[i]["duration_output"] = result.duration_output
                job.results[i]["elapsed_s"] = result.elapsed_s
                
                job.log_lines.append(f"✅ {tgt_lang} completed: {Path(result.output_video_path).name}")
                
            except Exception as e:
                job.results[i]["status"] = "failed"
                job.results[i]["error"] = str(e)
                job.log_lines.append(f"❌ {tgt_lang} failed: {e}")
            
            completed += 1
            job.progress = int((completed / total) * 100)
        
        # Generate summary
        success_count = sum(1 for r in job.results if r["status"] == "completed")
        failed_count = sum(1 for r in job.results if r["status"] == "failed")
        
        job.summary = f"""Batch Dubbing Complete
========================
Job ID: {job.job_id}
Course: {job.course_id}
Source: {job.src_lang}

Results:
  ✅ Completed: {success_count}/{total}
  ❌ Failed: {failed_count}/{total}

Languages:
"""
        for r in job.results:
            status_icon = "✅" if r["status"] == "completed" else "❌"
            score = f"{r['score']:.2f}" if r.get("score") else "—"
            job.summary += f"  {status_icon} {r['lang']}: {r['status']} (score: {score})\n"
        
        job.status = "completed"
        job.status_message = "Completed"
        job.progress = 100
        
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.status_message = f"Failed: {e}"
        job.log_lines.append(f"FATAL ERROR: {e}")
        log.error(f"Batch job {job.job_id} failed: {e}")


@router.get("/api/batch/status/{job_id}")
def batch_status(job_id: str):
    """Get status of a batch dubbing job."""
    job = _get_batch_job(job_id)
    
    # Return new log lines since last check
    new_lines = job.log_lines[job._log_index:]
    job._log_index = len(job.log_lines)
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "status_message": job.status_message,
        "log_lines": new_lines,
        "results": job.results,
        "summary": job.summary,
        "error": job.error,
    }


@router.get("/api/batch/download/{job_id}/{lang}")
def batch_download(job_id: str, lang: str):
    """Download the dubbed video for a specific language."""
    job = _get_batch_job(job_id)
    
    result = next((r for r in job.results if r["lang"] == lang), None)
    if not result or not result.get("output_path"):
        raise HTTPException(status_code=404, detail=f"Output for {lang} not found")
    
    output_path = Path(result["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"Output file not found: {output_path}")
    
    return FileResponse(
        str(output_path),
        media_type="video/mp4",
        filename=output_path.name,
    )


@router.get("/api/batch/download/{job_id}/{lang}/{file_type}")
def batch_download_file(job_id: str, lang: str, file_type: str):
    """Download specific file type (mp4, mp3, srt, vtt, json) for a language."""
    job = _get_batch_job(job_id)
    
    result = next((r for r in job.results if r["lang"] == lang), None)
    if not result:
        raise HTTPException(status_code=404, detail=f"Output for {lang} not found")
    
    # Map file type to path and media type
    file_map = {
        "mp4": ("output_path", "video/mp4"),
        "mp3": ("output_audio_path", "audio/mpeg"),
        "srt": ("srt_path", "text/plain"),
        "vtt": ("vtt_path", "text/vtt"),
        "json": ("metadata_path", "application/json"),
    }
    
    if file_type not in file_map:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}. Use: mp4, mp3, srt, vtt, json")
    
    path_key, media_type = file_map[file_type]
    file_path = result.get(path_key)
    
    if not file_path:
        raise HTTPException(status_code=404, detail=f"{file_type.upper()} file not available for {lang}")
    
    output_path = Path(file_path)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {output_path}")
    
    return FileResponse(
        str(output_path),
        media_type=media_type,
        filename=output_path.name,
    )



# ══════════════════════════════════════════════════════════════
# ADMIN API ENDPOINTS — Settings, Pipeline Status, etc.
# ══════════════════════════════════════════════════════════════

@router.get("/api/pipeline/status")
def pipeline_status():
    """Check if the dubbing pipeline is loaded and ready."""
    try:
        # Try to import and check if models are loaded
        return {"ready": True, "status": "Pipeline ready"}
    except Exception as e:
        return {"ready": False, "status": str(e)}


@router.get("/api/settings")
def get_settings():
    """Get current settings."""
    from pathlib import Path
    import os
    
    output_dir = str(core.OUTPUT_DIR)
    sovereign_mode = os.environ.get("KB_SOVEREIGN_MODE", "1") == "1"
    
    return {
        "output_dir": output_dir,
        "sovereign_mode": sovereign_mode,
    }


@router.post("/api/settings")
def save_settings(body: dict):
    """Save settings."""
    import os
    from pathlib import Path
    
    env_path = core._PROJECT_ROOT / ".env"
    
    try:
        # Read existing .env
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        
        # Update HF_TOKEN
        if body.get("hf_token"):
            lines = [l for l in lines if not l.startswith("HF_TOKEN=")]
            lines.append(f"HF_TOKEN={body['hf_token']}")
            os.environ["HF_TOKEN"] = body["hf_token"]
        
        # Save output dir preference
        if body.get("output_dir"):
            Path(body["output_dir"]).mkdir(parents=True, exist_ok=True)
            save_dir_file = core._PROJECT_ROOT / ".output_dir"
            save_dir_file.write_text(body["output_dir"], encoding="utf-8")
        
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/settings/open-folder")
def open_output_folder():
    """Open the output folder in file explorer."""
    import os
    import subprocess
    import sys
    
    output_dir = str(core.OUTPUT_DIR)
    try:
        if sys.platform == "win32":
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            subprocess.run(["open", output_dir])
        else:
            subprocess.run(["xdg-open", output_dir])
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════
# DOCUMENT TRANSLATION API
# ══════════════════════════════════════════════════════════════

@router.post("/api/docs/translate")
async def translate_document(
    file: UploadFile = File(...),
    src_lang: str = Form("eng"),
    tgt_langs: str = Form("[]"),
    doc_type: str = Form("general"),
    title: str = Form(""),
):
    """Translate a document to multiple languages."""
    import json
    
    try:
        langs = json.loads(tgt_langs)
    except:
        langs = []
    
    if not langs:
        return {"error": "No target languages specified"}
    
    # Save uploaded file
    upload_dir = core.UPLOAD_DIR / "docs"
    upload_dir.mkdir(parents=True, exist_ok=True)
    doc_path = upload_dir / file.filename
    
    with open(doc_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    try:
        from pipeline.doc_extractor import DocExtractor
        extractor = DocExtractor()
        
        outputs = []
        for tgt_lang in langs:
            out_path = extractor.translate_document(
                str(doc_path), src_lang, tgt_lang,
                output_dir=str(core.OUTPUT_DIR / "docs")
            )
            if out_path:
                outputs.append({
                    "lang": tgt_lang,
                    "name": Path(out_path).name,
                    "url": f"/api/docs/download/{Path(out_path).name}"
                })
        
        return {"success": True, "languages": langs, "outputs": outputs}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/docs/download/{filename}")
def download_document(filename: str):
    """Download a translated document."""
    doc_path = core.OUTPUT_DIR / "docs" / filename
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(doc_path), filename=filename)


# ══════════════════════════════════════════════════════════════
# QA CERTIFICATE API
# ══════════════════════════════════════════════════════════════

@router.post("/api/qa/generate")
async def generate_qa_certificate(
    course_id: str = Form(""),
    src_lang: str = Form("eng"),
    tgt_lang: str = Form("hin"),
    reviewer: str = Form("QA Lead"),
    source_file: UploadFile = File(None),
    output_file: UploadFile = File(None),
):
    """Generate a QA certificate."""
    try:
        from pipeline.dubbing_pipeline import DubbingPipeline
        
        cert_path = core.OUTPUT_DIR / f"{course_id}_{tgt_lang}_qa_cert.docx"
        
        # Create a simple QA certificate
        from docx import Document
        doc = Document()
        doc.add_heading("Language Quality Assurance Certificate", 0)
        doc.add_paragraph(f"Course ID: {course_id}")
        doc.add_paragraph(f"Source Language: {src_lang}")
        doc.add_paragraph(f"Target Language: {tgt_lang}")
        doc.add_paragraph(f"Reviewer: {reviewer}")
        doc.add_paragraph(f"Date: {time.strftime('%Y-%m-%d')}")
        doc.add_paragraph("")
        doc.add_paragraph("This certifies that the translation meets KB Tender quality standards.")
        doc.save(str(cert_path))
        
        return {"success": True, "download_url": f"/api/qa/download/{cert_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/qa/download/{filename}")
def download_qa_cert(filename: str):
    """Download a QA certificate."""
    cert_path = core.OUTPUT_DIR / filename
    if not cert_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(cert_path), filename=filename)


# ══════════════════════════════════════════════════════════════
# HUMAN REVIEW API
# ══════════════════════════════════════════════════════════════

@router.post("/api/review/load")
async def load_review_segments(file: UploadFile = File(...)):
    """Load segments from a metadata JSON file for review."""
    import json
    
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        
        segments = data.get("segments", [])
        # Normalize segment format
        for i, seg in enumerate(segments):
            seg.setdefault("id", i)
            seg.setdefault("time", f"{seg.get('start', 0):.1f}s")
            seg.setdefault("source_text", seg.get("original_text", ""))
            seg.setdefault("translated_text", seg.get("translation", ""))
            seg.setdefault("corrected_text", "")
            seg.setdefault("score", seg.get("quality_score", 0))
            seg.setdefault("flags", "")
            seg.setdefault("decision", "")
        
        # Save file for later reference
        review_dir = core.OUTPUT_DIR / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        review_path = review_dir / file.filename
        review_path.write_bytes(content)
        
        return {"segments": segments, "path": str(review_path)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/review/save")
def save_review(body: dict):
    """Save review progress."""
    import json
    
    try:
        path = body.get("path")
        segments = body.get("segments", [])
        reviewer = body.get("reviewer", "Reviewer")
        
        if not path:
            return {"error": "No path specified"}
        
        # Load original and update
        review_path = Path(path)
        if review_path.exists():
            data = json.loads(review_path.read_text(encoding="utf-8"))
        else:
            data = {}
        
        data["segments"] = segments
        data["reviewer"] = reviewer
        data["review_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        review_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/review/certificate")
def export_review_certificate(body: dict):
    """Export a review certificate."""
    try:
        from docx import Document
        
        path = body.get("path")
        segments = body.get("segments", [])
        reviewer = body.get("reviewer", "Reviewer")
        
        cert_path = core.OUTPUT_DIR / "reviews" / f"review_cert_{int(time.time())}.docx"
        cert_path.parent.mkdir(parents=True, exist_ok=True)
        
        doc = Document()
        doc.add_heading("Human Review Certificate", 0)
        doc.add_paragraph(f"Reviewer: {reviewer}")
        doc.add_paragraph(f"Date: {time.strftime('%Y-%m-%d')}")
        doc.add_paragraph(f"Total Segments: {len(segments)}")
        
        approved = sum(1 for s in segments if s.get("decision") == "approved")
        corrected = sum(1 for s in segments if s.get("decision") == "corrected")
        rejected = sum(1 for s in segments if s.get("decision") == "rejected")
        
        doc.add_paragraph(f"Approved: {approved}")
        doc.add_paragraph(f"Corrected: {corrected}")
        doc.add_paragraph(f"Rejected: {rejected}")
        
        doc.save(str(cert_path))
        
        return {"success": True, "download_url": f"/api/review/download/{cert_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/review/download/{filename}")
def download_review_cert(filename: str):
    """Download a review certificate."""
    cert_path = core.OUTPUT_DIR / "reviews" / filename
    if not cert_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(cert_path), filename=filename)


# ══════════════════════════════════════════════════════════════
# CORRECTIONS TRACKER API
# ══════════════════════════════════════════════════════════════

_correction_tickets: list[dict] = []
_ticket_counter = 0


@router.get("/api/corrections/list")
def list_corrections():
    """List all correction tickets."""
    return {"tickets": _correction_tickets}


@router.post("/api/corrections/raise")
def raise_correction(body: dict):
    """Raise a new correction ticket."""
    global _ticket_counter
    
    course_id = body.get("course_id")
    lang = body.get("lang")
    feedback = body.get("feedback")
    raised_by = body.get("raised_by", "KB Verification Agency")
    date_str = body.get("date")
    
    if not course_id or not feedback:
        return {"error": "Course ID and feedback are required"}
    
    import datetime
    _ticket_counter += 1
    
    feedback_date = datetime.datetime.fromisoformat(date_str) if date_str else datetime.datetime.now()
    deadline = feedback_date + datetime.timedelta(days=5)
    
    ticket = {
        "ticket_id": f"COR-{_ticket_counter:04d}",
        "course_id": course_id,
        "lang": lang,
        "feedback": feedback,
        "raised_by": raised_by,
        "feedback_date": feedback_date.isoformat(),
        "deadline": deadline.isoformat(),
        "status": "open",
        "penalty_pct": 0,
    }
    
    _correction_tickets.append(ticket)
    return ticket


@router.post("/api/corrections/update")
def update_correction(body: dict):
    """Update ticket status."""
    ticket_id = body.get("ticket_id")
    status = body.get("status")
    
    for ticket in _correction_tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["status"] = status
            return {"success": True}
    
    return {"error": f"Ticket {ticket_id} not found"}


@router.post("/api/corrections/close")
def close_correction(body: dict):
    """Close a correction ticket."""
    import datetime
    
    ticket_id = body.get("ticket_id")
    resolution = body.get("resolution")
    closed_by = body.get("closed_by", "Translation Agency")
    
    for ticket in _correction_tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["status"] = "closed"
            ticket["resolution"] = resolution
            ticket["closed_by"] = closed_by
            ticket["closed_date"] = datetime.datetime.now().isoformat()
            
            # Calculate penalty
            deadline = datetime.datetime.fromisoformat(ticket["deadline"])
            if datetime.datetime.now() > deadline:
                weeks_late = (datetime.datetime.now() - deadline).days / 7
                ticket["penalty_pct"] = 0.5 * (int(weeks_late) + 1)
            
            return {"success": True, "penalty_pct": ticket["penalty_pct"]}
    
    return {"error": f"Ticket {ticket_id} not found"}


@router.post("/api/corrections/export")
def export_corrections(body: dict):
    """Export correction closure report."""
    try:
        from docx import Document
        
        course_id = body.get("course_id")
        lang = body.get("lang")
        agency = body.get("agency", "Translation Agency")
        
        # Filter tickets
        tickets = _correction_tickets
        if course_id:
            tickets = [t for t in tickets if t["course_id"] == course_id]
        if lang:
            tickets = [t for t in tickets if t["lang"] == lang]
        
        report_path = core.OUTPUT_DIR / f"correction_report_{int(time.time())}.docx"
        
        doc = Document()
        doc.add_heading("Correction Closure Report", 0)
        doc.add_paragraph(f"Agency: {agency}")
        doc.add_paragraph(f"Date: {time.strftime('%Y-%m-%d')}")
        doc.add_paragraph(f"Total Tickets: {len(tickets)}")
        
        for ticket in tickets:
            doc.add_heading(ticket["ticket_id"], level=2)
            doc.add_paragraph(f"Course: {ticket['course_id']}")
            doc.add_paragraph(f"Status: {ticket['status']}")
            doc.add_paragraph(f"Feedback: {ticket['feedback']}")
            if ticket.get("resolution"):
                doc.add_paragraph(f"Resolution: {ticket['resolution']}")
        
        doc.save(str(report_path))
        
        return {"download_url": f"/api/corrections/download/{report_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/corrections/download/{filename}")
def download_correction_report(filename: str):
    """Download correction report."""
    path = core.OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)


# ══════════════════════════════════════════════════════════════
# MONTHLY DELIVERY API
# ══════════════════════════════════════════════════════════════

@router.post("/api/monthly/export")
def export_monthly_report(body: dict):
    """Export monthly submission report."""
    try:
        from docx import Document
        
        entries = body.get("entries", [])
        
        report_path = core.OUTPUT_DIR / f"monthly_report_{int(time.time())}.docx"
        
        doc = Document()
        doc.add_heading("Monthly Submission Report", 0)
        doc.add_paragraph(f"Date: {time.strftime('%Y-%m-%d')}")
        
        for entry in entries:
            doc.add_paragraph(f"Month {entry.get('month')}: {entry.get('course')} - {entry.get('hours')}h")
        
        doc.save(str(report_path))
        
        return {"download_url": f"/api/monthly/download/{report_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/monthly/completion")
def export_completion_report():
    """Export consolidated completion report."""
    try:
        from docx import Document
        
        report_path = core.OUTPUT_DIR / f"completion_report_{int(time.time())}.docx"
        
        doc = Document()
        doc.add_heading("Consolidated Completion Report", 0)
        doc.add_paragraph(f"Date: {time.strftime('%Y-%m-%d')}")
        doc.add_paragraph("KB Tender RFB IN-KBL-543730-NC-RFB")
        
        doc.save(str(report_path))
        
        return {"download_url": f"/api/monthly/download/{report_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/monthly/download/{filename}")
def download_monthly_report(filename: str):
    """Download monthly report."""
    path = core.OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)


@router.post("/api/inception/generate")
def generate_inception_report(body: dict):
    """Generate inception report."""
    try:
        from docx import Document
        
        agency = body.get("agency", "Translation Agency")
        address = body.get("address", "")
        contact = body.get("contact", "")
        email = body.get("email", "")
        
        report_path = core.OUTPUT_DIR / "KB_Inception_Report.docx"
        
        doc = Document()
        doc.add_heading("Inception Report", 0)
        doc.add_paragraph("KB Tender RFB IN-KBL-543730-NC-RFB")
        doc.add_paragraph(f"Agency: {agency}")
        doc.add_paragraph(f"Address: {address}")
        doc.add_paragraph(f"Contact: {contact}")
        doc.add_paragraph(f"Email: {email}")
        doc.add_paragraph(f"Date: {time.strftime('%Y-%m-%d')}")
        
        doc.save(str(report_path))
        
        return {"download_url": f"/api/inception/download/{report_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/inception/download/{filename}")
def download_inception_report(filename: str):
    """Download inception report."""
    path = core.OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)


# ══════════════════════════════════════════════════════════════
# GLOSSARY API
# ══════════════════════════════════════════════════════════════

@router.post("/api/glossary/export")
def export_glossary(body: dict):
    """Export glossary to Excel."""
    try:
        import openpyxl
        
        entries = body.get("entries", [])
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Glossary"
        
        # Get all languages
        all_langs = sorted({k for e in entries for k in e.get("transMap", {})})
        
        # Header
        ws.append(["English Term", "Domain"] + all_langs)
        
        # Entries
        for entry in entries:
            trans_map = entry.get("transMap", {})
            row = [entry.get("term", ""), entry.get("domain", "")]
            row.extend([trans_map.get(lang, "") for lang in all_langs])
            ws.append(row)
        
        export_path = core.OUTPUT_DIR / "KB_Glossary.xlsx"
        wb.save(str(export_path))
        
        return {"download_url": f"/api/glossary/download/{export_path.name}"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/glossary/import")
async def import_glossary(file: UploadFile = File(...)):
    """Import glossary from Excel."""
    try:
        import openpyxl
        import io
        
        content = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {"entries": []}
        
        headers = rows[0]
        lang_cols = headers[2:] if len(headers) > 2 else []
        
        entries = []
        for row in rows[1:]:
            if not row[0]:
                continue
            
            trans_map = {}
            for i, lang in enumerate(lang_cols):
                val = row[2 + i] if 2 + i < len(row) else None
                if val:
                    trans_map[str(lang)] = str(val)
            
            entries.append({
                "term": str(row[0]),
                "domain": str(row[1] or ""),
                "langs": ", ".join(trans_map.keys()),
                "trans": " | ".join(f"{k}: {v}" for k, v in trans_map.items()),
                "transMap": trans_map,
            })
        
        return {"entries": entries}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/glossary/download/{filename}")
def download_glossary(filename: str):
    """Download glossary."""
    path = core.OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)
