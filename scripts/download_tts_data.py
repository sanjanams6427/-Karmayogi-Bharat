# ============================================================
# download_tts_data.py
# Download TTS audio data for Parler-TTS fine-tuning.
#
# Sources (all public, no token required):
#   1. google/fleurs          — 14 Indian lang configs, ~500MB each
#   2. ai4bharat/Kathbath     — 12 langs, studio-quality read speech
#   3. psk/indic-tts-966h     — 6 langs (ben/mal/mar/pan/tam/tel)
#
# Output: datasets/tts/<lang>/train.jsonl + dev.jsonl
# Format: {"text": "...", "audio_path": "abs/path/to/file.wav", "lang": "hin"}
#
# Usage:
#   py -3.12 scripts/download_tts_data.py
#   py -3.12 scripts/download_tts_data.py --source fleurs
#   py -3.12 scripts/download_tts_data.py --source kathbath
#   py -3.12 scripts/download_tts_data.py --source indictts
#   py -3.12 scripts/download_tts_data.py --lang hin ben tam
# ============================================================

import argparse, json, os, sys, time, traceback
import numpy as np
from pathlib import Path

ROOT    = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TTS_DIR = ROOT / "datasets" / "tts"
WAV_DIR = ROOT / "datasets" / "tts_wav"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

import logging
log = logging.getLogger("dl_tts")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
_fh  = logging.FileHandler(str(LOG_DIR / "download_tts_data.log"), encoding="utf-8")
_fh.setFormatter(_fmt)
_sh  = logging.StreamHandler(sys.stdout)
_sh.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
_sh.setFormatter(_fmt)
log.addHandler(_fh)
log.addHandler(_sh)

TARGET_SR = 44_100
MAX_DUR_S = 20.0
MIN_DUR_S = 0.5

# ── Source configs ─────────────────────────────────────────────

FLEURS_CONFIGS = {
    "asm": "as_in", "ben": "bn_in", "guj": "gu_in", "hin": "hi_in",
    "kan": "kn_in", "mal": "ml_in", "mar": "mr_in", "ory": "or_in",
    "pan": "pa_in", "tam": "ta_in", "tel": "te_in", "urd": "ur_pk",
    "nep": "ne_np", "snd": "sd_in",
}

KATHBATH_CONFIGS = {
    "ben": "bengali",  "guj": "gujarati", "hin": "hindi",
    "kan": "kannada",  "mal": "malayalam", "mar": "marathi",
    "ory": "odia",     "pan": "punjabi",   "san": "sanskrit",
    "tam": "tamil",    "tel": "telugu",    "urd": "urdu",
}

INDICTTS_CONFIGS = {
    "ben": "bengali", "mal": "malayalam", "mar": "marathi",
    "pan": "punjabi", "tam": "tamil",     "tel": "telugu",
}


# ── Audio helpers ──────────────────────────────────────────────

def _to_wav(arr, src_sr: int, out_path: Path) -> bool:
    import soundfile as sf
    if arr is None or len(arr) == 0:
        return False
    audio = np.array(arr, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if src_sr != TARGET_SR:
        import librosa
        audio = librosa.resample(audio, orig_sr=src_sr, target_sr=TARGET_SR)
    audio = audio[:int(MAX_DUR_S * TARGET_SR)]
    if len(audio) / TARGET_SR < MIN_DUR_S:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, TARGET_SR)
    return True


def _extract_audio(row: dict) -> tuple:
    audio = row.get("audio") or {}
    if isinstance(audio, dict):
        return audio.get("array"), audio.get("sampling_rate", 16000)
    return None, 16000


def _get_text(row: dict) -> str:
    for key in ("transcription", "raw_transcription", "text", "sentence", "normalized_text"):
        v = row.get(key, "")
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _write_jsonl(records: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info(f"    -> {path.name}: {len(records):,} records")


def _merge_jsonl(new_records: list, path: Path):
    existing = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            existing = [json.loads(l) for l in f if l.strip()]
    seen    = {r["audio_path"] for r in existing}
    added   = [r for r in new_records if r["audio_path"] not in seen]
    combined = existing + added
    _write_jsonl(combined, path)
    return len(added)


# ── FLEURS ─────────────────────────────────────────────────────

def download_fleurs(lang: str, cfg: str):
    log.info(f"[FLEURS] {lang} ({cfg})")
    from datasets import load_dataset

    wav_dir = WAV_DIR / "fleurs" / lang
    train_recs, dev_recs = [], []

    for hf_split, recs in [("train", train_recs), ("validation", dev_recs)]:
        try:
            ds = load_dataset("google/fleurs", cfg, split=hf_split)
        except Exception as e:
            log.warning(f"  [{hf_split}] load failed: {e}")
            continue

        ok = skip = 0
        for i, row in enumerate(ds):
            text = _get_text(row)
            if not text:
                skip += 1
                continue
            arr, sr = _extract_audio(row)
            out_wav = wav_dir / f"{hf_split}_{i:05d}.wav"
            if not out_wav.exists():
                if not _to_wav(arr, sr, out_wav):
                    skip += 1
                    continue
            recs.append({"text": text, "audio_path": str(out_wav.resolve()), "lang": lang})
            ok += 1

        log.info(f"  [{hf_split}] ok={ok} skip={skip}")

    if train_recs:
        _merge_jsonl(train_recs, TTS_DIR / lang / "train.jsonl")
    if dev_recs:
        _merge_jsonl(dev_recs,   TTS_DIR / lang / "dev.jsonl")


# ── Kathbath ───────────────────────────────────────────────────

def download_kathbath(lang: str, cfg: str):
    log.info(f"[Kathbath] {lang} ({cfg})")
    from datasets import load_dataset

    wav_dir = WAV_DIR / "kathbath" / lang
    train_recs, dev_recs = [], []

    for hf_split, recs in [("train", train_recs), ("valid", dev_recs)]:
        try:
            ds = load_dataset("ai4bharat/Kathbath", cfg, split=hf_split)
        except Exception as e:
            log.warning(f"  [{hf_split}] load failed: {e}")
            continue

        ok = skip = 0
        for i, row in enumerate(ds):
            text = _get_text(row)
            if not text:
                skip += 1
                continue
            arr, sr = _extract_audio(row)
            out_wav = wav_dir / f"{hf_split}_{i:05d}.wav"
            if not out_wav.exists():
                if not _to_wav(arr, sr, out_wav):
                    skip += 1
                    continue
            recs.append({"text": text, "audio_path": str(out_wav.resolve()), "lang": lang})
            ok += 1

        log.info(f"  [{hf_split}] ok={ok} skip={skip}")

    if train_recs:
        _merge_jsonl(train_recs, TTS_DIR / lang / "train.jsonl")
    if dev_recs:
        _merge_jsonl(dev_recs,   TTS_DIR / lang / "dev.jsonl")


# ── psk/indic-tts-966h ─────────────────────────────────────────

def download_indictts(lang: str, cfg: str):
    log.info(f"[IndicTTS-966h] {lang} ({cfg})")
    from datasets import load_dataset

    wav_dir = WAV_DIR / "indictts" / lang

    try:
        ds = load_dataset("psk/indic-tts-966h", cfg, split="train")
    except Exception as e:
        log.warning(f"  load failed: {e}")
        return

    n     = len(ds)
    dev_n = max(50, int(n * 0.05))
    train_recs, dev_recs = [], []

    for i, row in enumerate(ds):
        text = _get_text(row)
        if not text:
            continue
        arr, sr  = _extract_audio(row)
        split_tag = "dev" if i < dev_n else "train"
        out_wav   = wav_dir / f"{split_tag}_{i:05d}.wav"
        if not out_wav.exists():
            if not _to_wav(arr, sr, out_wav):
                continue
        rec = {"text": text, "audio_path": str(out_wav.resolve()), "lang": lang}
        (dev_recs if split_tag == "dev" else train_recs).append(rec)

    log.info(f"  train={len(train_recs):,} dev={len(dev_recs):,}")
    if train_recs:
        _merge_jsonl(train_recs, TTS_DIR / lang / "train.jsonl")
    if dev_recs:
        _merge_jsonl(dev_recs,   TTS_DIR / lang / "dev.jsonl")


# ── Summary ────────────────────────────────────────────────────

def print_summary():
    from pipeline.lang_config import ALL_22, LANG_NAMES
    log.info("=" * 60)
    log.info("TTS DATA SUMMARY")
    log.info("=" * 60)
    total_train = total_dev = 0
    for lang in ALL_22:
        t = TTS_DIR / lang / "train.jsonl"
        d = TTS_DIR / lang / "dev.jsonl"
        tn = sum(1 for _ in open(t, encoding="utf-8")) if t.exists() else 0
        dn = sum(1 for _ in open(d, encoding="utf-8")) if d.exists() else 0
        total_train += tn
        total_dev   += dn
        status = "OK" if tn > 0 else "--"
        log.info(f"  [{status}] {lang:4s} {LANG_NAMES.get(lang,''):12s}  train={tn:6,}  dev={dn:5,}")
    log.info(f"\n  TOTAL  train={total_train:,}  dev={total_dev:,}")
    log.info("=" * 60)
    log.info("Next: accelerate launch --num_processes=4 --mixed_precision=bf16 finetune/finetune_parler_tts.py")


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["fleurs", "kathbath", "indictts", "all"],
                        default="all")
    parser.add_argument("--lang", nargs="*",
                        help="Specific lang codes e.g. --lang hin ben tam")
    args = parser.parse_args()

    t0 = time.time()
    log.info("=" * 60)
    log.info("TTS DATA DOWNLOADER — Parler-TTS fine-tune")
    log.info(f"source={args.source}  langs={args.lang or 'all'}")
    log.info("=" * 60)

    def _want(lang):
        return (not args.lang) or (lang in args.lang)

    if args.source in ("fleurs", "all"):
        for lang, cfg in FLEURS_CONFIGS.items():
            if not _want(lang):
                continue
            try:
                download_fleurs(lang, cfg)
            except Exception:
                log.error(f"[FLEURS/{lang}] crashed:\n{traceback.format_exc()}")

    if args.source in ("kathbath", "all"):
        for lang, cfg in KATHBATH_CONFIGS.items():
            if not _want(lang):
                continue
            try:
                download_kathbath(lang, cfg)
            except Exception:
                log.error(f"[Kathbath/{lang}] crashed:\n{traceback.format_exc()}")

    if args.source in ("indictts", "all"):
        for lang, cfg in INDICTTS_CONFIGS.items():
            if not _want(lang):
                continue
            try:
                download_indictts(lang, cfg)
            except Exception:
                log.error(f"[IndicTTS/{lang}] crashed:\n{traceback.format_exc()}")

    log.info(f"\nDone in {(time.time()-t0)/60:.1f} min")
    print_summary()


if __name__ == "__main__":
    main()
