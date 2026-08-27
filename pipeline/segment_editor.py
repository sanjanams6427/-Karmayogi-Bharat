# ============================================================
# Segment Editor — Interactive Dubbing Workflow
#
# Instead of one-shotting the entire video, this module enables:
#   1. Extract & Preview — ASR the video, show all segments
#   2. Edit Before Translation — skip, keep-original, adjust
#   3. Translate & Review — segment by segment, see duration
#   4. TTS & Preview — hear each segment before committing
#   5. Adjust & Re-run — fix individual segments
#   6. Stitch — assemble only approved segments
#
# This is how professional dubbing studios work.
# ============================================================

from __future__ import annotations
import json
import hashlib
import shutil
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import numpy as np
import soundfile as sf

from .logger import get_logger
from .lang_config import LANG_NAMES

log = get_logger("segment_editor")


class SegmentAction(Enum):
    """What to do with each segment during dubbing."""
    TRANSLATE = "translate"       # Normal: translate + TTS
    SKIP = "skip"                 # Don't include in output (silence)
    KEEP_ORIGINAL = "keep_orig"   # Use original audio unchanged
    PENDING = "pending"           # Not yet decided


class FitStrategy(Enum):
    """How to handle duration mismatch between TTS audio and original video segment."""
    SPEED_UP = "speed_up"         # Speed up audio to fit original timing (default)
    EXTEND_VIDEO = "extend_video" # Extend video segment (freeze/slow-mo) to fit audio
    TRIM_AUDIO = "trim_audio"     # Hard trim audio (may cut off words)
    AUTO = "auto"                 # Let system decide based on overflow amount


@dataclass
class Segment:
    """A single segment in the editing session."""
    id: int
    start: float                  # Original timestamp (seconds)
    end: float                    # Original end timestamp
    source_text: str              # ASR output (source language)
    detected_lang: str = ""       # Per-segment detected language
    
    # Editing state
    action: SegmentAction = SegmentAction.PENDING
    fit_strategy: FitStrategy = FitStrategy.AUTO  # How to handle duration mismatch
    
    # Translation
    translated_text: str = ""
    translation_engine: str = ""
    translation_score: float = 0.0
    translation_flags: list = field(default_factory=list)
    
    # TTS
    tts_audio_path: str = ""
    tts_duration: float = 0.0
    tts_engine: str = ""
    max_speed: float = 1.35       # Per-segment speed limit (for SPEED_UP strategy)
    
    # Video preview
    thumbnail_path: str = ""      # Frame thumbnail for UI preview
    video_clip_path: str = ""     # Short clip of this segment for preview
    
    # Adjusted timing (after fit strategy applied)
    adjusted_start: float = -1.0  # -1 means use original
    adjusted_end: float = -1.0    # -1 means use original
    
    # Approval
    approved: bool = False
    reviewer_notes: str = ""
    
    @property
    def original_duration(self) -> float:
        return max(self.end - self.start, 0.01)
    
    @property
    def final_start(self) -> float:
        """Start time after adjustments."""
        return self.adjusted_start if self.adjusted_start >= 0 else self.start
    
    @property
    def final_end(self) -> float:
        """End time after adjustments."""
        return self.adjusted_end if self.adjusted_end >= 0 else self.end
    
    @property
    def final_duration(self) -> float:
        """Duration after adjustments."""
        return max(self.final_end - self.final_start, 0.01)
    
    @property
    def duration_ratio(self) -> float:
        """TTS duration / original duration. >1.0 means overflow."""
        if self.tts_duration <= 0 or self.original_duration <= 0:
            return 1.0
        return self.tts_duration / self.original_duration
    
    @property
    def overflow_seconds(self) -> float:
        """How many seconds the TTS audio overflows the original slot."""
        if self.tts_duration <= 0:
            return 0.0
        return max(0, self.tts_duration - self.original_duration)
    
    @property
    def will_overflow(self) -> bool:
        """Will this segment overflow its original slot even after max speedup?"""
        return self.duration_ratio > self.max_speed
    
    @property
    def estimated_tts_duration(self) -> float:
        """Estimate TTS duration from translated text length.
        
        Rough heuristic: ~5 characters per second for most Indian languages.
        This is used BEFORE actual TTS to warn about potential overflow.
        """
        if not self.translated_text:
            return 0.0
        # Adjust for script density — Devanagari/Tamil are denser
        chars = len(self.translated_text)
        return chars / 5.0  # ~5 chars/sec average speaking rate
    
    @property
    def estimated_overflow(self) -> bool:
        """Will this segment likely overflow based on text length?"""
        est = self.estimated_tts_duration
        return est > self.original_duration * self.max_speed
    
    @property
    def extension_needed(self) -> float:
        """How much video extension needed if using EXTEND_VIDEO strategy."""
        if self.tts_duration <= 0 or self.tts_duration <= self.original_duration:
            return 0.0
        return self.tts_duration - self.original_duration
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "source_text": self.source_text,
            "detected_lang": self.detected_lang,
            "action": self.action.value,
            "fit_strategy": self.fit_strategy.value,
            "translated_text": self.translated_text,
            "translation_engine": self.translation_engine,
            "translation_score": self.translation_score,
            "translation_flags": self.translation_flags,
            "tts_audio_path": self.tts_audio_path,
            "tts_duration": self.tts_duration,
            "tts_engine": self.tts_engine,
            "max_speed": self.max_speed,
            "thumbnail_path": self.thumbnail_path,
            "video_clip_path": self.video_clip_path,
            "adjusted_start": self.adjusted_start,
            "adjusted_end": self.adjusted_end,
            "approved": self.approved,
            "reviewer_notes": self.reviewer_notes,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> Segment:
        return cls(
            id=d["id"],
            start=d["start"],
            end=d["end"],
            source_text=d["source_text"],
            detected_lang=d.get("detected_lang", ""),
            action=SegmentAction(d.get("action", "pending")),
            fit_strategy=FitStrategy(d.get("fit_strategy", "auto")),
            translated_text=d.get("translated_text", ""),
            translation_engine=d.get("translation_engine", ""),
            translation_score=d.get("translation_score", 0.0),
            translation_flags=d.get("translation_flags", []),
            tts_audio_path=d.get("tts_audio_path", ""),
            tts_duration=d.get("tts_duration", 0.0),
            tts_engine=d.get("tts_engine", ""),
            max_speed=d.get("max_speed", 1.35),
            thumbnail_path=d.get("thumbnail_path", ""),
            video_clip_path=d.get("video_clip_path", ""),
            adjusted_start=d.get("adjusted_start", -1.0),
            adjusted_end=d.get("adjusted_end", -1.0),
            approved=d.get("approved", False),
            reviewer_notes=d.get("reviewer_notes", ""),
        )


@dataclass
class EditSession:
    """
    A dubbing editing session.
    
    Workflow:
        1. Create session from video
        2. Review segments, mark skip/keep-original
        3. Translate segments (batch or one-by-one)
        4. Generate TTS for each segment
        5. Review audio, adjust as needed
        6. Stitch final output
    """
    session_id: str
    video_path: str
    source_lang: str
    target_lang: str
    output_dir: str
    
    # Video/audio info
    video_duration: float = 0.0
    source_wav_path: str = ""
    
    # Segments
    segments: list[Segment] = field(default_factory=list)
    
    # Session state
    step: str = "extract"  # extract → edit → translate → tts → review → stitch
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.updated_at = self.created_at
    
    @property
    def session_dir(self) -> Path:
        return Path(self.output_dir) / "sessions" / self.session_id
    
    @property
    def state_file(self) -> Path:
        return self.session_dir / "session_state.json"
    
    def save(self):
        """Persist session state to disk."""
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "session_id": self.session_id,
            "video_path": self.video_path,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "output_dir": self.output_dir,
            "video_duration": self.video_duration,
            "source_wav_path": self.source_wav_path,
            "step": self.step,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "segments": [s.to_dict() for s in self.segments],
        }
        self.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        log.info(f"[{self.session_id}] Session saved — {len(self.segments)} segments, step={self.step}")
    
    @classmethod
    def load(cls, session_dir: str | Path) -> EditSession:
        """Load session from disk."""
        state_file = Path(session_dir) / "session_state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"Session not found: {state_file}")
        state = json.loads(state_file.read_text(encoding="utf-8"))
        session = cls(
            session_id=state["session_id"],
            video_path=state["video_path"],
            source_lang=state["source_lang"],
            target_lang=state["target_lang"],
            output_dir=state["output_dir"],
            video_duration=state.get("video_duration", 0.0),
            source_wav_path=state.get("source_wav_path", ""),
            step=state.get("step", "extract"),
            created_at=state.get("created_at", ""),
            updated_at=state.get("updated_at", ""),
        )
        session.segments = [Segment.from_dict(s) for s in state.get("segments", [])]
        return session
    
    # ── Stats ─────────────────────────────────────────────────
    def stats(self) -> dict:
        """Get session statistics."""
        total = len(self.segments)
        by_action = {a.value: 0 for a in SegmentAction}
        translated = 0
        tts_done = 0
        approved = 0
        overflow_warning = 0
        
        for seg in self.segments:
            by_action[seg.action.value] += 1
            if seg.translated_text:
                translated += 1
            if seg.tts_audio_path and Path(seg.tts_audio_path).exists():
                tts_done += 1
            if seg.approved:
                approved += 1
            if seg.will_overflow or seg.estimated_overflow:
                overflow_warning += 1
        
        return {
            "total_segments": total,
            "by_action": by_action,
            "translated": translated,
            "tts_done": tts_done,
            "approved": approved,
            "overflow_warnings": overflow_warning,
            "ready_to_stitch": approved == total and total > 0,
        }


class SegmentEditor:
    """
    Main editor class — handles all segment-level operations.
    """
    
    def __init__(self):
        self._asr = None
        self._translator = None
        self._tts = None
        self._video = None
    
    @property
    def asr(self):
        if self._asr is None:
            from .asr import ASREngine
            self._asr = ASREngine()
        return self._asr
    
    @property
    def translator(self):
        if self._translator is None:
            from .translator import Translator
            self._translator = Translator()
        return self._translator
    
    @property
    def tts(self):
        if self._tts is None:
            from .tts import TTSEngine
            self._tts = TTSEngine()
        return self._tts
    
    @property
    def video(self):
        if self._video is None:
            from .video_processor import VideoProcessor
            self._video = VideoProcessor()
        return self._video
    
    # ══════════════════════════════════════════════════════════
    # STEP 1: Extract & Segment
    # ══════════════════════════════════════════════════════════
    def create_session(
        self,
        video_path: str,
        source_lang: str,
        target_lang: str,
        output_dir: str,
        course_id: str = "course",
    ) -> EditSession:
        """
        Create a new editing session from a video file.
        Extracts audio and runs ASR to get segments.
        """
        video_path = str(Path(video_path).resolve())
        session_id = hashlib.md5(
            f"{video_path}_{target_lang}_{time.time()}".encode()
        ).hexdigest()[:12]
        
        session = EditSession(
            session_id=session_id,
            video_path=video_path,
            source_lang=source_lang,
            target_lang=target_lang,
            output_dir=output_dir,
        )
        
        # Create session directory
        session.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract audio
        log.info(f"[{session_id}] Extracting audio from {Path(video_path).name}")
        source_wav = str(session.session_dir / "source.wav")
        self.video.extract_audio(video_path, source_wav, sample_rate=16000)
        session.source_wav_path = source_wav
        session.video_duration = self.video.get_video_duration(video_path)
        
        # Run ASR
        log.info(f"[{session_id}] Running ASR (source_lang={source_lang})")
        asr_segments = self.asr.transcribe_segments(source_wav, source_lang)
        
        # Convert to Segment objects
        for i, seg in enumerate(asr_segments):
            session.segments.append(Segment(
                id=i,
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                source_text=seg.get("text", "").strip(),
                detected_lang=seg.get("detected_lang", source_lang),
            ))
        
        session.step = "edit"
        session.save()
        
        log.info(f"[{session_id}] Session created — {len(session.segments)} segments")
        return session
    
    # ══════════════════════════════════════════════════════════
    # STEP 2: Pre-translation Editing
    # ══════════════════════════════════════════════════════════
    def set_segment_action(
        self,
        session: EditSession,
        segment_id: int,
        action: SegmentAction | str,
    ):
        """Mark a segment as translate/skip/keep-original."""
        if isinstance(action, str):
            action = SegmentAction(action)
        
        for seg in session.segments:
            if seg.id == segment_id:
                seg.action = action
                seg.approved = False  # Reset approval when action changes
                log.info(f"[{session.session_id}] Segment {segment_id} → {action.value}")
                session.save()
                return
        raise ValueError(f"Segment {segment_id} not found")
    
    def set_all_translate(self, session: EditSession):
        """Mark all segments for translation."""
        for seg in session.segments:
            if seg.action == SegmentAction.PENDING:
                seg.action = SegmentAction.TRANSLATE
        session.save()
    
    def auto_detect_skip(
        self,
        session: EditSession,
        skip_patterns: list[str] = None,
    ):
        """
        Auto-detect segments that should be skipped.
        
        Default patterns:
          - [Music], [Applause], etc.
          - Very short segments (<0.5s)
          - Empty segments
        """
        skip_patterns = skip_patterns or [
            r"\[.*\]",           # [Music], [Applause], etc.
            r"^\s*$",            # Empty
            r"^♪.*♪$",          # Music notes
        ]
        import re
        patterns = [re.compile(p, re.IGNORECASE) for p in skip_patterns]
        
        skipped = 0
        for seg in session.segments:
            if seg.action != SegmentAction.PENDING:
                continue
            
            # Skip very short segments
            if seg.original_duration < 0.5:
                seg.action = SegmentAction.SKIP
                skipped += 1
                continue
            
            # Skip pattern matches
            for pat in patterns:
                if pat.match(seg.source_text):
                    seg.action = SegmentAction.SKIP
                    skipped += 1
                    break
        
        session.save()
        log.info(f"[{session.session_id}] Auto-skip marked {skipped} segments")
        return skipped
    
    # ══════════════════════════════════════════════════════════
    # STEP 3: Translate (with preview)
    # ══════════════════════════════════════════════════════════
    def translate_segment(
        self,
        session: EditSession,
        segment_id: int,
        glossary=None,
    ) -> Segment:
        """Translate a single segment."""
        seg = self._get_segment(session, segment_id)
        
        if seg.action != SegmentAction.TRANSLATE:
            log.warning(f"Segment {segment_id} is marked {seg.action.value}, not translate")
            return seg
        
        if not seg.source_text.strip():
            seg.translated_text = ""
            seg.translation_engine = "empty"
            seg.translation_score = 1.0
            session.save()
            return seg
        
        result = self.translator.translate(
            seg.source_text,
            session.source_lang,
            session.target_lang,
            glossary=glossary,
            detected_lang=seg.detected_lang,
        )
        
        seg.translated_text = result["text"]
        seg.translation_engine = result["engine"]
        seg.translation_score = result["score"]["score"]
        seg.translation_flags = result["score"].get("flags", [])
        seg.approved = False  # Reset approval
        
        session.save()
        log.info(f"[{session.session_id}] Translated seg {segment_id}: "
                 f"score={seg.translation_score:.2f}, engine={seg.translation_engine}")
        return seg
    
    def translate_all(
        self,
        session: EditSession,
        glossary=None,
        progress_callback: Callable[[int, int], None] = None,
    ) -> list[Segment]:
        """Translate all segments marked for translation."""
        to_translate = [
            s for s in session.segments
            if s.action == SegmentAction.TRANSLATE and not s.translated_text
        ]
        
        total = len(to_translate)
        for i, seg in enumerate(to_translate):
            self.translate_segment(session, seg.id, glossary=glossary)
            if progress_callback:
                progress_callback(i + 1, total)
        
        session.step = "tts"
        session.save()
        return to_translate
    
    def translate_batch(
        self,
        session: EditSession,
        glossary=None,
    ) -> list[Segment]:
        """
        Batch translate all segments at once (faster but no per-segment progress).
        """
        to_translate = [
            s for s in session.segments
            if s.action == SegmentAction.TRANSLATE and not s.translated_text
        ]
        
        if not to_translate:
            return []
        
        texts = [s.source_text for s in to_translate]
        detected = [s.detected_lang for s in to_translate]
        
        results = self.translator.translate_batch(
            texts,
            session.source_lang,
            session.target_lang,
            glossary=glossary,
            detected_langs=detected if session.source_lang != "eng" else None,
        )
        
        for seg, result in zip(to_translate, results):
            seg.translated_text = result["text"]
            seg.translation_engine = result["engine"]
            seg.translation_score = result["score"]["score"]
            seg.translation_flags = result["score"].get("flags", [])
            seg.approved = False
        
        session.step = "tts"
        session.save()
        log.info(f"[{session.session_id}] Batch translated {len(to_translate)} segments")
        return to_translate
    
    def edit_translation(
        self,
        session: EditSession,
        segment_id: int,
        new_text: str,
    ):
        """Manually edit a translation."""
        seg = self._get_segment(session, segment_id)
        seg.translated_text = new_text.strip()
        seg.translation_engine = "human_edit"
        seg.approved = False  # Reset approval — need to re-TTS and review
        
        # Clear TTS since translation changed
        if seg.tts_audio_path and Path(seg.tts_audio_path).exists():
            try:
                Path(seg.tts_audio_path).unlink()
            except Exception:
                pass
        seg.tts_audio_path = ""
        seg.tts_duration = 0.0
        
        session.save()
        log.info(f"[{session.session_id}] Segment {segment_id} translation edited manually")
    
    # ══════════════════════════════════════════════════════════
    # STEP 4: TTS (with preview)
    # ══════════════════════════════════════════════════════════
    def synthesize_segment(
        self,
        session: EditSession,
        segment_id: int,
    ) -> Segment:
        """Generate TTS audio for a single segment."""
        seg = self._get_segment(session, segment_id)
        
        if seg.action != SegmentAction.TRANSLATE:
            return seg
        
        if not seg.translated_text.strip():
            seg.tts_audio_path = ""
            seg.tts_duration = 0.0
            seg.tts_engine = "empty"
            session.save()
            return seg
        
        # Create TTS output directory
        tts_dir = session.session_dir / "tts"
        tts_dir.mkdir(exist_ok=True)
        
        # Synthesize
        out_path = str(tts_dir / f"seg_{segment_id:04d}.wav")
        
        # Use the TTS engine's single-segment synthesis
        tts_result = self.tts.synthesize_single(
            seg.translated_text,
            session.target_lang,
            out_path,
        )
        
        seg.tts_audio_path = tts_result.get("audio_path", out_path)
        seg.tts_duration = tts_result.get("duration", 0.0)
        seg.tts_engine = tts_result.get("engine", "unknown")
        seg.approved = False  # Need to review
        
        session.save()
        log.info(f"[{session.session_id}] TTS seg {segment_id}: "
                 f"dur={seg.tts_duration:.2f}s (orig={seg.original_duration:.2f}s, "
                 f"ratio={seg.duration_ratio:.2f}x)")
        return seg
    
    def synthesize_all(
        self,
        session: EditSession,
        progress_callback: Callable[[int, int], None] = None,
    ) -> list[Segment]:
        """Generate TTS for all translated segments."""
        to_synth = [
            s for s in session.segments
            if s.action == SegmentAction.TRANSLATE
            and s.translated_text
            and not (s.tts_audio_path and Path(s.tts_audio_path).exists())
        ]
        
        total = len(to_synth)
        for i, seg in enumerate(to_synth):
            self.synthesize_segment(session, seg.id)
            if progress_callback:
                progress_callback(i + 1, total)
        
        session.step = "review"
        session.save()
        return to_synth
    
    def set_segment_max_speed(
        self,
        session: EditSession,
        segment_id: int,
        max_speed: float,
    ):
        """Set the maximum speedup for a segment during assembly."""
        seg = self._get_segment(session, segment_id)
        seg.max_speed = max(1.0, min(2.0, max_speed))  # Clamp to 1.0-2.0
        session.save()
    
    # ══════════════════════════════════════════════════════════
    # STEP 5: Review & Approve
    # ══════════════════════════════════════════════════════════
    def approve_segment(
        self,
        session: EditSession,
        segment_id: int,
        notes: str = "",
    ):
        """Mark a segment as approved for final assembly."""
        seg = self._get_segment(session, segment_id)
        seg.approved = True
        seg.reviewer_notes = notes
        session.save()
    
    def reject_segment(
        self,
        session: EditSession,
        segment_id: int,
        notes: str = "",
    ):
        """Mark a segment as rejected — needs re-work."""
        seg = self._get_segment(session, segment_id)
        seg.approved = False
        seg.reviewer_notes = notes
        session.save()
    
    def approve_all_non_overflow(self, session: EditSession):
        """Auto-approve all segments that don't have overflow issues.
        
        Segments with EXTEND_VIDEO fit strategy are approved even if they overflow,
        because the video will be extended to accommodate them.
        """
        approved = 0
        for seg in session.segments:
            if seg.action == SegmentAction.SKIP:
                seg.approved = True
                approved += 1
            elif seg.action == SegmentAction.KEEP_ORIGINAL:
                seg.approved = True
                approved += 1
            elif seg.action == SegmentAction.TRANSLATE:
                if not seg.tts_audio_path:
                    continue  # No TTS yet, can't approve
                
                # EXTEND_VIDEO segments are always OK (video extends to fit)
                if seg.fit_strategy == FitStrategy.EXTEND_VIDEO:
                    seg.approved = True
                    approved += 1
                # SPEED_UP segments need to fit within max_speed
                elif seg.fit_strategy == FitStrategy.SPEED_UP:
                    if not seg.will_overflow:
                        seg.approved = True
                        approved += 1
                # AUTO — approve if it fits, or if extension is reasonable (<2x)
                elif seg.fit_strategy == FitStrategy.AUTO:
                    if not seg.will_overflow or seg.duration_ratio <= 2.0:
                        seg.approved = True
                        approved += 1
                # TRIM_AUDIO — always approve (user accepted trimming)
                elif seg.fit_strategy == FitStrategy.TRIM_AUDIO:
                    seg.approved = True
                    approved += 1
        
        session.save()
        log.info(f"[{session.session_id}] Auto-approved {approved} segments")
        return approved
    
    # ══════════════════════════════════════════════════════════
    # STEP 6: Stitch Final Output
    # ══════════════════════════════════════════════════════════
    def stitch(
        self,
        session: EditSession,
        output_video_path: str = None,
        mix_original_bgm: bool = True,
        bgm_volume: float = 0.15,
    ) -> dict:
        """
        Assemble the final dubbed video from approved segments.
        
        Returns dict with output paths and stats.
        """
        stats = session.stats()
        if not stats["ready_to_stitch"]:
            unapproved = [s.id for s in session.segments if not s.approved]
            raise ValueError(
                f"Not all segments approved. Unapproved: {unapproved[:10]}..."
                if len(unapproved) > 10 else f"Unapproved: {unapproved}"
            )
        
        # Build segment list for assembler
        assembly_segments = []
        for seg in session.segments:
            entry = {
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.translated_text,
                "audio_path": None,
                "max_speed": seg.max_speed,
            }
            
            if seg.action == SegmentAction.TRANSLATE and seg.tts_audio_path:
                entry["audio_path"] = seg.tts_audio_path
            elif seg.action == SegmentAction.KEEP_ORIGINAL:
                # Extract original audio for this segment
                orig_clip = str(session.session_dir / f"orig_seg_{seg.id:04d}.wav")
                self._extract_segment_audio(
                    session.source_wav_path, seg.start, seg.end, orig_clip
                )
                entry["audio_path"] = orig_clip
            # SKIP segments have no audio_path → silence in output
            
            assembly_segments.append(entry)
        
        # Assemble dubbed audio
        dubbed_wav = str(session.session_dir / "dubbed_final.wav")
        bgm_path = session.source_wav_path if mix_original_bgm else None
        
        self.video.assemble_dubbed_audio(
            assembly_segments,
            session.video_duration,
            dubbed_wav,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume,
        )
        
        # Mux into video
        if output_video_path is None:
            output_video_path = str(
                Path(session.output_dir) / session.target_lang /
                f"{Path(session.video_path).stem}_{session.target_lang}.mp4"
            )
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.video.replace_audio_in_video(
            session.video_path,
            dubbed_wav,
            output_video_path,
        )
        
        # Generate subtitles
        from .subtitles import generate_subtitles
        sub_segments = [
            {"id": s.id, "start": s.start, "end": s.end, "text": s.translated_text}
            for s in session.segments
            if s.action == SegmentAction.TRANSLATE and s.translated_text
        ]
        subtitle_paths = generate_subtitles(
            sub_segments,
            str(Path(output_video_path).parent),
            Path(output_video_path).stem.replace(f"_{session.target_lang}", ""),
            session.target_lang,
            video_duration=session.video_duration,
        )
        
        session.step = "done"
        session.save()
        
        result = {
            "success": True,
            "output_video": output_video_path,
            "output_audio": dubbed_wav,
            "srt_path": subtitle_paths.get("srt"),
            "vtt_path": subtitle_paths.get("vtt"),
            "stats": stats,
        }
        
        log.info(f"[{session.session_id}] Stitch complete → {output_video_path}")
        return result
    
    # ══════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════
    def _get_segment(self, session: EditSession, segment_id: int) -> Segment:
        for seg in session.segments:
            if seg.id == segment_id:
                return seg
        raise ValueError(f"Segment {segment_id} not found")
    
    def _extract_segment_audio(
        self,
        source_wav: str,
        start: float,
        end: float,
        output_path: str,
    ):
        """Extract a portion of audio from source WAV."""
        audio, sr = sf.read(source_wav, dtype="float32")
        start_sample = int(start * sr)
        end_sample = int(end * sr)
        segment_audio = audio[start_sample:end_sample]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, segment_audio, sr)
    
    # ══════════════════════════════════════════════════════════
    # Video Preview — Thumbnails & Clips
    # ══════════════════════════════════════════════════════════
    def extract_thumbnail(
        self,
        session: EditSession,
        segment_id: int,
    ) -> str:
        """Extract a thumbnail frame from the middle of a segment."""
        seg = self._get_segment(session, segment_id)
        thumb_dir = session.session_dir / "thumbnails"
        thumb_dir.mkdir(exist_ok=True)
        
        thumb_path = str(thumb_dir / f"seg_{segment_id:04d}.jpg")
        mid_time = (seg.start + seg.end) / 2
        
        import subprocess
        try:
            # Get ffmpeg path
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg = "ffmpeg"
            
            subprocess.run([
                ffmpeg, "-y",
                "-ss", f"{mid_time:.3f}",
                "-i", session.video_path,
                "-frames:v", "1",
                "-q:v", "2",
                thumb_path,
                "-loglevel", "error"
            ], check=True, timeout=30)
            
            seg.thumbnail_path = thumb_path
            session.save()
            return thumb_path
        except Exception as e:
            log.warning(f"Thumbnail extraction failed for segment {segment_id}: {e}")
            return ""
    
    def extract_all_thumbnails(
        self,
        session: EditSession,
        progress_callback: Callable[[int, int], None] = None,
    ):
        """Extract thumbnails for all segments."""
        total = len(session.segments)
        for i, seg in enumerate(session.segments):
            if not seg.thumbnail_path or not Path(seg.thumbnail_path).exists():
                self.extract_thumbnail(session, seg.id)
            if progress_callback:
                progress_callback(i + 1, total)
    
    def extract_video_clip(
        self,
        session: EditSession,
        segment_id: int,
    ) -> str:
        """Extract a short video clip for preview."""
        seg = self._get_segment(session, segment_id)
        clips_dir = session.session_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        clip_path = str(clips_dir / f"seg_{segment_id:04d}.mp4")
        
        import subprocess
        try:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg = "ffmpeg"
            
            duration = seg.original_duration
            subprocess.run([
                ffmpeg, "-y",
                "-ss", f"{seg.start:.3f}",
                "-i", session.video_path,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart",
                clip_path,
                "-loglevel", "error"
            ], check=True, timeout=120)
            
            seg.video_clip_path = clip_path
            session.save()
            return clip_path
        except Exception as e:
            log.warning(f"Clip extraction failed for segment {segment_id}: {e}")
            return ""
    
    # ══════════════════════════════════════════════════════════
    # Fit Strategy Control
    # ══════════════════════════════════════════════════════════
    def set_fit_strategy(
        self,
        session: EditSession,
        segment_id: int,
        strategy: FitStrategy | str,
    ):
        """Set how to handle duration mismatch for a segment."""
        if isinstance(strategy, str):
            strategy = FitStrategy(strategy)
        
        seg = self._get_segment(session, segment_id)
        seg.fit_strategy = strategy
        seg.approved = False  # Reset approval when strategy changes
        
        # If extending video, calculate new end time
        if strategy == FitStrategy.EXTEND_VIDEO and seg.tts_duration > 0:
            seg.adjusted_end = seg.start + seg.tts_duration
        elif strategy == FitStrategy.SPEED_UP:
            # Reset to original timing
            seg.adjusted_start = -1.0
            seg.adjusted_end = -1.0
        
        session.save()
        log.info(f"[{session.session_id}] Segment {segment_id} fit strategy → {strategy.value}")
    
    def auto_assign_fit_strategies(self, session: EditSession):
        """
        Auto-assign fit strategies based on overflow amount.
        
        Rules:
          - No overflow → SPEED_UP (1.0x, no change needed)
          - Overflow <= max_speed → SPEED_UP
          - Overflow > max_speed but < 2x → EXTEND_VIDEO
          - Overflow >= 2x → flag for manual intervention
        """
        for seg in session.segments:
            if seg.action != SegmentAction.TRANSLATE:
                continue
            if seg.tts_duration <= 0:
                continue
            
            ratio = seg.duration_ratio
            if ratio <= 1.0:
                # Audio fits perfectly or is shorter
                seg.fit_strategy = FitStrategy.SPEED_UP
            elif ratio <= seg.max_speed:
                # Can speed up to fit
                seg.fit_strategy = FitStrategy.SPEED_UP
            elif ratio <= 2.0:
                # Need to extend video
                seg.fit_strategy = FitStrategy.EXTEND_VIDEO
                seg.adjusted_end = seg.start + seg.tts_duration
            else:
                # Too much overflow — keep as AUTO for manual review
                seg.fit_strategy = FitStrategy.AUTO
        
        session.save()
        log.info(f"[{session.session_id}] Auto-assigned fit strategies")
    
    def get_total_extension(self, session: EditSession) -> float:
        """Calculate total video duration extension needed."""
        total_ext = 0.0
        for seg in session.segments:
            if seg.fit_strategy == FitStrategy.EXTEND_VIDEO:
                total_ext += seg.extension_needed
        return total_ext
    
    def get_final_duration(self, session: EditSession) -> float:
        """Calculate final video duration after all extensions."""
        return session.video_duration + self.get_total_extension(session)
    
    # ══════════════════════════════════════════════════════════
    # Extended Stitch (with video extension support)
    # ══════════════════════════════════════════════════════════
    def stitch_with_extensions(
        self,
        session: EditSession,
        output_video_path: str = None,
        mix_original_bgm: bool = True,
        bgm_volume: float = 0.15,
    ) -> dict:
        """
        Assemble final video with support for EXTEND_VIDEO segments.
        
        For segments marked EXTEND_VIDEO:
          - The video frame is frozen/extended to match TTS duration
          - Subsequent segments are shifted forward in time
        
        Returns dict with output paths, stats, and final duration.
        """
        stats = session.stats()
        if not stats["ready_to_stitch"]:
            unapproved = [s.id for s in session.segments if not s.approved]
            raise ValueError(
                f"Not all segments approved. Unapproved: {unapproved[:10]}..."
                if len(unapproved) > 10 else f"Unapproved: {unapproved}"
            )
        
        # Calculate time shifts from extensions
        time_shift = 0.0  # Cumulative shift
        segment_timings = []  # (seg, new_start, new_end, audio_path)
        
        for seg in session.segments:
            new_start = seg.start + time_shift
            
            if seg.action == SegmentAction.SKIP:
                new_end = seg.end + time_shift
                segment_timings.append((seg, new_start, new_end, None))
            
            elif seg.action == SegmentAction.KEEP_ORIGINAL:
                new_end = seg.end + time_shift
                # Extract original audio
                orig_clip = str(session.session_dir / f"orig_seg_{seg.id:04d}.wav")
                self._extract_segment_audio(
                    session.source_wav_path, seg.start, seg.end, orig_clip
                )
                segment_timings.append((seg, new_start, new_end, orig_clip))
            
            elif seg.action == SegmentAction.TRANSLATE:
                if seg.fit_strategy == FitStrategy.EXTEND_VIDEO and seg.tts_duration > seg.original_duration:
                    # Video will be extended — audio plays at natural speed
                    new_end = new_start + seg.tts_duration
                    extension = seg.tts_duration - seg.original_duration
                    time_shift += extension
                else:
                    # Audio will be sped up to fit original timing
                    new_end = new_start + seg.original_duration
                
                segment_timings.append((seg, new_start, new_end, seg.tts_audio_path))
            
            else:  # PENDING — shouldn't happen if approved
                new_end = seg.end + time_shift
                segment_timings.append((seg, new_start, new_end, None))
        
        final_duration = session.video_duration + time_shift
        
        # Build assembly segments with new timings
        assembly_segments = []
        for seg, new_start, new_end, audio_path in segment_timings:
            entry = {
                "id": seg.id,
                "start": new_start,
                "end": new_end,
                "original_start": seg.start,
                "original_end": seg.end,
                "text": seg.translated_text,
                "audio_path": audio_path,
                "max_speed": seg.max_speed if seg.fit_strategy == FitStrategy.SPEED_UP else 1.0,
                "fit_strategy": seg.fit_strategy.value,
            }
            assembly_segments.append(entry)
        
        # Create extended video if needed
        if time_shift > 0.1:  # More than 0.1s extension needed
            log.info(f"[{session.session_id}] Creating extended video (+{time_shift:.2f}s)")
            extended_video = str(session.session_dir / "extended_base.mp4")
            self._create_extended_video(
                session.video_path,
                segment_timings,
                extended_video,
                final_duration,
            )
            video_for_mux = extended_video
            # When video is extended, original BGM won't align - disable it
            # The extended video clips already contain their original audio track
            bgm_path = None
            log.info(f"[{session.session_id}] BGM disabled for extended video (timeline mismatch)")
        else:
            video_for_mux = session.video_path
            bgm_path = session.source_wav_path if mix_original_bgm else None
        
        # Assemble dubbed audio with new timings
        dubbed_wav = str(session.session_dir / "dubbed_final.wav")
        
        self.video.assemble_dubbed_audio(
            assembly_segments,
            final_duration,
            dubbed_wav,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume,
        )
        
        # Mux into video
        if output_video_path is None:
            output_video_path = str(
                Path(session.output_dir) / session.target_lang /
                f"{Path(session.video_path).stem}_{session.target_lang}.mp4"
            )
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.video.replace_audio_in_video(
            video_for_mux,
            dubbed_wav,
            output_video_path,
        )
        
        # Generate subtitles with adjusted timings
        from .subtitles import generate_subtitles
        sub_segments = [
            {"id": seg.id, "start": new_start, "end": new_end, "text": seg.translated_text}
            for seg, new_start, new_end, _ in segment_timings
            if seg.action == SegmentAction.TRANSLATE and seg.translated_text
        ]
        subtitle_paths = generate_subtitles(
            sub_segments,
            str(Path(output_video_path).parent),
            Path(output_video_path).stem.replace(f"_{session.target_lang}", ""),
            session.target_lang,
            video_duration=final_duration,
        )
        
        session.step = "done"
        session.save()
        
        result = {
            "success": True,
            "output_video": output_video_path,
            "output_audio": dubbed_wav,
            "srt_path": subtitle_paths.get("srt"),
            "vtt_path": subtitle_paths.get("vtt"),
            "stats": stats,
            "original_duration": session.video_duration,
            "final_duration": final_duration,
            "total_extension": time_shift,
        }
        
        log.info(f"[{session.session_id}] Extended stitch complete → {output_video_path} "
                 f"(+{time_shift:.2f}s = {final_duration:.2f}s total)")
        return result
    
    def _create_extended_video(
        self,
        source_video: str,
        segment_timings: list,
        output_path: str,
        final_duration: float,
    ):
        """
        Create extended video by inserting freeze frames where needed.
        
        For each EXTEND_VIDEO segment:
          - Take the last frame of that segment
          - Hold it for the extension duration
          - Then continue with the next segment
        """
        import subprocess
        import tempfile
        
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = "ffmpeg"
        
        # Build a filter complex for the extensions
        # Strategy: extract clips, add freeze frames, concatenate
        
        clips = []
        prev_end = 0.0
        temp_dir = Path(output_path).parent / "temp_clips"
        temp_dir.mkdir(exist_ok=True)
        
        for i, (seg, new_start, new_end, _) in enumerate(segment_timings):
            # Extract segment from original video
            clip_path = str(temp_dir / f"clip_{i:04d}.mp4")
            duration = seg.end - seg.start
            
            subprocess.run([
                ffmpeg, "-y",
                "-ss", f"{seg.start:.3f}",
                "-i", source_video,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-an",  # No audio in intermediate clips
                clip_path,
                "-loglevel", "error"
            ], check=True, timeout=120)
            clips.append(clip_path)
            
            # If this segment needs extension, add a freeze frame
            if seg.fit_strategy == FitStrategy.EXTEND_VIDEO and seg.tts_duration > seg.original_duration:
                extension = seg.tts_duration - seg.original_duration
                freeze_path = str(temp_dir / f"freeze_{i:04d}.mp4")
                
                # Extract last frame and loop it
                last_frame_time = seg.end - 0.1  # Slightly before end
                subprocess.run([
                    ffmpeg, "-y",
                    "-ss", f"{last_frame_time:.3f}",
                    "-i", source_video,
                    "-frames:v", "1",
                    "-vf", f"loop=loop={int(extension * 30)}:size=1:start=0,setpts=N/30/TB",
                    "-t", f"{extension:.3f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    freeze_path,
                    "-loglevel", "error"
                ], check=True, timeout=60)
                clips.append(freeze_path)
        
        # Create concat list
        concat_list = str(temp_dir / "concat.txt")
        with open(concat_list, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")
        
        # Concatenate all clips
        subprocess.run([
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            output_path,
            "-loglevel", "error"
        ], check=True, timeout=300)
        
        # Cleanup temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        log.info(f"Created extended video: {output_path}")


# ══════════════════════════════════════════════════════════════
# Convenience functions for UI
# ══════════════════════════════════════════════════════════════

def segments_to_table(session: EditSession) -> list[list]:
    """Convert session segments to a table for Gradio Dataframe."""
    rows = []
    for seg in session.segments:
        # Status emoji
        if seg.approved:
            status = "✅"
        elif seg.action == SegmentAction.SKIP:
            status = "⏭️"
        elif seg.action == SegmentAction.KEEP_ORIGINAL:
            status = "🔊"
        elif seg.will_overflow or seg.estimated_overflow:
            status = "⚠️"
        else:
            status = "⏳"
        
        # Duration info
        orig_dur = f"{seg.original_duration:.1f}s"
        if seg.tts_duration > 0:
            tts_dur = f"{seg.tts_duration:.1f}s ({seg.duration_ratio:.2f}x)"
        elif seg.translated_text:
            est = seg.estimated_tts_duration
            tts_dur = f"~{est:.1f}s (est)"
        else:
            tts_dur = "—"
        
        rows.append([
            seg.id,
            f"{seg.start:.1f}–{seg.end:.1f}",
            orig_dur,
            seg.source_text[:100] + ("..." if len(seg.source_text) > 100 else ""),
            seg.action.value,
            seg.translated_text[:100] + ("..." if len(seg.translated_text) > 100 else ""),
            tts_dur,
            f"{seg.translation_score:.2f}" if seg.translation_score else "—",
            status,
        ])
    return rows


def segments_to_table_extended(session: EditSession) -> list[list]:
    """Extended table with fit strategy and extension info."""
    rows = []
    for seg in session.segments:
        # Status emoji
        if seg.approved:
            status = "✅"
        elif seg.action == SegmentAction.SKIP:
            status = "⏭️"
        elif seg.action == SegmentAction.KEEP_ORIGINAL:
            status = "🔊"
        elif seg.will_overflow or seg.estimated_overflow:
            status = "⚠️"
        else:
            status = "⏳"
        
        # Fit strategy display
        fit_icons = {
            FitStrategy.SPEED_UP: "⏩",
            FitStrategy.EXTEND_VIDEO: "📹+",
            FitStrategy.TRIM_AUDIO: "✂️",
            FitStrategy.AUTO: "🔄",
        }
        fit_str = fit_icons.get(seg.fit_strategy, "🔄") + " " + seg.fit_strategy.value
        
        # Duration info
        orig_dur = f"{seg.original_duration:.1f}s"
        if seg.tts_duration > 0:
            ratio = seg.duration_ratio
            if seg.fit_strategy == FitStrategy.EXTEND_VIDEO:
                ext = seg.extension_needed
                tts_dur = f"{seg.tts_duration:.1f}s (+{ext:.1f}s ext)"
            else:
                tts_dur = f"{seg.tts_duration:.1f}s ({ratio:.2f}x)"
        elif seg.translated_text:
            est = seg.estimated_tts_duration
            tts_dur = f"~{est:.1f}s (est)"
        else:
            tts_dur = "—"
        
        rows.append([
            seg.id,
            f"{seg.start:.1f}–{seg.end:.1f}",
            orig_dur,
            seg.source_text[:80] + ("..." if len(seg.source_text) > 80 else ""),
            seg.action.value,
            seg.translated_text[:80] + ("..." if len(seg.translated_text) > 80 else ""),
            tts_dur,
            fit_str,
            f"{seg.translation_score:.2f}" if seg.translation_score else "—",
            status,
        ])
    return rows


def table_headers() -> list[str]:
    return [
        "ID", "Time", "Orig Dur", "Source Text", "Action",
        "Translation", "TTS Dur", "Score", "Status"
    ]


def table_headers_extended() -> list[str]:
    return [
        "ID", "Time", "Orig Dur", "Source Text", "Action",
        "Translation", "TTS Dur", "Fit", "Score", "Status"
    ]
