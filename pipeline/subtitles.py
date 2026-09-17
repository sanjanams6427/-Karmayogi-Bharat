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
    "hin": [
        # Strip छे. / छे sentence-initial Maithili copula artifact
        (r'^\u091b\u0947\.?\s+', ''),
        # Strip OCR page-reference artifacts from slide images picked up by ASR
        # e.g. "अब समारोहक किछु विवरण" → "अब समारोह के कुछ विवरण"
        (r'\u0938\u092e\u093e\u0930\u094b\u0939\u0915\s+\u0915\u093f\u091b\u0941', 'समारोह के कुछ'),
        # Strip Maithili morphemes that survived drift guard
        (r'\u0913\s+\u092b\u094b\u091f\u094b\s+\u0916\u093f\u091a\u092f\u092c\u093e\u0915[^\u0964\u0965.!?]*',
         'फ़ोटो खिंचवाने के अवसर के लिए'),
        (r'\u0915\u0915\u094d\u0937\u092e\u0947(?=[\s\u0964\u0965]|$)', 'बैठक कक्ष में'),
        (r'\u0906\u092c\s+\u092e\u093e\u0928\u0928\u0940\u092f(?=[\s\u0964\u0965]|$)', 'अब माननीय'),
        (r'\u0938\u092e\u092f\u092e\u0947(?=[\s\u0964\u0965]|$)', 'समय में'),
        (r'\u0915\u093f\u091b\u0941(?=[\s\u0964\u0965]|$)', 'कुछ'),
        # Strip Bodo morphemes that may slip past translation-time guard
        (r'\u0916\u093e\u0932\u093e\u092e\u094b(?=[\s\u0964\u0965]|$)', ''),  # खालामो
        (r'\u0906\u0930\u094b(?=[\s\u0964\u0965]|$)', ''),                    # आरो (Bodo "and")
        (r'\u0917\u0941\u0926\u0941\u0902(?=[\s\u0964\u0965]|$)', ''),         # गुदुं
        (r'\u0928\u093f\u092b\u094d\u0930\u093e\u092f(?=[\s\u0964\u0965]|$)', ''),  # निफ्राय
    ],
    "kan": [
        # Strip ಸೇದುವು/ಸೇದು/ಸೇಡಂ/ಸೇಬಿನ/ಸೇರ್ಪಡೆಯ sentence-initial hallucination prefix
        (r'^\u0cb8\u0cc7(?:\u0ca6\u0cc1\u0cb5\u0cc1|\u0ca6\u0cc1|\u0ca1\u0c82|\u0cac\u0cbf\u0ca8|\u0ca6\u0ccd|\u0cb2\u0ccd|\u0cac\u0ccd|\u0cb0\u0ccd\u0caa\u0ca1\u0cc6\u0caf)[.\s]+', ''),
    ],
    "mal": [
        # Strip ഛ/ഛെ/ഛമായ prefix artifacts
        (r'^\u0d1b(?:\u0d2e\u0d3e\u0d2f|\u0d46)?\s*', ''),
        # Strip ഘനിർമ്മിത prefix artifact
        (r'^\u0d18\u0d28\u0d3f\u0d7c\u0d2e\u0d4d\u0d2e\u0d3f\u0d24\s*', ''),
        # Strip തൃ prefix artifact
        (r'^\u0d24\u0d43\s+', ''),
        # Strip തവണത്തെ prefix artifact
        (r'^\u0d24\u0d35\u0d23\u0d24\u0d4d\u0d24\u0d46\s+', ''),
    ],
    "tel": [
        # Strip Telugu sentence-initial conjunction/artifact
        (r'^(?:\u0c2e\u0c30\u0c3f\u0c2f\u0c41|\u0c05\u0c2f\u0c3f\u0c24\u0c47)\s+', ''),
    ],
    "urd": [
        # Strip کا / کہ sentence-initial bare preposition artifacts
        (r'^(?:\u06a9\u0627|\u06a9\u06c1)\s+', ''),
    ],
    "guj": [
        # Strip leading punctuation artifacts
        (r'^[,;:\u0964\u0965]+\s*', ''),
    ],
    "ben": [
        # Strip ঔর (Hindi "aur" in Bengali script) sentence-initial artifact
        (r'^\u0994\u09b0\s+', ''),
    ],
    "asm": [
        # Strip টাৰ/টা prefix artifact
        (r'^\u099f\u09be(?:\u09f0)?\s+', ''),
    ],
    "pan": [
        # Strip OCR page-reference artifacts: "ਸਫ਼ਾ 3 ਉੱਤੇ ਤਸਵੀਰ" (picture on page 3)
        (r'\u0a38\u0a2b\u0a3c\u0a3e\s+\d+\s+\u0a09\u0a71\u0a24\u0a47\s+\u0a24\u0a38\u0a35\u0a40\u0a30', ''),
        # Strip ਨਾ ਸਿਰਫ / ਨਾ ਭੁੱਲੋ prefix artifacts
        (r'^\u0a28\u0a3e\s+(?:\u0a38\u0a3f\u0a30\u0a2b\u0a3c?|\u0a2d\u0a41\u0a71\u0a32\u0a4b)\s*', ''),
    ],
    "ory": [
        # Strip ମରିଯୁ prefix artifact
        (r'^\u0b2e\u0b30\u0b3f\u0b2f\u0b41\s*', ''),
    ],
    "mar": [
        # Strip OCR page-reference artifacts: "१५ पानांवरील चित्र" / "१३ पानांवरील चित्र"
        (r'[\u0966-\u096f]+\s+\u092a\u093e\u0928\u093e\u0902\u0935\u0930\u0940\u0932\s+\u091a\u093f\u0924\u094d\u0930', ''),
        # Strip किवा/किवी/किडे prefix artifacts
        (r'^\u0915\u093f(?:\u0935\u093e|\u0935\u0940|\u0921\u0947)\s*', ''),
    ],
    "nep": [
        # Strip ते/तेता/तेसै/तेखाको/तेपनि hallucination prefixes
        (r'^\u0924\u0947(?:\u0924\u093e|\u0938\u0948|\u0916\u093e\u0915\u094b|\u092a\u0928\u093f|\u0916\u093e\u0930\u094d\u0928\u0947|\u0928\u094d\u091c\u0947\u0932|\u092a\u093e\u0938|\u0939\u093f\u0932\u094b|\u0928\u0940|\u0924\u094d\u0930\u0948)?\s+', ''),
    ],
    "mai": [
        # Fix Maithili postposition spacing: NLLB inserts space before क/मे postpositions
        # NOTE: replacement must be a lambda — \u escapes are invalid in re.sub replacement strings
        (r'([\u0900-\u097F]) \u0915(?=[\s\u0964\u0965,;]|$)', None),  # handled below
        (r'([\u0900-\u097F]) \u092e\u0947(?=[\s\u0964\u0965,;]|$)', None),  # handled below
    ],
    "doi": [
        # Strip फोरन/फोर/ऐम्म prefix artifacts
        (r'^\u092b\u094b\u0930(?:\u0928)?\s+', ''),
        (r'^\u0910\u092e\u094d\u092e\s+', ''),
    ],
    "bod": [
        # Strip stray single-quote artifacts around Devanagari technical terms
        ("(?<=[\u0900-\u097F]) '(?=[\u0900-\u097F])", ' '),
        ("(?<=[\u0900-\u097F])' (?=[\u0900-\u097F])", ' '),
    ],
    "san": [
        # Strip पाल्य/पालक/पालित/पालन prefix artifacts
        (r'^\u092a\u093e\u0932(?:\u094d\u092f(?:\u092e\u093e\u0928)?|\u0915|\u093f\u0924|\u0928)\s+', ''),
    ],
    "mni": [
        # Collapse Bengali virama + space + vowel sign (broken cluster from NLLB)
        (r'([\u09cd]) ([\u09be-\u09cc\u09d7])', r'\1\2'),
    ],
    "sat": [
        # Strip any non-Ol-Chiki prefix garbage (Latin/Devanagari leaking in)
        (r'^[^\u1c50-\u1c7f\s]+\s*', ''),
    ],
    "snd": [
        (r'^(?:\u06a9\u0627|\u06a9\u06c1)\s+', ''),
    ],
    "kas": [
        (r'^(?:\u06a9\u0627|\u06a9\u06c1)\s+', ''),
    ],
    "kok": [
        # Strip leading punctuation artifacts (Konkani shares Devanagari with Hindi/Marathi)
        (r'^[,;:\u0964\u0965]+\s*', ''),
    ],
}


def _apply_sub_fixups(text: str, tgt_lang: str) -> str:
    """Apply per-language post-translation fixups to subtitle text."""
    _MAI_KA  = '\u0915'
    _MAI_ME  = '\u092e\u0947'
    for pattern, replacement in _SUB_FIXUPS.get(tgt_lang, []):
        if replacement is None:
            # Lambda replacements for patterns where \u in replacement string is invalid
            if '\u0915' in pattern and '\u092e' not in pattern:
                text = re.sub(pattern, lambda m: m.group(1) + _MAI_KA, text)
            elif '\u092e\u0947' in pattern:
                text = re.sub(pattern, lambda m: m.group(1) + _MAI_ME, text)
        else:
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
        # Do NOT stretch the last subtitle to fill trailing video silence — that
        # produced a single 50s+ cue at the end. Leave it at its natural reading
        # end; trailing silence simply has no subtitle, which is correct.
        timings.append((start, end))
    return timings


# Maximum on-screen duration for a single subtitle cue. Blocks longer than this
# (e.g. a 62s ASR segment that merged many sentences) are split into multiple
# readable cues at sentence boundaries. This only affects the DISPLAYED subtitle
# — the dubbed audio segment is unchanged.
_MAX_CUE_S = 7.0


def _split_long_cue(start: float, end: float, text: str) -> list[tuple[float, float, str]]:
    """Split a (start, end, text) cue into readable sub-cues so that NO emitted
    cue exceeds _MAX_CUE_S. Splits at sentence boundaries first, then falls back
    to word groups for any piece that is still too long. Time is distributed
    proportionally to character length. Only affects displayed subtitles — the
    dubbed audio segment is unchanged."""
    dur = end - start
    if dur <= _MAX_CUE_S or not text.strip():
        return [(start, end, text)]
    import re as _re
    parts = [p.strip() for p in _re.split(r'(?<=[।॥.!?])\s+', text.strip()) if p.strip()]
    if len(parts) <= 1:
        parts = [text.strip()]

    # Distribute the total duration across sentence parts by char length, then
    # for any part whose allotted time still exceeds the cap, break it into
    # smaller word groups so every final cue is <= _MAX_CUE_S.
    total_chars = sum(len(p) for p in parts) or 1
    cues: list[tuple[float, float, str]] = []
    t = start
    for p in parts:
        p_dur = dur * (len(p) / total_chars)
        if p_dur <= _MAX_CUE_S:
            cues.append((t, t + p_dur, p))
            t += p_dur
            continue
        # Part still too long — break into word groups sized to the cap.
        words = p.split()
        n_chunks = max(2, int(p_dur / _MAX_CUE_S) + 1)
        size = max(1, (len(words) + n_chunks - 1) // n_chunks)
        chunks = [" ".join(words[j:j + size]) for j in range(0, len(words), size)]
        cchars = sum(len(c) for c in chunks) or 1
        for c in chunks:
            c_dur = p_dur * (len(c) / cchars)
            cues.append((t, t + c_dur, c))
            t += c_dur
    # Snap the last cue to exactly `end` to avoid rounding drift.
    if cues:
        ls, _, lt = cues[-1]
        cues[-1] = (ls, end, lt)
    return cues


def generate_srt(segments: list[dict], output_path: str,
                 video_duration: float = 0.0, tgt_lang: str = "") -> str:
    """
    Generate SRT subtitle file from translated segments.
    End times are extended to cover reading time of the translated text,
    clamped to the next segment's start so subtitles never overlap. Cues longer
    than _MAX_CUE_S are split at sentence boundaries for readability.
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
            # Prefer placed timings (from push-forward assembly) so subtitles
            # line up with the actual dubbed audio, not the original stamps.
            _seg = {**s, "_display_text": txt}
            if s.get("placed_start") is not None and s.get("placed_end") is not None:
                _seg["start"] = s["placed_start"]
                _seg["end"]   = s["placed_end"]
            segs.append(_seg)
    timings = _adjust_timings(segs, video_duration)
    for i, (seg, (start, end)) in enumerate(zip(segs, timings)):
        for (cs, ce, ctext) in _split_long_cue(start, end, seg["_display_text"]):
            text    = _wrap_subtitle(ctext)
            start_s = _seconds_to_srt_time(cs)
            end_s   = _seconds_to_srt_time(ce)
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
            # Prefer placed timings (from push-forward assembly) so subtitles
            # line up with the actual dubbed audio, not the original stamps.
            _seg = {**s, "_display_text": txt}
            if s.get("placed_start") is not None and s.get("placed_end") is not None:
                _seg["start"] = s["placed_start"]
                _seg["end"]   = s["placed_end"]
            segs.append(_seg)
    timings = _adjust_timings(segs, video_duration)
    for seg, (start, end) in zip(segs, timings):
        for (cs, ce, ctext) in _split_long_cue(start, end, seg["_display_text"]):
            text    = _wrap_subtitle(ctext)
            start_s = _seconds_to_vtt_time(cs)
            end_s   = _seconds_to_vtt_time(ce)
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
