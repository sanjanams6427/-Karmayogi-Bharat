"""
eval_finetuned.py — Compare fine-tuned vs base IndicTrans2 on dev set.
Usage:
    python scripts/eval_finetuned.py --direction en_indic [--langs hin ben tam] [--n 100]
"""
import argparse, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from pipeline.lang_config import INDIC_TRANS2_CODES, ALL_22

DATA_DIR  = Path("datasets/parallel")
MODELS_DIR = Path("models/indic_tr")
CKPT_DIR  = Path("checkpoints/indictrans")


def load_dev(lang: str, direction: str, n: int) -> list[dict]:
    path = DATA_DIR / lang / "dev.jsonl"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if len(rows) >= n:
                break
            r = json.loads(line)
            src = r["src"] if direction == "en_indic" else r.get("tgt", "")
            tgt = r["tgt"] if direction == "en_indic" else r.get("src", "")
            if src.strip() and tgt.strip():
                rows.append({"src": src, "tgt": tgt})
    return rows


def chrf(hyp: str, ref: str, n: int = 6) -> float:
    """Character n-gram F-score (ChrF)."""
    def ngrams(s, n):
        return {s[i:i+n] for i in range(len(s) - n + 1)}
    scores = []
    for k in range(1, n + 1):
        h, r = ngrams(hyp, k), ngrams(ref, k)
        if not r:
            continue
        p = len(h & r) / len(h) if h else 0
        rec = len(h & r) / len(r)
        f = 2 * p * rec / (p + rec) if (p + rec) > 0 else 0
        scores.append(f)
    return sum(scores) / len(scores) if scores else 0.0


def load_model(path: str, device: str):
    import torch
    from transformers import AutoModelForSeq2SeqLM
    import importlib, sys as _sys
    mod_key = f"it2_tok_{Path(path).name}"
    if mod_key not in _sys.modules:
        spec = importlib.util.spec_from_file_location(
            mod_key, str(Path(path) / "tokenization_indictrans.py"))
        mod = importlib.util.module_from_spec(spec)
        _sys.modules[mod_key] = mod
        spec.loader.exec_module(mod)
    else:
        mod = _sys.modules[mod_key]
    tok = mod.IndicTransTokenizer(
        src_vocab_fp=str(Path(path) / "dict.SRC.json"),
        tgt_vocab_fp=str(Path(path) / "dict.TGT.json"),
        src_spm_fp=str(Path(path) / "model.SRC"),
        tgt_spm_fp=str(Path(path) / "model.TGT"),
    )
    dtype = torch.float16 if "cuda" in device else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(
        path, trust_remote_code=True, torch_dtype=dtype, low_cpu_mem_usage=True
    ).to(device).eval()
    from IndicTransToolkit import IndicProcessor
    proc = IndicProcessor(inference=True)
    return tok, model, proc


def translate_batch(texts, src_code, tgt_code, tok, model, proc, device):
    import torch
    batch = proc.preprocess_batch(texts, src_lang=src_code, tgt_lang=tgt_code)
    inputs = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=256)
    dtype = next(model.parameters()).dtype
    inputs = {k: v.to(device) for k, v in inputs.items()}
    inputs = {k: v.to(dtype=dtype) if v.is_floating_point() else v for k, v in inputs.items()}
    tgt_id = tok.convert_tokens_to_ids(tgt_code)
    with torch.no_grad():
        out = model.generate(**inputs, forced_bos_token_id=tgt_id,
                             max_new_tokens=256, num_beams=4, use_cache=True)
    decoded = tok.batch_decode(out, skip_special_tokens=True)
    return proc.postprocess_batch(decoded, lang=tgt_code)


def eval_model(path, direction, langs, n, device, label):
    tok, model, proc = load_model(path, device)
    lang_scores = {}
    for lang in langs:
        rows = load_dev(lang, direction, n)
        if not rows:
            print(f"  [{label}] {lang}: no dev data — skipped")
            continue
        src_code = INDIC_TRANS2_CODES.get("eng" if direction == "en_indic" else lang)
        tgt_code = INDIC_TRANS2_CODES.get(lang if direction == "en_indic" else "eng")
        if not src_code or not tgt_code:
            continue
        hyps = translate_batch([r["src"] for r in rows], src_code, tgt_code, tok, model, proc, device)
        score = sum(chrf(h, r["tgt"]) for h, r in zip(hyps, rows)) / len(rows)
        lang_scores[lang] = round(score * 100, 2)
        print(f"  [{label}] {lang}: ChrF={score*100:.2f}  ({len(rows)} segs)")
    return lang_scores


def main():
    import torch
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction", default="en_indic",
                        choices=["en_indic", "indic_en", "indic_indic"])
    parser.add_argument("--langs", nargs="+", default=["hin", "ben", "tam", "tel", "kan", "mal"])
    parser.add_argument("--n", type=int, default=100, help="Dev samples per language")
    args = parser.parse_args()

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    ft_path   = str(CKPT_DIR / args.direction / "best")
    base_path = str(MODELS_DIR / args.direction)

    has_ft   = Path(ft_path).exists()
    has_base = Path(base_path).exists()

    if not has_ft and not has_base:
        print("Neither fine-tuned nor base model found. Exiting.")
        sys.exit(1)

    print(f"\n=== IndicTrans2 [{args.direction}] eval | device={device} | n={args.n}/lang ===\n")

    ft_scores   = eval_model(ft_path,   args.direction, args.langs, args.n, device, "fine-tuned") if has_ft   else {}
    base_scores = eval_model(base_path, args.direction, args.langs, args.n, device, "base")       if has_base else {}

    print("\n── Summary ──────────────────────────────────────────")
    print(f"{'Lang':<8} {'Base ChrF':>10} {'Fine-tuned':>12} {'Delta':>8}")
    print("-" * 42)
    all_langs = sorted(set(list(ft_scores) + list(base_scores)))
    deltas = []
    for lang in all_langs:
        b = base_scores.get(lang, float("nan"))
        f = ft_scores.get(lang, float("nan"))
        d = f - b if (b == b and f == f) else float("nan")
        deltas.append(d)
        flag = "✅" if d > 0 else ("⚠️" if d < -1 else "—")
        print(f"{lang:<8} {b:>10.2f} {f:>12.2f} {d:>+8.2f}  {flag}")
    valid = [d for d in deltas if d == d]
    if valid:
        avg = sum(valid) / len(valid)
        print("-" * 42)
        print(f"{'Avg':<8} {'':>10} {'':>12} {avg:>+8.2f}  {'✅ improved' if avg > 0 else '❌ regressed'}")
    print()


if __name__ == "__main__":
    main()
