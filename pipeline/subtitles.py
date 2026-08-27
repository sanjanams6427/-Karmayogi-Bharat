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
# across segment boundaries.
# Covers: Tamil dangling suffixes (க், ஸ்டர், ட்டி, ச்சான், மற்றும்),
# Devanagari/Indic punctuation, and common Latin punctuation.
_SUB_ARTIFACT_RE = re.compile(
    r'^(?:'
    r'[\u0b95-\u0bb9][\u0bcd]\s+'                        # bare Tamil consonant + virama only (e.g. க் )
    r'|[\u0b95-\u0bb9][\u0bcd][\u0b95-\u0bb9][\u0bcd]\s+'  # two-consonant virama cluster (e.g. ப்ப் )
    r'|[\u0b95-\u0bb9][\u0bcd][\u0b95-\u0bb9][\u0bbe-\u0bc8\u0bca-\u0bcc\u0bcd][\u0b95-\u0bb9\u0bbe-\u0bc8\u0bca-\u0bcc\u0bcd]*\s+'  # consonant+virama+consonant+vowel... (mid-word tail like ப்படிப்பு)
    r'|[\)\]},;.\u0964\u0965]+\s+'                        # punctuation artifacts
    r'|(?:\u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd|\u0bae\u0bc7\u0bb2\u0bc1\u0bae\u0bcd|\u0b86\u0ba9\u0bbe\u0bb2\u0bcd)\s+'  # Tamil sentence-initial conjunctions
    r')'
)

# Per-language post-translation fixup table.
# Keyed by tgt_lang. Each entry is a list of (pattern, replacement) pairs
# applied in order via re.sub. Used to correct known MT artifacts that
# survive all translation-time guards (wrong terminology, stray words, etc.).
_SUB_FIXUPS: dict[str, list[tuple[str, str]]] = {
    "tam": [
        # Fusion fix: மாண்புமிகுடியரசுத் → மாண்புமிகு குடியரசுத் (safety net for stale cache)
        ('\u0bae\u0bbe\u0ba3\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bc1\u0b9f\u0bbf\u0baf\u0bb0\u0b9a\u0bc1\u0ba4\u0bcd',
         '\u0bae\u0bbe\u0ba3\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bc1 \u0b95\u0bc1\u0b9f\u0bbf\u0baf\u0bb0\u0b9a\u0bc1\u0ba4\u0bcd'),
        # Time format: 10100 மணிநேரமும் → 1010 மணிநேரமும் (military time ASR corruption)
        (r'10100\s+\u0bae\u0ba3\u0bbf\u0ba8\u0bc7\u0bb0\u0bae\u0bc1\u0bae\u0bcd',
         '1010 \u0bae\u0ba3\u0bbf\u0ba8\u0bc7\u0bb0\u0bae\u0bc1\u0bae\u0bcd'),
        # Seg 4: "ஸ்டர்" → "கிளஸ்டர்" (cluster — ASR split dropped "கிளஸ்" prefix)
        (r'^\u0bb8\u0bcd\u0b9f\u0bb0\u0bcd\s+', '\u0b95\u0bbf\u0bb3\u0bcd\u0b9a\u0bcd\u0b9f\u0bb0\u0bcd '),
        # Seg 8: leading "க் கடன்கள்" → "தருண் கடன்கள்"
        (r'^\u0b95\u0bcd\s+\u0b95\u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bcd',
         '\u0ba4\u0bb0\u0bc1\u0ba3\u0bcd \u0b95\u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bcd'),
        # Seg 11: leading "க் கடன்கள்" (term loans context) → "காலக் கடன்கள்"
        # Only when followed by ரொக்கக் (cash credit) — distinguishes from seg 8
        (r'^\u0b95\u0bcd\s+(\u0b95\u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bcd,\s*\u0bb0\u0bca\u0b95\u0bcd\u0b95\u0b95\u0bcd)',
         '\u0b95\u0bbe\u0bb2\u0b95\u0bcd \u0b95\u0b9f\u0ba9\u0bcd\u0b95\u0bb3\u0bcd, \u0bb0\u0bca\u0b95\u0bcd\u0b95\u0b95\u0bcd'),
        # Seg 13: "உயர்வுகள்." standalone artifact → remove
        (r'^\u0b89\u0baf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bcd\.\s*', ''),
        # Seg 16: leading "ச்சான்றிதழ்கள்" → "சுய-சான்றிதழ்கள்"
        (r'^\u0b9a\u0bcd\u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bbf\u0ba4\u0bb4\u0bcd\u0b95\u0bb3\u0bcd',
         '\u0b9a\u0bc1\u0baf-\u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bbf\u0ba4\u0bb4\u0bcd\u0b95\u0bb3\u0bcd'),
        # Seg 17: "சட்டம்." as standalone sentence-initial artifact → remove
        (r'^\u0b9a\u0b9f\u0bcd\u0b9f\u0bae\u0bcd\.\s*', ''),
        # Seg 21: leading "க் கடனுக்கான" → "முத்ரா கடனுக்கான"
        (r'^\u0b95\u0bcd\s+\u0b95\u0b9f\u0ba9\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9',
         '\u0bae\u0bc1\u0ba4\u0bcd\u0bb0\u0bbe \u0b95\u0b9f\u0ba9\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9'),
        # Seg 22: leading "மற்றும் சிறு" → "நுண் மற்றும் சிறு"
        (r'^\u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd\s+\u0b9a\u0bbf\u0bb1\u0bc1',
         '\u0ba8\u0bc1\u0ba3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bc1'),
        # Seg 28: "க்கடனின்" (fused) → "கடனின்"
        (r'^\u0b95\u0bcd\u0b95\u0b9f\u0ba9\u0bbf\u0ba9\u0bcd',
         '\u0b95\u0b9f\u0ba9\u0bbf\u0ba9\u0bcd'),
        # Seg 29: leading "ட்டி கடன்" → "தகுதியான கடன்"
        (r'^\u0b9f\u0bcd\u0b9f\u0bbf\s+\u0b95\u0b9f\u0ba9\u0bcd',
         '\u0ba4\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0b95\u0b9f\u0ba9\u0bcd'),
        # Seg 29: fused "இணைக்கப்பட்டெபிட்" → "இணைக்கப்பட்ட டெபிட்"
        ('\u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc6\u0baa\u0bbf\u0b9f\u0bcd',
         '\u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9f\u0bc6\u0baa\u0bbf\u0b9f\u0bcd'),
        # Seg 25: leading "15 சதவீதம்." dangling number → add context
        (r'^15\s+\u0b9a\u0ba4\u0bb5\u0bc0\u0ba4\u0bae\u0bcd\.\s*',
         '\u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1 \u0ba4\u0bc7\u0bb5\u0bc8 15 \u0b9a\u0ba4\u0bb5\u0bc0\u0ba4\u0bae\u0bcd. '),
    ],
    "hin": [],
    "kan": [],
    "mal": [],
    "tel": [],
    "urd": [],
    "guj": [],
    "ben": [],
    "asm": [],
    "pan": [],
    "ory": [],
    "mar": [],



}


def _apply_sub_fixups(text: str, tgt_lang: str) -> str:
    """Apply per-language post-translation fixups to subtitle text."""
    for pattern, replacement in _SUB_FIXUPS.get(tgt_lang, []):
        text = re.sub(pattern, replacement, text)
    return text


def _clean_sub_text(text: str, tgt_lang: str = "") -> str:
    """Strip leading punctuation/fragment artifacts (loop until stable), apply fixups, collapse whitespace."""
    text = " ".join(text.split())
    # Loop: stripping one artifact may expose another (e.g. ப்படிப்பு மற்றும் → மற்றும் → <clean>)
    for _ in range(4):
        stripped = _SUB_ARTIFACT_RE.sub('', text)
        if stripped == text:
            break
        text = stripped.strip()
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
        end = max(end, start + 0.5)  # guard: end must always be > start
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
        if not txt:
            # Translation failed — fall back to source text so subtitles are not blank
            src = s.get("src_text", "")
            txt = _clean_sub_text(src, "") if src else ""
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
        if not txt:
            src = s.get("src_text", "")
            txt = _clean_sub_text(src, "") if src else ""
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
