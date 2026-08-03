# ============================================================
# prepare_dataset.py
# Downloads parallel text data for all 22 Indian languages.
#
# Sources (in priority order):
#   1. Samanantar v2     — 11 mainstream langs (200k each)
#   2. facebook/flores   — dev/test for all 22 (verified configs)
#   3. Helsinki-NLP/opus-100 — urd, nep (already done)
#   4. ai4bharat/IN22-Gen   — doi + supplement all gap langs
#
# Output: datasets/parallel/<lang>/{train,dev,test}.jsonl
# Each line: {"src":"...","tgt":"...","src_lang":"eng","tgt_lang":"<lang>"}
# ============================================================

import json
from pathlib import Path
from datasets import load_dataset

HF_TOKEN = open(".env").read().strip().split("=", 1)[1].strip().strip('"')

OUT_DIR = Path("datasets/parallel")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ALL_22 = [
    "asm", "ben", "guj", "hin", "kan", "mal", "mar", "ory", "pan", "tam", "tel",
    "bod", "doi", "kas", "kok", "mni", "mai", "nep", "san", "sat", "snd", "urd",
]

# Samanantar v2 — verified available configs
SAMANANTAR_CONFIGS = {
    "asm": "as", "ben": "bn", "guj": "gu", "hin": "hi", "kan": "kn",
    "mal": "ml", "mar": "mr", "ory": "or", "pan": "pa", "tam": "ta", "tel": "te",
}

# facebook/flores verified config names (from get_dataset_config_names)
# doi is NOT in flores — handled by IN22-Gen
# kok uses kon_Latn (Latin script) — only available form in flores
# nep uses npi_Deva (not nep_Deva)
FLORES_CODES = {
    "asm": "asm_Beng", "ben": "ben_Beng", "guj": "guj_Gujr", "hin": "hin_Deva",
    "kan": "kan_Knda", "mal": "mal_Mlym", "mar": "mar_Deva", "ory": "ory_Orya",
    "pan": "pan_Guru", "tam": "tam_Taml", "tel": "tel_Telu", "urd": "urd_Arab",
    "nep": "npi_Deva", "mai": "mai_Deva", "snd": "snd_Arab", "kas": "kas_Arab",
    "kok": "kon_Latn", "mni": "mni_Beng", "san": "san_Deva", "bod": "bod_Tibt",
    "sat": "sat_Olck",
    # doi: absent from flores, skip here
    "eng": "eng_Latn",
}

# IN22-Gen column names (flores-style codes used as column headers)
IN22_CODES = {
    "asm": "asm_Beng", "ben": "ben_Beng", "guj": "guj_Gujr", "hin": "hin_Deva",
    "kan": "kan_Knda", "mal": "mal_Mlym", "mar": "mar_Deva", "ory": "ory_Orya",
    "pan": "pan_Guru", "tam": "tam_Taml", "tel": "tel_Telu", "urd": "urd_Arab",
    "nep": "npi_Deva", "mai": "mai_Deva", "snd": "snd_Deva", "kas": "kas_Arab",
    "kok": "gom_Deva",  # Konkani in IN22 = Goan Konkani (gom_Deva)
    "mni": "mni_Mtei",  # Manipuri in IN22 uses Meitei script
    "san": "san_Deva", "bod": None,       # bod not in IN22-Gen
    "sat": "sat_Olck", "doi": "doi_Deva",
}

# opus-100 verified available configs
OPUS_CONFIGS = {
    "urd": "en-ur",
    "nep": "en-ne",
}


def write_jsonl(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Saved {len(records):,} -> {path}")


# ── 1. Samanantar ─────────────────────────────────────────────
def load_samanantar():
    print("\n[Samanantar] Loading 11 mainstream languages...")
    for lang, config in SAMANANTAR_CONFIGS.items():
        train_path = OUT_DIR / lang / "train.jsonl"
        if train_path.exists():
            print(f"  {lang}: exists, skipping")
            continue
        print(f"  {lang} ({config})...")
        try:
            ds = load_dataset("ai4bharat/samanantar", config, token=HF_TOKEN)
            split = ds.get("train", ds[list(ds.keys())[0]])
            records = []
            for row in split:
                src = (row.get("src") or row.get("en") or "").strip()
                tgt = (row.get("tgt") or row.get(config) or "").strip()
                if src and tgt:
                    records.append({"src": src, "tgt": tgt,
                                    "src_lang": "eng", "tgt_lang": lang})
                if len(records) >= 200_000:
                    break
            if not records:
                print(f"  {lang}: no records")
                continue
            dev_path = OUT_DIR / lang / "dev.jsonl"
            if not dev_path.exists() and len(records) > 2000:
                write_jsonl(dev_path, records[-2000:])
                records = records[:-2000]
            write_jsonl(train_path, records)
        except Exception as e:
            print(f"  {lang}: FAIL — {e}")
    print("[Samanantar] Done.")


# ── 2. FLORES (facebook/flores) ───────────────────────────────
def load_flores():
    print("\n[FLORES] Loading dev/test splits via facebook/flores...")

    # Load English once for both splits
    eng_rows = {}
    for split in ["dev", "devtest"]:
        try:
            ds = load_dataset("facebook/flores", FLORES_CODES["eng"],
                              split=split, token=HF_TOKEN)
            eng_rows[split] = list(ds)
        except Exception as e:
            print(f"  eng/{split}: FAIL — {e}")
            eng_rows[split] = []

    if not any(eng_rows.values()):
        print("  Could not load English, skipping FLORES.")
        return

    for lang in ALL_22:
        tgt_code = FLORES_CODES.get(lang)
        if not tgt_code:
            print(f"  {lang}: no flores config (doi), skipping")
            continue

        out_dir = OUT_DIR / lang
        dev_records, test_records = [], []

        for split_name, out_list, eng_list in [
            ("dev",     dev_records,  eng_rows.get("dev",     [])),
            ("devtest", test_records, eng_rows.get("devtest", [])),
        ]:
            # Skip if file already has data
            out_file = out_dir / ("dev.jsonl" if split_name == "dev" else "test.jsonl")
            if out_file.exists() and out_file.stat().st_size > 0:
                continue
            try:
                tgt_rows = list(load_dataset("facebook/flores", tgt_code,
                                             split=split_name, token=HF_TOKEN))
                for e, t in zip(eng_list, tgt_rows):
                    src = (e.get("sentence") or "").strip()
                    tgt = (t.get("sentence") or "").strip()
                    if src and tgt:
                        out_list.append({"src": src, "tgt": tgt,
                                         "src_lang": "eng", "tgt_lang": lang})
            except Exception as ex:
                print(f"  {lang}/{split_name}: {ex}")

        if test_records:
            write_jsonl(out_dir / "test.jsonl", test_records)
        if dev_records:
            write_jsonl(out_dir / "dev.jsonl", dev_records)
        if dev_records or test_records:
            print(f"  {lang}: dev={len(dev_records)}, test={len(test_records)}")

    print("[FLORES] Done.")


# ── 3. OPUS-100 (urd, nep train) ──────────────────────────────
def load_opus():
    print("\n[OPUS-100] Loading urd, nep...")
    for lang, config in OPUS_CONFIGS.items():
        train_path = OUT_DIR / lang / "train.jsonl"
        if train_path.exists():
            print(f"  {lang}: exists, skipping")
            continue
        tgt_key = config.split("-")[1]
        try:
            ds = load_dataset("Helsinki-NLP/opus-100", config,
                              split="train", token=HF_TOKEN)
            records = []
            for row in ds:
                pair = row.get("translation", {})
                src = pair.get("en", "").strip()
                tgt = pair.get(tgt_key, "").strip()
                if src and tgt:
                    records.append({"src": src, "tgt": tgt,
                                    "src_lang": "eng", "tgt_lang": lang})
                if len(records) >= 200_000:
                    break
            if not records:
                print(f"  {lang}: no records")
                continue
            dev_path = OUT_DIR / lang / "dev.jsonl"
            if not dev_path.exists() and len(records) > 2000:
                write_jsonl(dev_path, records[-2000:])
                records = records[:-2000]
            write_jsonl(train_path, records)
            print(f"  {lang}: {len(records):,} train")
        except Exception as e:
            print(f"  {lang}: FAIL — {e}")
    print("[OPUS-100] Done.")


# ── 4. IN22-Gen (all gap langs + doi) ────────────────────────
def load_in22():
    """
    ai4bharat/IN22-Gen: 1024 rows, all 22 Indian languages as columns.
    Primary source for: doi, kok, mni, sat, snd, bod(absent)
    Supplements dev/test for all others.
    English column: eng_Latn
    """
    print("\n[IN22-Gen] Loading gap languages...")
    try:
        ds = load_dataset("ai4bharat/IN22-Gen", split="test", token=HF_TOKEN)
    except Exception as e:
        print(f"  IN22-Gen load failed: {e}")
        return

    for lang, col in IN22_CODES.items():
        if not col:
            print(f"  {lang}: not in IN22-Gen, skipping")
            continue
        if col not in ds.column_names:
            print(f"  {lang}: column '{col}' not found in IN22-Gen")
            continue

        records = []
        for row in ds:
            src = (row.get("eng_Latn") or "").strip()
            tgt = (row.get(col) or "").strip()
            if src and tgt:
                records.append({"src": src, "tgt": tgt,
                                "src_lang": "eng", "tgt_lang": lang})

        if not records:
            print(f"  {lang}: no records extracted")
            continue

        train_path = OUT_DIR / lang / "train.jsonl"
        dev_path   = OUT_DIR / lang / "dev.jsonl"
        test_path  = OUT_DIR / lang / "test.jsonl"

        if not train_path.exists():
            # Use as train+dev for gap langs with no other source
            split_at = max(1, len(records) - 200)
            if not dev_path.exists():
                write_jsonl(dev_path, records[split_at:])
            write_jsonl(train_path, records[:split_at])
            print(f"  {lang} ({col}): {split_at} train, {len(records)-split_at} dev")
        elif not test_path.exists():
            # Already have train — add as test set
            write_jsonl(test_path, records)
            print(f"  {lang} ({col}): {len(records)} test records added")
        else:
            print(f"  {lang}: all splits exist, skipping")

    print("[IN22-Gen] Done.")


# ── 5. Bodo fix — promote dev→train, rebuild dev from test ──
def fix_bodo():
    """
    Bodo (bod) is absent from IN22-Gen and Samanantar.
    FLORES-200 provides dev (997) and devtest (1012).
    Strategy:
      train = current dev.jsonl  (997 sentences)
      dev   = first 200 of test.jsonl
      test  = remaining 812 of test.jsonl
    """
    print("\n[Bodo fix] Promoting dev→train, splitting test→dev+test...")
    lang_dir  = OUT_DIR / "bod"
    dev_path  = lang_dir / "dev.jsonl"
    test_path = lang_dir / "test.jsonl"
    train_path = lang_dir / "train.jsonl"

    if train_path.exists():
        print("  bod: train.jsonl already exists, skipping")
        return

    if not dev_path.exists():
        print("  bod: dev.jsonl missing — run load_flores() first")
        return

    dev_lines  = dev_path.read_text(encoding="utf-8").splitlines()
    test_lines = test_path.read_text(encoding="utf-8").splitlines() if test_path.exists() else []

    # train = all of current dev
    train_path.write_text("\n".join(dev_lines) + "\n", encoding="utf-8")
    print(f"  bod: train.jsonl written — {len(dev_lines):,} sentences")

    # new dev = first 200 lines of test, new test = rest
    if test_lines:
        new_dev  = test_lines[:200]
        new_test = test_lines[200:]
        dev_path.write_text("\n".join(new_dev) + "\n", encoding="utf-8")
        test_path.write_text("\n".join(new_test) + "\n", encoding="utf-8")
        print(f"  bod: dev.jsonl  = {len(new_dev):,} sentences")
        print(f"  bod: test.jsonl = {len(new_test):,} sentences")

    print("[Bodo fix] Done.")


# ── Summary ───────────────────────────────────────────────────
def print_summary():
    print("\n" + "=" * 55)
    print("DATASET SUMMARY")
    print("=" * 55)
    print(f"{'Lang':<6} {'Train':>10} {'Dev':>8} {'Test':>8}")
    print("-" * 55)
    for lang in ALL_22:
        d = OUT_DIR / lang
        def count(p): return sum(1 for _ in open(p, encoding="utf-8")) if p.exists() else 0
        print(f"{lang:<6} {count(d/'train.jsonl'):>10,} {count(d/'dev.jsonl'):>8,} {count(d/'test.jsonl'):>8,}")
    print("=" * 55)


if __name__ == "__main__":
    load_samanantar()   # 11 mainstream langs — 200k each
    load_flores()       # dev/test for 21 langs (no doi)
    load_opus()         # urd, nep train (already done, skips)
    load_in22()         # doi + all remaining gap langs
    fix_bodo()          # promote bod dev→train, split test→dev+test
    print_summary()
