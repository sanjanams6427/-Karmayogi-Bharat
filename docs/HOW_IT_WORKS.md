# KB Translation System — How It Works

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER UPLOADS VIDEO                                 │
│                              (MP4/WebM)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: AUDIO EXTRACTION                                                   │
│  ─────────────────────────                                                   │
│  Tool: FFmpeg                                                                │
│  Input: video.mp4                                                            │
│  Output: source.wav (16kHz mono)                                             │
│                                                                              │
│  What happens:                                                               │
│  • Extracts audio track from video                                           │
│  • Converts to 16kHz sample rate (required for ASR)                         │
│  • Saves as WAV file                                                         │
│                                                                              │
│  NO AI MODEL LOADED YET                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: ASR (Automatic Speech Recognition)                                 │
│  ───────────────────────────────────────────                                 │
│  Model: faster-whisper-large-v3 (~3GB VRAM)                                  │
│  Location: models/indic_asr/                                                 │
│  Input: source.wav                                                           │
│  Output: List of segments [{start, end, text}, ...]                         │
│                                                                              │
│  What happens:                                                               │
│  • Loads Whisper model to GPU (first time takes ~10-20 sec)                 │
│  • Listens to audio and converts speech → text                              │
│  • Splits into segments with timestamps                                      │
│                                                                              │
│  Example output:                                                             │
│  [                                                                           │
│    {start: 0.0,  end: 3.5,  text: "Welcome to this course"},                │
│    {start: 3.5,  end: 7.2,  text: "Today we will learn about..."},          │
│    {start: 7.2,  end: 12.0, text: "Let's get started"},                     │
│  ]                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: TRANSLATION                                                        │
│  ────────────────────                                                        │
│  Models (tries in order until one works):                                    │
│    1. IndicTrans2 (~1.2GB) - Best for Indian languages                      │
│    2. SeamlessM4T (~10GB) - Facebook's multilingual model                   │
│    3. NLLB-200 (~2.4GB) - Fallback                                          │
│  Location: models/indic_tr/, models/seamless/, models/nllb/                 │
│  Input: English text segments                                                │
│  Output: Translated text in target language (e.g., Hindi)                   │
│                                                                              │
│  What happens:                                                               │
│  • Loads translation model to GPU (first time takes ~30-60 sec)             │
│  • For each segment: English text → Hindi text                              │
│  • Calculates quality score (0-1)                                           │
│                                                                              │
│  Example:                                                                    │
│  "Welcome to this course" → "इस कोर्स में आपका स्वागत है"                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: TTS (Text-to-Speech)                                               │
│  ─────────────────────────────                                               │
│  Models (tries in order):                                                    │
│    1. Parler-TTS Indic Large (~3.6GB) - Best quality                        │
│    2. MMS-TTS (~1.5GB) - Facebook's multilingual TTS                        │
│  Location: models/indic_parler_tts_large/, models/mms_standalone/           │
│  Input: Translated text                                                      │
│  Output: WAV audio file for each segment                                    │
│                                                                              │
│  What happens:                                                               │
│  • Loads TTS model to GPU                                                    │
│  • Converts Hindi text → Hindi speech audio                                  │
│  • Saves as WAV file per segment                                            │
│                                                                              │
│  Example:                                                                    │
│  "इस कोर्स में आपका स्वागत है" → seg_0000.wav (3.2 seconds of Hindi audio)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 5: AUDIO ASSEMBLY                                                     │
│  ───────────────────────                                                     │
│  Tool: Python + FFmpeg                                                       │
│  Input: All segment WAV files + original timestamps                         │
│  Output: dubbed_final.wav (full dubbed audio track)                         │
│                                                                              │
│  What happens:                                                               │
│  • Creates empty audio buffer (same length as original video)               │
│  • Places each dubbed segment at its original timestamp                     │
│  • If dubbed audio is longer than original slot:                            │
│      - SPEED_UP: Speed up audio (max 1.35x) to fit                         │
│      - EXTEND_VIDEO: Keep audio normal, extend video later                  │
│  • Optionally mixes with background music from original                     │
│                                                                              │
│  Timeline example:                                                           │
│  Original: [____seg0____][____seg1____][____seg2____]                       │
│  Dubbed:   [__हिंदी_0__][___हिंदी_1___][__हिंदी_2__]                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE 6: VIDEO MUXING                                                       │
│  ─────────────────────                                                       │
│  Tool: FFmpeg                                                                │
│  Input: Original video + dubbed_final.wav                                   │
│  Output: final_video_hindi.mp4                                              │
│                                                                              │
│  What happens:                                                               │
│  • Takes original video (keeps all visuals)                                 │
│  • Replaces audio track with dubbed audio                                   │
│  • Generates subtitles (SRT/VTT)                                            │
│  • Outputs final dubbed video                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FINAL OUTPUT                                         │
│  • video_hindi.mp4  — Dubbed video                                          │
│  • video_hindi.srt  — Subtitles                                             │
│  • video_hindi.vtt  — Web subtitles                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Loads When?

### On UI Startup (python ui/app.py)
```
NOTHING is loaded yet!
Just starts a web server on port 7860.
Models are loaded LAZILY (only when first needed).
```

### On "Create Session" Click
```
1. FFmpeg extracts audio → source.wav
2. Whisper model loads to GPU (~10-20 sec first time)
3. ASR runs → segments with timestamps
4. Session saved to disk (JSON)
```

### On "Translate" Click
```
1. IndicTrans2 loads to GPU (~30 sec first time)
   - If fails → SeamlessM4T loads
   - If fails → NLLB loads
2. Translation runs
3. Results saved to session
```

### On "Generate TTS" Click
```
1. Parler-TTS loads to GPU (~20 sec first time)
   - If fails → MMS-TTS loads
2. TTS generates audio for each segment
3. WAV files saved to session folder
```

### On "Stitch" Click
```
1. Audio assembly (Python, no model)
2. FFmpeg muxes video + audio
3. Final video saved
```

---

## Memory Usage (GPU VRAM)

```
Model                    VRAM Usage
─────────────────────────────────────
Whisper large-v3         ~3 GB
IndicTrans2              ~4 GB
SeamlessM4T              ~10 GB (big!)
NLLB-200                 ~3 GB
Parler-TTS Large         ~4 GB
MMS-TTS                  ~2 GB

Peak usage (worst case):  ~10-14 GB
Recommended GPU:          12GB+ VRAM
```

---

## Segment Edit Suite — What Each Button Does

```
┌─────────────────────────────────────────────────────────────────┐
│ CREATE SESSION                                                   │
│ • Upload video → Extract audio → Run ASR → Get segments         │
│ • Shows table with all detected speech segments                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ SEGMENT TABLE                                                    │
│ ┌────┬──────────┬─────────┬────────────────────┬────────┐       │
│ │ ID │ Time     │ Dur     │ Source Text        │ Status │       │
│ ├────┼──────────┼─────────┼────────────────────┼────────┤       │
│ │ 0  │ 0.0-3.5  │ 3.5s    │ Welcome to this... │ ⏳     │       │
│ │ 1  │ 3.5-7.2  │ 3.7s    │ Today we will...   │ ⏳     │       │
│ │ 2  │ 7.2-12.0 │ 4.8s    │ Let's get started  │ ⏳     │       │
│ └────┴──────────┴─────────┴────────────────────┴────────┘       │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ACTIONS PER SEGMENT                                              │
│                                                                  │
│ [🌐 Translate] — Translate this segment to target language      │
│ [⏭️ Skip]      — Don't dub this (music, noise, silence)         │
│ [🔊 Keep Orig] — Keep original audio (don't translate)          │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ BATCH OPERATIONS                                                 │
│                                                                  │
│ [🌐 Translate All] — Translate all segments at once             │
│ [🔊 Generate TTS]  — Generate audio for all translations        │
│ [✅ Auto-Approve]  — Approve all segments that fit              │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FIT STRATEGY (when dubbed audio is longer than original)        │
│                                                                  │
│ ⏩ Speed Up    — Speed up audio to fit (max 1.35x)              │
│ 📹+ Extend     — Freeze video frame to fit longer audio         │
│ ✂️ Trim        — Cut off end of audio (may lose words)          │
│ 🔄 Auto        — Let system decide                              │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ FINAL STITCH                                                     │
│                                                                  │
│ [🎬 Stitch Final Video] — Combine everything into output video  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure During Processing

```
output/sessions/{session_id}/
├── source.wav              ← Extracted audio from video
├── session_state.json      ← All segment data, translations, status
├── tts/
│   ├── seg_0000.wav        ← TTS audio for segment 0
│   ├── seg_0001.wav        ← TTS audio for segment 1
│   └── ...
├── thumbnails/
│   ├── seg_0000.jpg        ← Preview frame for segment 0
│   └── ...
├── dubbed_final.wav        ← Assembled dubbed audio
└── extended_base.mp4       ← Extended video (if using EXTEND_VIDEO)

output/{course_id}/{lang}/
├── video_hindi.mp4         ← Final dubbed video
├── video_hindi.srt         ← Subtitles
└── video_hindi.vtt         ← Web subtitles
```

---

## Simple Mental Model

```
VIDEO → [Extract Audio] → [Speech-to-Text] → [Translate Text] → [Text-to-Speech] → [Combine] → DUBBED VIDEO
         (FFmpeg)         (Whisper)          (IndicTrans2)      (Parler-TTS)       (FFmpeg)
```

That's it! Just 5 steps:
1. **Extract** — Get audio from video
2. **Transcribe** — Speech → English text
3. **Translate** — English text → Hindi text  
4. **Synthesize** — Hindi text → Hindi audio
5. **Combine** — Put Hindi audio back in video
