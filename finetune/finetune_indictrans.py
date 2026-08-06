# ============================================================
# finetune_indictrans.py
# Full Fine-tune IndicTrans2 — HuggingFace Accelerate + FSDP
#
# Method: Full Fine-tune (100% params) + FSDP (Fully Sharded DP)
#   - Windows-compatible alternative to DeepSpeed ZeRO-3
#   - FSDP shards weights+gradients+optimizer across 4x A6000
#   - 192GB total VRAM used as one logical pool
#   - bf16 mixed precision (Ampere A6000 native)
#   - Gradient checkpointing for activation memory savings
#   - Best quality: all parameters updated, not just adapters
#
# en_indic direction: trains only on 12 high/medium-resource langs
#   (hin, ben, tam, tel, kan, mal, mar, guj, pan, ory, asm, urd)
#   Hindi is weighted 3x — it is the pivot lang for mni/sat/san.
#   kok/snd/kas/bod/doi excluded — pipeline bypasses IndicTrans2 for them.
#   indic_en / indic_indic directions: unchanged (train on all available data).
#
# Usage:
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_indictrans.py --direction en_indic
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       finetune/finetune_indictrans.py --direction all
# ============================================================

import argparse
import json
import os
import time
os.environ.setdefault("PL_TORCH_DISTRIBUTED_BACKEND", "gloo")
os.environ.setdefault("TORCH_DISTRIBUTED_DEFAULT_BACKEND", "gloo")
os.environ.setdefault("ACCELERATE_USE_FSDP", "false")
os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
os.environ.setdefault("MASTER_PORT", "29500")
os.environ.setdefault("GLOO_SOCKET_IFNAME", "loopback")
from pathlib import Path

import torch
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs

from pipeline.lang_config import INDIC_TRANS2_CODES, ALL_22
from pipeline.logger import get_logger

log = get_logger("finetune_indictrans", "finetune_indictrans.log")

# ── Paths ─────────────────────────────────────────────────────
MODELS_DIR = Path("models/indic_tr")
DATA_DIR   = Path("datasets/parallel")
CKPT_DIR   = Path("checkpoints/indictrans")
TM_PATH    = Path("translation_memory/govt_tm.jsonl")
HF_PATH    = Path("translation_memory/human_feedback.jsonl")

# ── Hyperparams ───────────────────────────────────────────────
BATCH_SIZE   = 16     # per GPU — A6000 48GB can handle 16 with FSDP sharding
GRAD_ACCUM   = 4      # effective batch = 16 * 4 * 4 GPUs = 256 (same, fewer accum steps)
MAX_EPOCHS   = 3
LR           = 3e-5   # slightly higher LR — larger effective batch
WARMUP_STEPS = 200
MAX_LEN      = 256
LOG_EVERY    = 100

# en_indic: 12 high/medium-resource langs only.
# kok/snd/kas -> NLLB-only in pipeline (IndicTrans2 not used).
# bod/doi     -> Seamless-first in pipeline (IndicTrans2 not primary).
# mni/sat/san -> pivot via Hindi (improving hin covers these indirectly).
EN_INDIC_TRAIN_LANGS = {
    "hin", "ben", "tam", "tel", "kan", "mal", "mar", "guj", "pan", "ory", "asm", "urd"
}
# Hindi weighted 3x — pivot language for mni/sat/san
HIN_WEIGHT = 3

INDIC_INDIC_PAIRS = [
    ("hin", "ben"), ("hin", "tam"), ("hin", "tel"), ("hin", "mar"),
    ("hin", "guj"), ("hin", "kan"), ("hin", "mal"), ("hin", "pan"),
    ("hin", "ory"), ("hin", "asm"), ("hin", "urd"), ("hin", "nep"),
    ("hin", "bod"), ("hin", "doi"), ("hin", "kas"), ("hin", "kok"),
    ("hin", "mni"), ("hin", "mai"), ("hin", "san"), ("hin", "sat"),
    ("hin", "snd"),
]

_VALID_LANG_TAG = set(INDIC_TRANS2_CODES.values())


# ── Dataset ───────────────────────────────────────────────────
class ParallelDataset(Dataset):
    def __init__(self, records: list, tokenizer):
        self.records   = records
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        return self.records[idx]

    def collate(self, batch):
        from collections import defaultdict
        groups = defaultdict(list)
        for r in batch:
            groups[(r["src_lang"], r["tgt_lang"])].append(r)

        all_input_ids, all_masks, all_labels = [], [], []

        for (src_lang, tgt_lang), recs in groups.items():
            srcs = [f"{src_lang} {tgt_lang} {r['src']}" for r in recs]
            tgts = [r["tgt"] for r in recs]

            self.tokenizer._switch_to_input_mode()
            enc = self.tokenizer(
                srcs, return_tensors="pt", padding=True,
                truncation=True, max_length=MAX_LEN,
            )

            self.tokenizer._switch_to_target_mode()
            tgt_ids_list = [
                self.tokenizer.convert_tokens_to_ids(
                    self.tokenizer.spm.EncodeAsPieces(t)
                ) + [self.tokenizer.eos_token_id]
                for t in tgts
            ]
            self.tokenizer._switch_to_input_mode()

            max_tgt_len = min(max(len(ids) for ids in tgt_ids_list), MAX_LEN)
            labels = torch.full((len(tgt_ids_list), max_tgt_len), -100, dtype=torch.long)
            for i, ids in enumerate(tgt_ids_list):
                ids = ids[:max_tgt_len]
                labels[i, :len(ids)] = torch.tensor(ids, dtype=torch.long)

            all_input_ids.append(enc["input_ids"])
            all_masks.append(enc["attention_mask"])
            all_labels.append(labels)

        max_src = max(t.shape[1] for t in all_input_ids)
        max_tgt = max(t.shape[1] for t in all_labels)

        def pad2d(t, length, pad_val=0):
            diff = length - t.shape[1]
            return torch.nn.functional.pad(t, (0, diff), value=pad_val) if diff > 0 else t

        return {
            "input_ids":      torch.cat([pad2d(t, max_src) for t in all_input_ids]),
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


def _valid_record(r: dict) -> bool:
    return (
        r.get("src_lang") in _VALID_LANG_TAG
        and r.get("tgt_lang") in _VALID_LANG_TAG
        and bool(r.get("src"))
        and bool(r.get("tgt"))
    )


def build_records(direction: str, split: str, quiet: bool = False) -> list:
    records = []
    tm_records = load_tm_records() if split == "train" else []

    if direction in ("en_indic", "indic_en"):
        # en_indic: restrict to 12 target langs; indic_en: use all available
        lang_set = EN_INDIC_TRAIN_LANGS if direction == "en_indic" else set(ALL_22)
        for lang in ALL_22:
            if lang not in lang_set:
                continue
            raw = load_jsonl(DATA_DIR / lang / f"{split}.jsonl")
            src_code = INDIC_TRANS2_CODES.get("eng" if direction == "en_indic" else lang)
            tgt_code = INDIC_TRANS2_CODES.get(lang if direction == "en_indic" else "eng")
            if not src_code or not tgt_code:
                continue
            lang_records = []
            for r in raw:
                src_text = r["src"] if direction == "en_indic" else r.get("tgt", "")
                tgt_text = r["tgt"] if direction == "en_indic" else r.get("src", "")
                if src_text and tgt_text:
                    lang_records.append({"src": src_text, "tgt": tgt_text,
                                         "src_lang": src_code, "tgt_lang": tgt_code})
            # Boost Hindi 3x — pivot language for mni/sat/san
            repeat = HIN_WEIGHT if (direction == "en_indic" and lang == "hin") else 1
            records.extend(lang_records * repeat)
        if direction == "en_indic":
            for r in tm_records:
                tgt_lang_short = r.get("tgt_lang", "")
                if tgt_lang_short not in EN_INDIC_TRAIN_LANGS:
                    continue
                sc = INDIC_TRANS2_CODES.get("eng")
                tc = INDIC_TRANS2_CODES.get(tgt_lang_short)
                if sc and tc and r.get("src") and r.get("tgt"):
                    records.append({"src": r["src"], "tgt": r["tgt"],
                                    "src_lang": sc, "tgt_lang": tc})

    elif direction == "indic_indic":
        for src_lang, tgt_lang in INDIC_INDIC_PAIRS:
            src_raw = load_jsonl(DATA_DIR / src_lang / f"{split}.jsonl")
            tgt_raw = load_jsonl(DATA_DIR / tgt_lang / f"{split}.jsonl")
            for s, t in zip(src_raw, tgt_raw):
                src_text = s.get("tgt", "")
                tgt_text = t.get("tgt", "")
                sc = INDIC_TRANS2_CODES.get(src_lang)
                tc = INDIC_TRANS2_CODES.get(tgt_lang)
                if src_text and tgt_text and sc and tc:
                    records.append({"src": src_text, "tgt": tgt_text,
                                    "src_lang": sc, "tgt_lang": tc})

    before = len(records)
    records = [r for r in records if _valid_record(r)]
    dropped = before - len(records)
    if not quiet:
        if dropped:
            log.info(f"[{direction}/{split}] Dropped {dropped:,} invalid records")
        log.info(f"[{direction}/{split}] {len(records):,} records loaded")
    return records


# ── Train ─────────────────────────────────────────────────────
def train(direction: str):
    import os
    os.environ.setdefault('NCCL_BACKEND', 'gloo')
    accelerator = Accelerator(
        mixed_precision="bf16",
        gradient_accumulation_steps=GRAD_ACCUM,
        kwargs_handlers=[InitProcessGroupKwargs(backend="gloo")],
    )
    is_main = accelerator.is_main_process

    model_path = str(MODELS_DIR / direction)
    ckpt_path  = CKPT_DIR / direction
    if is_main:
        ckpt_path.mkdir(parents=True, exist_ok=True)
        log.info(f"{'='*60}")
        log.info(f"Full Fine-tune IndicTrans2 [{direction}] | FSDP | {accelerator.num_processes} GPUs")
        if direction == "en_indic":
            log.info(f"en_indic: {len(EN_INDIC_TRAIN_LANGS)} langs={sorted(EN_INDIC_TRAIN_LANGS)} | hin weight={HIN_WEIGHT}x")
        log.info(f"{'='*60}")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                log.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        log.info(f"Batch/GPU={BATCH_SIZE} GradAccum={GRAD_ACCUM} "
                 f"EffectiveBatch={BATCH_SIZE * GRAD_ACCUM * accelerator.num_processes} "
                 f"LR={LR} Epochs={MAX_EPOCHS}")
        log.info(f"Loading model from {model_path} ...")

    t_load = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    _VALID_LANG_TAG.update(INDIC_TRANS2_CODES.values())

    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_path, trust_remote_code=True, torch_dtype=torch.bfloat16
    )
    model.gradient_checkpointing_enable()
    if is_main:
        log.info(f"Model loaded in {time.time() - t_load:.1f}s")

    train_records = build_records(direction, "train", quiet=not is_main)
    dev_records   = build_records(direction, "dev", quiet=not is_main)

    if not train_records:
        if is_main:
            log.warning(f"No data for {direction}, skipping.")
        return

    train_ds = ParallelDataset(train_records, tokenizer)
    dev_ds   = ParallelDataset(dev_records,   tokenizer)

    train_sampler = DistributedSampler(
        train_ds, accelerator.num_processes, accelerator.process_index, shuffle=True
    ) if accelerator.num_processes > 1 else None

    train_loader = DataLoader(train_ds, BATCH_SIZE, sampler=train_sampler,
                              shuffle=(train_sampler is None), collate_fn=train_ds.collate,
                              num_workers=0, pin_memory=False)
    dev_loader   = DataLoader(dev_ds, BATCH_SIZE, shuffle=False,
                              collate_fn=dev_ds.collate, num_workers=0, pin_memory=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    total_steps = (len(train_loader) // GRAD_ACCUM) * MAX_EPOCHS
    scheduler   = get_linear_schedule_with_warmup(optimizer, WARMUP_STEPS, total_steps)

    if is_main:
        log.info(f"Train batches/epoch={len(train_loader)} Dev batches={len(dev_loader)} "
                 f"Total optimizer steps={total_steps}")

    # Accelerate wraps model, optimizer, loaders — handles FSDP + bf16 internally
    model, optimizer, train_loader, dev_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, dev_loader, scheduler
    )

    best_dev_loss = float("inf")
    run_start = time.time()

    for epoch in range(1, MAX_EPOCHS + 1):
        if train_sampler:
            train_sampler.set_epoch(epoch)
        model.train()
        epoch_loss = 0.0
        epoch_start = time.time()
        window_start = epoch_start

        for step, batch in enumerate(train_loader, 1):
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
                    f"[{direction}] Epoch {epoch}/{MAX_EPOCHS} | Step {step}/{len(train_loader)} "
                    f"| Loss {epoch_loss/step:.4f} | LR {scheduler.get_last_lr()[0]:.2e} "
                    f"| {steps_per_s:.2f} steps/s | GPU mem {mem_gb:.1f}GB "
                    f"| ETA {remaining_s/60:.1f}min"
                )
                window_start = time.time()

        # Dev eval across all GPUs — no idle ranks
        model.eval()
        dev_loss_tensor = torch.zeros(1, device=accelerator.device)
        dev_steps = 0
        with torch.no_grad():
            for batch in dev_loader:
                dev_loss_tensor += model(**batch).loss
                dev_steps += 1
        dev_loss_tensor = accelerator.reduce(dev_loss_tensor, reduction="mean")
        dev_loss = (dev_loss_tensor / max(dev_steps, 1)).item()

        if is_main:
            epoch_mins = (time.time() - epoch_start) / 60
            log.info(f"[{direction}] Epoch {epoch}/{MAX_EPOCHS} complete in {epoch_mins:.1f}min "
                     f"| Train Loss {epoch_loss/max(len(train_loader),1):.4f} | Dev Loss {dev_loss:.4f}")
            if dev_loss < best_dev_loss:
                best_dev_loss = dev_loss
                unwrapped = accelerator.unwrap_model(model)
                unwrapped.save_pretrained(str(ckpt_path / "best"))
                tokenizer.save_pretrained(str(ckpt_path / "best"))
                log.info(f"[OK] Checkpoint saved -> {ckpt_path / 'best'} (dev_loss={dev_loss:.4f})")
            else:
                log.info(f"No improvement (best={best_dev_loss:.4f}), checkpoint not updated")

    if is_main:
        total_mins = (time.time() - run_start) / 60
        log.info(f"[{direction}] Done in {total_mins:.1f}min. Best dev loss: {best_dev_loss:.4f}")
        log.info(f"Checkpoint -> {ckpt_path / 'best'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction",
                        choices=["en_indic", "indic_en", "indic_indic", "all"],
                        default="en_indic")
    args = parser.parse_args()
    dirs = ["en_indic", "indic_en", "indic_indic"] if args.direction == "all" else [args.direction]
    for d in dirs:
        try:
            train(d)
        except Exception:
            log.exception(f"[{d}] Training crashed")
            raise
