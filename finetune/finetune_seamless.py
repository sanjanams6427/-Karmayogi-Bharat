# ============================================================
# finetune_seamless.py
# Full Fine-tune SeamlessM4T-v2-large — HuggingFace Accelerate + FSDP
#
# Method: Full Fine-tune (100% params) + FSDP (Fully Sharded DP)
#   - Windows-compatible alternative to DeepSpeed ZeRO-3
#   - FSDP shards weights+gradients+optimizer across 4x A6000
#   - 192GB total VRAM used as one logical pool
#   - bf16 mixed precision (Ampere A6000 native)
#   - Gradient checkpointing for activation memory savings
#
# Usage:
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_seamless.py --task asr
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_seamless.py --task t2t
# ============================================================

import argparse
import json
import os
import time
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from transformers import (
    AutoProcessor,
    SeamlessM4Tv2ForSpeechToText,
    SeamlessM4Tv2ForTextToText,
    get_linear_schedule_with_warmup,
)
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs

from pipeline.lang_config import SEAMLESS_CODES, ALL_22
from pipeline.logger import get_logger

log = get_logger("finetune_seamless", "finetune_seamless.log")

# ── Paths ─────────────────────────────────────────────────────
MODEL_PATH = Path("models/seamless")
AUDIO_DIR  = Path("datasets/audio")
TEXT_DIR   = Path("datasets/parallel")
CKPT_DIR   = Path("checkpoints/seamless")
TM_PATH    = Path("translation_memory/govt_tm.jsonl")
HF_PATH    = Path("translation_memory/human_feedback.jsonl")

SAMPLE_RATE = 16_000

# ── Hyperparams ───────────────────────────────────────────────
BATCH_ASR    = 4      # audio tensors are large (30s * 16kHz)
BATCH_T2T    = 8
GRAD_ACCUM   = 8      # effective ASR = 4*8*4=128 | T2T = 8*8*4=256
MAX_EPOCHS   = 3
LR_SPEECH    = 5e-6   # very low LR for full fine-tune of speech encoder
LR_TEXT      = 2e-5
WARMUP_STEPS = 300
MAX_AUDIO_S  = 30
MAX_TEXT_LEN = 256
LOG_EVERY    = 50

SEAMLESS_LANGS = {k for k in SEAMLESS_CODES if k in ALL_22}


# ── ASR Dataset ───────────────────────────────────────────────
class ASRDataset(Dataset):
    def __init__(self, records: list, processor, lang: str):
        self.records   = records
        self.processor = processor
        self.lang      = SEAMLESS_CODES.get(lang, lang)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        import librosa
        r = self.records[idx]
        audio, _ = librosa.load(r["audio_path"], sr=SAMPLE_RATE, mono=True,
                                duration=MAX_AUDIO_S)
        return audio.astype("float32"), r["text"]

    def collate(self, batch):
        audios, texts = zip(*batch)
        inputs = self.processor(
            audios=list(audios), sampling_rate=SAMPLE_RATE,
            return_tensors="pt", padding=True,
        )
        labels = self.processor(
            text=list(texts), src_lang=self.lang,
            return_tensors="pt", padding=True,
            truncation=True, max_length=MAX_TEXT_LEN,
        ).input_ids
        labels[labels == self.processor.tokenizer.pad_token_id] = -100
        return {**inputs, "labels": labels}


# ── T2T Dataset ───────────────────────────────────────────────
class TextDataset(Dataset):
    def __init__(self, records: list, processor):
        self.records   = records
        self.processor = processor

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        return self.records[idx]

    def collate(self, batch):
        from collections import defaultdict
        # Filter langs not in SeamlessM4T vocabulary (e.g. ory/__odi__)
        UNSUPPORTED = {"ory"}
        batch = [r for r in batch
                 if r.get("src_lang") not in UNSUPPORTED
                 and r.get("tgt_lang") not in UNSUPPORTED]
        if not batch:
            return None
        groups = defaultdict(list)
        for r in batch:
            groups[(r["src_lang"], r["tgt_lang"])].append(r)

        all_ids, all_masks, all_labels = [], [], []
        for (src_lang, tgt_lang), recs in groups.items():
            sm_src = SEAMLESS_CODES.get(src_lang, src_lang)
            sm_tgt = SEAMLESS_CODES.get(tgt_lang, tgt_lang)
            enc = self.processor(
                text=[r["src"] for r in recs], src_lang=sm_src,
                return_tensors="pt", padding=True,
                truncation=True, max_length=MAX_TEXT_LEN,
            )
            lbl = self.processor(
                text=[r["tgt"] for r in recs], src_lang=sm_tgt,
                return_tensors="pt", padding=True,
                truncation=True, max_length=MAX_TEXT_LEN,
            ).input_ids
            lbl[lbl == self.processor.tokenizer.pad_token_id] = -100
            all_ids.append(enc["input_ids"])
            all_masks.append(enc["attention_mask"])
            all_labels.append(lbl)

        max_src = max(t.shape[1] for t in all_ids)
        max_tgt = max(t.shape[1] for t in all_labels)

        def pad2d(t, length, val=0):
            d = length - t.shape[1]
            return torch.nn.functional.pad(t, (0, d), value=val) if d > 0 else t

        return {
            "input_ids":      torch.cat([pad2d(t, max_src) for t in all_ids]),
            "attention_mask": torch.cat([pad2d(t, max_src) for t in all_masks]),
            "labels":         torch.cat([pad2d(t, max_tgt, -100) for t in all_labels]),
        }


# ── Data helpers ──────────────────────────────────────────────
def load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_tm_records() -> list:
    tm = load_jsonl(TM_PATH)
    hf = load_jsonl(HF_PATH)
    return tm + hf * 3


def build_asr_records(split: str, quiet: bool = False) -> list:
    records = []
    for source in ["kathbath", "fleurs", "indicsuper"]:
        for lang in SEAMLESS_LANGS:
            for r in load_jsonl(AUDIO_DIR / source / lang / f"{split}.jsonl"):
                if r.get("audio_path") and r.get("text") and r.get("lang"):
                    records.append(r)
    if not quiet:
        log.info(f"[ASR/{split}] {len(records):,} records loaded")
    return records


def build_text_records(split: str, quiet: bool = False) -> list:
    records = []
    for lang in SEAMLESS_LANGS:
        for r in load_jsonl(TEXT_DIR / lang / f"{split}.jsonl"):
            if r.get("src") and r.get("tgt"):
                records.append({"src": r["src"], "tgt": r["tgt"],
                                 "src_lang": r.get("src_lang", "eng"),
                                 "tgt_lang": r.get("tgt_lang", lang)})
    if split == "train":
        for r in load_tm_records():
            if r.get("src") and r.get("tgt"):
                records.append(r)
    if not quiet:
        log.info(f"[T2T/{split}] {len(records):,} records loaded")
    return records


# ── Generic training loop ─────────────────────────────────────
def run_training(accelerator, model, train_loader, dev_loader,
                 optimizer, scheduler, ckpt_path: Path, task: str):
    is_main = accelerator.is_main_process
    best_dev_loss = float("inf")
    run_start = time.time()

    if is_main:
        log.info(f"[{task}] Train batches/epoch={len(train_loader)} Dev batches={len(dev_loader)}")

    for epoch in range(1, MAX_EPOCHS + 1):
        if hasattr(train_loader.sampler, "set_epoch"):
            train_loader.sampler.set_epoch(epoch)
        model.train()
        epoch_loss = 0.0
        epoch_start = time.time()
        window_start = epoch_start

        for step, batch in enumerate(train_loader, 1):
            if batch is None:
                continue
            with accelerator.accumulate(model):
                loss = model(**batch).loss
                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
            epoch_loss += loss.item()

            if is_main and step % LOG_EVERY == 0:
                elapsed = time.time() - window_start
                steps_per_s = LOG_EVERY / max(elapsed, 1e-6)
                remaining_s = (len(train_loader) - step) / max(steps_per_s, 1e-6)
                mem_gb = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0.0
                log.info(
                    f"[{task}] Epoch {epoch}/{MAX_EPOCHS} | Step {step}/{len(train_loader)} "
                    f"| Loss {epoch_loss/step:.4f} | LR {scheduler.get_last_lr()[0]:.2e} "
                    f"| {steps_per_s:.2f} steps/s | GPU mem {mem_gb:.1f}GB "
                    f"| ETA {remaining_s/60:.1f}min"
                )
                window_start = time.time()

        if is_main:
            model.eval()
            dev_loss = 0.0
            with torch.no_grad():
                for batch in dev_loader:
                    dev_loss += model(**batch).loss.item()
            dev_loss /= max(len(dev_loader), 1)
            epoch_mins = (time.time() - epoch_start) / 60
            log.info(f"[{task}] Epoch {epoch}/{MAX_EPOCHS} complete in {epoch_mins:.1f}min "
                     f"| Train Loss {epoch_loss/max(len(train_loader),1):.4f} | Dev Loss {dev_loss:.4f}")

            if dev_loss < best_dev_loss:
                best_dev_loss = dev_loss
                unwrapped = accelerator.unwrap_model(model)
                unwrapped.save_pretrained(str(ckpt_path / "best"))
                log.info(f"[OK] [{task}] Checkpoint saved -> {ckpt_path / 'best'} (dev_loss={dev_loss:.4f})")
            else:
                log.info(f"[{task}] No improvement (best={best_dev_loss:.4f}), checkpoint not updated")

    if is_main:
        total_mins = (time.time() - run_start) / 60
        log.info(f"[{task}] Done in {total_mins:.1f}min. Best dev loss: {best_dev_loss:.4f}")


# ── Accelerator builder ───────────────────────────────────────
def make_accelerator(grad_accum: int) -> Accelerator:
    return Accelerator(
        mixed_precision="bf16",
        gradient_accumulation_steps=grad_accum,
        kwargs_handlers=[InitProcessGroupKwargs(backend="gloo")],
    )


# ── ASR fine-tuning ───────────────────────────────────────────
def train_asr():
    accelerator = make_accelerator(GRAD_ACCUM)
    is_main = accelerator.is_main_process
    if is_main:
        log.info(f"{'='*60}")
        log.info(f"Full Fine-tune SeamlessM4T [ASR] | FSDP | {accelerator.num_processes} GPUs")
        log.info(f"{'='*60}")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                log.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        log.info(f"Batch/GPU={BATCH_ASR} GradAccum={GRAD_ACCUM} LR={LR_SPEECH} Epochs={MAX_EPOCHS}")
        log.info(f"Loading model from {MODEL_PATH} ...")

    t_load = time.time()
    processor = AutoProcessor.from_pretrained(str(MODEL_PATH))
    model = SeamlessM4Tv2ForSpeechToText.from_pretrained(
        str(MODEL_PATH), torch_dtype=torch.bfloat16
    )
    model.gradient_checkpointing_enable()
    if is_main:
        log.info(f"Model loaded in {time.time() - t_load:.1f}s")

    train_recs = build_asr_records("train", quiet=not is_main)
    dev_recs   = build_asr_records("dev", quiet=not is_main)
    if not train_recs:
        if is_main:
            log.warning("No ASR data. Run download_datasets.py first.")
        return

    train_ds = ASRDataset(train_recs, processor, "hin")
    dev_ds   = ASRDataset(dev_recs,   processor, "hin")
    train_sampler = DistributedSampler(
        train_ds, accelerator.num_processes, accelerator.process_index, shuffle=True
    ) if accelerator.num_processes > 1 else None
    train_loader = DataLoader(train_ds, BATCH_ASR, sampler=train_sampler,
                              shuffle=(train_sampler is None), collate_fn=train_ds.collate,
                              num_workers=0, pin_memory=False)
    dev_loader   = DataLoader(dev_ds, BATCH_ASR, shuffle=False,
                              collate_fn=dev_ds.collate, num_workers=0, pin_memory=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR_SPEECH, weight_decay=0.01)
    total_steps = (len(train_loader) // GRAD_ACCUM) * MAX_EPOCHS
    scheduler   = get_linear_schedule_with_warmup(optimizer, WARMUP_STEPS, total_steps)

    model, optimizer, train_loader, dev_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, dev_loader, scheduler
    )
    ckpt_path = CKPT_DIR / "asr"
    if accelerator.is_main_process:
        ckpt_path.mkdir(parents=True, exist_ok=True)
    run_training(accelerator, model, train_loader, dev_loader, optimizer, scheduler, ckpt_path, "ASR")


# ── T2T fine-tuning ───────────────────────────────────────────
def train_t2t():
    accelerator = make_accelerator(GRAD_ACCUM)
    is_main = accelerator.is_main_process
    if is_main:
        log.info(f"{'='*60}")
        log.info(f"Full Fine-tune SeamlessM4T [T2T] | FSDP | {accelerator.num_processes} GPUs")
        log.info(f"{'='*60}")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                log.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        log.info(f"Batch/GPU={BATCH_T2T} GradAccum={GRAD_ACCUM} LR={LR_TEXT} Epochs={MAX_EPOCHS}")
        log.info(f"Loading model from {MODEL_PATH} ...")

    t_load = time.time()
    processor = AutoProcessor.from_pretrained(str(MODEL_PATH))
    model = SeamlessM4Tv2ForTextToText.from_pretrained(
        str(MODEL_PATH), torch_dtype=torch.bfloat16
    )
    model.gradient_checkpointing_enable()
    # Freeze speech-only params unused in T2T forward pass to prevent DDP grad-sync crash
    for name, param in model.named_parameters():
        if any(k in name for k in ("speech_encoder", "t2u", "vocoder")):
            param.requires_grad_(False)
    if is_main:
        log.info(f"Model loaded in {time.time() - t_load:.1f}s")

    train_recs = build_text_records("train", quiet=not is_main)
    dev_recs   = build_text_records("dev", quiet=not is_main)
    if not train_recs:
        if is_main:
            log.warning("No T2T data found.")
        return

    train_ds = TextDataset(train_recs, processor)
    dev_ds   = TextDataset(dev_recs,   processor)
    train_sampler = DistributedSampler(
        train_ds, accelerator.num_processes, accelerator.process_index, shuffle=True
    ) if accelerator.num_processes > 1 else None
    train_loader = DataLoader(train_ds, BATCH_T2T, sampler=train_sampler,
                              shuffle=(train_sampler is None), collate_fn=train_ds.collate,
                              num_workers=0, pin_memory=False)
    dev_loader   = DataLoader(dev_ds, BATCH_T2T, shuffle=False,
                              collate_fn=dev_ds.collate, num_workers=0, pin_memory=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR_TEXT, weight_decay=0.01)
    total_steps = (len(train_loader) // GRAD_ACCUM) * MAX_EPOCHS
    scheduler   = get_linear_schedule_with_warmup(optimizer, WARMUP_STEPS, total_steps)

    model, optimizer, train_loader, dev_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, dev_loader, scheduler
    )
    ckpt_path = CKPT_DIR / "t2t"
    if accelerator.is_main_process:
        ckpt_path.mkdir(parents=True, exist_ok=True)
    run_training(accelerator, model, train_loader, dev_loader, optimizer, scheduler, ckpt_path, "T2T")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["asr", "t2t", "all"], default="asr")
    args = parser.parse_args()
    tasks = {"asr": train_asr, "t2t": train_t2t}
    to_run = list(tasks.items()) if args.task == "all" else [(args.task, tasks[args.task])]
    for name, fn in to_run:
        try:
            fn()
        except Exception:
            log.exception(f"[{name}] Training crashed")
            raise
