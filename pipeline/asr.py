# ============================================================
# ASR Module — returns sentence-level segments with timestamps
# Engine: faster-whisper large-v3 (no huggingface_hub conflict)
# ============================================================

import subprocess, tempfile, os
import torch, numpy as np
from pathlib import Path
from .lang_config import LANG_NAMES
from .lang_detect import tag_segments, fw_lang_to_internal

import os
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
    "ك": "ک",   # Arabic kaf → Urdu kaf
    "ي": "ی",   # Arabic ya → Urdu ya
    "ة": "ت",   # ta marbuta → ta
    "\u0649": "ی",  # alef maqsura → ya
    "\u0624": "و",  # waw with hamza above → waw
    "\u0626": "ی",  # ya with hamza above → ya
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
            import os as _os
            cpu_count = _os.cpu_count() or 4
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
            # consume generator to get info populated
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

            # Auto-detect language if not specified — single pass, no redundant probe
            fw_lang = None if (lang == "auto" or not lang) else FW_LANG_CODES.get(lang)
            raw_segs, info = model.transcribe(
                wav,
                language=fw_lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                word_timestamps=True,
                condition_on_previous_text=False,  # prevents Whisper hallucination loops
                temperature=[0.0, 0.2, 0.4],       # fallback temps break repetition
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4,
            )
            raw_segs = list(raw_segs)
            # Resolve auto-detected language after consuming generator
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
        merged = _merge_segments(raw_segs)
        segments = tag_segments(merged, lang)
        # Post-process Nastaliq script languages
        if lang in ("urd", "kas", "snd"):
            for seg in segments:
                seg["text"] = _normalize_nastaliq(seg["text"])
        # Strip ASR hallucination artifacts (garbage words at segment boundaries)
        for seg in segments:
            seg["text"] = _strip_hallucinations(seg["text"])
        segments = [s for s in segments if s["text"].strip()]
        return segments

    def transcribe_file(self, audio_path: str, lang: str) -> str:
        """Return full transcript as plain text (for quick tests)."""
        segs = self.transcribe_segments(audio_path, lang)
        return " ".join(s["text"] for s in segs)


def _strip_hallucinations(text: str) -> str:
    """
    Remove known Whisper hallucination patterns that appear at segment boundaries.
    These are real English words that Whisper hallucinates when audio is unclear
    at the start/end of a segment — they corrupt translation output.
    """
    import re
    # Sentence-initial hallucination words Whisper commonly produces
    _HALLUC_PREFIX = re.compile(
        r'^(?:Wanner|Whener|Viengore|Venue|Guinevere|Gindis|Wener|Whener|'
        r'Venger|Vien|Whan|Whan|Wener|Winer|Wanna|Gonna|Ginda|Gindas|'
        r'Wanna|Gonna|Vanna|Venna|Vinna|Vanna|Wenna|Winna)\s+',
        re.IGNORECASE
    )
    text = _HALLUC_PREFIX.sub('', text).strip()
    # Capitalise first letter after stripping
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
      - Always split on sentence-ending punctuation (. ! ?)
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
        ends_sentence = text[-1] in ".!?。"

        if (ends_sentence and words >= min_words and dur >= min_dur) or dur >= max_dur:
            flush()
            buf_text, buf_start, buf_end = [], None, None

    flush()
    return merged
