# ============================================================
# Structured Logger — JSON lines to file + console
# ============================================================
import json, logging, os, sys, time
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Which GPU this PROCESS is pinned to. Set by the parent's env= for TTS
# shard workers (and by dub_course_parallel language workers), absent in
# the web-server process. Read once at import — the env is fixed before
# the interpreter starts for subprocesses, which is the only case where
# it's meaningful. With 4 shard workers all writing pipeline.log, a line
# like "Parler single TIMEOUT [hin]" is unattributable without this.
_GPU = os.environ.get("PIPELINE_GPU")


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        obj = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        if _GPU is not None:
            obj["gpu"] = _GPU
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            obj.update(record.extra)
        return json.dumps(obj, ensure_ascii=False)


def get_logger(name: str, log_file: str = "pipeline.log") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    # File handler — JSON lines, 10MB rotate, keep 5
    fh = RotatingFileHandler(
        LOGS_DIR / log_file, maxBytes=10 * 1024 * 1024,
        backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(_JsonFormatter())
    fh.setLevel(logging.DEBUG)

    # Console handler — human readable, UTF-8 safe on Windows
    import io
    ch = logging.StreamHandler(
        io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        if hasattr(sys.stdout, 'buffer') else sys.stdout
    )
    _prefix = f"[gpu{_GPU}]" if _GPU is not None else ""
    ch.setFormatter(logging.Formatter(f"{_prefix}[%(name)s] %(message)s"))
    ch.setLevel(logging.INFO)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
