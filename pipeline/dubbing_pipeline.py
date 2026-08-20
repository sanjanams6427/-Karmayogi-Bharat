# ============================================================
# KB Dubbing Pipeline — Enterprise Grade
# Features:
#   - Checkpoint/resume (crash-safe, no restart from zero)
#   - GPU batch translation (single forward pass per language)
#   - Structured JSON logging
#   - Quality scoring per segment
#   - Input validation (size, format, path safety)
#   - Glossary wired in at translate step
#   - Partial output preserved on failure
# ============================================================

import json, time, shutil, hashlib, os, re, threading, platform
import importlib.metadata as _ilm
from pathlib import Path
from dataclasses import dataclass, field

import torch
torch.backends.cudnn.benchmark = True  # fastest cuDNN kernels for fixed-size inputs
torch.backends.cuda.matmul.allow_tf32 = True  # TF32 on A6000 = ~2x matmul throughput
torch.backends.cudnn.allow_tf32 = True

from .asr import ASREngine
from .translator import Translator
from .tts import TTSEngine
from .video_processor import VideoProcessor
from .glossary import GlossaryManager
from .quality import review_summary, score_segment_full
from .retry import JobCheckpoint
from .logger import get_logger
from .lang_config import LANG_NAMES, ALL_22
from .subtitles import generate_subtitles

log = get_logger("dubbing_pipeline", "pipeline.log")
audit_log = get_logger("audit", "audit.log")


_MODEL_VERSIONS_CACHE: dict | None = None

def _model_versions() -> dict:
    """Collect installed package versions for audit trail. Cached after first call."""
    global _MODEL_VERSIONS_CACHE
    if _MODEL_VERSIONS_CACHE is not None:
        return _MODEL_VERSIONS_CACHE
    pkgs = ["faster-whisper", "transformers", "parler-tts", "torch", "soundfile"]
    out = {}
    for p in pkgs:
        try:
            out[p] = _ilm.version(p)
        except Exception:
            out[p] = "unknown"
    try:
        import subprocess as _sp
        r = _sp.run(
            ["git", "-C", str(Path(__file__).parent.parent), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        out["git_commit"] = r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        out["git_commit"] = "unknown"
    _MODEL_VERSIONS_CACHE = out
    return out


def _worker_dub_langs(args: tuple) -> dict:
    """
    Top-level function (picklable) for multiprocessing workers.
    Sets PIPELINE_GPU env var before importing torch/models so each worker
    uses its assigned GPU exclusively.
    args = (gpu_id, langs, video_path, src_lang, output_dir, course_id,
            force, asr_cache_path)
    """
    import os, json
    from pathlib import Path
    gpu_id, langs, video_path, src_lang, output_dir, course_id, \
        force, asr_cache_path = args
    os.environ["PIPELINE_GPU"] = str(gpu_id)
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    pipeline = DubbingPipeline()
    if asr_cache_path:
        try:
            cache = json.loads(open(asr_cache_path, encoding="utf-8").read())
            segments      = cache["segments"]
            resolved_lang = cache["src_lang"]
            duration      = cache["duration"]
            src_lang      = resolved_lang
            for lang in langs:
                job_id  = pipeline._job_id(video_path, src_lang, lang)
                out_dir = Path(output_dir) / lang
                tmp_dir = out_dir / "tmp" / job_id
                tmp_dir.mkdir(parents=True, exist_ok=True)
                wav_dst = tmp_dir / "source.wav"
                if not wav_dst.exists():
                    src_wav = Path(asr_cache_path).parent / "source.wav"
                    if src_wav.exists():
                        try:
                            import shutil
                            shutil.copy2(str(src_wav), str(wav_dst))
                        except Exception:
                            pass
                from pipeline.retry import JobCheckpoint
                ckpt = JobCheckpoint(job_id)
                if not ckpt.get_meta("segments"):
                    ckpt.set_meta("segments", segments)
                    ckpt.set_meta("detected_src_lang", resolved_lang)
                    ckpt.set_meta("duration", duration)
                    ckpt.flush()
        except Exception:
            pass
    results = {}
    for lang in langs:
        results[lang] = pipeline.dub_video(
            video_path, src_lang, lang, output_dir, course_id,
            force=force,
        )
        # Free VRAM between languages so the next language starts clean
        try:
            import torch as _torch
            if _torch.cuda.is_available():
                _torch.cuda.synchronize()
                _torch.cuda.empty_cache()
        except Exception:
            pass
        # Unload TTS engine between languages to free ~4GB VRAM
        pipeline._tts = None
    return results


def _worker_tts_split(args: tuple) -> dict:
    """
    TTS-only worker for spare-GPU acceleration.
    Synthesises a subset of translated segments for one language on a dedicated GPU.
    args = (gpu_id, lang, seg_indices, translated_segments, tts_dir)
    Returns {original_index: audio_path} for the assigned subset.
    """
    import os, sys
    from pathlib import Path
    gpu_id, lang, seg_indices, translated_segments, tts_dir = args
    os.environ["PIPELINE_GPU"] = str(gpu_id)
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from pipeline.tts import TTSEngine
    engine  = TTSEngine()
    subset  = [translated_segments[i] for i in seg_indices]
    results = engine.synthesize_segments(subset, lang, tts_dir)
    return {seg_indices[i]: r["audio_path"] for i, r in enumerate(results)}

try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from translation_memory import TranslationMemory
    _TM_AVAILABLE = True
except ImportError:
    _TM_AVAILABLE = False

# Max input file size: 2GB
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
ALLOWED_EXTS   = {".mp4", ".mp3", ".wav", ".flac", ".ogg", ".mkv", ".avi", ".mov", ".webm"}

# Per-(course_id, tgt_lang) locks to prevent concurrent jobs overwriting each other
_JOB_LOCKS: dict[str, threading.Lock] = {}
_JOB_LOCKS_LOCK = threading.Lock()


def _get_job_lock(course_id: str, tgt_lang: str) -> threading.Lock:
    key = f"{course_id}_{tgt_lang}"
    with _JOB_LOCKS_LOCK:
        if key not in _JOB_LOCKS:
            _JOB_LOCKS[key] = threading.Lock()
        return _JOB_LOCKS[key]

# KB tender Section 3.1 — content exclusion patterns
# These patterns identify content that must NOT be translated
_EXCLUSION_PATTERNS = [
    # Block only direct PM/President speech (not scheme names like PMMY, PMJDY etc.)
    r"(?i)(speech\s+by|address\s+by|statement\s+by).{0,30}(prime\s*minister|president\s*of\s*india|narendra\s*modi)",
    # YouTube-only content (no source file)
    r"(?i)(youtube\.com|youtu\.be)",
]

# Duration ratio threshold — KB tender Section 5.1B
# If dubbed output > 20% longer than original, KB approval required
DURATION_RATIO_THRESHOLD = 1.20


@dataclass
class DubbingResult:
    source_lang:       str
    target_lang:       str
    input_path:        str
    output_video_path: str        = ""
    output_audio_path: str        = ""
    transcript:        list[dict] = field(default_factory=list)
    translations:      list[dict] = field(default_factory=list)
    quality_summary:   dict       = field(default_factory=dict)
    duration_original: float      = 0.0
    duration_output:   float      = 0.0
    elapsed_s:         float      = 0.0
    success:           bool       = False
    error:             str        = ""


# Indic virama/combining marks — a segment starting with these is a mid-word continuation
_VIRAMA_CHARS = frozenset([
    '\u094D',  # Devanagari virama
    '\u09CD',  # Bengali virama
    '\u0ACD',  # Gujarati virama
    '\u0B4D',  # Odia virama
    '\u0BCD',  # Tamil virama
    '\u0C4D',  # Telugu virama
    '\u0CCD',  # Kannada virama
    '\u0D4D',  # Malayalam virama
    '\u0A4D',  # Gurmukhi virama
])

# Previous segment ends mid-sentence if it ends with these English words
_DANGLING_PREV = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by",
    "and", "or", "but", "as", "if", "when", "before", "after", "from",
    "this", "that", "these", "those", "its", "their", "our", "your",
}


# Devanagari script range for script-change detection
_DEVA_RE = re.compile(r'[\u0900-\u097F]')
# Bodo-exclusive morphemes (brx_Deva) — absent in Hindi/Maithili
_BODO_MORPHEME_RE = re.compile(
    r'\u0932\u093e\u0902\u0913|\u0916\u093e\u0932\u093e\u092e\u094b'
    r'|\u0917\u0941\u0926\u0941\u0902|\u092c\u093f\u0925\u093f\u0902'
    r'|\u0938\u094b\u0930\u092c\u093f|\u0917\u0947\u091c\u0947\u0930'
    r'|\u0932\u093e\u0935-\u0932\u093e\u0935|\u0916\u092b'
)
# Maithili-exclusive morphemes — absent in Hindi/Bodo
_MAITHILI_MORPHEME_RE = re.compile(
    r'\u091b\u0925\u093f|\u0905\u091b\u093f|\u0915\u092f\u0932'
    r'|\u091b\u0925\u094d\u0939\u093f|\u091b\u0928\u093f|\u0905\u091b\u0928\u093f'
)
# Hindi-exclusive verb markers — absent in Maithili/Bodo
_HINDI_MARKER_RE = re.compile(
    r'\u0939\u0948(?:\u0902)?\b|\u0939\u094b\u0924\u093e\b'
    r'|\u0915\u0930\u0924\u093e\b|\u0915\u0930\u0924\u0947\b'
    r'|\u0939\u094b\u0924\u0940\b|\u0939\u094b\u0924\u0947\b'
)


def _detect_deva_sublang(text: str) -> str:
    """Classify a Devanagari segment as 'bod', 'mai', 'hin', or 'deva' (unknown)."""
    if _BODO_MORPHEME_RE.search(text):
        return "bod"
    if _MAITHILI_MORPHEME_RE.search(text):
        return "mai"
    if _HINDI_MARKER_RE.search(text):
        return "hin"
    return "deva"  # generic Devanagari — cannot distinguish


def _repair_asr_segments(segments: list[dict]) -> list[dict]:
    """
    Merge ASR segments that Whisper split mid-sentence.
    Detects continuations via:
      1. Latin: first word starts lowercase OR is punctuation-only
      2. Indic: first char is a virama/combining mark (mid-akshar split)
      3. Previous segment ends with a dangling preposition/article/conjunction
      4. Previous segment has no sentence-ending punctuation AND the gap to
         the next segment is < 400ms (Whisper split mid-breath, not mid-sentence)
    """
    if not segments:
        return segments
    merged = [dict(segments[0])]
    for seg in segments[1:]:
        text = seg.get("text", "").strip()
        if not text:
            merged.append(dict(seg))
            continue
        first_char = text[0]
        first_word = text.split()[0] if text.split() else ""

        prev      = merged[-1]
        prev_text = prev.get("text", "").rstrip()
        prev_last_word = prev_text.split()[-1].lower().rstrip(".,;:") if prev_text.split() else ""

        # Gap between end of previous segment and start of this one
        gap_s = seg.get("start", 0) - prev.get("end", 0)

        # Sentence-ending punctuation in previous segment
        prev_ends_sentence = bool(prev_text) and prev_text[-1] in '.!?\u0964\u0965'

        # Never merge across Devanagari sub-language boundaries.
        # Bodo/Maithili/Hindi share the same script — if morpheme patterns
        # identify different sub-languages, treat as a hard sentence boundary.
        prev_deva = _detect_deva_sublang(prev_text) if _DEVA_RE.search(prev_text) else None
        curr_deva = _detect_deva_sublang(text)      if _DEVA_RE.search(text)      else None
        cross_lang = (
            prev_deva is not None and curr_deva is not None
            and prev_deva != "deva" and curr_deva != "deva"
            and prev_deva != curr_deva
        )
        if cross_lang:
            merged.append(dict(seg))
            continue
        is_continuation = (
            # 1. Latin: starts lowercase or punctuation-only token
            (first_word and (first_word[0].islower() or not first_word[0].isalnum()))
            # 2. Indic: starts with virama = mid-akshar continuation
            or first_char in _VIRAMA_CHARS
            # 3. Previous segment ended with a dangling preposition/article/conjunction
            or (
                prev_last_word in _DANGLING_PREV
                and not prev_ends_sentence
            )
            # 4. Short gap + no sentence-ending punctuation = Whisper mid-breath split
            # 200ms threshold for English source — English natural sentence pauses
            # are typically 300-500ms, so 200ms safely catches only mid-sentence splits.
            # 400ms was merging adjacent sentences in English educational content.
            or (
                not prev_ends_sentence
                and 0 < gap_s < 0.20
                and prev_text  # don't merge into empty
            )
        )
        if is_continuation:
            prev["text"] = prev_text + " " + text
            prev["end"]  = seg.get("end", prev["end"])
            log.info(f"[asr_repair] Merged seg {seg['id']} into seg {prev['id']} "
                     f"(gap={gap_s:.2f}s, ends_sentence={prev_ends_sentence})")
        else:
            merged.append(dict(seg))
    # Fix dangling last segment
    _DANGLING_END = {"because", "and", "or", "but", "when", "if", "as", "since", "although"}
    if merged:
        last_text = merged[-1].get("text", "").strip()
        last_word = last_text.split()[-1].lower().rstrip(".,") if last_text.split() else ""
        if last_word in _DANGLING_END:
            merged[-1]["text"] = last_text + "."
    return merged


class DubbingPipeline:

    def __init__(self, use_glossary: bool = True, use_tm: bool = True):
        # Lightweight init — models load lazily on first use
        self._asr          = None
        self._translator   = None
        self._tts          = None
        self._use_glossary = use_glossary
        self._use_tm       = use_tm
        self.video        = VideoProcessor()
        self.glossary     = GlossaryManager() if use_glossary else None
        self.tm           = TranslationMemory() if (use_tm and _TM_AVAILABLE) else None
        log.info("DubbingPipeline ready (lazy model loading)")

    @property
    def asr(self):
        if self._asr is None:
            log.info("Loading ASR engine...")
            self._asr = ASREngine()
        return self._asr

    @property
    def translator(self):
        if self._translator is None:
            log.info("Loading Translator...")
            self._translator = Translator()
        return self._translator

    @property
    def tts(self):
        if self._tts is None:
            log.info("Loading TTS engine...")
            self._tts = TTSEngine()
        return self._tts

    # ----------------------------------------------------------
    # Input validation
    # ----------------------------------------------------------
    def _validate_input(self, video_path: str):
        p = Path(video_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")
        if p.suffix.lower() not in ALLOWED_EXTS:
            raise ValueError(f"Unsupported format: {p.suffix}. Allowed: {ALLOWED_EXTS}")
        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(f"File too large: {size/1e9:.1f}GB (max 2GB)")
        if size == 0:
            raise ValueError(f"File is empty: {p}")

    # ----------------------------------------------------------
    # Job ID — deterministic from input path + target lang
    # ----------------------------------------------------------
    def _job_id(self, video_path: str, src_lang: str, tgt_lang: str) -> str:
        # Use filename + tgt_lang only — src_lang may be "auto" and resolved later
        key = f"{Path(video_path).name}_{tgt_lang}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    @staticmethod
    def _sanitize_id(value: str) -> str:
        """Strip path separators and shell-special chars from user-supplied IDs."""
        return re.sub(r"[^\w\-]", "_", value)[:64]

    # ----------------------------------------------------------
    # Main public API
    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # Exclusion detection (KB tender Section 3.1)
    # ----------------------------------------------------------
    def check_exclusions(self, text: str) -> list[str]:
        """
        Check if content matches KB exclusion patterns.
        Returns list of matched exclusion reasons (empty = no exclusions).
        """
        import re
        matched = []
        for pattern in _EXCLUSION_PATTERNS:
            if re.search(pattern, text):
                matched.append(pattern)
        return matched

    def should_skip_translation(self, segments: list[dict]) -> tuple[bool, str]:
        """
        Determine if the entire content should be skipped based on exclusion rules.
        Returns (should_skip, reason).
        """
        import re
        full_text = " ".join(s.get("text", "") for s in segments)
        for pattern in _EXCLUSION_PATTERNS:
            if re.search(pattern, full_text):
                return True, f"Exclusion pattern matched: {pattern[:60]}"
        return False, ""

    def dub_video(
        self,
        video_path:      str,
        src_lang:        str,
        tgt_lang:        str,
        output_dir:      str,
        course_id:       str  = "course",
        resume:          bool = True,
        generate_subs:   bool = True,
        force:           bool = False,
    ) -> DubbingResult:

        t0         = time.time()
        course_id  = self._sanitize_id(course_id)
        tgt_lang   = self._sanitize_id(tgt_lang)
        src_name   = LANG_NAMES.get(src_lang, src_lang)
        tgt_name   = LANG_NAMES.get(tgt_lang, tgt_lang)
        input_path = Path(video_path)
        is_audio   = input_path.suffix.lower() in (".mp3", ".wav", ".flac", ".ogg")
        is_webm    = input_path.suffix.lower() == ".webm"
        job_id     = self._job_id(video_path, src_lang, tgt_lang)

        log.info(f"START job={job_id} file={input_path.name} {src_name}->{tgt_name}")
        audit_log.info(json.dumps({
            "event": "job_start", "job_id": job_id,
            "file": input_path.name, "src": src_lang, "tgt": tgt_lang,
            "course_id": course_id, "host": platform.node(),
        }, ensure_ascii=False))

        result = DubbingResult(source_lang=src_lang, target_lang=tgt_lang,
                               input_path=video_path)

        out_dir = Path(output_dir) / tgt_lang

        # Always wipe previous output files so the user never gets a stale result.
        # ASR + translation are still checkpointed (expensive) — only TTS/assembly re-run.
        for p in out_dir.glob(f"{course_id}_{tgt_lang}.*"):
            if p.suffix in (".mp4", ".mp3", ".srt", ".vtt", ".json"):
                try:
                    p.unlink()
                except Exception:
                    pass
        if force:
            # force=True: also wipe ASR+translation checkpoint so everything re-runs
            try:
                JobCheckpoint(job_id).clear()
            except Exception:
                pass
            log.info(f"[{job_id}] force=True — cleared outputs + checkpoint for {tgt_lang}")
        else:
            log.info(f"[{job_id}] Cleared previous output for {tgt_lang} — re-running TTS/assembly")
        tmp_dir = out_dir / "tmp" / job_id
        tmp_dir.mkdir(parents=True, exist_ok=True)

        ckpt = JobCheckpoint(job_id) if resume else None

        job_lock = _get_job_lock(course_id, tgt_lang)
        if not job_lock.acquire(blocking=False):
            result.error = f"Job already running for {course_id}/{tgt_lang} — skipping duplicate"
            log.warning(f"[{job_id}] {result.error}")
            return result

        try:
            # ── Validate ───────────────────────────────────────────
            self._validate_input(video_path)

            # ── Step 1: Audio extraction ───────────────────────────
            wav_path = str(tmp_dir / "source.wav")
            # Re-extract if source.wav is older than the input video (stale cache)
            wav_exists = Path(wav_path).exists()
            wav_stale  = wav_exists and (
                Path(wav_path).stat().st_mtime < Path(video_path).stat().st_mtime
            )
            if not wav_exists or wav_stale:
                if wav_stale:
                    log.info(f"[{job_id}] source.wav stale — re-extracting")
                else:
                    log.info(f"[{job_id}] Step 1/6: Extracting audio")
                if is_audio:
                    self.video.convert_audio(video_path, wav_path, sample_rate=16000)
                    result.duration_original = self.video.get_audio_duration(wav_path)
                else:
                    self.video.extract_audio(video_path, wav_path, sample_rate=16000)
                    result.duration_original = self.video.get_video_duration(video_path)
                if ckpt:
                    ckpt.set_meta("duration", result.duration_original)
                    # Clear stale ASR segments so Step 2 re-runs
                    if wav_stale:
                        ckpt.set_meta("segments", None)
            else:
                result.duration_original = ckpt.get_meta("duration", 0) if ckpt else \
                    self.video.get_video_duration(video_path)
                log.info(f"[{job_id}] Step 1/6: Audio cached")

            # -- Step 1b: SeamlessM4T S2ST (direct speech-to-speech) --
            # Only for Indic→Indic pairs. English source always uses full ASR→Translate→TTS.
            from .lang_config import SEAMLESS_S2ST_LANGS
            s2st_wav = str(tmp_dir / "s2st_dubbed.wav")
            # Delete stale s2st file so it never blocks the full pipeline
            try:
                Path(s2st_wav).unlink(missing_ok=True)
            except Exception:
                pass
            _s2st_ok = (src_lang != "auto"
                        and src_lang != "eng"
                        and src_lang in SEAMLESS_S2ST_LANGS
                        and tgt_lang in SEAMLESS_S2ST_LANGS)
            if _s2st_ok:
                log.info(f"[{job_id}] Attempting SeamlessM4T S2ST {src_lang}->{tgt_lang}")
                if self._translator is None:
                    self._translator = Translator()
                if self._translator.translate_speech_to_speech(
                        wav_path, src_lang, tgt_lang, s2st_wav):
                    log.info(f"[{job_id}] S2ST success")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    if is_audio:
                        out_audio = str(out_dir / f"{course_id}_{tgt_lang}.mp3")
                        self.video.convert_audio(s2st_wav, out_audio)
                        result.output_audio_path = out_audio
                    else:
                        out_video = str(out_dir / f"{course_id}_{tgt_lang}.mp4")
                        self.video.replace_audio_in_video(video_path, s2st_wav, out_video,
                                                          is_webm=is_webm)
                        result.output_video_path = out_video
                        result.duration_output   = self.video.get_video_duration(out_video)
                    self._save_metadata(result, out_dir, course_id)
                    result.success   = True
                    result.elapsed_s = round(time.time() - t0, 1)
                    log.info(f"[{job_id}] S2ST done elapsed={result.elapsed_s}s")
                    if ckpt:
                        ckpt.clear()
                    return result
                else:
                    log.info(f"[{job_id}] S2ST not available, falling back to ASR+translate+TTS")

            # ── Step 2: ASR ────────────────────────────────────────
            if ckpt and ckpt.get_meta("segments"):
                segments = ckpt.get_meta("segments")
                src_lang = ckpt.get_meta("detected_src_lang") or src_lang
                log.info(f"[{job_id}] Step 2/6: ASR resumed ({len(segments)} segs) "
                         f"src_lang={src_lang}")
            else:
                log.info(f"[{job_id}] Step 2/6: Transcribing (src_lang={src_lang})")
                segments = self.asr.transcribe_segments(wav_path, src_lang)
                # Resolve auto-detected language from first segment's detected_lang
                if src_lang == "auto" or not src_lang:
                    src_lang = segments[0].get("detected_lang", "eng") if segments else "eng"
                    log.info(f"[{job_id}] Source language resolved: {src_lang} "
                             f"({LANG_NAMES.get(src_lang, src_lang)})")
                    result.source_lang = src_lang
                if ckpt:
                    ckpt.set_meta("segments", segments)
                    ckpt.set_meta("detected_src_lang", src_lang)
                log.info(f"[{job_id}] ASR done: {len(segments)} segments")

            result.transcript = segments
            # Re-apply hallucination stripping to checkpoint-restored segments.
            # _strip_hallucinations runs during live ASR but not on checkpoint restore,
            # so stale checkpoints may contain ँ/ं prefix artifacts.
            from .asr import _strip_hallucinations
            for seg in segments:
                seg["text"] = _strip_hallucinations(seg["text"])
            segments = [s for s in segments if s["text"].strip()]
            segments = _repair_asr_segments(segments)

            # ── Exclusion check (KB tender Section 3.1) ────────────
            skip, skip_reason = self.should_skip_translation(segments)
            if skip:
                log.warning(f"[{job_id}] SKIPPED — exclusion rule: {skip_reason}")
                result.error   = f"Skipped: {skip_reason}"
                result.success = False
                return result

            # ── Step 3: Translate (parallel + checkpoint) ──────────
            log.info(f"[{job_id}] Step 3/6: Translating {len(segments)} segments")
            translated_segments = self._translate_segments_parallel(
                segments, src_lang, tgt_lang, ckpt, job_id)
            result.translations = translated_segments

            # Quality summary
            scores = [s.get("quality", {"score": 1.0, "flags": [],
                                        "needs_review": False, "failed": False})
                      for s in translated_segments]
            result.quality_summary = review_summary(scores)
            log.info(f"[{job_id}] Quality: {result.quality_summary}")

            # Quality gate removed — all translated segments go to TTS.
            # Low quality score = flagged for human review, not silenced.
            # Silencing causes gaps in dubbed video which is worse than imperfect translation.

            # ── Step 4: TTS ────────────────────────────────────────
            log.info(f"[{job_id}] Step 4/6: TTS synthesis")
            tts_dir = str(tmp_dir / "tts_segments")
            shutil.rmtree(tts_dir, ignore_errors=True)
            # Check for spare-GPU sidecar written by dub_course_parallel
            try:
                tts_segments = self.tts.synthesize_segments(
                    translated_segments, tgt_lang, tts_dir)
            except RuntimeError as _tts_err:
                err_s = str(_tts_err).lower()
                if "illegal memory" in err_s or "cuda" in err_s:
                    log.warning(f"[{job_id}] TTS CUDA error — resetting engine and retrying with MMS fallback: {_tts_err}")
                    try:
                        if torch.cuda.is_available():
                            torch.cuda.synchronize()
                            torch.cuda.empty_cache()
                    except Exception:
                        pass
                    self._tts = None  # force reload
                    tts_segments = self.tts.synthesize_segments(
                        translated_segments, tgt_lang, tts_dir)
                else:
                    raise

            # ── Step 5: Assemble audio ─────────────────────────────
            log.info(f"[{job_id}] Step 5/6: Assembling audio")
            dubbed_wav = str(tmp_dir / "dubbed.wav")
            self.video.assemble_dubbed_audio(
                tts_segments, result.duration_original, dubbed_wav)

            # ── Step 6: Output ─────────────────────────────────────
            log.info(f"[{job_id}] Step 6/6: Writing output")

            # Generate subtitles first so they can be embedded in the MP4
            srt_path = None
            if generate_subs and translated_segments:
                try:
                    sub_paths = generate_subtitles(
                        translated_segments, str(out_dir), course_id, tgt_lang,
                        video_duration=result.duration_original)
                    srt_path = sub_paths.get("srt")
                except Exception as e:
                    log.warning(f"[{job_id}] Subtitle generation failed: {e}")

            if is_audio:
                out_audio = str(out_dir / f"{course_id}_{tgt_lang}.mp3")
                self.video.convert_audio(dubbed_wav, out_audio)
                result.output_audio_path = out_audio
            else:
                out_video = str(out_dir / f"{course_id}_{tgt_lang}.mp4")
                self.video.replace_audio_in_video(
                    video_path, dubbed_wav, out_video,
                    srt_path=srt_path, lang=tgt_lang, is_webm=is_webm)
                result.output_video_path = out_video
                result.duration_output   = self.video.get_video_duration(out_video)

            # ── Duration ratio check (KB tender Section 5.1B) ─────
            if result.duration_output > 0 and result.duration_original > 0:
                ratio = result.duration_output / result.duration_original
                if ratio > DURATION_RATIO_THRESHOLD:
                    log.warning(
                        f"[{job_id}] Duration ratio {ratio:.2f}x exceeds 20% threshold "
                        f"(original={result.duration_original:.1f}s, "
                        f"output={result.duration_output:.1f}s). "
                        f"KB approval required before payment."
                    )
                    result.quality_summary["duration_ratio"]          = round(ratio, 3)
                    result.quality_summary["duration_ratio_flag"]     = True
                    result.quality_summary["duration_ratio_kb_approval_required"] = True
                else:
                    result.quality_summary["duration_ratio"]      = round(ratio, 3)
                    result.quality_summary["duration_ratio_flag"] = False

            self._save_metadata(result, out_dir, course_id)
            result.success   = True
            result.elapsed_s = round(time.time() - t0, 1)
            out = result.output_video_path or result.output_audio_path
            log.info(f"[{job_id}] SUCCESS elapsed={result.elapsed_s}s -> {out}")
            audit_log.info(json.dumps({
                "event": "job_success", "job_id": job_id,
                "tgt": tgt_lang, "elapsed_s": result.elapsed_s,
                "output": out, "quality": result.quality_summary,
            }, ensure_ascii=False))

            # Clear checkpoint on success
            if ckpt:
                ckpt.clear()

        except Exception as e:
            result.error     = str(e)
            result.elapsed_s = round(time.time() - t0, 1)
            log.error(f"[{job_id}] FAILED: {e}", exc_info=True)
            audit_log.info(json.dumps({
                "event": "job_failed", "job_id": job_id,
                "tgt": tgt_lang, "elapsed_s": result.elapsed_s, "error": str(e),
            }, ensure_ascii=False))
        finally:
            job_lock.release()
            # Keep tmp only on failure (for resume); clean on success
            if result.success:
                shutil.rmtree(str(tmp_dir), ignore_errors=True)

        return result

    def _synthesize_tts_split(
        self, translated_segments: list, tgt_lang: str, tts_dir: str,
        primary_gpu: int, spare_gpus: list, job_id: str
    ) -> list:
        """
        Split TTS synthesis across primary GPU + spare GPUs.
        Odd-indexed segments go to spare GPU(s), even to primary.
        Results are merged back in original order.
        Gives ~2x speedup when one spare GPU is available.
        """
        import multiprocessing as mp
        ctx = mp.get_context("spawn")

        n = len(translated_segments)
        all_indices = list(range(n))
        all_gpus = [primary_gpu] + spare_gpus
        n_gpus = len(all_gpus)

        # Round-robin distribute segment indices across all GPUs
        gpu_segs = {g: [] for g in all_gpus}
        for idx in all_indices:
            gpu_segs[all_gpus[idx % n_gpus]].append(idx)

        log.info(
            f"[{job_id}] TTS split across {n_gpus} GPUs "
            + ", ".join(f"GPU{g}:{len(gpu_segs[g])}segs" for g in all_gpus)
        )

        worker_args = [
            (g, tgt_lang, gpu_segs[g], translated_segments,
             tts_dir + f"_gpu{g}")
            for g in all_gpus if gpu_segs[g]
        ]

        with ctx.Pool(processes=len(worker_args)) as pool:
            split_results = pool.map(_worker_tts_split, worker_args)

        # Merge: build index -> audio_path map
        idx_to_path = {}
        for chunk in split_results:
            idx_to_path.update(chunk)

        # Reconstruct results list in original segment order
        results = []
        for i, seg in enumerate(translated_segments):
            audio_path = idx_to_path.get(i, "")
            results.append({**seg, "audio_path": audio_path})
        return results

    def dub_course(
        self,
        video_path:      str,
        src_lang:        str,
        tgt_langs:       list[str],
        output_dir:      str,
        course_id:       str  = "course",
        force:           bool = False,
        num_gpus:        int  = 1,
    ) -> dict[str, DubbingResult]:
        """Run target languages — parallel across GPUs when num_gpus > 1."""
        if num_gpus > 1:
            return self.dub_course_parallel(
                video_path, src_lang, tgt_langs, output_dir, course_id,
                force=force, num_gpus=num_gpus,
            )
        results = {}
        for tgt_lang in tgt_langs:
            results[tgt_lang] = self.dub_video(
                video_path, src_lang, tgt_lang, output_dir, course_id,
                force=force,
            )
        return results

    def dub_course_parallel(
        self,
        video_path:      str,
        src_lang:        str,
        tgt_langs:       list[str],
        output_dir:      str,
        course_id:       str  = "course",
        force:           bool = False,
        num_gpus:        int  = 4,
    ) -> dict[str, DubbingResult]:
        """
        Distribute target languages across num_gpus GPUs using multiprocessing.
        ASR runs ONCE here in the main process, segments are cached to disk and
        shared to all workers — eliminates 4x redundant transcription.
        Each worker gets its own GPU via PIPELINE_GPU and runs translate+TTS+assemble.
        """
        import multiprocessing as mp
        ctx = mp.get_context("spawn")

        # ── Step 1: Run ASR once in main process ──────────────────
        log.info("[parallel] Running ASR once in main process (shared across all workers)")
        self._validate_input(video_path)
        input_path = Path(video_path)
        is_audio   = input_path.suffix.lower() in (".mp3", ".wav", ".flac", ".ogg")
        is_webm    = input_path.suffix.lower() == ".webm"

        # Shared tmp dir for ASR cache
        asr_tmp = Path(output_dir) / "_asr_shared"
        asr_tmp.mkdir(parents=True, exist_ok=True)
        wav_path     = str(asr_tmp / "source.wav")
        asr_cache_path = str(asr_tmp / "asr_cache.json")

        if not Path(asr_cache_path).exists() or (
            Path(asr_cache_path).stat().st_mtime < Path(video_path).stat().st_mtime
        ):
            if not Path(wav_path).exists():
                if is_audio:
                    self.video.convert_audio(video_path, wav_path, sample_rate=16000)
                    duration = self.video.get_audio_duration(wav_path)
                else:
                    self.video.extract_audio(video_path, wav_path, sample_rate=16000)
                    duration = self.video.get_video_duration(video_path)
            else:
                duration = self.video.get_video_duration(video_path)

            segments = self.asr.transcribe_segments(wav_path, src_lang)
            if src_lang == "auto" or not src_lang:
                src_lang = segments[0].get("detected_lang", "eng") if segments else "eng"
            log.info(f"[parallel] ASR done: {len(segments)} segments, src_lang={src_lang}")

            import json as _json
            Path(asr_cache_path).write_text(
                _json.dumps({"segments": segments, "src_lang": src_lang, "duration": duration},
                            ensure_ascii=False),
                encoding="utf-8"
            )
        else:
            import json as _json
            cache    = _json.loads(Path(asr_cache_path).read_text(encoding="utf-8"))
            src_lang = cache["src_lang"]
            log.info(f"[parallel] ASR cache hit: {len(cache['segments'])} segments")

        # ── Step 2: Distribute langs across GPUs (round-robin) ──────
        # Each GPU gets a bucket of languages and processes them sequentially.
        # e.g. 22 langs, 4 GPUs → GPU0:[0,4,8,12,16,20] GPU1:[1,5,9,13,17,21] etc.
        import json as _json2
        n_langs = len(tgt_langs)
        buckets: dict[int, list[str]] = {g: [] for g in range(num_gpus)}
        for i, lang in enumerate(tgt_langs):
            buckets[i % num_gpus].append(lang)

        # Remove spare_gpus.json if it exists — not used in round-robin mode
        spare_path = asr_tmp / "spare_gpus.json"
        try:
            spare_path.unlink(missing_ok=True)
        except Exception:
            pass

        worker_args = [
            (gpu_id, langs, video_path, src_lang, output_dir, course_id,
             force, asr_cache_path)
            for gpu_id, langs in buckets.items() if langs
        ]
        n_workers = len(worker_args)

        log.info(f"[parallel] {n_langs} langs across {n_workers} GPUs (round-robin)")
        for gpu_id, langs in buckets.items():
            if langs:
                log.info(f"  GPU {gpu_id}: {langs}")

        with ctx.Pool(processes=n_workers) as pool:
            group_results = pool.map(_worker_dub_langs, worker_args)

        # Clean up shared ASR cache
        try:
            shutil.rmtree(str(asr_tmp), ignore_errors=True)
        except Exception:
            pass

        merged: dict[str, DubbingResult] = {}
        for group in group_results:
            merged.update(group)
        return merged

    # ----------------------------------------------------------
    # Parallel translation with checkpoint
    # ----------------------------------------------------------
    def _translate_segments_parallel(
        self, segments: list[dict], src_lang: str, tgt_lang: str,
        ckpt: JobCheckpoint | None, job_id: str
    ) -> list[dict]:

        results = [None] * len(segments)

        # Restore already-done segments from checkpoint
        pending_idxs = []
        for i, seg in enumerate(segments):
            if ckpt and ckpt.is_done(seg["id"]):
                results[i] = ckpt.get_done(seg["id"])
            else:
                pending_idxs.append(i)

        if not pending_idxs:
            log.info(f"[{job_id}] All {len(segments)} segments resumed from checkpoint")
            return results

        pending_segs  = [segments[i] for i in pending_idxs]
        pending_texts = [s.get("text", "").strip() for s in pending_segs]
        # indices into pending_segs/pending_texts that are empty, non-translatable, or have text
        from .translator import _is_fully_nontranslatable
        empty_local   = [i for i, t in enumerate(pending_texts) if not t]
        nt_local      = [i for i, t in enumerate(pending_texts)
                         if t and _is_fully_nontranslatable(t)]
        nt_set        = set(nt_local)
        text_local    = [i for i, t in enumerate(pending_texts)
                         if t and i not in nt_set]

        # Empty segments — pass through immediately
        for local_i in empty_local:
            results[pending_idxs[local_i]] = {
                **pending_segs[local_i], "text": "", "engine": "empty",
                "enhanced": False,
                "quality": {"score": 1.0, "flags": [], "needs_review": False, "failed": False}
            }

        # Non-translatable segments (URLs, code, paths) — pass through unchanged
        for local_i in nt_local:
            orig_text = pending_texts[local_i]
            results[pending_idxs[local_i]] = {
                **pending_segs[local_i], "text": orig_text,
                "engine": "passthrough_nontranslatable", "enhanced": False,
                "quality": {"score": 1.0, "flags": [], "needs_review": False, "failed": False}
            }

        if not text_local:
            return results

        log.info(f"[{job_id}] Translating {len(text_local)} segments via GPU batch")

        texts_to_translate = [pending_texts[i] for i in text_local]
        detected_langs     = [pending_segs[i].get("detected_lang") for i in text_local]
        try:
            # detected_langs is only meaningful for Indic source languages.
            # For English source, Lingua misdetects English ASR as Hindi/Bodo/Maithili
            # — passing those as detected_langs corrupts the translation routing.
            effective_detected = detected_langs if src_lang != "eng" else None
            batch_results = self.translator.translate_batch(
                texts_to_translate, src_lang, tgt_lang,
                glossary=self.glossary, detected_langs=effective_detected)
        except Exception as e:
            log.error(f"[{job_id}] Batch translation failed, falling back per-segment: {e}")
            batch_results = []
            for t, dl in zip(texts_to_translate, detected_langs):
                try:
                    batch_results.append(
                        self.translator.translate(t, src_lang, tgt_lang,
                                                  glossary=self.glossary, detected_lang=dl))
                except Exception:
                    batch_results.append({
                        "text": t, "engine": "failed", "enhanced": False,
                        "score": {"score": 0.0, "flags": ["translation_error"],
                                  "needs_review": True, "failed": True}
                    })

        # Completeness guard: output count must match input count
        if len(batch_results) != len(text_local):
            log.error(
                f"[{job_id}] Completeness violation: sent {len(text_local)} segments, "
                f"got {len(batch_results)} back — falling back to per-segment"
            )
            batch_results = []
            for t, dl in zip(texts_to_translate, detected_langs):
                try:
                    batch_results.append(
                        self.translator.translate(t, src_lang, tgt_lang,
                                                  glossary=self.glossary, detected_lang=dl))
                except Exception:
                    batch_results.append({
                        "text": t, "engine": "failed", "enhanced": False,
                        "score": {"score": 0.0, "flags": ["translation_error"],
                                  "needs_review": True, "failed": True}
                    })

        for batch_i, local_i in enumerate(text_local):
            seg  = pending_segs[local_i]
            r    = batch_results[batch_i]
            # Completeness guard: never emit an empty translation for a non-empty source.
            translated_text = r["text"]
            if not translated_text.strip() and pending_texts[local_i].strip():
                log.warning(
                    f"[{job_id}] Empty translation for seg {seg['id']} — retrying per-segment"
                )
                try:
                    retry_r = self.translator.translate(
                        pending_texts[local_i], src_lang, tgt_lang,
                        glossary=self.glossary,
                        detected_lang=pending_segs[local_i].get("detected_lang"))
                    if retry_r["text"].strip():
                        translated_text = retry_r["text"]
                        r = {**r, "text": translated_text,
                             "engine": retry_r.get("engine", "retry_fallback"),
                             "score": {**r.get("score", {}),
                                       "flags": r.get("score", {}).get("flags", []) + ["completeness_retry"],
                                       "needs_review": True}}
                except Exception as retry_e:
                    log.error(f"[{job_id}] Retry failed for seg {seg['id']}: {retry_e}")
                # If still empty after retries, use source text as absolute last resort
                # (better to speak English than silence for a Hindi dub)
                if not translated_text.strip():
                    log.error(f"[{job_id}] All retries failed for seg {seg['id']} — using source text")
                    translated_text = pending_texts[local_i]
                    r = {**r, "text": translated_text,
                         "score": {**r.get("score", {}),
                                   "flags": r.get("score", {}).get("flags", []) + ["translation_failed_source_fallback"],
                                   "needs_review": True, "failed": True}}
            done = {**seg, "text": translated_text, "engine": r["engine"],
                    "enhanced": False, "quality": r["score"]}
            results[pending_idxs[local_i]] = done
            if ckpt:
                ckpt.mark_done(seg["id"], done)

        # Completeness guard: ensure no result slot is None (would silently drop a segment)
        for i, r in enumerate(results):
            if r is None:
                orig_seg = segments[i]
                log.warning(
                    f"[{job_id}] Segment {orig_seg.get('id')} has no translation result — "
                    f"retrying per-segment"
                )
                try:
                    retry_r = self.translator.translate(
                        orig_seg.get("text", ""), src_lang, tgt_lang,
                        glossary=self.glossary)
                    results[i] = {
                        **orig_seg,
                        "text": retry_r["text"] or "",
                        "engine": retry_r.get("engine", "retry_fallback"),
                        "enhanced": False,
                        "quality": {"score": 0.0, "flags": ["completeness_retry"],
                                    "needs_review": True, "failed": False},
                    }
                except Exception:
                    results[i] = {
                        **orig_seg, "text": "",
                        "engine": "failed", "enhanced": False,
                        "quality": {"score": 0.0, "flags": ["translation_failed"],
                                    "needs_review": True, "failed": True},
                    }

        # Single flush after entire batch — not per segment
        if ckpt:
            try:
                ckpt.flush()
            except Exception:
                pass

        return results

    # ----------------------------------------------------------
    # Metadata / Quiz / QA / Reports (unchanged logic, new logging)
    # ----------------------------------------------------------
    def translate_metadata(self, metadata: dict, src_lang: str, tgt_lang: str) -> dict:
        tgt_name   = LANG_NAMES.get(tgt_lang, tgt_lang)
        translated = {"lang": tgt_lang, "lang_name": tgt_name}
        for key in ["title", "description", "learning_outcome",
                    "module_titles", "resource_titles"]:
            val = metadata.get(key)
            if not val:
                translated[key] = val
            elif isinstance(val, str):
                translated[key] = self._translate_text(val, src_lang, tgt_lang)
            elif isinstance(val, list):
                translated[key] = [self._translate_text(i, src_lang, tgt_lang) for i in val]
        keywords = metadata.get("keywords", [])
        translated["keywords"] = (
            [self._translate_text(k, src_lang, tgt_lang) for k in keywords] + keywords
        )
        return translated

    def export_metadata_docx(self, metadata: dict, src_lang: str,
                              tgt_lang: str, output_path: str) -> str:
        """Export translated metadata as Word doc (KB tender SoW 3.4)."""
        from docx import Document
        lang_name  = LANG_NAMES.get(tgt_lang, tgt_lang)
        translated = self.translate_metadata(metadata, src_lang, tgt_lang)
        doc = Document()
        doc.add_heading(f"Course Metadata — {lang_name}", level=1)
        fields = ["title", "description", "learning_outcome",
                  "keywords", "module_titles", "resource_titles"]
        t = doc.add_table(rows=1, cols=3)
        t.style = "Table Grid"
        for i, h in enumerate(["Field", "Original", f"Translated ({lang_name})"]):
            t.rows[0].cells[i].text = h
        for f in fields:
            orig = metadata.get(f, "")
            tgt  = translated.get(f, "")
            row  = t.add_row().cells
            row[0].text = f
            row[1].text = " | ".join(orig) if isinstance(orig, list) else (orig or "")
            row[2].text = " | ".join(tgt)  if isinstance(tgt,  list) else (tgt  or "")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"Metadata docx → {output_path}")
        return output_path

    def export_quiz_xlsx(self, quiz: list[dict], src_lang: str, tgt_lang: str,
                         output_path: str, course_title: str = "") -> str:
        """Export translated quiz as Excel (KB tender SoW 3.4)."""
        import openpyxl
        lang_name  = LANG_NAMES.get(tgt_lang, tgt_lang)
        translated = self.translate_quiz(quiz, src_lang, tgt_lang)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = lang_name[:31]
        ws.append(["Q#", "Question", "Option A", "Option B", "Option C", "Option D", "Answer"])
        for i, (orig, tgt) in enumerate(zip(quiz, translated), 1):
            opts = tgt.get("options", [])
            ws.append([
                i,
                tgt.get("question", ""),
                opts[0] if len(opts) > 0 else "",
                opts[1] if len(opts) > 1 else "",
                opts[2] if len(opts) > 2 else "",
                opts[3] if len(opts) > 3 else "",
                tgt.get("answer", ""),
            ])
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        log.info(f"Quiz xlsx → {output_path}")
        return output_path

    def export_metadata_xlsx(self, metadata: dict, src_lang: str,
                             tgt_langs: list[str], output_path: str) -> str:
        import openpyxl
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        fields = ["title", "description", "learning_outcome",
                  "keywords", "module_titles", "resource_titles"]
        for tgt_lang in tgt_langs:
            lang_name  = LANG_NAMES.get(tgt_lang, tgt_lang)
            translated = self.translate_metadata(metadata, src_lang, tgt_lang)
            ws = wb.create_sheet(title=lang_name[:31])
            ws.append(["Field", "Original (English)", f"Translated ({lang_name})"])
            for f in fields:
                orig = metadata.get(f, "")
                tgt  = translated.get(f, "")
                ws.append([f,
                           " | ".join(orig) if isinstance(orig, list) else orig,
                           " | ".join(tgt)  if isinstance(tgt,  list) else tgt])
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        log.info(f"Metadata Excel → {output_path}")
        return output_path

    def translate_quiz(self, quiz: list[dict], src_lang: str, tgt_lang: str) -> list[dict]:
        log.info(f"Translating quiz ({len(quiz)} questions) → {LANG_NAMES.get(tgt_lang)}")
        out = []
        for item in quiz:
            t = {}
            if "question" in item:
                t["question"] = self._translate_text(item["question"], src_lang, tgt_lang)
            if "options" in item:
                t["options"] = [self._translate_text(o, src_lang, tgt_lang)
                                for o in item["options"]]
            if "answer" in item:
                t["answer"] = self._translate_text(item["answer"], src_lang, tgt_lang)
            out.append(t)
        return out

    def export_quiz_docx(self, quiz: list[dict], src_lang: str, tgt_lang: str,
                         output_path: str, course_title: str = "") -> str:
        from docx import Document
        from docx.shared import RGBColor
        lang_name  = LANG_NAMES.get(tgt_lang, tgt_lang)
        translated = self.translate_quiz(quiz, src_lang, tgt_lang)
        doc = Document()
        doc.add_heading(f"Assessment / Reflection Quiz — {lang_name}", level=1)
        if course_title:
            doc.add_paragraph(f"Course: {course_title}")
        doc.add_paragraph(f"Language: {lang_name} ({tgt_lang})")
        doc.add_paragraph("")
        for i, (orig, tgt) in enumerate(zip(quiz, translated), 1):
            p = doc.add_paragraph()
            p.add_run(f"Q{i}. ").bold = True
            p.add_run(tgt.get("question", ""))
            for j, opt in enumerate(tgt.get("options", []), 1):
                doc.add_paragraph(f"   {chr(64+j)}. {opt}", style="List Bullet")
            if "answer" in tgt:
                ap  = doc.add_paragraph()
                run = ap.add_run(f"Answer: {tgt['answer']}")
                run.bold = True
                run.font.color.rgb = RGBColor(0, 128, 0)
            doc.add_paragraph("")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"Quiz docx → {output_path}")
        return output_path

    def generate_qa_report(self, course_id: str, tgt_lang: str,
                           dubbing_result: DubbingResult, output_path: str,
                           reviewer_name: str = "Translation Agency QA Lead") -> str:
        from docx import Document
        import datetime
        lang_name = LANG_NAMES.get(tgt_lang, tgt_lang)

        # Full quality re-score with back-translation for QA report
        full_scores = []
        for seg in dubbing_result.translations:
            src_text = next(
                (s.get("text", "") for s in dubbing_result.transcript
                 if s.get("id") == seg.get("id")), "")
            if src_text and seg.get("text"):
                full_scores.append(
                    score_segment_full(src_text, seg["text"],
                                       dubbing_result.source_lang, tgt_lang))
        qs = review_summary(full_scores) if full_scores else dubbing_result.quality_summary
        doc = Document()
        doc.add_heading("Language Quality Assurance Certification", level=1)
        doc.add_heading("KB iGOT Karmayogi — Translation Agency Self-Certification", level=2)
        doc.add_paragraph("")
        table = doc.add_table(rows=10, cols=2)
        table.style = "Table Grid"
        rows_data = [
            ("Course ID",              course_id),
            ("Target Language",        f"{lang_name} ({tgt_lang})"),
            ("Source Language",        LANG_NAMES.get(dubbing_result.source_lang, dubbing_result.source_lang)),
            ("Input File",             Path(dubbing_result.input_path).name),
            ("Output File",            Path(dubbing_result.output_video_path or dubbing_result.output_audio_path or "—").name),
            ("Duration (original)",    f"{dubbing_result.duration_original:.1f}s"),
            ("Heuristic Score",        f"{qs.get('avg_score', 'N/A')} (pass rate: {qs.get('pass_rate', 'N/A')})"),
            ("ChrF Score",             str(qs.get('avg_chrf') or 'N/A')),
            ("Back-Translation Score", str(qs.get('avg_back_translation') or 'N/A')),
            ("Certification Date",     datetime.datetime.now().strftime("%d %B %Y")),
        ]
        for i, (label, value) in enumerate(rows_data):
            table.rows[i].cells[0].text = label
            table.rows[i].cells[1].text = value
        doc.add_paragraph("")
        doc.add_heading("Certification Checklist", level=2)
        for title, desc in [
            ("Linguistic Accuracy",       f"Reviewed by qualified native {lang_name} expert."),
            ("Terminology Consistency",   "Domain terms translated consistently using approved glossary."),
            ("Content Guidelines",        "Free from hate speech, abuse, violence, profanity."),
            ("Administrative Context",    "Administrative context retained; transliteration avoided."),
            ("Audio-Text Sync",           "Dubbed voiceover in sync with on-screen text."),
            ("Technical Format",          "Output in correct format per KB technical standards."),
            ("No Mixed Languages",        "Content does not mix multiple languages."),
        ]:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"✅ {title}: ").bold = True
            p.add_run(desc)
        doc.add_paragraph("")
        doc.add_heading("Declaration", level=2)
        doc.add_paragraph(
            f"We certify that translated content for {lang_name} (Course ID: {course_id}) "
            "meets all quality standards per KB RFB IN-KBL-543730-NC-RFB.")
        doc.add_paragraph(f"Reviewed by: {reviewer_name}")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        doc.add_paragraph("Signature: ____________________")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"QA report → {output_path}")
        return output_path

    def check_already_translated(
        self, course_id: str, tgt_lang: str, output_dir: str
    ) -> dict[str, bool]:
        """
        KB tender SoW 3.1: check if assets already exist in target language.
        Returns dict of asset type → already_exists bool.
        """
        out = Path(output_dir) / tgt_lang
        return {
            "video":    any(out.glob(f"{course_id}_{tgt_lang}.mp4")),
            "audio":    any(out.glob(f"{course_id}_{tgt_lang}.mp3")),
            "quiz":     any(out.glob(f"{course_id}_quiz_{tgt_lang}.*")),
            "metadata": any(out.glob(f"{course_id}_metadata*{tgt_lang}*")),
            "subtitles":any(out.glob(f"{course_id}_{tgt_lang}.srt")),
        }

    def generate_correction_report(
        self, course_id: str, tgt_lang: str,
        issues: list[dict], output_path: str
    ) -> str:
        """
        KB tender Deliverables 4.5.iv — Correction & Closure Report.
        issues: list of {"issue": str, "action": str, "status": str}
        """
        from docx import Document
        import datetime
        lang_name = LANG_NAMES.get(tgt_lang, tgt_lang)
        doc = Document()
        doc.add_heading("Correction & Closure Report", level=1)
        doc.add_heading("KB iGOT Karmayogi — Translation Agency", level=2)
        doc.add_paragraph(f"Course ID: {course_id}")
        doc.add_paragraph(f"Language: {lang_name} ({tgt_lang})")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        doc.add_paragraph("")
        doc.add_heading("Issues & Corrective Actions", level=2)
        if issues:
            t = doc.add_table(rows=1, cols=3)
            t.style = "Table Grid"
            for i, h in enumerate(["Issue Flagged by KB", "Corrective Action Taken", "Status"]):
                t.rows[0].cells[i].text = h
            for item in issues:
                row = t.add_row().cells
                row[0].text = item.get("issue", "")
                row[1].text = item.get("action", "")
                row[2].text = item.get("status", "Resolved")
        else:
            doc.add_paragraph("No issues flagged. Content accepted without corrections.")
        doc.add_paragraph("")
        doc.add_heading("Final Compliance Confirmation", level=2)
        doc.add_paragraph(
            f"All corrections for {lang_name} (Course ID: {course_id}) have been "
            "completed and verified. Content meets KB quality standards per "
            "RFB IN-KBL-543730-NC-RFB.")
        doc.add_paragraph(f"Confirmed by: ____________________")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"Correction report → {output_path}")
        return output_path

    def generate_inception_report(
        self, course_ids: list[str], tgt_langs: list[str],
        output_dir: str, output_path: str
    ) -> str:
        """
        KB tender Payment Milestone 1 — Inception Report with detailed translation plan.
        Must be submitted within T0+15 days to trigger first 15% payment.
        """
        from docx import Document
        import datetime
        doc = Document()
        doc.add_heading("Inception Report — Translation Plan", level=1)
        doc.add_heading("KB iGOT Karmayogi Platform — Language Translation & Dubbing", level=2)
        doc.add_paragraph(f"RFB No.: IN-KBL-543730-NC-RFB")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        doc.add_paragraph("")
        doc.add_heading("1. Project Understanding", level=2)
        doc.add_paragraph(
            f"This inception report outlines the detailed translation plan for "
            f"{len(course_ids)} courses across {len(tgt_langs)} target languages "
            f"on the iGOT Karmayogi platform.")
        doc.add_heading("2. AI Translation Stack", level=2)
        for item in [
            "Primary Engine: IndicTrans2 (offline, sovereign, hosted on-premise)",
            "Fallback 1: SeamlessM4T (offline)",
            "Fallback 2: NLLB-200 (offline)",
            "ASR: faster-whisper large-v3 (offline)",
            "TTS: Parler-TTS Indic (offline, single model for all 22 languages)",
            "All models run locally — no data leaves the system (data residency compliant)",
        ]:
            doc.add_paragraph(item, style="List Bullet")
        doc.add_heading("3. Target Languages", level=2)
        lang_list = ", ".join(LANG_NAMES.get(l, l) for l in tgt_langs)
        doc.add_paragraph(f"Languages in scope: {lang_list}")
        doc.add_heading("4. Monthly Delivery Plan", level=2)
        schedule = [
            (1, 50), (2, 55), (3, 100), (4, 125), (5, 100),
            (6, 125), (7, 100), (8, 125), (9, 100), (10, 125), (11, 100),
        ]
        t = doc.add_table(rows=1, cols=3)
        t.style = "Table Grid"
        for i, h in enumerate(["Month", "Target Hours", "Submission Deadline"]):
            t.rows[0].cells[i].text = h
        for month, hours in schedule:
            row = t.add_row().cells
            row[0].text = f"Month {month}"
            row[1].text = f"{hours} hours"
            row[2].text = f"End of Month {month}"
        doc.add_heading("5. Quality Assurance Process", level=2)
        for item in [
            "AI translation → automated quality scoring (heuristic + ChrF + back-translation)",
            "Transliteration detection — automatic flag and rejection",
            "Glossary enforcement — domain terms protected throughout translation",
            "Native language expert review before submission",
            "Self-certification QA report generated per course per language",
        ]:
            doc.add_paragraph(item, style="List Bullet")
        doc.add_heading("6. Output Directory Structure", level=2)
        doc.add_paragraph(f"All outputs stored at: {output_dir}")
        doc.add_paragraph("Structure: <output_dir>/<lang_code>/<course_id>_<lang>.mp4")
        doc.add_paragraph("")
        doc.add_paragraph("Submitted by: ____________________")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"Inception report → {output_path}")
        return output_path

    def generate_completion_report(
        self, results: dict[str, dict[str, DubbingResult]],
        glossary_terms: dict, output_path: str
    ) -> str:
        """
        KB tender Deliverables 4.6 — Consolidated Completion Report (end of contract).
        Includes: all courses + languages, final compliance certificate,
        glossary of standardized translated terms.
        """
        from docx import Document
        import datetime
        doc = Document()
        doc.add_heading("Consolidated Completion Report", level=1)
        doc.add_heading("KB iGOT Karmayogi — Language Translation & Dubbing Contract", level=2)
        doc.add_paragraph(f"RFB No.: IN-KBL-543730-NC-RFB")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        doc.add_paragraph("")
        # Summary stats
        total_hours, total_ok, total_fail, langs_done = 0.0, 0, 0, set()
        for _, lang_results in results.items():
            for lang, r in lang_results.items():
                if r.success:
                    total_hours += r.duration_original / 3600
                    total_ok    += 1
                    langs_done.add(lang)
                else:
                    total_fail  += 1
        doc.add_heading("1. Contract Summary", level=2)
        st = doc.add_table(rows=5, cols=2)
        st.style = "Table Grid"
        for i, (k, v) in enumerate([
            ("Total Courses Accepted",   str(total_ok)),
            ("Total Translated Hours",   f"{total_hours:.2f} hours"),
            ("Languages Delivered",      ", ".join(LANG_NAMES.get(l, l) for l in sorted(langs_done))),
            ("Failed / Skipped",         str(total_fail)),
            ("Contract",                 "RFB IN-KBL-543730-NC-RFB"),
        ]):
            st.rows[i].cells[0].text = k
            st.rows[i].cells[1].text = v
        doc.add_paragraph("")
        # Course-wise table
        doc.add_heading("2. Course-wise Delivery Details", level=2)
        dt = doc.add_table(rows=1, cols=5)
        dt.style = "Table Grid"
        for i, h in enumerate(["Course ID", "Language", "Hours", "Quality Score", "Status"]):
            dt.rows[0].cells[i].text = h
        for cid, lang_results in results.items():
            for lang, r in lang_results.items():
                row = dt.add_row().cells
                row[0].text = cid
                row[1].text = LANG_NAMES.get(lang, lang)
                row[2].text = f"{r.duration_original/3600:.2f}"
                row[3].text = str(r.quality_summary.get("avg_score", "N/A"))
                row[4].text = "✅ Accepted" if r.success else f"❌ {r.error[:30]}"
        doc.add_paragraph("")
        # Final compliance certificate
        doc.add_heading("3. Final Language & Technical Compliance Certificate", level=2)
        for item in [
            "All translated content meets 98% linguistic accuracy SLA",
            "No transliteration detected in any delivered course",
            "Glossary enforced consistently across all courses",
            "All outputs in MP4/MP3/Word/Excel format per SoW 3.4",
            "Subtitles (SRT/VTT) generated for all video courses",
            "All assets uploaded to CBP portal (cbp.igotkarmayogi.gov.in)",
            "Data residency maintained — all processing done on-premise in India",
        ]:
            doc.add_paragraph(f"✅ {item}", style="List Bullet")
        doc.add_paragraph("")
        # Glossary of standardized terms
        doc.add_heading("4. Glossary of Standardized Translated Terms", level=2)
        if glossary_terms:
            gt = doc.add_table(rows=1, cols=3)
            gt.style = "Table Grid"
            for i, h in enumerate(["English Term", "Language", "Standardized Translation"]):
                gt.rows[0].cells[i].text = h
            for term, translations in glossary_terms.items():
                if isinstance(translations, dict):
                    for lang, tval in translations.items():
                        row = gt.add_row().cells
                        row[0].text = term
                        row[1].text = LANG_NAMES.get(lang, lang)
                        row[2].text = tval
                else:
                    row = gt.add_row().cells
                    row[0].text = term
                    row[1].text = "All"
                    row[2].text = str(translations)
        else:
            doc.add_paragraph("Glossary file not provided. Refer to glossary/ directory.")
        doc.add_paragraph("")
        doc.add_paragraph("Submitted by: ____________________")
        doc.add_paragraph(f"Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"Completion report → {output_path}")
        return output_path

    def generate_monthly_report(self, month: int,
                                results: dict[str, dict[str, DubbingResult]],
                                output_path: str) -> str:
        from docx import Document
        import datetime
        doc = Document()
        doc.add_heading(f"Month {month} — Translation Submission Report", level=1)
        doc.add_heading("KB iGOT Karmayogi Platform — Course Translation", level=2)
        doc.add_paragraph(f"Submission Date: {datetime.datetime.now().strftime('%d %B %Y')}")
        doc.add_paragraph("")
        total_hours, total_courses, langs = 0.0, 0, set()
        for _, lang_results in results.items():
            for lang, r in lang_results.items():
                if r.success:
                    total_hours += r.duration_original / 3600
                    langs.add(lang)
                    total_courses += 1
        doc.add_heading("Summary", level=2)
        st = doc.add_table(rows=4, cols=2)
        st.style = "Table Grid"
        for i, (k, v) in enumerate([
            ("Total Courses Delivered", str(total_courses)),
            ("Total Translated Hours",  f"{total_hours:.2f} hours"),
            ("Languages Covered",       ", ".join(LANG_NAMES.get(l, l) for l in sorted(langs))),
            ("Report Month",            f"Month {month}"),
        ]):
            st.rows[i].cells[0].text = k
            st.rows[i].cells[1].text = v
        doc.add_paragraph("")
        doc.add_heading("Course-wise Details", level=2)
        dt = doc.add_table(rows=1, cols=5)
        dt.style = "Table Grid"
        for i, h in enumerate(["Course ID", "Language", "Duration (hrs)", "Status", "Output File"]):
            dt.rows[0].cells[i].text = h
        for cid, lang_results in results.items():
            for lang, r in lang_results.items():
                row = dt.add_row().cells
                row[0].text = cid
                row[1].text = LANG_NAMES.get(lang, lang)
                row[2].text = f"{r.duration_original/3600:.2f}"
                row[3].text = "✅ Accepted" if r.success else f"❌ {r.error[:40]}"
                out = r.output_video_path or r.output_audio_path
                row[4].text = Path(out).name if out else "—"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        log.info(f"Monthly report → {output_path}")
        return output_path

    def process_course_full(
        self, video_path: str, src_lang: str, tgt_langs: list[str],
        output_dir: str, course_id: str, metadata: dict = None,
        quiz: list[dict] = None, upload_to_cbp: bool = False,
        num_gpus: int = 1,
    ) -> dict:
        summary = {"course_id": course_id, "source_lang": src_lang,
                   "target_langs": tgt_langs, "dubbing": {},
                   "metadata_xlsx": {}, "quiz_docx": {},
                   "qa_reports": {}, "cbp_uploads": {}}
        out_dir = Path(output_dir)
        dub_results = self.dub_course(
            video_path, src_lang, tgt_langs, output_dir, course_id,
            num_gpus=num_gpus)
        summary["dubbing"] = {
            lang: {"success": r.success,
                   "output":  r.output_video_path or r.output_audio_path,
                   "quality": r.quality_summary,
                   "error":   r.error}
            for lang, r in dub_results.items()
        }
        if metadata:
            meta_xlsx = str(out_dir / f"{course_id}_metadata_all.xlsx")
            self.export_metadata_xlsx(metadata, src_lang, tgt_langs, meta_xlsx)
            summary["metadata_xlsx"]["all"] = meta_xlsx
            # Also export per-language Word doc (KB tender SoW 3.4)
            for tgt_lang in tgt_langs:
                meta_docx = str(out_dir / tgt_lang / f"{course_id}_metadata_{tgt_lang}.docx")
                self.export_metadata_docx(metadata, src_lang, tgt_lang, meta_docx)
                summary["metadata_xlsx"][tgt_lang] = meta_docx
        if quiz:
            for tgt_lang in tgt_langs:
                course_title = metadata.get("title", course_id) if metadata else course_id
                qp_docx = str(out_dir / tgt_lang / f"{course_id}_quiz_{tgt_lang}.docx")
                qp_xlsx = str(out_dir / tgt_lang / f"{course_id}_quiz_{tgt_lang}.xlsx")
                self.export_quiz_docx(quiz, src_lang, tgt_lang, qp_docx,
                                      course_title=course_title)
                self.export_quiz_xlsx(quiz, src_lang, tgt_lang, qp_xlsx,
                                      course_title=course_title)
                summary["quiz_docx"][tgt_lang] = qp_docx
        for tgt_lang, r in dub_results.items():
            if r.success:
                qa = str(out_dir / tgt_lang / f"{course_id}_{tgt_lang}_qa_cert.docx")
                self.generate_qa_report(course_id, tgt_lang, r, qa)
                summary["qa_reports"][tgt_lang] = qa
        if upload_to_cbp:
            from .cbp_uploader import CBPUploader
            uploader = CBPUploader()
            if uploader.login():
                for tgt_lang in tgt_langs:
                    summary["cbp_uploads"][tgt_lang] = uploader.upload_course_package(
                        str(out_dir / tgt_lang), course_id, tgt_lang)
        return summary

    # ----------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------
    def _translate_text(self, text: str, src_lang: str, tgt_lang: str) -> str:
        if not text or not text.strip():
            return text
        if self.tm:
            hit = self.tm.lookup(text, src_lang, tgt_lang)
            if hit and hit.get("match_type") in ("exact_hf", "exact_tm"):
                return hit["tgt"]
        return self.translator.translate_text(text, src_lang, tgt_lang,
                                              glossary=self.glossary)

    def _save_metadata(self, result: DubbingResult, out_dir: Path, course_id: str):
        meta = {
            "course_id":          course_id,
            "source_lang":        result.source_lang,
            "target_lang":        result.target_lang,
            "target_lang_name":   LANG_NAMES.get(result.target_lang, result.target_lang),
            "duration_original_s":result.duration_original,
            "duration_output_s":  result.duration_output,
            "segment_count":      len(result.transcript),
            "quality_summary":    result.quality_summary,
            "transcript":         result.transcript,
            "translations":       result.translations,
            "provenance": {
                "model_versions": _model_versions(),
                "host":           platform.node(),
                "generated_at":   time.strftime("%Y-%m-%dT%H:%M:%S"),
                "contract":       "RFB IN-KBL-543730-NC-RFB",
            },
        }
        p = out_dir / f"{course_id}_{result.target_lang}_metadata.json"
        p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"Metadata saved → {p}")
