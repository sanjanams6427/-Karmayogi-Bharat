# ============================================================
# ASR Module — returns sentence-level segments with timestamps
# Engine: faster-whisper large-v3 (no huggingface_hub conflict)
# ============================================================

import re, subprocess, tempfile, os
import torch, numpy as np
torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
from pathlib import Path
from .lang_config import LANG_NAMES
from .lang_detect import tag_segments, fw_lang_to_internal

try:
    _gpu = int(os.environ.get("PIPELINE_GPU", "0"))
except ValueError:
    _gpu = 0
DEVICE     = f"cuda:{_gpu}" if torch.cuda.is_available() else "cpu"
ASR_DEVICE = DEVICE
MODELS_DIR = Path(__file__).parent.parent / "models"

# Nastaliq script normalization map for Urdu / Kashmiri / Sindhi
# Fixes common OCR/ASR output inconsistencies in Arabic-script languages
_NASTALIQ_NORM = {
    "\u0643": "\u06a9",   # Arabic kaf → Urdu kaf
    "\u064a": "\u06cc",   # Arabic ya → Urdu ya
    "\u0629": "\u062a",   # ta marbuta → ta
    "\u0649": "\u06cc",   # alef maqsura → ya
    "\u0624": "\u0648",   # waw with hamza above → waw
    "\u0626": "\u06cc",   # ya with hamza above → ya
}


def _normalize_nastaliq(text: str) -> str:
    """Normalize Arabic-script ASR output for Urdu/Kashmiri/Sindhi."""
    for src, tgt in _NASTALIQ_NORM.items():
        text = text.replace(src, tgt)
    return text

# faster-whisper large-v3 language codes for all 22 Indian languages
# large-v3 supports all of these natively — no MMS fallback needed
FW_LANG_CODES = {
    "eng": "en",  "hin": "hi",  "ben": "bn",  "guj": "gu",  "kan": "kn",
    "mal": "ml",  "mar": "mr",  "ory": "or",  "pan": "pa",  "tam": "ta",
    "tel": "te",  "urd": "ur",  "asm": "as",  "nep": "ne",  "mai": "mai",
    "snd": "sd",  "kas": "ks",  "kok": "kok", "mni": "mni", "san": "sa",
    "bod": "bo",  "sat": "sat", "doi": "doi",
}

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"


def _extract_wav(path: str) -> str:
    """Extract/convert any media file to 16kHz mono WAV."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".wav",):
        return path
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        [_FFMPEG, "-y", "-i", path, "-ac", "1", "-ar", "16000", "-vn", tmp.name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=True, timeout=300,
    )
    return tmp.name


class ASREngine:
    def __init__(self):
        self._fw_model = None

    def _load_fw(self):
        if self._fw_model is None:
            from faster_whisper import WhisperModel
            # Priority: local CT2 model.bin > downloaded HF cache snapshot > auto-download
            ct2_local    = MODELS_DIR / "indic_asr" / "model.bin"
            ct2_snapshot = MODELS_DIR / "indic_asr" / \
                "models--Systran--faster-whisper-large-v3" / "snapshots" / \
                "edaa852ec7e145841d8ffdb056a99866b5f0a478"
            if ct2_local.exists():
                src = str(MODELS_DIR / "indic_asr")
            elif ct2_snapshot.exists():
                src = str(ct2_snapshot)
            else:
                src = "large-v3"
            compute = "float16" if torch.cuda.is_available() else "int8"
            print(f"[ASR] Loading faster-whisper from {src} on {ASR_DEVICE}")
            cpu_count = os.cpu_count() or 4
            self._fw_model = WhisperModel(
                src,
                device="cuda" if torch.cuda.is_available() else "cpu",
                device_index=int(ASR_DEVICE.split(":")[1]) if ":" in ASR_DEVICE else 0,
                compute_type=compute,
                num_workers=1,  # >1 deadlocks on Windows (no fork)
                cpu_threads=min(cpu_count, 8),
                download_root=str(MODELS_DIR / "indic_asr"),
            )
        return self._fw_model

    def detect_language(self, audio_path: str) -> tuple[str, float]:
        """
        Detect the spoken language of an audio file using faster-whisper.
        Returns (internal_lang_code, probability) e.g. ("hin", 0.97).
        """
        wav = _extract_wav(str(audio_path))
        try:
            model = self._load_fw()
            segments, info = model.transcribe(wav, beam_size=1, language=None,
                                              vad_filter=True, max_new_tokens=1)
            _ = list(segments)
            fw_code  = info.language
            prob     = round(info.language_probability, 3)
            internal = fw_lang_to_internal(fw_code, fallback="eng")
            print(f"[ASR] Detected language: {fw_code} ({internal}) prob={prob}")
            return internal, prob
        finally:
            if wav != str(audio_path):
                try:
                    os.unlink(wav)
                except Exception:
                    pass

    def transcribe_segments(self, audio_path: str, lang: str) -> list[dict]:
        """
        Transcribe audio using faster-whisper large-v3 for all 22 languages.
        Pass lang="auto" to auto-detect the source language from audio.
        Single model, single load — no per-language adapter swaps.
        """
        wav = _extract_wav(str(audio_path))
        try:
            model = self._load_fw()

            fw_lang = None if (lang == "auto" or not lang) else FW_LANG_CODES.get(lang)

            # Hindi and Devanagari langs: beam_size=5 for better compound word accuracy.
            # Other langs: beam_size=2 for speed with minimal quality loss.
            _DEVA_LANGS = {"hin", "mar", "nep", "mai", "san", "doi", "kok", "bod"}
            beam = 5 if lang in _DEVA_LANGS else 2

            raw_segs, info = model.transcribe(
                wav,
                language=fw_lang,
                beam_size=beam,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
                word_timestamps=True,
                condition_on_previous_text=False,  # prevents Whisper hallucination loops
                temperature=[0.0, 0.2, 0.4],       # fallback temps break repetition
                no_speech_threshold=0.45,
                log_prob_threshold=-1.2,
                compression_ratio_threshold=2.4,
            )
            raw_segs = list(raw_segs)
            if fw_lang is None:
                lang = fw_lang_to_internal(info.language, fallback="eng")
                print(f"[ASR] Auto-detected language: {info.language} → {lang} "
                      f"(prob={info.language_probability:.2f})")
        finally:
            if wav != str(audio_path):
                try:
                    os.unlink(wav)
                except Exception:
                    pass

        if not raw_segs:
            return []
        # Tamil/Telugu/Malayalam/Kannada are morphologically rich — use longer merge windows
        if lang in ("tam", "tel", "mal", "kan"):
            merged = _merge_segments(raw_segs, min_words=5, min_dur=2.0, max_dur=8.0)
        elif lang in ("hin", "mar", "nep", "mai", "san", "doi", "kok", "bod"):
            # Devanagari langs: higher min_words — Hindi compound sentences are long;
            # 6 words is barely a clause. max_dur=20s to avoid mid-sentence cuts.
            # bod (Bodo/brx_Deva) also uses Devanagari — same merge strategy.
            merged = _merge_segments(raw_segs, min_words=10, min_dur=2.0, max_dur=20.0)
        else:
            merged = _merge_segments(raw_segs)
        segments = tag_segments(merged, lang)
        if lang in ("urd", "kas", "snd"):
            for seg in segments:
                seg["text"] = _normalize_nastaliq(seg["text"])
        for seg in segments:
            seg["text"] = _strip_hallucinations(seg["text"])
        segments = [s for s in segments if s["text"].strip()]
        return segments

    def transcribe_file(self, audio_path: str, lang: str) -> str:
        """Return full transcript as plain text (for quick tests)."""
        segs = self.transcribe_segments(audio_path, lang)
        return " ".join(s["text"] for s in segs)


# Pre-compiled hallucination prefix pattern — covers English and Devanagari artifacts
_HALLUC_PREFIX_RE = re.compile(
    r'^(?:'
    r'Wanner|Whener|Viengore|Venue|Guinevere|Gindis|Wener|Whener|'
    r'Venger|Vien|Whan|Wener|Winer|Wanna|Gonna|Ginda|Gindas|'
    r'Vanna|Venna|Vinna|Wenna|Winna'
    r')\s+',
    re.IGNORECASE
)

# Devanagari hallucination prefixes — strip known Whisper segment-boundary artifacts.
#
# Whisper large-v3 consistently emits छे/चे at the START of Devanagari segments
# when it mishears the boundary. These appear in two forms:
#   1. Standalone:  "छे वर्णन..."  — छे followed by space
#   2. Fused:       "छेदक", "छेकिन", "छेवआ", "छेना" — artifact glued to next word
#
# For fused form: strip only the 2-char prefix (छे/चे) and keep the remainder.
# The remainder is the real first word — e.g. "छेदक" → "दक" is WRONG;
# we need to detect that "दक" is not a real word start and instead the whole
# fused token is artifact+word. We do this by matching छे/चे at position 0
# followed immediately by a Devanagari consonant (no matra/space) — that
# pattern never occurs in real Hindi/Maithili/Bodo sentence-initial position.
#
# DO NOT strip से/हे/ये/वे/जे — common Hindi words (from/O/these/they/which).
_HALLUC_DEVA_RE = re.compile(
    r'^(?:'
    # Standalone: छे/चे followed by whitespace
    r'\u091b\u0947\s+'   # छे + space
    r'|\u091a\u0947\s+'  # चे + space
    # Fused: छे/चे immediately followed by a Devanagari consonant (U+0915–U+0939)
    # This is the "छेदक", "छेकिन", "छेवआ", "छेना", "छेदे" pattern.
    # Consume only the 2-char prefix; the consonant stays.
    r'|\u091b\u0947(?=[\u0915-\u0939])'  # छे fused with consonant
    r'|\u091a\u0947(?=[\u0915-\u0939])'  # चे fused with consonant
    r')'
)

# Known छे-fused hallucination corrections:
# Whisper replaces the first syllable of a word with छे, producing छे+remainder.
# Map remainder → corrected full word (most common cases in Hindi/Maithili/Bodo).
_HALLUC_DEVA_CORRECTIONS = {
    # छेकिन → लेकिन  (lekIn — Hindi "but/however")
    "\u0915\u093f\u0928": "\u0932\u0947\u0915\u093f\u0928",
    # छेदक → जलचक्र is wrong; दक alone is a fragment — drop it
    "\u0926\u0915": "",
    # छेदे → "दे हुए" — दे IS a real Hindi word (imperative देना) so sentinel would
    # restore it. But छेदे is always an artifact — drop दे unconditionally here.
    # Real sentence-initial "दे" (e.g. "दे दो", "दे रहा") never follows छे in real text.
    "\u0926\u0947": "",  # unconditional drop — छेदे is always artifact
    # छेवआ → वआ is a fragment — drop it
    "\u0935\u0906": "",
    # छेना → ना is a negation suffix — drop it
    "\u0928\u093e": "",
    # छेदककेँ → दककेँ is a fragment — drop it
    "\u0926\u0915\u0915\u0947\u0901": "",
}


def _correct_deva_halluc(text: str) -> str:
    """
    After stripping छे/चे prefix, check if the first word is a known fragment
    and either correct it to the full word or drop it.
    """
    if not text:
        return text
    parts = text.split(None, 1)
    first = parts[0]
    rest  = parts[1] if len(parts) > 1 else ""
    correction = _HALLUC_DEVA_CORRECTIONS.get(first)
    if correction is None:
        return text  # key not in map — no correction needed
    if correction:
        # Full word replacement (e.g. किन → लेकिन)
        return (correction + " " + rest).strip()
    # Empty string — unconditional drop
    return rest.strip()


# Indic punctuation boundary artifacts: leading । ॥ or ASCII ) , . followed by space
_HALLUC_BOUNDARY_RE = re.compile(
    r'^[\)\]\},;.\u0964\u0965]+\s+'
)


def _strip_hallucinations(text: str) -> str:
    """
    Remove known Whisper hallucination patterns at segment boundaries.
    Covers English, Devanagari, and Tamil/Telugu boundary artifacts.
    Apply iteratively — stripping one artifact can expose another.
    """
    text = _HALLUC_PREFIX_RE.sub('', text).strip()

    # Strip छे/चे prefix iteratively — one pass may expose another artifact
    for _ in range(3):
        new = _HALLUC_DEVA_RE.sub('', text).strip()
        if new == text:
            break
        text = _correct_deva_halluc(new)

    text = _HALLUC_BOUNDARY_RE.sub('', text).strip()

    # Strip leading standalone Devanagari combining marks (anusvara ँ/ं, visarga ः,
    # chandrabindu, nukta) that Whisper emits as segment-boundary artifacts.
    # These characters (U+0900–U+0903, U+093C) can NEVER start a real word.
    text = re.sub(r'^[\u0900-\u0903\u093C]+\s+', '', text).strip()

    # Strip leading incomplete syllable fragments for Tamil (U+0B80–U+0BFF + virama U+0BCD)
    text = re.sub(r'^[\u0B80-\u0BFF]{1,3}\u0BCD\s+', '', text)
    # Strip leading incomplete syllable fragments for Telugu (U+0C00–U+0C7F + virama U+0C4D)
    text = re.sub(r'^[\u0C00-\u0C7F]{1,3}\u0C4D\s+', '', text)
    if text:
        text = text[0].upper() + text[1:]
    return text


def _merge_segments(raw_segs, min_words: int = 6, min_dur: float = 1.5,
                    max_dur: float = 12.0) -> list[dict]:
    """
    Merge faster-whisper segments into natural sentence-length chunks.
    Rules:
      - Keep merging until >= min_words words AND >= min_dur seconds
      - Never exceed max_dur seconds
      - Always split on sentence-ending punctuation (. ! ? । ॥)
    """
    merged, buf_text, buf_start, buf_end = [], [], None, None

    def flush():
        if buf_text:
            text = " ".join(buf_text).strip()
            if text:
                merged.append({
                    "id": len(merged),
                    "start": round(buf_start, 3),
                    "end": round(buf_end, 3),
                    "text": text,
                })

    for seg in raw_segs:
        text = seg.text.strip()
        if not text:
            continue
        start, end = seg.start, seg.end

        if buf_start is None:
            buf_start = start

        buf_text.append(text)
        buf_end = end

        dur = buf_end - buf_start
        words = sum(len(t.split()) for t in buf_text)
        ends_sentence = text[-1] in ".!?\u3002\u0964\u0965"

        # Only hard-split on duration if the segment ends on a sentence boundary.
        # Never split mid-sentence — a dangling half-sentence translates badly
        # and sounds broken in TTS.
        force_split = dur >= max_dur and ends_sentence
        # If we've exceeded max_dur and there's NO sentence boundary, still split
        # to prevent the buffer growing unbounded — but only at a word boundary
        # (the current segment end is always a word boundary in Whisper output).
        if dur >= max_dur * 1.5 and not ends_sentence:
            force_split = True
        # natural_split: flush on sentence boundary when we have enough content.
        # last_seg_words >= 2 guard prevents splitting on a lone danda (।) with
        # only 1 word — but 2 words is enough for a complete clause.
        last_seg_words = len(buf_text[-1].split()) if buf_text else 0
        natural_split = ends_sentence and words >= min_words and dur >= min_dur and last_seg_words >= 2
        if natural_split or force_split:
            flush()
            buf_text, buf_start, buf_end = [], None, None

    flush()
    return merged
