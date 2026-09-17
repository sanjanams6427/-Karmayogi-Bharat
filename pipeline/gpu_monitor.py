# ============================================================
# GPU Monitor — live stats + model load/evict event log
#
# Two independent things live here:
#
#   1. get_gpu_stats() shells out to `nvidia-smi` for current per-GPU
#      utilization / VRAM / temperature. Degrades to
#      {"available": False, ...} if nvidia-smi isn't on PATH (no NVIDIA
#      driver, CPU-only box, non-NVIDIA GPU) — callers must handle that,
#      not assume a GPU exists.
#
#   2. A small in-memory, thread-safe event log that pipeline code calls
#      into (log_load / log_swap / log_evict) whenever it actually loads,
#      swaps, or frees a GPU-resident engine. This is what makes the web
#      UI's GPU Monitor page show *why* memory moved — "IndicTrans2
#      (en_indic) loaded" / "SeamlessM4T loaded" / "translator+tts
#      evicted" — not just a number going up and down.
#
# Engine keys use a "<family>:<detail>" convention so unload_models() can
# evict everything under a prefix without needing to know every specific
# engine that might be loaded:
#   asr                              — faster-whisper (never evicted)
#   translator:indictrans2:<dir>     — one per IndicTrans2 direction
#   translator:seamless
#   translator:nllb
#   tts:parler
#   tts:mms_base                     — shared VITS base (adapter swaps
#                                       logged as "swap", not a new key)
#   tts:standalone_vits:<lang>       — one per language (these DO
#                                       accumulate — see tts.py)
# ============================================================

import subprocess
import threading
import time

_lock = threading.Lock()
_events: list[dict] = []
_loaded: dict[str, dict] = {}
_EVENT_CAP = 500  # bounded ring buffer — this is a live dashboard feed, not an audit log


def _now() -> float:
    return time.time()


def _record(kind: str, engine: str, label: str = "", detail: str = "") -> None:
    with _lock:
        _events.append({
            "ts": _now(), "kind": kind, "engine": engine,
            "label": label or engine, "detail": detail,
        })
        if len(_events) > _EVENT_CAP:
            del _events[: len(_events) - _EVENT_CAP]
        if kind in ("load", "swap"):
            _loaded[engine] = {"label": label or engine, "since": _now(), "detail": detail}
        elif kind == "evict":
            _loaded.pop(engine, None)


def log_load(engine: str, label: str = "", detail: str = "") -> None:
    """Record that `engine` was just loaded onto the GPU for the first time."""
    _record("load", engine, label, detail)


def log_swap(engine: str, label: str = "", detail: str = "") -> None:
    """Record an in-place swap on an already-loaded engine (e.g. MMS adapter change) —
    memory footprint doesn't grow, but it's still worth showing on the timeline."""
    _record("swap", engine, label, detail)


def log_evict(engine: str, label: str = "", detail: str = "") -> None:
    """Record that `engine` was just freed."""
    _record("evict", engine, label, detail)


def evict_all(prefix: str) -> None:
    """Mark every currently-loaded engine whose key starts with `prefix` as evicted.
    Used by DubbingPipeline.unload_models() / SegmentEditor.unload_models()."""
    with _lock:
        keys = [k for k in _loaded if k.startswith(prefix)]
    for k in keys:
        log_evict(k, detail="unload_models()")


def recent_events(since: float = 0.0, limit: int = 200) -> list[dict]:
    """Events strictly after `since` (unix seconds), most recent `limit` of them."""
    with _lock:
        out = [e for e in _events if e["ts"] > since]
    return out[-limit:]


def currently_loaded() -> dict[str, dict]:
    with _lock:
        return dict(_loaded)


def get_gpu_stats() -> dict:
    """Current per-GPU utilization/VRAM/temperature via `nvidia-smi`.
    Never raises — returns {"available": False, ...} on any failure so
    this is always safe to poll from an API endpoint."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return {"available": False, "gpus": [], "ts": _now(),
                     "error": (out.stderr or "nvidia-smi returned no output").strip()[:200]}
        gpus = []
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 6:
                continue
            idx, name, util, mem_used, mem_total, temp = parts
            mem_used_mb = float(mem_used)
            mem_total_mb = float(mem_total)
            # Some virtualized/passthrough drivers report a sentinel value
            # for memory.used (observed: 17592186044375 — ~2^44) instead of
            # a real reading or "[N/A]". Never show "used > total" in the UI.
            if mem_used_mb > mem_total_mb:
                mem_used_mb = mem_total_mb
            gpus.append({
                "index": int(idx), "name": name,
                "util_pct": float(util), "mem_used_mb": mem_used_mb,
                "mem_total_mb": mem_total_mb, "temp_c": float(temp),
            })
        return {"available": True, "gpus": gpus, "ts": _now()}
    except FileNotFoundError:
        return {"available": False, "gpus": [], "ts": _now(),
                 "error": "nvidia-smi not found on PATH"}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "gpus": [], "ts": _now(), "error": str(e)[:200]}
