"""Live host concurrent K04 after process restart. Does not print secrets."""
from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
DATA_DIR = Path("/private/tmp/yunpai-followup-20260911")
CREDS = DATA_DIR / ".host-api-creds.json"
RUNTIME = EVIDENCE / "runtime.json"


def main() -> int:
    creds = json.loads(CREDS.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    listen = runtime["host_api"]["listen"]
    api = f"http://{listen}"
    headers = {
        "X-Client-Id": creds["client_id"],
        "X-Client-Key": creds["client_key"],
        "X-Subject-Id": "k04-live-green-buyer",
        "Idempotency-Key": "k04-live-green-" + uuid.uuid4().hex,
    }
    payload = {
        "session_id": "k04g-" + uuid.uuid4().hex[:10],
        "message": "QA-FU-11SEP26 5L?",
        "context": {"store_id": "followup-store"},
    }
    out: list[dict] = []

    def _post() -> None:
        resp = httpx.post(f"{api}/v1/chat", json=payload, headers=headers, timeout=180.0, trust_env=False)
        body: dict | str
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:400]
        item = {
            "status": resp.status_code,
            "message_id": body.get("message_id") if isinstance(body, dict) else None,
        }
        if resp.status_code != 200:
            item["body_preview"] = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)[:400]
        out.append(item)

    t1 = threading.Thread(target=_post)
    t2 = threading.Thread(target=_post)
    t1.start()
    t2.start()
    t1.join(180)
    t2.join(180)
    ids = {item.get("message_id") for item in out if item.get("status") == 200}
    ok = len(out) == 2 and all(item["status"] == 200 for item in out) and len(ids) == 1 and 500 not in {
        item["status"] for item in out
    }
    payload_out = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "id": "K04",
        "phase": "live-green-after-restart",
        "host": listen,
        "runtime_pid": runtime.get("pid"),
        "status_codes": [item["status"] for item in out],
        "message_ids": [item.get("message_id") for item in out],
        "same_message_id": len(ids) == 1,
        "has_500": any(item["status"] == 500 for item in out),
        "status": "PASS" if ok else "FAIL",
        "rows": out,
        "notes": [
            "same DATA_DIR; process restarted to load graph.py persist_response fix",
            "does not close crash-recovery or at-most-once graph execution",
        ],
    }
    dest = EVIDENCE / "live" / "k04-after-restart.json"
    dest.write_text(json.dumps(payload_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "status_codes": payload_out["status_codes"], "same_message_id": payload_out["same_message_id"]}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
