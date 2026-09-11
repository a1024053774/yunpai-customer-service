"""K04 red: concurrent same Idempotency-Key + same body must not 500."""
from __future__ import annotations

import json
import sys
import threading
import uuid
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
    with TemporaryDirectory(prefix="yunpai-k04-red-", dir="/tmp") as raw:
        data_dir = Path(raw)
        settings = make_settings(data_dir)
        core = build_core(data_dir, settings=settings, model=TableDrivenModel(settings))
        try:
            auth = AuthenticationService(core.db, settings)
            app = create_api_app(core, auth=auth)
            headers = {
                "X-Client-Id": settings.bootstrap_client_id,
                "X-Client-Key": settings.bootstrap_client_key,
                "X-Subject-Id": "k04-buyer",
                "Idempotency-Key": "k04-same-concurrent",
            }
            payload = {
                "session_id": "k04sess-" + uuid.uuid4().hex[:10],
                "message": "same concurrent kettle question",
            }
            statuses: list[int] = []
            bodies: list[str] = []
            with TestClient(app, raise_server_exceptions=False) as client:
                def _post() -> None:
                    resp = client.post("/v1/chat", headers=headers, json=payload)
                    statuses.append(resp.status_code)
                    bodies.append(resp.text[:500])

                threads = [threading.Thread(target=_post) for _ in range(2)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(30)
            has_500 = 500 in statuses
            payload_out = {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "id": "K04",
                "phase": "red",
                "status_codes": statuses,
                "bodies": bodies,
                "has_500": has_500,
                "status": "FAIL" if has_500 else "INCOMPLETE",
                "expected": "both 200 same message_id; never 500",
                "notes": [
                    "live L3 also saw 200+500 with RuntimeError agent invocation completion was not persisted"
                ],
            }
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            (EVIDENCE / "before.json").write_text(
                json.dumps(payload_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps({"has_500": has_500, "status_codes": statuses}))
            return 0 if has_500 else 1
        finally:
            core.close()


if __name__ == "__main__":
    raise SystemExit(main())
