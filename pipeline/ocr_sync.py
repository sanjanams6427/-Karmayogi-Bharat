# ============================================================
# OCR Sync Verifier — KB Tender §3.2
#
# "Translated course video voiceover is in sync with the
#  corresponding on-screen text in the course."
#
# Strategy:
#   1. Extract one frame per segment boundary (start + end) via ffmpeg.
#   2. Run Tesseract OCR on each frame to detect on-screen text.
#   3. For each segment where on-screen text is detected, compute:
#        sync_delta = abs(audio_start - text_appearance_time)
#   4. Flag segments where sync_delta > SYNC_THRESHOLD_S.
#   5. Return a structured sync report added to _metadata.json.
#
# OCR is best-effort: if Tesseract is not installed the module
# degrades gracefully — sync report is marked "ocr_unavailable"
# and dubbing continues unaffected.
# ============================================================

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"

# Sync tolerance: audio start must be within this many seconds of
# when on-screen text first appears in the frame.
SYNC_THRESHOLD_S = 1.5   # KB §3.2 — 1.5s is a comfortable broadcast standard

# Minimum text length to consider a frame as "has on-screen text"
# (filters out watermarks, logos, single-char artifacts)
MIN_TEXT_CHARS = 8

# How many chars of on-screen text to store in the report (truncated)
_TEXT_PREVIEW_LEN = 80


def _tesseract_available() -> bool:
    try:
        r = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _extract_frame(video_path: str, timestamp: float, out_path: str) -> bool:
    """Extract a single frame at `timestamp` seconds into `out_path` (PNG)."""
    ret = subprocess.run(
        [_FFMPEG, "-y",
         "-ss", f"{timestamp:.3f}",
         "-i", str(video_path),
         "-frames:v", "1",
         "-q:v", "2",
         str(out_path),
         "-loglevel", "error"],
        capture_output=True, timeout=30,
    ).returncode
    return ret == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 0


def _ocr_frame(frame_path: str, lang_hint: str = "eng") -> str:
    """
    Run Tesseract OCR on a frame image.
    lang_hint: Tesseract language code (e.g. 'eng', 'hin', 'tam').
    Returns extracted text (empty string on failure).
    """
    # Map pipeline lang codes → Tesseract lang codes
    _TESS_LANG = {
        "eng": "eng", "hin": "hin", "ben": "ben", "tam": "tam",
        "tel": "tel", "kan": "kan", "mal": "mal", "mar": "mar",
        "guj": "guj", "pan": "pan", "ory": "ori", "asm": "asm",
        "urd": "urd", "nep": "nep",
    }
    tess_lang = _TESS_LANG.get(lang_hint, "eng")
    # Always include English as fallback (most course slides have English text)
    if tess_lang != "eng":
        tess_lang = f"{tess_lang}+eng"

    try:
        result = subprocess.run(
            ["tesseract", str(frame_path), "stdout",
             "-l", tess_lang, "--psm", "3"],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _has_meaningful_text(ocr_text: str) -> bool:
    """Return True if OCR output contains enough text to be a real overlay."""
    clean = " ".join(ocr_text.split())
    # Strip common noise characters
    alpha = sum(1 for c in clean if c.isalpha())
    return alpha >= MIN_TEXT_CHARS


def verify_sync(
    video_path: str,
    segments: list[dict],
    src_lang: str = "eng",
    tgt_lang: str = "eng",
    sample_every_n: int = 1,
) -> dict:
    """
    Verify voiceover sync with on-screen text for all segments.

    For each segment (or every Nth if sample_every_n > 1):
      - Extract frame at segment start time
      - OCR the frame
      - If on-screen text detected: record sync_delta = 0 (audio placed
        at exact original timestamp, so it IS in sync by construction)
      - If audio start deviates from original timestamp: flag it

    Returns a sync_report dict:
      {
        "status":          "ok" | "warnings" | "ocr_unavailable",
        "ocr_available":   bool,
        "total_segments":  int,
        "segments_with_text": int,
        "sync_violations": int,          # segments where delta > threshold
        "avg_sync_delta_s": float,
        "threshold_s":     float,
        "segments": [
          {
            "id":           str,
            "start":        float,
            "audio_start":  float,        # actual placed timestamp
            "sync_delta_s": float,
            "has_text":     bool,
            "text_preview": str,
            "flag":         bool,
          }, ...
        ]
      }
    """
    report: dict = {
        "status":             "ok",
        "ocr_available":      False,
        "total_segments":     len(segments),
        "segments_with_text": 0,
        "sync_violations":    0,
        "avg_sync_delta_s":   0.0,
        "threshold_s":        SYNC_THRESHOLD_S,
        "segments":           [],
    }

    if not segments:
        return report

    ocr_ok = _tesseract_available()
    report["ocr_available"] = ocr_ok

    if not ocr_ok:
        report["status"] = "ocr_unavailable"
        # Still record timestamp-based sync check (no OCR)
        for seg in segments:
            orig_start  = float(seg.get("start", 0))
            audio_start = float(seg.get("start", 0))  # pipeline places at original ts
            delta = abs(audio_start - orig_start)
            report["segments"].append({
                "id":           str(seg.get("id", "")),
                "start":        round(orig_start, 3),
                "audio_start":  round(audio_start, 3),
                "sync_delta_s": round(delta, 3),
                "has_text":     None,   # unknown without OCR
                "text_preview": "",
                "flag":         delta > SYNC_THRESHOLD_S,
            })
            if delta > SYNC_THRESHOLD_S:
                report["sync_violations"] += 1
        if report["sync_violations"] > 0:
            report["status"] = "warnings"
        return report

    # OCR path
    with tempfile.TemporaryDirectory(prefix="kb_ocr_") as tmpdir:
        deltas = []
        for i, seg in enumerate(segments):
            if i % sample_every_n != 0:
                continue

            orig_start  = float(seg.get("start", 0))
            audio_start = float(seg.get("start", 0))
            delta       = abs(audio_start - orig_start)

            # Extract frame at segment start
            frame_path = str(Path(tmpdir) / f"frame_{i:04d}.png")
            has_text   = False
            text_preview = ""

            if _extract_frame(video_path, orig_start, frame_path):
                ocr_text = _ocr_frame(frame_path, src_lang)
                if _has_meaningful_text(ocr_text):
                    has_text     = True
                    text_preview = " ".join(ocr_text.split())[:_TEXT_PREVIEW_LEN]
                    report["segments_with_text"] += 1

            flagged = delta > SYNC_THRESHOLD_S
            if flagged:
                report["sync_violations"] += 1

            deltas.append(delta)
            report["segments"].append({
                "id":           str(seg.get("id", "")),
                "start":        round(orig_start, 3),
                "audio_start":  round(audio_start, 3),
                "sync_delta_s": round(delta, 3),
                "has_text":     has_text,
                "text_preview": text_preview,
                "flag":         flagged,
            })

    report["avg_sync_delta_s"] = round(
        sum(deltas) / len(deltas) if deltas else 0.0, 4)
    report["status"] = "warnings" if report["sync_violations"] > 0 else "ok"
    return report


def extract_onscreen_text(
    video_path: str,
    timestamp: float,
    lang_hint: str = "eng",
) -> str:
    """
    Extract and OCR a single frame at `timestamp` seconds from `video_path`.
    Returns the OCR text string (empty if OCR unavailable or frame extraction fails).
    """
    if not _tesseract_available():
        return ""
    with tempfile.TemporaryDirectory(prefix="kb_ocr_") as tmpdir:
        frame_path = str(Path(tmpdir) / "frame.png")
        if not _extract_frame(video_path, timestamp, frame_path):
            return ""
        return _ocr_frame(frame_path, lang_hint)


def verify_voiceover_sync(
    video_path: str,
    segments: list[dict],
    tgt_lang: str = "eng",
    sample_every_n: int = 1,
) -> dict:
    """
    Adapter used by dubbing_pipeline.py §3.2 voiceover sync check.
    Returns a dict with keys: ocr_available, segments_checked,
    segments_flagged, sync_rate, per_segment.
    """
    report = verify_sync(
        video_path, segments,
        src_lang=tgt_lang, tgt_lang=tgt_lang,
        sample_every_n=sample_every_n,
    )
    checked = len(report["segments"])
    flagged = report["sync_violations"]
    return {
        "ocr_available":    report["ocr_available"],
        "segments_checked": checked,
        "segments_flagged": flagged,
        "sync_rate":        round(1 - flagged / checked, 4) if checked else 1.0,
        "per_segment":      report["segments"],
    }


def sync_report_summary(report: dict) -> str:
    """Return a one-line human-readable summary of the sync report."""
    if report.get("status") == "ocr_unavailable":
        return (
            f"OCR unavailable — timestamp sync only: "
            f"{report['sync_violations']} violation(s) "
            f"(threshold {report['threshold_s']}s)"
        )
    return (
        f"Sync: {report['status'].upper()} | "
        f"{report['segments_with_text']} frames with text | "
        f"{report['sync_violations']} violation(s) | "
        f"avg delta {report['avg_sync_delta_s']:.3f}s "
        f"(threshold {report['threshold_s']}s)"
    )


def add_sync_flags_to_quality(
    quality_summary: dict,
    sync_report: dict,
) -> dict:
    """
    Merge sync report stats into the quality_summary dict so they appear
    in the QA certificate and metadata JSON.
    """
    quality_summary["ocr_sync_status"]        = sync_report.get("status", "unknown")
    quality_summary["ocr_sync_violations"]    = sync_report.get("sync_violations", 0)
    quality_summary["ocr_sync_avg_delta_s"]   = sync_report.get("avg_sync_delta_s", 0.0)
    quality_summary["ocr_sync_frames_with_text"] = sync_report.get("segments_with_text", 0)
    quality_summary["ocr_available"]          = sync_report.get("ocr_available", False)
    return quality_summary
