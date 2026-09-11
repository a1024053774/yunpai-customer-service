"""K04 green: concurrent same key + same body both 200 and reuse message_id."""
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
    with TemporaryDirectory(prefix="yunpai-k04-green-", dir="/tmp") as raw:
        data_dir = Path(raw)
        settings = make_settings(data_dir)
        core = build_core(data_dir, settings=settings, model=TableDrivenModel(settings))
        try:
            auth = AuthenticationService(core.db, settings)
            app = create_api_app(core, auth=auth)
            key = "k04-same-concurrent-green"
            headers = {
                "X-Client-Id": settings.bootstrap_client_id,
                "X-Client-Key": settings.bootstrap_client_key,
                "X-Subject-Id": "k04-buyer",
                "Idempotency-Key": key,
            }
            payload = {
                "session_id": "k04sess-" + uuid.uuid4().hex[:10],
                "message": "same concurrent kettle question",
            }
            statuses: list[int] = []
            ids: list[str | None] = []
            bodies: list[str] = []
            with TestClient(app, raise_server_exceptions=False) as client:
                def _post() -> None:
                    resp = client.post("/v1/chat", headers=headers, json=payload)
                    statuses.append(resp.status_code)
                    bodies.append(resp.text[:400])
                    try:
                        ids.append(resp.json().get("message_id"))
                    except Exception:
                        ids.append(None)

                threads = [threading.Thread(target=_post) for _ in range(2)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(30)
            unique_ids = {item for item in ids if item}
            ok = statuses == [200, 200] or sorted(statuses) == [200, 200]
            ok = ok and 500 not in statuses and len(unique_ids) == 1
            payload_out = {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "id": "K04",
                "phase": "green",
                "status_codes": statuses,
                "message_ids": ids,
                "same_message_id": len(unique_ids) == 1,
                "has_500": 500 in statuses,
                "status": "PASS" if ok else "FAIL",
                "bodies": bodies,
            }
            (EVIDENCE / "after.json").write_text(
                json.dumps(payload_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps({"ok": ok, "status_codes": statuses, "ids": ids}))
            return 0 if ok else 1
        finally:
            core.close()


if __name__ == "__main__":
    raise SystemExit(main())
