"""K05 red: host /v1/chat maps idempotency conflict to 500. Isolated /tmp. No secrets."""
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
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="yunpai-k05-red-", dir="/tmp") as raw:
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
                second = client.post(
                    "/v1/chat",
                    headers=headers,
                    json={"session_id": "k05-session-aaaaaaaa", "message": "different question"},
                )
            payload = {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "id": "K05",
                "phase": "red",
                "command": "TestClient POST /v1/chat twice, same Idempotency-Key, different message",
                "first_status": first.status_code,
                "second_status": second.status_code,
                "second_body_preview": second.text[:400],
                "expected": "409/422 with idempotency_key_conflict, not 500",
                "observed": second.status_code,
                "status": "FAIL" if second.status_code == 500 else "UNEXPECTED",
            }
            (EVIDENCE / "before.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps({"first": first.status_code, "second": second.status_code}))
            return 0 if second.status_code == 500 else 1
        finally:
            core.close()


if __name__ == "__main__":
    raise SystemExit(main())
