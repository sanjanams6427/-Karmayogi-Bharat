"""
Download + convert parallel data for 4 gap languages: doi, bod, kok, san
Writes datasets/parallel/<lang>/train.jsonl  dev.jsonl  test.jsonl
"""

import json, os, random
from pathlib import Path
from datasets import load_dataset

random.seed(42)

# ── lang config ──────────────────────────────────────────────────────────────
# flores: use bilingual pair config eng_Latn-<script> (always available)
# opus:   only configs that actually exist in opus-100
LANGS = {
    "doi": {
        "flores": "eng_Latn-doi_Deva",
        "opus":   None,               # not in opus-100
        "in22":   "doi",
    },
    "bod": {
        "flores": "eng_Latn-bod_Tibt",
        "opus":   None,               # not in opus-100
        "in22":   "bod",
    },
    "kok": {
        "flores": "eng_Latn-kok_Deva",
        "opus":   None,               # not in opus-100
        "in22":   "kok",
    },
    "san": {
        "flores": "eng_Latn-san_Deva",
        "opus":   None,               # en-sa not in opus-100
        "in22":   "san",
    },
}

# IN22-Gen column names per lang (flores_code → column in dataset)
IN22_COL = {
    "doi": "doi_Deva",
    "bod": "brx_Deva",   # Bodo in IN22 is brx_Deva
    "kok": "gom_Deva",   # Konkani in IN22 is gom_Deva (Goan Konkani)
    "san": "san_Deva",
}

HF_TOKEN = os.environ.get("HF_TOKEN")


def _row(src, tgt, lang):
    return {"src": src, "tgt": tgt, "src_lang": "eng", "tgt_lang": lang}


def _write(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  wrote {len(records):>5} lines -> {path}")


def fetch_flores(flores_cfg: str, lang: str) -> list:
    """FLORES-200 bilingual pair config eng_Latn-<script> → parallel records."""
    records = []
    try:
        ds = load_dataset("facebook/flores", flores_cfg, token=HF_TOKEN)
        for split in ("dev", "devtest"):
            if split not in ds:
                continue
            for row in ds[split]:
                src = row.get("sentence_eng_Latn", "")
                # target key is sentence_<script>
                tgt_key = [k for k in row.keys() if k.startswith("sentence_") and k != "sentence_eng_Latn"]
                tgt = row.get(tgt_key[0], "") if tgt_key else ""
                if src and tgt:
                    records.append(_row(src, tgt, lang))
        print(f"  [flores] {lang}: {len(records)} pairs")
    except Exception as ex:
        print(f"  [flores] {lang} FAILED: {ex}")
    return records


def fetch_in22(in22_col: str, lang: str) -> list:
    """IN22-Gen: ~1000 high-quality sentences per language."""
    records = []
    try:
        ds = load_dataset("ai4bharat/IN22-Gen", token=HF_TOKEN)
        split = list(ds.keys())[0]
        for row in ds[split]:
            src = row.get("eng_Latn", "")
            tgt = row.get(in22_col, "")
            if src and tgt:
                records.append(_row(src, tgt, lang))
        print(f"  [in22]   {lang}: {len(records)} pairs")
    except Exception as ex:
        print(f"  [in22]   {lang} FAILED: {ex}")
    return records


def fetch_opus(opus_cfg: str, lang: str, max_rows: int = 20_000) -> list:
    """OPUS-100 en-XX pairs, capped at max_rows. Returns [] if cfg is None."""
    if not opus_cfg:
        return []
    records = []
    try:
        ds = load_dataset("Helsinki-NLP/opus-100", opus_cfg, token=HF_TOKEN)
        split = "train" if "train" in ds else list(ds.keys())[0]
        for row in ds[split]:
            t = row.get("translation", {})
            src = t.get("en", "")
            tgt_key = opus_cfg.split("-")[1]
            tgt = t.get(tgt_key, "")
            if src and tgt:
                records.append(_row(src, tgt, lang))
            if len(records) >= max_rows:
                break
        print(f"  [opus]   {lang}: {len(records)} pairs")
    except Exception as ex:
        print(f"  [opus]   {lang} FAILED: {ex}")
    return records


def build_splits(all_records: list) -> tuple:
    """Shuffle then split 80/10/10 → train/dev/test."""
    random.shuffle(all_records)
    n = len(all_records)
    dev_n  = max(50, n // 10)
    test_n = max(50, n // 10)
    test   = all_records[:test_n]
    dev    = all_records[test_n:test_n + dev_n]
    train  = all_records[test_n + dev_n:]
    return train, dev, test


def process_lang(lang: str, cfg: dict):
    print(f"\n{'='*50}\n{lang.upper()}\n{'='*50}")
    out = Path(f"datasets/parallel/{lang}")

    records = []
    records += fetch_flores(cfg["flores"], lang)
    records += fetch_in22(IN22_COL[lang], lang)
    records += fetch_opus(cfg["opus"], lang)

    if not records:
        print(f"  !! No data collected for {lang}, skipping.")
        return

    # Deduplicate on (src, tgt)
    seen = set()
    unique = []
    for r in records:
        key = (r["src"], r["tgt"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    print(f"  total unique: {len(unique)}")

    train, dev, test = build_splits(unique)
    _write(out / "train.jsonl", train)
    _write(out / "dev.jsonl",   dev)
    _write(out / "test.jsonl",  test)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    for lang, cfg in LANGS.items():
        process_lang(lang, cfg)
    print("\nDone. Run scripts/check_gaps.py to verify.")
