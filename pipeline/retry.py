# ============================================================
# Retry decorator + Checkpoint/Resume manager
# ============================================================
import json, time, functools, threading
from pathlib import Path
from .logger import get_logger

log = get_logger("retry")
CHECKPOINT_DIR = Path(__file__).parent.parent / "checkpoints" / "jobs"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def retry(max_attempts: int = 3, delay: float = 2.0, exceptions=(Exception,)):
    """Decorator: retry on failure with exponential backoff."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    wait = delay * (2 ** (attempt - 1))
                    log.warning(f"{fn.__name__} attempt {attempt}/{max_attempts} failed: {e} — retrying in {wait:.1f}s")
                    if attempt < max_attempts:
                        time.sleep(wait)
            log.error(f"{fn.__name__} failed after {max_attempts} attempts: {last_exc}")
            raise last_exc
        return wrapper
    return decorator


class JobCheckpoint:
    """
    Persist per-segment results to disk so a crashed job can resume
    from the last completed segment instead of restarting from zero.
    Thread-safe: all reads/writes protected by an instance-level lock.
    """

    def __init__(self, job_id: str):
        self.path   = CHECKPOINT_DIR / f"{job_id}.json"
        self._lock  = threading.Lock()
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"completed": {}, "meta": {}}

    def _save(self):
        # Atomic write: write to .tmp then rename so partial writes never corrupt
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        tmp.replace(self.path)

    def set_meta(self, key: str, value):
        with self._lock:
            self._data["meta"][key] = value
            self._save()

    def get_meta(self, key: str, default=None):
        with self._lock:
            return self._data["meta"].get(key, default)

    def mark_done(self, seg_id: int, result: dict):
        with self._lock:
            self._data["completed"][str(seg_id)] = result

    def flush(self):
        """Persist checkpoint to disk atomically."""
        with self._lock:
            self._save()

    def get_done(self, seg_id: int) -> dict | None:
        with self._lock:
            return self._data["completed"].get(str(seg_id))

    def is_done(self, seg_id: int) -> bool:
        with self._lock:
            return str(seg_id) in self._data["completed"]

    def clear(self):
        with self._lock:
            if self.path.exists():
                self.path.unlink()
            self._data = {"completed": {}, "meta": {}}
