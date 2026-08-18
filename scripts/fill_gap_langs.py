"""
fill_gap_langs.py — Fetch parallel data for the 8 gap languages and write
to datasets/parallel/<lang>/{train,dev,test}.jsonl

Sources (all public, no token needed):
  1. ai4bharat/IN22-Gen   — ~1000 high-quality sentences × 22 langs (primary)
  2. ai4bharat/IN22-Conv  — ~1000 conversational sentences × 22 langs
  3. facebook/flores      — ~1000 eval sentences × 22 langs (dev/test)
  4. Helsinki-NLP/opus-100 — larger train sets where available

Gap langs: bod, doi, kas, kok, mni, mai, san, sat

Usage:
    python scripts/fill_gap_langs.py [--langs bod doi kas kok mni mai san sat] [--force]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

PARALLEL_DIR = Path("datasets/parallel")

# flores200 config name → our lang code
FLORES_CONFIGS = {
    "bod": "brx_Deva",   # Bodo — IndicTrans2 uses brx_Deva
    "doi": "doi_Deva",
    "kas": "kas_Arab",
    "kok": "kok_Deva",
    "mni": "mni_Mtei",
    "mai": "mai_Deva",
    "san": "san_Deva",
    "sat": "sat_Olck",
}

# IN22 column names per lang (flores200 code used as column key in IN22)
IN22_COLS = {
    "bod": "brx_Deva",
    "doi": "doi_Deva",
    "kas": "kas_Arab",
    "kok": "kok_Deva",
    "mni": "mni_Mtei",
    "mai": "mai_Deva",
    "san": "san_Deva",
    "sat": "sat_Olck",
}

# OPUS-100 configs for gap langs (some don't exist — handled gracefully)
OPUS_CONFIGS = {
    "san": "en-sa",
    "mai": "en-mai",
    "kok": "en-kok",
    "mni": "en-mni",
    "kas": "en-ks",
    "sat": "en-sat",
    # bod and doi have no OPUS-100 config
}

GAP_LANGS = ["bod", "doi", "kas", "kok", "mni", "mai", "san", "sat"]


def write_jsonl(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  wrote {len(records):,} → {path}")


def fetch_in22(lang: str, col: str) -> list[dict]:
    """Fetch from IN22-Gen + IN22-Conv. Returns list of {src, tgt} dicts."""
    from datasets import load_dataset
    records = []
    for repo in ("ai4bharat/IN22-Gen", "ai4bharat/IN22-Conv"):
        try:
            ds = load_dataset(repo, split="gen" if "Gen" in repo else "conv",
                              trust_remote_code=True)
            eng_col = "eng_Latn"
            if eng_col not in ds.column_names or col not in ds.column_names:
                # Try loading without split name
                ds = load_dataset(repo, trust_remote_code=True)
                split_name = list(ds.keys())[0]
                ds = ds[split_name]
            for row in ds:
                src = row.get(eng_col, "").strip()
                tgt = row.get(col, "").strip()
                if src and tgt:
                    records.append({"src": src, "tgt": tgt,
                                    "src_lang": "eng", "tgt_lang": lang})
            print(f"  IN22 ({repo.split('/')[-1]}): {len(records)} pairs so far")
        except Exception as e:
            print(f"  IN22 ({repo}) failed: {e}")
    return records


def fetch_flores(lang: str, flores_config: str) -> list[dict]:
    """Fetch FLORES-200 dev+devtest as eval pairs."""
    from datasets import load_dataset
    records = []
    try:
        ds = load_dataset("facebook/flores", flores_config, trust_remote_code=True)
        for split_name in ("dev", "devtest"):
            if split_name not in ds:
                continue
            # FLORES has 'sentence' column; English is loaded separately
            eng_ds = load_dataset("facebook/flores", "eng_Latn",
                                  trust_remote_code=True)[split_name]
            tgt_ds = ds[split_name]
            for eng_row, tgt_row in zip(eng_ds, tgt_ds):
                src = eng_row.get("sentence", "").strip()
                tgt = tgt_row.get("sentence", "").strip()
                if src and tgt:
                    records.append({"src": src, "tgt": tgt,
                                    "src_lang": "eng", "tgt_lang": lang})
        print(f"  FLORES ({flores_config}): {len(records)} pairs")
    except Exception as e:
        print(f"  FLORES ({flores_config}) failed: {e}")
    return records


def fetch_opus(lang: str, config: str) -> list[dict]:
    """Fetch OPUS-100 train split."""
    from datasets import load_dataset
    records = []
    try:
        ds = load_dataset("Helsinki-NLP/opus-100", config,
                          split="train", trust_remote_code=True)
        for row in ds:
            tr = row.get("translation", {})
            # opus-100 keys are ISO codes e.g. "en", "sa"
            keys = list(tr.keys())
            en_key  = next((k for k in keys if k == "en"), None)
            tgt_key = next((k for k in keys if k != "en"), None)
            if not en_key or not tgt_key:
                continue
            src = tr[en_key].strip()
            tgt = tr[tgt_key].strip()
            if src and tgt:
                records.append({"src": src, "tgt": tgt,
                                "src_lang": "eng", "tgt_lang": lang})
        print(f"  OPUS-100 ({config}): {len(records):,} pairs")
    except Exception as e:
        print(f"  OPUS-100 ({config}) failed: {e}")
    return records


def fill_lang(lang: str, force: bool):
    train_path = PARALLEL_DIR / lang / "train.jsonl"
    dev_path   = PARALLEL_DIR / lang / "dev.jsonl"
    test_path  = PARALLEL_DIR / lang / "test.jsonl"

    existing_train = sum(1 for _ in open(train_path, encoding="utf-8")) if train_path.exists() else 0
    if existing_train > 0 and not force:
        print(f"[{lang}] already has {existing_train:,} train rows — skipping (use --force to overwrite)")
        return

    print(f"\n[{lang}] fetching data...")
    flores_cfg = FLORES_CONFIGS.get(lang)
    in22_col   = IN22_COLS.get(lang)
    opus_cfg   = OPUS_CONFIGS.get(lang)

    all_records = []

    # 1. IN22 (highest quality — government/official text)
    if in22_col:
        all_records += fetch_in22(lang, in22_col)

    # 2. OPUS-100 (larger volume for train)
    if opus_cfg:
        all_records += fetch_opus(lang, opus_cfg)

    # 3. FLORES (high quality eval sentences — use for dev/test)
    flores_records = fetch_flores(lang, flores_cfg) if flores_cfg else []

    # Deduplicate by src text
    seen = set()
    unique = []
    for r in all_records:
        if r["src"] not in seen:
            seen.add(r["src"])
            unique.append(r)

    flores_unique = []
    for r in flores_records:
        if r["src"] not in seen:
            seen.add(r["src"])
            flores_unique.append(r)

    print(f"  Total unique: {len(unique):,} train  +  {len(flores_unique):,} flores eval")

    if not unique and not flores_unique:
        print(f"  [WARN] No data found for {lang} — leaving empty")
        return

    # Split: use FLORES for dev+test, rest for train
    # If no FLORES, carve 10% from unique for dev, 5% for test
    if flores_unique:
        mid = len(flores_unique) // 2
        dev_records  = flores_unique[:mid]
        test_records = flores_unique[mid:]
        train_records = unique
    else:
        import random
        random.shuffle(unique)
        n = len(unique)
        dev_n  = max(50, n // 10)
        test_n = max(50, n // 20)
        dev_records   = unique[:dev_n]
        test_records  = unique[dev_n:dev_n + test_n]
        train_records = unique[dev_n + test_n:]

    write_jsonl(train_path, train_records)
    write_jsonl(dev_path,   dev_records)
    write_jsonl(test_path,  test_records)
    print(f"[{lang}] done — train={len(train_records):,}  dev={len(dev_records):,}  test={len(test_records):,}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="+", default=GAP_LANGS)
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing non-empty files")
    args = parser.parse_args()

    print(f"Filling gap languages: {args.langs}")
    for lang in args.langs:
        if lang not in GAP_LANGS:
            print(f"[{lang}] not a gap language — skipping")
            continue
        fill_lang(lang, args.force)

    print("\nDone. Run: python scripts/check_gaps.py")


if __name__ == "__main__":
    main()
