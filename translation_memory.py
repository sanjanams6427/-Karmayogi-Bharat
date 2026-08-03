# ============================================================
# translation_memory.py
# Central layer of the Unified Localization Pipeline
#
# Architecture position:
#   SeamlessM4T + IndicTrans2
#          ↓
#   Government Translation Memory   ← THIS FILE
#          ↓
#   Domain-specific Fine-tuning
#          ↓
#   Human Feedback / Corrections
#          ↓
#   Unified Localization Pipeline
#
# Responsibilities:
#   1. Store verified government/domain translations (TM)
#   2. Accept human feedback corrections
#   3. Serve TM matches to live pipeline (exact + fuzzy)
#   4. Export TM records for fine-tuning injection
#   5. Track correction history for audit trail
#
# TM files:
#   translation_memory/govt_tm.jsonl          ← domain TM
#   translation_memory/human_feedback.jsonl   ← corrections
#   translation_memory/correction_log.jsonl   ← audit trail
# ============================================================

import json
import re
import hashlib
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

from pipeline.lang_config import ALL_22, LANG_NAMES

TM_DIR = Path("translation_memory")
TM_DIR.mkdir(exist_ok=True)

GOVT_TM_PATH    = TM_DIR / "govt_tm.jsonl"
HF_PATH         = TM_DIR / "human_feedback.jsonl"
CORR_LOG_PATH   = TM_DIR / "correction_log.jsonl"

# Fuzzy match threshold
FUZZY_THRESHOLD = 0.85
_write_lock = threading.Lock()  # serialise all JSONL appends


# ── Record schema ─────────────────────────────────────────────
# {
#   "id":        "<sha256 of src+tgt_lang>",
#   "src":       "source text",
#   "tgt":       "translated text",
#   "src_lang":  "eng",
#   "tgt_lang":  "hin",
#   "domain":    "government|legal|health|education|general",
#   "verified":  true/false,
#   "source":    "govt_doc|human_correction|auto",
#   "added_at":  "2024-01-01T00:00:00"
# }


class TranslationMemory:
    """
    Government Translation Memory with O(1) exact lookup index,
    fuzzy matching, and human feedback integration.
    """

    def __init__(self):
        self._tm: dict[str, list] = {lang: [] for lang in ALL_22 + ["eng"]}
        self._hf: dict[str, list] = {lang: [] for lang in ALL_22 + ["eng"]}
        # O(1) exact-match indexes: lang -> {normalised_src: record}
        self._tm_idx: dict[str, dict] = defaultdict(dict)
        self._hf_idx: dict[str, dict] = defaultdict(dict)
        self._load()

    # ── Load ──────────────────────────────────────────────────
    def _load(self):
        for record in _read_jsonl(GOVT_TM_PATH):
            lang = record.get("tgt_lang")
            if lang in self._tm:
                self._tm[lang].append(record)
                self._tm_idx[lang][record.get("src", "").strip().lower()] = record

        for record in _read_jsonl(HF_PATH):
            lang = record.get("tgt_lang")
            if lang in self._hf:
                self._hf[lang].append(record)
                self._hf_idx[lang][record.get("src", "").strip().lower()] = record

    # ── Lookup ────────────────────────────────────────────────
    def lookup(self, src_text: str, src_lang: str, tgt_lang: str,
               fuzzy: bool = True) -> dict | None:
        """
        O(1) exact lookup via index; O(n) fuzzy only when no exact match.
        Human feedback corrections take priority over govt TM.
        """
        src_norm = src_text.strip().lower()

        # 1. O(1) exact match — human feedback first
        r = self._hf_idx.get(tgt_lang, {}).get(src_norm)
        if r:
            return {**r, "match_type": "exact_hf", "score": 1.0}

        # 2. O(1) exact match — govt TM
        r = self._tm_idx.get(tgt_lang, {}).get(src_norm)
        if r:
            return {**r, "match_type": "exact_tm", "score": 1.0}

        if not fuzzy:
            return None

        # 3. Fuzzy match — only runs when no exact hit
        best_score, best_record = 0.0, None
        for r in self._hf.get(tgt_lang, []) + self._tm.get(tgt_lang, []):
            score = SequenceMatcher(None, src_norm, r.get("src", "").lower()).ratio()
            if score > best_score:
                best_score, best_record = score, r

        if best_score >= FUZZY_THRESHOLD and best_record:
            return {**best_record, "match_type": "fuzzy", "score": round(best_score, 3)}
        return None

    def lookup_batch(self, texts: list[str], src_lang: str,
                     tgt_lang: str) -> list[dict | None]:
        return [self.lookup(t, src_lang, tgt_lang) for t in texts]

    # ── Add government TM entries ─────────────────────────────
    def add_govt_entry(self, src: str, tgt: str, src_lang: str, tgt_lang: str,
                       domain: str = "government", verified: bool = True):
        record = _make_record(src, tgt, src_lang, tgt_lang, domain, verified, "govt_doc")
        self._tm.setdefault(tgt_lang, []).append(record)
        self._tm_idx[tgt_lang][src.strip().lower()] = record
        _append_jsonl(GOVT_TM_PATH, record)

    def add_govt_bulk(self, entries: list[dict]):
        """
        Bulk import government translations.
        entries: [{"src": "...", "tgt": "...", "src_lang": "eng",
                   "tgt_lang": "hin", "domain": "government"}]
        """
        for e in entries:
            self.add_govt_entry(
                e["src"], e["tgt"], e.get("src_lang", "eng"),
                e["tgt_lang"], e.get("domain", "government"),
                e.get("verified", True),
            )
        print(f"[TM] Added {len(entries)} govt entries")

    # ── Human feedback ────────────────────────────────────────
    def add_correction(self, src: str, wrong_tgt: str, correct_tgt: str,
                       src_lang: str, tgt_lang: str,
                       corrected_by: str = "human_reviewer"):
        log_entry = {
            "timestamp":    datetime.utcnow().isoformat(),
            "src":          src,
            "wrong_tgt":    wrong_tgt,
            "correct_tgt":  correct_tgt,
            "src_lang":     src_lang,
            "tgt_lang":     tgt_lang,
            "corrected_by": corrected_by,
        }
        _append_jsonl(CORR_LOG_PATH, log_entry)
        record = _make_record(src, correct_tgt, src_lang, tgt_lang,
                              "correction", True, "human_correction")
        self._hf.setdefault(tgt_lang, []).append(record)
        self._hf_idx[tgt_lang][src.strip().lower()] = record
        _append_jsonl(HF_PATH, record)
        print(f"[TM] Correction recorded → {LANG_NAMES.get(tgt_lang, tgt_lang)}: '{src[:40]}'")

    def add_corrections_bulk(self, corrections: list[dict]):
        """
        Bulk import human corrections.
        corrections: [{"src": "...", "wrong_tgt": "...", "correct_tgt": "...",
                       "src_lang": "eng", "tgt_lang": "hin"}]
        """
        for c in corrections:
            self.add_correction(
                c["src"], c.get("wrong_tgt", ""), c["correct_tgt"],
                c.get("src_lang", "eng"), c["tgt_lang"],
                c.get("corrected_by", "human_reviewer"),
            )
        print(f"[TM] Added {len(corrections)} corrections")

    # ── Export for fine-tuning ────────────────────────────────
    def export_for_finetuning(self, tgt_lang: str | None = None) -> list[dict]:
        """
        Export TM + HF records in fine-tuning format.
        Human feedback is returned 3x (upweighted) as in training scripts.
        If tgt_lang is None, exports all languages.
        """
        langs = [tgt_lang] if tgt_lang else ALL_22
        records = []
        for lang in langs:
            tm_recs = self._tm.get(lang, [])
            hf_recs = self._hf.get(lang, [])
            for r in tm_recs:
                records.append({"src": r["src"], "tgt": r["tgt"],
                                "src_lang": r["src_lang"], "tgt_lang": r["tgt_lang"]})
            for r in hf_recs * 3:   # 3x upweight
                records.append({"src": r["src"], "tgt": r["tgt"],
                                "src_lang": r["src_lang"], "tgt_lang": r["tgt_lang"]})
        return records

    # ── Stats ─────────────────────────────────────────────────
    def stats(self):
        print(f"\n{'='*55}")
        print("Translation Memory Stats")
        print(f"{'='*55}")
        print(f"{'Lang':<12} {'Govt TM':>10} {'Human FB':>10} {'Total':>10}")
        print("-" * 55)
        for lang in ALL_22:
            tm_n  = len(self._tm.get(lang, []))
            hf_n  = len(self._hf.get(lang, []))
            name  = LANG_NAMES.get(lang, lang)
            print(f"{name:<12} {tm_n:>10,} {hf_n:>10,} {tm_n+hf_n:>10,}")
        total_tm = sum(len(v) for v in self._tm.values())
        total_hf = sum(len(v) for v in self._hf.values())
        print("-" * 55)
        print(f"{'TOTAL':<12} {total_tm:>10,} {total_hf:>10,} {total_tm+total_hf:>10,}")
        print(f"{'='*55}\n")

    def correction_log(self) -> list[dict]:
        """Return full audit trail of human corrections."""
        return _read_jsonl(CORR_LOG_PATH)


# ── Helpers ───────────────────────────────────────────────────
def _make_record(src, tgt, src_lang, tgt_lang, domain, verified, source) -> dict:
    uid = hashlib.sha256(f"{src}{tgt_lang}".encode()).hexdigest()[:16]
    return {
        "id":       uid,
        "src":      src.strip(),
        "tgt":      tgt.strip(),
        "src_lang": src_lang,
        "tgt_lang": tgt_lang,
        "domain":   domain,
        "verified": verified,
        "source":   source,
        "added_at": datetime.utcnow().isoformat(),
    }


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _append_jsonl(path: Path, record: dict):
    """Thread-safe single-line append to a JSONL file."""
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── CLI ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Translation Memory Manager")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("stats", help="Show TM statistics")

    p_add = sub.add_parser("add", help="Add a govt TM entry")
    p_add.add_argument("--src",      required=True)
    p_add.add_argument("--tgt",      required=True)
    p_add.add_argument("--src-lang", default="eng")
    p_add.add_argument("--tgt-lang", required=True)
    p_add.add_argument("--domain",   default="government")

    p_fix = sub.add_parser("correct", help="Record a human correction")
    p_fix.add_argument("--src",       required=True)
    p_fix.add_argument("--wrong",     required=True)
    p_fix.add_argument("--correct",   required=True)
    p_fix.add_argument("--src-lang",  default="eng")
    p_fix.add_argument("--tgt-lang",  required=True)
    p_fix.add_argument("--by",        default="human_reviewer")

    p_imp = sub.add_parser("import", help="Bulk import from JSON file")
    p_imp.add_argument("--file",   required=True, help="Path to JSON array file")
    p_imp.add_argument("--type",   choices=["govt", "correction"], default="govt")

    p_look = sub.add_parser("lookup", help="Look up a translation")
    p_look.add_argument("--src",      required=True)
    p_look.add_argument("--src-lang", default="eng")
    p_look.add_argument("--tgt-lang", required=True)

    sub.add_parser("log", help="Show correction audit log")

    args = parser.parse_args()
    tm = TranslationMemory()

    if args.cmd == "stats":
        tm.stats()

    elif args.cmd == "add":
        tm.add_govt_entry(args.src, args.tgt, args.src_lang, args.tgt_lang, args.domain)
        print(f"[TM] Added: {args.src[:50]} → {args.tgt[:50]}")

    elif args.cmd == "correct":
        tm.add_correction(args.src, args.wrong, args.correct,
                          args.src_lang, args.tgt_lang, args.by)

    elif args.cmd == "import":
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        if args.type == "govt":
            tm.add_govt_bulk(data)
        else:
            tm.add_corrections_bulk(data)

    elif args.cmd == "lookup":
        result = tm.lookup(args.src, args.src_lang, args.tgt_lang)
        if result:
            print(f"Match ({result['match_type']}, score={result['score']}):")
            print(f"  src: {result['src']}")
            print(f"  tgt: {result['tgt']}")
        else:
            print("No TM match found.")

    elif args.cmd == "log":
        log = tm.correction_log()
        for entry in log[-20:]:   # last 20
            print(f"[{entry['timestamp']}] {entry['src_lang']}→{entry['tgt_lang']}: "
                  f"'{entry['src'][:40]}' corrected by {entry['corrected_by']}")
