# ============================================================
# TTS Engine — Offline, Zero-cost
# Primary  : Indic Parler-TTS — 22 langs, 44kHz, GPU batch
# Fallback1: MMS-TTS — all 22 langs
# Fallback2: Coqui XTTS-v2 — open-source, near-human quality
# ============================================================

import os, subprocess, json
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
XTTS_DIR         = MODELS_DIR / "xtts_v2"          # Coqui XTTS-v2 — open-source fallback

# Languages that have a standalone VITS model (not an adapter of the shared MMS base)
# key = pipeline lang code, value = subfolder under MMS_STANDALONE
# Download with: python scripts/download_models.py
_MMS_STANDALONE_LANGS = {
    "doi": "dgo",   # Dogri standalone VITS (downloaded)
    "bod": "bod",   # Bodo standalone VITS  (downloaded)
    "mni": "mni",   # Manipuri proxy VITS (facebook/mms-tts-ben)
    "kok": "kok",   # Konkani proxy VITS (facebook/mms-tts-mar)
    "kas": "kas",   # Kashmiri proxy VITS (facebook/mms-tts-urd-script_arabic)
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


# Languages where Parler-TTS cannot render the script — skip directly to MMS
# sat=Ol Chiki, kas/snd=Arabic script — Parler always produces silence for these
_PARLER_SKIP_LANGS: set = {"sat", "kas", "snd"}

# Generic description style — this model (parler-tts-mini-v2 Indic fine-tune) was NOT
# trained with named speakers. Named descriptions like "Divya's voice..." produce silence.
# Generic style produces real audio (tested: peak 0.36 vs 0.008 with named style).
_PARLER_DESC = "A speaker delivers clear and expressive speech at a moderate pace with a natural pitch. The recording is of very high quality, with a close-sounding voice and no background noise."

# Per-language descriptions — all use generic style, no named speakers
_PARLER_SPEAKERS = {lang: ("generic", _PARLER_DESC) for lang in [
    "hin", "ben", "tam", "tel", "kan", "mal", "mar", "guj", "pan", "ory",
    "asm", "urd", "nep", "bod", "doi", "kok", "mni", "mai", "san",
    "sat", "snd", "kas", "eng",
]}

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

# XTTS-v2 language codes (Coqui TTS)
# https://github.com/coqui-ai/TTS — Apache 2.0, offline, near-human quality
_XTTS_LANG_CODES = {
    "hin": "hi", "ben": "bn", "tam": "ta", "tel": "te", "kan": "kn",
    "mal": "ml", "mar": "mr", "guj": "gu", "pan": "pa", "ury": "ur",
    "urd": "ur", "nep": "ne", "asm": "as", "ory": "or",
    # Low-resource: route to closest supported language
    "mai": "hi", "doi": "hi", "kok": "mr", "mni": "bn",
    "san": "hi",  # Sanskrit -- closest XTTS lang; Parler is preferred for san
    "sat": "hi", "snd": "ur", "kas": "ur",
    "bod": "hi",
}

# Reference speaker WAV for XTTS voice cloning — 6-second clean female voice per lang
# Falls back to a single generic Indian-English reference if per-lang file missing
_XTTS_REF_DIR = Path(__file__).parent.parent / "assets" / "xtts_refs"




def _post_process(audio: np.ndarray, sr: int = SR, is_mms: bool = False, female_shift: bool = False) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    # High-pass to remove DC/rumble
    sos = butter(2, 80.0 / (sr / 2), btype="high", output="sos")
    audio = sosfilt(sos, audio).astype(np.float32)
    if is_mms:
        sos_lp = butter(2, 12000.0 / (sr / 2), btype="low", output="sos")
        audio  = sosfilt(sos_lp, audio).astype(np.float32)
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
    _PARLER_MIN_DUR = 0.5  # seconds — shorter means silence/failure

    def __init__(self):
        self._parler_model     = None
        self._parler_tokenizer = None
        self._parler_desc_tok  = None
        self._parler_label     = None  # "large" or "mini"
        self._mms_model        = None
        self._mms_processor    = None
        self._mms_current_lang = None
        self._ai4bharat        = {}  # dict keyed by model dir path
        self._standalone_vits: dict = {}  # lang -> {model, tokenizer}
        self._xtts_model       = None     # Coqui XTTS-v2
        self._mms_load_failed  = False     # instance-level — reset per TTSEngine

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
        _, desc = _PARLER_SPEAKERS.get(lang, ("generic", _PARLER_DESC))
        return desc

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
            from transformers import VitsModel, AutoTokenizer
            log.info(f"Loading standalone VITS [{lang}] from {model_path}")
            tokenizer = AutoTokenizer.from_pretrained(str(model_path))
            model = VitsModel.from_pretrained(
                str(model_path), torch_dtype=torch.float32
            ).to(DEVICE).eval()
            self._standalone_vits[lang] = {"model": model, "tokenizer": tokenizer}
            log.info(f"Standalone VITS [{lang}] loaded")
            return True
        except Exception as e:
            log.error(f"Standalone VITS load failed [{lang}]: {e}")
            return False

    def _synthesize_standalone_vits(self, text: str, lang: str, output_path: str) -> bool:
        if not self._load_standalone_vits(lang):
            return False
        try:
            engine    = self._standalone_vits[lang]
            tokenizer = engine["tokenizer"]
            model     = engine["model"]
            inputs = tokenizer(text, return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                out = model(**inputs)
            native = model.config.sampling_rate
            w = out.waveform[0].cpu().float().numpy().squeeze()
            nz = np.where(np.abs(w) > 1e-5)[0]
            if len(nz) == 0:
                return False
            w = w[:nz[-1] + 1]
            if native != SR:
                import librosa
                w = librosa.resample(w, orig_sr=native, target_sr=SR)
            w = _post_process(w, SR, is_mms=True)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, w, SR)
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
    # Fixed seed per language — ensures same voice character across ALL segments
    _LANG_SEEDS = {
        "hin": 42, "ben": 43, "tam": 44, "tel": 45, "kan": 46,
        "mal": 47, "mar": 48, "guj": 49, "pan": 50, "ory": 51,
        "asm": 52, "urd": 53, "nep": 54, "bod": 55, "doi": 56,
        "kok": 57, "mni": 58, "mai": 59, "san": 60, "sat": 61,
        "snd": 62, "kas": 63, "eng": 64,
    }

    def _parler_generate(self, desc_ids, prompt_ids, max_tok: int):
        """Single generate call — always called with same args for voice consistency."""
        return self._parler_model.generate(
            input_ids=desc_ids.input_ids,
            attention_mask=desc_ids.attention_mask,
            prompt_input_ids=prompt_ids.input_ids,
            prompt_attention_mask=prompt_ids.attention_mask,
            do_sample=True,
            temperature=0.7,
            max_new_tokens=max_tok,
        )

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
        """Estimate max audio tokens from visible grapheme count.
        Parler/ai4bharat codec: ~86 tokens/sec.
        Indic akshars average ~0.28s each → 86*0.28 ≈ 24 tokens/akshar.
        min 200 (covers single short word), max 1500 (~17s, longest segment).
        """
        graphemes = self._count_graphemes(text)
        return min(max(graphemes * 25, 200), 1500)

    def _synthesize_parler(self, text: str, lang: str, output_path: str) -> bool:
        if lang in _PARLER_SKIP_LANGS:
            return False
        if not self._load_parler():
            return False
        for _oom_attempt in range(2):
            try:
                desc       = self._build_description(lang)
                desc_ids   = self._parler_desc_tok(desc, return_tensors="pt").to(DEVICE)
                prompt_ids = self._parler_tokenizer(text, return_tensors="pt").to(DEVICE)
                max_tok    = self._calc_max_tokens(text)
                seed = self._LANG_SEEDS.get(lang, 42)
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)
                with torch.no_grad():
                    gen = self._parler_generate(desc_ids, prompt_ids, max_tok)
                wav = gen.cpu().numpy().squeeze().astype(np.float32)
                sr  = self._parler_model.config.sampling_rate
                if len(wav) / sr < self._PARLER_MIN_DUR:
                    log.warning(f"Parler output too short [{lang}] — MMS fallback")
                    return False
                if np.max(np.abs(wav)) < 0.02:
                    log.warning(f"Parler output near-silent [{lang}] — MMS fallback")
                    return False
                wav = _post_process(wav, sr, is_mms=False)
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, wav, sr)
                return True
            except RuntimeError as e:
                if "out of memory" in str(e).lower() and _oom_attempt == 0:
                    log.warning(f"Parler OOM [{lang}] — clearing cache and retrying")
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    continue
                log.error(f"Parler synthesis failed [{lang}]: {e}")
                return False
            except Exception as e:
                log.error(f"Parler synthesis failed [{lang}]: {e}")
                return False
        return False

    # ----------------------------------------------------------
    # Coqui XTTS-v2 — open-source, Apache 2.0, near-human quality
    # Model: tts_models/multilingual/multi-dataset/xtts_v2
    # Supports 17 languages natively + cross-lingual for the rest
    # ----------------------------------------------------------
    def _load_xtts(self) -> bool:
        if self._xtts_model is not None:
            return True
        try:
            from TTS.api import TTS as CoquiTTS
            log.info("Loading Coqui XTTS-v2")
            if XTTS_DIR.exists():
                self._xtts_model = CoquiTTS(model_path=str(XTTS_DIR),
                                            config_path=str(XTTS_DIR / "config.json"),
                                            progress_bar=False).to(DEVICE)
            else:
                # Auto-download on first use (~1.8GB, cached to ~/.local/share/tts)
                self._xtts_model = CoquiTTS(
                    "tts_models/multilingual/multi-dataset/xtts_v2",
                    progress_bar=False
                ).to(DEVICE)
            log.info("Coqui XTTS-v2 loaded")
            return True
        except Exception as e:
            log.error(f"XTTS-v2 load failed: {e}")
            self._xtts_model = None
            return False

    def _get_xtts_ref(self, lang: str) -> str | None:
        """Return path to a reference speaker WAV for XTTS voice cloning."""
        # Per-language reference file
        ref = _XTTS_REF_DIR / f"{lang}.wav"
        if ref.exists():
            return str(ref)
        # Generic Indian-English female reference
        generic = _XTTS_REF_DIR / "generic_indic.wav"
        if generic.exists():
            return str(generic)
        return None

    def _synthesize_xtts(self, text: str, lang: str, output_path: str) -> bool:
        if not self._load_xtts():
            return False
        xtts_lang = _XTTS_LANG_CODES.get(lang, "hi")
        ref_wav   = self._get_xtts_ref(lang)
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            if ref_wav:
                self._xtts_model.tts_to_file(
                    text=text,
                    speaker_wav=ref_wav,
                    language=xtts_lang,
                    file_path=output_path,
                )
            else:
                # No reference wav — use built-in speaker
                speakers = getattr(self._xtts_model, "speakers", None) or []
                speaker  = speakers[0] if speakers else None
                self._xtts_model.tts_to_file(
                    text=text,
                    speaker=speaker,
                    language=xtts_lang,
                    file_path=output_path,
                )
            # Verify output is valid audio
            if Path(output_path).exists() and Path(output_path).stat().st_size > 1000:
                wav, sr = sf.read(output_path, dtype="float32")
                if len(wav) / sr > 0.3:
                    wav = _post_process(wav, sr, is_mms=False)
                    sf.write(output_path, wav, sr)
                    return True
        except Exception as e:
            log.error(f"XTTS-v2 [{lang}] failed: {e}")
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
    def synthesize(self, text: str, lang: str, output_path: str,
                   speaker_wav: str = None) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        parler_text = self._normalize_text_for_tts(text, lang, for_mms=False)
        if self._synthesize_parler(parler_text, lang, output_path):
            return output_path
        if self._synthesize_standalone_vits(text, lang, output_path):
            return output_path
        mms_text = self._normalize_text_for_tts(text, lang, for_mms=True)
        if self._synthesize_mms_batch([mms_text], lang, [output_path])[0]:
            return output_path
        if self._synthesize_xtts(text, lang, output_path):
            log.info(f"XTTS-v2 used [{LANG_NAMES.get(lang, lang)}]")
            return output_path
        self._write_silence(2.0, output_path)
        log.warning(f"All TTS engines failed [{LANG_NAMES.get(lang, lang)}] — silence written")
        return output_path

    def synthesize_segments(self, segments: list[dict], lang: str,
                            output_dir: str, speaker_wav: str = None) -> list[dict]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        results    = [{**seg, "audio_path": str(out_dir / f"seg_{seg['id']:04d}.wav")}
                      for seg in segments]
        text_idxs  = [i for i, s in enumerate(segments) if s.get("text", "").strip()]
        empty_idxs = [i for i in range(len(segments)) if i not in text_idxs]

        for i in empty_idxs:
            seg = segments[i]
            self._write_silence(
                max(0.1, seg.get("end", 0) - seg.get("start", 0)),
                results[i]["audio_path"])

        if not text_idxs:
            return results

        # Parler-TTS batch
        # _PARLER_SKIP_LANGS only applies to the mini checkpoint, not ai4bharat
        parler_skip = lang in _PARLER_SKIP_LANGS
        if not parler_skip and self._load_parler():
            failed = []
            BATCH  = 32  # A6000 48GB — large batch saturates GPU
            for batch_start in range(0, len(text_idxs), BATCH):
                bidxs  = text_idxs[batch_start:batch_start + BATCH]
                btexts = [self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=False) for i in bidxs]
                bpaths = [results[i]["audio_path"] for i in bidxs]
                desc   = self._build_description(lang)
                seed = self._LANG_SEEDS.get(lang, 42)
                desc_ids = self._parler_desc_tok(desc, return_tensors="pt").to(DEVICE)
                for bidx, text, path in zip(bidxs, btexts, bpaths):
                    for _oom_attempt in range(2):
                        try:
                            prompt_ids = self._parler_tokenizer(text, return_tensors="pt").to(DEVICE)
                            max_tok = self._calc_max_tokens(text)
                            torch.manual_seed(seed)
                            if torch.cuda.is_available():
                                torch.cuda.manual_seed_all(seed)
                            with torch.no_grad():
                                gen = self._parler_generate(desc_ids, prompt_ids, max_tok)
                            sr  = self._parler_model.config.sampling_rate
                            wav = gen.cpu().float().numpy().squeeze()
                            dur = len(wav) / sr
                            if dur < self._PARLER_MIN_DUR:
                                failed.append(bidx)
                                break
                            if np.max(np.abs(wav)) < 0.02:
                                failed.append(bidx)
                                break
                            wav = _post_process(wav, sr, is_mms=False)
                            Path(path).parent.mkdir(parents=True, exist_ok=True)
                            sf.write(path, wav, sr)
                            break  # success
                        except RuntimeError as e:
                            if "out of memory" in str(e).lower() and _oom_attempt == 0:
                                log.warning(f"Parler OOM seg {bidx} [{lang}] — clearing cache and retrying")
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()
                                continue
                            log.error(f"Parler seg {bidx} failed [{lang}]: {e}")
                            failed.append(bidx)
                            break
                        except Exception as e:
                            log.error(f"Parler seg {bidx} failed [{lang}]: {e}")
                            failed.append(bidx)
                            break
            text_idxs = failed

        # Standalone VITS — tried before MMS adapter for langs that have a native model
        # (doi, san, kas, snd, kok, mni). For kas/snd/kok/mni this avoids the wrong-language
        # MMS adapter. Falls through to MMS adapter if standalone model not downloaded.
        if text_idxs and lang in _MMS_STANDALONE_LANGS:
            still_failed = []
            for i in text_idxs:
                ok = self._synthesize_standalone_vits(
                    segments[i]["text"].strip(), lang, results[i]["audio_path"])
                if not ok:
                    still_failed.append(i)
            text_idxs = still_failed

        # MMS-TTS fallback for anything Parler/standalone missed
        if text_idxs:
            texts = [self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=True) for i in text_idxs]
            paths = [results[i]["audio_path"] for i in text_idxs]
            oks   = self._synthesize_mms_batch(texts, lang, paths)
            still_failed = [i for i, ok in zip(text_idxs, oks) if not ok]
            # XTTS-v2 fallback for anything MMS missed
            for i in still_failed:
                seg_text = self._normalize_text_for_tts(segments[i]["text"].strip(), lang, for_mms=False)
                if not self._synthesize_xtts(seg_text, lang, results[i]["audio_path"]):
                    self._write_silence(2.0, results[i]["audio_path"])

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
                try:
                    # transformers >= 4.40 has load_adapter
                    self._mms_model.load_adapter(str(MMS_DIR), adapter_code)
                except AttributeError:
                    # fallback for older transformers: manual safetensors load
                    import safetensors.torch as st
                    sf_path = MMS_DIR / f"adapter.{adapter_code}.safetensors"
                    bin_path = MMS_DIR / f"adapter.{adapter_code}.bin"
                    weights = (st.load_file(str(sf_path)) if sf_path.exists()
                               else torch.load(str(bin_path), map_location=DEVICE,
                                               weights_only=True))
                    # MMS adapter keys are prefixed with "vits." in the base model
                    model_sd = self._mms_model.state_dict()
                    matched = {k: v for k, v in weights.items() if k in model_sd}
                    if not matched:
                        # try adding common prefix
                        matched = {f"vits.{k}": v for k, v in weights.items()
                                   if f"vits.{k}" in model_sd}
                    if not matched:
                        log.error(f"MMS adapter keys unmatched for {lang} ({adapter_code})")
                        return False
                    model_sd.update(matched)
                    self._mms_model.load_state_dict(model_sd, strict=False)
                self._mms_processor.set_target_lang(adapter_code)
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
                w = out.waveform[0].cpu().float().numpy().squeeze()
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
