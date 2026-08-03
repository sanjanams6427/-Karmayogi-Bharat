# ============================================================
# Voice Cloning Module
# Uses Coqui XTTS-v2 to clone a speaker's voice from a
# reference audio sample and synthesize dubbed speech.
# Meets KB tender "with voice cloning" pricing tier.
# All processing is local — no cloud API.
# ============================================================

import torch
import numpy as np
import soundfile as sf
from pathlib import Path
from .lang_config import LANG_NAMES
from .logger import get_logger

log    = get_logger("voice_clone")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# XTTS-v2 supported languages for Indian languages
XTTS_LANG_MAP = {
    "hin": "hi", "ben": "bn", "guj": "gu", "mar": "mr",
    "tam": "ta", "tel": "te", "kan": "kn", "mal": "ml",
    "pan": "pa", "urd": "ur",
}


class VoiceCloner:
    """
    Clones a speaker's voice from a reference audio clip and
    synthesizes new speech in the target language using that voice.

    Usage:
        cloner = VoiceCloner()
        cloner.synthesize_with_clone(
            text="नमस्ते",
            lang="hin",
            reference_audio="speaker_sample.wav",
            output_path="output.wav"
        )
    """

    def __init__(self):
        self._xtts = None

    def _load_xtts(self):
        if self._xtts is None:
            try:
                from TTS.api import TTS
                log.info("Loading Coqui XTTS-v2")
                self._xtts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
                log.info("XTTS-v2 loaded")
            except Exception as e:
                log.error(f"XTTS-v2 load failed: {e}")
                self._xtts = "unavailable"
        return self._xtts

    def is_supported(self, lang: str) -> bool:
        return lang in XTTS_LANG_MAP

    def extract_speaker_embedding(self, reference_audio: str) -> dict:
        """
        Extract speaker embedding from a reference audio file.
        reference_audio: path to .wav file (min 6 seconds recommended)
        Returns: dict with embedding tensors for reuse across segments.
        """
        model = self._load_xtts()
        if model == "unavailable":
            raise RuntimeError("XTTS-v2 not available for speaker embedding extraction")
        try:
            gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(
                audio_path=[reference_audio]
            )
            return {
                "gpt_cond_latent": gpt_cond_latent,
                "speaker_embedding": speaker_embedding,
                "reference_audio": reference_audio,
            }
        except Exception as e:
            raise RuntimeError(f"[VoiceClone] Embedding extraction failed: {e}")

    def synthesize_with_clone(
        self,
        text: str,
        lang: str,
        reference_audio: str,
        output_path: str,
        speaker_embedding: dict = None,
    ) -> str:
        """
        Synthesize speech in target language using cloned voice.

        text: translated text to speak
        lang: 3-letter target language code
        reference_audio: path to source speaker's audio sample
        output_path: where to save the synthesized audio
        speaker_embedding: pre-computed embedding dict (optional, for speed)
        """
        lang_name = LANG_NAMES.get(lang, lang)
        xtts_lang = XTTS_LANG_MAP.get(lang)

        if not xtts_lang:
            raise ValueError(
                f"[VoiceClone] {lang_name} not supported by XTTS-v2. "
                f"Supported: {list(XTTS_LANG_MAP.keys())}"
            )

        model = self._load_xtts()
        if model == "unavailable":
            raise RuntimeError("[VoiceClone] XTTS-v2 not available")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            if speaker_embedding:
                # Use pre-computed embedding (faster for batch processing)
                out = model.inference(
                    text=text,
                    language=xtts_lang,
                    gpt_cond_latent=speaker_embedding["gpt_cond_latent"],
                    speaker_embedding=speaker_embedding["speaker_embedding"],
                )
                sf.write(output_path, np.array(out["wav"]), 24000)
            else:
                # Extract embedding on the fly
                model.tts_to_file(
                    text=text,
                    language=xtts_lang,
                    speaker_wav=reference_audio,
                    file_path=output_path,
                )
            return output_path
        except Exception as e:
            raise RuntimeError(f"[VoiceClone] Synthesis failed for {lang_name}: {e}")

    def synthesize_segments_with_clone(
        self,
        segments: list[dict],
        lang: str,
        reference_audio: str,
        output_dir: str,
    ) -> list[dict]:
        """
        Synthesize all segments using cloned voice.
        Pre-computes speaker embedding once for efficiency.
        """
        # Pre-compute embedding once for all segments
        embedding = self.extract_speaker_embedding(reference_audio)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for seg in segments:
            out_path = str(out_dir / f"seg_{seg['id']:04d}.wav")
            self.synthesize_with_clone(
                text=seg["text"],
                lang=lang,
                reference_audio=reference_audio,
                output_path=out_path,
                speaker_embedding=embedding,
            )
            results.append({**seg, "audio_path": out_path})
        return results
