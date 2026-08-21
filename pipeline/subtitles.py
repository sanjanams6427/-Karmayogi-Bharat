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
_SUB_ARTIFACT_RE = re.compile(r'^[\)\]},;.\u0964\u0965]+\s+')

# Per-language post-translation fixup table.
# Keyed by tgt_lang. Each entry is a list of (pattern, replacement) pairs
# applied in order via re.sub. Used to correct known MT artifacts that
# survive all translation-time guards (wrong terminology, stray words, etc.).
_SUB_FIXUPS: dict[str, list[tuple[str, str]]] = {
    "hin": [
        # Seg 4: "transpiration" → IndicTrans2 outputs "पसीना आना" (sweating).
        # Correct term is वाष्पोत्सर्जन.
        ('पसीना आना', 'वाष्पोत्सर्जन'),
        # Seg 6: "sleet" → IndicTrans2 outputs "कम" (less/low) — stray artifact.
        # Remove isolated "कम" between comma-separated precipitation items.
        (r',\s*कम,', ','),
        # Seg 3: "पानी को गर्म करता" missing subject सूर्य.
        # Fires when sentence starts with a locative phrase ending in में
        # and contains "पानी को गर्म करता" with no subject before it.
        (r'^(\S+ों.*?में\s+)(पानी को गर्म करता)',
         'सूर्य ' + r'\2'),
    ],
}


def _apply_sub_fixups(text: str, tgt_lang: str) -> str:
    """Apply per-language post-translation fixups to subtitle text."""
    for pattern, replacement in _SUB_FIXUPS.get(tgt_lang, []):
        text = re.sub(pattern, replacement, text)
    return text


def _clean_sub_text(text: str, tgt_lang: str = "") -> str:
    """Strip leading punctuation artifacts, apply fixups, collapse whitespace."""
    text = " ".join(text.split())
    text = _SUB_ARTIFACT_RE.sub('', text)
    if tgt_lang:
        text = _apply_sub_fixups(text, tgt_lang)
    return text.strip()


# Max chars per subtitle line — 42 chars fits ~2 lines of Devanagari on a
# standard 1080p screen. Recursive splitting ensures no line exceeds this.
_MAX_SUB_LINE = 42


def _wrap_subtitle(text: str, max_chars: int = _MAX_SUB_LINE) -> str:
    """
    Recursively wrap subtitle text so every line is <= max_chars.
    Splits only at word boundaries (spaces). Never breaks mid-word.
    Finds the split point closest to the midpoint of the text.
    """
    if len(text) <= max_chars:
        return text
    words = text.split(' ')
    if len(words) < 2:
        return text  # single word longer than max — can't split
    mid = len(text) // 2
    best_pos = None
    best_dist = len(text)
    pos = 0
    for w in words[:-1]:
        pos += len(w)
        dist = abs(pos - mid)
        if pos >= 10 and (len(text) - pos - 1) >= 10 and dist < best_dist:
            best_dist = dist
            best_pos = pos
        pos += 1  # account for the space
    if best_pos is None:
        return text
    left  = text[:best_pos]
    right = text[best_pos + 1:]
    return _wrap_subtitle(left, max_chars) + '\n' + _wrap_subtitle(right, max_chars)


def _seconds_to_srt_time(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_vtt_time(seconds: float) -> str:
    return _seconds_to_srt_time(seconds).replace(",", ".")


# Reading speed for Devanagari/Indic subtitles: ~17 chars/second is comfortable.
# Minimum display time: 1.5s regardless of text length.
_CHARS_PER_SEC  = 17.0
_MIN_DISPLAY_S  = 1.5
# Gap to leave before the next subtitle starts (seconds)
_SUBTITLE_GAP_S = 0.04


def _reading_duration(text: str) -> float:
    """Minimum seconds needed to read `text` comfortably."""
    chars = len(text.replace('\n', ' '))
    return max(_MIN_DISPLAY_S, chars / _CHARS_PER_SEC)


def _adjust_timings(segs: list[dict], video_duration: float) -> list[tuple[float, float]]:
    """
    Return (start, end) pairs with end times extended to cover reading time.
    End is clamped to (next_start - gap) so subtitles never overlap.
    Last segment end is extended to video_duration if available.
    """
    timings = []
    n = len(segs)
    for i, seg in enumerate(segs):
        start    = seg["start"]
        orig_end = seg["end"]
        text     = seg.get("_display_text", "")
        needed   = start + _reading_duration(text)
        # Hard ceiling: next segment start minus gap
        if i < n - 1:
            next_start = segs[i + 1]["start"]
            ceiling    = next_start - _SUBTITLE_GAP_S
        else:
            ceiling = video_duration if video_duration > orig_end else orig_end + 2.0
        end = min(max(orig_end, needed), ceiling)
        # Last segment: always extend to video_duration
        if i == n - 1 and video_duration > end:
            end = video_duration
        timings.append((start, end))
    return timings


def generate_srt(segments: list[dict], output_path: str,
                 video_duration: float = 0.0, tgt_lang: str = "") -> str:
    """
    Generate SRT subtitle file from translated segments.
    End times are extended to cover reading time of the translated text,
    clamped to the next segment's start so subtitles never overlap.
    """
    lines = []
    idx   = 1
    # Pre-compute display text so _adjust_timings can use it
    segs  = []
    for s in segments:
        txt = _clean_sub_text(s.get("text", ""), tgt_lang)
        if txt:
            segs.append({**s, "_display_text": txt})
    timings = _adjust_timings(segs, video_duration)
    for i, (seg, (start, end)) in enumerate(zip(segs, timings)):
        text    = _wrap_subtitle(seg["_display_text"])
        start_s = _seconds_to_srt_time(start)
        end_s   = _seconds_to_srt_time(end)
        lines.append(f"{idx}\r\n{start_s} --> {end_s}\r\n{text}\r\n")
        idx += 1
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(("\r\n".join(lines)).encode("utf-8-sig"))
    log.info(f"SRT generated ({idx-1} entries) → {output_path}")
    return output_path


def generate_vtt(segments: list[dict], output_path: str,
                 video_duration: float = 0.0, tgt_lang: str = "") -> str:
    """Generate WebVTT subtitle file from translated segments."""
    lines = ["WEBVTT", ""]
    segs  = []
    for s in segments:
        txt = _clean_sub_text(s.get("text", ""), tgt_lang)
        if txt:
            segs.append({**s, "_display_text": txt})
    timings = _adjust_timings(segs, video_duration)
    for seg, (start, end) in zip(segs, timings):
        text    = _wrap_subtitle(seg["_display_text"])
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
    Returns {format: path}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lang_name = LANG_NAMES.get(tgt_lang, tgt_lang)
    results = {}
    if "srt" in formats:
        srt_path = str(out_dir / f"{course_id}_{tgt_lang}.srt")
        generate_srt(segments, srt_path, video_duration=video_duration, tgt_lang=tgt_lang)
        results["srt"] = srt_path
    if "vtt" in formats:
        vtt_path = str(out_dir / f"{course_id}_{tgt_lang}.vtt")
        generate_vtt(segments, vtt_path, video_duration=video_duration, tgt_lang=tgt_lang)
        results["vtt"] = vtt_path
    log.info(f"Subtitles [{lang_name}] → {list(results.values())}")
    return results


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
) -> str:
    """Burn (hardcode) SRT subtitles into video using ffmpeg."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
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
    """Embed SRT as a soft subtitle track (selectable, not burned in)."""
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
