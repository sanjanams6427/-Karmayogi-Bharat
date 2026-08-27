#!/usr/bin/env python
# ============================================================
# KB Translation System — Web UI launcher
# RFB IN-KBL-543730-NC-RFB | iGOT Karmayogi
#
#   python run_web.py
#
# Starts the FastAPI backend (api/server.py) which serves both the
# REST/SSE API and the static web UI in web/.  Open:
#
#       http://localhost:8000
#
# Options (all optional):
#   --host 0.0.0.0     bind address (default 127.0.0.1)
#   --port 8000        port (default 8000)
#   --reload           auto-reload on code changes (dev only)
# ============================================================

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path
from threading import Timer

# Make the project root importable so `api.server` resolves.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the KB Dubbing Studio web UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        sys.exit(
            "uvicorn is not installed. Install web dependencies with:\n"
            "    pip install -r requirements.txt"
        )

    web_dir = _ROOT / "web"
    if not (web_dir / "index.html").exists():
        print(f"WARNING: {web_dir/'index.html'} not found — the UI may not load.")

    display_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{display_host}:{args.port}"

    print("=" * 60)
    print("  KB Dubbing Studio — Web UI")
    print(f"  Serving at:  {url}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    if not args.no_browser and not args.reload:
        Timer(1.5, _open_browser, args=(url,)).start()

    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
