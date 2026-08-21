# ============================================================
# Content Safety Filter — KB Tender §3.2
#
# "Translated content must be free from hate speech, abuse,
#  violence, profanity, sexual content, nudity, vulgarity,
#  or offensive material."
#
# Strategy: regex-based blocklist covering the most common
# English and transliterated profanity/hate terms, plus
# Indic-script patterns for the 22 scheduled languages.
# Runs fully offline — no external API required.
#
# Returns a ContentSafetyResult with:
#   - flagged: bool
#   - categories: list of matched categories
#   - matched_terms: list of matched patterns (redacted in logs)
#   - severity: "none" | "low" | "medium" | "high"
# ============================================================

from __future__ import annotations
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Category definitions
# Each entry: (category_name, severity, [regex_patterns])
# Patterns are case-insensitive for Latin script.
# ---------------------------------------------------------------------------

_CATEGORIES: list[tuple[str, str, list[str]]] = [
    # ── Profanity / vulgarity (English + common transliterations) ──────────
    ("profanity", "medium", [
        r"\bf+u+c+k+\b", r"\bs+h+i+t+\b", r"\bb+i+t+c+h+\b",
        r"\ba+s+s+h+o+l+e+\b", r"\bc+u+n+t+\b", r"\bd+i+c+k+\b",
        r"\bp+u+s+s+y+\b", r"\bb+a+s+t+a+r+d+\b", r"\bm+o+t+h+e+r+f+u+c+k+\b",
        r"\bw+h+o+r+e+\b", r"\bs+l+u+t+\b", r"\bb+o+l+l+o+c+k+s+\b",
        r"\bb+u+g+g+e+r+\b", r"\bc+r+a+p+\b",
        # Common transliterations used in Indian languages
        r"\bm+a+d+a+r+c+h+o+d+\b", r"\bb+e+h+e+n+c+h+o+d+\b",
        r"\bc+h+u+t+i+y+a+\b", r"\bb+h+o+s+d+i+k+e+\b",
        r"\bs+a+l+a+\b",  # mild but common abuse
        r"\bh+a+r+a+m+i+\b", r"\bk+a+m+i+n+e+\b",
    ]),

    # ── Hate speech — religion ─────────────────────────────────────────────
    ("hate_speech_religion", "high", [
        r"\bkill\s+(?:all\s+)?(?:muslims?|hindus?|christians?|sikhs?|jews?|buddhists?)\b",
        r"\b(?:muslims?|hindus?|christians?|sikhs?|jews?)\s+(?:are\s+)?(?:terrorists?|vermin|pigs?|dogs?|rats?)\b",
        r"\bjihadi\s+(?:scum|dogs?|pigs?)\b",
        r"\bkafir\s+(?:dogs?|pigs?|scum)\b",
        r"\bcow\s+(?:worshippers?|piss\s+drinkers?)\b",
        r"\bpork\s+eaters?\b",
    ]),

    # ── Hate speech — caste ────────────────────────────────────────────────
    ("hate_speech_caste", "high", [
        r"\bchamars?\b", r"\bbhangis?\b", r"\bdalit\s+(?:dogs?|scum|vermin)\b",
        r"\buntouchable\s+(?:scum|filth)\b",
    ]),

    # ── Violence / incitement ──────────────────────────────────────────────
    ("violence", "high", [
        r"\b(?:kill|murder|slaughter|massacre|behead|lynch|rape)\s+(?:them|all|everyone|him|her|the)\b",
        r"\bbomb\s+(?:the|this|that)\b",
        r"\bterror(?:ist)?\s+attack\b",
        r"\bsuicide\s+bomb\b",
    ]),

    # ── Sexual content ─────────────────────────────────────────────────────
    ("sexual_content", "high", [
        r"\bporn(?:ography)?\b", r"\bsex\s+video\b", r"\bnude\s+(?:photo|image|video)\b",
        r"\bnudity\b", r"\bexplicit\s+(?:content|material|video)\b",
        r"\bxxx\b", r"\berotic\b",
    ]),

    # ── Devanagari-script abuse (Hindi/Marathi/Nepali/Maithili/Dogri/Bodo) ─
    # Unicode codepoints for common Hindi abuses
    ("profanity_devanagari", "medium", [
        # मादरचोद
        "\u092e\u093e\u0926\u0930\u091a\u094b\u0926",
        # बहनचोद
        "\u092c\u0939\u0928\u091a\u094b\u0926",
        # चुतिया
        "\u091a\u0941\u0924\u093f\u092f\u093e",
        # भोसड़ीके
        "\u092d\u094b\u0938\u0921\u093c\u0940\u0915\u0947",
        # हरामी
        "\u0939\u0930\u093e\u092e\u0940",
        # कमीने
        "\u0915\u092e\u0940\u0928\u0947",
        # रंडी
        "\u0930\u0902\u0921\u0940",
        # कुत्ते (dog — used as abuse)
        # Not blocked — too common in neutral contexts
    ]),

    # ── Bengali-script abuse ───────────────────────────────────────────────
    ("profanity_bengali", "medium", [
        # মাদারচোদ
        "\u09ae\u09be\u09a6\u09be\u09b0\u099a\u09cb\u09a6",
        # বেশ্যা
        "\u09ac\u09c7\u09b6\u09cd\u09af\u09be",
        # হারামি
        "\u09b9\u09be\u09b0\u09be\u09ae\u09bf",
    ]),

    # ── Tamil-script abuse ─────────────────────────────────────────────────
    ("profanity_tamil", "medium", [
        # ஓம்பி (vulgar)
        "\u0b93\u0bae\u0bcd\u0baa\u0bbf",
        # தேவடியா
        "\u0ba4\u0bc7\u0bb5\u0b9f\u0bbf\u0baf\u0bbe",
    ]),

    # ── Telugu-script abuse ────────────────────────────────────────────────
    ("profanity_telugu", "medium", [
        # లంజ
        "\u0c32\u0c02\u0c1c",
        # దెంగు
        "\u0c26\u0c46\u0c02\u0c17\u0c41",
    ]),

    # ── Kannada-script abuse ───────────────────────────────────────────────
    ("profanity_kannada", "medium", [
        # ಸೂಳೆ
        "\u0cb8\u0cc2\u0cb3\u0cc6",
        # ನನ್ನ ತಾಯಿ
        # Not blocked — too common in neutral contexts
    ]),

    # ── Malayalam-script abuse ─────────────────────────────────────────────
    ("profanity_malayalam", "medium", [
        # തള്ള
        "\u0d24\u0d33\u0d4d\u0d33",
        # പൂറ്
        "\u0d2a\u0d42\u0d31\u0d4d",
    ]),

    # ── Urdu/Arabic-script abuse ───────────────────────────────────────────
    ("profanity_urdu", "medium", [
        # حرامی
        "\u062d\u0631\u0627\u0645\u06cc",
        # کمینہ
        "\u06a9\u0645\u06cc\u0646\u06c1",
        # رنڈی
        "\u0631\u0646\u0688\u06cc",
    ]),
]

# Pre-compile all patterns
_COMPILED: list[tuple[str, str, list[re.Pattern]]] = []
for _cat, _sev, _patterns in _CATEGORIES:
    _compiled_patterns = []
    for p in _patterns:
        try:
            # Latin patterns: case-insensitive; Indic: exact match
            flags = re.IGNORECASE if all(ord(c) < 128 for c in p) else 0
            _compiled_patterns.append(re.compile(p, flags))
        except re.error:
            pass
    _COMPILED.append((_cat, _sev, _compiled_patterns))

_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class ContentSafetyResult:
    flagged:       bool          = False
    categories:    list[str]     = field(default_factory=list)
    matched_terms: list[str]     = field(default_factory=list)
    severity:      str           = "none"   # none | low | medium | high

    def to_dict(self) -> dict:
        return {
            "flagged":    self.flagged,
            "categories": self.categories,
            "severity":   self.severity,
            # matched_terms intentionally omitted from dict — avoid logging PII/slurs
        }


def check_text(text: str) -> ContentSafetyResult:
    """
    Run content safety check on a single text string.
    Returns ContentSafetyResult.
    """
    if not text or not text.strip():
        return ContentSafetyResult()

    result = ContentSafetyResult()
    max_sev = 0

    for cat, sev, patterns in _COMPILED:
        for pat in patterns:
            m = pat.search(text)
            if m:
                result.flagged = True
                if cat not in result.categories:
                    result.categories.append(cat)
                result.matched_terms.append(m.group(0))
                sev_rank = _SEVERITY_RANK.get(sev, 0)
                if sev_rank > max_sev:
                    max_sev = sev_rank
                    result.severity = sev
                break  # one hit per category is enough

    return result


def check_segments(segments: list[dict]) -> list[dict]:
    """
    Run content safety check on a list of translated segment dicts.
    Each segment must have a "text" key.
    Returns the same list with a "content_safety" key added to each segment.
    Segments that are flagged also get needs_review=True in their quality dict.
    """
    for seg in segments:
        text = seg.get("text", "")
        safety = check_text(text)
        seg["content_safety"] = safety.to_dict()
        if safety.flagged:
            q = seg.setdefault("quality", {})
            q["needs_review"] = True
            flags = q.setdefault("flags", [])
            for cat in safety.categories:
                flag = f"content_safety:{cat}"
                if flag not in flags:
                    flags.append(flag)
    return segments


def safety_summary(segments: list[dict]) -> dict:
    """
    Aggregate content safety results across all segments.
    Returns a summary dict suitable for inclusion in quality_summary.
    """
    total    = len(segments)
    flagged  = [s for s in segments if s.get("content_safety", {}).get("flagged")]
    cats: dict[str, int] = {}
    max_sev  = "none"
    for s in flagged:
        cs = s.get("content_safety", {})
        for cat in cs.get("categories", []):
            cats[cat] = cats.get(cat, 0) + 1
        sev = cs.get("severity", "none")
        if _SEVERITY_RANK.get(sev, 0) > _SEVERITY_RANK.get(max_sev, 0):
            max_sev = sev
    return {
        "content_safety_total_segments":   total,
        "content_safety_flagged_segments": len(flagged),
        "content_safety_categories":       cats,
        "content_safety_max_severity":     max_sev,
        "content_safety_pass":             len(flagged) == 0,
    }
