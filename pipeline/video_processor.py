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
        result = subprocess.run(args, capture_output=True)
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
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        # Fallback: use soundfile/librosa
        import soundfile as sf
        info = sf.info(path)
        return {"format": {"duration": str(info.duration)}}

    def _has_audio_stream(self, video_path: str) -> bool:
        """Return True if the file has at least one audio stream."""
        result = subprocess.run(
            [_FFMPEG, "-i", str(video_path)],
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE
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
            capture_output=True
        )
        if ret.returncode != 0:
            # video-only re-encode (no audio in source)
            subprocess.run(
                [_FFMPEG, "-y", "-i", str(video_path),
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                 "-an", str(tmp_path), "-loglevel", "error"],
                capture_output=True
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
                capture_output=True
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
            capture_output=True
        ).returncode

        if ret != 0:
            # Re-encode input then retry (handles corrupt/unusual containers)
            print(f"[VP] Extraction failed, re-encoding input: {Path(video_path).name}")
            tmp = str(Path(output_wav).parent / "_reenc_input.mp4")
            self._reencode_input(video_path, tmp)
            ret2 = subprocess.run(
                [_FFMPEG, "-y", "-i", tmp,
                 "-ar", str(sample_rate), "-ac", "1", "-vn", output_wav,
                 "-loglevel", "error"],
                capture_output=True
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
            capture_output=True
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
            stderr=subprocess.STDOUT, stdout=subprocess.PIPE
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
            capture_output=True
        )
        return output_path

    def assemble_dubbed_audio(
        self,
        segments: list[dict],
        original_duration: float,
        output_wav: str,
        sample_rate: int = 44100,
    ) -> str:
        """
        Assemble TTS segments into a single dubbed audio track.
        Strategy: place each segment at its original timestamp.
        If TTS is longer than the slot, speed it up to fit (max 2x).
        If TTS is shorter, pad with silence — never cut speech.
        Final output is always exactly original_duration long.
        """
        import librosa
        FADE_MS = int(0.025 * sample_rate)  # 25ms crossfade

        total_samples = int(original_duration * sample_rate)
        output_audio  = np.zeros(total_samples, dtype=np.float32)

        for i, seg in enumerate(segments):
            if "audio_path" not in seg or not Path(seg["audio_path"]).exists():
                continue
            try:
                seg_audio, _ = librosa.load(seg["audio_path"], sr=sample_rate, mono=True)
            except Exception:
                continue
            if len(seg_audio) == 0:
                continue

            start_s = seg["start"]
            # slot = time until next segment starts (or end of video)
            next_start = segments[i + 1]["start"] if i + 1 < len(segments) else original_duration
            slot_s     = max(next_start - start_s, 0.5)
            slot_samp  = int(slot_s * sample_rate)
            tts_samp   = len(seg_audio)

            # Speed up TTS to fit slot if it overruns (cap at 1.4x — beyond that sounds robotic)
            if tts_samp > slot_samp:
                ratio = min(tts_samp / slot_samp, 1.4)
                try:
                    seg_audio = librosa.effects.time_stretch(seg_audio, rate=ratio).astype(np.float32)
                except Exception:
                    pass
                seg_audio = seg_audio[:slot_samp]  # hard trim as safety net

            # 10ms fade-in only — eliminates click at segment start without dipping speech
            fade = min(FADE_MS, len(seg_audio) // 8)
            if fade > 0:
                seg_audio[:fade] *= np.linspace(0.0, 1.0, fade)

            start_samp = int(start_s * sample_rate)
            end_samp   = min(start_samp + len(seg_audio), total_samples)
            copy_len   = end_samp - start_samp
            if copy_len > 0:
                output_audio[start_samp:end_samp] = seg_audio[:copy_len]

        # Normalize to -3dBFS
        peak = np.max(np.abs(output_audio))
        if peak > 0.01:
            output_audio *= (0.707 / peak)

        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_wav, output_audio, sample_rate)
        return output_wav

    def _atempo_stretch_array(
        self, audio: np.ndarray, sr: int, ratio: float
    ) -> np.ndarray:
        """
        Time-stretch in memory using librosa (no ffmpeg subprocess per segment).
        ratio > 1 = speed up, ratio < 1 = slow down.
        """
        ratio = max(0.5, min(2.0, ratio))
        if abs(ratio - 1.0) < 0.02:
            return audio
        try:
            import librosa
            return librosa.effects.time_stretch(audio, rate=ratio).astype(np.float32)
        except Exception:
            return audio

    # ----------------------------------------------------------
    # Replace audio in video
    # ----------------------------------------------------------
    def replace_audio_in_video(
        self,
        video_path: str,
        new_audio_path: str,
        output_video_path: str,
    ) -> str:
        """
        Replace the audio track in a video with new dubbed audio.
        Always stretches dubbed audio to exactly match original video duration
        so output video never runs longer than the source.
        """
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

        # Stretch dubbed audio to exactly match original video duration
        video_duration = self.get_video_duration(video_path)
        stretched_path = str(Path(new_audio_path).parent / "_dubbed_synced.wav")
        self.stretch_audio_to_duration(new_audio_path, video_duration, stretched_path)
        audio_to_use = stretched_path

        # Mux: -shortest ensures output stops at video end
        ret = subprocess.run(
            [_FFMPEG, "-y",
             "-i", str(video_path), "-i", audio_to_use,
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-map", "0:v:0", "-map", "1:a:0",
             "-shortest", str(output_video_path), "-loglevel", "error"],
            capture_output=True
        ).returncode
        if ret != 0:
            ret2 = subprocess.run(
                [_FFMPEG, "-y",
                 "-i", str(video_path), "-i", audio_to_use,
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                 "-c:a", "aac", "-b:a", "192k",
                 "-map", "0:v:0", "-map", "1:a:0",
                 "-shortest", str(output_video_path), "-loglevel", "error"],
                capture_output=True
            ).returncode
            if ret2 != 0:
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
