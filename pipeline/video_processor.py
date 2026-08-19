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
import numpy as np
import soundfile as sf
from pathlib import Path

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
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE, timeout=60,
        )
        return b"Audio:" in result.stdout

    def _reencode_input(self, video_path: str, tmp_path: str) -> str:
        """
        Re-encode input to a clean MP4 so ffmpeg can always read it.
        Handles corrupt containers, unusual codecs, Gradio temp copies.
        """
        Path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        ret = subprocess.run(
            [_FFMPEG, "-y", "-i", str(video_path),
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
             "-c:a", "aac", "-b:a", "128k",
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
        ratio = max(0.25, min(4.0, ratio))

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
        Place each TTS segment at its original timestamp in the output buffer.
        Strategy (in order):
          1. If audio fits in slot — place as-is.
          2. If audio overruns into the silence gap before next speech — allow overflow.
          3. If audio would overlap next segment's speech — speed up (max 1.35x).
          4. Only trim as last resort — always fade out over 150ms so no word is cut.
        Crossfade 30ms between adjacent segments for smooth transitions.
        """
        FADE_MS    = int(0.005 * sample_rate)  # 5ms fade in/out — just enough to kill DC click
        XFADE_MS   = 0                          # no crossfade — segments are time-separated
        MAX_SPEED  = 1.35
        TAIL_FADE  = int(0.150 * sample_rate)  # 150ms fade-out before any hard trim

        # Pre-load all audio
        loaded = []
        for seg in segments:
            if "audio_path" not in seg or not Path(seg["audio_path"]).exists():
                loaded.append(None)
                continue
            try:
                seg_audio, tts_sr = sf.read(seg["audio_path"], dtype="float32", always_2d=False)
                if seg_audio.ndim > 1:
                    seg_audio = seg_audio.mean(axis=1)
                if tts_sr != sample_rate:
                    import librosa
                    seg_audio = librosa.resample(seg_audio, orig_sr=tts_sr, target_sr=sample_rate)
                loaded.append(seg_audio if len(seg_audio) > 0 else None)
            except Exception:
                loaded.append(None)

        total_samp   = max(int(original_duration * sample_rate), 1)
        buffer_samp  = total_samp + int(10.0 * sample_rate)  # 10s tail
        output_audio = np.zeros(buffer_samp, dtype=np.float32)

        # For the last segment, extend total_samp to fit its full audio
        # so the final word is never cut by the original-duration trim below.
        if segments and loaded:
            last_seg   = segments[-1]
            last_audio = loaded[-1]
            if last_audio is not None:
                last_end = int(last_seg["start"] * sample_rate) + len(last_audio)
                if last_end > total_samp:
                    total_samp = min(last_end, buffer_samp)

        for i, (seg, seg_audio) in enumerate(zip(segments, loaded)):
            if seg_audio is None:
                continue

            start_samp = int(seg["start"] * sample_rate)

            # Find next segment that actually has speech
            next_speech_samp = buffer_samp
            for j in range(i + 1, len(segments)):
                if loaded[j] is not None and len(loaded[j]) > 0:
                    next_speech_samp = int(segments[j]["start"] * sample_rate)
                    break

            # Hard limit = next speech start minus 200ms breathing room.
            # Audio CAN freely overflow into the silence gap before next_speech_samp.
            # The 200ms buffer ensures the last word of this segment fully completes
            # before the next segment begins (was 0ms — caused last-word cut-off).
            # For the last segment (next_speech_samp == buffer_samp) there is no limit.
            is_last_seg = (next_speech_samp == buffer_samp)
            if is_last_seg:
                hard_limit = buffer_samp - start_samp  # no trim for last segment
            else:
                gap = next_speech_samp - start_samp
                hard_limit = max(gap + int(0.200 * sample_rate), int(0.1 * sample_rate))

            if len(seg_audio) > hard_limit:
                # Step 1: try speed-up to fit within hard_limit
                ratio     = min(len(seg_audio) / hard_limit, MAX_SPEED)
                stretched = self._atempo_stretch_file(seg_audio, sample_rate, ratio)

                if len(stretched) <= hard_limit:
                    seg_audio = stretched
                else:
                    # Step 2: must trim — fade out over 150ms so last word completes
                    seg_audio = stretched
                    cut      = hard_limit
                    fade_len = min(TAIL_FADE, cut // 2)
                    seg_audio[cut - fade_len:cut] *= np.linspace(1.0, 0.0, fade_len)
                    seg_audio = seg_audio[:cut]

            # 5ms fade-in/out — kills DC click only, no audible gap
            fade_in = min(FADE_MS, len(seg_audio) // 6)
            if fade_in > 0:
                seg_audio[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
            fade_out = min(FADE_MS, len(seg_audio) // 6)
            if fade_out > 0:
                seg_audio[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)

            # Write full seg_audio — never clamp to slot end, only to buffer
            end_samp = min(start_samp + len(seg_audio), buffer_samp)
            output_audio[start_samp:end_samp] = seg_audio[:end_samp - start_samp]

        # Trim back to original duration
        output_audio = output_audio[:total_samp]

        # Add comfort noise in silence gaps between segments
        # This eliminates the jarring dead-silence between sentences and gives
        # a natural "room tone" feel — same as professional dubbing studios use.
        # Level: -42 dBFS (inaudible as noise, but fills the perceptual gap)
        COMFORT_LEVEL = 0.002  # -54dBFS — truly inaudible room tone, not a hiss
        rng = np.random.default_rng(seed=42)  # fixed seed = same noise every run
        # Build a speech mask: 1 where any segment is playing, 0 in gaps
        speech_mask = np.zeros(total_samp, dtype=np.float32)
        for seg, seg_audio in zip(segments, loaded):
            if seg_audio is None:
                continue
            s = int(seg["start"] * sample_rate)
            e = min(s + len(seg_audio), total_samp)
            speech_mask[s:e] = 1.0
        # Smooth the mask edges (50ms fade) so comfort noise doesn't click in/out
        smooth_len = int(0.050 * sample_rate)
        from scipy.ndimage import uniform_filter1d
        speech_mask = uniform_filter1d(speech_mask, size=smooth_len)
        gap_mask = np.clip(1.0 - speech_mask, 0.0, 1.0)
        # Pink-ish noise: average white noise with its 3-sample-delayed version
        white = rng.standard_normal(total_samp).astype(np.float32)
        pink  = (white
                 + np.concatenate([np.zeros(3, dtype=np.float32), white[:-3]])
                 + np.concatenate([np.zeros(7, dtype=np.float32), white[:-7]])) / 3.0
        output_audio += pink * gap_mask * COMFORT_LEVEL
        np.clip(output_audio, -1.0, 1.0, out=output_audio)

        # Mix BGM under dubbed voice
        if bgm_path and Path(bgm_path).exists():
            try:
                bgm, bgm_sr = sf.read(bgm_path, dtype="float32", always_2d=False)
                if bgm.ndim > 1:
                    bgm = bgm.mean(axis=1)
                if bgm_sr != sample_rate:
                    import librosa
                    bgm = librosa.resample(bgm, orig_sr=bgm_sr, target_sr=sample_rate)
                if len(bgm) < total_samp:
                    bgm = np.concatenate([bgm, np.zeros(total_samp - len(bgm), dtype=np.float32)])
                else:
                    bgm = bgm[:total_samp]
                # Duck BGM under speech regions
                duck_mask = np.full(total_samp, bgm_volume, dtype=np.float32)
                fade_d    = int(0.05 * sample_rate)  # 50ms duck fade
                for seg, seg_audio_orig in zip(segments, loaded):
                    if seg_audio_orig is None:
                        continue
                    s = int(seg["start"] * sample_rate)
                    e = min(s + len(seg_audio_orig) + int(0.15 * sample_rate), total_samp)
                    duck_mask[s:e] = bgm_volume * 0.4
                    if fade_d > 0:
                        fs = min(fade_d, e - s)
                        duck_mask[s:s + fs] = np.linspace(bgm_volume, bgm_volume * 0.4, fs)
                        fe = min(fade_d, e - s)
                        duck_mask[e - fe:e]  = np.linspace(bgm_volume * 0.4, bgm_volume, fe)
                output_audio += bgm * duck_mask
                np.clip(output_audio, -1.0, 1.0, out=output_audio)
            except Exception as _bgm_err:
                import logging
                logging.getLogger(__name__).warning(f"BGM mix failed: {_bgm_err} — skipping BGM")

        # Normalize to -1 dBFS
        np.clip(output_audio, -1.0, 1.0, out=output_audio)
        peak = np.max(np.abs(output_audio))
        if peak > 0.01:
            output_audio *= (0.891 / peak)

        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_wav, output_audio, sample_rate)
        return output_wav

    # ----------------------------------------------------------
    # Replace audio in video
    # ----------------------------------------------------------
    def replace_audio_in_video(
        self,
        video_path: str,
        new_audio_path: str,
        output_video_path: str,
        srt_path: str = None,
        lang: str = None,
    ) -> str:
        """
        Replace the audio track in a video with new dubbed audio.
        Optionally embeds SRT as a soft subtitle track (mov_text) inside the MP4.
        """
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        video_duration = self.get_video_duration(video_path)
        # Pad with silence to match video duration — do NOT stretch (stretching slows all speech)
        padded_path = str(Path(new_audio_path).parent / "_dubbed_synced.wav")
        audio_data, audio_sr = sf.read(new_audio_path, dtype="float32", always_2d=False)
        target_samples = int(video_duration * audio_sr)
        if len(audio_data) < target_samples:
            audio_data = np.concatenate([audio_data, np.zeros(target_samples - len(audio_data), dtype=np.float32)])
        else:
            audio_data = audio_data[:target_samples]
        sf.write(padded_path, audio_data, audio_sr)
        audio_to_use = padded_path

        has_srt = srt_path and Path(srt_path).exists()

        def _mux(reencode_video: bool) -> int:
            cmd = [_FFMPEG, "-y", "-i", str(video_path), "-i", audio_to_use]
            if has_srt:
                cmd += ["-i", str(srt_path)]
            if reencode_video:
                cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
            else:
                cmd += ["-c:v", "copy"]
            cmd += ["-c:a", "aac", "-b:a", "192k"]
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
            if has_srt:
                cmd += ["-map", "2:0", "-c:s", "mov_text"]
                if lang:
                    cmd += ["-metadata:s:s:0", f"language={lang}"]
                cmd += ["-disposition:s:0", "default"]
            cmd += ["-shortest", str(output_video_path), "-loglevel", "error"]
            return subprocess.run(cmd, capture_output=True, timeout=600).returncode

        if _mux(reencode_video=False) != 0:
            if _mux(reencode_video=True) != 0:
                raise RuntimeError(f"Audio replacement failed for {Path(video_path).name}")
        return output_video_path

    # ----------------------------------------------------------
    # Simple full-audio replacement (no segment sync)
    # ----------------------------------------------------------
    def dub_video_simple(
        self,
        video_path: str,
        dubbed_audio_path: str,
        output_path: str,
    ) -> str:
        """
        Simplest dubbing: stretch entire dubbed audio to video duration,
        then replace. Use when segment-level sync is not needed.
        """
        video_duration = self.get_video_duration(video_path)
        stretched_path = dubbed_audio_path.replace(".wav", "_stretched.wav").replace(".mp3", "_stretched.wav")
        self.stretch_audio_to_duration(dubbed_audio_path, video_duration, stretched_path)
        return self.replace_audio_in_video(video_path, stretched_path, output_path)
