# ============================================================
# TTS Engine — Offline, Zero-cost
# Primary  : Indic Parler-TTS — 21 langs, 44kHz, GPU batch
# Fallback : MMS-TTS — all 22 langs (Tamil primary)
# Last     : pyttsx3 system voices
# ============================================================

import os, subprocess, json
import torch
import numpy as np
import soundfile as sf
from pathlib import Path
from .lang_config import LANG_NAMES
from .logger import get_logger

log = get_logger(__name__)

DEVICE = (
    os.environ.get("TTS_DEVICE")
    or ("cuda:1" if torch.cuda.is_available() and torch.cuda.device_count() > 1 else
        "cuda:0" if torch.cuda.is_available() else "cpu")
)

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"

MODELS_DIR  = Path(__file__).parent.parent / "models"
PARLER_DIR  = MODELS_DIR / "indic_parler_tts"
FLAN_T5_DIR = MODELS_DIR / "flan_t5_large"
MMS_DIR     = MODELS_DIR / "mms"

SR = 44100  # target sample rate


def _is_ai4bharat_model() -> bool:
    """Detect if the downloaded Parler checkpoint is ai4bharat large (self-contained)
    vs parler-tts-mini (needs separate flan-t5 tokenizer)."""
    cfg = PARLER_DIR / "config.json"
    if not cfg.exists():
        return False
    try:
        c = json.loads(cfg.read_text(encoding="utf-8"))
        name = c.get("_name_or_path", "")
        return "ai4bharat" in name or "indic-parler" in name.lower()
    except Exception:
        return False


# Languages where Parler-TTS mini produces silence — route directly to MMS
# Empty: let Parler try all langs, fall back to MMS if output too short
_PARLER_SKIP_LANGS: set = set()

# Speaker descriptions for Parler-TTS mini
_PARLER_SPEAKERS = {
    "hin": ("Priya",     "Priya has a warm, clear female voice with perfect Hindi diction. She speaks at a slow, natural pace with proper intonation, crisp consonants, and clear pauses between words."),
    "ben": ("Ananya",    "Ananya has a clear, melodious female voice with authentic Bengali pronunciation. She speaks slowly and clearly at a natural pace with proper intonation and distinct syllables."),
    "tam": ("Kavitha",   "Kavitha has a very clear, slow, expressive female voice with authentic Tamil pronunciation and melodic intonation. She speaks slowly and deliberately, enunciating every syllable clearly."),
    "tel": ("Sravani",   "Sravani has a warm, clear female voice with authentic Telugu pronunciation. She speaks at a slow, natural pace with proper intonation and crisp, distinct syllables."),
    "kan": ("Deepa",     "Deepa has a clear, expressive female voice with authentic Kannada pronunciation and crisp consonants. She speaks slowly and clearly with natural pauses between phrases."),
    "mal": ("Anjali",    "Anjali has a clear, melodious female voice with authentic Malayalam pronunciation. She speaks slowly and naturally with proper intonation and distinct syllables."),
    "mar": ("Sneha",     "Sneha has a warm, clear female voice with authentic Marathi pronunciation. She speaks at a slow, natural pace with proper intonation and clear word boundaries."),
    "guj": ("Riya",      "Riya has a clear, expressive female voice with authentic Gujarati pronunciation. She speaks slowly and clearly with natural intonation and distinct syllables."),
    "pan": ("Harpreet",  "Harpreet has a warm, clear female voice with authentic Punjabi pronunciation. She speaks at a slow, natural pace with proper intonation and crisp consonants."),
    "ory": ("Sarita",    "Sarita has a clear, melodious female voice with authentic Odia pronunciation. She speaks slowly and clearly with natural intonation and distinct syllables."),
    "asm": ("Purnima",   "Purnima has a clear, expressive female voice with authentic Assamese pronunciation. She speaks slowly and naturally with proper intonation and clear pauses."),
    "urd": ("Zara",      "Zara has a warm, clear female voice with authentic Urdu pronunciation. She speaks slowly at a natural pace with proper intonation and crisp, distinct syllables."),
    "nep": ("Amrita",    "Amrita has a clear, melodious female voice with authentic Nepali pronunciation. She speaks slowly and clearly with natural intonation and distinct syllables."),
    "bod": ("Dolma",     "Dolma has a clear, expressive female voice with authentic Bodo pronunciation. She speaks slowly and naturally with proper intonation and clear word boundaries."),
    "doi": ("Reena",     "Reena has a warm, clear female voice with authentic Dogri pronunciation. She speaks at a slow, natural pace with proper intonation and crisp consonants."),
    "kok": ("Sujata",    "Sujata has a clear, melodious female voice with authentic Konkani pronunciation. She speaks slowly and clearly with natural intonation and distinct syllables."),
    "mni": ("Sanatombi", "Sanatombi has a clear, expressive female voice with authentic Manipuri pronunciation. She speaks slowly and naturally with proper intonation and clear pauses."),
    "mai": ("Sunita",    "Sunita has a warm, clear female voice with authentic Maithili pronunciation. She speaks at a slow, natural pace with proper intonation and distinct syllables."),
    "san": ("Vedika",    "Vedika has a clear, precise female voice with authentic Sanskrit pronunciation and measured intonation. She speaks slowly and deliberately, enunciating every syllable."),
    "sat": ("Champa",    "Champa has a clear, expressive female voice with authentic Santhali pronunciation. She speaks slowly and naturally with proper intonation and clear word boundaries."),
    "snd": ("Nazia",     "Nazia has a warm, clear female voice with authentic Sindhi pronunciation. She speaks at a slow, natural pace with proper intonation and crisp consonants."),
    "kas": ("Rukhsar",   "Rukhsar has a clear, melodious female voice with authentic Kashmiri pronunciation. She speaks slowly and clearly with natural intonation and distinct syllables."),
    "eng": ("Aria",      "Aria has a clear, professional female voice with crisp English pronunciation. She speaks at a slow, natural pace with proper intonation and clear word boundaries."),
}
_PARLER_DESC_SUFFIX = " The recording is of very high quality, very close up, with no background noise."

# Speaker names for ai4bharat large model
_AI4BHARAT_SPEAKERS = {
    "hin": "Divya",    "ben": "Ananya",    "tam": "Kavitha",  "tel": "Sravani",
    "kan": "Deepa",    "mal": "Anjali",    "mar": "Sneha",    "guj": "Riya",
    "pan": "Harpreet", "ory": "Sarita",    "asm": "Purnima",  "urd": "Zara",
    "nep": "Amrita",   "mai": "Sunita",    "doi": "Reena",    "kas": "Rukhsar",
    "kok": "Sujata",   "mni": "Sanatombi", "sat": "Champa",   "snd": "Nazia",
    "bod": "Dolma",    "san": "Vedika",    "eng": "Aria",
}

# MMS-TTS adapter codes for all 22 languages
MMS_LANG_CODES = {
    "asm": "asm", "ben": "ben", "guj": "guj", "hin": "hin",
    "kan": "kan", "mal": "mal", "mar": "mar", "ory": "ory",
    "pan": "pan", "tam": "tam", "tel": "tel",
    "urd": "urd-script_arabic", "nep": "npi", "bod": "bod",
    "mai": "mai", "sat": "sat", "snd": "snd",
    "doi": "hin", "kas": "urd-script_arabic",
    "kok": "mar", "mni": "ben", "san": "hin",
}

# pyttsx3 last-resort lang tags
PYTTSX3_LANGS = {
    "hin": "hi", "ben": "bn", "guj": "gu", "mar": "mr",
    "tam": "ta", "tel": "te", "kan": "kn", "mal": "ml",
    "ory": "or", "pan": "pa", "asm": "as", "urd": "ur",
    "nep": "ne", "bod": "hi", "doi": "hi", "kas": "ur",
    "kok": "mr", "mni": "bn", "mai": "hi", "san": "hi",
    "sat": "hi", "snd": "ur",
}


def _post_process(audio: np.ndarray, sr: int = SR) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    # High-pass to remove DC/rumble
    sos   = butter(2, 60.0 / (sr / 2), btype="high", output="sos")
    audio = sosfilt(sos, audio).astype(np.float32)
    # Gentle low-pass to soften harshness (MMS/VITS can be shrill)
    sos_lp = butter(2, 7500.0 / (sr / 2), btype="low", output="sos")
    audio  = sosfilt(sos_lp, audio).astype(np.float32)
    peak  = np.max(np.abs(audio))
    if peak > 0.01:
        audio = audio * (0.891 / peak)
    return audio


class TTSEngine:
    _PARLER_MIN_DUR = 0.5  # seconds — shorter means silence/failure

    def __init__(self):
        self._parler_model     = None
        self._parler_tokenizer = None
        self._parler_desc_tok  = None
        self._mms_model        = None
        self._mms_processor    = None
        self._mms_current_lang = None
        self._ai4bharat        = None

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _is_ai4bharat(self) -> bool:
        if self._ai4bharat is None:
            self._ai4bharat = _is_ai4bharat_model()
        return self._ai4bharat

    def _build_description(self, lang: str) -> str:
        if self._is_ai4bharat():
            speaker = _AI4BHARAT_SPEAKERS.get(lang, "Divya")
            return f"{speaker}'s voice is clear and natural."
        speaker, desc = _PARLER_SPEAKERS.get(
            lang, ("Rohit", "Rohit speaks clearly and naturally at a moderate pace."))
        return desc + _PARLER_DESC_SUFFIX

    # ----------------------------------------------------------
    # Parler-TTS loader
    # ----------------------------------------------------------
    def _load_parler(self) -> bool:
        if self._parler_model is not None:
            return True
        if not PARLER_DIR.exists():
            log.warning("Parler-TTS model not found")
            return False
        needs_flan = not self._is_ai4bharat()
        if needs_flan and not FLAN_T5_DIR.exists():
            log.warning("flan_t5_large not found — Parler-TTS unavailable")
            return False
        try:
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
            import transformers
            transformers.logging.set_verbosity_error()
            log.info(f"Loading Parler-TTS ({'ai4bharat' if self._is_ai4bharat() else 'mini'})")
            self._parler_model = ParlerTTSForConditionalGeneration.from_pretrained(
                str(PARLER_DIR),
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                attn_implementation="eager",
            ).to(DEVICE).eval()
            self._parler_tokenizer = AutoTokenizer.from_pretrained(str(PARLER_DIR))
            desc_tok_src = str(PARLER_DIR) if self._is_ai4bharat() else str(FLAN_T5_DIR)
            self._parler_desc_tok = AutoTokenizer.from_pretrained(desc_tok_src)
            transformers.logging.set_verbosity_warning()
            log.info("Parler-TTS loaded")
            return True
        except Exception as e:
            log.error(f"Parler-TTS load failed: {e}")
            self._parler_model = None
            return False

    # ----------------------------------------------------------
    # Parler-TTS synthesis (single)
    # ----------------------------------------------------------
    def _synthesize_parler(self, text: str, lang: str, output_path: str) -> bool:
        # Only skip Tamil for mini checkpoint; ai4bharat large supports it
        if not self._is_ai4bharat() and lang in _PARLER_SKIP_LANGS:
            return False
        if not self._load_parler():
            return False
        try:
            desc       = self._build_description(lang)
            desc_ids   = self._parler_desc_tok(desc, return_tensors="pt").to(DEVICE)
            prompt_ids = self._parler_tokenizer(text, return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                gen = self._parler_model.generate(
                    input_ids=desc_ids.input_ids,
                    attention_mask=desc_ids.attention_mask,
                    prompt_input_ids=prompt_ids.input_ids,
                    prompt_attention_mask=prompt_ids.attention_mask,
                )
            wav = gen.cpu().numpy().squeeze().astype(np.float32)
            sr  = self._parler_model.config.sampling_rate
            if len(wav) / sr < self._PARLER_MIN_DUR:
                log.warning(f"Parler output too short [{lang}] — MMS fallback")
                return False
            wav = _post_process(wav, sr)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, wav, sr)
            return True
        except Exception as e:
            log.error(f"Parler synthesis failed [{lang}]: {e}")
            return False

    # ----------------------------------------------------------
    # pyttsx3 — last resort
    # ----------------------------------------------------------
    def _synthesize_pyttsx3(self, text: str, lang: str, output_path: str) -> bool:
        try:
            import pyttsx3
            engine   = pyttsx3.init()
            lang_tag = PYTTSX3_LANGS.get(lang, "hi")
            voices   = engine.getProperty("voices")
            matched  = next(
                (v for v in voices if lang_tag in (v.languages[0] if v.languages else "")), None)
            if matched:
                engine.setProperty("voice", matched.id)
            engine.setProperty("rate", 145)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            engine.stop()
            if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                try:
                    wav, sr = sf.read(output_path)
                    if len(wav) > 0:
                        sf.write(output_path, _post_process(wav.astype(np.float32), sr), sr)
                        return True
                except Exception:
                    pass
        except Exception as e:
            log.error(f"pyttsx3 failed [{lang}]: {e}")
        # pyttsx3 produced empty/invalid audio — write silence so pipeline continues
        self._write_silence(2.0, output_path)
        return True

    # ----------------------------------------------------------
    # Silence generator
    # ----------------------------------------------------------
    def _write_silence(self, duration: float, output_path: str):
        subprocess.run(
            [_FFMPEG, "-y", "-f", "lavfi",
             "-i", f"anullsrc=r={SR}:cl=mono",
             "-t", str(max(0.1, duration)), output_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def synthesize(self, text: str, lang: str, output_path: str,
                   speaker_wav: str = None) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if self._synthesize_parler(text, lang, output_path):
            return output_path
        if self._synthesize_mms_batch([text], lang, [output_path])[0]:
            return output_path
        if self._synthesize_pyttsx3(text, lang, output_path):
            log.warning(f"pyttsx3 fallback used [{LANG_NAMES.get(lang, lang)}]")
            return output_path
        raise RuntimeError(f"All TTS engines failed for {LANG_NAMES.get(lang, lang)}")

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
        parler_skip = not self._is_ai4bharat() and lang in _PARLER_SKIP_LANGS
        if not parler_skip and self._load_parler():
            failed = []
            BATCH  = 8
            for batch_start in range(0, len(text_idxs), BATCH):
                bidxs  = text_idxs[batch_start:batch_start + BATCH]
                btexts = [segments[i]["text"].strip() for i in bidxs]
                bpaths = [results[i]["audio_path"] for i in bidxs]
                desc   = self._build_description(lang)
                try:
                    desc_ids = self._parler_desc_tok(
                        [desc] * len(btexts), return_tensors="pt", padding=True).to(DEVICE)
                    prompt_ids = self._parler_tokenizer(
                        btexts, return_tensors="pt", padding=True).to(DEVICE)
                    with torch.no_grad():
                        gen = self._parler_model.generate(
                            input_ids=desc_ids.input_ids,
                            attention_mask=desc_ids.attention_mask,
                            prompt_input_ids=prompt_ids.input_ids,
                            prompt_attention_mask=prompt_ids.attention_mask,
                        )
                    sr = self._parler_model.config.sampling_rate
                    if gen.ndim == 3:
                        gen = gen.squeeze(1)
                    for j, (path, bidx) in enumerate(zip(bpaths, bidxs)):
                        wav = gen[j].cpu().float().numpy()
                        if len(wav) / sr < self._PARLER_MIN_DUR:
                            failed.append(bidx)
                            continue
                        wav = _post_process(wav, sr)
                        Path(path).parent.mkdir(parents=True, exist_ok=True)
                        sf.write(path, wav, sr)
                except Exception as e:
                    log.error(f"Parler batch failed: {e}")
                    failed.extend(bidxs)
            text_idxs = failed

        # MMS-TTS fallback for anything Parler missed
        # No batching needed — _synthesize_mms_batch now processes one-at-a-time
        if text_idxs:
            texts = [segments[i]["text"].strip() for i in text_idxs]
            paths = [results[i]["audio_path"] for i in text_idxs]
            oks   = self._synthesize_mms_batch(texts, lang, paths)
            for i, ok in zip(text_idxs, oks):
                if not ok:
                    self._synthesize_pyttsx3(
                        segments[i]["text"].strip(), lang, results[i]["audio_path"])

        return results

    # ----------------------------------------------------------
    # MMS-TTS — single shared model + per-lang adapter
    # ----------------------------------------------------------
    def _load_mms(self, lang: str) -> bool:
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
                    low_cpu_mem_usage=False,
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
                # VITS length_scale > 1.0 = slower speech (1.15 ≈ 15% slower, clearer)
                orig_length_scale = getattr(self._mms_model.config, "length_scale", 1.0)
                self._mms_model.config.length_scale = 1.15
                try:
                    with torch.no_grad():
                        out = self._mms_model(**inputs)
                finally:
                    self._mms_model.config.length_scale = orig_length_scale
                native = self._mms_model.config.sampling_rate
                w = out.waveform[0].cpu().float().numpy().squeeze()
                nz = np.where(np.abs(w) > 1e-5)[0]
                if len(nz) == 0:
                    continue
                w = w[:nz[-1] + 1]
                if native != SR:
                    import librosa
                    w = librosa.resample(w, orig_sr=native, target_sr=SR)
                w = _post_process(w, SR)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                sf.write(path, w, SR)
                results[i] = True
            except Exception as e:
                log.error(f"MMS [{lang}] seg {i} failed: {e}")
        return results

    def get_audio_duration(self, audio_path: str) -> float:
        return sf.info(audio_path).duration
