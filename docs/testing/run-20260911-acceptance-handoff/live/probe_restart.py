"""Post-restart session survival + live K05 409. Creds stay in DATA_DIR tmp file."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

RUN = Path("/Users/luckye/Documents/Code/yunpai-customer-service/docs/testing/run-20260911-acceptance-handoff")
RUNTIME = json.loads((RUN / "runtime.json").read_text(encoding="utf-8"))
BEFORE = json.loads((RUN / "runtime-before-restart.json").read_text(encoding="utf-8"))
DEMO = RUNTIME["demo_url"]
API = f"http://{RUNTIME['host_api']['listen']}"
DATA_DIR = Path(RUNTIME["data_dir"])


def main() -> None:
    sessions = httpx.get(f"{DEMO}/api/sessions", timeout=20.0, trust_env=False)
    items = sessions.json().get("items") if sessions.status_code == 200 else []
    survived = any("c01" in (it.get("session_id") or "") or "d01" in (it.get("session_id") or "") for it in items)
    chat = httpx.post(
        f"{DEMO}/api/chat",
        json={"session_id": "c08-restart-" + "abcdefgh", "message": "QA-HO-11SEP26 5L?"},
        timeout=180.0,
        trust_env=False,
    )
    body = chat.json() if chat.headers.get("content-type", "").startswith("application/json") else {}
    creds = json.loads((DATA_DIR / ".host-api-creds.json").read_text(encoding="utf-8"))
    headers = {
        "X-Client-Id": creds["client_id"],
        "X-Client-Key": creds["client_key"],
        "X-Subject-Id": "handoff-buyer-restart",
        "Idempotency-Key": "restart-k05-" + "deadbeef",
    }
    r1 = httpx.post(
        f"{API}/v1/chat",
        json={"session_id": "k05-restart-aaaaaaaa", "message": "first after restart"},
        headers=headers,
        timeout=180.0,
        trust_env=False,
    )
    r2 = httpx.post(
        f"{API}/v1/chat",
        json={"session_id": "k05-restart-aaaaaaaa", "message": "different after restart"},
        headers=headers,
        timeout=60.0,
        trust_env=False,
    )
    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "old_pid": BEFORE.get("pid"),
        "new_pid": RUNTIME.get("pid"),
        "same_data_dir": BEFORE.get("data_dir") == RUNTIME.get("data_dir"),
        "sessions_http": sessions.status_code,
        "session_count": len(items),
        "survived_probe_sessions": survived,
        "c08_chat_status": chat.status_code,
        "c08_used_synthetic": "QA-HO-11SEP26" in json.dumps(body, ensure_ascii=False),
        "k05_first": r1.status_code,
        "k05_conflict": r2.status_code,
        "k05_conflict_preview": r2.text[:300],
        "C08": "PASS" if sessions.status_code == 200 and len(items) >= 1 and chat.status_code == 200 else "INCOMPLETE",
        "K05_live_after_restart": "PASS" if r1.status_code == 200 and r2.status_code == 409 else "FAIL",
    }
    (RUN / "live" / "restart.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("C08", "K05_live_after_restart", "session_count", "k05_first", "k05_conflict", "new_pid")}))


if __name__ == "__main__":
    main()
