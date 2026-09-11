"""Localhost HTTP for G04 screenshots. Do not use file://."""
from __future__ import annotations

import http.server
import os
import socket
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("G04_HTML_PORT", "18771"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, *_args):
        return


def main() -> None:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", PORT))
    except OSError as exc:
        raise SystemExit(f"port {PORT} in use: {exc}") from exc
    finally:
        sock.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"http://127.0.0.1:{PORT}/before.html", flush=True)
    print(f"http://127.0.0.1:{PORT}/after.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
