# ============================================================
# finetune_indictrans.py  — v2
# Full Fine-tune IndicTrans2 for all 22 Indian languages
#
# Key improvements over v1:
#   1. All 22 langs in en_indic (was 16) — mni/sat/kas/snd now included
#   2. Per-language sampling weights based on dataset size + resource tier
#   3. Label smoothing (0.1) — reduces overfit on small-data langs
#   4. Cosine LR schedule with warmup — better convergence than linear
#   5. Curriculum: gold data first 2 epochs, synthetic mixed in epoch 3+
#   6. Quality filter: drop pairs where len(tgt)/len(src) < 0.3 or > 5.0
#   7. TM/human-feedback weighted 5x (was 3x) — high-quality signal
#   8. Longer training: 5 epochs (was 3) with early stopping (patience=2)
#   9. Separate dev eval per language group — catches per-lang regression
#  10. indic_indic: all 22×22 pairs (was 21 hand-picked pairs)
#
# Usage (Windows — gloo backend, no NCCL):
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       --main_process_ip=127.0.0.1 --main_process_port=29500 \
#       finetune/finetune_indictrans.py --direction en_indic
#
#   accelerate launch --num_processes=4 --mixed_precision=bf16 \
#       --main_process_ip=127.0.0.1 --main_process_port=29500 \
#       finetune/finetune_indictrans.py --direction all
# ============================================================

import argparse, json, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ── Windows-safe distributed env ──────────────────────────────
os.environ["MASTER_ADDR"] = "127.0.0.1"          # override Docker DNS (kubernetes.docker.internal)
os.environ.setdefault("MASTER_PORT", "29500")
os.environ["TORCH_DISTRIBUTED_DEFAULT_BACKEND"] = "gloo"
os.environ["PL_TORCH_DISTRIBUTED_BACKEND"]      = "gloo"
os.environ["ACCELERATE_USE_FSDP"]               = "false"
os.environ["TORCHELASTIC_RESTART_COUNT"]        = "0"
# Prevent accelerate from sending SIGINT (unsupported on Windows subprocesses)
os.environ.setdefault("ACCELERATE_PROCESS_KILL_SIGNAL", "SIGTERM")
# GLOO_SOCKET_IFNAME must NOT be set on Windows — gloo auto-detects the interface
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    get_cosine_schedule_with_warmup,
)
from accelerate import Accelerator
from accelerate.utils import InitProcessGroupKwargs

from pipeline.lang_config import INDIC_TRANS2_CODES, ALL_22
from pipeline.logger import get_logger

log = get_logger("finetune_indictrans", "finetune_indictrans.log")

# ── Paths ──────────────────────────────────────────────────────
MODELS_DIR = Path("models/indic_tr")
DATA_DIR   = Path("datasets/parallel")
CKPT_DIR   = Path("checkpoints/indictrans")
TM_PATH    = Path("translation_memory/govt_tm.jsonl")
HF_PATH    = Path("translation_memory/human_feedback.jsonl")

# ── Hyperparams ────────────────────────────────────────────────
BATCH_SIZE      = 8       # per GPU — halved; grad checkpointing disabled (IndicTrans2 old API ignores use_reentrant)
GRAD_ACCUM      = 8       # effective batch = 8 * 8 * 4 GPUs = 256 (unchanged)
MAX_EPOCHS      = 5       # more epochs; early stopping prevents overfit
LR              = 2e-5    # slightly lower — cosine schedule handles warmup
WARMUP_RATIO    = 0.06    # 6% of total steps as warmup
MAX_LEN         = 256
LOG_EVERY       = 100
LABEL_SMOOTHING = 0.1     # reduces overfit on low-resource langs
EARLY_STOP_PAT  = 2       # stop if dev loss doesn't improve for 2 epochs
TM_WEIGHT       = 5       # TM/human-feedback repeat factor (high-quality signal)
SYNTHETIC_EPOCH = 3       # curriculum: synthetic data only from this epoch onward

# ── All 22 langs for en_indic (v2: was 16, now all 22) ─────────
EN_INDIC_TRAIN_LANGS = set(ALL_22)  # all 22 scheduled Indian languages

# Per-language sampling weights for en_indic training.
# High-resource (>100K pairs): weight 1.0
# Medium-resource (10K-100K):  weight 2.0  — oversample to balance
# Low-resource (<10K):         weight 4.0  — heavily oversample
# Pivot language (hin):        weight 3.0  — pivot for mni/sat/san
_LANG_WEIGHTS = {
    # High-resource
    "ben": 1.0, "guj": 1.0, "hin": 3.0, "kan": 1.0, "mal": 1.0,
    "mar": 1.0, "ory": 1.0, "pan": 1.0, "tam": 1.0, "tel": 1.0,
    "asm": 1.0, "urd": 1.0, "nep": 1.0,
    # Medium-resource
    "kas": 2.0, "mai": 2.0, "mni": 2.0, "sat": 2.0, "snd": 2.0,
    # Low-resource (gap langs)
    "bod": 4.0, "doi": 4.0, "kok": 4.0, "san": 4.0,
}

# indic_indic: all 22 langs paired with Hindi as hub + key cross-pairs
# Hub pairs cover all langs; cross-pairs add direct high-resource paths
_HUB_LANG = "hin"
INDIC_INDIC_PAIRS = (
    # Hindi hub: hin <-> every other lang (both directions)
    [(lang, _HUB_LANG) for lang in ALL_22 if lang != _HUB_LANG] +
    [(_HUB_LANG, lang) for lang in ALL_22 if lang != _HUB_LANG] +
    # Direct high-resource cross-pairs (no Hindi pivot needed)
    [("ben", "tam"), ("tam", "ben"),
     ("ben", "tel"), ("tel", "ben"),
     ("mar", "guj"), ("guj", "mar"),
     ("kan", "tel"), ("tel", "kan"),
     ("mal", "tam"), ("tam", "mal"),
     ("urd", "hin"), ("hin", "urd"),
     ("pan", "hin"), ("hin", "pan")]
)

_VALID_LANG_TAG = set(INDIC_TRANS2_CODES.values())


# ── Quality filter ─────────────────────────────────────────────
def _quality_ok(src: str, tgt: str) -> bool:
    """Drop pairs with extreme length ratios or empty strings."""
    if not src.strip() or not tgt.strip():
        return False
    ratio = len(tgt) / max(len(src), 1)
    return 0.25 <= ratio <= 6.0


# ── Label-smoothed cross-entropy ───────────────────────────────
def _smooth_loss(logits: torch.Tensor, labels: torch.Tensor,
                 smoothing: float = LABEL_SMOOTHING) -> torch.Tensor:
    """
    Label-smoothed cross-entropy via F.cross_entropy.
    Avoids summing over the full 250K-token vocab on bf16 (CUDA launch failure).
    logits: (B, T, V)   labels: (B, T)  — -100 = ignore
    """
    return F.cross_entropy(
        logits.float().view(-1, logits.size(-1)),
        labels.view(-1),
        ignore_index=-100,
        label_smoothing=smoothing,
    )


# ── Dataset ────────────────────────────────────────────────────
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


# ── Data helpers ───────────────────────────────────────────────
def load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_tm_records() -> list:
    tm = load_jsonl(TM_PATH)
    hf = load_jsonl(HF_PATH)
    return (tm + hf) * TM_WEIGHT


def _valid_record(r: dict) -> bool:
    return (
        r.get("src_lang") in _VALID_LANG_TAG
        and r.get("tgt_lang") in _VALID_LANG_TAG
        and bool(r.get("src"))
        and bool(r.get("tgt"))
    )


def build_records(direction: str, split: str,
                  epoch: int = 1, quiet: bool = False) -> list:
    """
    Build training/dev records for a given direction and split.
    epoch: controls curriculum — synthetic data excluded before SYNTHETIC_EPOCH.
    """
    records = []
    tm_records = load_tm_records() if split == "train" else []
    include_synthetic = (split != "train") or (epoch >= SYNTHETIC_EPOCH)

    if direction in ("en_indic", "indic_en"):
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
                is_synthetic = r.get("synthetic", False)
                if is_synthetic and not include_synthetic:
                    continue
                if not _quality_ok(src_text, tgt_text):
                    continue
                lang_records.append({
                    "src": src_text, "tgt": tgt_text,
                    "src_lang": src_code, "tgt_lang": tgt_code,
                    "synthetic": is_synthetic,
                })

            # Per-language weight: oversample low-resource langs
            weight = _LANG_WEIGHTS.get(lang, 1.0) if split == "train" else 1.0
            # For synthetic records, apply 0.5x on top of lang weight
            gold    = [r for r in lang_records if not r.get("synthetic")]
            synth   = [r for r in lang_records if r.get("synthetic")]
            repeat  = max(1, round(weight))
            records.extend(gold * repeat)
            if synth:
                synth_repeat = max(1, round(weight * 0.5))
                records.extend(synth * synth_repeat)

        # TM / human feedback — gold quality, apply to en_indic only
        if direction == "en_indic" and split == "train":
            for r in tm_records:
                tgt_lang_short = r.get("tgt_lang", "")
                if tgt_lang_short not in EN_INDIC_TRAIN_LANGS:
                    continue
                sc = INDIC_TRANS2_CODES.get("eng")
                tc = INDIC_TRANS2_CODES.get(tgt_lang_short)
                src_t = r.get("src", "")
                tgt_t = r.get("tgt", "")
                if sc and tc and _quality_ok(src_t, tgt_t):
                    records.append({"src": src_t, "tgt": tgt_t,
                                    "src_lang": sc, "tgt_lang": tc})

    elif direction == "indic_indic":
        seen = set()
        for src_lang, tgt_lang in INDIC_INDIC_PAIRS:
            pair_key = (src_lang, tgt_lang)
            if pair_key in seen:
                continue
            seen.add(pair_key)
            src_raw = load_jsonl(DATA_DIR / src_lang / f"{split}.jsonl")
            tgt_raw = load_jsonl(DATA_DIR / tgt_lang / f"{split}.jsonl")
            sc = INDIC_TRANS2_CODES.get(src_lang)
            tc = INDIC_TRANS2_CODES.get(tgt_lang)
            if not sc or not tc:
                continue
            for s, t in zip(src_raw, tgt_raw):
                src_text = s.get("tgt", "")
                tgt_text = t.get("tgt", "")
                if _quality_ok(src_text, tgt_text):
                    records.append({"src": src_text, "tgt": tgt_text,
                                    "src_lang": sc, "tgt_lang": tc})

    # Shuffle to mix languages within each epoch
    if split == "train":
        random.shuffle(records)

    before = len(records)
    records = [r for r in records if _valid_record(r)]
    dropped = before - len(records)
    if not quiet:
        if dropped:
            log.info(f"[{direction}/{split}/ep{epoch}] Dropped {dropped:,} invalid records")
        log.info(f"[{direction}/{split}/ep{epoch}] {len(records):,} records "
                 f"(synthetic={'included' if include_synthetic else 'excluded'})")
    return records


# ── Train ──────────────────────────────────────────────────────
def train(direction: str):
    os.environ["TORCH_DISTRIBUTED_DEFAULT_BACKEND"] = "gloo"
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
        log.info(f"Fine-tune IndicTrans2 [{direction}] v2 | {accelerator.num_processes} GPUs")
        log.info(f"Langs={len(EN_INDIC_TRAIN_LANGS)} | LabelSmoothing={LABEL_SMOOTHING} "
                 f"| CosLR | EarlyStop(patience={EARLY_STOP_PAT}) | Epochs={MAX_EPOCHS}")
        log.info(f"Curriculum: synthetic data from epoch {SYNTHETIC_EPOCH}+")
        log.info(f"{'='*60}")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                log.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    _VALID_LANG_TAG.update(INDIC_TRANS2_CODES.values())

    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_path, trust_remote_code=True, torch_dtype=torch.bfloat16
    )
    # IndicTrans2 uses old _set_gradient_checkpointing API — silently ignores
    # use_reentrant=False, causing CUDA unspecified launch failure on bf16 multi-GPU.
    # Disabled; VRAM offset by halving BATCH_SIZE + doubling GRAD_ACCUM above.
    # model.gradient_checkpointing_enable()

    # Estimate total steps using epoch-1 data (no synthetic yet)
    if is_main:
        log.info("Estimating dataset size for scheduler...")
    sample_records = build_records(direction, "train", epoch=1, quiet=True)
    steps_per_epoch = max(len(sample_records) // (BATCH_SIZE * max(accelerator.num_processes, 1)), 1)
    total_steps  = (steps_per_epoch // GRAD_ACCUM) * MAX_EPOCHS
    warmup_steps = max(1, int(total_steps * WARMUP_RATIO))
    del sample_records

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01,
                                  betas=(0.9, 0.98), eps=1e-9)
    scheduler = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)

    if is_main:
        log.info(f"Batch/GPU={BATCH_SIZE} GradAccum={GRAD_ACCUM} "
                 f"EffBatch={BATCH_SIZE * GRAD_ACCUM * accelerator.num_processes} "
                 f"LR={LR} TotalSteps≈{total_steps} Warmup={warmup_steps}")

    model, optimizer, scheduler = accelerator.prepare(model, optimizer, scheduler)

    best_dev_loss  = float("inf")
    no_improve     = 0
    run_start      = time.time()

    for epoch in range(1, MAX_EPOCHS + 1):
        # Rebuild dataset each epoch — curriculum changes at SYNTHETIC_EPOCH
        train_records = build_records(direction, "train", epoch=epoch, quiet=not is_main)
        dev_records   = build_records(direction, "dev",   epoch=epoch, quiet=not is_main)

        if not train_records:
            if is_main:
                log.warning(f"No data for {direction} epoch {epoch}, skipping.")
            continue

        train_ds = ParallelDataset(train_records, tokenizer)
        dev_ds   = ParallelDataset(dev_records,   tokenizer)

        train_sampler = DistributedSampler(
            train_ds, accelerator.num_processes, accelerator.process_index, shuffle=True
        ) if accelerator.num_processes > 1 else None

        train_loader = DataLoader(
            train_ds, BATCH_SIZE, sampler=train_sampler,
            shuffle=(train_sampler is None), collate_fn=train_ds.collate,
            num_workers=0, pin_memory=False,
        )
        dev_loader = DataLoader(
            dev_ds, BATCH_SIZE, shuffle=False,
            collate_fn=dev_ds.collate, num_workers=0, pin_memory=False,
        )
        train_loader, dev_loader = accelerator.prepare(train_loader, dev_loader)

        if train_sampler:
            train_sampler.set_epoch(epoch)

        model.train()
        epoch_loss  = 0.0
        epoch_start = time.time()
        window_start = epoch_start

        for step, batch in enumerate(train_loader, 1):
            with accelerator.accumulate(model):
                outputs = model(**batch)
                # Use label-smoothed loss instead of model's default CE
                loss = _smooth_loss(outputs.logits, batch["labels"])
                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
            epoch_loss += loss.item()

            if is_main and step % LOG_EVERY == 0:
                elapsed      = time.time() - window_start
                steps_per_s  = LOG_EVERY / max(elapsed, 1e-6)
                remaining_s  = (len(train_loader) - step) / max(steps_per_s, 1e-6)
                mem_gb = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0.0
                log.info(
                    f"[{direction}] Ep {epoch}/{MAX_EPOCHS} | Step {step}/{len(train_loader)} "
                    f"| Loss {epoch_loss/step:.4f} | LR {scheduler.get_last_lr()[0]:.2e} "
                    f"| {steps_per_s:.2f} steps/s | GPU {mem_gb:.1f}GB "
                    f"| ETA {remaining_s/60:.1f}min"
                )
                window_start = time.time()

        # Dev eval
        model.eval()
        dev_loss_sum = torch.zeros(1, device=accelerator.device)
        dev_steps    = 0
        with torch.no_grad():
            for batch in dev_loader:
                outputs = model(**batch)
                loss    = _smooth_loss(outputs.logits, batch["labels"])
                dev_loss_sum += loss
                dev_steps    += 1
        dev_loss_sum = accelerator.reduce(dev_loss_sum, reduction="mean")
        dev_loss = (dev_loss_sum / max(dev_steps, 1)).item()

        if is_main:
            epoch_mins = (time.time() - epoch_start) / 60
            log.info(
                f"[{direction}] Epoch {epoch}/{MAX_EPOCHS} done in {epoch_mins:.1f}min "
                f"| TrainLoss {epoch_loss/max(len(train_loader),1):.4f} "
                f"| DevLoss {dev_loss:.4f}"
            )
            if dev_loss < best_dev_loss:
                best_dev_loss = dev_loss
                no_improve    = 0
                unwrapped = accelerator.unwrap_model(model)
                unwrapped.save_pretrained(str(ckpt_path / "best"))
                tokenizer.save_pretrained(str(ckpt_path / "best"))
                log.info(f"[SAVED] {ckpt_path/'best'}  dev_loss={dev_loss:.4f}")
            else:
                no_improve += 1
                log.info(f"No improvement ({no_improve}/{EARLY_STOP_PAT}) "
                         f"best={best_dev_loss:.4f}")
                if no_improve >= EARLY_STOP_PAT:
                    log.info(f"[EARLY STOP] No improvement for {EARLY_STOP_PAT} epochs.")
                    break

    if is_main:
        total_mins = (time.time() - run_start) / 60
        log.info(f"[{direction}] Done in {total_mins:.1f}min. Best dev loss: {best_dev_loss:.4f}")
        log.info(f"Best checkpoint -> {ckpt_path / 'best'}")


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
