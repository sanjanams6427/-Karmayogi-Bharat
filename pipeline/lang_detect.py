# ============================================================
# Per-segment language detection
# Model: lingua-language-detector (offline, no API)
# Handles English/Hindi code-switching in ASR output
# ============================================================

from .logger import get_logger

log = get_logger("lang_detect")

# faster-whisper detected language codes → internal lang codes
_FW_TO_INTERNAL = {
    "en": "eng", "hi": "hin", "bn": "ben", "gu": "guj", "kn": "kan",
    "ml": "mal", "mr": "mar", "or": "ory", "pa": "pan", "ta": "tam",
    "te": "tel", "ur": "urd", "as": "asm", "ne": "nep", "mai": "mai",
    "sd": "snd", "ks": "kas", "kok": "kok", "mni": "mni", "sa": "san",
    "bo": "bod", "sat": "sat", "doi": "doi",
}


def fw_lang_to_internal(fw_code: str, fallback: str = "eng") -> str:
    """Convert faster-whisper detected language code to internal lang code."""
    return _FW_TO_INTERNAL.get(fw_code, fallback)


# Map lingua Language enum names → our internal lang codes
# Note: bod, doi, kas, kok, mni, sat, snd not supported by lingua — handled by fallback
_LINGUA_TO_INTERNAL = {
    "ENGLISH":    "eng",
    "HINDI":      "hin",
    "BENGALI":    "ben",
    "GUJARATI":   "guj",
    "KANNADA":    "kan",
    "MALAYALAM":  "mal",
    "MARATHI":    "mar",
    "ORIYA":      "ory",
    "PUNJABI":    "pan",
    "TAMIL":      "tam",
    "TELUGU":     "tel",
    "URDU":       "urd",
    "NEPALI":     "nep",
    "SANSKRIT":   "san",
    "MAITHILI":   "mai",
    "ASSAMESE":   "asm",
}

# Languages lingua cannot detect — always trust assumed_lang
_LINGUA_UNSUPPORTED = {"bod", "doi", "kas", "kok", "mni", "sat", "snd"}

_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        try:
            from lingua import Language, LanguageDetectorBuilder
            langs = [getattr(Language, k) for k in _LINGUA_TO_INTERNAL if hasattr(Language, k)]
            _detector = LanguageDetectorBuilder.from_languages(*langs).build()
            log.info("Lingua language detector loaded")
        except ImportError:
            log.warning("lingua not installed — pip install lingua-language-detector")
            _detector = "unavailable"
    return _detector


def detect_lang(text: str, fallback: str = "hin") -> str:
    """Detect language of a text segment. Returns internal lang code."""
    if not text or not text.strip():
        return fallback
    detector = _get_detector()
    if detector == "unavailable":
        return fallback
    try:
        result = detector.detect_language_of(text)
        if result is None:
            return fallback
        return _LINGUA_TO_INTERNAL.get(result.name, fallback)
    except Exception as e:
        log.debug(f"Detection failed: {e}")
        return fallback


def tag_segments(segments: list[dict], assumed_lang: str) -> list[dict]:
    """
    Add 'detected_lang' to each segment.
    - For lingua-unsupported langs (bod/doi/kas/kok/mni/sat/snd), always keep assumed_lang.
    - For supported langs, use detection but fall back to assumed_lang (not 'eng') on failure.
    """
    if assumed_lang in _LINGUA_UNSUPPORTED:
        return [{**s, "detected_lang": assumed_lang} for s in segments]

    detector = _get_detector()
    if detector == "unavailable":
        return [{**s, "detected_lang": assumed_lang} for s in segments]

    tagged = []
    for seg in segments:
        detected = detect_lang(seg.get("text", ""), fallback=assumed_lang)
        tagged.append({**seg, "detected_lang": detected})
    return tagged
