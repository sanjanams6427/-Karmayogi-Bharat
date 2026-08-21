# ============================================================
# TTS Engine — Offline, Zero-cost
# Primary  : Indic Parler-TTS — 22 langs, 44kHz, GPU batch
# Fallback1: MMS-TTS — all 22 langs
# ============================================================

import os, subprocess, json
import os as _os_numba
_os_numba.environ.setdefault("NUMBA_DISABLE_JIT", "1")  # prevent NumPy version crash in Numba
import torch
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
import numpy as np
import soundfile as sf
from pathlib import Path
from .lang_config import LANG_NAMES
from .logger import get_logger

log = get_logger(__name__)

# Warn once at import time if resampy is missing — pitch_shift will use soxr fallback
try:
    import resampy as _resampy_check  # noqa: F401
except ImportError:
    log.warning("resampy not installed — librosa pitch_shift will use soxr_hq backend")

import os as _os
_gpu = _os.environ.get("PIPELINE_GPU", "0")
DEVICE = (
    _os.environ.get("TTS_DEVICE")
    or (f"cuda:{_gpu}" if torch.cuda.is_available() else "cpu")
)

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"

MODELS_DIR       = Path(__file__).parent.parent / "models"
CKPT_DIR         = Path(__file__).parent.parent / "checkpoints"
# Fine-tuned checkpoint takes priority over base models
_PARLER_FT_DIR   = CKPT_DIR / "parler_tts" / "best"
PARLER_LARGE_DIR = MODELS_DIR / "indic_parler_tts_large"
PARLER_MINI_DIR  = MODELS_DIR / "indic_parler_tts"
PARLER_DIR       = (_PARLER_FT_DIR   if _PARLER_FT_DIR.exists()   else
                    PARLER_LARGE_DIR if PARLER_LARGE_DIR.exists() else PARLER_MINI_DIR)
FLAN_T5_DIR      = MODELS_DIR / "flan_t5_large"
MMS_DIR          = MODELS_DIR / "mms"
MMS_STANDALONE   = MODELS_DIR / "mms_standalone"  # standalone per-lang VITS models
# All languages use standalone VITS models downloaded to mms_standalone/
# The models/mms directory contains a wav2vec2 ASR model — NOT a TTS model.
# MMS-TTS requires per-language VITS models from facebook/mms-tts-<lang>.
_MMS_STANDALONE_LANGS = {
    # 11 mandatory languages
    "tam": "tam",  "tel": "tel",  "hin": "hin",  "kan": "kan",
    "mal": "mal",  "ben": "ben",  "mar": "mar",  "guj": "guj",
    "pan": "pan",  "ory": "ory",  "asm": "asm",
    # 11 additional languages
    "doi": "dgo",  "bod": "bod",  "mni": "mni",
    "kok": "kok",  "kas": "kas",
    "urd": "urd",  "mai": "mai",
    # sat/snd: no standalone model downloaded — fall through to Parler
}

SR = 44100  # target sample rate


def _is_ai4bharat_model(model_dir: Path = None) -> bool:
    """Detect if the Parler checkpoint has its own text encoder tokenizer embedded."""
    d = model_dir or PARLER_DIR
    cfg = d / "config.json"
    if not cfg.exists():
        return False
    try:
        c = json.loads(cfg.read_text(encoding="utf-8"))
        name = c.get("_name_or_path", "")
        has_own_tokenizer = (d / "tokenizer.json").exists()
        return "ai4bharat" in name or "indic-parler" in name.lower() or has_own_tokenizer
    except Exception:
        return False


# Languages where Parler-TTS is PRIMARY.
# Hindi and all Devanagari-family langs use Parler-TTS Indic Large as primary —
# it produces the most natural Indian human-sounding dubbing for these scripts.
# MMS-VITS is the fallback when Parler fails.
#
# Dravidian langs (tam/tel/kan/mal) still use MMS-VITS primary — Parler produces
# near-silence or very low amplitude for those scripts without a dedicated fine-tune.
_PARLER_SKIP_LANGS: set = {
    # Dravidian — MMS-VITS primary (Parler amplitude too low for these scripts)
    "tam", "tel", "kan", "mal",
    # Bengali-script family — MMS-VITS primary
    "ben", "asm", "mni",
    # Gurmukhi / Odia / Gujarati — MMS-VITS primary
    "pan", "ory", "guj",
    # Arabic-script family — MMS-VITS primary
    "urd", "kas",
    # Low-resource / special scripts — MMS-VITS or silence
    "sat", "snd",
    # Langs with no Parler training signal — MMS-VITS primary
    "mni", "kok", "bod", "doi",
    # NOTE: "hin", "mar", "nep", "mai", "san" are NOT in this set —
    # Parler-TTS Indic Large is trained on these and produces natural human dubbing.
}

# Tamil-specific: inter-segment silence gap (ms) added between VITS chunks
# to give natural breathing room between sentences.
_TAM_INTER_SEG_SILENCE_MS = 60  # 60ms — natural pause, not robotic gap


# Per-language descriptions for ai4bharat Indic Parler-TTS.
# The model was trained with Indian-language-specific prompts — using the correct
# language name and "Indian" cues is essential for natural-sounding output.
# "slightly high-pitched" is kept for Dravidian langs (tam/tel/kan/mal) because
# deep-voice prompts produce near-silence on those scripts.
# All descriptions are identical in structure so the speaker embedding stays
# consistent across segments — only the language name changes.
# Single unified voice description used for ALL languages and ALL segments.
# One consistent young Indian male voice — clear, natural, fluent, no voice switching.
# The language name is injected per-language so the model activates the correct phoneme set,
# but the speaker identity (young, clear, natural, Indian) is identical across every segment.
# Hindi-specific Parler description — tuned for natural Indian human dubbing.
# Key findings from testing ai4bharat/indic-parler-tts-pretrained-v1:
#   - "Jon" speaker name activates the clearest Hindi male voice in the model
#   - "slightly expressive" prevents the flat robotic monotone
#   - "reverberation" must be absent — reverb causes hollow robotic echo
#   - "very close-sounding" microphone cue gives warmth and presence
#   - Explicit "Hindi" language name activates correct Devanagari phoneme set
_PARLER_DESCS: dict[str, str] = {
    "hin": (
        "Arjun speaks fluent Hindi with a natural Indian male voice, clear and expressive "
        "Devanagari pronunciation, warm resonant tone, moderate pace, slightly expressive "
        "intonation with natural sentence rhythm. "
        "The recording is very close-sounding with no reverberation, "
        "captured in a very high quality studio with no background noise."
    ),
    "mar": (
        "Arjun speaks fluent Marathi with a natural Indian male voice, clear Devanagari "
        "pronunciation, warm tone, moderate pace, and natural Indian intonation. "
        "The recording is very close-sounding with no reverberation, "
        "captured in a very high quality studio with no background noise."
    ),
    "nep": (
        "Arjun speaks fluent Nepali with a natural Indian male voice, clear Devanagari "
        "pronunciation, warm tone, moderate pace, and natural Indian intonation. "
        "The recording is very close-sounding with no reverberation, "
        "captured in a very high quality studio with no background noise."
    ),
    "mai": (
        "Arjun speaks fluent Maithili with a natural Indian male voice, clear Devanagari "
        "pronunciation, warm tone, moderate pace, and natural Indian intonation. "
        "The recording is very close-sounding with no reverberation, "
        "captured in a very high quality studio with no background noise."
    ),
    "san": (
        "Arjun speaks fluent Sanskrit with a natural Indian male voice, clear Devanagari "
        "pronunciation, warm tone, moderate pace, and natural Indian intonation. "
        "The recording is very close-sounding with no reverberation, "
        "captured in a very high quality studio with no background noise."
    ),
}
# Fallback for any language not in the dict above
_PARLER_DESC_DEFAULT = (
    "Arjun speaks with a natural Indian male voice, clear pronunciation, "
    "warm tone, moderate pace, and natural Indian intonation. "
    "The recording is very close-sounding with no reverberation, "
    "captured in a very high quality studio with no background noise."
)

# MMS-TTS adapter codes for all 22 languages (shared-base adapter model)
# Langs with standalone VITS (doi/san/kas/snd/kok/mni) are excluded —
# they use _MMS_STANDALONE_LANGS and only fall through to adapter if standalone missing.
MMS_LANG_CODES = {
    "asm": "asm", "ben": "ben", "guj": "guj", "hin": "hin",
    "kan": "kan", "mal": "mal", "mar": "mar", "ory": "ory",
    "pan": "pan", "tam": "tam", "tel": "tel",
    "urd": "urd-script_arabic", "nep": "npi", "bod": "bod",
    "mai": "mai", "sat": "sat", "snd": "snd",
    "san": "hin",               # no san adapter - hin shares Devanagari
    "kas": "urd-script_arabic",  # no kas adapter - urd Nastaliq is closest
    "kok": "mar",                # no kok adapter - mar shares Devanagari
    "mni": "ben",                # no mni adapter - ben shares Bengali script
}


def _trim_leading_silence(audio: np.ndarray, sr: int, threshold: float = 0.015) -> np.ndarray:
    """Trim silent/noisy preamble from Parler output.
    Parler-TTS often generates 100-300ms of near-silent noise before actual speech.
    Threshold 0.015 — catches low-level buzz without cutting the soft onset of
    Hindi breathy consonants (ह, भ, घ) which start at ~0.02 amplitude.
    Scans in 10ms frames, returns audio starting from first frame above threshold.
    """
    frame = int(0.010 * sr)  # 10ms frames
    for i in range(0, len(audio) - frame, frame):
        if np.max(np.abs(audio[i:i + frame])) >= threshold:
            lead = max(0, i - int(0.005 * sr))
            return audio[lead:]
    return audio


def _post_process(audio: np.ndarray, sr: int = SR, is_mms: bool = False,
                  female_shift: bool = False, lang: str = "") -> np.ndarray:
    from scipy.signal import butter, sosfilt
    # High-pass at 80Hz — removes DC/rumble without cutting low vowels.
    sos = butter(4, 80.0 / (sr / 2), btype="high", output="sos")
    audio = sosfilt(sos, audio).astype(np.float32)
    # Parler Hindi/Devanagari: gentle presence boost at 2-4kHz removes the
    # "muffled robotic" quality. Parler output is slightly mid-heavy;
    # a mild high-shelf at 3kHz (+2dB equivalent via gentle LP removal) opens it up.
    # Implemented as a mild low-pass shelf: attenuate above 8kHz slightly
    # to remove Parler's high-frequency hiss without muffling consonants.
    _DEVA_PARLER_LANGS = {"hin", "mar", "nep", "mai", "san"}
    if not is_mms and lang in _DEVA_PARLER_LANGS:
        sos_hiss = butter(2, 8000.0 / (sr / 2), btype="low", output="sos")
        audio_hf  = sosfilt(sos_hiss, audio).astype(np.float32)
        # Blend: 70% filtered + 30% original — keeps consonant crispness and naturalness
        audio = (0.70 * audio_hf + 0.30 * audio).astype(np.float32)
    if is_mms:
        # Low-pass at 9500Hz for all MMS VITS langs.
        # Indic VITS models have significant consonant energy at 8-10kHz
        # (retroflex stops, nasals, fricatives). 7500Hz was muffling these.
        sos_lp = butter(3, 9500.0 / (sr / 2), btype="low", output="sos")
        audio  = sosfilt(sos_lp, audio).astype(np.float32)
        # Trim trailing near-silence — threshold 0.001 for all MMS langs.
        # 0.003 was cutting into final consonants of retroflex stops in
        # Kannada/Malayalam/Bengali/Marathi whose amplitude decays to ~0.001
        # before burst release completes.
        trim_thresh = 0.001
        nz = np.where(np.abs(audio) > trim_thresh)[0]
        if len(nz) > 0:
            # 80ms decay tail for all langs — long vowels and retroflex stops
            # need full decay; 50ms was cutting the final syllable.
            keep = min(nz[-1] + int(80 * 0.001 * sr), len(audio))
            audio = audio[:keep]
    if female_shift:
        try:
            import librosa
            audio = librosa.effects.pitch_shift(audio.astype(np.float32), sr=sr, n_steps=5, res_type='soxr_hq')
        except Exception as _ps_err:
            log.warning(f"pitch_shift failed ({_ps_err}) — keeping original pitch")
    # Normalize to -3 dBFS — broadcast/streaming standard.
    # iOS AVFoundation AAC encoder clips peaks above -1 dBFS;
    # -3 dBFS (0.708) gives 3dB headroom so no clipping on device.
    peak = np.max(np.abs(audio))
    if peak > 0.01:
        audio = audio * (0.708 / peak)
    return audio


class TTSEngine:
    _PARLER_MIN_DUR = 0.4  # seconds — below this is likely a noise burst, not speech

    def __init__(self):
        self._parler_model     = None
        self._parler_tokenizer = None
        self._parler_desc_tok  = None
        self._parler_label     = None
        self._mms_model        = None
        self._mms_processor    = None
        self._mms_current_lang = None
        self._ai4bharat        = {}
        self._standalone_vits: dict = {}
        self._mms_load_failed  = False
        self._mms_adapter_failed: set = set()  # per-lang adapter failures
        self._vits_rng_pinned: bool = False    # True while a segment batch is running

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _is_ai4bharat(self, model_dir: Path = None) -> bool:
        d = model_dir or PARLER_DIR
        key = str(d)
        if key not in (self._ai4bharat or {}):
            if self._ai4bharat is None:
                self._ai4bharat = {}
            self._ai4bharat[key] = _is_ai4bharat_model(d)
        return self._ai4bharat[key]

    def _build_description(self, lang: str, model_dir: Path = None) -> str:
        # Language-specific description — gives the model the correct Indian-language
        # speaker cue while keeping structure identical across all segments.
        return _PARLER_DESCS.get(lang, _PARLER_DESC_DEFAULT)

    # ----------------------------------------------------------
    # Standalone VITS loader (facebook/mms-tts-<lang> separate repos)
    # ----------------------------------------------------------
    def _load_standalone_vits(self, lang: str) -> bool:
        if lang in self._standalone_vits:
            return True
        subfolder = _MMS_STANDALONE_LANGS.get(lang)
        if not subfolder:
            return False
        model_path = MMS_STANDALONE / subfolder
        if not model_path.exists():
            log.warning(f"Standalone VITS model not found for {lang} at {model_path}")
            return False
        try:
            # Suppress Numba/NumPy version warnings — not needed for VITS inference
            import warnings
            import os as _os2
            _os2.environ.setdefault("NUMBA_DISABLE_JIT", "1")
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*[Nn]umba.*")
                warnings.filterwarnings("ignore", message=".*[Nn]um[Pp]y.*")
                from transformers import VitsModel, AutoTokenizer
                log.info(f"Loading standalone VITS [{lang}] from {model_path}")
                tokenizer = AutoTokenizer.from_pretrained(str(model_path))
                # Load on CPU first to avoid CUDA illegal memory access on some
                # VITS checkpoints — move to DEVICE only after successful load.
                model = VitsModel.from_pretrained(
                    str(model_path), torch_dtype=torch.float32
                ).eval()
                try:
                    model = model.to(DEVICE)
                except RuntimeError as _cuda_err:
                    log.warning(f"Standalone VITS [{lang}] CUDA move failed ({_cuda_err}) — using CPU")
                    model = model.to("cpu")
            # Pin noise_scale to 0.0 — eliminates stochastic voice variation between
            # segments. Default 0.667 causes different timbre on every call.
            # noise_scale_duration=0.0 locks duration predictor too (consistent pacing).
            # noise_scale: per-lang tuning for natural prosody
            # Hindi/Devanagari: 0.45 — enough variance for natural intonation
            # Dravidian/Bengali: 0.3 — tighter control for complex akshara clusters
            _DEVA_LANGS_NS = {"hin", "mar", "mai", "nep", "san", "doi", "kok"}
            _ns = 0.45 if lang in _DEVA_LANGS_NS else 0.3
            model.config.noise_scale          = _ns
            # 0.6 locks duration predictor tightly — consistent pacing for dubbing
            # where TTS audio must fit original timestamp slots.
            # 0.8 caused pacing drift between chunks, making fit-to-slot harder.
            model.config.noise_scale_duration  = 0.6
            for _attr in ("inference_noise_scale",):
                if hasattr(model.config, _attr):
                    setattr(model.config, _attr, _ns)
            if hasattr(model.config, "inference_noise_scale_dp"):
                setattr(model.config, "inference_noise_scale_dp", 0.6)
            self._standalone_vits[lang] = {"model": model, "tokenizer": tokenizer,
                                           "seed": 42}
            log.info(f"Standalone VITS [{lang}] loaded (noise_scale=0.3 natural prosody)")
            # Warm up once with a short text to advance past any init RNG state,
            # then capture the RNG state — this becomes the pinned state for all inference.
            # Use a real word in the target script — VITS phonemiser produces 0 tokens
            # for punctuation-only input (".") which causes a negative-output-size error.
            _WARMUP_TEXT = {
                "tam": "வணக்கம்", "tel": "నమస్కారం", "hin": "नमस्ते",
                "kan": "ನಮಸ್ಕಾರ", "mal": "നമസ്കാരം", "ben": "নমস্কার",
                "mar": "नमस्कार", "guj": "નમસ્તે",   "pan": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ",
                "ory": "ନମସ୍କାର", "asm": "নমস্কাৰ",  "urd": "سلام",
                "nep": "नमस्ते",  "mai": "प्रणाम",   "doi": "नमस्ते",
                "kok": "नमस्कार", "mni": "ꯍꯥꯌ",      "san": "नमस्ते",
                "bod": "བཀྲ་ཤིས", "sat": "ᱡᱚᱦᱟᱨ",   "kas": "سلام",
                "snd": "سلام",
            }
            _warm_text = _WARMUP_TEXT.get(lang, "नमस्ते")  # Devanagari fallback — never Latin
            try:
                _warm = tokenizer(_warm_text, return_tensors="pt")
                _warm = {k: v.long().to(DEVICE) if k == "input_ids" else v.to(DEVICE)
                         for k, v in _warm.items()}
                torch.manual_seed(42)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(42)
                with torch.no_grad():
                    model(**_warm)
                # State after warmup is the pinned baseline for all real inference
                _pinned_cpu  = torch.get_rng_state()
                _pinned_cuda = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
                self._standalone_vits[lang]["pinned_cpu_rng"]  = _pinned_cpu
                self._standalone_vits[lang]["pinned_cuda_rng"] = _pinned_cuda
                log.info(f"Standalone VITS [{lang}] RNG state pinned after warmup")
            except Exception as _we:
                log.warning(f"Standalone VITS [{lang}] warmup failed: {_we} — RNG not pinned")
            return True
        except Exception as e:
            log.error(f"Standalone VITS load failed [{lang}]: {e}")
            return False

    # VITS token limit — beyond this the model loops/glitches/cuts off.
    # 500 tokens: Tamil akshars are multi-codepoint; 400 was splitting mid-clause.
    _VITS_MAX_TOKENS = 500

    def _vits_chunks(self, text: str, tokenizer, lang: str = "") -> list[str]:
        """Split text into chunks that fit within VITS token limit.
        Preference order: no split → sentence boundary (. ! ? । ॥) → word boundary.
        Never splits on commas or clause markers — those cause audible voice
        breaks mid-clause which sound like a different speaker.
        All Indic langs use the same rule: split only at hard sentence endings.
        """
        import re
        ids = tokenizer(text, return_tensors="pt")["input_ids"]
        if ids.shape[-1] <= self._VITS_MAX_TOKENS:
            return [text]
        # Universal Indic sentence boundary — works for Tamil, Devanagari, Dravidian.
        # Splitting at clause markers (Tamil virama, ம் etc.) causes mid-sentence
        # voice breaks that sound like a different speaker. Only split at hard
        # sentence endings so the voice stays natural and continuous.
        parts = re.split(r'(?<=[.!?\u0964\u0965])\s+', text.strip())
        if len(parts) <= 1:
            # No sentence boundary — split on word boundary only (never mid-akshara).
            # Build parts by greedily adding words until token limit reached.
            words = text.split()
            parts, current_words = [], []
            for word in words:
                candidate = " ".join(current_words + [word])
                if tokenizer(candidate, return_tensors="pt")["input_ids"].shape[-1] <= self._VITS_MAX_TOKENS:
                    current_words.append(word)
                else:
                    if current_words:
                        parts.append(" ".join(current_words))
                    current_words = [word]
            if current_words:
                parts.append(" ".join(current_words))
            if not parts:
                parts = [text]
        chunks, current = [], ""
        for part in parts:
            candidate = (current + " " + part).strip() if current else part
            if tokenizer(candidate, return_tensors="pt")["input_ids"].shape[-1] <= self._VITS_MAX_TOKENS:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if tokenizer(part, return_tensors="pt")["input_ids"].shape[-1] > self._VITS_MAX_TOKENS:
                    # Part still too long — split greedily by word
                    sub_words, sub_cur = [], []
                    for w in part.split():
                        cand = " ".join(sub_cur + [w])
                        if tokenizer(cand, return_tensors="pt")["input_ids"].shape[-1] <= self._VITS_MAX_TOKENS:
                            sub_cur.append(w)
                        else:
                            if sub_cur:
                                chunks.append(" ".join(sub_cur))
                            sub_cur = [w]
                    current = " ".join(sub_cur) if sub_cur else ""
                else:
                    current = part
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()] or [text]

    def _synthesize_standalone_vits(self, text: str, lang: str, output_path: str) -> bool:
        if not self._load_standalone_vits(lang):
            return False
        try:
            engine    = self._standalone_vits[lang]
            tokenizer = engine["tokenizer"]
            model     = engine["model"]
            native    = model.config.sampling_rate
            chunks    = self._vits_chunks(text, tokenizer, lang=lang)
            wavs      = []
            # RNG advances naturally from the state pinned in synthesize_segments.
            # For standalone calls (not via synthesize_segments) seed with fixed
            # value so voice is still deterministic and consistent.
            if not getattr(self, "_vits_rng_pinned", False):
                torch.manual_seed(engine.get("seed", 42))
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(engine.get("seed", 42))
            for ci, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                inputs = tokenizer(chunk, return_tensors="pt")
                inputs = {k: v.long().to(DEVICE) if k == "input_ids" else v.to(DEVICE)
                          for k, v in inputs.items()}
                with torch.no_grad():
                    out = model(**inputs)
                if out.waveform is None:
                    log.warning(f"Standalone VITS [{lang}] waveform=None for chunk {ci} — skipping")
                    continue
                w = out.waveform[0].detach().cpu().float().numpy().squeeze()
                # No per-chunk nz trim — _post_process handles trailing silence.
                # Trimming here cuts the last consonant of retroflex stops whose
                # amplitude decays below any threshold before burst release completes.
                if len(w) == 0:
                    continue
                # 2ms fade-in only — kills DC click at chunk start, no fade-out
                fade_in = min(int(0.002 * native), len(w) // 8)
                if fade_in > 0:
                    w[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
                wavs.append(w)
                # Add silence ONLY at hard sentence boundaries (. ! ? । ॥).
                # Word-boundary splits get NO silence — they are mid-sentence
                # and a pause there sounds like a different speaker / voice break.
                if ci < len(chunks) - 1:
                    prev_chunk = chunks[ci]
                    at_sentence_boundary = prev_chunk.rstrip()[-1:] in '.!?\u0964\u0965'
                    if at_sentence_boundary:
                        silence_samp = int(80 * 0.001 * native)  # 80ms natural breath
                        wavs.append(np.zeros(silence_samp, dtype=np.float32))
            if not wavs:
                return False
            combined = np.concatenate(wavs)
            if native != SR:
                import librosa
                combined = librosa.resample(combined, orig_sr=native, target_sr=SR)
            combined = _post_process(combined, SR, is_mms=True, lang=lang)
            if len(combined) / SR < 0.1:
                log.warning(f"Standalone VITS [{lang}] output too short ({len(combined)/SR:.3f}s) — skipping")
                return False
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, combined, SR, subtype="PCM_16")
            return True
        except Exception as e:
            log.error(f"Standalone VITS [{lang}] failed: {e}")
            return False

    # ----------------------------------------------------------
    # Parler-TTS loader
    # ----------------------------------------------------------
    def _load_parler(self) -> bool:
        if self._parler_model is not None:
            return True
        # Try large first, fall back to mini
        candidates = []
        if _PARLER_FT_DIR.exists():
            candidates.append((_PARLER_FT_DIR,   "fine-tuned"))
        if PARLER_LARGE_DIR.exists():
            candidates.append((PARLER_LARGE_DIR, "large"))
        if PARLER_MINI_DIR.exists():
            candidates.append((PARLER_MINI_DIR,  "mini"))
        if not candidates:
            log.warning("No Parler-TTS model found (checked large + mini dirs)")
            return False
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
        import transformers
        transformers.logging.set_verbosity_error()
        for model_dir, label in candidates:
            try:
                log.info(f"Loading Parler-TTS [{label}] from {model_dir.name}")
                self._parler_model = ParlerTTSForConditionalGeneration.from_pretrained(
                    str(model_dir),
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    attn_implementation="eager",
                ).to(DEVICE).eval()

                self._parler_tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
                # Description tokenizer MUST be flan-t5-large (text encoder), not the model's LLaMA tokenizer
                text_enc_name = self._parler_model.config.text_encoder._name_or_path
                if FLAN_T5_DIR.exists():
                    desc_tok_src = str(FLAN_T5_DIR)
                else:
                    desc_tok_src = text_enc_name  # download from HF if not cached
                self._parler_desc_tok = AutoTokenizer.from_pretrained(desc_tok_src)
                self._parler_label = label  # track which one is loaded
                transformers.logging.set_verbosity_warning()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                log.info(f"Parler-TTS [{label}] loaded successfully")
                return True
            except Exception as e:
                log.warning(f"Parler-TTS [{label}] load failed: {e} — trying next")
                self._parler_model = None
        log.error("All Parler-TTS candidates failed to load")
        return False

    # ----------------------------------------------------------
    # Parler-TTS synthesis (single)
    # ----------------------------------------------------------
    # Single fixed seed 42 for ALL languages — same seed every segment = identical voice throughout.
    # Do NOT change this — it is the voice identity anchor for the entire video.
    _LANG_SEEDS = {lang: 42 for lang in [
        "hin", "ben", "tam", "tel", "kan", "mal", "mar", "guj", "pan", "ory",
        "asm", "urd", "nep", "bod", "doi", "kok", "mni", "mai", "san", "sat",
        "snd", "kas", "eng",
    ]}

    def _parler_encode_description(self, desc_ids):
        """Run the text encoder ONCE and cache the result.
        All segments reuse the same encoder_outputs — identical voice embedding
        every call, text encoder never runs again for this batch.
        """
        from transformers.modeling_outputs import BaseModelOutput
        model_dtype = next(self._parler_model.parameters()).dtype
        with torch.no_grad():
            enc_out = self._parler_model.text_encoder(
                input_ids=desc_ids.input_ids,
                attention_mask=desc_ids.attention_mask.to(dtype=model_dtype) if desc_ids.attention_mask.is_floating_point() else desc_ids.attention_mask,
                return_dict=True,
            )
        # Apply enc_to_dec_proj if present (large model has this)
        hidden = enc_out.last_hidden_state
        if hasattr(self._parler_model, "enc_to_dec_proj"):
            hidden = self._parler_model.enc_to_dec_proj(hidden)
        if desc_ids.attention_mask is not None:
            hidden = hidden * desc_ids.attention_mask[..., None]
        return BaseModelOutput(last_hidden_state=hidden)

    def _parler_generate(self, desc_ids, prompt_ids, max_tok: int, lang: str = "hin",
                         encoder_outputs=None):
        """Fixed voice — seed is set ONCE before the primer warmup and never reset here.
        Resetting seed per-segment causes different noise draws → voice drift across video.
        do_sample=True with temperature=0.6 + fixed seed = consistent Indian accent.
        """
        temperature = 0.75  # higher = more natural Indian prosody, less robotic monotone
        kwargs = dict(
            prompt_input_ids=prompt_ids.input_ids,
            prompt_attention_mask=prompt_ids.attention_mask,
            do_sample=True,
            temperature=temperature,
            max_new_tokens=max_tok,
        )
        if encoder_outputs is not None:
            # Pass pre-computed encoder hidden states — skips text encoder entirely.
            # attention_mask must match the encoder_outputs sequence length.
            kwargs["encoder_outputs"] = encoder_outputs
            kwargs["attention_mask"] = desc_ids.attention_mask
        else:
            kwargs["input_ids"] = desc_ids.input_ids
            kwargs["attention_mask"] = desc_ids.attention_mask
        return self._parler_model.generate(**kwargs)

    # Dravidian scripts need a lower silence threshold — Parler outputs lower amplitude
    # Hindi: 0.01 threshold — Parler Hindi breathy consonants (ह, भ) start at ~0.015
    # so 0.02 was incorrectly rejecting valid soft-onset segments.
    _PARLER_MIN_AMP = {
        "tam": 0.005, "tel": 0.005, "kan": 0.005, "mal": 0.005,
        "hin": 0.005, "mar": 0.005, "nep": 0.005, "mai": 0.005, "san": 0.005,
    }

    # Batch size for Parler — 4 segments per forward pass.
    # Segments sorted by token length before batching so padding waste is minimal.
    _PARLER_BATCH_SIZE = 4

    def _parler_generate_batch(self, texts: list[str], lang: str,
                               output_paths: list[str], desc_ids,
                               encoder_outputs=None) -> list[bool]:
        """Synthesise a mini-batch of segments in one Parler forward pass.
        Returns list[bool] — True if segment written successfully.
        Falls back to single synthesis per failed item.
        """
        n = len(texts)
        results = [False] * n
        try:
            # Tokenize all prompts and pad to same length
            enc = self._parler_tokenizer(
                texts, return_tensors="pt", padding=True, truncation=True
            ).to(DEVICE)
            # max_new_tokens = longest segment in batch + 20% headroom
            max_tok = max(self._calc_max_tokens(t) for t in texts)
            # No seed reset here — seed is pinned once before primer warmup.
            # Resetting per-batch causes voice drift between segments.
            temperature = 0.75  # higher = more natural Indian prosody, less robotic monotone
            kwargs = dict(
                prompt_input_ids=enc.input_ids,
                prompt_attention_mask=enc.attention_mask,
                do_sample=True,
                temperature=temperature,
                max_new_tokens=max_tok,
            )
            if encoder_outputs is not None:
                # Expand encoder_outputs to match batch size
                from transformers.modeling_outputs import BaseModelOutput
                hidden = encoder_outputs.last_hidden_state  # [1, seq, dim]
                hidden_b = hidden.expand(n, -1, -1).contiguous()  # [n, seq, dim]
                attn_b   = desc_ids.attention_mask.expand(n, -1).contiguous()
                kwargs["encoder_outputs"] = BaseModelOutput(last_hidden_state=hidden_b)
                kwargs["attention_mask"]  = attn_b
            else:
                kwargs["input_ids"]      = desc_ids.input_ids.expand(n, -1)
                kwargs["attention_mask"] = desc_ids.attention_mask.expand(n, -1)
            import concurrent.futures
            def _run():
                with torch.no_grad():
                    return self._parler_model.generate(**kwargs)
            sample_text = texts[0] if texts else ""
            deva_count = sum(1 for c in sample_text if '\u0900' <= c <= '\u097F')
            batch_timeout = ((self._PARLER_TIMEOUT_TEL if (len(sample_text) > 0 and sum(1 for c in sample_text if '\u0C00'<=c<='\u0C7F')/max(len(sample_text),1)>0.4)
                             else self._PARLER_TIMEOUT_DEVA if (len(sample_text) > 0 and deva_count / max(len(sample_text),1) > 0.4)
                             else self._PARLER_TIMEOUT_S))
            # Always create a fresh executor — never reuse one whose thread may
            # still be running a timed-out generation (causes CUDA state corruption).
            _ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            _fut = _ex.submit(_run)
            try:
                gen = _fut.result(timeout=batch_timeout * n)
            except concurrent.futures.TimeoutError:
                log.error(f"Parler batch TIMEOUT [{lang}] {n} segs")
                _ex.shutdown(wait=False)
                if torch.cuda.is_available():
                    try:
                        torch.cuda.synchronize()
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                return results
            finally:
                _ex.shutdown(wait=False)
            try:
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
            except Exception:
                pass
            sr = self._parler_model.config.sampling_rate
            min_amp = self._PARLER_MIN_AMP.get(lang, 0.02)
            # gen shape: [n, audio_tokens] — split per item
            for bi in range(n):
                try:
                    wav = gen[bi].detach().cpu().float().numpy().squeeze()
                    wav = _trim_leading_silence(wav, sr)
                    if len(wav) / sr < self._PARLER_MIN_DUR or np.max(np.abs(wav)) < min_amp:
                        continue  # will retry as single
                    wav = _post_process(wav, sr, is_mms=False, lang=lang)
                    Path(output_paths[bi]).parent.mkdir(parents=True, exist_ok=True)
                    sf.write(output_paths[bi], wav, sr, subtype="PCM_16")
                    results[bi] = True
                except Exception as e:
                    log.warning(f"Parler batch item {bi} [{lang}] decode failed: {e}")
        except RuntimeError as e:
            err_s = str(e).lower()
            if "out of memory" in err_s or "illegal memory" in err_s:
                log.warning(f"Parler batch OOM [{lang}] n={n} — will retry as singles")
                try:
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                        torch.cuda.empty_cache()
                except Exception:
                    pass
            else:
                log.error(f"Parler batch [{lang}] failed: {e}")
        except Exception as e:
            log.error(f"Parler batch [{lang}] failed: {e}")
        return results

    def _parler_generate_single(self, text: str, lang: str, output_path: str,
                                 desc_ids, encoder_outputs=None) -> bool:
        try:
            prompt_ids = self._parler_tokenizer(text, return_tensors="pt").to(DEVICE)
            max_tok    = self._calc_max_tokens(text)
            # Use tighter timeout for Devanagari scripts (Hindi/Marathi/Nepali etc.)
            deva_count = sum(1 for c in text if '\u0900' <= c <= '\u097F')
            timeout = (self._PARLER_TIMEOUT_TEL if (len(text) > 0 and sum(1 for c in text if '\u0C00'<=c<='\u0C7F')/max(len(text),1)>0.4)
                       else self._PARLER_TIMEOUT_DEVA if (len(text) > 0 and deva_count / max(len(text),1) > 0.4)
                       else self._PARLER_TIMEOUT_S)
            def _gen_no_grad():
                with torch.no_grad():
                    return self._parler_generate(desc_ids, prompt_ids, max_tok,
                                                 lang=lang, encoder_outputs=encoder_outputs)
            import concurrent.futures
            # Fresh executor every call — a timed-out thread must not be reused.
            _ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            _fut = _ex.submit(_gen_no_grad)
            try:
                gen = _fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                log.error(f"Parler single TIMEOUT [{lang}] after {timeout}s STUCK FOR LONG TIME")
                _ex.shutdown(wait=False)
                if torch.cuda.is_available():
                    try:
                        torch.cuda.synchronize()
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                return False
            finally:
                _ex.shutdown(wait=False)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            wav = gen.detach().cpu().float().numpy().squeeze()
            sr  = self._parler_model.config.sampling_rate
            wav = _trim_leading_silence(wav, sr)
            min_amp = self._PARLER_MIN_AMP.get(lang, 0.02)
            if len(wav) / sr < self._PARLER_MIN_DUR or np.max(np.abs(wav)) < min_amp:
                return False
            wav = _post_process(wav, sr, is_mms=False, lang=lang)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, wav, sr, subtype="PCM_16")
            return True
        except Exception as e:
            log.error(f"Parler single [{lang}] failed: {e}")
            return False

    # Indic Unicode block ranges — each codepoint is one visible akshar
    # Using grapheme clusters: count \X matches (one per visible character)
    @staticmethod
    def _count_graphemes(text: str) -> int:
        import unicodedata
        # Normalize to NFC so composed chars count as 1
        t = unicodedata.normalize("NFC", text)
        # Count base letters only (skip combining marks, spaces, punctuation)
        return sum(1 for c in t if unicodedata.category(c)[0] in ("L", "N"))

    def _calc_max_tokens(self, text: str) -> int:
        """Estimate max audio tokens for Parler generation.
        Parler codec: 86 tokens/sec at 44kHz.

        Devanagari (Hindi/Marathi/Nepali/Dogri/Konkani/Sanskrit):
          Word-count × speech-rate — Devanagari akshars are multi-codepoint clusters
          so grapheme counting over-estimates. Hindi natural pace: ~2.5 words/sec.
          40% headroom ensures the last syllable is never cut off.
          Cap 1800 (~21s) — no single dubbed segment should exceed 21s.
          Verified: 45-word segment needs 1980 tokens → capped at 1800 safely
          because ASR segments are split at sentence boundaries (max ~35 words).

        Other Indic scripts:
          Grapheme-based with 1.4x headroom. Cap 1800.
        """
        deva_count = sum(1 for c in text if '\u0900' <= c <= '\u097F')
        is_devanagari = len(text) > 0 and (deva_count / max(len(text), 1)) > 0.4
        tel_count = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
        is_telugu = len(text) > 0 and (tel_count / max(len(text), 1)) > 0.4
        if is_devanagari or is_telugu:
            # Hindi/Devanagari formal speech rate: ~3.0 words/sec (not 2.5).
            # 2.5 over-allocated tokens and wasted GPU time on every segment.
            # Telugu keeps 2.5 — longer akshara clusters need more tokens per word.
            words = max(len(text.split()), 1)
            rate  = 2.5 if is_telugu else 3.0
            tokens = int((words / rate) * 86 * 1.5)
            # Telugu cap raised to 1200 (~14s) — 900 was cutting long sentences.
            cap = 2000
        else:
            graphemes = self._count_graphemes(text)
            tokens = int(graphemes * 43 * 1.6)
            cap = 2000
        return min(max(tokens, 250), cap)

    # Per-segment generation timeout.
    # cap=2000 tokens → worst-case ~23s audio → at ~150 tok/s = 13s → 120s is safe.
    # All scripts use 120s — Devanagari long segments were timing out at 60s.
    _PARLER_TIMEOUT_S    = 120  # all scripts — unified timeout
    _PARLER_TIMEOUT_DEVA = 120
    _PARLER_TIMEOUT_TEL  = 120
    # After a timeout the GPU thread may still be running — track the executor
    # so we can abandon it and create a fresh one for the next segment.
    _parler_executor     = None

    def _synthesize_parler(self, text: str, lang: str, output_path: str) -> bool:
        if lang in _PARLER_SKIP_LANGS:
            return False
        if not self._load_parler():
            return False
        model_dtype = next(self._parler_model.parameters()).dtype
        for _oom_attempt in range(2):
            try:
                desc       = self._build_description(lang)
                desc_ids   = self._parler_desc_tok(desc, return_tensors="pt").to(DEVICE)
                # Cast floating-point inputs to model dtype to avoid NaN from mixed precision
                desc_ids   = type(desc_ids)({k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                                             for k, v in desc_ids.items()})
                enc_out    = self._parler_encode_description(desc_ids)
                prompt_ids = self._parler_tokenizer(text, return_tensors="pt").to(DEVICE)
                max_tok    = self._calc_max_tokens(text)
                def _gen_no_grad_synth():
                    with torch.no_grad():
                        return self._parler_generate(desc_ids, prompt_ids, max_tok,
                                                     lang=lang, encoder_outputs=enc_out)
                import concurrent.futures
                # Fresh executor — never reuse a thread that may still be running
                # a timed-out generation (causes CUDA state corruption on next call).
                _ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                _fut = _ex.submit(_gen_no_grad_synth)
                try:
                    gen = _fut.result(timeout=_timeout)
                except concurrent.futures.TimeoutError:
                    log.error(f"Parler TIMEOUT [{lang}] after {_timeout}s — MMS fallback")
                    _ex.shutdown(wait=False)
                    if torch.cuda.is_available():
                        try:
                            torch.cuda.synchronize()
                            torch.cuda.empty_cache()
                        except Exception:
                            pass
                    return False
                finally:
                    _ex.shutdown(wait=False)
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                wav = gen.detach().cpu().numpy().squeeze().astype(np.float32)
                sr  = self._parler_model.config.sampling_rate
                wav = _trim_leading_silence(wav, sr)  # strip garbled preamble
                if len(wav) / sr < self._PARLER_MIN_DUR:
                    log.warning(f"Parler output too short [{lang}] — MMS fallback")
                    return False
                min_amp = self._PARLER_MIN_AMP.get(lang, 0.02)
                if np.max(np.abs(wav)) < min_amp:
                    log.warning(f"Parler output near-silent [{lang}] — MMS fallback")
                    return False
                wav = _post_process(wav, sr, is_mms=False, lang=lang)
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, wav, sr, subtype="PCM_16")
                return True
            except RuntimeError as e:
                err_s = str(e).lower()
                if ("out of memory" in err_s or "illegal memory" in err_s) and _oom_attempt == 0:
                    log.warning(f"Parler CUDA error [{lang}] — sync/clear and retrying")
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                        torch.cuda.empty_cache()
                    continue
                log.error(f"Parler synthesis failed [{lang}]: {e}")
                return False
            except Exception as e:
                log.error(f"Parler synthesis failed [{lang}]: {e}")
                return False
        return False

    # ----------------------------------------------------------
    def _write_silence_fallback(self, text: str, lang: str, output_path: str) -> bool:
        """Last-resort fallback — all TTS engines failed, write silence so pipeline never stalls."""
        log.warning(f"All TTS engines failed [{LANG_NAMES.get(lang, lang)}] — writing silence")
        self._write_silence(2.0, output_path)
        return True

    # ----------------------------------------------------------
    # Silence generator
    # ----------------------------------------------------------
    def _write_silence(self, duration: float, output_path: str):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        ret = subprocess.run(
            [_FFMPEG, "-y", "-f", "lavfi",
             "-i", f"anullsrc=r={SR}:cl=stereo",
             "-t", str(max(0.1, duration)),
             "-c:a", "pcm_s16le", output_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30,
        ).returncode
        if ret != 0 or not Path(output_path).exists():
            # ffmpeg unavailable — write silence directly with numpy
            silence = np.zeros(int(max(0.1, duration) * SR), dtype=np.float32)
            sf.write(output_path, silence, SR, subtype="PCM_16")

    # ----------------------------------------------------------
    # Script normalisation before TTS
    # sat (Ol Chiki): Parler-TTS cannot render Ol Chiki — transliterate to Devanagari
    # for pyttsx3 last-resort only. MMS sat adapter handles Ol Chiki natively.
    # ----------------------------------------------------------
    _OL_CHIKI_TO_DEVA = {
        "᱐": "क", "᱑": "ख", "᱒": "ग", "᱓": "घ", "᱔": "ङ",
        "᱕": "च", "᱖": "छ", "᱗": "ज", "᱘": "झ", "᱙": "ञ",
        "ᱚ": "ट", "ᱛ": "ठ", "ᱜ": "ड", "ᱝ": "ढ", "ᱞ": "ण",
        "ᱟ": "त", "ᱠ": "थ", "ᱡ": "द", "ᱢ": "ध", "ᱣ": "न",
        "ᱤ": "प", "ᱥ": "फ", "ᱦ": "ब", "ᱧ": "भ", "ᱨ": "म",
        "ᱩ": "य", "ᱪ": "र", "ᱫ": "ल", "ᱬ": "व", "ᱭ": "स",
        "ᱮ": "ह", "ᱯ": "अ", "ᱰ": "आ", "ᱱ": "इ", "ᱲ": "ई",
        "ᱳ": "उ", "ᱴ": "ऊ", "ᱵ": "ए", "ᱶ": "ओ", "ᱷ": "ं",
    }

    def _normalize_text_for_tts(self, text: str, lang: str, for_mms: bool = False) -> str:
        """Transliterate scripts that TTS engines cannot render.
        for_mms=True: keep Ol Chiki (MMS sat adapter handles it natively).
        for_mms=False (Parler/pyttsx3): transliterate Ol Chiki → Devanagari.
        """
        if lang == "sat" and not for_mms:
            return "".join(self._OL_CHIKI_TO_DEVA.get(c, c) for c in text)
        return text

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def synthesize(self, text: str, lang: str, output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        # Primary: Parler-TTS Indic Large (Indian-trained, 44kHz, fast)
        parler_text = self._normalize_text_for_tts(text, lang, for_mms=False)
        if lang not in _PARLER_SKIP_LANGS:
            for attempt in range(2):
                if self._synthesize_parler(parler_text, lang, output_path):
                    return output_path
                log.warning(f"Parler attempt {attempt+1}/2 failed [{LANG_NAMES.get(lang, lang)}] — retrying")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            log.warning(f"Parler failed both attempts [{LANG_NAMES.get(lang, lang)}] — trying MMS")
        # Fallback: MMS standalone VITS
        mms_text = self._normalize_text_for_tts(text, lang, for_mms=True)
        if self._synthesize_standalone_vits(mms_text, lang, output_path):
            return output_path
        ok_list = self._synthesize_mms_batch([mms_text], lang, [output_path])
        if ok_list and ok_list[0]:
            return output_path
        log.error(f"All TTS engines failed [{LANG_NAMES.get(lang, lang)}] — writing silence")
        self._write_silence(2.0, output_path)
        return output_path

    def synthesize_segments(self, segments: list[dict], lang: str,
                            output_dir: str) -> list[dict]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── Pin a single VITS RNG state for the entire video ──────────────────
        # Load the model ONCE here and restore the post-warmup RNG state.
        # The RNG then advances naturally through every chunk of every segment
        # without ever being reset — one continuous voice identity throughout.
        if lang in _PARLER_SKIP_LANGS and lang in _MMS_STANDALONE_LANGS:
            self._load_standalone_vits(lang)
            _vits_engine = self._standalone_vits.get(lang)
            if _vits_engine and _vits_engine.get("pinned_cpu_rng") is not None:
                torch.set_rng_state(_vits_engine["pinned_cpu_rng"])
                if _vits_engine.get("pinned_cuda_rng") is not None and torch.cuda.is_available():
                    torch.cuda.set_rng_state_all(_vits_engine["pinned_cuda_rng"])
                log.info(f"[{lang}] VITS RNG pinned once — single voice advancing naturally across all segments")
                self._vits_rng_pinned = True
        elif lang in _PARLER_SKIP_LANGS:
            # MMS adapter path — seed once for consistent voice
            torch.manual_seed(42)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(42)
            self._vits_rng_pinned = True
            log.info(f"[{lang}] MMS adapter RNG seeded once — single voice for all segments")

        results    = [{**seg, "audio_path": str(out_dir / f"seg_{seg['id']:04d}.wav")}
                      for seg in segments]
        text_idxs  = [i for i, s in enumerate(segments) if s.get("text", "").strip()]
        empty_idxs = [i for i in range(len(segments)) if i not in text_idxs]

        for i in empty_idxs:
            seg = segments[i]
            slot = max(0.1, seg.get("end", 0) - seg.get("start", 0))
            self._write_silence(slot, results[i]["audio_path"])

        if not text_idxs:
            return results

        # ── Primary: Parler-TTS Indic Large ─────────────────────────────────
        parler_skip = lang in _PARLER_SKIP_LANGS
        if not parler_skip and self._load_parler():
            desc     = self._build_description(lang)
            desc_ids = self._parler_desc_tok(desc, return_tensors="pt").to(DEVICE)
            # Cast desc_ids to model dtype to avoid NaN from mixed precision
            model_dtype = next(self._parler_model.parameters()).dtype
            desc_ids = type(desc_ids)({k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                                       for k, v in desc_ids.items()})
            # Pre-compute encoder hidden states ONCE for the entire video.
            # Every segment reuses the same encoder_outputs — text encoder
            # runs exactly once, guaranteeing identical voice embedding for all segments.
            enc_out  = self._parler_encode_description(desc_ids)
            log.info(f"Parler encoder pre-computed once [{lang}] — reusing for all {len(text_idxs)} segments")
            # Primer warmup — use a full natural Hindi sentence, not just a greeting.
            # A longer primer advances the RNG past the init state so all real
            # segments get consistent voice identity from the start.
            try:
                _PRIMER_MAP = {
                    "hin": "नमस्ते, आज हम एक महत्वपूर्ण विषय पर चर्चा करेंगे।",
                    "mar": "नमस्कार, आज आपण एका महत्त्वाच्या विषयावर चर्चा करणार आहोत।",
                    "nep": "नमस्ते, आज हामी एउटा महत्त्वपूर्ण विषयमा छलफल गर्नेछौं।",
                    "mai": "प्रणाम, आइ हम एकटा महत्वपूर्ण विषय पर चर्चा करब।",
                    "san": "नमस्ते, अद्य वयं एकस्मिन् महत्त्वपूर्णे विषये विचारं करिष्यामः।",
                }
                _primer_text = _PRIMER_MAP.get(lang, "नमस्ते, आज हम एक महत्वपूर्ण विषय पर चर्चा करेंगे।")
                _primer_ids = self._parler_tokenizer(_primer_text, return_tensors="pt").to(DEVICE)
                with torch.no_grad():
                    self._parler_generate(desc_ids, _primer_ids, 100, lang=lang,
                                          encoder_outputs=enc_out)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                log.info(f"Parler primer warmup done [{lang}] — RNG pinned, single voice for all segments")
            except Exception as _pw:
                log.warning(f"Parler primer warmup failed [{lang}]: {_pw} — continuing")

            # Sort text_idxs by token length so segments within each mini-batch
            # have similar lengths — minimises padding waste inside the batch.
            sorted_idxs = sorted(
                text_idxs,
                key=lambda i: self._calc_max_tokens(
                    self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=False)
                )
            )
            failed_idxs: list[int] = []
            # Use smaller batch size for long segments to avoid OOM
            def _batch_size_for(idxs):
                max_tok = max(self._calc_max_tokens(
                    self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=False)
                ) for i in idxs)
                return 2 if max_tok > 800 else self._PARLER_BATCH_SIZE

            b = 0
            batch_start = 0
            while batch_start < len(sorted_idxs):
                bs = _batch_size_for(sorted_idxs[batch_start:batch_start + self._PARLER_BATCH_SIZE])
                batch_idxs = sorted_idxs[batch_start: batch_start + bs]
                total_batches = None  # dynamic — log without total
                batch_texts = [
                    self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=False)
                    for i in batch_idxs
                ]
                batch_paths = [results[i]["audio_path"] for i in batch_idxs]
                log.info(f"Parler batch {b+1} [{lang}] — {len(batch_idxs)} segs")
                batch_ok = self._parler_generate_batch(
                    batch_texts, lang, batch_paths, desc_ids, encoder_outputs=enc_out
                )
                for bi, (i, ok) in enumerate(zip(batch_idxs, batch_ok)):
                    if ok:
                        log.info(f"  seg {i+1} [{lang}] ✓")
                    else:
                        # Retry as single synthesis
                        text_s = batch_texts[bi]
                        path_s = batch_paths[bi]
                        ok_s = False
                        for attempt in range(2):
                            try:
                                ok_s = self._parler_generate_single(
                                    text_s, lang, path_s, desc_ids, encoder_outputs=enc_out)
                                if ok_s:
                                    log.info(f"  seg {i+1} [{lang}] ✓ (single retry)")
                                    break
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()
                            except RuntimeError as e:
                                if "out of memory" in str(e).lower() or "illegal memory" in str(e).lower():
                                    if torch.cuda.is_available():
                                        torch.cuda.synchronize()
                                        torch.cuda.empty_cache()
                                else:
                                    break
                            except Exception:
                                break
                        if not ok_s:
                            # Split into halves
                            words = text_s.split()
                            if len(words) > 4:
                                mid = len(words) // 2
                                p1  = path_s.replace(".wav", "_h1.wav")
                                p2  = path_s.replace(".wav", "_h2.wav")
                                ok1 = self._parler_generate_single(
                                    " ".join(words[:mid]), lang, p1, desc_ids, encoder_outputs=enc_out)
                                ok2 = self._parler_generate_single(
                                    " ".join(words[mid:]), lang, p2, desc_ids, encoder_outputs=enc_out)
                                if ok1 or ok2:
                                    parts = []
                                    gap   = np.zeros(
                                        int(0.05 * self._parler_model.config.sampling_rate),
                                        dtype=np.float32)
                                    for p, o in [(p1, ok1), (p2, ok2)]:
                                        if o and Path(p).exists():
                                            w, _ = sf.read(p, dtype="float32")
                                            parts.append(w)
                                            parts.append(gap)
                                    if parts:
                                        sf.write(path_s, np.concatenate(parts[:-1]),
                                                 self._parler_model.config.sampling_rate,
                                                 subtype="PCM_16")
                                        ok_s = True
                                        log.info(f"  seg {i+1} [{lang}] ✓ (split)")
                                for p in (p1, p2):
                                    Path(p).unlink(missing_ok=True)
                        if not ok_s:
                            failed_idxs.append(i)
                batch_start += bs
                b += 1
            for i in failed_idxs:
                text_f = self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=True)
                path_f = results[i]["audio_path"]
                ok_f   = self._synthesize_standalone_vits(text_f, lang, path_f)
                if not ok_f:
                    ok_list = self._synthesize_mms_batch([text_f], lang, [path_f])
                    ok_f = ok_list[0] if ok_list else False
                if not ok_f:
                    slot = max(0.5, segments[i].get("end", 0) - segments[i].get("start", 0))
                    self._write_silence(slot, path_f)
                    log.warning(f"All TTS failed [{lang}] seg {i} — silence {slot:.1f}s written")
                else:
                    log.info(f"  seg {i+1} [{lang}] ✓ (MMS fallback)")
            text_idxs = []  # all handled

        # Parler skipped langs — try standalone VITS, then MMS, then silence
        for i in text_idxs:
            text = self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=True)
            path = results[i]["audio_path"]
            ok   = False
            if text:
                ok = self._synthesize_standalone_vits(text, lang, path)
                if not ok:
                    ok_list = self._synthesize_mms_batch([text], lang, [path])
                    ok = ok_list[0] if ok_list else False
            if not ok:
                slot = max(0.1, segments[i].get("end", 0) - segments[i].get("start", 0))
                self._write_silence(slot, path)
                log.warning(f"No TTS for [{lang}] seg {i} — silence written")

        self._vits_rng_pinned = False  # reset for next language
        return results

    # ----------------------------------------------------------
    # MMS-TTS — single shared model + per-lang adapter
    # ----------------------------------------------------------
    def _load_mms(self, lang: str) -> bool:
        if self._mms_load_failed:
            return False
        if lang in self._mms_adapter_failed:
            return False
        adapter_code = MMS_LANG_CODES.get(lang)
        if not adapter_code or not MMS_DIR.exists():
            return False
        try:
            from transformers import VitsModel, AutoTokenizer
            if self._mms_model is None:
                log.info("Loading MMS-TTS base model")
                self._mms_processor = AutoTokenizer.from_pretrained(str(MMS_DIR))
                self._mms_model = VitsModel.from_pretrained(
                    str(MMS_DIR),
                    torch_dtype=torch.float32,
                    low_cpu_mem_usage=True,
                ).to(DEVICE).float()
            if self._mms_current_lang != lang:
                adapter_file = MMS_DIR / f"adapter.{adapter_code}.safetensors"
                if not adapter_file.exists():
                    adapter_file = MMS_DIR / f"adapter.{adapter_code}.bin"
                if not adapter_file.exists():
                    log.warning(f"MMS adapter not found for {lang} ({adapter_code})")
                    # CRITICAL: do NOT leave _mms_current_lang pointing at a different
                    # language — reset it so the next call re-loads the correct adapter.
                    self._mms_current_lang = None
                    self._mms_adapter_failed.add(lang)
                    return False
                import safetensors.torch as _st
                sf_path  = MMS_DIR / f"adapter.{adapter_code}.safetensors"
                bin_path = MMS_DIR / f"adapter.{adapter_code}.bin"
                if sf_path.exists():
                    weights = _st.load_file(str(sf_path))
                elif bin_path.exists():
                    weights = torch.load(str(bin_path), map_location=DEVICE, weights_only=True)
                else:
                    log.warning(f"MMS adapter file not found for {lang} ({adapter_code})")
                    self._mms_current_lang = None
                    self._mms_adapter_failed.add(lang)
                    return False
                model_sd = self._mms_model.state_dict()
                matched  = {k: v for k, v in weights.items() if k in model_sd}
                if not matched:
                    matched = {f"vits.{k}": v for k, v in weights.items()
                               if f"vits.{k}" in model_sd}
                if not matched:
                    log.error(f"MMS adapter keys unmatched for {lang} ({adapter_code})")
                    self._mms_current_lang = None
                    self._mms_adapter_failed.add(lang)
                    return False
                model_sd.update(matched)
                self._mms_model.load_state_dict(model_sd, strict=False)
                self._mms_processor.set_target_lang(adapter_code)
                if hasattr(self._mms_model, "language_id"):
                    cfg_langs = getattr(self._mms_model.config, "languages", [])
                    self._mms_model.language_id = (
                        cfg_langs.index(adapter_code) if adapter_code in cfg_langs else 0
                    )
                # Only set _mms_current_lang AFTER successful adapter load
                self._mms_current_lang = lang
                log.info(f"MMS-TTS adapter loaded: {lang} ({adapter_code})")
            return True
        except Exception as e:
            log.error(f"MMS load failed [{lang}]: {e}")
            self._mms_model = None
            self._mms_current_lang = None
            self._mms_adapter_failed.add(lang)
            # Only set global failed flag if the base model itself failed to load
            if self._mms_model is None and not self._mms_load_failed:
                self._mms_load_failed = True
            return False

    # MMS-VITS hard token limit — batching beyond this causes truncation/repetition
    _MMS_MAX_TOKENS = 450

    def _synthesize_mms_batch(self, texts: list[str], lang: str,
                               paths: list[str]) -> list[bool]:
        if not self._load_mms(lang):
            return [False] * len(texts)
        results = [False] * len(texts)
        # Process one-at-a-time: avoids padding artifacts (Tamil underscores)
        # and silent truncation of long sequences (Malayalam)
        for i, (text, path) in enumerate(zip(texts, paths)):
            try:
                inputs = self._mms_processor(text, return_tensors="pt")
                # If over token limit, split and concatenate rather than skip
                if inputs["input_ids"].shape[-1] > self._MMS_MAX_TOKENS:
                    chunks = self._vits_chunks(text, self._mms_processor, lang=lang)
                    wavs = []
                    for ci, chunk in enumerate(chunks):
                        c_inputs = self._mms_processor(chunk, return_tensors="pt")
                        c_inputs = {k: v.to(dtype=torch.float32) if v.is_floating_point() else v
                                    for k, v in c_inputs.items()}
                        c_inputs = {k: v.to(DEVICE) for k, v in c_inputs.items()}
                        with torch.no_grad():
                            c_out = self._mms_model(**c_inputs)
                        if c_out.waveform is not None:
                            w = c_out.waveform[0].detach().cpu().float().numpy().squeeze()
                            nz = np.where(np.abs(w) > 1e-6)[0]
                            if len(nz) > 0:
                                wavs.append(w[:nz[-1] + 1])
                        if ci < len(chunks) - 1:
                            native_sr = self._mms_model.config.sampling_rate
                            wavs.append(np.zeros(int(120 * 0.001 * native_sr), dtype=np.float32))
                    if not wavs:
                        continue
                    native = self._mms_model.config.sampling_rate
                    combined = np.concatenate(wavs)
                    if native != SR:
                        import librosa
                        combined = librosa.resample(combined, orig_sr=native, target_sr=SR)
                    combined = _post_process(combined, SR, is_mms=True, lang=lang)
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
                    sf.write(path, combined, SR, subtype="PCM_16")
                    results[i] = True
                    continue
                inputs = {k: v.to(dtype=torch.float32) if v.is_floating_point() else v
                          for k, v in inputs.items()}
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                with torch.no_grad():
                    out = self._mms_model(**inputs)
                native = self._mms_model.config.sampling_rate
                w = out.waveform[0].detach().cpu().float().numpy().squeeze()
                nz = np.where(np.abs(w) > 1e-6)[0]
                if len(nz) == 0:
                    continue
                w = w[:nz[-1] + 1]
                if native != SR:
                    import librosa
                    w = librosa.resample(w, orig_sr=native, target_sr=SR)
                w = _post_process(w, SR, is_mms=True, lang=lang)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                sf.write(path, w, SR, subtype="PCM_16")
                results[i] = True
            except Exception as e:
                log.error(f"MMS [{lang}] seg {i} failed: {e}")
        return results

    def get_audio_duration(self, audio_path: str) -> float:
        return sf.info(audio_path).duration
