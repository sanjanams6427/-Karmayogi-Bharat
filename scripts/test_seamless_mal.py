"""
Diagnostic: test SeamlessM4T for Malayalam across all modes.
Usage: python scripts/test_seamless_mal.py --audio path/to/mal_sample.wav
       python scripts/test_seamless_mal.py --text "നമസ്കാരം, എങ്ങനെ ഉണ്ട്?"
"""
import sys, argparse, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from transformers import AutoProcessor, SeamlessM4Tv2Model

MODELS_DIR = Path("models/seamless")
DEVICE     = "cuda:0" if torch.cuda.is_available() else "cpu"

# Malayalam is "mal" in SEAMLESS_CODES — confirmed supported
TEST_PAIRS = [
    ("mal", "hin"),
    ("mal", "tam"),
    ("mal", "tel"),
    ("mal", "eng"),
    ("hin", "mal"),
    ("eng", "mal"),
]

SEAMLESS_CODES = {
    "eng": "eng", "hin": "hin", "mal": "mal",
    "tam": "tam", "tel": "tel", "ben": "ben",
}


def load_model():
    print(f"[load] SeamlessM4T from {MODELS_DIR} on {DEVICE}")
    t = time.time()
    processor = AutoProcessor.from_pretrained(str(MODELS_DIR))
    model = SeamlessM4Tv2Model.from_pretrained(
        str(MODELS_DIR), torch_dtype=torch.float16
    ).to(DEVICE).eval()
    print(f"[load] done in {time.time()-t:.1f}s")
    return processor, model


def test_t2t(processor, model, text: str):
    print(f"\n{'='*55}")
    print(f"TEXT-TO-TEXT  input: {text[:80]}")
    print(f"{'='*55}")
    for src, tgt in TEST_PAIRS:
        src_code = SEAMLESS_CODES[src]
        tgt_code = SEAMLESS_CODES[tgt]
        try:
            inputs = processor(text=text, src_lang=src_code,
                               return_tensors="pt").to(DEVICE)
            inputs = {k: v.to(torch.float16) if v.is_floating_point() else v
                      for k, v in inputs.items()}
            with torch.no_grad():
                out = model.generate(**inputs, tgt_lang=tgt_code,
                                     generate_speech=False, num_beams=5)
            result = processor.decode(out.sequences[0], skip_special_tokens=True).strip()
            status = "OK " if result else "EMPTY"
            print(f"  [{status}] {src}→{tgt}: {result[:100]}")
        except Exception as e:
            print(f"  [ERR] {src}→{tgt}: {e}")


def test_s2t(processor, model, audio_path: str):
    import soundfile as sf
    print(f"\n{'='*55}")
    print(f"SPEECH-TO-TEXT  audio: {audio_path}")
    print(f"{'='*55}")
    audio, sr = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    for tgt in ["mal", "hin", "eng", "tam"]:
        tgt_code = SEAMLESS_CODES.get(tgt, tgt)
        try:
            inputs = processor(audios=audio, sampling_rate=sr,
                               return_tensors="pt").to(DEVICE)
            inputs = {k: v.to(torch.float16) if v.is_floating_point() else v
                      for k, v in inputs.items()}
            with torch.no_grad():
                out = model.generate(**inputs, tgt_lang=tgt_code,
                                     generate_speech=False, num_beams=5)
            result = processor.decode(out.sequences[0], skip_special_tokens=True).strip()
            status = "OK " if result else "EMPTY"
            print(f"  [{status}] speech→{tgt}: {result[:100]}")
        except Exception as e:
            print(f"  [ERR] speech→{tgt}: {e}")


def test_s2s(processor, model, audio_path: str):
    import soundfile as sf, numpy as np
    print(f"\n{'='*55}")
    print(f"SPEECH-TO-SPEECH  audio: {audio_path}")
    print(f"{'='*55}")
    audio, sr = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    for tgt in ["hin", "tam", "eng"]:
        tgt_code = SEAMLESS_CODES.get(tgt, tgt)
        out_path = f"temp/s2s_mal_{tgt}.wav"
        Path("temp").mkdir(exist_ok=True)
        try:
            inputs = processor(audios=audio, sampling_rate=sr,
                               return_tensors="pt").to(DEVICE)
            inputs = {k: v.to(torch.float16) if v.is_floating_point() else v
                      for k, v in inputs.items()}
            with torch.no_grad():
                out = model.generate(**inputs, tgt_lang=tgt_code,
                                     generate_speech=True)
            wav = out.waveform[0].cpu().float().numpy().squeeze()
            out_sr = getattr(model.config, "sampling_rate", 16000)
            dur = len(wav) / out_sr
            sf.write(out_path, wav, out_sr)
            status = "OK " if dur > 0.3 else "SHORT"
            print(f"  [{status}] speech→{tgt}: {dur:.1f}s → {out_path}")
        except Exception as e:
            print(f"  [ERR] speech→{tgt}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", help="Path to Malayalam WAV file (16kHz mono)")
    parser.add_argument("--text",  default="നമസ്കാരം, എങ്ങനെ ഉണ്ട്? ഇന്ന് കാലാവസ്ഥ നല്ലതാണ്.",
                        help="Malayalam text for T2T test")
    args = parser.parse_args()

    processor, model = load_model()

    # Always run T2T
    test_t2t(processor, model, args.text)

    # Run audio tests only if audio provided
    if args.audio:
        if not Path(args.audio).exists():
            print(f"[ERR] Audio file not found: {args.audio}")
            sys.exit(1)
        test_s2t(processor, model, args.audio)
        test_s2s(processor, model, args.audio)
    else:
        print("\n[INFO] No --audio provided. Skipping S2T and S2S tests.")
        print("       Run with: python scripts/test_seamless_mal.py --audio path/to/mal.wav")
