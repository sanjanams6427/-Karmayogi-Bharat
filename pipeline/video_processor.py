# ============================================================
# Video Processor - Extract audio, replace with dubbed audio,
# sync timing to match original video duration.
# Input:  MP4 video
# Output: MP4 video with dubbed audio track
# ============================================================

import os
import json
import tempfile
import subprocess
import logging
import numpy as np
import soundfile as sf
from pathlib import Path

log = logging.getLogger(__name__)

# Use bundled ffmpeg from imageio_ffmpeg if system ffmpeg not on PATH
try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"


class VideoProcessor:
    """
    Handles all video/audio operations using ffmpeg + librosa.
    No GPU required - pure CPU processing.
    """

    # ----------------------------------------------------------
    # Audio extraction
    # ----------------------------------------------------------
    def _run(self, args: list) -> int:
        """Run ffmpeg/ffprobe command, replacing 'ffmpeg'/'ffprobe' with bundled path."""
        if args[0] == "ffmpeg":
            args[0] = _FFMPEG
        elif args[0] == "ffprobe":
            # ffprobe lives next to ffmpeg binary
            import shutil
            ffprobe = shutil.which("ffprobe") or _FFMPEG.replace("ffmpeg", "ffprobe")
            args[0] = ffprobe
        result = subprocess.run(args, capture_output=True, timeout=600)
        return result.returncode

    def _probe(self, path: str) -> dict:
        """Get duration via ffprobe, fallback to librosa."""
        # Try ffprobe next to ffmpeg binary first
        ffprobe = str(Path(_FFMPEG).parent / "ffprobe.exe")
        if not Path(ffprobe).exists():
            import shutil
            ffprobe = shutil.which("ffprobe") or ""
        if ffprobe and Path(ffprobe).exists():
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "json", path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        # Fallback: parse Duration from ffmpeg stderr (works for MP4/MKV/WAV/MP3)
        result = subprocess.run(
            [_FFMPEG, "-i", path],
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE, timeout=60,
        )
        out = result.stdout.decode("utf-8", errors="replace")
        import re as _re
        m = _re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out)
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            dur = h * 3600 + mn * 60 + s
            return {"format": {"duration": str(dur)}}
        raise RuntimeError(f"Cannot determine duration for: {path}")

    def _has_audio_stream(self, video_path: str) -> bool:
        """Return True if the file has at least one audio stream."""
        result = subprocess.run(
            [_FFMPEG, "-i", str(video_path)],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, timeout=60,
        )
        return b"Audio:" in result.stderr

    def _reencode_input(self, video_path: str, tmp_path: str) -> str:
        """
        Re-encode input to a clean MP4 so ffmpeg can always read it.
        Handles corrupt containers, unusual codecs, Gradio temp copies.
        """
        Path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        ret = subprocess.run(
            [_FFMPEG, "-y", "-i", str(video_path),
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
             "-c:a", "aac", "-b:a", "128k", "-ac", "2",
             "-profile:a", "aac_low",
             "-movflags", "+faststart", str(tmp_path),
             "-loglevel", "error"],
            capture_output=True, timeout=600,
        )
        if ret.returncode != 0:
            subprocess.run(
                [_FFMPEG, "-y", "-i", str(video_path),
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                 "-an", str(tmp_path), "-loglevel", "error"],
                capture_output=True, timeout=600,
            )
        return tmp_path

    def extract_audio(self, video_path: str, output_wav: str, sample_rate: int = 16000) -> str:
        """Extract audio track from MP4 as WAV. Generates silence if no audio stream."""
        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        video_path = str(video_path)

        # If no audio stream → generate silence matching video duration
        if not self._has_audio_stream(video_path):
            print(f"[VP] No audio stream in {Path(video_path).name} — generating silence")
            duration = self.get_video_duration(video_path)
            ret = subprocess.run(
                [_FFMPEG, "-y", "-f", "lavfi",
                 "-i", f"anullsrc=r={sample_rate}:cl=mono",
                 "-t", str(duration), output_wav, "-loglevel", "error"],
                capture_output=True, timeout=60,
            ).returncode
            if ret != 0:
                # fallback: write numpy silence
                import soundfile as sf
                silence = np.zeros(int(duration * sample_rate), dtype=np.float32)
                sf.write(output_wav, silence, sample_rate)
            return output_wav

        # Normal extraction
        ret = subprocess.run(
            [_FFMPEG, "-y", "-i", video_path,
             "-ar", str(sample_rate), "-ac", "1", "-vn", output_wav,
             "-loglevel", "error"],
            capture_output=True, timeout=600,
        ).returncode

        if ret != 0:
            print(f"[VP] Extraction failed, re-encoding input: {Path(video_path).name}")
            tmp = str(Path(output_wav).parent / "_reenc_input.mp4")
            self._reencode_input(video_path, tmp)
            ret2 = subprocess.run(
                [_FFMPEG, "-y", "-i", tmp,
                 "-ar", str(sample_rate), "-ac", "1", "-vn", output_wav,
                 "-loglevel", "error"],
                capture_output=True, timeout=600,
            ).returncode
            if ret2 != 0:
                raise RuntimeError(f"Audio extraction failed for {Path(video_path).name}")
        return output_wav

    def convert_audio(self, input_path: str, output_path: str, sample_rate: int = 44100) -> str:
        """Convert any audio format to another via ffmpeg."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        ret = subprocess.run(
            [_FFMPEG, "-y", "-i", str(input_path),
             "-ar", str(sample_rate), "-ac", "1", str(output_path),
             "-loglevel", "error"],
            capture_output=True, timeout=600,
        ).returncode
        if ret != 0:
            raise RuntimeError(f"ffmpeg audio conversion failed: {input_path}")
        return output_path

    def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of an audio file in seconds."""
        try:
            data = self._probe(str(audio_path))
            return float(data["format"]["duration"])
        except Exception:
            import librosa
            y, sr = librosa.load(str(audio_path), sr=None)
            return len(y) / sr

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        # Use ffprobe with video stream duration as fallback
        result = subprocess.run(
            [_FFMPEG, "-i", str(video_path)],
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE, timeout=60,
        )
        out = result.stdout.decode("utf-8", errors="replace")
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out)
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mn * 60 + s
        try:
            data = self._probe(str(video_path))
            return float(data["format"]["duration"])
        except Exception:
            return 0.0

    # ----------------------------------------------------------
    # Audio segmentation (for per-sentence TTS)
    # ----------------------------------------------------------
    def segment_audio_by_silence(
        self, wav_path: str, min_silence_ms: int = 500
    ) -> list[dict]:
        """
        Split audio into segments based on silence.
        Returns: [{"id": 0, "start": 0.0, "end": 2.3, "duration": 2.3}, ...]
        """
        import librosa
        y, sr = librosa.load(wav_path, sr=16000)
        # Use librosa effects to find non-silent intervals
        intervals = librosa.effects.split(y, top_db=30, frame_length=512, hop_length=128)
        segments = []
        for i, (start_sample, end_sample) in enumerate(intervals):
            start = start_sample / sr
            end = end_sample / sr
            segments.append({
                "id": i,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
            })
        return segments

    # ----------------------------------------------------------
    # Audio time-stretching for sync
    # ----------------------------------------------------------
    def stretch_audio_to_duration(
        self, audio_path: str, target_duration: float, output_path: str
    ) -> str:
        """
        Time-stretch audio using ffmpeg atempo (cleaner than librosa).
        Chains multiple atempo filters for ratios outside 0.5-2.0 range.
        """
        import soundfile as sf
        info = sf.info(audio_path)
        current_duration = info.duration

        if abs(current_duration - target_duration) < 0.05:
            import shutil
            shutil.copy(audio_path, output_path)
            return output_path

        ratio = current_duration / target_duration
        ratio = max(0.5, min(4.0, ratio))  # atempo minimum is 0.5 per stage

        # ffmpeg atempo only supports 0.5-2.0 per filter — chain if needed
        if ratio <= 0.5:
            atempo = f"atempo=0.5,atempo={ratio/0.5:.4f}"
        elif ratio >= 2.0:
            atempo = f"atempo=2.0,atempo={ratio/2.0:.4f}"
        else:
            atempo = f"atempo={ratio:.4f}"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [_FFMPEG, "-y", "-i", str(audio_path),
             "-filter:a", atempo, str(output_path), "-loglevel", "error"],
            capture_output=True, timeout=300,
        )
        return output_path

    def _atempo_stretch_file(self, audio: np.ndarray, sr: int, ratio: float) -> np.ndarray:
        """
        Time-stretch using ffmpeg atempo (time-domain, no phase smearing).
        ratio > 1 = speed up. Chains filters for ratios outside 0.5-2.0.
        Falls back to original on error.
        """
        if abs(ratio - 1.0) < 0.02:
            return audio
        # Clamp to sane range — beyond 3x is unintelligible anyway
        ratio = max(0.5, min(3.0, ratio))
        # Build chained atempo filter — each stage must be in [0.5, 2.0]
        if ratio > 2.0:
            # e.g. ratio=2.5 → atempo=2.0,atempo=1.25
            atempo = f"atempo=2.0,atempo={ratio/2.0:.4f}"
        elif ratio < 0.5:
            atempo = f"atempo=0.5,atempo={ratio/0.5:.4f}"
        else:
            atempo = f"atempo={ratio:.4f}"
        import tempfile
        with tempfile.NamedTemporaryFile(suffix="_in.wav", delete=False) as fi, \
             tempfile.NamedTemporaryFile(suffix="_out.wav", delete=False) as fo:
            in_path, out_path = fi.name, fo.name
        try:
            sf.write(in_path, audio, sr)
            subprocess.run(
                [_FFMPEG, "-y", "-i", in_path,
                 "-filter:a", atempo,
                 out_path, "-loglevel", "error"],
                capture_output=True, check=True, timeout=300,
            )
            stretched, _ = sf.read(out_path, dtype="float32")
            return stretched
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"atempo stretch failed (ratio={ratio:.3f}): {e} — using original")
            return audio
        finally:
            for p in (in_path, out_path):
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass

    def extract_bgm(self, video_path: str, output_wav: str, sample_rate: int = 44100) -> str:
        """Extract original audio from video for BGM mixing. Returns path or empty string."""
        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        ret = subprocess.run(
            [_FFMPEG, "-y", "-i", str(video_path),
             "-ar", str(sample_rate), "-ac", "1", "-vn", output_wav,
             "-loglevel", "error"],
            capture_output=True, timeout=600,
        ).returncode
        return output_wav if ret == 0 and Path(output_wav).exists() else ""

    def assemble_dubbed_audio(
        self,
        segments: list[dict],
        original_duration: float,
        output_wav: str,
        sample_rate: int = 44100,
        bgm_path: str = None,
        bgm_volume: float = 0.18,
    ) -> str:
        """
        Slot-locked dubbing assembly (video-synced).

        Each segment is ANCHORED at its original start timestamp so the dubbed
        voice stays aligned with the on-screen speaker for the entire video —
        there is NO cumulative push-forward drift. A segment longer than its slot
        is time-compressed (atempo, pitch-preserving) up to MAX_SPEED; if it is
        still longer it may extend into the following silent gap only, and is
        clipped at the next segment's anchor so two voices never overlap. Output
        length matches the original video (no freeze-frame tail needed).

        Guarantees:
          - Every segment starts exactly at its original timestamp (video sync).
          - No cumulative drift; subtitles resync to these anchored positions.
          - No overlapping voices (tail clipped at next anchor in extreme cases).
        """
        import logging as _log
        _vp_log = _log.getLogger(__name__)

        FADE_IN_MS  = int(0.005 * sample_rate)   # 5ms click-kill fade-in
        FADE_OUT_MS = int(0.020 * sample_rate)   # 20ms fade-out — VITS endings are abrupt
        # Slot-locked sync: each segment is ANCHORED to its original start time so
        # the dubbed voice stays aligned with the on-screen speaker for the whole
        # video (no cumulative push-forward drift). A segment longer than its slot
        # is time-compressed (atempo, pitch-preserving) up to MAX_SPEED; if it is
        # still longer it may run into the FOLLOWING gap only (bounded by the next
        # segment's start), so it never pushes later segments and never drifts.
        MAX_SPEED   = 1.6   # allow a little more compression than before (was 1.35)
                            # so dense segments fit their slot and stay in sync.

        # ── Pre-load all segment audio ────────────────────────────────────────
        loaded: list = []
        for seg in segments:
            ap = seg.get("audio_path", "")
            if not ap or not Path(ap).exists():
                loaded.append(None)
                continue
            try:
                wav, tts_sr = sf.read(ap, dtype="float32", always_2d=False)
                if wav.ndim > 1:
                    wav = wav.mean(axis=1)
                if tts_sr != sample_rate:
                    import librosa
                    wav = librosa.resample(wav, orig_sr=tts_sr, target_sr=sample_rate)
                loaded.append(wav if len(wav) > 0 else None)
            except Exception as e:
                _vp_log.warning(f"[assemble] Could not load {ap}: {e}")
                loaded.append(None)

        # ── Allocate output buffer ────────────────────────────────────────────
        # Slot-locked: output length tracks the original video. Keep a small 5s
        # margin only for a final segment that overflows its last slot (bounded).
        total_samp  = max(int(original_duration * sample_rate), 1)
        buffer_samp = total_samp + int(5.0 * sample_rate)
        output_audio = np.zeros(buffer_samp, dtype=np.float32)

        # Track the actual placed start/end sample of each segment so the
        # comfort-noise mask, BGM ducking, and subtitle resync are built from
        # real placed audio positions.
        placed_start: list[int] = []   # parallel to segments
        placed_end: list[int] = []     # parallel to segments

        # ── Place each segment (slot-locked) ──────────────────────────────────
        # Each segment is anchored at its ORIGINAL start timestamp. To decide how
        # much a long segment may overflow, we need the next segment's original
        # start, so precompute the anchor starts first.
        n_seg = len(segments)
        anchor_start = [int(seg.get("start", 0) * sample_rate) for seg in segments]

        for i, (seg, seg_audio) in enumerate(zip(segments, loaded)):
            start_samp = anchor_start[i]
            if seg_audio is None:
                placed_start.append(start_samp)
                placed_end.append(start_samp)
                continue

            orig_start_samp = anchor_start[i]
            orig_end_samp   = int(seg.get("end", seg.get("start", 0)) * sample_rate)
            slot_samp       = max(orig_end_samp - orig_start_samp, int(0.1 * sample_rate))

            # Available room = own slot + the gap until the NEXT segment starts.
            # Overflowing into the following gap is allowed (it is silence anyway)
            # but we NEVER move this segment's start or the next segment's start,
            # so there is zero cumulative drift — the voice stays locked to video.
            next_start = anchor_start[i + 1] if i + 1 < n_seg else (orig_end_samp + slot_samp)
            room_samp  = max(slot_samp, next_start - orig_start_samp)

            audio_len = len(seg_audio)
            final_audio = seg_audio
            # Time-compress to fit the available room, capped at MAX_SPEED so it
            # never sounds chipmunk-fast. Pitch is preserved (atempo).
            # A per-segment cap > 1.0 (segment editor SPEED_UP strategy with a
            # user-set max speed) overrides the global cap; <= 1.0 or absent
            # means "no per-segment preference" and uses the global MAX_SPEED.
            # This field used to be passed by both stitch paths and silently
            # ignored here — the UI's per-segment max-speed did nothing.
            seg_cap = seg.get("max_speed") or 0
            eff_max = seg_cap if seg_cap > 1.0 else MAX_SPEED
            if audio_len > room_samp:
                ratio = min(audio_len / room_samp, eff_max)
                if ratio > 1.01:
                    stretched = self._atempo_stretch_file(seg_audio, sample_rate, ratio)
                    if len(stretched) > 0:
                        final_audio = stretched
                        audio_len   = len(stretched)

            # 5ms/20ms click-kill fades (no forced word trim).
            final_audio = final_audio.copy()

            # Overlap guard: keep starts locked to the video, so if a segment is
            # STILL longer than the room even after max compression, prevent it
            # from bleeding over the next segment's voice. Clip the tail to the
            # next anchor (rare — only for extremely dense segments) and apply a
            # fade so the clip is not an abrupt cut. This preserves sync and
            # avoids two overlapping voices, which is worse than a tiny tail loss.
            if i + 1 < n_seg:
                max_len = max(int(0.1 * sample_rate), next_start - start_samp)
                if len(final_audio) > max_len:
                    final_audio = final_audio[:max_len]

            fi = min(FADE_IN_MS, len(final_audio) // 8)
            if fi > 0:
                final_audio[:fi] *= np.linspace(0.0, 1.0, fi)
            fo = min(FADE_OUT_MS, len(final_audio) // 8)
            if fo > 0:
                final_audio[-fo:] *= np.linspace(1.0, 0.0, fo)

            need = start_samp + len(final_audio)
            if need > len(output_audio):
                output_audio = np.concatenate(
                    [output_audio,
                     np.zeros(need - len(output_audio) + sample_rate, dtype=np.float32)])

            end_samp = start_samp + len(final_audio)
            output_audio[start_samp:end_samp] += final_audio
            placed_start.append(start_samp)
            placed_end.append(end_samp)

            # Write placed timings back so subtitle generation resyncs SRT/VTT to
            # the actual dubbed audio positions (now == original stamps, so the
            # subtitle blocks match the video and are no longer 30-60s long).
            seg["placed_start"] = start_samp / sample_rate
            seg["placed_end"]   = end_samp / sample_rate

        # ── Trim/pad to cover all placed audio, then pad to original_duration ─
        # Never trim below the last placed segment's end so the final word
        # is never cut off. Pad with silence if shorter than original.
        if placed_end:
            last_placed = max(placed_end)
            # Use whichever is longer: original duration or last placed audio end
            final_samp = max(int(original_duration * sample_rate), last_placed)
            final_samp = min(final_samp, len(output_audio))
        else:
            final_samp = int(original_duration * sample_rate)
        if len(output_audio) < final_samp:
            output_audio = np.concatenate(
                [output_audio, np.zeros(final_samp - len(output_audio), dtype=np.float32)])
        else:
            output_audio = output_audio[:final_samp]

        # ── Comfort noise in silence gaps ─────────────────────────────────────
        # Production-ready output uses TRUE digital silence in gaps. Any injected
        # comfort/pink noise (previously 0.002, then 0.0004) was audible on quiet
        # playback and headphones as a faint background hiss between every
        # segment — reported as "noise in the silence". Set to 0.0 so gaps are
        # clean silence. Keep the masking scaffold behind a guard so re-enabling
        # a small comfort level later is a one-line change if ever needed.
        COMFORT_LEVEL = 0.0
        if COMFORT_LEVEL > 0.0:
            rng = np.random.default_rng(seed=42)
            speech_mask = np.zeros(final_samp, dtype=np.float32)
            for ps, pe in zip(placed_start, placed_end):
                s = min(ps, final_samp)
                e = min(pe, final_samp)
                if e > s:
                    speech_mask[s:e] = 1.0
            # 50ms smooth so comfort noise fades in/out at segment edges
            smooth_len = int(0.050 * sample_rate)
            from scipy.ndimage import uniform_filter1d
            speech_mask = uniform_filter1d(speech_mask.astype(np.float64),
                                           size=smooth_len).astype(np.float32)
            gap_mask = np.clip(1.0 - speech_mask, 0.0, 1.0)
            white = rng.standard_normal(final_samp).astype(np.float32)
            pink  = (white
                     + np.concatenate([np.zeros(3,  dtype=np.float32), white[:-3]])
                     + np.concatenate([np.zeros(7,  dtype=np.float32), white[:-7]])) / 3.0
            output_audio[:final_samp] += pink * gap_mask * COMFORT_LEVEL

        # ── BGM mix ───────────────────────────────────────────────────────────
        if bgm_path and Path(bgm_path).exists():
            try:
                bgm, bgm_sr = sf.read(bgm_path, dtype="float32", always_2d=False)
                if bgm.ndim > 1:
                    bgm = bgm.mean(axis=1)
                if bgm_sr != sample_rate:
                    # Use scipy for resampling to avoid librosa numba issues
                    from scipy import signal
                    num_samples = int(len(bgm) * sample_rate / bgm_sr)
                    bgm = signal.resample(bgm, num_samples).astype(np.float32)
                if len(bgm) < final_samp:
                    bgm = np.concatenate(
                        [bgm, np.zeros(final_samp - len(bgm), dtype=np.float32)])
                else:
                    bgm = bgm[:final_samp]
                duck_mask = np.full(final_samp, bgm_volume, dtype=np.float32)
                fade_d    = int(0.05 * sample_rate)
                for i, (ps, pe) in enumerate(zip(placed_start, placed_end)):
                    if loaded[i] is None:
                        continue
                    s = min(ps, final_samp)
                    e = min(pe + int(0.15 * sample_rate), final_samp)
                    duck_mask[s:e] = bgm_volume * 0.4
                    if fade_d > 0 and e > s:
                        fs = min(fade_d, e - s)
                        duck_mask[s:s + fs] = np.linspace(bgm_volume, bgm_volume * 0.4, fs)
                        fe = min(fade_d, e - s)
                        duck_mask[e - fe:e]  = np.linspace(bgm_volume * 0.4, bgm_volume, fe)
                output_audio[:final_samp] += bgm * duck_mask
            except Exception as _bgm_err:
                import logging
                logging.getLogger(__name__).warning(
                    f"BGM mix failed: {_bgm_err} — skipping BGM")

        # ── Normalize to -1 dBFS ──────────────────────────────────────────────
        np.clip(output_audio, -1.0, 1.0, out=output_audio)
        peak = np.max(np.abs(output_audio))
        if peak > 0.01:
            output_audio *= (0.708 / peak)  # -3 dBFS — iOS AAC headroom

        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        # Upmix mono → stereo: duplicate channel so iOS AAC encoder gets stereo input.
        # All TTS engines output mono; stereo is required for iOS AVFoundation AAC.
        if output_audio.ndim == 1:
            output_audio = np.stack([output_audio, output_audio], axis=1)
        sf.write(output_wav, output_audio, sample_rate, subtype="PCM_16")
        return output_wav

    # ----------------------------------------------------------
    # Replace audio in video
    # ----------------------------------------------------------
    def replace_audio_in_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        srt_path: str = None,
        lang: str = "",
        is_webm: bool = False,
    ) -> str:
        """
        Replace the audio track in a video with dubbed audio.
        WebM inputs are re-encoded (VP8/VP9 cannot be stream-copied into MP4).
        Subtitles are delivered as external SRT/VTT files only -- not burned into video.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        video_dur = self.get_video_duration(video_path)
        audio_dur = self.get_audio_duration(audio_path)

        # Dubbed audio may be longer than the video because translated speech
        # takes longer to say (push-forward assembly). ALWAYS extend the video
        # with a freeze-frame tail to match — never trim the audio, so the last
        # sentence is never cut. The assembly step already trims the silence
        # buffer, so audio_dur reflects real speech content.
        work_audio = audio_path
        work_video = video_path
        if audio_dur > video_dur + 0.1:
            # Pad video with freeze-frame tail to match dubbed audio length.
            # tpad clones the last frame for the overflow duration.
            pad_dur = audio_dur - video_dur
            padded_video = str(Path(output_path).parent / "_padded_video.mp4")
            ret = subprocess.run(
                [_FFMPEG, "-y", "-i", str(video_path),
                 "-vf", f"tpad=stop_mode=clone:stop_duration={pad_dur:.3f}",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                 "-an", padded_video, "-loglevel", "error"],
                capture_output=True, timeout=300,
            ).returncode
            if ret == 0 and Path(padded_video).exists():
                work_video = padded_video
                is_webm = False  # already re-encoded
            else:
                log.warning(f"[VP] freeze-frame pad failed for {Path(video_path).name} — using original video")

        # Mux video + dubbed audio.
        # WebM must re-encode video (VP8/VP9 cannot be stream-copied into MP4).
        # Use -t to set output duration to whichever is longer (video or audio)
        # so the final sentence is never cut by -shortest.
        work_audio_dur = self.get_audio_duration(work_audio)
        output_dur = max(video_dur, work_audio_dur)
        v_codec = ["libx264", "-preset", "fast", "-crf", "23"] if is_webm else ["copy"]
        # -t output_dur: set explicit output duration to whichever is longer
        # (video or dubbed audio). Without this ffmpeg defaults to the shorter
        # stream, silently cutting off the final sentence when audio > video.
        cmd = [_FFMPEG, "-y",
               "-i", str(work_video),
               "-i", str(work_audio),
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v"] + v_codec + [
               "-c:a", "aac", "-b:a", "192k", "-ac", "2",
               "-t", f"{output_dur:.3f}",
               "-movflags", "+faststart",
               "-profile:a", "aac_low",
               "-avoid_negative_ts", "make_zero",
               str(output_path),
               "-loglevel", "error"]

        ret = subprocess.run(cmd, capture_output=True, timeout=600).returncode
        if ret != 0:
            # Fallback: re-encode input video first
            tmp = str(Path(output_path).parent / "_reenc_input.mp4")
            self._reencode_input(work_video, tmp)
            cmd[cmd.index(str(work_video))] = tmp
            ret2 = subprocess.run(cmd, capture_output=True, timeout=600).returncode
            if ret2 != 0:
                raise RuntimeError(
                    f"replace_audio_in_video failed for {Path(video_path).name}"
                )

        # Clean up temp files
        if work_audio != audio_path:
            try:
                Path(work_audio).unlink(missing_ok=True)
            except Exception:
                pass
        if work_video != video_path:
            try:
                Path(work_video).unlink(missing_ok=True)
            except Exception:
                pass

        return output_path
