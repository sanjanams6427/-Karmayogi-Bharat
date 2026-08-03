# ============================================================
# Subtitle / SRT Generator
# KB tender Section 4 Financial Schedule — sub-titling/captioning
# Generates SRT and VTT subtitle files from translated segments.
# Also burns subtitles into video (optional).
# ============================================================

import subprocess
from pathlib import Path
from .lang_config import LANG_NAMES
from .logger import get_logger

log = get_logger("subtitles")

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"


def _seconds_to_srt_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_vtt_time(seconds: float) -> str:
    return _seconds_to_srt_time(seconds).replace(",", ".")


def generate_srt(segments: list[dict], output_path: str) -> str:
    """
    Generate SRT subtitle file from translated segments.
    segments: list of {id, start, end, text}
    """
    lines = []
    idx = 1
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        start = _seconds_to_srt_time(seg.get("start", 0))
        end   = _seconds_to_srt_time(seg.get("end",   0))
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
        idx += 1
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    log.info(f"SRT generated ({idx-1} entries) → {output_path}")
    return output_path


def generate_vtt(segments: list[dict], output_path: str) -> str:
    """Generate WebVTT subtitle file from translated segments."""
    lines = ["WEBVTT", ""]
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        start = _seconds_to_vtt_time(seg.get("start", 0))
        end   = _seconds_to_vtt_time(seg.get("end",   0))
        lines.append(f"{start} --> {end}\n{text}\n")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    log.info(f"VTT generated → {output_path}")
    return output_path


def generate_subtitles(
    segments: list[dict],
    output_dir: str,
    course_id: str,
    tgt_lang: str,
    formats: list[str] = ("srt", "vtt"),
) -> dict[str, str]:
    """
    Generate subtitle files in requested formats.
    Returns {format: path}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lang_name = LANG_NAMES.get(tgt_lang, tgt_lang)
    results = {}
    if "srt" in formats:
        srt_path = str(out_dir / f"{course_id}_{tgt_lang}.srt")
        generate_srt(segments, srt_path)
        results["srt"] = srt_path
    if "vtt" in formats:
        vtt_path = str(out_dir / f"{course_id}_{tgt_lang}.vtt")
        generate_vtt(segments, vtt_path)
        results["vtt"] = vtt_path
    log.info(f"Subtitles [{lang_name}] → {list(results.values())}")
    return results


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
) -> str:
    """
    Burn (hardcode) SRT subtitles into video using ffmpeg.
    Output is a new MP4 with subtitles embedded in the video stream.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # Escape Windows path backslashes for ffmpeg subtitles filter
    srt_escaped = str(Path(srt_path).resolve()).replace("\\", "/").replace(":", "\\:")
    ret = subprocess.run(
        [_FFMPEG, "-y", "-i", str(video_path),
         "-vf", f"subtitles='{srt_escaped}'",
         "-c:a", "copy", str(output_path), "-loglevel", "error"],
        capture_output=True,
    ).returncode
    if ret != 0:
        log.error(f"Subtitle burn failed for {Path(video_path).name}")
        raise RuntimeError(f"ffmpeg subtitle burn failed: {video_path}")
    log.info(f"Subtitles burned → {output_path}")
    return output_path


def embed_subtitles_soft(
    video_path: str,
    srt_path: str,
    output_path: str,
    lang: str = "hin",
) -> str:
    """
    Embed SRT as a soft subtitle track (selectable, not burned in).
    Viewer can toggle on/off.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    ret = subprocess.run(
        [_FFMPEG, "-y",
         "-i", str(video_path),
         "-i", str(srt_path),
         "-c:v", "copy", "-c:a", "copy",
         "-c:s", "mov_text",
         "-metadata:s:s:0", f"language={lang}",
         "-map", "0:v", "-map", "0:a", "-map", "1:0",
         str(output_path), "-loglevel", "error"],
        capture_output=True,
    ).returncode
    if ret != 0:
        log.warning(f"Soft subtitle embed failed, falling back to burn: {Path(video_path).name}")
        return burn_subtitles(video_path, srt_path, output_path)
    log.info(f"Soft subtitles embedded → {output_path}")
    return output_path
