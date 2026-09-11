"""K05 green: same TestClient signal after host API maps SessionScopeError."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import TableDrivenModel, build_core  # noqa: E402
from yunpai_customer_service.api import create_api_app  # noqa: E402
from yunpai_customer_service.auth import AuthenticationService  # noqa: E402


def main() -> int:
    with TemporaryDirectory(prefix="yunpai-k05-green-", dir="/tmp") as raw:
        data_dir = Path(raw)
        settings = make_settings(data_dir)
        core = build_core(data_dir, settings=settings, model=TableDrivenModel(settings))
        try:
            auth = AuthenticationService(core.db, settings)
            app = create_api_app(core, auth=auth)
            headers = {
                "X-Client-Id": settings.bootstrap_client_id,
                "X-Client-Key": settings.bootstrap_client_key,
                "X-Subject-Id": "k05-buyer",
                "Idempotency-Key": "k05-same-key",
            }
            with TestClient(app, raise_server_exceptions=False) as client:
                first = client.post(
                    "/v1/chat",
                    headers=headers,
                    json={"session_id": "k05-session-aaaaaaaa", "message": "first question"},
                )
                replay = client.post(
                    "/v1/chat",
                    headers=headers,
                    json={"session_id": "k05-session-aaaaaaaa", "message": "first question"},
                )
                second = client.post(
                    "/v1/chat",
                    headers=headers,
                    json={"session_id": "k05-session-aaaaaaaa", "message": "different question"},
                )
                stream = client.post(
                    "/v1/chat/stream",
                    headers=headers,
                    json={"session_id": "k05-session-aaaaaaaa", "message": "another different"},
                )
            body = second.json() if second.headers.get("content-type", "").startswith("application/json") else {"raw": second.text[:400]}
            ok = (
                first.status_code == 200
                and replay.status_code == 200
                and first.json().get("message_id") == replay.json().get("message_id")
                and second.status_code == 409
                and (body.get("detail") or {}).get("code") == "idempotency_key_conflict"
                and stream.status_code == 409
            )
            payload = {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "id": "K05",
                "phase": "green",
                "first_status": first.status_code,
                "replay_status": replay.status_code,
                "same_message_id": first.json().get("message_id") == replay.json().get("message_id"),
                "second_status": second.status_code,
                "second_body": body,
                "stream_status": stream.status_code,
                "status": "PASS" if ok else "FAIL",
            }
            (EVIDENCE / "after.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"ok": ok, "second": second.status_code, "stream": stream.status_code}))
            return 0 if ok else 1
        finally:
            core.close()


if __name__ == "__main__":
    raise SystemExit(main())
