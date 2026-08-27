# ============================================================
# KB Translation System — FastAPI Backend
# RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi
#
# REST + SSE API over the interactive segment-editing dubbing
# workflow implemented in pipeline/segment_editor.py.
#
# Run:
#   uvicorn api.server:app --host 0.0.0.0 --port 8000
#   # or:  python api/server.py
#
# Sessions are held in an in-memory registry AND persisted to
# disk (output/sessions/<session_id>/session_state.json) via
# EditSession.save(). On a cold lookup the session is lazily
# re-loaded from disk, so the API survives restarts.
# ============================================================

from __future__ import annotations

import asyncio
import json
import queue
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# ── Make the project root importable when run as a script ─────
import sys
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.segment_editor import (  # noqa: E402
    EditSession,
    FitStrategy,
    SegmentAction,
    SegmentEditor,
)
from pipeline.logger import get_logger  # noqa: E402

log = get_logger("api")

# ── Storage locations ─────────────────────────────────────────
OUTPUT_DIR = _PROJECT_ROOT / "output"
SESSIONS_DIR = OUTPUT_DIR / "sessions"
UPLOAD_DIR = _PROJECT_ROOT / "input" / "uploads"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# App + shared editor
# ══════════════════════════════════════════════════════════════
app = FastAPI(
    title="KB Dubbing Pipeline API",
    version="1.0.0",
    description="REST/SSE API for the interactive 22-language dubbing workflow.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One shared editor — its model handles (ASR/Translator/TTS) are
# lazily instantiated and safe to reuse across requests.
_editor = SegmentEditor()

# In-memory session registry: session_id -> EditSession
_sessions: dict[str, EditSession] = {}
_sessions_lock = threading.Lock()

# Per-session lock so concurrent long-running ops don't clobber
# each other's state / disk writes.
_session_locks: dict[str, threading.Lock] = {}


def _get_glossary(tgt_lang: str) -> Optional["GlossaryManager"]:
    """Load the GlossaryManager (best effort). Returns the manager, not raw dict."""
    try:
        from pipeline.glossary import GlossaryManager
        return GlossaryManager()  # Return the manager instance, not .get_glossary()
    except Exception as e:  # noqa: BLE001
        log.warning(f"Glossary load failed for {tgt_lang}: {e}")
        return None


def _session_lock(session_id: str) -> threading.Lock:
    with _sessions_lock:
        lk = _session_locks.get(session_id)
        if lk is None:
            lk = threading.Lock()
            _session_locks[session_id] = lk
        return lk


def _load_session(session_id: str) -> EditSession:
    """
    Fetch a session from the in-memory registry, falling back to
    loading its persisted state from disk. Raises 404 if missing.
    """
    with _sessions_lock:
        sess = _sessions.get(session_id)
    if sess is not None:
        return sess

    session_dir = SESSIONS_DIR / session_id
    if not (session_dir / "session_state.json").exists():
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    try:
        sess = EditSession.load(session_dir)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load session: {e}")
    with _sessions_lock:
        _sessions[session_id] = sess
    return sess


def _get_segment_or_404(sess: EditSession, seg_id: int):
    for seg in sess.segments:
        if seg.id == seg_id:
            return seg
    raise HTTPException(status_code=404, detail=f"Segment {seg_id} not found")


def _session_payload(sess: EditSession) -> dict:
    """Full JSON representation of a session."""
    return {
        "session_id": sess.session_id,
        "video_path": sess.video_path,
        "source_lang": sess.source_lang,
        "target_lang": sess.target_lang,
        "output_dir": sess.output_dir,
        "video_duration": sess.video_duration,
        "step": sess.step,
        "created_at": sess.created_at,
        "updated_at": sess.updated_at,
        "stats": sess.stats(),
        "segments": [s.to_dict() for s in sess.segments],
    }


# ══════════════════════════════════════════════════════════════
# SSE helper
# ══════════════════════════════════════════════════════════════
def _sse(event: str, data: Any) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _run_with_progress(
    worker: Callable[[Callable[[int, int], None]], Any],
) -> StreamingResponse:
    """
    Run ``worker(progress_callback)`` in a background thread and stream
    progress + completion/error frames as Server-Sent Events.

    ``worker`` receives a ``progress_callback(done, total)`` it should call
    as it makes progress. Its return value is emitted in the ``done`` event.
    """
    q: "queue.Queue[tuple[str, Any]]" = queue.Queue()

    def progress_cb(done: int, total: int) -> None:
        q.put(("progress", {"done": done, "total": total}))

    def _target() -> None:
        try:
            result = worker(progress_cb)
            q.put(("done", result))
        except Exception as e:  # noqa: BLE001
            log.error(f"SSE worker failed: {e}")
            q.put(("error", {"detail": str(e)}))
        finally:
            q.put(("__END__", None))

    threading.Thread(target=_target, daemon=True).start()

    async def event_stream():
        yield _sse("start", {"ts": time.time()})
        loop = asyncio.get_event_loop()
        while True:
            event, data = await loop.run_in_executor(None, q.get)
            if event == "__END__":
                break
            yield _sse(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ══════════════════════════════════════════════════════════════
# Request models
# ══════════════════════════════════════════════════════════════
class ActionBody(BaseModel):
    action: str  # translate | skip | keep_orig | pending


class FitStrategyBody(BaseModel):
    strategy: str  # speed_up | extend_video | trim_audio | auto


class ApproveBody(BaseModel):
    approved: bool = True
    notes: str = ""


class EditBody(BaseModel):
    text: str


class StitchBody(BaseModel):
    use_extensions: bool = True
    mix_original_bgm: bool = True
    bgm_volume: float = 0.15


# ══════════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    with _sessions_lock:
        active = list(_sessions.keys())
    return {"status": "ok", "active_sessions": active}


# ══════════════════════════════════════════════════════════════
# POST /api/session/create — upload video, create session
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/create")
async def create_session(
    video: UploadFile = File(...),
    source_lang: str = Form("eng"),
    target_lang: str = Form(...),
    course_id: str = Form("course"),
):
    """Upload a video, run ASR, and create a new editing session."""
    # Persist the upload to disk
    safe_name = Path(video.filename or "upload.mp4").name
    dest = UPLOAD_DIR / f"{int(time.time())}_{safe_name}"
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(video.file, f)
    finally:
        await video.close()

    # Heavy work (ffmpeg + ASR) — run off the event loop
    def _create() -> EditSession:
        return _editor.create_session(
            video_path=str(dest),
            source_lang=source_lang,
            target_lang=target_lang,
            output_dir=str(OUTPUT_DIR),
            course_id=course_id,
        )

    try:
        sess = await asyncio.to_thread(_create)
    except Exception as e:  # noqa: BLE001
        log.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {e}")

    with _sessions_lock:
        _sessions[sess.session_id] = sess

    return {
        "session_id": sess.session_id,
        "step": sess.step,
        "video_duration": sess.video_duration,
        "num_segments": len(sess.segments),
        "segments": [s.to_dict() for s in sess.segments],
    }


# ══════════════════════════════════════════════════════════════
# GET /api/session/{session_id} — status + all segments
# ══════════════════════════════════════════════════════════════
@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    sess = _load_session(session_id)
    return _session_payload(sess)


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/translate — translate all (SSE)
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/translate")
def translate_all(session_id: str):
    sess = _load_session(session_id)
    glossary = _get_glossary(sess.target_lang)
    lock = _session_lock(session_id)

    def worker(progress_cb):
        with lock:
            # Ensure any still-PENDING segments are queued for translation
            _editor.set_all_translate(sess)
            _editor.translate_all(sess, glossary=glossary, progress_callback=progress_cb)
            return {"stats": sess.stats(), "step": sess.step}

    return _run_with_progress(worker)


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/translate/{seg_id} — single
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/translate/{seg_id}")
def translate_one(session_id: str, seg_id: int):
    sess = _load_session(session_id)
    seg = _get_segment_or_404(sess, seg_id)
    glossary = _get_glossary(sess.target_lang)
    lock = _session_lock(session_id)

    # Make sure the segment is marked for translation
    if seg.action == SegmentAction.PENDING:
        _editor.set_segment_action(sess, seg_id, SegmentAction.TRANSLATE)

    with lock:
        try:
            updated = _editor.translate_segment(sess, seg_id, glossary=glossary)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Translation failed: {e}")
    return {"segment": updated.to_dict()}


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/tts — TTS for all (SSE)
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/tts")
def tts_all(session_id: str):
    sess = _load_session(session_id)
    lock = _session_lock(session_id)

    def worker(progress_cb):
        with lock:
            _editor.synthesize_all(sess, progress_callback=progress_cb)
            return {"stats": sess.stats(), "step": sess.step}

    return _run_with_progress(worker)


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/tts/{seg_id} — single TTS
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/tts/{seg_id}")
def tts_one(session_id: str, seg_id: int):
    sess = _load_session(session_id)
    _get_segment_or_404(sess, seg_id)
    lock = _session_lock(session_id)
    with lock:
        try:
            updated = _editor.synthesize_segment(sess, seg_id)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    return {"segment": updated.to_dict()}


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/segment/{seg_id}/action
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/segment/{seg_id}/action")
def set_action(session_id: str, seg_id: int, body: ActionBody):
    sess = _load_session(session_id)
    _get_segment_or_404(sess, seg_id)
    try:
        action = SegmentAction(body.action)
    except ValueError:
        valid = [a.value for a in SegmentAction]
        raise HTTPException(status_code=400, detail=f"Invalid action. Use one of {valid}")
    _editor.set_segment_action(sess, seg_id, action)
    return {"segment": _get_segment_or_404(sess, seg_id).to_dict()}


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/segment/{seg_id}/fit-strategy
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/segment/{seg_id}/fit-strategy")
def set_fit_strategy(session_id: str, seg_id: int, body: FitStrategyBody):
    sess = _load_session(session_id)
    _get_segment_or_404(sess, seg_id)
    try:
        strategy = FitStrategy(body.strategy)
    except ValueError:
        valid = [s.value for s in FitStrategy]
        raise HTTPException(status_code=400, detail=f"Invalid strategy. Use one of {valid}")
    _editor.set_fit_strategy(sess, seg_id, strategy)
    return {"segment": _get_segment_or_404(sess, seg_id).to_dict()}


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/segment/{seg_id}/approve
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/segment/{seg_id}/approve")
def approve(session_id: str, seg_id: int, body: ApproveBody = ApproveBody()):
    sess = _load_session(session_id)
    _get_segment_or_404(sess, seg_id)
    if body.approved:
        _editor.approve_segment(sess, seg_id, notes=body.notes)
    else:
        _editor.reject_segment(sess, seg_id, notes=body.notes)
    return {"segment": _get_segment_or_404(sess, seg_id).to_dict()}


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/segment/{seg_id}/edit
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/segment/{seg_id}/edit")
def edit_translation(session_id: str, seg_id: int, body: EditBody):
    sess = _load_session(session_id)
    _get_segment_or_404(sess, seg_id)
    _editor.edit_translation(sess, seg_id, body.text)
    return {"segment": _get_segment_or_404(sess, seg_id).to_dict()}


# ══════════════════════════════════════════════════════════════
# POST /api/session/{session_id}/stitch — final assembly (SSE)
# ══════════════════════════════════════════════════════════════
@app.post("/api/session/{session_id}/stitch")
def stitch(session_id: str, body: StitchBody = StitchBody()):
    sess = _load_session(session_id)
    lock = _session_lock(session_id)

    def worker(progress_cb):
        with lock:
            progress_cb(0, 1)
            if body.use_extensions:
                result = _editor.stitch_with_extensions(
                    sess,
                    mix_original_bgm=body.mix_original_bgm,
                    bgm_volume=body.bgm_volume,
                )
            else:
                result = _editor.stitch(
                    sess,
                    mix_original_bgm=body.mix_original_bgm,
                    bgm_volume=body.bgm_volume,
                )
            progress_cb(1, 1)
            # Expose a convenient download URL
            result["download_url"] = f"/api/session/{session_id}/download"
            return result

    return _run_with_progress(worker)


# ══════════════════════════════════════════════════════════════
# GET /api/session/{session_id}/audio/{seg_id} — TTS audio
# ══════════════════════════════════════════════════════════════
@app.get("/api/session/{session_id}/audio/{seg_id}")
def get_audio(session_id: str, seg_id: int):
    sess = _load_session(session_id)
    seg = _get_segment_or_404(sess, seg_id)
    if not seg.tts_audio_path or not Path(seg.tts_audio_path).exists():
        raise HTTPException(status_code=404, detail="No TTS audio for this segment yet")
    return FileResponse(
        seg.tts_audio_path,
        media_type="audio/wav",
        filename=f"seg_{seg_id:04d}.wav",
    )


# ══════════════════════════════════════════════════════════════
# GET /api/session/{session_id}/thumbnail/{seg_id} — frame
# ══════════════════════════════════════════════════════════════
@app.get("/api/session/{session_id}/thumbnail/{seg_id}")
def get_thumbnail(session_id: str, seg_id: int):
    sess = _load_session(session_id)
    seg = _get_segment_or_404(sess, seg_id)
    # Lazily extract the thumbnail on first request
    if not seg.thumbnail_path or not Path(seg.thumbnail_path).exists():
        try:
            _editor.extract_thumbnail(sess, seg_id)
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
# GET /api/session/{session_id}/download — final video
# ══════════════════════════════════════════════════════════════
@app.get("/api/session/{session_id}/download")
def download(session_id: str):
    sess = _load_session(session_id)
    expected = (
        Path(sess.output_dir)
        / sess.target_lang
        / f"{Path(sess.video_path).stem}_{sess.target_lang}.mp4"
    )
    if not expected.exists():
        raise HTTPException(
            status_code=404,
            detail="Final video not found. Run /stitch first.",
        )
    return FileResponse(
        str(expected),
        media_type="video/mp4",
        filename=expected.name,
    )


# ══════════════════════════════════════════════════════════════
# Web UI — adapter router (/api/sessions/...) + static files
#
# The frontend in web/ was written against a poll-based
# /api/sessions/... convention. The adapter router in
# api/web_routes.py exposes exactly those routes on top of the same
# shared editor + session registry. It MUST be included before the
# catch-all StaticFiles mount so /api/* is never shadowed.
# ══════════════════════════════════════════════════════════════
try:
    from api.web_routes import router as web_router  # noqa: E402

    app.include_router(web_router)
    log.info("Web UI adapter router mounted (/api/sessions/...)")
except Exception as e:  # noqa: BLE001
    log.warning(f"Web UI adapter router not mounted: {e}")

# Serve the static web UI from web/ at the site root. Mounted LAST so
# every real /api/* route above wins; StaticFiles only handles the
# remaining paths (/, /index.html, /app.js, /style.css, ...).
from fastapi.staticfiles import StaticFiles  # noqa: E402

_WEB_DIR = _PROJECT_ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
    log.info(f"Static web UI mounted from {_WEB_DIR}")
else:
    log.warning(f"web/ directory not found at {_WEB_DIR} — UI will not be served")


# ══════════════════════════════════════════════════════════════
# Entrypoint
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
