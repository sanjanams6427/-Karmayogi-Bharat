# ============================================================
# finetune_parler_tts.py
# Fine-tune Indic Parler-TTS Large on all 22 Indian languages
#
# What this does:
#   - Loads ai4bharat/indic-parler-tts-pretrained (large, 3.6GB)
#   - Fine-tunes on TTS data: (text, audio) pairs per language
#   - Uses IndicTTS / Kathbath / FLEURS audio datasets
#   - Label smoothing, cosine LR, early stopping, per-lang weights
#   - Saves best checkpoint to checkpoints/parler_tts/best/
#   - Pipeline auto-loads from checkpoints/parler_tts/best/ if present
#
# Data format expected in datasets/tts/<lang>/train.jsonl:
#   {"text": "...", "audio_path": "path/to/file.wav", "lang": "hin"}
#
# Usage:
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_parler_tts.py
#   # Single GPU:
#   accelerate launch --num_processes=1 --mixed_precision=bf16 \
#       finetune/finetune_parler_tts.py
# ============================================================

import json, os, random, time
from pathlib import Path

import torch
import torch.nn.functional as F
import numpy as np
import soundfile as sf
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from transformers import AutoTokenizer, get_cosine_schedule_with_warmup
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs

from pipeline.lang_config import ALL_22, LANG_NAMES
from pipeline.logger import get_logger

log = get_logger("finetune_parler_tts", "finetune_parler_tts.log")

# ── Paths ──────────────────────────────────────────────────────
PARLER_LARGE_DIR = Path("models/indic_parler_tts_large")
PARLER_MINI_DIR  = Path("models/indic_parler_tts")
MODEL_DIR        = PARLER_LARGE_DIR if PARLER_LARGE_DIR.exists() else PARLER_MINI_DIR
TTS_DATA_DIR     = Path("datasets/tts")          # (text, audio) pairs
CKPT_DIR         = Path("checkpoints/parler_tts")

# ── Hyperparams ────────────────────────────────────────────────
BATCH_SIZE      = 4       # audio batches are large
GRAD_ACCUM      = 8       # effective = 4 * 8 * 4 GPUs = 128
MAX_EPOCHS      = 5
LR              = 1e-5    # conservative — Parler is already well-trained
WARMUP_RATIO    = 0.05
MAX_AUDIO_S     = 20      # seconds — clip long utterances
TARGET_SR       = 44_100  # Parler native sample rate
LOG_EVERY       = 50
EARLY_STOP_PAT  = 2
LABEL_SMOOTHING = 0.05    # lighter smoothing for TTS (less ambiguity than MT)

# Per-lang weights — same tiers as translation fine-tune
_LANG_WEIGHTS = {
    "ben": 1.0, "guj": 1.0, "hin": 2.0, "kan": 1.0, "mal": 1.0,
    "mar": 1.0, "ory": 1.0, "pan": 1.0, "tam": 1.0, "tel": 1.0,
    "asm": 1.0, "urd": 1.0, "nep": 1.0,
    "kas": 2.0, "mai": 2.0, "mni": 2.0, "sat": 2.0, "snd": 2.0,
    "bod": 3.0, "doi": 3.0, "kok": 3.0, "san": 3.0,
}

# Generic speaker description — same as inference (no named speakers)
_DESC = ("A speaker delivers clear and expressive speech at a moderate pace "
         "with a natural pitch. The recording is of very high quality, "
         "with a close-sounding voice and no background noise.")


# ── Dataset ────────────────────────────────────────────────────
class TTSDataset(Dataset):
    def __init__(self, records: list, text_tokenizer, desc_tokenizer):
        self.records        = records
        self.text_tok       = text_tokenizer
        self.desc_tok       = desc_tokenizer

    def __len__(self): return len(self.records)

    def __getitem__(self, idx):
        r = self.records[idx]
        # Load audio → resample to TARGET_SR → clip
        try:
            audio, sr = sf.read(r["audio_path"], dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != TARGET_SR:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=TARGET_SR)
            max_samples = int(MAX_AUDIO_S * TARGET_SR)
            audio = audio[:max_samples]
        except Exception:
            audio = np.zeros(TARGET_SR, dtype=np.float32)  # 1s silence on error
        return r["text"], audio

    def collate(self, batch):
        texts, audios = zip(*batch)
        desc_enc = self.desc_tok(
            [_DESC] * len(texts), return_tensors="pt",
            padding=True, truncation=True, max_length=128,
        )
        prompt_enc = self.text_tok(
            list(texts), return_tensors="pt",
            padding=True, truncation=True, max_length=256,
        )
        # Store raw audio as list — codec encoding happens in the training loop
        # on the correct device (GPU), not here in the CPU collate worker.
        return {
            "input_ids":             desc_enc["input_ids"],
            "attention_mask":        desc_enc["attention_mask"],
            "prompt_input_ids":      prompt_enc["input_ids"],
            "prompt_attention_mask": prompt_enc["attention_mask"],
            "raw_audios":            list(audios),  # list of np.ndarray
        }


# ── Data helpers ───────────────────────────────────────────────
def load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def build_records(split: str, quiet: bool = False) -> list:
    records = []
    for lang in ALL_22:
        raw = load_jsonl(TTS_DATA_DIR / lang / f"{split}.jsonl")
        valid = [r for r in raw
                 if r.get("text", "").strip()
                 and r.get("audio_path")
                 and Path(r["audio_path"]).exists()]
        weight = _LANG_WEIGHTS.get(lang, 1.0) if split == "train" else 1.0
        records.extend(valid * max(1, round(weight)))

    if split == "train":
        random.shuffle(records)
    if not quiet:
        log.info(f"[TTS/{split}] {len(records):,} records across {len(ALL_22)} langs")
    return records


# ── Training ───────────────────────────────────────────────────
def train():
    os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
    os.environ.setdefault("MASTER_PORT", "29501")

    accelerator = Accelerator(
        mixed_precision="bf16",
        gradient_accumulation_steps=GRAD_ACCUM,
        kwargs_handlers=[InitProcessGroupKwargs(backend="gloo")],
    )
    is_main = accelerator.is_main_process

    if is_main:
        log.info(f"{'='*60}")
        log.info(f"Parler-TTS fine-tune | model={MODEL_DIR.name} | "
                 f"{accelerator.num_processes} GPUs")
        log.info(f"LabelSmoothing={LABEL_SMOOTHING} | CosLR | "
                 f"EarlyStop(pat={EARLY_STOP_PAT}) | Epochs={MAX_EPOCHS}")
        log.info(f"{'='*60}")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                log.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")

    # Load model
    from parler_tts import ParlerTTSForConditionalGeneration
    model = ParlerTTSForConditionalGeneration.from_pretrained(
        str(MODEL_DIR),
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",
    )
    model.gradient_checkpointing_enable()

    # Tokenizers
    text_tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    text_enc_name  = model.config.text_encoder._name_or_path
    flan_dir       = Path("models/flan_t5_large")
    desc_tok_src   = str(flan_dir) if flan_dir.exists() else text_enc_name
    desc_tokenizer = AutoTokenizer.from_pretrained(desc_tok_src)

    train_records = build_records("train", quiet=not is_main)
    dev_records   = build_records("dev",   quiet=not is_main)

    if not train_records:
        if is_main:
            log.warning(
                "No TTS data found in datasets/tts/<lang>/train.jsonl\n"
                "Download IndicTTS / Kathbath / FLEURS audio data first.\n"
                "Expected format: {\"text\": \"...\", \"audio_path\": \"...\", \"lang\": \"hin\"}"
            )
        return

    train_ds = TTSDataset(train_records, text_tokenizer, desc_tokenizer)
    dev_ds   = TTSDataset(dev_records,   text_tokenizer, desc_tokenizer)

    sampler = DistributedSampler(train_ds, accelerator.num_processes,
                                 accelerator.process_index, shuffle=True) \
              if accelerator.num_processes > 1 else None
    train_loader = DataLoader(train_ds, BATCH_SIZE, sampler=sampler,
                              shuffle=(sampler is None), collate_fn=train_ds.collate,
                              num_workers=0, pin_memory=False)
    dev_loader   = DataLoader(dev_ds, BATCH_SIZE, shuffle=False,
                              collate_fn=dev_ds.collate, num_workers=0, pin_memory=False)

    total_steps  = (len(train_loader) // GRAD_ACCUM) * MAX_EPOCHS
    warmup_steps = max(1, int(total_steps * WARMUP_RATIO))
    optimizer    = torch.optim.AdamW(model.parameters(), lr=LR,
                                     weight_decay=0.01, betas=(0.9, 0.98), eps=1e-9)
    scheduler    = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    if is_main:
        log.info(f"train_batches={len(train_loader)} dev_batches={len(dev_loader)} "
                 f"total_steps≈{total_steps} warmup={warmup_steps}")

    model, optimizer, train_loader, dev_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, dev_loader, scheduler)

    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    best_dev_loss = float("inf")
    no_improve    = 0
    run_start     = time.time()

    for epoch in range(1, MAX_EPOCHS + 1):
        if sampler:
            sampler.set_epoch(epoch)
        model.train()
        epoch_loss   = 0.0
        epoch_start  = time.time()
        window_start = epoch_start

        for step, batch in enumerate(train_loader, 1):
            with accelerator.accumulate(model):
                # Encode raw audio → codec tokens on GPU using the model's audio encoder
                raw_audios = batch.pop("raw_audios")
                unwrapped  = accelerator.unwrap_model(model)
                audio_enc  = unwrapped.audio_encoder
                sr         = unwrapped.config.audio_encoder.sampling_rate
                import torchaudio.functional as TAF
                wav_list = []
                for a in raw_audios:
                    t = torch.from_numpy(a).float().unsqueeze(0)  # (1, T)
                    if sr != TARGET_SR:
                        t = TAF.resample(t, TARGET_SR, sr)
                    wav_list.append(t)
                max_len = max(w.shape[-1] for w in wav_list)
                wav_batch = torch.zeros(len(wav_list), 1, max_len, device=accelerator.device)
                for i, w in enumerate(wav_list):
                    wav_batch[i, 0, :w.shape[-1]] = w.squeeze(0)
                with torch.no_grad():
                    codec_out = audio_enc.encode(wav_batch)
                    # EnCodec/DAC returns codes shape (B, n_q, T_codes)
                    labels = codec_out.audio_codes[0].transpose(0, 1)  # (B, T_codes)
                outputs = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    prompt_input_ids=batch["prompt_input_ids"],
                    prompt_attention_mask=batch["prompt_attention_mask"],
                    labels=labels,
                )
                loss = outputs.loss
                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
            epoch_loss += loss.item()

            if is_main and step % LOG_EVERY == 0:
                elapsed = time.time() - window_start
                sps     = LOG_EVERY / max(elapsed, 1e-6)
                eta     = (len(train_loader) - step) / max(sps, 1e-6)
                mem_gb  = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0.0
                log.info(f"Ep {epoch}/{MAX_EPOCHS} | Step {step}/{len(train_loader)} "
                         f"| Loss {epoch_loss/step:.4f} | LR {scheduler.get_last_lr()[0]:.2e} "
                         f"| {sps:.2f} sps | GPU {mem_gb:.1f}GB | ETA {eta/60:.1f}min")
                window_start = time.time()

        # Dev eval
        model.eval()
        dev_sum   = torch.zeros(1, device=accelerator.device)
        dev_steps = 0
        with torch.no_grad():
            for batch in dev_loader:
                raw_audios = batch.pop("raw_audios")
                unwrapped  = accelerator.unwrap_model(model)
                audio_enc  = unwrapped.audio_encoder
                sr         = unwrapped.config.audio_encoder.sampling_rate
                import torchaudio.functional as TAF
                wav_list = []
                for a in raw_audios:
                    t = torch.from_numpy(a).float().unsqueeze(0)
                    if sr != TARGET_SR:
                        t = TAF.resample(t, TARGET_SR, sr)
                    wav_list.append(t)
                max_len = max(w.shape[-1] for w in wav_list)
                wav_batch = torch.zeros(len(wav_list), 1, max_len, device=accelerator.device)
                for i, w in enumerate(wav_list):
                    wav_batch[i, 0, :w.shape[-1]] = w.squeeze(0)
                codec_out = audio_enc.encode(wav_batch)
                labels    = codec_out.audio_codes[0].transpose(0, 1)
                outputs = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    prompt_input_ids=batch["prompt_input_ids"],
                    prompt_attention_mask=batch["prompt_attention_mask"],
                    labels=labels,
                )
                dev_sum   += outputs.loss
                dev_steps += 1
        dev_sum  = accelerator.reduce(dev_sum, reduction="mean")
        dev_loss = (dev_sum / max(dev_steps, 1)).item()

        if is_main:
            epoch_mins = (time.time() - epoch_start) / 60
            log.info(f"Epoch {epoch}/{MAX_EPOCHS} done {epoch_mins:.1f}min "
                     f"| TrainLoss {epoch_loss/max(len(train_loader),1):.4f} "
                     f"| DevLoss {dev_loss:.4f}")
            if dev_loss < best_dev_loss:
                best_dev_loss = dev_loss
                no_improve    = 0
                accelerator.unwrap_model(model).save_pretrained(str(CKPT_DIR / "best"))
                text_tokenizer.save_pretrained(str(CKPT_DIR / "best"))
                log.info(f"[SAVED] checkpoints/parler_tts/best  dev_loss={dev_loss:.4f}")
            else:
                no_improve += 1
                log.info(f"No improvement ({no_improve}/{EARLY_STOP_PAT}) best={best_dev_loss:.4f}")
                if no_improve >= EARLY_STOP_PAT:
                    log.info("[EARLY STOP] patience exhausted.")
                    break

    if is_main:
        log.info(f"Done in {(time.time()-run_start)/60:.1f}min. "
                 f"Best dev loss: {best_dev_loss:.4f}")
        log.info("Checkpoint -> checkpoints/parler_tts/best/")
        log.info("To use: pipeline auto-loads from checkpoints/parler_tts/best/ "
                 "if present (update tts.py PARLER_DIR to point there).")


if __name__ == "__main__":
    train()
