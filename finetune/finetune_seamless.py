# ============================================================
# finetune_seamless.py  — v2
# Fine-tune SeamlessM4T-v2-large (T2T fallback translator)
#
# Improvements over v1:
#   1. Label smoothing 0.1
#   2. Cosine LR with warmup (was linear)
#   3. Quality filter: length ratio 0.25–6.0
#   4. Early stopping patience=2
#   5. TM/human-feedback 5x (was 3x)
#   6. Per-lang weights matching IndicTrans2 script
#   7. All 22 langs (was SEAMLESS_LANGS subset)
#   8. 5 epochs (was 3)
#
# Usage:
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_seamless.py --task t2t
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_seamless.py --task asr
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_seamless.py --task all
# ============================================================

import argparse, json, os, random, time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from transformers import (
    AutoProcessor,
    SeamlessM4Tv2ForSpeechToText,
    SeamlessM4Tv2ForTextToText,
    get_cosine_schedule_with_warmup,
)
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs

from pipeline.lang_config import SEAMLESS_CODES, ALL_22
from pipeline.logger import get_logger

log = get_logger("finetune_seamless", "finetune_seamless.log")

# ── Paths ──────────────────────────────────────────────────────
MODEL_PATH = Path("models/seamless")
AUDIO_DIR  = Path("datasets/audio")
TEXT_DIR   = Path("datasets/parallel")
CKPT_DIR   = Path("checkpoints/seamless")
TM_PATH    = Path("translation_memory/govt_tm.jsonl")
HF_PATH    = Path("translation_memory/human_feedback.jsonl")

SAMPLE_RATE = 16_000

# ── Hyperparams ────────────────────────────────────────────────
BATCH_ASR       = 4
BATCH_T2T       = 8
GRAD_ACCUM      = 8
MAX_EPOCHS      = 5
LR_SPEECH       = 5e-6
LR_TEXT         = 2e-5
WARMUP_RATIO    = 0.06
MAX_AUDIO_S     = 30
MAX_TEXT_LEN    = 256
LOG_EVERY       = 50
LABEL_SMOOTHING = 0.1
EARLY_STOP_PAT  = 2
TM_WEIGHT       = 5

# Per-lang weights — same tiers as IndicTrans2
_LANG_WEIGHTS = {
    "ben": 1.0, "guj": 1.0, "hin": 3.0, "kan": 1.0, "mal": 1.0,
    "mar": 1.0, "ory": 1.0, "pan": 1.0, "tam": 1.0, "tel": 1.0,
    "asm": 1.0, "urd": 1.0, "nep": 1.0,
    "kas": 2.0, "mai": 2.0, "mni": 2.0, "sat": 2.0, "snd": 2.0,
    "bod": 4.0, "doi": 4.0, "kok": 4.0, "san": 4.0,
}

# Only langs SeamlessM4T actually supports for T2T
_SEAMLESS_T2T_LANGS = {k for k in SEAMLESS_CODES if k in ALL_22}


# ── Helpers ────────────────────────────────────────────────────
def load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_tm_records() -> list:
    return (load_jsonl(TM_PATH) + load_jsonl(HF_PATH)) * TM_WEIGHT


def _quality_ok(src: str, tgt: str) -> bool:
    if not src.strip() or not tgt.strip():
        return False
    ratio = len(tgt) / max(len(src), 1)
    return 0.25 <= ratio <= 6.0


def _smooth_loss(logits: torch.Tensor, labels: torch.Tensor,
                 smoothing: float = LABEL_SMOOTHING) -> torch.Tensor:
    vocab = logits.size(-1)
    log_probs = F.log_softmax(logits.float(), dim=-1)
    mask = labels != -100
    flat_labels = labels.clone()
    flat_labels[~mask] = 0
    nll    = -log_probs.gather(dim=-1, index=flat_labels.unsqueeze(-1)).squeeze(-1)
    smooth = -log_probs.sum(dim=-1) / vocab
    loss   = (1 - smoothing) * nll + smoothing * smooth
    return loss[mask].mean()


# ── ASR Dataset ────────────────────────────────────────────────
class ASRDataset(Dataset):
    def __init__(self, records, processor, lang):
        self.records   = records
        self.processor = processor
        self.lang      = SEAMLESS_CODES.get(lang, lang)

    def __len__(self): return len(self.records)

    def __getitem__(self, idx):
        import librosa
        r = self.records[idx]
        audio, _ = librosa.load(r["audio_path"], sr=SAMPLE_RATE, mono=True,
                                duration=MAX_AUDIO_S)
        return audio.astype("float32"), r["text"]

    def collate(self, batch):
        audios, texts = zip(*batch)
        inputs = self.processor(audios=list(audios), sampling_rate=SAMPLE_RATE,
                                return_tensors="pt", padding=True)
        labels = self.processor(text=list(texts), src_lang=self.lang,
                                return_tensors="pt", padding=True,
                                truncation=True, max_length=MAX_TEXT_LEN).input_ids
        labels[labels == self.processor.tokenizer.pad_token_id] = -100
        return {**inputs, "labels": labels}


# ── T2T Dataset ────────────────────────────────────────────────
class TextDataset(Dataset):
    def __init__(self, records, processor):
        self.records   = records
        self.processor = processor

    def __len__(self): return len(self.records)
    def __getitem__(self, idx): return self.records[idx]

    def collate(self, batch):
        from collections import defaultdict
        # ory not in SeamlessM4T vocab
        batch = [r for r in batch
                 if r.get("src_lang") != "ory" and r.get("tgt_lang") != "ory"]
        if not batch:
            return None
        groups = defaultdict(list)
        for r in batch:
            groups[(r["src_lang"], r["tgt_lang"])].append(r)

        all_ids, all_masks, all_labels = [], [], []
        for (src_lang, tgt_lang), recs in groups.items():
            sm_src = SEAMLESS_CODES.get(src_lang, src_lang)
            sm_tgt = SEAMLESS_CODES.get(tgt_lang, tgt_lang)
            enc = self.processor(text=[r["src"] for r in recs], src_lang=sm_src,
                                 return_tensors="pt", padding=True,
                                 truncation=True, max_length=MAX_TEXT_LEN)
            lbl = self.processor(text=[r["tgt"] for r in recs], src_lang=sm_tgt,
                                 return_tensors="pt", padding=True,
                                 truncation=True, max_length=MAX_TEXT_LEN).input_ids
            lbl[lbl == self.processor.tokenizer.pad_token_id] = -100
            all_ids.append(enc["input_ids"])
            all_masks.append(enc["attention_mask"])
            all_labels.append(lbl)

        max_src = max(t.shape[1] for t in all_ids)
        max_tgt = max(t.shape[1] for t in all_labels)

        def pad2d(t, length, val=0):
            d = length - t.shape[1]
            return F.pad(t, (0, d), value=val) if d > 0 else t

        return {
            "input_ids":      torch.cat([pad2d(t, max_src)       for t in all_ids]),
            "attention_mask": torch.cat([pad2d(t, max_src)       for t in all_masks]),
            "labels":         torch.cat([pad2d(t, max_tgt, -100) for t in all_labels]),
        }


# ── Data builders ──────────────────────────────────────────────
def build_asr_records(split: str, quiet: bool = False) -> list:
    records = []
    for source in ["kathbath", "fleurs", "indicsuper"]:
        for lang in _SEAMLESS_T2T_LANGS:
            for r in load_jsonl(AUDIO_DIR / source / lang / f"{split}.jsonl"):
                if r.get("audio_path") and r.get("text"):
                    records.append(r)
    if not quiet:
        log.info(f"[ASR/{split}] {len(records):,} records")
    return records


def build_text_records(split: str, quiet: bool = False) -> list:
    records = []
    for lang in ALL_22:
        sm_src = SEAMLESS_CODES.get("eng")
        sm_tgt = SEAMLESS_CODES.get(lang)
        if not sm_src or not sm_tgt:
            continue  # skip langs SeamlessM4T doesn't support (ory, kok, san)
        raw = load_jsonl(TEXT_DIR / lang / f"{split}.jsonl")
        lang_recs = []
        for r in raw:
            src_t = r.get("src", "")
            tgt_t = r.get("tgt", "")
            if _quality_ok(src_t, tgt_t):
                lang_recs.append({"src": src_t, "tgt": tgt_t,
                                  "src_lang": "eng", "tgt_lang": lang})
        weight = _LANG_WEIGHTS.get(lang, 1.0) if split == "train" else 1.0
        records.extend(lang_recs * max(1, round(weight)))

    if split == "train":
        for r in load_tm_records():
            src_t = r.get("src", "")
            tgt_t = r.get("tgt", "")
            tgt_l = r.get("tgt_lang", "")
            if tgt_l in ALL_22 and _quality_ok(src_t, tgt_t):
                records.append({"src": src_t, "tgt": tgt_t,
                                 "src_lang": "eng", "tgt_lang": tgt_l})
        random.shuffle(records)

    if not quiet:
        log.info(f"[T2T/{split}] {len(records):,} records")
    return records


# ── Generic training loop ──────────────────────────────────────
def run_training(accelerator, model, train_loader, dev_loader,
                 optimizer, scheduler, ckpt_path: Path, task: str,
                 use_smooth_loss: bool = True):
    is_main = accelerator.is_main_process
    best_dev_loss = float("inf")
    no_improve    = 0
    run_start     = time.time()

    if is_main:
        log.info(f"[{task}] train_batches={len(train_loader)} dev_batches={len(dev_loader)}")

    for epoch in range(1, MAX_EPOCHS + 1):
        if hasattr(train_loader.sampler, "set_epoch"):
            train_loader.sampler.set_epoch(epoch)
        model.train()
        epoch_loss   = 0.0
        epoch_start  = time.time()
        window_start = epoch_start

        for step, batch in enumerate(train_loader, 1):
            if batch is None:
                continue
            with accelerator.accumulate(model):
                outputs = model(**batch)
                loss = (_smooth_loss(outputs.logits, batch["labels"])
                        if use_smooth_loss else outputs.loss)
                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
            epoch_loss += loss.item()

            if is_main and step % LOG_EVERY == 0:
                elapsed     = time.time() - window_start
                sps         = LOG_EVERY / max(elapsed, 1e-6)
                eta         = (len(train_loader) - step) / max(sps, 1e-6)
                mem_gb      = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0.0
                log.info(f"[{task}] Ep {epoch}/{MAX_EPOCHS} | Step {step}/{len(train_loader)} "
                         f"| Loss {epoch_loss/step:.4f} | LR {scheduler.get_last_lr()[0]:.2e} "
                         f"| {sps:.2f} sps | GPU {mem_gb:.1f}GB | ETA {eta/60:.1f}min")
                window_start = time.time()

        # Dev eval
        model.eval()
        dev_sum   = torch.zeros(1, device=accelerator.device)
        dev_steps = 0
        with torch.no_grad():
            for batch in dev_loader:
                if batch is None:
                    continue
                outputs = model(**batch)
                loss = (_smooth_loss(outputs.logits, batch["labels"])
                        if use_smooth_loss else outputs.loss)
                dev_sum   += loss
                dev_steps += 1
        dev_sum  = accelerator.reduce(dev_sum, reduction="mean")
        dev_loss = (dev_sum / max(dev_steps, 1)).item()

        if is_main:
            epoch_mins = (time.time() - epoch_start) / 60
            log.info(f"[{task}] Epoch {epoch}/{MAX_EPOCHS} done {epoch_mins:.1f}min "
                     f"| TrainLoss {epoch_loss/max(len(train_loader),1):.4f} "
                     f"| DevLoss {dev_loss:.4f}")
            if dev_loss < best_dev_loss:
                best_dev_loss = dev_loss
                no_improve    = 0
                accelerator.unwrap_model(model).save_pretrained(str(ckpt_path / "best"))
                log.info(f"[SAVED] {ckpt_path/'best'}  dev_loss={dev_loss:.4f}")
            else:
                no_improve += 1
                log.info(f"No improvement ({no_improve}/{EARLY_STOP_PAT}) best={best_dev_loss:.4f}")
                if no_improve >= EARLY_STOP_PAT:
                    log.info(f"[EARLY STOP] patience exhausted.")
                    break

    if is_main:
        log.info(f"[{task}] Done in {(time.time()-run_start)/60:.1f}min. "
                 f"Best dev loss: {best_dev_loss:.4f}")


def _make_accelerator():
    return Accelerator(
        mixed_precision="bf16",
        gradient_accumulation_steps=GRAD_ACCUM,
        kwargs_handlers=[InitProcessGroupKwargs(backend="gloo")],
    )


# ── ASR fine-tune ──────────────────────────────────────────────
def train_asr():
    accelerator = _make_accelerator()
    is_main = accelerator.is_main_process
    if is_main:
        log.info(f"{'='*60}\nSeamlessM4T ASR fine-tune | {accelerator.num_processes} GPUs\n{'='*60}")

    processor = AutoProcessor.from_pretrained(str(MODEL_PATH))
    model = SeamlessM4Tv2ForSpeechToText.from_pretrained(
        str(MODEL_PATH), torch_dtype=torch.bfloat16)
    model.gradient_checkpointing_enable()

    train_recs = build_asr_records("train", quiet=not is_main)
    dev_recs   = build_asr_records("dev",   quiet=not is_main)
    if not train_recs:
        if is_main:
            log.warning("No ASR data — run download_datasets.py first.")
        return

    train_ds = ASRDataset(train_recs, processor, "hin")
    dev_ds   = ASRDataset(dev_recs,   processor, "hin")
    sampler  = DistributedSampler(train_ds, accelerator.num_processes,
                                  accelerator.process_index, shuffle=True) \
               if accelerator.num_processes > 1 else None
    train_loader = DataLoader(train_ds, BATCH_ASR, sampler=sampler,
                              shuffle=(sampler is None), collate_fn=train_ds.collate,
                              num_workers=0, pin_memory=False)
    dev_loader   = DataLoader(dev_ds, BATCH_ASR, shuffle=False,
                              collate_fn=dev_ds.collate, num_workers=0, pin_memory=False)

    total_steps  = (len(train_loader) // GRAD_ACCUM) * MAX_EPOCHS
    warmup_steps = max(1, int(total_steps * WARMUP_RATIO))
    optimizer    = torch.optim.AdamW(model.parameters(), lr=LR_SPEECH,
                                     weight_decay=0.01, betas=(0.9, 0.98))
    scheduler    = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    model, optimizer, train_loader, dev_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, dev_loader, scheduler)

    ckpt_path = CKPT_DIR / "asr"
    if is_main:
        ckpt_path.mkdir(parents=True, exist_ok=True)
    # ASR uses model's built-in CTC/CE loss (no logits for smooth loss)
    run_training(accelerator, model, train_loader, dev_loader,
                 optimizer, scheduler, ckpt_path, "ASR", use_smooth_loss=False)


# ── T2T fine-tune ──────────────────────────────────────────────
def train_t2t():
    accelerator = _make_accelerator()
    is_main = accelerator.is_main_process
    if is_main:
        log.info(f"{'='*60}\nSeamlessM4T T2T fine-tune | {accelerator.num_processes} GPUs\n"
                 f"LabelSmoothing={LABEL_SMOOTHING} | CosLR | EarlyStop(pat={EARLY_STOP_PAT})\n{'='*60}")

    processor = AutoProcessor.from_pretrained(str(MODEL_PATH))
    model = SeamlessM4Tv2ForTextToText.from_pretrained(
        str(MODEL_PATH), torch_dtype=torch.bfloat16)
    model.gradient_checkpointing_enable()
    # Freeze speech-only params — not used in T2T, prevents DDP grad-sync crash
    for name, param in model.named_parameters():
        if any(k in name for k in ("speech_encoder", "t2u", "vocoder")):
            param.requires_grad_(False)

    train_recs = build_text_records("train", quiet=not is_main)
    dev_recs   = build_text_records("dev",   quiet=not is_main)
    if not train_recs:
        if is_main:
            log.warning("No T2T data found.")
        return

    train_ds = TextDataset(train_recs, processor)
    dev_ds   = TextDataset(dev_recs,   processor)
    sampler  = DistributedSampler(train_ds, accelerator.num_processes,
                                  accelerator.process_index, shuffle=True) \
               if accelerator.num_processes > 1 else None
    train_loader = DataLoader(train_ds, BATCH_T2T, sampler=sampler,
                              shuffle=(sampler is None), collate_fn=train_ds.collate,
                              num_workers=0, pin_memory=False)
    dev_loader   = DataLoader(dev_ds, BATCH_T2T, shuffle=False,
                              collate_fn=dev_ds.collate, num_workers=0, pin_memory=False)

    total_steps  = (len(train_loader) // GRAD_ACCUM) * MAX_EPOCHS
    warmup_steps = max(1, int(total_steps * WARMUP_RATIO))
    optimizer    = torch.optim.AdamW(model.parameters(), lr=LR_TEXT,
                                     weight_decay=0.01, betas=(0.9, 0.98), eps=1e-9)
    scheduler    = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    model, optimizer, train_loader, dev_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, dev_loader, scheduler)

    ckpt_path = CKPT_DIR / "t2t"
    if is_main:
        ckpt_path.mkdir(parents=True, exist_ok=True)
    run_training(accelerator, model, train_loader, dev_loader,
                 optimizer, scheduler, ckpt_path, "T2T", use_smooth_loss=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["asr", "t2t", "all"], default="t2t")
    args = parser.parse_args()
    tasks = {"asr": train_asr, "t2t": train_t2t}
    to_run = list(tasks.items()) if args.task == "all" else [(args.task, tasks[args.task])]
    for name, fn in to_run:
        try:
            fn()
        except Exception:
            log.exception(f"[{name}] Training crashed")
            raise
