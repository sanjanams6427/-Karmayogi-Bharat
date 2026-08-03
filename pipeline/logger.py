# ============================================================
# Structured Logger — JSON lines to file + console
# ============================================================
import json, logging, sys, time
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        obj = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
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
    ch.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    ch.setLevel(logging.INFO)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
