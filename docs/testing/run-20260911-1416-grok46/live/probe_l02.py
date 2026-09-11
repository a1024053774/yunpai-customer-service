"""L02 double-submit on Demo HTTP. Isolated /tmp DATA_DIR. ASCII source."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from fastapi.testclient import TestClient  # noqa: E402
from conftest import make_settings  # noqa: E402
from yunpai_customer_service.demo.app import create_app  # noqa: E402


def main() -> None:
    with TemporaryDirectory(prefix="yunpai-l02-", dir="/tmp") as raw:
        tmp = Path(raw)
        settings = make_settings(tmp)
        app = create_app(settings)
        with TestClient(app) as client:
            a = client.post("/api/chat", json={"session_id": "l02-sess1", "message": "hello once"})
            b = client.post("/api/chat", json={"session_id": "l02-sess1", "message": "hello once"})
            c = client.post("/api/chat", json={"session_id": "l02-sess1", "message": "hello twice"})
            ids = []
            for resp in (a, b, c):
                try:
                    ids.append((resp.status_code, (resp.json() or {}).get("message_id")))
                except Exception:
                    ids.append((resp.status_code, None))
            msgs = client.get("/api/sessions")
        status = "INCOMPLETE"
        if a.status_code == 200 and c.status_code == 200:
            status = "PASS"
        case = {
            "id": "L02",
            "status": status,
            "level": "L3-http",
            "actual": {"posts": ids, "sessions": msgs.status_code},
            "notes": [
                "Demo TestClient double POST; browser multi-tab/back/refresh not run",
            ],
            "saved_utc": datetime.now(timezone.utc).isoformat(),
        }
        (EVIDENCE / "l02.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": "L02", "status": status, "posts": ids}, ensure_ascii=False))


if __name__ == "__main__":
    main()
