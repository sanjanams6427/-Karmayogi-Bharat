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
    "urd": "urd",  "nep": "nep",  "mai": "mai",
    "san": "san",  "sat": "sat",  "snd": "snd",
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


# Languages where Parler-TTS cannot render the script at all.
# sat/kas/snd: Ol Chiki / Arabic script — skip Parler, go straight to MMS VITS.
# tam/tel: Dravidian scripts — dedicated MMS VITS models are faster, more stable,
# and produce better quality than Parler (which needs amplitude hacks + bs=2).
_PARLER_SKIP_LANGS: set = {
    "sat", "kas", "snd", "tam", "tel",
}


# Per-language descriptions for ai4bharat Indic Parler-TTS.
# The model was trained with Indian-language-specific prompts — using the correct
# language name and "Indian" cues is essential for natural-sounding output.
# "slightly high-pitched" is kept for Dravidian langs (tam/tel/kan/mal) because
# deep-voice prompts produce near-silence on those scripts.
# All descriptions are identical in structure so the speaker embedding stays
# consistent across segments — only the language name changes.
_PARLER_DESCS: dict[str, str] = {
    "tel": "A Telugu male speaker with a clear, slightly high-pitched natural Indian voice "
           "delivers fluent Telugu speech at a moderate pace, pronouncing every word fully. "
           "The recording is of very high quality with no background noise.",
    "tam": "A Tamil male speaker with a clear, slightly high-pitched natural Indian voice "
           "delivers fluent Tamil speech at a moderate pace, pronouncing every word fully. "
           "The recording is of very high quality with no background noise.",
    "kan": "A Kannada male speaker with a clear, slightly high-pitched natural Indian voice "
           "delivers fluent Kannada speech at a moderate pace, pronouncing every word fully. "
           "The recording is of very high quality with no background noise.",
    "mal": "A Malayalam male speaker with a clear, slightly high-pitched natural Indian voice "
           "delivers fluent Malayalam speech at a moderate pace, pronouncing every word fully. "
           "The recording is of very high quality with no background noise.",
    "hin": "A Hindi male speaker with a clear, natural Indian voice delivers fluent Hindi speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "ben": "A Bengali male speaker with a clear, natural Indian voice delivers fluent Bengali speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "mar": "A Marathi male speaker with a clear, natural Indian voice delivers fluent Marathi speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "guj": "A Gujarati male speaker with a clear, natural Indian voice delivers fluent Gujarati speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "pan": "A Punjabi male speaker with a clear, natural Indian voice delivers fluent Punjabi speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "ory": "An Odia male speaker with a clear, natural Indian voice delivers fluent Odia speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "asm": "An Assamese male speaker with a clear, natural Indian voice delivers fluent Assamese speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "urd": "An Urdu male speaker with a clear, natural Indian voice delivers fluent Urdu speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "nep": "A Nepali male speaker with a clear, natural Indian voice delivers fluent Nepali speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "mai": "A Maithili male speaker with a clear, natural Indian voice delivers fluent Maithili speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "doi": "A Dogri male speaker with a clear, natural Indian voice delivers fluent Dogri speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "kok": "A Konkani male speaker with a clear, natural Indian voice delivers fluent Konkani speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "mni": "A Manipuri male speaker with a clear, natural Indian voice delivers fluent Manipuri speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "san": "A Sanskrit male speaker with a clear, natural Indian voice delivers fluent Sanskrit speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
    "bod": "A Bodo male speaker with a clear, natural Indian voice delivers fluent Bodo speech "
           "at a moderate pace, pronouncing every word fully and distinctly. "
           "The recording is of very high quality with no background noise.",
}
# Fallback for any language not in the dict above
_PARLER_DESC_DEFAULT = (
    "A male speaker with a clear, natural Indian voice delivers speech at a moderate pace, "
    "pronouncing every word fully and distinctly. "
    "The recording is of very high quality with no background noise."
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


def _trim_leading_silence(audio: np.ndarray, sr: int, threshold: float = 0.03) -> np.ndarray:
    """Trim silent/noisy preamble from Parler output.
    Parler-TTS often generates 100-300ms of near-silent noise before actual speech.
    Threshold raised to 0.03 (was 0.015) — catches the low-level buzz that
    Dravidian-script outputs (tel/tam/kan/mal) produce before real speech starts.
    Scans in 10ms frames, returns audio starting from first frame above threshold.
    """
    frame = int(0.010 * sr)  # 10ms frames
    for i in range(0, len(audio) - frame, frame):
        if np.max(np.abs(audio[i:i + frame])) >= threshold:
            lead = max(0, i - int(0.005 * sr))
            return audio[lead:]
    return audio


def _post_process(audio: np.ndarray, sr: int = SR, is_mms: bool = False, female_shift: bool = False) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    # High-pass at 80Hz — removes DC/rumble without cutting Telugu/Tamil low vowels.
    # 120Hz was too aggressive: clipped the fundamental of retroflex consonants.
    sos = butter(2, 80.0 / (sr / 2), btype="high", output="sos")
    audio = sosfilt(sos, audio).astype(np.float32)
    if is_mms:
        # Low-pass at 7500Hz — MMS VITS 16kHz model; aliasing artefacts above 7.5kHz
        # are the main source of the "noise between words" in Telugu/Tamil.
        sos_lp = butter(3, 7500.0 / (sr / 2), btype="low", output="sos")
        audio  = sosfilt(sos_lp, audio).astype(np.float32)
        # Trim trailing near-silence — use 0.015 threshold (was 0.005).
        # 0.005 kept aliasing noise tail; 0.015 cuts it cleanly without
        # clipping the last consonant of Telugu words.
        nz = np.where(np.abs(audio) > 0.015)[0]
        if len(nz) > 0:
            keep = min(nz[-1] + int(0.035 * sr), len(audio))  # 35ms decay tail
            audio = audio[:keep]
    if female_shift:
        try:
            import librosa
            audio = librosa.effects.pitch_shift(audio.astype(np.float32), sr=sr, n_steps=5, res_type='soxr_hq')
        except Exception as _ps_err:
            log.warning(f"pitch_shift failed ({_ps_err}) — keeping original pitch")
    # Normalize to -1 dBFS
    peak = np.max(np.abs(audio))
    if peak > 0.01:
        audio = audio * (0.891 / peak)
    return audio


class TTSEngine:
    _PARLER_MIN_DUR = 0.3  # seconds — lower threshold, short words are valid

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
                model = VitsModel.from_pretrained(
                    str(model_path), torch_dtype=torch.float32
                ).to(DEVICE).eval()
            # Pin noise_scale to 0.0 — eliminates stochastic voice variation between
            # segments. Default 0.667 causes different timbre on every call.
            # noise_scale_duration=0.0 locks duration predictor too (consistent pacing).
            # noise_scale=0.3 — small variance gives natural prosody without
            # voice drift between chunks. 0.0 causes robotic flat intonation
            # in Telugu/Tamil; 0.667 (default) causes timbre shift per chunk.
            model.config.noise_scale          = 0.3
            model.config.noise_scale_duration  = 0.1
            for _attr in ("inference_noise_scale", "inference_noise_scale_dp"):
                if hasattr(model.config, _attr):
                    setattr(model.config, _attr, 0.3)
            self._standalone_vits[lang] = {"model": model, "tokenizer": tokenizer,
                                           "seed": 42}
            log.info(f"Standalone VITS [{lang}] loaded (noise_scale=0.3)")
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
            _warm_text = _WARMUP_TEXT.get(lang, "hello")
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
    # Tamil/Telugu akshara clusters tokenize to ~3-4 tokens each — 200 tokens
    # fits ~50-65 akshars which is a comfortable sentence length.
    # 300 was too high: chunk boundary fell mid-word causing cut-off last syllable.
    _VITS_MAX_TOKENS = 200

    def _vits_chunks(self, text: str, tokenizer) -> list[str]:
        """Split text into chunks that fit within VITS token limit.
        Preference order: no split → sentence boundary (। . ! ?) → word midpoint.
        Never splits on commas/semicolons — those cause audible voice breaks
        mid-clause which sound like a different speaker.
        """
        import re
        ids = tokenizer(text, return_tensors="pt")["input_ids"]
        if ids.shape[-1] <= self._VITS_MAX_TOKENS:
            return [text]
        # Only split on hard sentence boundaries
        parts = re.split(r'(?<=[\u0964.!?])\s+', text.strip())
        if len(parts) <= 1:
            # No sentence boundary — split on word midpoint
            words = text.split()
            mid   = len(words) // 2
            parts = [" ".join(words[:mid]), " ".join(words[mid:])]
        chunks, current = [], ""
        for part in parts:
            candidate = (current + " " + part).strip() if current else part
            if tokenizer(candidate, return_tensors="pt")["input_ids"].shape[-1] <= self._VITS_MAX_TOKENS:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if tokenizer(part, return_tensors="pt")["input_ids"].shape[-1] > self._VITS_MAX_TOKENS:
                    words = part.split()
                    mid   = len(words) // 2
                    chunks.append(" ".join(words[:mid]))
                    current = " ".join(words[mid:])
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
            chunks    = self._vits_chunks(text, tokenizer)
            wavs      = []
            # Use pinned RNG state from warmup if available, else seed fresh
            _pinned_cpu  = engine.get("pinned_cpu_rng")
            _pinned_cuda = engine.get("pinned_cuda_rng")
            if _pinned_cpu is not None:
                _cpu_rng  = _pinned_cpu
                _cuda_rng = _pinned_cuda
            else:
                seed = engine.get("seed", 42)
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)
                _cpu_rng  = torch.get_rng_state()
                _cuda_rng = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None

            for ci, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                # Restore identical RNG state before every chunk — same noise draw every time
                torch.set_rng_state(_cpu_rng)
                if _cuda_rng is not None:
                    torch.cuda.set_rng_state_all(_cuda_rng)
                inputs = tokenizer(chunk, return_tensors="pt")
                inputs = {k: v.long().to(DEVICE) if k == "input_ids" else v.to(DEVICE)
                          for k, v in inputs.items()}
                with torch.no_grad():
                    out = model(**inputs)
                if out.waveform is None:
                    log.warning(f"Standalone VITS [{lang}] waveform=None for chunk {ci} — skipping")
                    continue
                w = out.waveform[0].detach().cpu().float().numpy().squeeze()
                # Use 0.01 threshold (was 1e-5) — keeps Telugu consonant decay
                # that 1e-5 was trimming, causing cut-off last syllable.
                nz = np.where(np.abs(w) > 0.01)[0]
                if len(nz) == 0:
                    continue
                # Keep 30ms after last active sample — preserves final consonant release
                w = w[:min(nz[-1] + int(0.03 * native), len(w))]
                # 2ms crossfade only — eliminates click without audible gap
                fade = min(int(0.002 * native), len(w) // 8)
                if fade > 0:
                    w[:fade]  *= np.linspace(0.0, 1.0, fade)
                    w[-fade:] *= np.linspace(1.0, 0.0, fade)
                wavs.append(w)
            if not wavs:
                return False
            combined = np.concatenate(wavs)
            if native != SR:
                import librosa
                combined = librosa.resample(combined, orig_sr=native, target_sr=SR)
            combined = _post_process(combined, SR, is_mms=True)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, combined, SR)
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
    # Single fixed seed for ALL languages — guarantees identical voice character
    # across every language and every segment. One voice throughout the video.
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
        """Fixed Generator per language — same voice every segment, no drift.
        encoder_outputs pre-computed once and reused — text encoder never re-runs.
        do_sample=True is required (model trained with sampling; greedy = silence/garbage).
        torch.Generator pinned to a fixed seed per language gives deterministic output.
        """
        seed = self._LANG_SEEDS.get(lang, 42)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        kwargs = dict(
            prompt_input_ids=prompt_ids.input_ids,
            prompt_attention_mask=prompt_ids.attention_mask,
            do_sample=True,
            temperature=0.7,
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
    _PARLER_MIN_AMP = {"tam": 0.008, "tel": 0.008, "kan": 0.008, "mal": 0.008}

    # Batch size for Parler — 4 segments per forward pass.
    # A6000 47GB: Parler Large ~3.6GB weights + ~1GB KV cache per item → 4 safe, 8 risky.
    # Segments sorted by token length so padding waste is minimal within each batch.
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
            seed = self._LANG_SEEDS.get(lang, 42)
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            # temperature=0.7 reduces sampling variance across batch items —
            # keeps voice timbre consistent between segments while still
            # sounding natural (temperature=1.0 causes noticeable voice drift
            # between items in the same batch).
            kwargs = dict(
                prompt_input_ids=enc.input_ids,
                prompt_attention_mask=enc.attention_mask,
                do_sample=True,
                temperature=0.7,
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
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
                _fut = _ex.submit(_run)
                try:
                    gen = _fut.result(timeout=self._PARLER_TIMEOUT_S * n)
                except concurrent.futures.TimeoutError:
                    log.error(f"Parler batch TIMEOUT [{lang}] {n} segs")
                    return results
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
                    wav = _post_process(wav, sr, is_mms=False)
                    Path(output_paths[bi]).parent.mkdir(parents=True, exist_ok=True)
                    sf.write(output_paths[bi], wav, sr)
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
            def _gen_no_grad():
                with torch.no_grad():
                    return self._parler_generate(desc_ids, prompt_ids, max_tok,
                                                 lang=lang, encoder_outputs=encoder_outputs)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
                _fut = _ex.submit(_gen_no_grad)
                try:
                    gen = _fut.result(timeout=self._PARLER_TIMEOUT_S)
                except concurrent.futures.TimeoutError:
                    log.error(f"Parler single TIMEOUT [{lang}] after {self._PARLER_TIMEOUT_S}s")
                    return False
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            wav = gen.detach().cpu().float().numpy().squeeze()
            sr  = self._parler_model.config.sampling_rate
            wav = _trim_leading_silence(wav, sr)
            min_amp = self._PARLER_MIN_AMP.get(lang, 0.02)
            if len(wav) / sr < self._PARLER_MIN_DUR or np.max(np.abs(wav)) < min_amp:
                return False
            wav = _post_process(wav, sr, is_mms=False)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, wav, sr)
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
        """Estimate max audio tokens.
        ai4bharat Parler codec: ~86 tokens/sec at 44kHz.
        Natural Indic speech: ~2.0 words/sec, ~1.5 akshars/word → ~0.5s/akshar → 43 tokens/akshar.
        Add 20% headroom (was 40%) — tighter cap prevents multi-minute hangs on long segments.
        min 200, max 1500 (~17s) — no single TTS segment should exceed 17s.
        """
        graphemes = self._count_graphemes(text)
        return min(max(int(graphemes * 43 * 1.2), 200), 1500)

    # Per-segment generation timeout in seconds — prevents infinite hang
    _PARLER_TIMEOUT_S = 120

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
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
                    _fut = _ex.submit(_gen_no_grad_synth)
                    try:
                        gen = _fut.result(timeout=self._PARLER_TIMEOUT_S)
                    except concurrent.futures.TimeoutError:
                        log.error(f"Parler TIMEOUT [{lang}] after {self._PARLER_TIMEOUT_S}s — MMS fallback")
                        return False
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
                wav = _post_process(wav, sr, is_mms=False)
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, wav, sr)
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
    def _synthesize_pyttsx3(self, text: str, lang: str, output_path: str) -> bool:
        """Removed — writes silence so pipeline never stalls."""
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
             "-i", f"anullsrc=r={SR}:cl=mono",
             "-t", str(max(0.1, duration)), output_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30,
        ).returncode
        if ret != 0 or not Path(output_path).exists():
            # ffmpeg unavailable — write silence directly with numpy
            silence = np.zeros(int(max(0.1, duration) * SR), dtype=np.float32)
            sf.write(output_path, silence, SR)

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
            for attempt in range(3):
                if self._synthesize_parler(parler_text, lang, output_path):
                    return output_path
                log.warning(f"Parler attempt {attempt+1}/3 failed [{LANG_NAMES.get(lang, lang)}] — retrying")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            log.warning(f"Parler failed all 3 attempts [{LANG_NAMES.get(lang, lang)}] — trying MMS")
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
            # Pre-compute encoder hidden states ONCE for the entire video.
            # Every segment reuses the same encoder_outputs — text encoder
            # runs exactly once, guaranteeing identical voice embedding for all segments.
            enc_out  = self._parler_encode_description(desc_ids)
            log.info(f"Parler encoder pre-computed once [{lang}] — reusing for all {len(text_idxs)} segments")
            # Primer warmup
            try:
                _primer_ids = self._parler_tokenizer(".", return_tensors="pt").to(DEVICE)
                with torch.no_grad():
                    self._parler_generate(desc_ids, _primer_ids, 50, lang=lang,
                                          encoder_outputs=enc_out)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                log.info(f"Parler primer warmup done [{lang}]")
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
                return 2 if max_tok > 1200 else self._PARLER_BATCH_SIZE

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
                                                 self._parler_model.config.sampling_rate)
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
                    slot = max(0.1, segments[i].get("end", 0) - segments[i].get("start", 0))
                    self._write_silence(slot, path_f)
                    log.warning(f"All TTS failed [{lang}] seg {i} — silence written")
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

        return results

    # ----------------------------------------------------------
    # MMS-TTS — single shared model + per-lang adapter
    # ----------------------------------------------------------
    def _load_mms(self, lang: str) -> bool:
        if self._mms_load_failed:
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
                # Use load_adapter API — correct way to swap MMS language adapters
                adapter_file = MMS_DIR / f"adapter.{adapter_code}.safetensors"
                if not adapter_file.exists():
                    adapter_file = MMS_DIR / f"adapter.{adapter_code}.bin"
                if not adapter_file.exists():
                    log.warning(f"MMS adapter not found for {lang} ({adapter_code})")
                    return False
                # Always load adapter weights directly from local safetensors/bin file.
                # load_adapter() with a local path uses HF hub resolution which fails
                # for locally-downloaded adapters — use safetensors direct load instead.
                import safetensors.torch as _st
                sf_path  = MMS_DIR / f"adapter.{adapter_code}.safetensors"
                bin_path = MMS_DIR / f"adapter.{adapter_code}.bin"
                if sf_path.exists():
                    weights = _st.load_file(str(sf_path))
                elif bin_path.exists():
                    weights = torch.load(str(bin_path), map_location=DEVICE, weights_only=True)
                else:
                    log.warning(f"MMS adapter file not found for {lang} ({adapter_code})")
                    return False
                model_sd = self._mms_model.state_dict()
                matched  = {k: v for k, v in weights.items() if k in model_sd}
                if not matched:
                    matched = {f"vits.{k}": v for k, v in weights.items()
                               if f"vits.{k}" in model_sd}
                if not matched:
                    log.error(f"MMS adapter keys unmatched for {lang} ({adapter_code})")
                    return False
                model_sd.update(matched)
                self._mms_model.load_state_dict(model_sd, strict=False)
                self._mms_processor.set_target_lang(adapter_code)
                # Set language_id on model if it uses a language embedding table
                if hasattr(self._mms_model, "language_id"):
                    cfg_langs = getattr(self._mms_model.config, "languages", [])
                    self._mms_model.language_id = (
                        cfg_langs.index(adapter_code) if adapter_code in cfg_langs else 0
                    )
                self._mms_current_lang = lang
                log.info(f"MMS-TTS adapter loaded: {lang} ({adapter_code})")
            return True
        except Exception as e:
            log.error(f"MMS load failed [{lang}]: {e}")
            self._mms_model = None
            self._mms_load_failed = True  # stop retrying on every segment
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
                # Reject if over token limit — prevents VITS repetition loop
                if inputs["input_ids"].shape[-1] > self._MMS_MAX_TOKENS:
                    log.warning(f"MMS [{lang}] text too long ({inputs['input_ids'].shape[-1]} tokens), skipping")
                    continue
                inputs = {k: v.to(dtype=torch.float32) if v.is_floating_point() else v
                          for k, v in inputs.items()}
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                with torch.no_grad():
                    out = self._mms_model(**inputs)
                native = self._mms_model.config.sampling_rate
                w = out.waveform[0].detach().cpu().float().numpy().squeeze()
                nz = np.where(np.abs(w) > 1e-5)[0]
                if len(nz) == 0:
                    continue
                w = w[:nz[-1] + 1]
                if native != SR:
                    import librosa
                    w = librosa.resample(w, orig_sr=native, target_sr=SR)
                w = _post_process(w, SR, is_mms=True)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                sf.write(path, w, SR)
                results[i] = True
            except Exception as e:
                log.error(f"MMS [{lang}] seg {i} failed: {e}")
        return results

    def get_audio_duration(self, audio_path: str) -> float:
        return sf.info(audio_path).duration
