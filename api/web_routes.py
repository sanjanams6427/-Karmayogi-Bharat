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
    expected = (
        Path(sess.output_dir)
        / sess.target_lang
        / f"{Path(sess.video_path).stem}_{sess.target_lang}.mp4"
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
