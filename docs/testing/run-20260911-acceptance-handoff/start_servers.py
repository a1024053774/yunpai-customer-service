"""Isolated demo + host API for acceptance-handoff. Writes no secrets to evidence."""
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
WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
DATA_DIR = Path(os.environ["DATA_DIR"]).resolve()
WS_DATA = (WORKSPACE / "data").resolve()
if DATA_DIR == WS_DATA or (WORKSPACE in DATA_DIR.parents and DATA_DIR.name == "data"):
    raise SystemExit("ISO-001: refusing workspace data/; set DATA_DIR under /tmp")
if not (str(DATA_DIR).startswith("/tmp/") or str(DATA_DIR).startswith("/private/tmp/")):
    raise SystemExit("ISO-001: DATA_DIR must be under /tmp or /private/tmp")

DEMO_PORT = int(os.environ.get("YUNPAI_DEMO_PORT", "0"))
API_PORT = int(os.environ.get("YUNPAI_API_PORT", "0"))

sys.path.insert(0, str(WORKSPACE / "src"))

from yunpai_customer_service.api import create_api_app  # noqa: E402
from yunpai_customer_service.demo.app import create_app  # noqa: E402


def _free_port() -> int:
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


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
    deadline = time.monotonic() + 240
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
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["ADMIN_AUTH_REQUIRED"] = "true"
    os.environ["BOOTSTRAP_TENANT_ID"] = "handoff-l3-tenant"
    os.environ["BOOTSTRAP_CLIENT_ID"] = "handoff-l3-client"
    os.environ["BOOTSTRAP_ADMIN_ID"] = "handoff-l3-admin"
    os.environ.setdefault("BOOTSTRAP_CLIENT_KEY", secrets.token_hex(32))
    os.environ.setdefault("SUBJECT_HASH_KEY", secrets.token_hex(32))
    os.environ.setdefault("ADMIN_API_KEY", secrets.token_hex(32))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cred_path = DATA_DIR / ".host-api-creds.json"
    cred_path.write_text(
        json.dumps(
            {
                "client_id": os.environ["BOOTSTRAP_CLIENT_ID"],
                "client_key": os.environ["BOOTSTRAP_CLIENT_KEY"],
                "tenant_id": os.environ["BOOTSTRAP_TENANT_ID"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cred_path.chmod(0o600)

    demo_port = DEMO_PORT or _free_port()
    api_port = API_PORT or _free_port()
    if demo_port == api_port:
        api_port = _free_port()
    if not _port_free(demo_port):
        raise SystemExit(f"demo port {demo_port} is in use")
    if not _port_free(api_port):
        raise SystemExit(f"api port {api_port} is in use")

    demo_app = create_app()
    demo_server, demo_thread = _serve(demo_app, "127.0.0.1", demo_port)
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
        api_server, api_thread = _serve(api_app, "127.0.0.1", api_port)
        host_api = {
            "started": True,
            "error": None,
            "listen": f"127.0.0.1:{api_port}",
            "note": (
                "Host API started with ephemeral isolated credentials. "
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

    identity = getattr(runtime.core.knowledge.embedding_provider, "identity", None)
    if hasattr(identity, "__dict__"):
        identity = {
            k: v
            for k, v in vars(identity).items()
            if not SECRET_ish(k)
        }
    public = {
        "run_id": "run-20260911-acceptance-handoff",
        "executor": "cursor-grok-4.6-xhigh-fast",
        "not_orca": True,
        "not_luna": True,
        "candidate_root": str(WORKSPACE),
        "data_dir": str(DATA_DIR),
        "workspace_data_refused": True,
        "demo_url": f"http://127.0.0.1:{demo_port}",
        "demo_listen": f"127.0.0.1:{demo_port}",
        "host_api": host_api,
        "pid": os.getpid(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "configured_model_name": runtime.settings.model_name,
        "configured_model_provider": runtime.settings.model_provider,
        "configured_model_base_host": _host_only(runtime.settings.model_base_url),
        "model_mode": runtime.model_mode,
        "model_enabled": runtime.settings.model_enabled,
        "model_mock_mode": runtime.settings.model_mock_mode,
        "model_api_key_present": bool(runtime.settings.model_api_key),
        "vision_enabled": runtime.settings.vision_enabled,
        "vision_model": runtime.settings.vision_model_name,
        "embedding_provider": runtime.core.knowledge.embedding_provider.name,
        "embedding_identity": _safe_identity(identity),
        "embedding_model": runtime.settings.rag_embedding_model,
        "ocr_parser": "pdfplumber+optional-docling",
        "auth_required_in_process": runtime.settings.auth_required,
        "schema_version": runtime.db.schema_version()
        if hasattr(runtime.db, "schema_version")
        else None,
        "iso_001": "source env.md then export DATA_DIR; refused workspace data/",
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


def SECRET_ish(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in ("key", "secret", "token", "password"))


def _safe_identity(identity):
    if identity is None:
        return None
    if isinstance(identity, dict):
        return {k: v for k, v in identity.items() if not SECRET_ish(k)}
    text = str(identity)
    return text[:500]


def _host_only(url: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    return parts.hostname or ""


if __name__ == "__main__":
    main()
