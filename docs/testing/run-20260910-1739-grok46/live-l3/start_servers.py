"""Isolated demo + optional host API for Grok 4.6 L3 probes. Writes no secrets."""
from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

EVIDENCE = Path(__file__).resolve().parent
CANDIDATE = Path("/tmp/yunpai-test-candidate-grok46-pZG5r3")
DATA_DIR = Path(os.environ["DATA_DIR"]).resolve()
DEMO_PORT = int(os.environ.get("YUNPAI_DEMO_PORT", "18765"))
API_PORT = int(os.environ.get("YUNPAI_API_PORT", "18767"))

sys.path.insert(0, str(CANDIDATE / "src"))

from yunpai_customer_service.api import create_api_app  # noqa: E402
from yunpai_customer_service.demo.app import create_app  # noqa: E402


def _port_free(port: int) -> bool:
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _serve(app, host: str, port: int):
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, name=f"uvicorn-{port}", daemon=True)
    thread.start()
    deadline = time.monotonic() + 180
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.1)
    if not server.started:
        raise RuntimeError(f"server on {host}:{port} failed to start")
    return server, thread


def main() -> None:
    os.environ["DATA_DIR"] = str(DATA_DIR)
    os.environ["KG_IMPORT_ENABLED"] = "false"
    os.environ["KG_DREAM_WORKER_ENABLED"] = "false"
    os.environ.setdefault("MODEL_RETRY_ATTEMPTS", "0")
    # Isolated test credentials only. Never written to evidence.
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["ADMIN_AUTH_REQUIRED"] = "true"
    os.environ["BOOTSTRAP_TENANT_ID"] = "grok46-l3-tenant"
    os.environ["BOOTSTRAP_CLIENT_ID"] = "grok46-l3-client"
    os.environ["BOOTSTRAP_ADMIN_ID"] = "grok46-l3-admin"
    os.environ["BOOTSTRAP_CLIENT_KEY"] = secrets.token_hex(32)
    os.environ["SUBJECT_HASH_KEY"] = secrets.token_hex(32)
    os.environ["ADMIN_API_KEY"] = secrets.token_hex(32)

    if not _port_free(DEMO_PORT):
        raise SystemExit(f"demo port {DEMO_PORT} is in use")
    if not _port_free(API_PORT):
        raise SystemExit(f"api port {API_PORT} is in use")

    demo_app = create_app()
    demo_server, demo_thread = _serve(demo_app, "127.0.0.1", DEMO_PORT)
    runtime = demo_app.state.runtime
    host_api = {
        "started": False,
        "error": None,
        "listen": None,
        "note": "Demo is not a public host.",
    }
    api_server = None
    api_thread = None
    try:
        api_app = create_api_app(runtime.core)
        api_server, api_thread = _serve(api_app, "127.0.0.1", API_PORT)
        host_api = {
            "started": True,
            "error": None,
            "listen": f"127.0.0.1:{API_PORT}",
            "note": (
                "Host API started with ephemeral isolated credentials; "
                "env.md AUTH_REQUIRED was false and had no site client keys. "
                "Demo remains loopback-only and is not a public host."
            ),
        }
    except Exception as exc:
        host_api = {
            "started": False,
            "error": f"{type(exc).__name__}: {exc}",
            "listen": None,
            "note": "Host API did not start. Demo is not a public host.",
        }

    public = {
        "run_id": "run-20260910-1739-grok46",
        "executor": "cursor-grok-4.6",
        "candidate_root": str(CANDIDATE),
        "data_dir": str(DATA_DIR),
        "demo_url": f"http://127.0.0.1:{DEMO_PORT}",
        "demo_listen": f"127.0.0.1:{DEMO_PORT}",
        "host_api": host_api,
        "pid": os.getpid(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "configured_model_name": runtime.settings.model_name,
        "configured_model_provider": runtime.settings.model_provider,
        "model_mode": runtime.model_mode,
        "embedding_provider": runtime.core.knowledge.embedding_provider.name,
        "embedding_model": runtime.settings.rag_embedding_model,
        "auth_required_in_process": runtime.settings.auth_required,
        "source_file": str(CANDIDATE / "src" / "yunpai_customer_service" / "demo" / "app.py"),
        "qingchuan_seed_note": (
            "Demo runtime always seeds the Qingchuan catalog; "
            "synthetic QA-GROK document is imported via /api/knowledge/import "
            "and is the independent oracle."
        ),
    }
    (EVIDENCE / "runtime.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ready": True, **public}, ensure_ascii=False), flush=True)
    try:
        while True:
            time.sleep(1)
            if not demo_thread.is_alive():
                raise SystemExit("demo thread died")
    except KeyboardInterrupt:
        pass
    finally:
        demo_server.should_exit = True
        if api_server is not None:
            api_server.should_exit = True
        demo_thread.join(10)
        if api_thread is not None:
            api_thread.join(10)


if __name__ == "__main__":
    main()
