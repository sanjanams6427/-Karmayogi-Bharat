"""
Loop-engineered audio dataset collector.
Runs until all 22 Indian languages have audio data.
Tries every known source per language before giving up.
"""
import os, sys, io, time, logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Fix Windows cp1252 console
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/collect_audio_22.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

AUDIO_BASE = Path("datasets/audio")

ALL_22 = [
    "asm", "ben", "guj", "hin", "kan", "mal", "mar", "ory", "pan", "tam", "tel",
    "bod", "doi", "kas", "kok", "mni", "mai", "nep", "san", "sat", "snd", "urd",
]

LANG_NAMES = {
    "asm": "Assamese",  "ben": "Bengali",   "guj": "Gujarati",  "hin": "Hindi",
    "kan": "Kannada",   "mal": "Malayalam", "mar": "Marathi",   "ory": "Odia",
    "pan": "Punjabi",   "tam": "Tamil",     "tel": "Telugu",    "bod": "Bodo",
    "doi": "Dogri",     "kas": "Kashmiri",  "kok": "Konkani",   "mni": "Manipuri",
    "mai": "Maithili",  "nep": "Nepali",    "san": "Sanskrit",  "sat": "Santhali",
    "snd": "Sindhi",    "urd": "Urdu",
}

# Minimum bytes to consider a language "covered" (~30 min audio)
MIN_AUDIO_BYTES = 200 * 1024 * 1024  # 200 MB

# Languages that currently only have tiny IndicSUPERB stubs — force re-collect
FORCE_COLLECT = {"doi", "kas", "kok", "mai", "mni", "san", "sat", "snd"}

# OpenSLR direct HTTP downloads (datasets 5.x dropped legacy script support)
# Only Kashmiri (SLR122) actually exists on OpenSLR for these 8 langs.
# doi, kok, mni, mai, san, sat, snd have NO public audio datasets available.
OPENSLR_HTTP = {
    "kas": ("https://openslr.trmal.net/resources/122/kashmiri.tar.gz", "openslr/kashmiri"),
}

# Each entry: (source_key, hf_repo, hf_config_or_None, local_subdir)
SOURCES = {
    "asm": [
        ("fleurs",     "google/fleurs",                        "as_in",    "fleurs/assamese"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "ben": [
        ("fleurs",     "google/fleurs",                        "bn_in",    "fleurs/bengali"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "bn",       "common_voice/bengali"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "guj": [
        ("fleurs",     "google/fleurs",                        "gu_in",    "fleurs/gujarati"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "gu-IN",    "common_voice/gujarati"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "hin": [
        ("fleurs",     "google/fleurs",                        "hi_in",    "fleurs/hindi"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "hi",       "common_voice/hindi"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "kan": [
        ("fleurs",     "google/fleurs",                        "kn_in",    "fleurs/kannada"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "kn",       "common_voice/kannada"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "mal": [
        ("fleurs",     "google/fleurs",                        "ml_in",    "fleurs/malayalam"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "ml",       "common_voice/malayalam"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "mar": [
        ("fleurs",     "google/fleurs",                        "mr_in",    "fleurs/marathi"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "mr",       "common_voice/marathi"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "ory": [
        ("fleurs",     "google/fleurs",                        "or_in",    "fleurs/odia"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "or",       "common_voice/odia"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "pan": [
        ("fleurs",     "google/fleurs",                        "pa_in",    "fleurs/punjabi"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "pa-IN",    "common_voice/punjabi"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "tam": [
        ("fleurs",     "google/fleurs",                        "ta_in",    "fleurs/tamil"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "ta",       "common_voice/tamil"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "tel": [
        ("fleurs",     "google/fleurs",                        "te_in",    "fleurs/telugu"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "te",       "common_voice/telugu"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "urd": [
        ("fleurs",     "google/fleurs",                        "ur_pk",    "fleurs/urdu"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "ur",       "common_voice/urdu"),
        ("shrutilipi", "ai4bharat/Shrutilipi",                 None,       "shrutilipi"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "nep": [
        ("fleurs",     "google/fleurs",                        "ne_np",    "fleurs/nepali"),
        ("cv",         "mozilla-foundation/common_voice_17_0", "ne-NP",    "common_voice/nepali"),
        ("indicsuper", "alekya/IndicSUPERB",                   None,       "indicsuper"),
    ],
    "mai": [
        ("indicvoices", "ai4bharat/IndicVoices", "maithili",  "indicvoices/maithili"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
    ],
    "san": [
        ("indicvoices", "ai4bharat/IndicVoices", "sanskrit",  "indicvoices/sanskrit"),
        ("cv",          "mozilla-foundation/common_voice_17_0", "sa", "common_voice/sanskrit"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
    ],
    "bod": [
        ("bodo_asr",    "XKaab/ASR-Bodo_5hrs",   None,        "bodo_asr"),
        ("indicvoices", "ai4bharat/IndicVoices", "bodo",      "indicvoices/bodo"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
    "doi": [
        ("indicvoices", "ai4bharat/IndicVoices", "dogri",     "indicvoices/dogri"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
    "kas": [
        ("indicvoices", "ai4bharat/IndicVoices", "kashmiri",  "indicvoices/kashmiri"),
        ("openslr_http", None, None,                          "openslr/kashmiri"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
    "kok": [
        ("indicvoices", "ai4bharat/IndicVoices", "konkani",   "indicvoices/konkani"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
    "mni": [
        ("indicvoices", "ai4bharat/IndicVoices", "manipuri",  "indicvoices/manipuri"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
    "sat": [
        ("indicvoices", "ai4bharat/IndicVoices", "santali",   "indicvoices/santali"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
    "snd": [
        ("indicvoices", "ai4bharat/IndicVoices", "sindhi",    "indicvoices/sindhi"),
        ("shrutilipi",  "ai4bharat/Shrutilipi",  None,        "shrutilipi"),
        ("indicsuper",  "alekya/IndicSUPERB",    None,        "indicsuper"),
    ],
}


def audio_bytes(local_subdir: str) -> int:
    p = AUDIO_BASE / local_subdir
    return sum(f.stat().st_size for f in p.rglob("*") if f.suffix in (".arrow", ".wav", ".flac", ".mp3")) if p.exists() else 0


def has_audio(local_subdir: str) -> bool:
    return audio_bytes(local_subdir) > 0


def lang_covered(lang: str) -> bool:
    total = sum(audio_bytes(subdir) for (_, _, _, subdir) in SOURCES[lang])
    if lang in FORCE_COLLECT:
        return total >= MIN_AUDIO_BYTES
    return total > 0


def download_openslr_http(lang: str) -> bool:
    import urllib.request, tarfile
    if lang not in OPENSLR_HTTP:
        return False
    url, local_subdir = OPENSLR_HTTP[lang]
    dest = AUDIO_BASE / local_subdir
    if audio_bytes(local_subdir) >= MIN_AUDIO_BYTES:
        log.info(f"  [SKIP] {local_subdir} already has sufficient data")
        return True
    dest.mkdir(parents=True, exist_ok=True)
    tar_path = dest / "data.tar.gz"
    try:
        t0 = time.time()
        log.info(f"    Downloading {url}")
        urllib.request.urlretrieve(url, tar_path)
        log.info(f"    Extracting...")
        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(dest)
        tar_path.unlink()
        log.info(f"  [OK] {local_subdir}  ({time.time()-t0:.0f}s)  {audio_bytes(local_subdir)//1024**2} MB raw")
        return True
    except Exception as e:
        log.warning(f"  [FAIL] openslr_http/{local_subdir}: {str(e)[:200]}")
        if tar_path.exists():
            tar_path.unlink()
        return False


def download(src_key: str, repo: str, config, local_subdir: str) -> bool:
    if src_key == "openslr_http":
        lang = next((l for l, (_, s) in OPENSLR_HTTP.items() if s == local_subdir), None)
        return download_openslr_http(lang) if lang else False
    from datasets import load_dataset, DatasetDict
    dest = AUDIO_BASE / local_subdir
    if has_audio(local_subdir):
        log.info(f"  [SKIP] {local_subdir} already has data")
        return True
    dest.mkdir(parents=True, exist_ok=True)
    try:
        t0 = time.time()
        kwargs = dict(token=HF_TOKEN) if HF_TOKEN else {}
        ds = load_dataset(repo, config, **kwargs) if config else load_dataset(repo, **kwargs)
        if not isinstance(ds, dict):
            ds = DatasetDict({"train": ds})
        ds.save_to_disk(str(dest))
        log.info(f"  [OK] {local_subdir}  ({time.time()-t0:.0f}s)")
        return True
    except Exception as e:
        log.warning(f"  [FAIL] {src_key}/{local_subdir}: {str(e)[:200]}")
        try:
            if dest.exists() and not any(dest.iterdir()):
                dest.rmdir()
        except Exception:
            pass
        return False


SEP = "-" * 65

log.info(SEP)
log.info("  AUDIO COLLECTION LOOP - target: all 22 languages")
log.info(SEP)

MAX_ROUNDS = 10

for round_num in range(1, MAX_ROUNDS + 1):
    missing = [l for l in ALL_22 if not lang_covered(l)]
    done    = [l for l in ALL_22 if     lang_covered(l)]

    log.info(f"\n{SEP}")
    log.info(f"  ROUND {round_num}/{MAX_ROUNDS}  |  Done {len(done)}/22  |  Missing: {missing or 'NONE'}")
    log.info(SEP)

    if not missing:
        log.info("  [DONE] All 22 languages covered - stopping.")
        break

    made_progress = False
    for lang in missing:
        lang_name = LANG_NAMES[lang]
        log.info(f"\n  [{lang}] {lang_name} - trying sources...")
        for (src_key, repo, config, subdir) in SOURCES[lang]:
            log.info(f"    -> {src_key}  repo={repo}  config={config}")
            ok = download(src_key, repo, config, subdir)
            if ok and lang_covered(lang):
                log.info(f"    [COVERED] {lang_name} via {src_key}")
                made_progress = True
                break

    if not made_progress:
        log.warning("\n  [WARN] No progress this round - all remaining sources failed.")
        log.warning("  Check HF_TOKEN, network, or dataset availability. Exiting loop.")
        break

# Final report
log.info(f"\n{SEP}")
log.info("  FINAL AUDIO COVERAGE REPORT")
log.info(SEP)
covered = []
still_missing = []
for lang in ALL_22:
    total_mb = sum(audio_bytes(d) for (_, _, _, d) in SOURCES[lang]) / 1024**2
    sources_found = [s for (s, _, _, d) in SOURCES[lang] if has_audio(d)]
    if lang_covered(lang):
        log.info(f"  [OK] {lang:<5} {LANG_NAMES[lang]:<12}  {total_mb:6.0f} MB  {', '.join(sources_found)}")
        covered.append(lang)
    else:
        log.info(f"  [XX] {lang:<5} {LANG_NAMES[lang]:<12}  {total_mb:6.0f} MB  INSUFFICIENT")
        still_missing.append(lang)

log.info(f"\n  Coverage: {len(covered)}/22")
if still_missing:
    log.info(f"  Still missing: {still_missing}")
    log.info("  Possible reasons: dataset gated, config name changed, or not on HF Hub.")
else:
    log.info("  All 22 languages have audio data!")
log.info(SEP)
