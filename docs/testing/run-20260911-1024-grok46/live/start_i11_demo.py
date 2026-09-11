"""Isolated mock Demo for I11 XSS. Refuses workspace data/."""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

EVIDENCE = Path(__file__).resolve().parent
WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
DATA_DIR = Path(os.environ["DATA_DIR"]).resolve()
if DATA_DIR == (WORKSPACE / "data").resolve() or (
    WORKSPACE in DATA_DIR.parents and DATA_DIR.name == "data"
):
    raise SystemExit("refusing to use workspace data/; set DATA_DIR under /tmp")
PORT = int(os.environ.get("YUNPAI_DEMO_PORT", "18770"))

sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from yunpai_customer_service.demo.app import create_app  # noqa: E402


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings = make_settings(DATA_DIR)
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", PORT))
    except OSError as exc:
        raise SystemExit(f"port {PORT} in use: {exc}") from exc
    finally:
        sock.close()
    app = create_app(settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="info", lifespan="on")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.1)
    if not server.started:
        raise SystemExit("demo failed to start")
    runtime = {
        "run_id": "run-20260911-1024-grok46",
        "demo_url": f"http://127.0.0.1:{PORT}",
        "data_dir": str(DATA_DIR),
        "pid": os.getpid(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "model_mode": "mock",
    }
    (EVIDENCE / "i11-runtime.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ready": True, **runtime}, ensure_ascii=False), flush=True)
    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(10)


if __name__ == "__main__":
    main()
