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


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already listening on host:port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        # connect_ex == 0 means a listener accepted the connection.
        return s.connect_ex(("127.0.0.1" if host == "0.0.0.0" else host, port)) == 0


def _pid_on_port(port: int):
    """Return the PID listening on `port` (Windows netstat), or None."""
    import subprocess, re
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            m = re.search(r"(\d+)\s*$", line.strip())
            if m:
                return int(m.group(1))
    return None


def _free_or_pick_port(host: str, port: int) -> int:
    """If `port` is busy, try to free a stale server on it; if that fails, pick
    the next open port. Returns the port to actually bind."""
    if not _port_in_use(host, port):
        return port
    pid = _pid_on_port(port)
    print(f"⚠️  Port {port} is already in use" + (f" by PID {pid}." if pid else "."))
    if pid:
        # Only offer to kill a stale *python* server (the usual cause here) —
        # never blindly kill an unknown process.
        import subprocess
        try:
            name = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10,
            ).stdout.lower()
        except Exception:
            name = ""
        if "python" in name:
            print(f"   It's a stale python server. Stopping PID {pid} to free the port...")
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=10)
                import time
                time.sleep(1.0)
                if not _port_in_use(host, port):
                    print(f"   ✅ Port {port} freed — starting here.")
                    return port
            except Exception as e:
                print(f"   Could not stop PID {pid}: {e}")
        else:
            print(f"   PID {pid} is not a python process — not touching it.")
    # Fall back to the next free port so the server always starts.
    import socket
    for p in range(port + 1, port + 21):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:  # nothing listening → free
                print(f"   → Using next free port {p} instead.")
                return p
    print(f"   Could not find a free port near {port}; trying {port} anyway.")
    return port


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

    # Resolve port conflicts up front: free a stale python server on the port,
    # or fall back to the next open port, so the launcher never dies with
    # "[Errno 10048] only one usage of each socket address ...".
    args.port = _free_or_pick_port(args.host, args.port)

    display_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    url = f"http://{display_host}:{args.port}"

    print("=" * 60)
    print("  KB Dubbing Studio — Web UI")
    print(f"  Serving at:  {url}")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    if not args.no_browser and not args.reload:
        _t = Timer(1.5, _open_browser, args=(url,))
        _t.daemon = True  # never block process exit
        _t.start()

    try:
        uvicorn.run(
            "api.server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    finally:
        # After uvicorn stops, torch/torch.compile/Triton worker threads and a
        # resident CUDA context can keep this process alive, hanging the
        # terminal and holding the port + GPU memory. The server's shutdown
        # hook (api/server.py) already released the models; force a hard exit
        # so the process actually terminates instead of waiting on
        # non-joinable background threads.
        import os
        try:
            sys.stdout.flush()
        except Exception:
            pass
        os._exit(0)


if __name__ == "__main__":
    main()
