# ============================================================
# Subtitle / SRT Generator
# KB tender Section 4 Financial Schedule — sub-titling/captioning
# Generates SRT and VTT subtitle files from translated segments.
# Also burns subtitles into video (optional).
# ============================================================

import subprocess, re
from pathlib import Path
from .lang_config import LANG_NAMES
from .logger import get_logger

log = get_logger("subtitles")

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"

# Subtitle text cleanup: strip leading boundary artifacts that ASR bleeds
# across segment boundaries (e.g. ") ", ", ", ". ", "। ")
_SUB_ARTIFACT_RE = re.compile(r'^[)\]},;.\u0964\u0965]+\s+')


def _clean_sub_text(text: str) -> str:
    """Strip leading punctuation artifacts and collapse whitespace."""
    text = " ".join(text.split())          # collapse embedded newlines/spaces
    text = _SUB_ARTIFACT_RE.sub('', text)  # strip leading boundary artifacts
    return text.strip()


def _seconds_to_srt_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_vtt_time(seconds: float) -> str:
    return _seconds_to_srt_time(seconds).replace(",", ".")


def generate_srt(segments: list[dict], output_path: str,
                 video_duration: float = 0.0) -> str:
    """
    Generate SRT subtitle file from translated segments.
    video_duration: if provided, extends the last segment's end to cover full audio.
    """
    lines = []
    idx = 1
    segs = [s for s in segments if _clean_sub_text(s.get("text", ""))]
    for i, seg in enumerate(segs):
        text  = _clean_sub_text(seg.get("text", ""))
        start = seg.get("start", 0)
        end   = seg.get("end",   0)
        # Extend last segment to video duration so final words aren’t cut off
        if i == len(segs) - 1 and video_duration > end:
            end = video_duration
        start_s = _seconds_to_srt_time(start)
        end_s   = _seconds_to_srt_time(end)
        lines.append(f"{idx}\r\n{start_s} --> {end_s}\r\n{text}\r\n")
        idx += 1
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(("\r\n".join(lines)).encode("utf-8-sig"))
    log.info(f"SRT generated ({idx-1} entries) → {output_path}")
    return output_path


def generate_vtt(segments: list[dict], output_path: str,
                 video_duration: float = 0.0) -> str:
    """Generate WebVTT subtitle file from translated segments."""
    lines = ["WEBVTT", ""]
    segs = [s for s in segments if _clean_sub_text(s.get("text", ""))]
    for i, seg in enumerate(segs):
        text  = _clean_sub_text(seg.get("text", ""))
        start = seg.get("start", 0)
        end   = seg.get("end",   0)
        if i == len(segs) - 1 and video_duration > end:
            end = video_duration
        start_s = _seconds_to_vtt_time(start)
        end_s   = _seconds_to_vtt_time(end)
        lines.append(f"{start_s} --> {end_s}\n{text}\n")
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
    video_duration: float = 0.0,
) -> dict[str, str]:
    """
    Generate subtitle files in requested formats.
    video_duration: pass dubbed video duration to extend last subtitle to end of video.
    Returns {format: path}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lang_name = LANG_NAMES.get(tgt_lang, tgt_lang)
    results = {}
    if "srt" in formats:
        srt_path = str(out_dir / f"{course_id}_{tgt_lang}.srt")
        generate_srt(segments, srt_path, video_duration=video_duration)
        results["srt"] = srt_path
    if "vtt" in formats:
        vtt_path = str(out_dir / f"{course_id}_{tgt_lang}.vtt")
        generate_vtt(segments, vtt_path, video_duration=video_duration)
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
