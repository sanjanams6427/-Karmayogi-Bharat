# ============================================================
# Translation Module — Offline, Zero-cost
# Primary  : IndicTrans2 (local, all 22 Indian languages)
# Fallback : SeamlessM4T → NLLB-200
# No LLM, no internet, no API keys required.
# ============================================================

import threading
import torch
from pathlib import Path
from .lang_config import INDIC_TRANS2_CODES, SEAMLESS_CODES, SEAMLESS_S2ST_LANGS, NLLB_CODES, LANG_NAMES
from .logger import get_logger
from .retry import retry
from .quality import score_segment, review_summary

log = get_logger("translator")

# UI inference pinned to cuda:0 — fine-tuning runs on cuda:1/2/3 via FSDP
DEVICE       = "cuda:0" if torch.cuda.is_available() else "cpu"
SEAMLESS_DEV = "cuda:0" if torch.cuda.is_available() else "cpu"
NLLB_DEV     = "cuda:0" if torch.cuda.is_available() else "cpu"
MODELS_DIR  = Path(__file__).parent.parent / "models"


class Translator:
    def __init__(self):
        self._indic_trans2: dict = {}
        self._seamless = None
        self._nllb     = None
        self._load_lock = threading.Lock()
        log.info(f"Translator init | device={DEVICE} | mode=offline-only")

    # ----------------------------------------------------------
    # Lazy loaders
    # ----------------------------------------------------------
    def _load_indic_trans2(self, direction: str):
        if direction in self._indic_trans2:
            return self._indic_trans2[direction]
        with self._load_lock:
            if direction in self._indic_trans2:
                return self._indic_trans2[direction]
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            from IndicTransToolkit import IndicProcessor
            # Prefer fine-tuned checkpoint if it exists, fall back to base model
            ft_path   = MODELS_DIR.parent / "checkpoints" / "indictrans" / direction / "best"
            base_path = MODELS_DIR / "indic_tr" / direction
            path = str(ft_path) if ft_path.exists() else str(base_path)
            log.info(f"Loading IndicTrans2 ({direction}) from {'fine-tuned' if ft_path.exists() else 'base'} on {DEVICE}")
            tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            model = AutoModelForSeq2SeqLM.from_pretrained(
                path, trust_remote_code=True, low_cpu_mem_usage=False,
            )
            model = model.to(dtype=dtype).to(DEVICE)
            model.eval()
            processor = IndicProcessor(inference=True)
            self._indic_trans2[direction] = {
                "tokenizer": tokenizer, "model": model, "processor": processor
            }
        return self._indic_trans2[direction]

    def _load_seamless(self):
        if self._seamless is None:
            from transformers import AutoProcessor, SeamlessM4Tv2Model
            path = str(MODELS_DIR / "seamless")
            log.info(f"Loading SeamlessM4T on {SEAMLESS_DEV}")
            seamless_model = SeamlessM4Tv2Model.from_pretrained(
                path, torch_dtype=torch.float16, low_cpu_mem_usage=False
            )
            self._seamless = {
                "processor": AutoProcessor.from_pretrained(path),
                "model": seamless_model.to(SEAMLESS_DEV),
            }
        return self._seamless

    def translate_speech_to_speech(
        self, audio_path: str, src_lang: str, tgt_lang: str, output_path: str
    ) -> bool:
        """
        SeamlessM4T S2ST: audio file → dubbed audio file in target language.
        Returns True on success. Falls back gracefully on unsupported lang pairs.
        """
        if src_lang not in SEAMLESS_CODES or tgt_lang not in SEAMLESS_CODES:
            log.warning(f"S2ST: {src_lang}/{tgt_lang} not in SEAMLESS_CODES — skipping")
            return False
        if src_lang not in SEAMLESS_S2ST_LANGS or tgt_lang not in SEAMLESS_S2ST_LANGS:
            log.warning(f"S2ST: {src_lang}/{tgt_lang} not in S2ST speech-output langs — skipping")
            return False
        try:
            import soundfile as sf
            import numpy as np
            engine    = self._load_seamless()
            processor = engine["processor"]
            model     = engine["model"]
            audio, sr = sf.read(audio_path, dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            inputs = processor(
                audios=audio, sampling_rate=sr,
                src_lang=SEAMLESS_CODES[src_lang],
                return_tensors="pt",
            ).to(SEAMLESS_DEV)
            inputs = {k: v.to(torch.float16) if v.is_floating_point() else v
                      for k, v in inputs.items()}
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    tgt_lang=SEAMLESS_CODES[tgt_lang],
                    generate_speech=True,
                )
            wav = out.waveform[0].cpu().float().numpy().squeeze()
            out_sr = model.config.sampling_rate if hasattr(model.config, "sampling_rate") else 16000
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, wav, out_sr)
            log.info(f"S2ST: {src_lang}→{tgt_lang} → {output_path}")
            return True
        except Exception as e:
            log.error(f"S2ST failed {src_lang}→{tgt_lang}: {e}")
            return False

    def _load_nllb(self):
        if self._nllb is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            path = str(MODELS_DIR / "nllb")
            log.info(f"Loading NLLB-200 on {NLLB_DEV}")
            self._nllb = {
                "tokenizer": AutoTokenizer.from_pretrained(path),
                "model": AutoModelForSeq2SeqLM.from_pretrained(
                    path, torch_dtype=torch.float16
                ).to(NLLB_DEV),
            }
        return self._nllb

    # ----------------------------------------------------------
    # Core engines (with retry)
    # ----------------------------------------------------------
    @retry(max_attempts=2, delay=1.0)
    def _translate_indic_trans2(self, text: str, src_lang: str, tgt_lang: str) -> str:
        return self._translate_indic_trans2_batch([text], src_lang, tgt_lang)[0]

    def _translate_indic_trans2_batch(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        direction = ("en_indic"    if src_lang == "eng_Latn" else
                     "indic_en"    if tgt_lang == "eng_Latn" else
                     "indic_indic")
        engine    = self._load_indic_trans2(direction)
        tokenizer = engine["tokenizer"]
        model     = engine["model"]
        processor = engine["processor"]
        batch  = processor.preprocess_batch(texts, src_lang=src_lang, tgt_lang=tgt_lang)
        inputs = tokenizer(
            batch, return_tensors="pt", padding=True,
            truncation=True, max_length=512
        )
        # Move to device first, then cast to model dtype
        model_dtype = next(model.parameters()).dtype
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        inputs = {k: v.to(dtype=model_dtype) if v.is_floating_point() else v
                  for k, v in inputs.items()}
        tgt_id = tokenizer.convert_tokens_to_ids(tgt_lang)
        with torch.no_grad():
            output = model.generate(
                **inputs, forced_bos_token_id=tgt_id,
                max_new_tokens=512, num_beams=5,
                no_repeat_ngram_size=3, repetition_penalty=1.2,
                use_cache=True, early_stopping=True,
            )
        decoded = tokenizer.batch_decode(output, skip_special_tokens=True)
        results = processor.postprocess_batch(decoded, lang=tgt_lang)
        return [t.strip() for t in results]

    @retry(max_attempts=2, delay=2.0)
    def _translate_seamless(self, text: str, src_code: str, tgt_code: str) -> str:
        engine    = self._load_seamless()
        processor = engine["processor"]
        model     = engine["model"]
        inputs    = processor(text=text, src_lang=src_code,
                              return_tensors="pt").to(SEAMLESS_DEV)
        inputs    = {k: v.to(torch.float16) if v.is_floating_point() else v
                     for k, v in inputs.items()}
        with torch.no_grad():
            output = model.generate(**inputs, tgt_lang=tgt_code,
                                    generate_speech=False, num_beams=5,
                                    no_repeat_ngram_size=4, repetition_penalty=1.3)
        return processor.decode(output.sequences[0], skip_special_tokens=True).strip()

    @retry(max_attempts=2, delay=2.0)
    def _translate_nllb(self, text: str, src_code: str, tgt_code: str) -> str:
        engine    = self._load_nllb()
        tokenizer = engine["tokenizer"]
        model     = engine["model"]
        tokenizer.src_lang = src_code
        inputs = tokenizer(text, return_tensors="pt",
                           truncation=True, max_length=512).to(NLLB_DEV)
        tgt_id = tokenizer.convert_tokens_to_ids(tgt_code)
        with torch.no_grad():
            output = model.generate(**inputs, forced_bos_token_id=tgt_id,
                                    max_new_tokens=512, num_beams=5,
                                    no_repeat_ngram_size=4, repetition_penalty=1.3)
        return tokenizer.decode(output[0], skip_special_tokens=True).strip()

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------
    def translate(self, text: str, src_lang: str, tgt_lang: str,
                  glossary=None, detected_lang: str = None) -> dict:
        """
        Returns: {"text": str, "engine": str, "score": dict}
        detected_lang: per-segment detected language (overrides src_lang for routing)
        """
        # Use detected language for routing if available and different from assumed
        effective_src = detected_lang if detected_lang else src_lang
        if effective_src != src_lang:
            log.info(f"Lang override: assumed={src_lang} detected={effective_src}")
        src_lang = effective_src

        if src_lang == tgt_lang:
            return {"text": text, "engine": "passthrough", "enhanced": False,
                    "score": {"score": 1.0, "flags": [],
                              "needs_review": False, "failed": False}}

        src_name = LANG_NAMES.get(src_lang, src_lang)
        tgt_name = LANG_NAMES.get(tgt_lang, tgt_lang)

        # Glossary: do NOT protect terms before translation for non-Latin scripts
        # (placeholders get corrupted by the model into "_ _ GLOSS _ N _" patterns)
        # Instead apply glossary only as post-processing after translation.
        work_text = text
        placeholder_map = {}

        translated  = None
        engine_used = None

        # Low-resource langs: always route through Hindi pivot for best quality.
        # Covers both indic→indic AND eng→low-resource (eng→hin→tgt).
        _PIVOT_LANGS = {"bod", "doi", "kas", "kok", "mni", "sat", "snd"}
        use_pivot = (
            (src_lang in _PIVOT_LANGS or tgt_lang in _PIVOT_LANGS)
            and src_lang != "hin" and tgt_lang != "hin"
        )

        # kok: IndicTrans2 rejects gom_Deva tag in this build — force NLLB
        # nep: Seamless uses npi code, IndicTrans2 npi_Deva works but NLLB is more reliable
        _NLLB_ONLY = {"kok"}
        force_nllb = src_lang in _NLLB_ONLY or tgt_lang in _NLLB_ONLY

        # 1. IndicTrans2 — primary (skip for kok/nep: rejected by this model build)
        if not force_nllb and src_lang in INDIC_TRANS2_CODES and tgt_lang in INDIC_TRANS2_CODES:
            try:
                if use_pivot:
                    translated  = self._pivot_via_hindi(work_text, src_lang, tgt_lang)
                else:
                    translated  = self._translate_indic_trans2(
                        work_text,
                        INDIC_TRANS2_CODES[src_lang],
                        INDIC_TRANS2_CODES[tgt_lang])
                engine_used = "indictrans2"
            except Exception as e:
                log.warning(f"IndicTrans2 failed {src_name}\u2192{tgt_name}: {e}")

        # 2. SeamlessM4T fallback (skip for Konkani — not in SEAMLESS_CODES anyway)
        if translated is None and not force_nllb and \
                src_lang in SEAMLESS_CODES and tgt_lang in SEAMLESS_CODES:
            try:
                translated  = self._translate_seamless(
                    work_text,
                    SEAMLESS_CODES[src_lang],
                    SEAMLESS_CODES[tgt_lang])
                engine_used = "seamless"
            except Exception as e:
                log.warning(f"SeamlessM4T failed {src_name}\u2192{tgt_name}: {e}")

        # 3. NLLB-200 — final fallback, also primary for Konkani
        if translated is None and \
                src_lang in NLLB_CODES and tgt_lang in NLLB_CODES:
            try:
                translated  = self._translate_nllb(
                    work_text,
                    NLLB_CODES[src_lang],
                    NLLB_CODES[tgt_lang])
                engine_used = "nllb"
            except Exception as e:
                log.warning(f"NLLB failed {src_name}\u2192{tgt_name}: {e}")

        if translated is None:
            raise RuntimeError(
                f"All translation engines failed: {src_name} → {tgt_name}")

        # Glossary: apply post-translation only (no placeholder restore needed)
        if glossary:
            translated = glossary.apply(text, src_lang, tgt_lang, translated)

        quality = score_segment(text, translated, src_lang, tgt_lang)
        log.info(f"[{engine_used}] {src_name}→{tgt_name} "
                 f"score={quality['score']} flags={quality['flags']}")

        return {"text": translated, "engine": engine_used, "enhanced": False, "score": quality}

    def translate_text(self, text: str, src_lang: str, tgt_lang: str,
                       glossary=None, detected_lang: str = None) -> str:
        return self.translate(text, src_lang, tgt_lang, glossary=glossary,
                              detected_lang=detected_lang)["text"]

    def translate_batch(self, texts: list[str], src_lang: str, tgt_lang: str,
                        glossary=None, detected_langs: list[str] = None) -> list[dict]:
        _PIVOT_LANGS = {"bod", "doi", "kas", "kok", "mni", "sat", "snd"}
        _NLLB_ONLY   = {"kok"}
        needs_pivot  = (
            (src_lang in _PIVOT_LANGS or tgt_lang in _PIVOT_LANGS)
            and src_lang != "hin" and tgt_lang != "hin"
        )
        force_nllb = src_lang in _NLLB_ONLY or tgt_lang in _NLLB_ONLY

        # True GPU batch for IndicTrans2 — all langs except pivot/nllb-only
        if (not needs_pivot and not force_nllb
                and src_lang in INDIC_TRANS2_CODES
                and tgt_lang in INDIC_TRANS2_CODES):
            try:
                work_texts       = texts
                if glossary:
                    pass  # no pre-protection; apply glossary post-translation
                translated_list = self._translate_indic_trans2_batch(
                    work_texts, INDIC_TRANS2_CODES[src_lang], INDIC_TRANS2_CODES[tgt_lang])
                results = []
                for i, (orig, trans) in enumerate(zip(texts, translated_list)):
                    t = trans.strip()
                    if glossary:
                        t = glossary.apply(orig, src_lang, tgt_lang, t)
                    q = score_segment(orig, t, src_lang, tgt_lang)
                    results.append({"text": t, "engine": "indictrans2", "enhanced": False, "score": q})
                summary = review_summary([r["score"] for r in results])
                log.info(f"Batch [{tgt_lang}] {len(texts)} segs | "
                         f"avg_score={summary['avg_score']} "
                         f"needs_review={summary['needs_review']}/{summary['total']}")
                return results
            except Exception as e:
                log.warning(f"Batch IndicTrans2 failed, falling back to per-segment: {e}")

        # Pivot langs or fallback: per-segment
        results = [
            self.translate(t, src_lang, tgt_lang, glossary=glossary,
                           detected_lang=(detected_langs[i] if detected_langs else None))
            for i, t in enumerate(texts)
        ]
        summary = review_summary([r["score"] for r in results])
        log.info(f"Batch [{tgt_lang}] {len(texts)} segs | "
                 f"avg_score={summary['avg_score']} "
                 f"needs_review={summary['needs_review']}/{summary['total']}")
        return results

    def _pivot_via_hindi(self, text: str, src_lang: str, tgt_lang: str) -> str:
        # Step 1: src → Hindi (skip if src is already Hindi or English going direct)
        if src_lang == "hin":
            mid = text
        else:
            mid = self._translate_indic_trans2(
                text, INDIC_TRANS2_CODES[src_lang], INDIC_TRANS2_CODES["hin"])
        # Step 2: Hindi → tgt (skip if tgt is Hindi)
        if tgt_lang == "hin":
            return mid
        return self._translate_indic_trans2(
            mid, INDIC_TRANS2_CODES["hin"], INDIC_TRANS2_CODES[tgt_lang])
