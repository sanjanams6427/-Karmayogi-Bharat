# ============================================================
# Translation Module — Offline, Zero-cost
# Primary  : IndicTrans2 (local, all 22 Indian languages)
# Fallback : SeamlessM4T → NLLB-200
# No LLM, no internet, no API keys required.
# ============================================================

import re
import threading
import torch
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
from pathlib import Path
from .lang_config import INDIC_TRANS2_CODES, SEAMLESS_CODES, SEAMLESS_S2ST_LANGS, NLLB_CODES, LANG_NAMES
from .logger import get_logger
from .retry import retry
from .quality import score_segment, review_summary

# Matches <unk>, &lt;unk&gt;, [unk], (unk) — case-insensitive, with surrounding whitespace
_UNK_RE = re.compile(r"\s*(?:<unk>|&lt;unk&gt;|\[unk\]|\(unk\))\s*", re.IGNORECASE)

# HTML / XML tags
_HTML_TAG_RE = re.compile(r"<[^>]{1,80}>")

# ── Formatting / template token protection ───────────────────────────────
# Preserves intentional placeholders: {name}, %s, ${value}, {{var}}, <USER_NAME>
_FORMAT_TOKEN_RE = re.compile(
    r"""
    \{\{[^}]+\}\}          # {{variable}}  — double-brace (Jinja/Mustache)
    |\{[\w.\[\]]+\}        # {name} {obj.attr} {list[0]}  — single-brace
    |\$\{[^}]+\}           # ${value}  — shell/JS template literal
    |%(?:\(\w+\))?[sdifgr%]  # %s %d %(key)s  — printf-style
    |<[A-Z][A-Z0-9_]{1,30}>  # <USER_NAME> <PLACEHOLDER>  — XML-style caps
    """,
    re.VERBOSE,
)


def _protect_format_tokens(text: str) -> tuple[str, dict[str, str]]:
    """
    Replace formatting/template placeholders with __FMT0__, __FMT1__, … so
    translation engines cannot alter or drop them.
    Returns (protected_text, {placeholder: original_token}).
    """
    fmt_map: dict[str, str] = {}
    matches = list(_FORMAT_TOKEN_RE.finditer(text))
    for i, m in enumerate(reversed(matches)):
        ph = f"__FMT{len(matches) - 1 - i}__"
        fmt_map[ph] = m.group(0)
        text = text[:m.start()] + ph + text[m.end():]
    return text, fmt_map


def _restore_format_tokens(text: str, fmt_map: dict[str, str]) -> str:
    for ph, original in fmt_map.items():
        text = text.replace(ph, original)
    return text


# ── Trademark passthrough — KB tender §3.2 ───────────────────────────────
# "Ensure translation to exclude any trademarks of the content provider."
# Common content-provider trademarks on iGOT: Microsoft, Meta, Google, etc.
# These are protected as non-translatable so they pass through unchanged.
_TRADEMARK_TERMS: frozenset[str] = frozenset([
    "Microsoft", "Meta", "Google", "YouTube", "WhatsApp", "Instagram",
    "Facebook", "LinkedIn", "Twitter", "X", "Zerodha", "Fractal",
    "iGOT", "Karmayogi", "XLRI", "IIT", "IIM", "IISc", "ISB",
    "PMFBY", "PMJDY", "PMMY", "PRAGATI", "GSV", "DPI", "NEGD",
    "MeitY", "DoPT", "CBC", "CBP", "CPPP", "NIC",
])

# Regex: whole-word match for any trademark term (case-sensitive)
_TRADEMARK_RE = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in sorted(_TRADEMARK_TERMS, key=len, reverse=True)) + r')\b'
)


def _protect_trademarks(text: str) -> tuple[str, dict[str, str]]:
    """
    Replace trademark terms with __TM0__, __TM1__, … placeholders.
    Returns (protected_text, {placeholder: original_term}).
    """
    tm_map: dict[str, str] = {}
    matches = list(_TRADEMARK_RE.finditer(text))
    for i, m in enumerate(reversed(matches)):
        ph = f"__TM{len(matches) - 1 - i}__"
        tm_map[ph] = m.group(0)
        text = text[:m.start()] + ph + text[m.end():]
    return text, tm_map


def _restore_trademarks(text: str, tm_map: dict[str, str]) -> str:
    for ph, original in tm_map.items():
        text = text.replace(ph, original)
    return text


# ── Non-translatable token protection ─────────────────────────────────────
# Tokens that must pass through unchanged: URLs, file paths, shell commands,
# code identifiers, email addresses, hashtags, @mentions.
_NONTRANS_RE = re.compile(
    r"https?://\S+"
    r"|www\.\S+"
    r"|\S+@\S+\.\S+"
    r"|(?:/[\w./-]+){2,}"
    r"|[A-Za-z]:\\\\[\\\w ./-]+"
    r"|\b[\w.-]+\.(?:py|sh|bat|js|ts|json|yaml|yml|xml|csv|txt|mp4|mp3|wav|pdf|docx?|xlsx?|zip|tar|gz)\b"
    r"|`[^`]+`"
    r"|\b(?:pip|python|conda|npm|yarn|git|docker|kubectl|bash|sh)\s+\S+(?:\s+\S+)*"
    r"|#[\w]+"
    r"|@[\w]+"
    r"|\b[A-Z][A-Z0-9_]*[0-9_][A-Z0-9_]*\b"
)

# A segment is fully non-translatable when ≥90% of its non-space chars
# belong to non-translatable tokens (URL, code, path, etc.)
def _is_fully_nontranslatable(text: str) -> bool:
    """Return True if the segment contains nothing worth translating."""
    stripped = text.strip()
    if not stripped:
        return True
    total_chars = len(stripped.replace(" ", ""))
    if total_chars == 0:
        return True
    nt_chars = sum(len(m.group(0).replace(" ", "")) for m in _NONTRANS_RE.finditer(stripped))
    return (nt_chars / total_chars) >= 0.90


def _protect_nontranslatable(text: str) -> tuple[str, dict[str, str]]:
    """
    Replace non-translatable tokens (URLs, paths, code, identifiers) with
    __NT0__, __NT1__, … placeholders before sending to the translation engine.
    Returns (protected_text, {placeholder: original_token}).
    """
    nt_map: dict[str, str] = {}
    matches = list(_NONTRANS_RE.finditer(text))
    # Replace right-to-left so offsets stay valid
    for i, m in enumerate(reversed(matches)):
        ph = f"__NT{len(matches) - 1 - i}__"
        nt_map[ph] = m.group(0)
        text = text[:m.start()] + ph + text[m.end():]
    return text, nt_map


def _restore_nontranslatable(text: str, nt_map: dict[str, str]) -> str:
    for ph, original in nt_map.items():
        text = text.replace(ph, original)
    return text

# ── Meaning-preservation: protect & verify factual tokens ──────────────────
# Matches: integers, decimals, percentages, years, ordinals, measurements,
# dates (DD/MM/YYYY, Month DD YYYY, YYYY-MM-DD), times (HH:MM), currency (₹/$)
_FACTUAL_TOKEN_RE = re.compile(
    r"""
    (?:₹|\$|€|£|¥)\s*[\d,]+(?:\.\d+)?   # currency
    |\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b  # dates DD/MM/YYYY or DD-MM-YYYY
    |\b\d{4}-\d{2}-\d{2}\b               # ISO date
    |\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?
         |Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?
         |Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b
    |\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?\b  # time
    |\b\d+(?:[,.]\d+)*(?:\.\d+)?\s*%     # percentage
    |\b\d+(?:[,.]\d+)*(?:\.\d+)?\s*(?:km|m|cm|mm|kg|g|mg|L|ml|km/h|mph
                                         |sq\.?\s*km|sq\.?\s*m|ha|acre
                                         |MW|GW|kW|kWh|GHz|MHz|TB|GB|MB|KB)\b
    |\b\d{4}\b                            # bare 4-digit year
    |\b\d+(?:[,.]\d+)*(?:\.\d+)?\b        # any remaining number
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _extract_factual_tokens(text: str) -> list[str]:
    """Return all factual tokens found in text, in order."""
    return _FACTUAL_TOKEN_RE.findall(text)


def _protect_factual_tokens(text: str) -> tuple[str, dict[str, str]]:
    """
    Replace each factual token with a placeholder __F0__, __F1__, …
    Returns (protected_text, {placeholder: original_token}).
    Placeholders use only ASCII digits/underscores — safe across all scripts.
    """
    placeholder_map: dict[str, str] = {}
    result = text
    # Process longest matches first to avoid partial overlaps
    tokens = list(_FACTUAL_TOKEN_RE.finditer(text))
    # Replace right-to-left so offsets stay valid
    for i, m in enumerate(reversed(tokens)):
        ph = f"__F{len(tokens) - 1 - i}__"
        placeholder_map[ph] = m.group(0)
        result = result[:m.start()] + ph + result[m.end():]
    return result, placeholder_map


def _restore_factual_tokens(text: str, placeholder_map: dict[str, str]) -> str:
    """Restore __FN__ placeholders with their original tokens."""
    for ph, original in placeholder_map.items():
        text = text.replace(ph, original)
    return text


def _verify_factual_tokens(source: str, translated: str,
                           placeholder_map: dict[str, str]) -> str:
    """
    After placeholder restore, check that every source factual token appears
    in the translation. Append any missing tokens at the end so no fact is lost.
    Only appends tokens that are genuinely absent (not a substring of another).
    """
    if not placeholder_map:
        return translated
    missing = []
    for original in placeholder_map.values():
        # Normalise: strip spaces around separators for comparison
        norm = original.strip()
        if norm not in translated:
            missing.append(norm)
    if missing:
        translated = translated.rstrip() + " " + " ".join(missing)
    return translated

# Allowed Unicode ranges per language code.
# Format: list of (lo, hi) inclusive codepoint pairs.
# All langs share: Basic Latin digits+punct (0x0020-0x0040, 0x005B-0x0060, 0x007B-0x007E),
# General Punctuation (0x2000-0x206F), and common symbols.
_SCRIPT_RANGES: dict[str, list[tuple[int, int]]] = {
    # Devanagari family
    "hin": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    "mar": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    "mai": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    "doi": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    "san": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    "nep": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    "bod": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],  # Bodo/Boro written in Devanagari (brx_Deva)
    # NOTE: bod shares Devanagari with hin/mar/mai/nep — script-level stripping
    # cannot distinguish them. Drift is caught by morpheme-level guards.
    # Bengali script (also used by Assamese and Manipuri)
    "ben": [(0x0980, 0x09FF)],
    "asm": [(0x0980, 0x09FF)],
    "mni": [(0x0980, 0x09FF)],          # Meitei Mayek also accepted below
    # Gujarati
    "guj": [(0x0A80, 0x0AFF)],
    # Gurmukhi (Punjabi)
    "pan": [(0x0A00, 0x0A7F)],
    # Kannada
    "kan": [(0x0C80, 0x0CFF)],
    # Malayalam
    "mal": [(0x0D00, 0x0D7F)],
    # Odia
    "ory": [(0x0B00, 0x0B7F)],
    # Tamil
    "tam": [(0x0B80, 0x0BFF)],
    # Telugu
    "tel": [(0x0C00, 0x0C7F)],
    # Arabic script family
    "urd": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "kas": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "snd": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    # Ol Chiki (Santhali)
    "sat": [(0x1C50, 0x1C7F)],
    # Konkani — written in Devanagari
    "kok": [(0x0900, 0x097F), (0x1CD0, 0x1CFF)],
    # English — Latin only (passthrough, no stripping needed)
    "eng": [(0x0000, 0x007F), (0x0080, 0x024F)],
}

# Codepoints always allowed regardless of language:
# spaces, digits, common punctuation, quotation marks, dashes, ellipsis
_ALWAYS_ALLOWED: list[tuple[int, int]] = [
    (0x0009, 0x000D),  # tab, newline, CR
    (0x0020, 0x0040),  # space ! " # $ % & ' ( ) * + , - . / 0-9 : ; < = > ?
    (0x005B, 0x0060),  # [ \ ] ^ _ `
    (0x007B, 0x007E),  # { | } ~
    (0x00A0, 0x00A0),  # non-breaking space
    (0x2000, 0x206F),  # General Punctuation (em-dash, ellipsis, quotes …)
    (0x2018, 0x201F),  # Typographic quotes
    (0x20A0, 0x20CF),  # Currency symbols (₹ etc.)
    (0x2100, 0x214F),  # Letterlike symbols
    (0x0964, 0x0965),  # Devanagari danda / double danda (used across Indic scripts)
]


def _is_allowed(cp: int, allowed: list[tuple[int, int]]) -> bool:
    for lo, hi in allowed:
        if lo <= cp <= hi:
            return True
    return False


def _build_foreign_word_re(tgt_lang: str) -> re.Pattern | None:
    """
    Build a regex that matches contiguous runs of characters that belong to
    a script OTHER than the target language's script(s).
    Returns None for English (no stripping needed).

    Strategy: collect all Unicode script blocks that are NOT allowed for
    tgt_lang, build a character class from them, match 1+ char runs.
    The 22 Indian scripts + common foreign scripts covered:
      Burmese/Myanmar  1000-109F
      Thai             0E00-0E7F
      Khmer            1780-17FF
      Tibetan          0F00-0FFF  (not Bodo — Bodo uses Devanagari)
      Georgian         10A0-10FF
      Armenian         0530-058F
      Hebrew           0590-05FF
      CJK              4E00-9FFF, 3000-303F
      Hangul           AC00-D7FF
      Cyrillic         0400-04FF
      Greek            0370-03FF
      Latin (for non-Latin targets)  0041-007A, 00C0-024F
    """
    if tgt_lang == "eng":
        return None
    script_ranges = _SCRIPT_RANGES.get(tgt_lang)
    if not script_ranges:
        return None

    # All known non-target foreign script blocks
    ALL_SCRIPT_BLOCKS = [
        (0x0041, 0x007A),  # Basic Latin letters A-z
        (0x00C0, 0x024F),  # Latin Extended
        (0x0370, 0x03FF),  # Greek
        (0x0400, 0x04FF),  # Cyrillic
        (0x0530, 0x058F),  # Armenian
        (0x0590, 0x05FF),  # Hebrew
        (0x0600, 0x06FF),  # Arabic
        (0x0750, 0x077F),  # Arabic Supplement
        (0x0900, 0x097F),  # Devanagari
        (0x0980, 0x09FF),  # Bengali
        (0x0A00, 0x0A7F),  # Gurmukhi
        (0x0A80, 0x0AFF),  # Gujarati
        (0x0B00, 0x0B7F),  # Odia
        (0x0B80, 0x0BFF),  # Tamil
        (0x0C00, 0x0C7F),  # Telugu
        (0x0C80, 0x0CFF),  # Kannada
        (0x0D00, 0x0D7F),  # Malayalam
        (0x0E00, 0x0E7F),  # Thai
        (0x0F00, 0x0FFF),  # Tibetan
        (0x1000, 0x109F),  # Myanmar/Burmese
        (0x1780, 0x17FF),  # Khmer
        (0x1C50, 0x1C7F),  # Ol Chiki
        (0x1CD0, 0x1CFF),  # Vedic Extensions
        (0x3000, 0x303F),  # CJK Symbols
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
        (0xAC00, 0xD7FF),  # Hangul
        (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    ]

    # Keep only blocks that are NOT part of the target script
    allowed_set = set()
    for lo, hi in script_ranges + _ALWAYS_ALLOWED:
        for cp in range(lo, hi + 1):
            allowed_set.add(cp)

    foreign_ranges = []
    for lo, hi in ALL_SCRIPT_BLOCKS:
        # Only include this block if it has chars NOT in the allowed set
        foreign_cps = [cp for cp in range(lo, min(hi, lo + 256) + 1)
                       if cp not in allowed_set]
        if foreign_cps:
            foreign_ranges.append((lo, hi))

    if not foreign_ranges:
        return None

    # Build regex character class: [\uXXXX-\uYYYY...]+
    char_class = "".join(
        f"\\u{lo:04X}-\\u{hi:04X}" for lo, hi in foreign_ranges
    )
    return re.compile(f"[{char_class}]+")


# Pre-build foreign-word regexes for all 22 languages at import time
_FOREIGN_WORD_RE: dict[str, re.Pattern | None] = {
    lang: _build_foreign_word_re(lang)
    for lang in list(_SCRIPT_RANGES.keys())
}


def _clean_mixed_lang(text: str, tgt_lang: str) -> str:
    """Strip HTML tags and remove foreign-script word runs from the output.
    Tamil exception: short Latin words (<=12 chars, no spaces) that appear in
    Tamil text are technical/brand terms (iGOT, platform, portal, module etc.)
    that Tamil speakers use natively. Stripping them causes missing words in TTS.
    """
    # 1. Remove HTML/XML tags
    text = _HTML_TAG_RE.sub("", text)

    if tgt_lang == "eng":
        return re.sub(r" {2,}", " ", text).strip()

    # 2. Strip entire foreign-script word runs (word-level, not char-level)
    fw_re = _FOREIGN_WORD_RE.get(tgt_lang)
    if fw_re:
        # For Indic scripts: preserve short Latin words (≤15 chars) — these are
        # technical terms, brand names, acronyms (iGOT, RTX, API, etc.) that
        # appear legitimately in translated text. Strip only long Latin runs
        # (>15 chars) which are untranslated English sentences.
        _INDIC_SCRIPTS = {
            "hin", "mar", "mai", "doi", "san", "nep", "bod", "kok",
            "ben", "asm", "mni", "guj", "pan", "kan", "mal", "ory",
            "tam", "tel", "urd", "kas", "snd", "sat",
        }
        if tgt_lang in _INDIC_SCRIPTS:
            def _indic_replace(m):
                word = m.group(0)
                if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9\-_.]{0,14}', word):
                    return word
                return " "
            text = fw_re.sub(_indic_replace, text)
        else:
            text = fw_re.sub(" ", text)

    # 3. Collapse multiple spaces and strip
    return re.sub(r" {2,}", " ", text).strip()


def _clean_unk(text: str) -> str:
    """Remove all <unk> token variants, collapsing any double-spaces left behind."""
    cleaned = _UNK_RE.sub(" ", text).strip()
    return re.sub(r" {2,}", " ", cleaned)


# ── Readability post-processing ───────────────────────────────────────────
# Fixes common MT artifacts so the output reads naturally.

# Repeated adjacent identical words: "the the", "है है"
_REPEAT_WORD_RE = re.compile(r"\b(\S+)( \1){1,}\b")
# Space before punctuation: "word ," → "word,"
_SPACE_BEFORE_PUNCT_RE = re.compile(r" +([,;:!?।॥\.])")
# Multiple punctuation of same kind: ",," → ","  (ellipsis "..." preserved)
_MULTI_PUNCT_RE = re.compile(r"([,;:!?]){2,}")


# Hindi direct question: sentence where the interrogative word क्या/कैसे/कब/कहाँ/क्यों
# is NOT part of an indirect clause ("कि कैसे", "कि क्या", "कि कब" etc.).
# Indirect clauses use these words as subordinators, not interrogatives.
# Strategy: fire only when no "कि" precedes the interrogative word in the sentence.
_HIN_QUESTION_RE = re.compile(
    r'^(?:(?!\u0915\u093f\s).)*?'    # no "कि " anywhere before the match
    r'(?:^|\s)'                        # word boundary
    r'(?:\u0915\u094d\u092f\u093e|\u0915\u0948\u0938\u0947|\u0915\u092c'
    r'|\u0915\u0939\u093e\u0901|\u0915\u094d\u092f\u094b\u0902)'
    r'[^\u0964\u0965]*\u0964$',
    re.DOTALL
)


# Tamil word-boundary regex: vowel sign immediately followed by consonant
# with no virama (U+0BCD) in between = fused word boundary → insert space.
# Applied to both NLLB (fused) and IndicTrans2 (occasionally fused) output.
_TAM_FUSE_RE = re.compile(r'([\u0bbe-\u0bc8\u0bca-\u0bcc])(?!\u0bcd)([\u0b95-\u0bb9])')
# IndicTrans2 syllable-split: vowel sign + SPACE + Tamil char → collapse.
_TAM_VS_RE = re.compile(r'([\u0bbe-\u0bcc\u0bcd]) ([\u0b80-\u0bff])')


def _naturalise(text: str, tgt_lang: str = "") -> str:
    """Rule-based cleanup of common MT readability artifacts."""
    # Tamil: fix both IndicTrans2 syllable-splits and NLLB word-fusions.
    # Step 1 — collapse IndicTrans2 syllable-splits (vowel/virama + space + Tamil char).
    # Step 2 — insert spaces at NLLB fused word boundaries (vowel sign → consonant, no virama).
    if tgt_lang.split("_")[0] == "tam":
        while _TAM_VS_RE.search(text):
            text = _TAM_VS_RE.sub(r'\1\2', text)
        text = _TAM_FUSE_RE.sub(r'\1 \2', text)
    text = _REPEAT_WORD_RE.sub(r"\1", text)
    # Also catch X மற்றும் X / X और X / X and X patterns (same word both sides of conjunction)
    text = re.sub(
        r'(\S{4,})\s+(?:\u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd|\u0914\u0930|and|\u0905\u0928\u094d\u0924\u0947|\u0924\u0925\u093e)\s+\1(?=\s|$|[.,;!?])',
        r'\1', text
    )
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _MULTI_PUNCT_RE.sub(r"\1", text)
    # Strip leading punctuation artifacts (comma, semicolon at sentence start)
    text = re.sub(r'^[,;:\u0964\u0965]+\s*', '', text)
    # Strip Bengali ঔর (Hindi "aur" in Bengali script) as sentence-initial artifact
    text = re.sub(r'^\u0994\u09b0\s+', '', text)
    # Strip Nepali ते/तेता/तेपनि etc. hallucination prefixes
    text = re.sub(r'^\u0924\u0947(?:\u0924\u093e|\u092a\u0928\u093f|\u0916\u093e\u0930\u094d\u0928\u0947|\u0928\u094d\u091c\u0947\u0932|\u092a\u093e\u0938|\u0939\u093f\u0932\u094b|\u0928\u0940|\u0924\u094d\u0930\u0948)?\s+', '', text)
    # Strip Kannada ಸೇದುವು/ಸೇದು/ಸೇಡಂ/ಸೇರ್ಪಡೆಯ hallucination prefixes (fused or standalone sentence)
    text = re.sub(r'^\u0cb8\u0cc7(?:\u0ca6\u0cc1\u0cb5\u0cc1|\u0ca6\u0cc1|\u0ca1\u0c82|\u0cac\u0cbf\u0ca8|\u0ca6\u0ccd|\u0cb2\u0ccd|\u0cac\u0ccd|\u0cb0\u0ccd\u0caa\u0ca1\u0cc6\u0caf)[.\s]+', '', text)
    # Strip Malayalam ഛ/ഛെ/ഛമായ/ഘ prefix artifacts
    text = re.sub(r'^\u0d1b(?:\u0d2e\u0d3e\u0d2f|\u0d46)?\s*', '', text)
    text = re.sub(r'^\u0d18\u0d28\u0d3f\u0d7c\u0d2e\u0d4d\u0d2e\u0d3f\u0d24\s*', '', text)
    text = re.sub(r'^\u0d24\u0d43\s+', '', text)
    text = re.sub(r'^\u0d24\u0d35\u0d23\u0d24\u0d4d\u0d24\u0d46\s+', '', text)
    # Strip Odia ମରିଯୁ prefix artifact
    text = re.sub(r'^\u0b2e\u0b30\u0b3f\u0b2f\u0b41\s*', '', text)
    # Strip Assamese টাৰ/টা prefix artifact
    text = re.sub(r'^\u099f\u09be(?:\u09b0)?\s+', '', text)
    # Strip Punjabi ਨਾ ਸਿਰਫ / ਨਾ ਭੁੱਲੋ prefix artifacts
    text = re.sub(r'^\u0a28\u0a3e\s+(?:\u0a38\u0a3f\u0a30\u0a2b\u0a3c?|\u0a2d\u0a41\u0a71\u0a32\u0a4b)\s*', '', text)
    # Strip Marathi किवा/किवी/किडे prefix artifacts
    text = re.sub(r'^\u0915\u093f(?:\u0935\u093e|\u0935\u0940|\u0921\u0947|\u0935\u093e\u0937\u094d\u092a\u0940\u0915\u0930\u0923)\s*', '', text)
    # Strip Sanskrit पाल्य/पालक/पालित/पालन prefix artifacts
    text = re.sub(r'^\u092a\u093e\u0932(?:\u094d\u092f(?:\u092e\u093e\u0928)?|\u0915|\u093f\u0924|\u0928)\s+', '', text)
    # Strip Dogri फोरन/फोर/ऐम्म prefix artifacts
    text = re.sub(r'^\u092b\u094b\u0930(?:\u0928)?\s+', '', text)
    text = re.sub(r'^\u0910\u092e\u094d\u092e\s+', '', text)
    # Strip Urdu کا / کہ sentence-initial artifacts (bare prepositions)
    text = re.sub(r'^(?:\u06a9\u0627|\u06a9\u06c1)\s+', '', text)
    # Hindi question sentences ending with danda → replace with ?
    if _HIN_QUESTION_RE.search(text):
        text = text.rstrip('\u0964\u0965').rstrip() + '?'
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ── Final quality check ───────────────────────────────────────────────────
# Stray placeholder patterns that must never appear in final output:
# __NTn__, __Fn__, __FMTn__, and any leftover __WORD__ tokens.
_STRAY_PLACEHOLDER_RE = re.compile(r"__[A-Z]{1,6}\d*__")


def _final_quality_check(
    source: str, translated: str, tgt_lang: str,
    fmt_map: dict, nt_map: dict, factual_map: dict,
) -> tuple[str, list[str]]:
    """
    Final gate before returning a translation. Verifies all 10 quality criteria
    and auto-corrects where possible. Returns (cleaned_text, [flag, ...]).

    Checks:
      1. Accurate        — non-empty output for non-empty source
      2. Complete        — translated length not suspiciously short vs source
      3. Grammar         — no stray sentence-initial lowercase after period
      4. Fluency         — no excessive repeated punctuation surviving naturalise
      5. Consistency     — placeholder counts match (fmt_map keys all restored)
      6. Corruption-free — no replacement char U+FFFD, no null bytes
      7. Placeholder-free — no __NTn__ / __Fn__ / __FMTn__ artifacts remain
      8. Mixed-lang-free — re-run _clean_mixed_lang as final pass
      9. Formatting      — leading/trailing whitespace stripped, single spaces
     10. Professional    — strip any debug/internal tokens that leaked through
    """
    flags: list[str] = []

    # 1. Accuracy — non-empty
    if source.strip() and not translated.strip():
        flags.append("fqc:empty_output")
        return source, flags  # restore source as last resort

    # 2. Completeness — translated should be at least 35% as long as source
    #    for Devanagari targets (subject-drop = ~15% shorter than source).
    #    20% for other scripts (agglutinative langs can be much shorter).
    src_len = len(source.strip())
    tgt_len = len(translated.strip())
    _deva_tgt = tgt_lang in {"hin", "mar", "mai", "nep", "doi", "san", "kok", "bod"}
    _completeness_threshold = 0.35 if _deva_tgt else 0.20
    if src_len > 20 and tgt_len < src_len * _completeness_threshold:
        flags.append("fqc:suspiciously_short")

    # 3. Grammar — sentence-initial lowercase after ". " (Latin-script targets only)
    if tgt_lang in ("eng",):
        translated = re.sub(
            r'(\.\s+)([a-z])',
            lambda m: m.group(1) + m.group(2).upper(),
            translated
        )

    # 4. Fluency — collapse any surviving run of 3+ identical punctuation
    translated = re.sub(r'([!?.,;:]){3,}', r'\1', translated)

    # 5. Consistency — all fmt_map placeholders must be restored
    for ph in fmt_map:
        if ph in translated:
            flags.append(f"fqc:unreplaced_fmt:{ph}")
            translated = translated.replace(ph, fmt_map[ph])
    for ph in nt_map:
        if ph in translated:
            flags.append(f"fqc:unreplaced_nt:{ph}")
            translated = translated.replace(ph, nt_map[ph])
    for ph in factual_map:
        if ph in translated:
            flags.append(f"fqc:unreplaced_factual:{ph}")
            translated = translated.replace(ph, factual_map[ph])

    # 6. Corruption — replacement char U+FFFD and null bytes
    if "\uFFFD" in translated:
        flags.append("fqc:replacement_char")
        translated = translated.replace("\uFFFD", "")
    if "\x00" in translated:
        flags.append("fqc:null_byte")
        translated = translated.replace("\x00", "")

    # 7. Placeholder artifacts — any __WORD__ pattern that survived
    if _STRAY_PLACEHOLDER_RE.search(translated):
        flags.append("fqc:stray_placeholder")
        translated = _STRAY_PLACEHOLDER_RE.sub("", translated)

    # 8. Mixed-language — re-run clean pass; preserves short Latin technical terms
    #    (≤15 chars) for all scripts, strips untranslated English sentences.
    translated = _clean_mixed_lang(translated, tgt_lang)

    # 9. Formatting — normalise whitespace
    translated = re.sub(r" {2,}", " ", translated).strip()

    # 10. Professional — strip any internal debug tokens that may have leaked
    translated = re.sub(r"\[(?:UNK|PAD|BOS|EOS|MASK)\]", "", translated, flags=re.IGNORECASE)
    translated = re.sub(r" {2,}", " ", translated).strip()

    return translated, flags

log = get_logger("translator")

import os as _os
try:
    _gpu = int(_os.environ.get("PIPELINE_GPU", "0"))
except ValueError:
    _gpu = 0
DEVICE       = f"cuda:{_gpu}" if torch.cuda.is_available() else "cpu"
SEAMLESS_DEV = DEVICE
NLLB_DEV     = DEVICE
MODELS_DIR  = Path(__file__).parent.parent / "models"


class Translator:
    # Langs routed via Hindi pivot through IndicTrans2 indic_indic
    # sat: low-resource — pivot via Hindi, then SeamlessM4T as score-based fallback
    _PIVOT_LANGS = {"sat"}

    # Force NLLB as primary — IndicTrans2 outputs Hindi/garbage for these
    # After NLLB, try SeamlessM4T as a score-based second opinion
    # kok (Konkani): IndicTrans2 produces English passthrough + emoji garbage — NLLB is only working option
    # ben: IndicTrans2 en_indic outputs Hindi transliterated into Bengali script — NLLB gives real Bengali
    # mni: both IndicTrans2 and Seamless produce repeated garbage — NLLB has mni_Mtei support
    # mar: IndicTrans2 prepends किवा/किवी/किडे artifacts — NLLB is cleaner
    # ory: IndicTrans2 prepends ମରିଯୁ artifact on every segment — NLLB is cleaner
    # asm: IndicTrans2 prepends টাৰ/টা artifact on every segment — NLLB is cleaner
    # pan: IndicTrans2 prepends ਨਾ ਸਿਰਫ ("not only") on every segment — NLLB is cleaner
    # san: IndicTrans2 prepends ਪਾਲ੍ਯ/ਪਾਲਕ artifacts — NLLB is cleaner
    # doi: IndicTrans2 prepends ਫੋਰਨ/ਫੋਰ artifacts — NLLB is cleaner
    _NLLB_FIRST = {"snd", "kas", "kok", "ben", "mni", "mar", "ory", "asm", "pan", "san", "doi", "mai", "kan", "mal", "tam"}

    # Use Seamless FIRST before IndicTrans2 for these langs
    # (mni moved to NLLB_FIRST — Seamless also produces garbage for Manipuri)
    _SEAMLESS_FIRST: set = set()

    def __init__(self):
        self._indic_trans2: dict = {}
        self._seamless = None
        self._nllb     = None
        self._load_lock = threading.Lock()
        log.info(f"Translator init | device={DEVICE} | mode=offline-only")

    # ----------------------------------------------------------
    # Lazy loaders
    # ----------------------------------------------------------
    def _load_indic_trans2(self, direction: str):
        if direction in self._indic_trans2:
            return self._indic_trans2[direction]
        with self._load_lock:
            if direction in self._indic_trans2:
                return self._indic_trans2[direction]
            from transformers import AutoModelForSeq2SeqLM
            from IndicTransToolkit import IndicProcessor
            # Prefer fine-tuned checkpoint if present — it has better Hindi/Indic quality
            _ckpt = Path(__file__).parent.parent / "checkpoints" / "indictrans" / direction / "best"
            path = str(_ckpt if _ckpt.exists() else MODELS_DIR / "indic_tr" / direction)
            log.info(f"Loading IndicTrans2 ({direction}) from {'checkpoint' if _ckpt.exists() else 'base'} on {DEVICE}")
            # AutoTokenizer passes src_vocab_file as a kwarg which clashes with
            # IndicTransTokenizer's own src_vocab_fp positional param — load the
            # tokenizer class directly from the model's local module to avoid it.
            import importlib, sys
            mod_key = f"transformers_modules.indictrans_{direction}.tokenization_indictrans"
            if mod_key not in sys.modules:
                spec = importlib.util.spec_from_file_location(
                    mod_key,
                    str(Path(path) / "tokenization_indictrans.py")
                )
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_key] = mod
                spec.loader.exec_module(mod)
            else:
                mod = sys.modules[mod_key]
            tokenizer = mod.IndicTransTokenizer(src_vocab_fp=str(Path(path) / "dict.SRC.json"),
                                                tgt_vocab_fp=str(Path(path) / "dict.TGT.json"),
                                                src_spm_fp=str(Path(path) / "model.SRC"),
                                                tgt_spm_fp=str(Path(path) / "model.TGT"))
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            model = AutoModelForSeq2SeqLM.from_pretrained(
                path, trust_remote_code=True, low_cpu_mem_usage=True,
                torch_dtype=dtype,
            )
            model = model.to(DEVICE)
            model.eval()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                # torch.compile gives ~20% speedup on repeated forward passes
                try:
                    model = torch.compile(model, mode="reduce-overhead", fullgraph=False)
                except Exception:
                    pass  # compile unavailable (torch < 2.0 or Windows dynamo issue)
            processor = IndicProcessor(inference=True)
            self._indic_trans2[direction] = {
                "tokenizer": tokenizer, "model": model, "processor": processor
            }
        return self._indic_trans2[direction]

    def _load_seamless(self):
        if self._seamless is None:
            from transformers import AutoProcessor, SeamlessM4Tv2Model
            path = str(MODELS_DIR / "seamless")
            log.info(f"Loading SeamlessM4T on {SEAMLESS_DEV}")
            seamless_model = SeamlessM4Tv2Model.from_pretrained(
                path, torch_dtype=torch.float16, low_cpu_mem_usage=True,
            ).to(SEAMLESS_DEV)
            self._seamless = {
                "processor": AutoProcessor.from_pretrained(path),
                "model": seamless_model,
            }
        return self._seamless

    def translate_speech_to_speech(
        self, audio_path: str, src_lang: str, tgt_lang: str, output_path: str
    ) -> bool:
        """
        SeamlessM4T S2ST: audio file → dubbed audio file in target language.
        Returns True on success. Falls back gracefully on unsupported lang pairs.
        """
        if src_lang not in SEAMLESS_CODES or tgt_lang not in SEAMLESS_CODES:
            log.warning(f"S2ST: {src_lang}/{tgt_lang} not in SEAMLESS_CODES — skipping")
            return False
        if src_lang not in SEAMLESS_S2ST_LANGS or tgt_lang not in SEAMLESS_S2ST_LANGS:
            log.warning(f"S2ST: {src_lang}/{tgt_lang} not in S2ST speech-output langs — skipping")
            return False
        try:
            import soundfile as sf
            import numpy as np
            engine    = self._load_seamless()
            processor = engine["processor"]
            model     = engine["model"]
            audio, sr = sf.read(audio_path, dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            inputs = processor(
                audios=audio, sampling_rate=sr,
                src_lang=SEAMLESS_CODES[src_lang],
                return_tensors="pt",
            ).to(SEAMLESS_DEV)
            inputs = {k: v.to(torch.float16) if v.is_floating_point() else v
                      for k, v in inputs.items()}
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    tgt_lang=SEAMLESS_CODES[tgt_lang],
                    generate_speech=True,
                )
            # SeamlessM4Tv2 returns (waveform_tensor, sample_rate) tuple in newer transformers
            if isinstance(out, tuple):
                wav_tensor, out_sr = out[0], out[1]
            else:
                wav_tensor = out.waveform[0]
                out_sr = model.config.sampling_rate if hasattr(model.config, "sampling_rate") else 16000
            wav = wav_tensor.cpu().float().numpy().squeeze()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, wav, out_sr)
            log.info(f"S2ST: {src_lang}→{tgt_lang} → {output_path}")
            return True
        except Exception as e:
            log.error(f"S2ST failed {src_lang}→{tgt_lang}: {e}")
            return False

    def _load_nllb(self):
        if self._nllb is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            path = str(MODELS_DIR / "nllb")
            log.info(f"Loading NLLB-200 on {NLLB_DEV}")
            self._nllb = {
                "tokenizer": AutoTokenizer.from_pretrained(path),
                "model": AutoModelForSeq2SeqLM.from_pretrained(
                    path, torch_dtype=torch.float16, low_cpu_mem_usage=True,
                ).to(NLLB_DEV),
            }
        return self._nllb

    # ----------------------------------------------------------
    # Core engines (with retry)
    # ----------------------------------------------------------
    @retry(max_attempts=2, delay=1.0)
    def _translate_indic_trans2(self, text: str, src_lang: str, tgt_lang: str) -> str:
        return self._translate_indic_trans2_batch([text], src_lang, tgt_lang)[0]

    def _translate_indic_trans2_batch(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        """src_lang / tgt_lang are flores200 codes e.g. eng_Latn, ben_Beng."""
        direction = ("en_indic"    if src_lang == "eng_Latn" else
                     "indic_en"    if tgt_lang == "eng_Latn" else
                     "indic_indic")
        # Derive short lang code for _clean_mixed_lang (reverse lookup flores200 → short)
        _flores_to_short = {v: k for k, v in __import__(
            'pipeline.lang_config', fromlist=['INDIC_TRANS2_CODES']
        ).INDIC_TRANS2_CODES.items()} if False else {
            v: k for k, v in INDIC_TRANS2_CODES.items()
        }
        tgt_short = _flores_to_short.get(tgt_lang, "eng")
        engine    = self._load_indic_trans2(direction)
        tokenizer = engine["tokenizer"]
        model     = engine["model"]
        processor = engine["processor"]
        # No placeholder protection — __NT__ / __F__ tokens cause hallucination.
        # The model handles technical terms, numbers and URLs natively.
        pairs = [_protect_format_tokens(t) for t in texts]
        fmt_protected = [p[0] for p in pairs]
        fmt_maps      = [p[1] for p in pairs]
        protected_texts = fmt_protected
        nt_maps      = [{} for _ in texts]
        factual_maps = [{} for _ in texts]
        # Per-text Devanagari sub-language rerouting.
        # When src is a Devanagari lang (hin/mai/bod/mar/nep) in indic_indic direction,
        # individual texts may actually be a different Devanagari sub-language.
        # Detect per-text and reroute to the correct src code so IndicTrans2 gets
        # the right language pair. Never passthrough — always translate to tgt_lang.
        _deva_re_batch = re.compile(r'[\u0900-\u097F]')
        _bodo_morph_re = re.compile(
            r'\u0932\u093e\u0902\u0913|\u0916\u093e\u0932\u093e\u092e\u094b'
            r'|\u0917\u0941\u0926\u0941\u0902|\u092c\u093f\u0925\u093f\u0902'
            r'|\u0938\u094b\u0930\u092c\u093f|\u0917\u0947\u091c\u0947\u0930'
            r'|\u0932\u093e\u0935-\u0932\u093e\u0935|\u0916\u092b'
        )
        _mai_morph_re = re.compile(
            r'\u091b\u0925\u093f|\u0905\u091b\u093f|\u0915\u092f\u0932'
            r'|\u091b\u0925\u094d\u0939\u093f|\u091b\u0928\u093f|\u0905\u091b\u0928\u093f'
        )
        _flores_to_short_local = {v: k for k, v in INDIC_TRANS2_CODES.items()}
        _src_short = _flores_to_short_local.get(src_lang, "")
        _tgt_short_local = _flores_to_short_local.get(tgt_lang, "")
        # _rerouted: index → already-translated text (handled outside main batch)
        _rerouted: dict[int, str] = {}
        if direction == "indic_indic" and _src_short in {"hin", "mai", "bod", "mar", "nep"}:
            for _bi, _pt in enumerate(protected_texts):
                if not _deva_re_batch.search(_pt):
                    continue
                if _bodo_morph_re.search(_pt):
                    _detected_sub = "bod"
                elif _mai_morph_re.search(_pt):
                    _detected_sub = "mai"
                else:
                    continue  # no sub-lang override needed
                if _detected_sub == _src_short:
                    continue  # already correct src, no reroute needed
                if _detected_sub in INDIC_TRANS2_CODES:
                    try:
                        _sub_src_code = INDIC_TRANS2_CODES[_detected_sub]
                        _sub_result = self._translate_indic_trans2(
                            _pt, _sub_src_code, tgt_lang)
                        _rerouted[_bi] = _sub_result
                        log.info(f"[batch] Sub-lang reroute idx={_bi}: {_src_short}→{_detected_sub}→{_tgt_short_local}")
                    except Exception as _sub_e:
                        log.warning(f"[batch] Sub-lang reroute failed idx={_bi}: {_sub_e}")
        # Build batch for all texts not already rerouted
        _active_indices = [i for i in range(len(protected_texts)) if i not in _rerouted]
        _active_texts = [protected_texts[i] for i in _active_indices]
        batch  = processor.preprocess_batch(
            _active_texts if _active_texts else [""],
            src_lang=src_lang, tgt_lang=tgt_lang
        )
        model_dtype = next(model.parameters()).dtype
        if _active_texts:
            inputs = tokenizer(
                batch, return_tensors="pt", padding=True,
                truncation=True, max_length=768
            )
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
            inputs = {k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                      for k, v in inputs.items()}
        else:
            inputs = None
        tgt_id = tokenizer.convert_tokens_to_ids(tgt_lang)
        _AGGLUTINATIVE = {"tam", "tel", "mal", "kan", "hin", "mar", "ben", "guj", "pan", "ory", "asm", "mai", "nep", "urd", "bod"}
        max_new_tok  = 1024 if tgt_short in _AGGLUTINATIVE else 768
        ngram_size   = 0    if tgt_short in _AGGLUTINATIVE else 3
        avg_len = sum(len(t) for t in texts) / max(len(texts), 1)
        _DEVA_LANGS_TR = {"hin", "mar", "nep", "mai", "san", "doi", "kok", "bod"}
        if tgt_short in _DEVA_LANGS_TR:
            rep_penalty = 1.3
        elif avg_len < 40:
            rep_penalty = 1.1
        else:
            rep_penalty = 1.2
        if tgt_short in _DEVA_LANGS_TR:
            num_beams = 5
        elif tgt_short in {"tam", "tel", "kan", "mal"}:
            num_beams = 4
        else:
            num_beams = 3
        length_pen = 1.2 if tgt_short in _DEVA_LANGS_TR else 1.0
        # Run model only if there are active (non-rerouted) texts
        if inputs is not None:
            with torch.no_grad():
                output = model.generate(
                    **inputs, forced_bos_token_id=tgt_id,
                    max_new_tokens=max_new_tok, num_beams=num_beams,
                    no_repeat_ngram_size=ngram_size, repetition_penalty=rep_penalty,
                    length_penalty=length_pen,
                    use_cache=True, early_stopping=True,
                )
            decoded = tokenizer.batch_decode(output, skip_special_tokens=True)
            active_results = processor.postprocess_batch(decoded, lang=tgt_lang)
        else:
            active_results = []
        # Fix Tamil script word-boundary merges: IndicTrans2 occasionally fuses
        # two words when the first ends with a vowel sign and the second starts
        # with a consonant (e.g. பனிப்பொழிவாகீழே → பனிப்பொழிவாக கீழே).
        # ONLY insert space when a Tamil vowel sign is immediately followed by
        # a Tamil consonant WITH NO intervening virama (U+0BCD) — virama means
        # the consonant is part of the same akshara cluster, not a new word.
        _TAM_FUSE_RE = re.compile(
            r'([\u0bbe-\u0bc8\u0bca-\u0bcc])(?!\u0bcd)([\u0b95-\u0bb9])'
        )
        if tgt_short == "tam":
            active_results = [_TAM_FUSE_RE.sub(r'\1 \2', t) for t in active_results]

        # Fix multi-sentence truncation: IndicTrans2 drops the first sentence when
        # the input contains two sentences (e.g. "A. B.") — it only translates B.
        # Detect: source has 2+ sentences (split on '. ') but output is suspiciously
        # short relative to the first sentence alone. Re-translate sentence by sentence
        # and concatenate.
        _SENT_SPLIT_RE = re.compile(r'(?<=[.!?\u0964])\s+')
        for _si, _ai in enumerate(_active_indices):
            _src = texts[_ai]
            _out = active_results[_si] if _si < len(active_results) else ""
            _src_sents = [s.strip() for s in _SENT_SPLIT_RE.split(_src) if s.strip()]
            if len(_src_sents) < 2:
                continue
            # If output is shorter than 50% of what the first sentence alone would produce
            # (rough estimate: target chars ≈ source chars * 1.3 for Indic scripts),
            # the first sentence was likely dropped — re-translate sentence by sentence.
            _expected_min = len(_src_sents[0]) * 0.8
            if len(_out) >= _expected_min:
                continue
            try:
                _sent_results = []
                for _sent in _src_sents:
                    _sb = processor.preprocess_batch([_sent], src_lang=src_lang, tgt_lang=tgt_lang)
                    _si2 = tokenizer(_sb, return_tensors="pt", padding=True,
                                     truncation=True, max_length=512)
                    _si2 = {k: v.to(DEVICE) for k, v in _si2.items()}
                    _si2 = {k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                            for k, v in _si2.items()}
                    with torch.no_grad():
                        _so = model.generate(
                            **_si2, forced_bos_token_id=tgt_id,
                            max_new_tokens=max_new_tok, num_beams=num_beams,
                            no_repeat_ngram_size=ngram_size, repetition_penalty=rep_penalty,
                            length_penalty=length_pen, use_cache=True, early_stopping=True,
                        )
                    _sd = tokenizer.batch_decode(_so, skip_special_tokens=True)
                    _sr = processor.postprocess_batch(_sd, lang=tgt_lang)
                    if _sr and _sr[0].strip():
                        _sent_results.append(_sr[0].strip())
                if len(_sent_results) == len(_src_sents):
                    active_results[_si] = " ".join(_sent_results)
                    log.info(f"[multi_sent] Re-translated {len(_src_sents)} sentences for idx={_ai}")
            except Exception as _mse:
                log.warning(f"[multi_sent] Failed idx={_ai}: {_mse}")

        # Merge active_results back into full results list (rerouted slots filled from _rerouted)
        _PREFIX_RE = re.compile(
            r'^(?:'
            r'[\u0900-\u097F]{2,3}\s+'                    # 2-3 Devanagari chars + SPACE
            r'|\u091b\u0947[\u0900-\u097F]{1,4}\s*'       # छे + 1-4 more Devanagari chars (fused artifact)
            r'|\u091a\u0947[\u0900-\u097F]{1,4}\s*'       # चे + 1-4 more Devanagari chars
            # Nepali hallucination prefixes: ते/तेता/तेपनि/तेखार्ने/तेन्जेल/तेपास/तेहिलो etc.
            r'|\u0924\u0947(?:\u0924\u093e|\u092a\u0928\u093f|\u0916\u093e\u0930\u094d\u0928\u0947|\u0928\u094d\u091c\u0947\u0932|\u092a\u093e\u0938|\u0939\u093f\u0932\u094b|\u0928\u0940|\u0924\u094d\u0930\u0948)?\s+'
            # Kannada hallucination prefix: ಸೇದುವು/ಸೇದು/ಸೇಡಂ/ಸೇಬಿನ/ಸೇರ್ಪಡೆಯ (fused or standalone sentence)
            r'|\u0cb8\u0cc7(?:\u0ca6\u0cc1\u0cb5\u0cc1|\u0ca6\u0cc1|\u0ca1\u0c82|\u0cac\u0cbf\u0ca8|\u0ca6\u0ccd|\u0cb2\u0ccd|\u0cac\u0ccd|\u0cb0\u0ccd\u0caa\u0ca1\u0cc6\u0caf)[.\s]+'
            # Bengali: ঔর (Hindi "aur" in Bengali script) as sentence-initial artifact
            r'|\u0994\u09b0\s+'
            # Malayalam: ഛ/ഛെ/ഛമായ/ഘ prefix artifacts
            r'|\u0d1b(?:\u0d2e\u0d3e\u0d2f|\u0d46)?\s*'
            r'|\u0d18\u0d28\u0d3f\u0d7c\u0d2e\u0d4d\u0d2e\u0d3f\u0d24\s*'  # ഘനിർമ്മിത
            # Malayalam seg 9: തൃ prefix
            r'|\u0d24\u0d43\s+'
            # Malayalam seg 10: തവണത്തെ → strip and keep rest
            r'|\u0d24\u0d35\u0d23\u0d24\u0d4d\u0d24\u0d46\s+'
            # Odia: ମରିଯୁ prefix artifact
            r'|\u0b2e\u0b30\u0b3f\u0b2f\u0b41\s*'
            # Assamese: টাৰ/টা prefix artifact
            r'|\u099f\u09be(?:\u09b0)?\s+'
            # Punjabi: ਨਾ ਸਿਰਫ / ਨਾ ਭੁੱਲੋ prefix artifacts
            r'|\u0a28\u0a3e\s+(?:\u0a38\u0a3f\u0a30\u0a2b\u0a3c?|\u0a2d\u0a41\u0a71\u0a32\u0a4b)\s*'
            # Marathi: किवा/किवी/किडे/किवाष्पीकरण prefix artifacts
            r'|\u0915\u093f(?:\u0935\u093e|\u0935\u0940|\u0921\u0947|\u0935\u093e\u0937\u094d\u092a\u0940\u0915\u0930\u0923)\s*'
            # Sanskrit: पाल्य/पालक/पालित/पालन/पाल्यमान prefix artifacts
            r'|\u092a\u093e\u0932(?:\u094d\u092f(?:\u092e\u093e\u0928)?|\u0915|\u093f\u0924|\u0928)\s+'
            # Dogri: फोरन/फोर/ऐम्म/गी prefix artifacts
            r'|\u092b\u094b\u0930(?:\u0928)?\s+'
            r'|\u0910\u092e\u094d\u092e\s+'
            # Urdu: کا / کہ sentence-initial bare preposition artifacts
            r'|(?:\u06a9\u0627|\u06a9\u06c1)\s+'
            r'|[)\]}>]+\s*)'
        )
        active_results = [_PREFIX_RE.sub('', t).strip() for t in active_results]
        # Strip leading punctuation artifacts (comma, semicolon, colon at sentence start)
        # Tamil seg 2 issue: ", ஆறுகள்" — leading comma from dropped subject
        _LEAD_PUNCT_RE = re.compile(r'^[,;:\u0964\u0965]+\s*')
        active_results = [_LEAD_PUNCT_RE.sub('', t).strip() for t in active_results]
        # Reconstruct full results in original order
        results = ["" ] * len(texts)
        for _slot, _ai in enumerate(_active_indices):
            results[_ai] = active_results[_slot] if _slot < len(active_results) else ""
        for _bi, _rt in _rerouted.items():
            results[_bi] = _rt
        # Guard: IndicProcessor postprocess_batch can drop the first subword of a segment
        # when padding causes BOS/EOS bleed in batch mode. Only check active (non-rerouted) slots.
        for _slot, _ai in enumerate(_active_indices):
            _res = results[_ai]
            _orig_text = texts[_ai]
            if _res and len(_res) < len(_orig_text) * 0.35:
                try:
                    _solo_batch = processor.preprocess_batch([_orig_text], src_lang=src_lang, tgt_lang=tgt_lang)
                    _solo_inp   = tokenizer(_solo_batch, return_tensors="pt", padding=True,
                                            truncation=True, max_length=512)
                    _solo_inp   = {k: v.to(DEVICE) for k, v in _solo_inp.items()}
                    _solo_inp   = {k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                                   for k, v in _solo_inp.items()}
                    with torch.no_grad():
                        _solo_out = model.generate(
                            **_solo_inp, forced_bos_token_id=tgt_id,
                            max_new_tokens=max_new_tok, num_beams=num_beams,
                            no_repeat_ngram_size=ngram_size, repetition_penalty=rep_penalty,
                            length_penalty=1.0, use_cache=True, early_stopping=True,
                        )
                    _solo_dec = tokenizer.batch_decode(_solo_out, skip_special_tokens=True)
                    _solo_res = processor.postprocess_batch(_solo_dec, lang=tgt_lang)
                    if _solo_res and len(_solo_res[0]) > len(_res):
                        results[_ai] = _solo_res[0]
                except Exception:
                    pass  # keep original batch result
        # Restore + verify per result: non-translatable first, then factual, then format
        final = []
        for t, nt_map, fmap, fmt_map, orig in zip(results, nt_maps, factual_maps, fmt_maps, texts):
            t = _clean_unk(t)
            t = _clean_mixed_lang(t, tgt_short)  # pass 1: raw engine output
            t = _restore_nontranslatable(t, nt_map)
            t = _restore_factual_tokens(t, fmap)
            t = _verify_factual_tokens(orig, t, fmap)
            t = _restore_format_tokens(t, fmt_map)
            t = _naturalise(t, tgt_lang)
            # Wrong-language drift guard: detect Maithili markers in Hindi output.
            # अछि/छथि/करैत/छनि/कयल are Maithili-exclusive verb forms never found in Hindi.
            # Threshold=2: two hits = definite Maithili drift.
            _MAITHILI_RE = re.compile(
                r'\u0905\u091b\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'   # अछि
                r'|\u091b\u0925\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'   # छथि
                r'|\u0915\u0930\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # करैत
                r'|\u091a\u0932\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # चलैत
                r'|\u0915\u0939\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # कहैत
                r'|\u091b\u0928\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'   # छनि
                r'|\u0905\u091b\u0928\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # अछनि
                r'|\u091b\u0925\u094d\u0939\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # छथ्हि
                r'|\u0915\u092f\u0932(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'   # कयल
                r'|\u091c\u093e\u0907\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # जाइत
                r'|\u0938\u0902(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'          # सँ (Maithili postposition)
                r'|\u091b\u094b\u0921\u093c\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # छोड़ैत
                r'|\u0938\u0915\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # सकैत (Maithili: can)
                r'|\u0916\u0938\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # खसि (Maithili: fell)
                r'|\u091b\u0940(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # Maithili: we are/can
            )
            # Hindi subject-drop guard: verb-initial output = dropped subject
            # Hindi is SOV — sentence starting with verb (no subject) is ungrammatical.
            # e.g. "गर्म करता है" should be "सूर्य गर्म करता है"
            _SUBJ_DROP_RE = re.compile(
                r'^स+(?:ता|ती|ते|ना|नी|ने)'
                r'\s+(?:करता|है|हैं|था|थे)'
            )
            if tgt_short == "hin" and _SUBJ_DROP_RE.match(t):
                log.warning(f"[hin] Subject-drop detected — retrying via NLLB")
                try:
                    nllb_t = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                    if nllb_t.strip():
                        t = _clean_unk(nllb_t)
                except Exception as _sd:
                    log.warning(f"NLLB subject-drop retry failed: {_sd}")
            if tgt_short == "hin":
                _mai_hits = _MAITHILI_RE.findall(t)
                if len(_mai_hits) >= 2:
                    log.warning(f"[hin] Maithili drift detected ({len(_mai_hits)} markers) — retrying via NLLB")
                    try:
                        nllb_t = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                        if nllb_t.strip():
                            t = _clean_unk(nllb_t)
                    except Exception as _nd:
                        log.warning(f"NLLB drift-retry failed: {_nd}")
            # Maithili output drift guard: IndicTrans2 mai_Deva shares Devanagari with Hindi
            # and drifts to Hindi for segments it can't confidently render in Maithili.
            # Hindi verb markers: है/हैं/होता/करता/करते/होती/होते — absent in Maithili
            # (Maithili uses छथि/अछि/छनि/कयल instead). Require 3+ to avoid false positives.
            _HINDI_IN_MAI_RE = re.compile(
                r'\u0939\u0948(?:\u0902)?(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0939\u094b\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0915\u0930\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0915\u0930\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0939\u094b\u0924\u0940(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0939\u094b\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0915\u0940 \u0935\u091c\u0939|\u0915\u0947 \u0932\u093f\u090f'
            )
            if tgt_short == "mai":
                _hin_hits = _HINDI_IN_MAI_RE.findall(t)
                if len(_hin_hits) >= 3:
                    log.warning(f"[mai] Hindi drift detected ({len(_hin_hits)} markers) — retrying via NLLB")
                    try:
                        nllb_t = self._translate_nllb(orig, NLLB_CODES.get("eng", "eng_Latn"), NLLB_CODES["mai"])
                        if nllb_t.strip():
                            t = _clean_unk(nllb_t)
                    except Exception as _nd:
                        log.warning(f"NLLB mai drift-retry failed: {_nd}")
                # Bodo drift guard: Bodo (brx_Deva) uses Devanagari so _clean_mixed_lang
                # cannot strip it from Maithili output. Detect Bodo-exclusive morphemes.
                # लांओ/खालामो/गुदुं/बिथिं/नाय/फारि are Bodo verb/noun suffixes absent in Maithili.
                _BODO_IN_MAI_RE = re.compile(
                    r'\u0932\u093e\u0902\u0913(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u0916\u093e\u0932\u093e\u092e\u094b(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u0917\u0941\u0926\u0941\u0902(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u092c\u093f\u0925\u093f\u0902(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u0928\u093e\u092f\u093e\u0935(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u092b\u093e\u0930\u093f\u0916\u093e\u0928(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u0917\u0947\u091c\u0947\u0930(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                    r'|\u0938\u094b\u0930\u092c\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                )
                _bodo_hits = _BODO_IN_MAI_RE.findall(t)
                if len(_bodo_hits) >= 2:
                    log.warning(f"[mai] Bodo drift detected ({len(_bodo_hits)} markers) — retrying via NLLB")
                    try:
                        nllb_t = self._translate_nllb(orig, NLLB_CODES.get("eng", "eng_Latn"), NLLB_CODES["mai"])
                        if nllb_t.strip():
                            t = _clean_unk(nllb_t)
                    except Exception as _nd:
                        log.warning(f"NLLB mai bodo-drift-retry failed: {_nd}")
            # Bodo drift guard: brx_Deva shares Devanagari with Hindi.
            # Detect Hindi-exclusive verb markers in Bodo output — retry via NLLB.
            _HINDI_IN_BOD_RE = re.compile(
                r'\u0939\u0948(?:\u0902)?(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0939\u094b\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0915\u0930\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0915\u0930\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0939\u094b\u0924\u0940(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                r'|\u0939\u094b\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
            )
            if tgt_short == "bod":
                _hin_in_bod = _HINDI_IN_BOD_RE.findall(t)
                if len(_hin_in_bod) >= 2:
                    log.warning(f"[bod] Hindi drift ({len(_hin_in_bod)} markers) — retrying via NLLB")
                    try:
                        _src_nllb = NLLB_CODES.get("eng", "eng_Latn")
                        nllb_t = self._translate_nllb(orig, _src_nllb, NLLB_CODES["bod"])
                        if nllb_t.strip():
                            t = _clean_unk(nllb_t)
                    except Exception as _bd:
                        log.warning(f"NLLB bod drift-retry failed: {_bd}")
            t, fqc_flags = _final_quality_check(orig, t, tgt_short, fmt_map, nt_map, fmap)
            if fqc_flags:
                log.warning(f"FQC [{tgt_short}] seg flags={fqc_flags}")
            # Subject-drop structural check (single path)
            if tgt_short == "hin":
                _HIN_SUBJ_S = re.compile(
                    r'(?:^|\s)(?:'
                    r'\u0938\u0942\u0930\u094d\u092f|\u092f\u0939|\u0935\u0939|\u0935\u0947|\u0939\u092e'
                    r'|\u092e\u0948\u0902|\u0924\u0941\u092e|\u0906\u092a'
                    r'|\u091c\u0932|\u092a\u093e\u0928\u0940'
                    r'|\u092c\u093e\u0926\u0932|\u0935\u0930\u094d\u0937\u093e'
                    r'|\u092a\u094c\u0927\u0947|\u092a\u0943\u0925\u094d\u0935\u0940'
                    r')(?:\s|$)'
                )
                _HIN_VERB_S = re.compile(
                    r'\u0917\u0930\u094d\u092e\s+\u0915\u0930\u0924\u093e'  # गर्म करता
                    r'|\u0915\u094b\s+\u0917\u0930\u094d\u092e'              # को गर्म (पानी को गर्म)
                    r'|\u0915\u0930\u0924\u093e\s+\u0939\u0948'              # करता है
                    r'|\u0926\u0947\u0924\u093e\s+\u0939\u0948'              # देता है
                    r'|\u0926\u0947\u0924\u0940\s+\u0939\u0948'              # देती है
                    r'|\u092c\u0928\u093e\u0924\u093e'                       # बनाता
                    r'|\u0917\u0930\u094d\u092e\s+\u0915\u0930\u0924\u0940'  # गर्म करती
                )
                if _HIN_VERB_S.search(t) and not _HIN_SUBJ_S.search(t):
                    try:
                        nllb_t = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                        if nllb_t.strip():
                            t = _clean_unk(nllb_t)
                            log.warning(f"[hin] Subject-drop structural (single) — NLLB preferred")
                    except Exception as _sq:
                        log.warning(f"NLLB subject-drop single retry failed: {_sq}")
            final.append(t)
        return final

    @retry(max_attempts=2, delay=2.0)
    def _translate_seamless(self, text: str, src_code: str, tgt_code: str) -> str:
        engine    = self._load_seamless()
        processor = engine["processor"]
        model     = engine["model"]
        inputs    = processor(text=text, src_lang=src_code,
                              return_tensors="pt").to(SEAMLESS_DEV)
        inputs    = {k: v.to(torch.float16) if v.is_floating_point() else v
                     for k, v in inputs.items()}
        with torch.no_grad():
            output = model.generate(**inputs, tgt_lang=tgt_code,
                                    generate_speech=False, num_beams=4,
                                    no_repeat_ngram_size=4, repetition_penalty=1.3)
        return processor.decode(output.sequences[0], skip_special_tokens=True).strip()

    @retry(max_attempts=2, delay=2.0)
    def _translate_nllb(self, text: str, src_code: str, tgt_code: str) -> str:
        engine    = self._load_nllb()
        tokenizer = engine["tokenizer"]
        model     = engine["model"]
        tokenizer.src_lang = src_code
        inputs = tokenizer(text, return_tensors="pt",
                           truncation=True, max_length=512).to(NLLB_DEV)
        tgt_id = tokenizer.convert_tokens_to_ids(tgt_code)
        with torch.no_grad():
            output = model.generate(**inputs, forced_bos_token_id=tgt_id,
                                    max_new_tokens=512, num_beams=4,
                                    no_repeat_ngram_size=4, repetition_penalty=1.3)
        return tokenizer.decode(output[0], skip_special_tokens=True).strip()

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def translate(self, text: str, src_lang: str, tgt_lang: str,
                  glossary=None, detected_lang: str = None) -> dict:
        """
        Returns: {"text": str, "engine": str, "score": dict}
        detected_lang: per-segment detected language (overrides src_lang for routing)
        """
        # Use detected language for routing ONLY for Indic source languages.
        # For English source, Lingua frequently misdetects English ASR output as
        # Hindi/Bodo/Maithili — overriding src_lang in that case routes to the
        # wrong IndicTrans2 direction (indic_indic instead of en_indic).
        if detected_lang and src_lang != "eng" and detected_lang != src_lang:
            log.info(f"Lang override: assumed={src_lang} detected={detected_lang}")
            src_lang = detected_lang

        if src_lang == tgt_lang:
            return {"text": text, "engine": "passthrough", "enhanced": False,
                    "score": {"score": 1.0, "flags": [],
                              "needs_review": False, "failed": False}}

        # Fully non-translatable segments (pure URL / code / path / identifier):
        # pass through unchanged — do not send to any engine.
        if _is_fully_nontranslatable(text):
            return {"text": text, "engine": "passthrough_nontranslatable", "enhanced": False,
                    "score": {"score": 1.0, "flags": [],
                              "needs_review": False, "failed": False}}

        src_name = LANG_NAMES.get(src_lang, src_lang)
        tgt_name = LANG_NAMES.get(tgt_lang, tgt_lang)

        # Protect formatting tokens first, then trademarks, then non-translatable, then factual.
        work_text, fmt_map     = _protect_format_tokens(text)
        work_text, tm_map      = _protect_trademarks(work_text)
        work_text, nt_map      = _protect_nontranslatable(work_text)
        work_text, factual_map = _protect_factual_tokens(work_text)

        translated  = None
        engine_used = None

        use_pivot = (
            (src_lang in self._PIVOT_LANGS or tgt_lang in self._PIVOT_LANGS)
            and src_lang != "hin" and tgt_lang != "hin"
        )
        force_nllb    = src_lang in self._NLLB_FIRST or tgt_lang in self._NLLB_FIRST
        seamless_first = src_lang in self._SEAMLESS_FIRST or tgt_lang in self._SEAMLESS_FIRST

        # 1a. Seamless-first langs — try Seamless before IndicTrans2
        if seamless_first and not force_nllb and \
                src_lang in SEAMLESS_CODES and tgt_lang in SEAMLESS_CODES:
            try:
                translated  = self._translate_seamless(
                    work_text, SEAMLESS_CODES[src_lang], SEAMLESS_CODES[tgt_lang])
                engine_used = "seamless"
            except Exception as e:
                log.warning(f"Seamless-first failed {src_name}\u2192{tgt_name}: {e}")
            # IndicTrans2 second opinion for Hindi — pick whichever scores higher
            if translated and tgt_lang == "hin" and \
                    src_lang in INDIC_TRANS2_CODES and tgt_lang in INDIC_TRANS2_CODES:
                try:
                    indic_out = self._translate_indic_trans2(
                        work_text,
                        INDIC_TRANS2_CODES[src_lang],
                        INDIC_TRANS2_CODES[tgt_lang])
                    # Score on original text (not work_text which has __F0__ placeholders)
                    s_seamless = score_segment(text, translated,  src_lang, tgt_lang)["score"]
                    s_indic    = score_segment(text, indic_out,   src_lang, tgt_lang)["score"]
                    if s_indic > s_seamless + 0.05:
                        translated  = indic_out
                        engine_used = "indictrans2"
                        log.info(f"[hin] IndicTrans2 ({s_indic:.2f}) beat Seamless ({s_seamless:.2f})")
                except Exception as e:
                    log.warning(f"IndicTrans2 second-opinion failed {src_name}\u2192{tgt_name}: {e}")

        # 1b. NLLB-first langs (kas, snd) — NLLB primary, then SeamlessM4T score-based fallback
        if translated is None and force_nllb and \
                src_lang in NLLB_CODES and tgt_lang in NLLB_CODES:
            try:
                nllb_out    = self._translate_nllb(
                    work_text, NLLB_CODES[src_lang], NLLB_CODES[tgt_lang])
                translated  = nllb_out
                engine_used = "nllb"
            except Exception as e:
                log.warning(f"NLLB-first failed {src_name}\u2192{tgt_name}: {e}")
            # SeamlessM4T second opinion — pick whichever scores higher
            if translated and src_lang in SEAMLESS_CODES and tgt_lang in SEAMLESS_CODES:
                try:
                    seamless_out = self._translate_seamless(
                        work_text, SEAMLESS_CODES[src_lang], SEAMLESS_CODES[tgt_lang])
                    s_nllb     = score_segment(work_text, translated,   src_lang, tgt_lang)["score"]
                    s_seamless = score_segment(work_text, seamless_out, src_lang, tgt_lang)["score"]
                    if s_seamless > s_nllb + 0.05:  # only switch if meaningfully better
                        translated  = seamless_out
                        engine_used = "seamless"
                        log.info(f"[{tgt_lang}] SeamlessM4T ({s_seamless:.2f}) beat NLLB ({s_nllb:.2f}) — using Seamless")
                except Exception as e:
                    log.warning(f"SeamlessM4T second-opinion failed {src_name}\u2192{tgt_name}: {e}")

        # 1c. IndicTrans2 — primary for all other langs
        if translated is None and not force_nllb and \
                src_lang in INDIC_TRANS2_CODES and tgt_lang in INDIC_TRANS2_CODES:
            try:
                if use_pivot:
                    translated  = self._pivot_via_hindi(work_text, src_lang, tgt_lang)
                else:
                    translated  = self._translate_indic_trans2(
                        work_text,
                        INDIC_TRANS2_CODES[src_lang],
                        INDIC_TRANS2_CODES[tgt_lang])
                engine_used = "indictrans2"
            except Exception as e:
                log.warning(f"IndicTrans2 failed {src_name}\u2192{tgt_name}: {e}")

        # 2. SeamlessM4T fallback (for pivot langs that failed, and non-nllb-first langs)
        if translated is None and not force_nllb and not seamless_first and \
                src_lang in SEAMLESS_CODES and tgt_lang in SEAMLESS_CODES:
            try:
                translated  = self._translate_seamless(
                    work_text, SEAMLESS_CODES[src_lang], SEAMLESS_CODES[tgt_lang])
                engine_used = "seamless"
            except Exception as e:
                log.warning(f"SeamlessM4T failed {src_name}\u2192{tgt_name}: {e}")

        # For pivot langs (mni/sat): if IndicTrans2 pivot succeeded but score is low,
        # try SeamlessM4T as a score-based alternative
        if translated and use_pivot and \
                src_lang in SEAMLESS_CODES and tgt_lang in SEAMLESS_CODES:
            try:
                s_pivot = score_segment(work_text, translated, src_lang, tgt_lang)["score"]
                if s_pivot < 0.50:  # pivot quality is poor — try Seamless
                    seamless_out = self._translate_seamless(
                        work_text, SEAMLESS_CODES[src_lang], SEAMLESS_CODES[tgt_lang])
                    s_seamless = score_segment(work_text, seamless_out, src_lang, tgt_lang)["score"]
                    if s_seamless > s_pivot:
                        translated  = seamless_out
                        engine_used = "seamless"
                        log.info(f"[{tgt_lang}] SeamlessM4T ({s_seamless:.2f}) beat pivot ({s_pivot:.2f})")
            except Exception as e:
                log.warning(f"Pivot score-check Seamless failed {src_name}\u2192{tgt_name}: {e}")

        # 3. NLLB-200 — final fallback for everything
        if translated is None and \
                src_lang in NLLB_CODES and tgt_lang in NLLB_CODES:
            try:
                translated  = self._translate_nllb(
                    work_text, NLLB_CODES[src_lang], NLLB_CODES[tgt_lang])
                engine_used = "nllb"
            except Exception as e:
                log.warning(f"NLLB failed {src_name}\u2192{tgt_name}: {e}")

        if translated is None:
            raise RuntimeError(
                f"All translation engines failed: {src_name} → {tgt_name}")

        translated = _clean_unk(translated)
        translated = _clean_mixed_lang(translated, tgt_lang)  # pass 1: engine output
        translated = _restore_nontranslatable(translated, nt_map)
        translated = _restore_trademarks(translated, tm_map)
        translated = _restore_factual_tokens(translated, factual_map)
        translated = _verify_factual_tokens(text, translated, factual_map)
        translated = _restore_format_tokens(translated, fmt_map)
        translated = _naturalise(translated, tgt_lang)
        # Rule 20: final quality gate covers pass-2 mixed-lang clean internally
        translated, fqc_flags = _final_quality_check(
            text, translated, tgt_lang, fmt_map, nt_map, factual_map)
        if fqc_flags:
            log.warning(f"FQC [{tgt_lang}] flags={fqc_flags}")

        # Rule 12: glossary applied last — after all cleaning, never overwritten
        if glossary:
            translated = glossary.apply(text, src_lang, tgt_lang, translated)

        quality = score_segment(text, translated, src_lang, tgt_lang)
        if fqc_flags:
            quality["flags"] = quality.get("flags", []) + fqc_flags
            quality["needs_review"] = True
        log.info(f"[{engine_used}] {src_name}→{tgt_name} "
                 f"score={quality['score']} flags={quality['flags']}")

        return {"text": translated, "engine": engine_used, "enhanced": False, "score": quality}

    def translate_text(self, text: str, src_lang: str, tgt_lang: str,
                       glossary=None, detected_lang: str = None) -> str:
        return self.translate(text, src_lang, tgt_lang, glossary=glossary,
                              detected_lang=detected_lang)["text"]

    def translate_document_batch(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        """
        Document-mode translation. Always uses base model.
        Returns list[str] (translated texts, 1-to-1 with input).
        """
        needs_pivot    = (src_lang in self._PIVOT_LANGS or tgt_lang in self._PIVOT_LANGS) \
                         and src_lang != "hin" and tgt_lang != "hin"
        force_nllb     = src_lang in self._NLLB_FIRST or tgt_lang in self._NLLB_FIRST
        seamless_first = src_lang in self._SEAMLESS_FIRST or tgt_lang in self._SEAMLESS_FIRST
        results        = []

        # IndicTrans2 batch path
        if not needs_pivot and not force_nllb and not seamless_first \
                and src_lang in INDIC_TRANS2_CODES and tgt_lang in INDIC_TRANS2_CODES:
            try:
                src_code  = INDIC_TRANS2_CODES[src_lang]
                tgt_code  = INDIC_TRANS2_CODES[tgt_lang]
                direction = ("en_indic"    if src_code == "eng_Latn" else
                             "indic_en"    if tgt_code == "eng_Latn" else
                             "indic_indic")
                engine    = self._load_indic_trans2(direction)
                batch     = engine["processor"].preprocess_batch(texts, src_lang=src_code, tgt_lang=tgt_code)
                inputs    = engine["tokenizer"](batch, return_tensors="pt", padding=True,
                                               truncation=True, max_length=512)
                model_dtype = next(engine["model"].parameters()).dtype
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                inputs = {k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                          for k, v in inputs.items()}
                tgt_id = engine["tokenizer"].convert_tokens_to_ids(tgt_code)
                _tgt_short = {v: k for k, v in INDIC_TRANS2_CODES.items()}.get(tgt_code, "eng")
                _AGGLUTINATIVE = {"tam", "tel", "mal", "kan", "hin", "mar", "ben", "guj", "pan", "ory", "asm", "mai", "nep", "urd", "bod"}
                _max_tok  = 1024 if _tgt_short in _AGGLUTINATIVE else 768
                _ngram    = 0    if _tgt_short in _AGGLUTINATIVE else 3
                _DEVA_DOC = {"hin", "mar", "nep", "mai", "san", "doi", "kok", "bod"}
                _doc_beams = 5 if _tgt_short in _DEVA_DOC else (4 if _tgt_short in {"tam", "tel", "kan", "mal"} else 3)
                _doc_rep   = 1.3 if _tgt_short in _DEVA_DOC else 1.1
                with torch.no_grad():
                    output = engine["model"].generate(
                        **inputs, forced_bos_token_id=tgt_id,
                        max_new_tokens=_max_tok, num_beams=_doc_beams,
                        no_repeat_ngram_size=_ngram, repetition_penalty=_doc_rep,
                        length_penalty=1.0, use_cache=True, early_stopping=True,
                    )
                decoded = engine["tokenizer"].batch_decode(output, skip_special_tokens=True)
                results = engine["processor"].postprocess_batch(decoded, lang=tgt_code)
                return [_clean_unk(t) if t.strip() else src for t, src in zip(results, texts)]
            except Exception as e:
                log.warning(f"Doc batch IndicTrans2 failed ({src_lang}→{tgt_lang}): {e}")

        # Fallback: per-paragraph via pivot / NLLB
        for text in texts:
            try:
                if needs_pivot and not force_nllb \
                        and src_lang in INDIC_TRANS2_CODES and tgt_lang in INDIC_TRANS2_CODES:
                    t = self._pivot_via_hindi(text, src_lang, tgt_lang)
                elif src_lang in NLLB_CODES and tgt_lang in NLLB_CODES:
                    t = self._translate_nllb(text, NLLB_CODES[src_lang], NLLB_CODES[tgt_lang])
                else:
                    t = text
                results.append(_clean_unk(t) if t.strip() else text)
            except Exception as e:
                log.warning(f"Doc para fallback failed: {e}")
                results.append(text)
        return results

    def translate_batch(self, texts: list[str], src_lang: str, tgt_lang: str,
                        glossary=None, detected_langs: list[str] = None) -> list[dict]:
        needs_pivot   = (
            (src_lang in self._PIVOT_LANGS or tgt_lang in self._PIVOT_LANGS)
            and src_lang != "hin" and tgt_lang != "hin"
        )
        force_nllb    = src_lang in self._NLLB_FIRST or tgt_lang in self._NLLB_FIRST
        seamless_first = src_lang in self._SEAMLESS_FIRST or tgt_lang in self._SEAMLESS_FIRST

        # True GPU batch for IndicTrans2 — skip for pivot/nllb-only/seamless-first
        if (not needs_pivot and not force_nllb and not seamless_first
                and src_lang in INDIC_TRANS2_CODES
                and tgt_lang in INDIC_TRANS2_CODES):
            try:
                work_texts       = texts
                if glossary:
                    pass  # no pre-protection; apply glossary post-translation
                translated_list = self._translate_indic_trans2_batch(
                    work_texts, INDIC_TRANS2_CODES[src_lang], INDIC_TRANS2_CODES[tgt_lang])
                # Completeness guard: output must match input 1-to-1
                if len(translated_list) != len(texts):
                    raise RuntimeError(
                        f"Completeness violation: sent {len(texts)} texts, "
                        f"got {len(translated_list)} translations back"
                    )
                results = []
                for i, (orig, trans) in enumerate(zip(texts, translated_list)):
                    # Never emit empty translation for non-empty source — retry via single translate()
                    if not trans.strip() and orig.strip():
                        log.warning(
                            f"Batch completeness: empty translation at index {i} — "
                            f"retrying per-segment"
                        )
                        try:
                            trans = self._translate_indic_trans2(
                                orig, INDIC_TRANS2_CODES[src_lang], INDIC_TRANS2_CODES[tgt_lang])
                        except Exception:
                            trans = ""  # silence is better than wrong-language audio
                    # length_penalty: >1.0 encourages longer outputs — better for
                    # Hindi which tends to produce shorter translations than source
                    t = _clean_unk(trans)
                    t = _clean_mixed_lang(t, tgt_lang)
                    t = _naturalise(t, tgt_lang)
                    # Wrong-language drift guard for Hindi — threshold=2
                    _MAITHILI_BATCH_RE = re.compile(
                        r'\u0905\u091b\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u091b\u0925\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0915\u0930\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u091a\u0932\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0915\u0939\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u091b\u0928\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0905\u091b\u0928\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u091b\u0925\u094d\u0939\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0915\u092f\u0932(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u091c\u093e\u0907\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0938\u0902(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u091b\u094b\u0921\u093c\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0938\u0915\u0948\u0924(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # सकैत (Maithili: can)
                        r'|\u0916\u0938\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # खसि (Maithili: fell/fall)
                        r'|\u091b\u0940(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'  # Maithili: we are/can
                    )
                    # Hindi subject-drop guard (batch path)
                    _SUBJ_DROP_RE_B = re.compile(
                        r'^स+(?:ता|ती|ते|ना|नी|ने)'
                        r'\s+(?:करता|है|हैं|था|थे)'
                    )
                    if tgt_lang == "hin" and _SUBJ_DROP_RE_B.match(t):
                        log.warning(f"[hin] Subject-drop in batch idx={i} — retrying via NLLB")
                        try:
                            nllb_t = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                            if nllb_t.strip():
                                t = _clean_unk(nllb_t)
                        except Exception as _sd:
                            log.warning(f"NLLB subject-drop batch retry failed: {_sd}")
                    _mai_batch_hits = _MAITHILI_BATCH_RE.findall(t)
                    if len(_mai_batch_hits) >= 2:
                        log.warning(f"[hin] Maithili drift in batch idx={i} ({len(_mai_batch_hits)} markers) — retrying via NLLB")
                        try:
                            nllb_t = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                            if nllb_t.strip():
                                t = _clean_unk(nllb_t)
                        except Exception as _nd:
                            log.warning(f"NLLB drift-retry failed: {_nd}")
                    _HINDI_IN_MAI_BATCH_RE = re.compile(
                        r'\u0939\u0948(?:\u0902)?(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0939\u094b\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0915\u0930\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0915\u0930\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0939\u094b\u0924\u0940(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0939\u094b\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        r'|\u0915\u0940 \u0935\u091c\u0939|\u0915\u0947 \u0932\u093f\u090f'
                    )
                    if tgt_lang == "bod":
                        _HINDI_IN_BOD_BATCH_RE = re.compile(
                            r'\u0939\u0948(?:\u0902)?(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0939\u094b\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0915\u0930\u0924\u093e(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0915\u0930\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0939\u094b\u0924\u0940(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0939\u094b\u0924\u0947(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        )
                        _hin_in_bod_batch = _HINDI_IN_BOD_BATCH_RE.findall(t)
                        if len(_hin_in_bod_batch) >= 2:
                            log.warning(f"[bod] Hindi drift in batch idx={i} ({len(_hin_in_bod_batch)} markers) — retrying via NLLB")
                            try:
                                nllb_t = self._translate_nllb(orig, NLLB_CODES.get("eng", "eng_Latn"), NLLB_CODES["bod"])
                                if nllb_t.strip():
                                    t = _clean_unk(nllb_t)
                            except Exception as _bd:
                                log.warning(f"NLLB bod batch drift-retry failed: {_bd}")
                    if tgt_lang == "mai":
                        _hin_batch_hits = _HINDI_IN_MAI_BATCH_RE.findall(t)
                        if len(_hin_batch_hits) >= 3:
                            log.warning(f"[mai] Hindi drift in batch idx={i} ({len(_hin_batch_hits)} markers) — retrying via NLLB")
                            try:
                                nllb_t = self._translate_nllb(orig, NLLB_CODES.get("eng", "eng_Latn"), NLLB_CODES["mai"])
                                if nllb_t.strip():
                                    t = _clean_unk(nllb_t)
                            except Exception as _nd:
                                log.warning(f"NLLB mai batch drift-retry failed: {_nd}")
                        _BODO_IN_MAI_BATCH_RE = re.compile(
                            r'\u0932\u093e\u0902\u0913(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0916\u093e\u0932\u093e\u092e\u094b(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0917\u0941\u0926\u0941\u0902(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u092c\u093f\u0925\u093f\u0902(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0928\u093e\u092f\u093e\u0935(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u092b\u093e\u0930\u093f\u0916\u093e\u0928(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0917\u0947\u091c\u0947\u0930(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                            r'|\u0938\u094b\u0930\u092c\u093f(?=[\s\u0964\u0965]|$|[^\u0900-\u097F])'
                        )
                        _bodo_batch_hits = _BODO_IN_MAI_BATCH_RE.findall(t)
                        if len(_bodo_batch_hits) >= 2:
                            log.warning(f"[mai] Bodo drift in batch idx={i} ({len(_bodo_batch_hits)} markers) — retrying via NLLB")
                            try:
                                nllb_t = self._translate_nllb(orig, NLLB_CODES.get("eng", "eng_Latn"), NLLB_CODES["mai"])
                                if nllb_t.strip():
                                    t = _clean_unk(nllb_t)
                            except Exception as _nd:
                                log.warning(f"NLLB mai bodo batch drift-retry failed: {_nd}")
                    # Hindi NLLB second-opinion: IndicTrans2 drops subjects for Hindi.
                    # Structural check: if output has a transitive verb but no nominative
                    # subject (pronoun or common noun) before it, prefer NLLB.
                    if tgt_lang == "hin":
                        _HIN_SUBJ_NOUNS = re.compile(
                            r'(?:^|\s)(?:'
                            r'\u0938\u0942\u0930\u094d\u092f'   # सूर्य
                            r'|\u092f\u0939|\u0935\u0939|\u0935\u0947|\u0939\u092e'  # यह वह वे हम
                            r'|\u092e\u0948\u0902|\u0924\u0941\u092e|\u0906\u092a'  # मैं तुम आप
                            r'|\u091c\u0932|\u092a\u093e\u0928\u0940'  # जल पानी
                            r'|\u092c\u093e\u0926\u0932|\u0935\u0930\u094d\u0937\u093e'  # बादल वर्षा
                            r'|\u092a\u094c\u0927\u0947|\u092a\u0943\u0925\u094d\u0935\u0940'  # पौधे पृथ्वी
                            r')(?:\s|$)'
                        )
                        _HIN_TRANS_VERB = re.compile(
                            r'\u0917\u0930\u094d\u092e\s+\u0915\u0930\u0924\u093e'  # गर्म करता
                            r'|\u0915\u094b\s+\u0917\u0930\u094d\u092e'              # को गर्म
                            r'|\u0915\u0930\u0924\u093e\s+\u0939\u0948'              # करता है
                            r'|\u0926\u0947\u0924\u093e\s+\u0939\u0948'              # देता है
                            r'|\u0926\u0947\u0924\u0940\s+\u0939\u0948'              # देती है
                            r'|\u092c\u0928\u093e\u0924\u093e'                       # बनाता
                            r'|\u0917\u0930\u094d\u092e\s+\u0915\u0930\u0924\u0940'  # गर्म करती
                        )
                        _has_subj = bool(_HIN_SUBJ_NOUNS.search(t))
                        _has_verb = bool(_HIN_TRANS_VERB.search(t))
                        if _has_verb and not _has_subj:
                            try:
                                _nllb_2nd = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                                if _nllb_2nd.strip():
                                    t = _clean_unk(_nllb_2nd)
                                    log.info(f"[hin] Subject-drop structural — NLLB preferred")
                            except Exception as _n2:
                                pass
                        elif _nllb_2nd_len := 0:  # dead branch — keep old length fallback disabled
                            pass
                    # Rule 20: final quality gate — all 10 checks
                    t, fqc_flags = _final_quality_check(orig, t, tgt_lang, {}, {}, {})
                    if fqc_flags:
                        log.warning(f"FQC batch [{tgt_lang}] idx={i} flags={fqc_flags}")
                    # If Hindi output is suspiciously short (subject dropped), retry via NLLB
                    if tgt_lang == "hin" and "fqc:suspiciously_short" in fqc_flags:
                        try:
                            nllb_t = self._translate_nllb(orig, NLLB_CODES["eng"], NLLB_CODES["hin"])
                            if nllb_t.strip() and len(nllb_t) > len(t):
                                t = _clean_unk(nllb_t)
                                log.warning(f"[hin] Short batch output — NLLB retry gave longer result")
                        except Exception as _sq:
                            log.warning(f"NLLB short-output batch retry failed: {_sq}")
                    # Rule 12: glossary applied last so it is never overwritten
                    if glossary:
                        t = glossary.apply(orig, src_lang, tgt_lang, t)
                    q = score_segment(orig, t, src_lang, tgt_lang)
                    if fqc_flags:
                        q["flags"] = q.get("flags", []) + fqc_flags
                        q["needs_review"] = True
                    results.append({"text": t, "engine": "indictrans2", "enhanced": False, "score": q})
                summary = review_summary([r["score"] for r in results])
                log.info(f"Batch [{tgt_lang}] {len(texts)} segs | "
                         f"avg_score={summary['avg_score']} "
                         f"needs_review={summary['needs_review']}/{summary['total']}")
                return results
            except Exception as e:
                log.warning(f"Batch IndicTrans2 failed, falling back to per-segment: {e}")

        # Pivot langs or fallback: per-segment
        results = [
            self.translate(t, src_lang, tgt_lang, glossary=glossary,
                           detected_lang=(detected_langs[i] if detected_langs else None))
            for i, t in enumerate(texts)
        ]
        summary = review_summary([r["score"] for r in results])
        log.info(f"Batch [{tgt_lang}] {len(texts)} segs | "
                 f"avg_score={summary['avg_score']} "
                 f"needs_review={summary['needs_review']}/{summary['total']}")
        return results

    def _pivot_via_hindi(self, text: str, src_lang: str, tgt_lang: str) -> str:
        # Step 1: src → Hindi (skip if src is already Hindi or English going direct)
        if src_lang == "hin":
            mid = text
        else:
            mid = self._translate_indic_trans2(
                text, INDIC_TRANS2_CODES[src_lang], INDIC_TRANS2_CODES["hin"])
        # Step 2: Hindi → tgt (skip if tgt is Hindi)
        if tgt_lang == "hin":
            return mid
        return self._translate_indic_trans2(
            mid, INDIC_TRANS2_CODES["hin"], INDIC_TRANS2_CODES[tgt_lang])
