"""
Back-translation augmentation for doi and kok.

Strategy:
  doi: OPUS en-hi (534K pairs) -> translate hi->doi via IndicTrans2 base
       -> synthetic (eng_src, doi_tgt) pairs appended to datasets/parallel/doi/
  kok: OPUS en-mr (27K pairs)  -> translate mr->kok via IndicTrans2 base
       -> synthetic (eng_src, kok_tgt) pairs appended to datasets/parallel/kok/

Synthetic pairs are marked with "synthetic": true in jsonl so fine-tuning
can weight them lower than gold IN22/FLORES data.
"""

import json, os, sys, random
from pathlib import Path

random.seed(42)

MODELS_DIR = Path(__file__).parent.parent / "models"
DEVICE = "cuda" if __import__("torch").cuda.is_available() else "cpu"

# How many synthetic pairs to generate per lang (cap to avoid noise domination)
MAX_SYNTHETIC = {"doi": 15_000, "kok": 10_000}


def _load_indictrans2(direction: str):
    import torch
    from transformers import AutoModelForSeq2SeqLM
    import importlib, sys as _sys
    path = str(MODELS_DIR / "indic_tr" / direction)
    mod_key = f"transformers_modules.indictrans_{direction}.tokenization_indictrans"
    if mod_key not in _sys.modules:
        spec = importlib.util.spec_from_file_location(
            mod_key, str(Path(path) / "tokenization_indictrans.py"))
        mod = importlib.util.module_from_spec(spec)
        _sys.modules[mod_key] = mod
        spec.loader.exec_module(mod)
    else:
        mod = _sys.modules[mod_key]
    tokenizer = mod.IndicTransTokenizer(
        src_vocab_fp=str(Path(path) / "dict.SRC.json"),
        tgt_vocab_fp=str(Path(path) / "dict.TGT.json"),
        src_spm_fp=str(Path(path) / "model.SRC"),
        tgt_spm_fp=str(Path(path) / "model.TGT"),
    )
    dtype = __import__("torch").float16 if __import__("torch").cuda.is_available() \
        else __import__("torch").float32
    model = AutoModelForSeq2SeqLM.from_pretrained(
        path, trust_remote_code=True, low_cpu_mem_usage=True, torch_dtype=dtype
    ).to(DEVICE)
    model.eval()
    from IndicTransToolkit import IndicProcessor
    processor = IndicProcessor(inference=True)
    return {"tokenizer": tokenizer, "model": model, "processor": processor}


def _translate_batch(engine, texts, src_code, tgt_code, batch_size=32):
    import torch
    tokenizer = engine["tokenizer"]
    model     = engine["model"]
    processor = engine["processor"]
    results   = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        batch = processor.preprocess_batch(chunk, src_lang=src_code, tgt_lang=tgt_code)
        inputs = tokenizer(batch, return_tensors="pt", padding=True,
                           truncation=True, max_length=256)
        dtype = next(model.parameters()).dtype
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        inputs = {k: v.to(dtype=dtype) if v.is_floating_point() else v
                  for k, v in inputs.items()}
        tgt_id = tokenizer.convert_tokens_to_ids(tgt_code)
        with torch.no_grad():
            out = model.generate(
                **inputs, forced_bos_token_id=tgt_id,
                max_new_tokens=256, num_beams=4,
                no_repeat_ngram_size=3, repetition_penalty=1.1,
                use_cache=True, early_stopping=True,
            )
        decoded = tokenizer.batch_decode(out, skip_special_tokens=True)
        results.extend(processor.postprocess_batch(decoded, lang=tgt_code))
        if (i // batch_size) % 10 == 0:
            print(f"  translated {min(i+batch_size, len(texts))}/{len(texts)}")
    return results


def _append_jsonl(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  appended {len(records)} synthetic lines -> {path}")


def augment_doi():
    """OPUS en-hi -> translate hi->doi -> append to doi splits."""
    print("\n" + "="*50)
    print("DOI augmentation (OPUS en-hi -> hi->doi)")
    print("="*50)

    from datasets import load_dataset
    ds = load_dataset("Helsinki-NLP/opus-100", "en-hi")
    rows = list(ds["train"])
    random.shuffle(rows)
    rows = rows[:MAX_SYNTHETIC["doi"]]

    eng_texts = [r["translation"]["en"] for r in rows]
    hin_texts = [r["translation"]["hi"] for r in rows]

    print(f"  loaded {len(rows)} en-hi pairs, translating hi->doi...")
    engine = _load_indictrans2("indic_indic")
    doi_texts = _translate_batch(engine, hin_texts, "hin_Deva", "doi_Deva")

    records = [
        {"src": e, "tgt": d, "src_lang": "eng", "tgt_lang": "doi", "synthetic": True}
        for e, d in zip(eng_texts, doi_texts)
        if e.strip() and d.strip()
    ]
    print(f"  generated {len(records)} synthetic doi pairs")

    # 80/10/10 split
    n = len(records)
    dev_n = max(50, n // 10)
    test_n = max(50, n // 10)
    _append_jsonl(Path("datasets/parallel/doi/train.jsonl"), records[test_n + dev_n:])
    _append_jsonl(Path("datasets/parallel/doi/dev.jsonl"),   records[test_n:test_n + dev_n])
    _append_jsonl(Path("datasets/parallel/doi/test.jsonl"),  records[:test_n])


def augment_kok():
    """OPUS en-mr -> translate mr->kok -> append to kok splits."""
    print("\n" + "="*50)
    print("KOK augmentation (OPUS en-mr -> mr->kok)")
    print("="*50)

    from datasets import load_dataset
    ds = load_dataset("Helsinki-NLP/opus-100", "en-mr")
    rows = list(ds["train"])
    random.shuffle(rows)
    rows = rows[:MAX_SYNTHETIC["kok"]]

    eng_texts = [r["translation"]["en"] for r in rows]
    mar_texts = [r["translation"]["mr"] for r in rows]

    print(f"  loaded {len(rows)} en-mr pairs, translating mr->kok...")
    engine = _load_indictrans2("indic_indic")
    kok_texts = _translate_batch(engine, mar_texts, "mar_Deva", "gom_Deva")

    records = [
        {"src": e, "tgt": k, "src_lang": "eng", "tgt_lang": "kok", "synthetic": True}
        for e, k in zip(eng_texts, kok_texts)
        if e.strip() and k.strip()
    ]
    print(f"  generated {len(records)} synthetic kok pairs")

    n = len(records)
    dev_n = max(50, n // 10)
    test_n = max(50, n // 10)
    _append_jsonl(Path("datasets/parallel/kok/train.jsonl"), records[test_n + dev_n:])
    _append_jsonl(Path("datasets/parallel/kok/dev.jsonl"),   records[test_n:test_n + dev_n])
    _append_jsonl(Path("datasets/parallel/kok/test.jsonl"),  records[:test_n])


def augment_san():
    """IITB en-hi (1.6M) -> translate hi->san via IndicTrans2 base -> append to san splits."""
    print("\n" + "="*50)
    print("SAN augmentation (IITB en-hi -> hi->san)")
    print("="*50)

    from datasets import load_dataset
    ds = load_dataset("cfilt/iitb-english-hindi")
    rows = list(ds["train"])
    random.shuffle(rows)
    rows = rows[:15_000]

    eng_texts = [r["translation"]["en"] for r in rows]
    hin_texts = [r["translation"]["hi"] for r in rows]

    print(f"  loaded {len(rows)} en-hi pairs, translating hi->san...")
    engine = _load_indictrans2("indic_indic")
    san_texts = _translate_batch(engine, hin_texts, "hin_Deva", "san_Deva")

    records = [
        {"src": e, "tgt": s, "src_lang": "eng", "tgt_lang": "san", "synthetic": True}
        for e, s in zip(eng_texts, san_texts)
        if e.strip() and s.strip()
    ]
    print(f"  generated {len(records)} synthetic san pairs")

    n = len(records)
    dev_n = max(50, n // 10)
    test_n = max(50, n // 10)
    _append_jsonl(Path("datasets/parallel/san/train.jsonl"), records[test_n + dev_n:])
    _append_jsonl(Path("datasets/parallel/san/dev.jsonl"),   records[test_n:test_n + dev_n])
    _append_jsonl(Path("datasets/parallel/san/test.jsonl"),  records[:test_n])



    # Check indic_indic model exists before starting
    indic_indic_path = MODELS_DIR / "indic_tr" / "indic_indic"
    if not indic_indic_path.exists():
        print(f"ERROR: indic_indic model not found at {indic_indic_path}")
        print("Run: python scripts/download_models.py first")
        sys.exit(1)

    lang = sys.argv[1] if len(sys.argv) > 1 else "all"
    if lang in ("doi", "all"):
        augment_doi()
    if lang in ("kok", "all"):
        augment_kok()
    if lang in ("san", "all"):
        augment_san()

    print("\nDone. Run scripts/check_gaps.py to verify updated counts.")
    print("Note: synthetic pairs are marked 'synthetic: true' in jsonl.")
    print("In finetune_indictrans.py, weight synthetic pairs at 0.5x gold pairs.")
