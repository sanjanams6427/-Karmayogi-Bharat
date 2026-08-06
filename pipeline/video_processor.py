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

    def assemble_dubbed_audio(
        self,
        segments: list[dict],
        original_duration: float,
        output_wav: str,
        sample_rate: int = 44100,
    ) -> str:
        """
        Place each TTS segment at its original timestamp in the output buffer.
        Speed-up (max 1.35x) applied if segment overruns its slot.
        """
        FADE_SAMP = int(0.010 * sample_rate)
        MAX_SPEED = 1.35

        total_samp   = max(int(original_duration * sample_rate), 1)
        output_audio = np.zeros(total_samp, dtype=np.float32)

        for i, seg in enumerate(segments):
            if "audio_path" not in seg or not Path(seg["audio_path"]).exists():
                continue
            try:
                seg_audio, tts_sr = sf.read(seg["audio_path"], dtype="float32", always_2d=False)
                if seg_audio.ndim > 1:
                    seg_audio = seg_audio.mean(axis=1)
                if tts_sr != sample_rate:
                    import librosa
                    seg_audio = librosa.resample(seg_audio, orig_sr=tts_sr, target_sr=sample_rate)
            except Exception:
                continue
            if len(seg_audio) == 0:
                continue

            start_s    = seg["start"]
            seg_end    = seg.get("end", start_s + 1.0)
            next_start = segments[i + 1]["start"] if i + 1 < len(segments) else original_duration
            slot_samp  = max(
                int((next_start - start_s) * sample_rate),
                int((seg_end   - start_s) * sample_rate),
                int(0.1 * sample_rate),
            )

            # Speed up if overruns slot (max 1.35x)
            if len(seg_audio) > slot_samp:
                ratio     = min(len(seg_audio) / slot_samp, MAX_SPEED)
                seg_audio = self._atempo_stretch_file(seg_audio, sample_rate, ratio)
                if len(seg_audio) > slot_samp:
                    seg_audio = seg_audio[:slot_samp]

            # 10ms fade-in to eliminate click
            fade = min(FADE_SAMP, len(seg_audio) // 8)
            if fade > 0:
                seg_audio[:fade] *= np.linspace(0.0, 1.0, fade)

            # Place at original timestamp
            start_samp = int(start_s * sample_rate)
            end_samp   = min(start_samp + len(seg_audio), total_samp)
            output_audio[start_samp:end_samp] = seg_audio[:end_samp - start_samp]

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
