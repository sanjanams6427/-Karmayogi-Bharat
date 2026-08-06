# ============================================================
# Translation Quality Scorer
# Heuristic + ChrF + back-translation scoring.
# Flags segments that need human review.
# ============================================================
import re
from .logger import get_logger

log = get_logger("quality")

# Thresholds
REVIEW_THRESHOLD  = 0.55   # below this → flag for human review
REJECT_THRESHOLD  = 0.30   # below this → mark as failed

# Script ranges per language (for transliteration detection)
_SCRIPT_RANGES = {
    "hin": "\u0900-\u097F", "mar": "\u0900-\u097F", "nep": "\u0900-\u097F",
    "mai": "\u0900-\u097F", "san": "\u0900-\u097F", "doi": "\u0900-\u097F",
    "kok": "\u0900-\u097F", "ben": "\u0980-\u09FF", "asm": "\u0980-\u09FF",
    "mni": "\u0980-\u09FF", "guj": "\u0A80-\u0AFF", "pan": "\u0A00-\u0A7F",
    "ory": "\u0B00-\u0B7F", "tam": "\u0B80-\u0BFF", "tel": "\u0C00-\u0C7F",
    "kan": "\u0C80-\u0CFF", "mal": "\u0D00-\u0D7F",
    "urd": "\u0600-\u06FF", "kas": "\u0600-\u06FF", "snd": "\u0600-\u06FF",
    "sat": "\u1C50-\u1C7F",
    "bod": "\u0900-\u097F",  # Bodo uses Devanagari (brx_Deva), not Tibetan script
}


def detect_transliteration(text: str, tgt_lang: str) -> bool:
    """
    Detect if text is transliterated (source language words written in Latin
    script instead of being translated into the target script).
    KB tender Section 3.2: agency shall not attempt mere transliteration.
    Returns True if transliteration is suspected.
    """
    if tgt_lang == "eng" or not text.strip():
        return False
    script_range = _SCRIPT_RANGES.get(tgt_lang)
    if not script_range:
        return False
    # Count native script chars vs Latin chars
    native_chars = len(re.findall(f"[{script_range}]", text))
    latin_chars  = len(re.findall(r"[a-zA-Z]", text))
    total_alpha  = native_chars + latin_chars
    if total_alpha < 5:
        return False
    # If Latin chars dominate in a non-Latin target language → transliteration
    latin_ratio = latin_chars / total_alpha
    return latin_ratio > 0.60


def chrf_score(reference: str, hypothesis: str, n: int = 6, beta: float = 2.0) -> float:
    """
    Character n-gram F-score (ChrF). Works well for Indic scripts.
    beta=2 weights recall higher than precision (standard for MT).
    Returns 0.0–1.0.
    """
    def _ngrams(s, n):
        return [s[i:i+n] for i in range(len(s) - n + 1)]

    ref = reference.replace(" ", "")
    hyp = hypothesis.replace(" ", "")
    if not ref or not hyp:
        return 0.0

    total_p, total_r = 0.0, 0.0
    for k in range(1, n + 1):
        ref_ng = _ngrams(ref, k)
        hyp_ng = _ngrams(hyp, k)
        if not ref_ng or not hyp_ng:
            continue
        ref_counts = {}
        for g in ref_ng:
            ref_counts[g] = ref_counts.get(g, 0) + 1
        matches = sum(min(hyp_ng.count(g), ref_counts.get(g, 0)) for g in set(hyp_ng))
        total_p += matches / len(hyp_ng)
        total_r += matches / len(ref_ng)

    p = total_p / n
    r = total_r / n
    if p + r == 0:
        return 0.0
    return round((1 + beta**2) * p * r / (beta**2 * p + r), 4)


_bt_translator = None  # module-level singleton — never reload
_bt_lock = __import__('threading').Lock()


def set_shared_translator(t) -> None:
    """Inject the pipeline's existing Translator so back-translation
    reuses it instead of loading a second model instance into GPU memory."""
    global _bt_translator
    with _bt_lock:
        _bt_translator = t


def back_translation_score(source: str, translation: str,
                           src_lang: str, tgt_lang: str,
                           translator=None) -> float:
    """
    Translate `translation` back to `src_lang`, then measure word overlap.
    Pass `translator` to reuse an existing instance and avoid double GPU load.
    Returns 0.0–1.0, or -1.0 on failure.
    """
    global _bt_translator
    try:
        t = translator
        if t is None:
            with _bt_lock:
                if _bt_translator is None:
                    from .translator import Translator
                    _bt_translator = Translator()
                t = _bt_translator
        back = t.translate_text(translation, tgt_lang, src_lang)
        src_words  = set(source.lower().split())
        back_words = set(back.lower().split())
        if not src_words:
            return -1.0
        return round(len(src_words & back_words) / len(src_words), 4)
    except Exception as e:
        log.warning(f"Back-translation failed ({tgt_lang}→{src_lang}): {e}")
        return -1.0


def score_segment(source: str, translation: str,
                  src_lang: str, tgt_lang: str) -> dict:
    """
    Heuristic + ChrF quality score (0.0–1.0) for a single segment.
    Returns: {score, chrf, flags, needs_review, failed}
    """
    flags = []
    score = 1.0

    if not translation or not translation.strip():
        return {"score": 0.0, "chrf": 0.0, "flags": ["empty_translation"],
                "needs_review": True, "failed": True}

    src_words = len(source.split())
    tgt_words = len(translation.split())

    # 1. Length ratio check
    if src_words > 0:
        ratio = tgt_words / src_words
        if ratio < 0.3 or ratio > 4.0:
            flags.append(f"length_ratio_{ratio:.1f}x")
            score -= 0.25

    # 2. Source language leakage
    script_range = _SCRIPT_RANGES.get(tgt_lang)
    if script_range and tgt_lang != "eng":
        indic_chars = len(re.findall(f"[{script_range}]", translation))
        total_alpha = len(re.findall(r"[a-zA-Z\u0080-\uFFFF]", translation))
        if total_alpha > 0:
            indic_ratio = indic_chars / total_alpha
            if indic_ratio < 0.5:
                flags.append("source_language_leakage")
                score -= 0.30

    # 3. Repetition loop
    words = translation.split()
    for i in range(len(words) - 3):
        if words[i] == words[i+1] == words[i+2] == words[i+3]:
            flags.append("repetition_loop")
            score -= 0.35
            break

    # 4. Untranslated — exact copy OR source script dominates when target script expected
    if tgt_lang != "eng" and translation.strip() == source.strip():
        flags.append("untranslated")
        score -= 0.40
    elif tgt_lang != "eng" and src_lang == "eng":
        # If target expects a non-Latin script but output is >80% Latin, it's untranslated
        latin_chars  = len(re.findall(r"[a-zA-Z]", translation))
        total_alpha  = len(re.findall(r"[\w]", translation))
        if total_alpha > 4 and latin_chars / total_alpha > 0.80:
            script_range = _SCRIPT_RANGES.get(tgt_lang)
            if script_range:  # only flag for non-Latin target scripts
                flags.append("untranslated_latin_output")
                score -= 0.35

    # 5. Too short
    if src_words >= 5 and tgt_words < 2:
        flags.append("too_short")
        score -= 0.30

    # 6. Transliteration check (KB tender Section 3.2)
    if detect_transliteration(translation, tgt_lang):
        flags.append("transliteration_detected")
        score -= 0.35

    # 7. Factual token preservation — numbers, dates, measurements must survive
    src_tokens = set(re.findall(r"[\d]+(?:[.,][\d]+)*", source))
    tgt_tokens = set(re.findall(r"[\d]+(?:[.,][\d]+)*", translation))
    missing_nums = src_tokens - tgt_tokens
    if missing_nums:
        flags.append(f"missing_numbers:{','.join(sorted(missing_nums)[:5])}")
        score -= 0.20

    # 8. ChrF — only meaningful when comparing translation to a reference.
    #    source ≠ reference (different scripts), so skip cross-script pairs.
    same_script = (src_lang == "eng" and tgt_lang == "eng") or (src_lang == tgt_lang)
    chrf = chrf_score(source, translation) if same_script else 0.0

    score = max(0.0, round(score, 3))
    needs_review = score < REVIEW_THRESHOLD
    failed       = score < REJECT_THRESHOLD

    if flags:
        log.warning(f"Quality flags [{tgt_lang}] score={score} chrf={chrf}: "
                    f"{flags} | {translation[:60]}")

    return {
        "score":        score,
        "chrf":         chrf,
        "flags":        flags,
        "needs_review": needs_review,
        "failed":       failed,
    }


def score_segment_full(source: str, translation: str,
                       src_lang: str, tgt_lang: str,
                       translator=None) -> dict:
    """
    Full scoring: heuristic + ChrF + back-translation.
    Pass translator to reuse existing instance (avoids double GPU load).
    """
    result = score_segment(source, translation, src_lang, tgt_lang)
    bt_overlap = back_translation_score(source, translation, src_lang, tgt_lang,
                                        translator=translator)
    result["back_translation_overlap"] = bt_overlap

    # If back-translation overlap is very low, flag for review
    if bt_overlap >= 0 and bt_overlap < 0.25:
        result["flags"].append(f"low_back_translation_{bt_overlap:.2f}")
        result["score"] = max(0.0, round(result["score"] - 0.15, 3))
        result["needs_review"] = result["score"] < REVIEW_THRESHOLD
        result["failed"]       = result["score"] < REJECT_THRESHOLD
        log.warning(f"Low back-translation overlap [{tgt_lang}]: {bt_overlap:.2f} | "
                    f"{translation[:60]}")
    return result


def score_batch(sources: list[str], translations: list[str],
                src_lang: str, tgt_lang: str,
                full: bool = False) -> list[dict]:
    fn = score_segment_full if full else score_segment
    return [
        fn(s, t, src_lang, tgt_lang)
        for s, t in zip(sources, translations)
    ]


def review_summary(scores: list[dict]) -> dict:
    total        = len(scores)
    if not total:
        return {"total": 0, "avg_score": 0, "avg_chrf": 0,
                "needs_review": 0, "failed": 0, "pass_rate": 0}
    needs_review = sum(1 for s in scores if s["needs_review"])
    failed       = sum(1 for s in scores if s["failed"])
    avg_score    = round(sum(s["score"] for s in scores) / total, 3)
    avg_chrf     = round(sum(s.get("chrf", 0) for s in scores) / total, 3)
    bt_scores    = [s["back_translation_overlap"] for s in scores
                    if s.get("back_translation_overlap", -1) >= 0]
    avg_bt       = round(sum(bt_scores) / len(bt_scores), 3) if bt_scores else None
    return {
        "total":        total,
        "avg_score":    avg_score,
        "avg_chrf":     avg_chrf,
        "avg_back_translation": avg_bt,
        "needs_review": needs_review,
        "failed":       failed,
        "pass_rate":    round((total - needs_review) / total, 3),
    }
