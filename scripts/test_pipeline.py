# ============================================================
# Smoke test — verifies pipeline logic WITHOUT loading models
# Run: python scripts/test_pipeline.py  (from project root)
# ============================================================

import sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

PASS_COUNT = 0
FAIL_COUNT = 0

def check(label, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  PASS  {label}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))
    return condition

print("\n=== KB Pipeline Smoke Test ===\n")

# ── 1. lang_config ────────────────────────────────────────────
print("[1] lang_config — all 22 languages covered:")
try:
    from pipeline.lang_config import (
        ALL_22, LANG_NAMES, INDIC_TRANS2_CODES,
        SEAMLESS_CODES, NLLB_CODES
    )
    check("ALL_22 has 22 entries", len(ALL_22) == 22, str(len(ALL_22)))
    check("All 22 have LANG_NAMES",  all(c in LANG_NAMES         for c in ALL_22))
    check("All 22 have INDIC_TRANS2_CODES", all(c in INDIC_TRANS2_CODES for c in ALL_22))
    check("eng in INDIC_TRANS2_CODES (pivot)", "eng" in INDIC_TRANS2_CODES)
    check("SEAMLESS_CODES has eng+15 Indic langs", len(SEAMLESS_CODES) >= 15)
    check("NLLB_CODES has 21+ langs", len(NLLB_CODES) >= 21)
except Exception as e:
    check("lang_config import", False, str(e))

# ── 2. logger ─────────────────────────────────────────────────
print("\n[2] logger:")
try:
    from pipeline.logger import get_logger
    log = get_logger("smoke_test")
    check("get_logger returns logger", log is not None)
    log.info("smoke test log entry")
    check("log.info works without crash", True)
except Exception as e:
    check("logger", False, str(e))

# ── 3. retry + checkpoint ─────────────────────────────────────
print("\n[3] retry + JobCheckpoint:")
try:
    from pipeline.retry import retry, JobCheckpoint
    @retry(max_attempts=3, delay=0.01)
    def _flaky(counter=[0]):
        counter[0] += 1
        if counter[0] < 3:
            raise ValueError("retry me")
        return "ok"
    result = _flaky()
    check("retry decorator retries and succeeds", result == "ok")

    ckpt = JobCheckpoint("_smoke_test_job")
    ckpt.set_meta("test_key", 42)
    check("checkpoint set_meta/get_meta", ckpt.get_meta("test_key") == 42)
    ckpt.mark_done(0, {"text": "hello"})
    ckpt.flush()
    check("checkpoint mark_done + flush", ckpt.is_done(0))
    ckpt.clear()
    check("checkpoint clear removes file", not ckpt.path.exists())
except Exception as e:
    check("retry/checkpoint", False, str(e))
    traceback.print_exc()

# ── 4. quality scorer ─────────────────────────────────────────
print("\n[4] quality scorer:")
try:
    from pipeline.quality import score_segment, review_summary, detect_transliteration
    s = score_segment("Hello world how are you", "नमस्ते दुनिया आप कैसे हैं", "eng", "hin")
    check("score_segment returns dict with score", "score" in s and 0 <= s["score"] <= 1)
    check("score_segment has flags list", isinstance(s.get("flags"), list))

    # Transliteration detection
    check("detects transliteration (Latin in Hindi target)",
          detect_transliteration("namaste duniya aap kaise hain", "hin"))
    check("no false positive on real Hindi",
          not detect_transliteration("नमस्ते दुनिया आप कैसे हैं", "hin"))

    summary = review_summary([s, s])
    check("review_summary has avg_score", "avg_score" in summary)
    check("review_summary total=2", summary["total"] == 2)
except Exception as e:
    check("quality scorer", False, str(e))
    traceback.print_exc()

# ── 5. glossary ───────────────────────────────────────────────
print("\n[5] glossary:")
try:
    from pipeline.glossary import GlossaryManager
    gm = GlossaryManager()
    gm.add_term("iGOT", "iGOT", "hin")
    protected, pmap = gm.protect_terms("iGOT Karmayogi platform", "hin")
    check("protect_terms replaces glossary term", "__GLOSS_" in protected)
    restored = gm.restore_terms(protected, pmap)
    check("restore_terms brings back original", "iGOT" in restored)
except Exception as e:
    check("glossary", False, str(e))
    traceback.print_exc()

# ── 6. subtitles ──────────────────────────────────────────────
print("\n[6] subtitles:")
try:
    import tempfile, os
    from pipeline.subtitles import generate_srt, generate_vtt
    segs = [
        {"id": 0, "start": 0.0,  "end": 3.5,  "text": "Hello world"},
        {"id": 1, "start": 3.5,  "end": 7.0,  "text": "This is a test"},
        {"id": 2, "start": 7.0,  "end": 10.0, "text": ""},
    ]
    with tempfile.TemporaryDirectory() as td:
        srt = generate_srt(segs, os.path.join(td, "test.srt"))
        vtt = generate_vtt(segs, os.path.join(td, "test.vtt"))
        srt_content = Path(srt).read_text(encoding="utf-8")
        vtt_content = Path(vtt).read_text(encoding="utf-8")
        check("SRT file created with 2 entries", srt_content.count("-->") == 2)
        check("VTT file starts with WEBVTT", vtt_content.startswith("WEBVTT"))
        check("Empty segment skipped in SRT", "3\n" not in srt_content)
except Exception as e:
    check("subtitles", False, str(e))
    traceback.print_exc()

# ── 7. lang_detect ────────────────────────────────────────────
print("\n[7] lang_detect:")
try:
    from pipeline.lang_detect import fw_lang_to_internal, tag_segments
    check("fw hi -> hin", fw_lang_to_internal("hi") == "hin")
    check("fw en -> eng", fw_lang_to_internal("en") == "eng")
    check("fw unknown -> fallback eng", fw_lang_to_internal("xx", "eng") == "eng")

    segs = [{"id": 0, "start": 0.0, "end": 2.0, "text": "test"}]
    # bod is lingua-unsupported — should always return assumed_lang
    tagged = tag_segments(segs, "bod")
    check("tag_segments bod always returns bod", tagged[0]["detected_lang"] == "bod")
except Exception as e:
    check("lang_detect", False, str(e))
    traceback.print_exc()

# ── 8. dubbing pipeline instantiation ────────────────────────
print("\n[8] DubbingPipeline (no model load):")
try:
    from pipeline.dubbing_pipeline import DubbingPipeline, DubbingResult
    dp = DubbingPipeline(use_glossary=True, use_tm=False)
    check("DubbingPipeline instantiates", dp is not None)
    check("_asr is None (lazy)", dp._asr is None)
    check("_translator is None (lazy)", dp._translator is None)
    check("_tts is None (lazy)", dp._tts is None)

    # Test exclusion detection
    skip, reason = dp.should_skip_translation([
        {"text": "Speech by Prime Minister Narendra Modi at the event"}
    ])
    check("exclusion: PM speech detected", skip)

    skip2, _ = dp.should_skip_translation([
        {"text": "PMMY scheme helps farmers get loans"}
    ])
    check("exclusion: PMMY scheme NOT blocked", not skip2)

    # Test input validation errors
    try:
        dp._validate_input("nonexistent_file.mp4")
        check("validate_input raises on missing file", False)
    except FileNotFoundError:
        check("validate_input raises FileNotFoundError", True)

    try:
        dp._validate_input(__file__)  # .py file — wrong extension
        check("validate_input raises on bad extension", False)
    except ValueError:
        check("validate_input raises ValueError on bad ext", True)

except Exception as e:
    check("DubbingPipeline", False, str(e))
    traceback.print_exc()

# ── 9. translator instantiation (no model load) ───────────────
print("\n[9] Translator (no model load):")
try:
    from pipeline.translator import Translator
    t = Translator()
    check("Translator instantiates", t is not None)
    check("_seamless is None (lazy)", t._seamless is None)
    check("_nllb is None (lazy)", t._nllb is None)
    check("passthrough for same lang", 
          t.translate("hello", "eng", "eng")["engine"] == "passthrough")
except Exception as e:
    check("Translator", False, str(e))
    traceback.print_exc()

# ── 10. datasets present ──────────────────────────────────────
print("\n[10] Datasets:")
try:
    from pipeline.lang_config import ALL_22
    data_root = Path("datasets/parallel")
    missing = [l for l in ALL_22 if not (data_root / l / "train.jsonl").exists()]
    check(f"All 22 parallel train sets present", len(missing) == 0,
          f"missing: {missing}")
    # Check record counts for a few key langs
    import json
    for lang in ["hin", "tam", "ben"]:
        p = data_root / lang / "train.jsonl"
        if p.exists():
            n = sum(1 for _ in p.open(encoding="utf-8"))
            check(f"{lang} train has records", n > 0, f"{n} records")
except Exception as e:
    check("datasets", False, str(e))

# ── 11. model weights present ─────────────────────────────────
print("\n[11] Model weights:")
try:
    checks = [
        ("IndicTrans2 en_indic",    Path("models/indic_tr/en_indic/pytorch_model.bin")),
        ("IndicTrans2 indic_en",    Path("models/indic_tr/indic_en/pytorch_model.bin")),
        ("IndicTrans2 indic_indic", Path("models/indic_tr/indic_indic/pytorch_model.bin")),
        ("SeamlessM4T shard 1",     Path("models/seamless/model-00001-of-00002.safetensors")),
        ("SeamlessM4T shard 2",     Path("models/seamless/model-00002-of-00002.safetensors")),
        ("faster-whisper",          Path("models/indic_asr")),
        ("Parler-TTS",              Path("models/indic_parler_tts")),
    ]
    for label, p in checks:
        check(label, p.exists(), f"not found: {p}")
except Exception as e:
    check("model weights", False, str(e))

# ── Summary ───────────────────────────────────────────────────
total = PASS_COUNT + FAIL_COUNT
print(f"\n{'='*40}")
print(f"  PASSED: {PASS_COUNT}/{total}")
print(f"  FAILED: {FAIL_COUNT}/{total}")
print(f"{'='*40}\n")
sys.exit(0 if FAIL_COUNT == 0 else 1)
