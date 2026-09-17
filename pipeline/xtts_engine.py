# ============================================================
# XTTS-v2 engine (Coqui) — natural, neutral-tone Indic TTS
#
# Isolated in its own module so a missing/broken Coqui `TTS` install can never
# break `pipeline.tts` import. All heavy imports are lazy (inside methods), and
# every failure path returns False so the caller falls back to Parler cleanly.
#
# Enable by:
#   1. pip install coqui-tts        (maintained fork of the archived `TTS`)
#   2. download XTTS-v2 weights to models/xtts_v2/  (see scripts/download_models)
#   3. optionally place a reference voice clip at assets/xtts_refs/<lang>.wav
# ============================================================

import os
from pathlib import Path
import numpy as np
import soundfile as sf

from .logger import get_logger

log = get_logger("xtts")

MODELS_DIR = Path(__file__).parent.parent / "models"
XTTS_DIR   = MODELS_DIR / "xtts_v2"
REFS_DIR   = Path(__file__).parent.parent / "assets" / "xtts_refs"

SR = 44100  # pipeline target sample rate

# XTTS-v2 language codes (subset relevant to this pipeline).
_XTTS_LANG = {
    "hin": "hi",
    # XTTS-v2 also supports a few others, but we scope this to what we route.
}

# Languages we route through XTTS-v2 (primary). Kept small and explicit.
XTTS_LANGS = {"hin"}


def xtts_available() -> bool:
    """True only if the Coqui TTS library AND the XTTS-v2 model dir are present.
    Cheap check (no model load) — used for routing decisions."""
    try:
        import importlib.util
        if importlib.util.find_spec("TTS") is None:
            return False
    except Exception:
        return False
    return XTTS_DIR.exists()


class XTTSEngine:
    """Thin wrapper around Coqui XTTS-v2. One model instance, reused across calls.
    A fixed reference clip per language gives a consistent speaker; without a
    clip, XTTS uses its built-in default speaker latents."""

    def __init__(self, device: str | None = None):
        self._model = None
        self._loaded = False
        self._load_failed = False
        self._device = device or os.environ.get("TTS_DEVICE") or "cpu"
        self._speaker_cache: dict = {}

    def _load(self) -> bool:
        if self._loaded:
            return True
        if self._load_failed:
            return False
        try:
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import Xtts
            import torch
            cfg_path = XTTS_DIR / "config.json"
            if not cfg_path.exists():
                log.warning(f"XTTS config not found at {cfg_path} — cannot load")
                self._load_failed = True
                return False
            config = XttsConfig()
            config.load_json(str(cfg_path))
            model = Xtts.init_from_config(config)
            model.load_checkpoint(config, checkpoint_dir=str(XTTS_DIR), eval=True)
            dev = self._device
            try:
                if dev.startswith("cuda") and torch.cuda.is_available():
                    model = model.to(dev)
                else:
                    dev = "cpu"
            except Exception as _e:
                log.warning(f"XTTS to({dev}) failed ({_e}) — using CPU")
                dev = "cpu"
                model = model.to("cpu")
            self._model = model
            self._device = dev
            self._loaded = True
            log.info(f"XTTS-v2 loaded on {dev}")
            return True
        except Exception as e:
            log.error(f"XTTS-v2 load failed: {e}")
            self._load_failed = True
            return False

    def _speaker_latents(self, lang: str):
        """Compute (gpt_cond_latent, speaker_embedding) once per language from a
        reference clip if present; cache for consistency across all segments."""
        if lang in self._speaker_cache:
            return self._speaker_cache[lang]
        ref = REFS_DIR / f"{lang}.wav"
        ref_paths = [str(ref)] if ref.exists() else None
        try:
            if ref_paths:
                gpt_cond_latent, speaker_embedding = \
                    self._model.get_conditioning_latents(audio_path=ref_paths)
            else:
                # No reference clip — use the model's default built-in speaker.
                # get_conditioning_latents requires audio; fall back to the
                # config's default speaker if available.
                speakers = getattr(self._model, "speaker_manager", None)
                if speakers and getattr(speakers, "speakers", None):
                    name = next(iter(speakers.speakers))
                    gpt_cond_latent, speaker_embedding = \
                        speakers.speakers[name]["gpt_cond_latent"], \
                        speakers.speakers[name]["speaker_embedding"]
                else:
                    log.warning(f"XTTS [{lang}] has no reference clip and no default "
                                f"speaker — provide assets/xtts_refs/{lang}.wav")
                    self._speaker_cache[lang] = None
                    return None
            self._speaker_cache[lang] = (gpt_cond_latent, speaker_embedding)
            return self._speaker_cache[lang]
        except Exception as e:
            log.error(f"XTTS [{lang}] speaker latent computation failed: {e}")
            self._speaker_cache[lang] = None
            return None

    def synthesize(self, text: str, lang: str, output_path: str) -> bool:
        """Synthesize one segment with XTTS-v2. Returns True on success.
        Any failure returns False so the caller falls back to Parler."""
        if lang not in _XTTS_LANG:
            return False
        if not text or not text.strip():
            return False
        if not self._load():
            return False
        latents = self._speaker_latents(lang)
        if latents is None:
            return False
        gpt_cond_latent, speaker_embedding = latents
        try:
            out = self._model.inference(
                text=text,
                language=_XTTS_LANG[lang],
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                temperature=0.3,          # low = stable, neutral prosody
                repetition_penalty=2.0,
                enable_text_splitting=True,
            )
            wav = np.asarray(out["wav"], dtype=np.float32)
            native = 24000  # XTTS-v2 native sample rate
            if native != SR:
                from scipy.signal import resample as _resample
                wav = _resample(wav, int(len(wav) * SR / native)).astype(np.float32)
            # Peak-normalize to -3 dBFS (broadcast headroom).
            peak = float(np.max(np.abs(wav))) if len(wav) else 0.0
            if peak > 0.01:
                wav = wav * (0.708 / peak)
            if len(wav) / SR < 0.1:
                return False
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, wav, SR, subtype="PCM_16")
            return True
        except Exception as e:
            log.error(f"XTTS-v2 synth failed [{lang}]: {e}")
            return False
