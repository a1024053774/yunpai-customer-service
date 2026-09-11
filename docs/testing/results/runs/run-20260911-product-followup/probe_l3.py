"""L3 live probes on the frozen followup digest. No secrets in evidence."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx

EVIDENCE = Path(__file__).resolve().parent
LIVE = EVIDENCE / "live"
RUNTIME_PATH = EVIDENCE / "runtime.json"
CREDS_NAME = ".host-api-creds.json"
SECRET_KEY_RE = re.compile(r"(key|secret|token|password|authorization|credential)", re.I)
QUOTA_RE = re.compile(r"quota|rate.?limit|429|insufficient|unauthorized|api.?key", re.I)

PRODUCT = "QA-FU-11SEP26"
COLOR = "\u7c73\u767d"
CAP = "5L"
NO_MW = "\u4e0d\u53ef\u5fae\u6ce2"
RECEIPT = "FU-RCPT-11SEP26"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_B64 = base64.b64encode(PNG).decode("ascii")

results: list[dict] = []
quota_stop = False
cost = {
    "run_id": "run-20260911-product-followup",
    "currency": "unknown",
    "model_calls": 0,
    "http_ms_total": 0,
    "amount": None,
    "note": "provider token/cost fields unknown unless present in response",
    "items": [],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(obj):
    if isinstance(obj, dict):
        return {
            k: "<redacted>" if SECRET_KEY_RE.search(str(k)) else redact(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def save() -> None:
    LIVE.mkdir(parents=True, exist_ok=True)
    (LIVE / "live-results.json").write_text(
        json.dumps(
            {
                "saved_utc": utc_now(),
                "run_id": "run-20260911-product-followup",
                "quota_stop": quota_stop,
                "product": PRODUCT,
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (EVIDENCE / "cost.json").write_text(
        json.dumps(cost, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def record(case: dict) -> None:
    results.append(case)
    save()
    print(json.dumps({"id": case.get("id"), "status": case.get("status"), "http": case.get("status_code")}, ensure_ascii=False), flush=True)


def add_cost(case_id: str, ms: int, kind: str) -> None:
    cost["http_ms_total"] += ms or 0
    if kind == "model":
        cost["model_calls"] += 1
    cost["items"].append({"id": case_id, "ms": ms, "kind": kind})


def lookup(data_dir: Path, message_id: str | None):
    if not message_id:
        return None
    db = data_dir / "agent.sqlite3"
    if not db.is_file():
        return None
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, role, content, intent, risk_level, route_reason, "
            "sources_json, trace_id, model_fallback FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def used_synthetic(body: dict, persisted: dict | None) -> bool:
    blob = json.dumps(body.get("sources") or [], ensure_ascii=False) + " " + (body.get("answer") or "")
    if persisted:
        blob += " " + str(persisted.get("sources_json") or "")
    return PRODUCT in blob or RECEIPT in blob or "synthetic-QA-FU" in blob


def json_or_text(resp: httpx.Response) -> dict:
    ctype = resp.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        try:
            data = resp.json()
            return redact(data) if isinstance(data, dict) else {"value": data}
        except Exception:
            return {"raw": resp.text[:2000]}
    return {"raw": resp.text[:2000]}


def write_fixture() -> Path:
    txt = LIVE / "synthetic-QA-FU-11SEP26.txt"
    body = (
        "\u5b64\u5c9b\u7eed\u6d4b\u7535\u70ed\u6c34\u58f6 \u4ea7\u54c1\u8bf4\u660e\u4e66\uff08\u5408\u6210\u9a8c\u6536\u8d44\u6599\uff0c\u975e\u771f\u5b9e\u5546\u54c1\uff09\n\n"
        f"\u4ea7\u54c1\u578b\u53f7\uff1a{PRODUCT}\n"
        "\u4ea7\u54c1\u540d\u79f0\uff1a\u5b64\u5c9b\u7eed\u6d4b\u7535\u70ed\u6c34\u58f6\n"
        f"\u989c\u8272\uff1a{COLOR}\n"
        f"\u5bb9\u91cf\uff1a{CAP}\n"
        "\u6d4b\u8bd5\u6807\u4ef7\uff1a329 \u5143\n"
        "\u4fdd\u4fee\uff1a\u6574\u673a\u4fdd\u4fee 12 \u4e2a\u6708\u3002\n\n"
        f"\u52a0\u70ed\u4e0e\u4f7f\u7528\u9650\u5236\uff1a\u672c\u4ea7\u54c1{NO_MW}\u3002\n\n"
        "\u9000\u6b3e\u4e0e\u9000\u8d27\uff08\u54a8\u8be2\u8bf4\u660e\uff0c\u667a\u80fd\u5ba2\u670d\u4e0d\u5f97\u4ee3\u4e3a\u6267\u884c\u9000\u6b3e\uff09\uff1a\n"
        "\u82e5\u4ee5\u540e\u7533\u8bf7\u9000\u6b3e\uff0c\u987b\u540c\u65f6\u6ee1\u8db3\uff1a\u5546\u54c1\u672a\u4f7f\u7528\u3001\u5305\u88c5\u5b8c\u597d\u3001\u7b7e\u6536\u540e 7 \u65e5\u5185\u63d0\u51fa\u3002\n"
        f"\u9700\u8981\u6750\u6599\uff1a1\uff09\u8ba2\u5355\u53f7\uff1b2\uff09\u672a\u62c6\u5c01\u5916\u7bb1\u7167\u7247\uff1b3\uff09\u6838\u9a8c\u7801 {RECEIPT}\u3002\n"
        "\u5ba2\u670d\u53ea\u80fd\u8bf4\u660e\u6761\u4ef6\uff0c\u4e0d\u80fd\u76f4\u63a5\u7ed9\u8ba2\u5355\u9000\u6b3e\uff0c\u4e5f\u4e0d\u80fd\u628a\u8d44\u91d1\u72b6\u6001\u6539\u6210\u5df2\u9000\u6b3e\u3002\n"
        "\u672c\u8d44\u6599\u4e0d\u8bb0\u8f7d\u5e93\u5b58\u3001\u9500\u91cf\u6216\u5230\u8d26\u65f6\u95f4\u3002\n"
    )
    txt.write_text(body, encoding="utf-8")
    return txt


def insert_second_client(data_dir: Path, client_id: str, key: str, tenant_id: str) -> None:
    db = data_dir / "agent.sqlite3"
    salt = os.urandom(16)
    key_hash = hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt, 210_000)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO api_clients(
                id, tenant_id, name, key_salt, key_hash, key_iterations,
                can_supply_order_context, status, created_at, updated_at, role
            ) VALUES (?, ?, ?, ?, ?, 210000, 0, 'active', ?, ?, 'client')
            ON CONFLICT(id) DO UPDATE SET
                key_salt=excluded.key_salt,
                key_hash=excluded.key_hash,
                key_iterations=excluded.key_iterations,
                status='active',
                updated_at=excluded.updated_at
            """,
            (client_id, tenant_id, "followup-second-client", salt, key_hash, now, now),
        )
        conn.commit()


def collect_fields(body: dict) -> dict:
    return {
        "has_answer": bool(body.get("answer")),
        "intent": body.get("intent"),
        "customer_intent": body.get("customer_intent"),
        "risk_level": body.get("risk_level"),
        "requires_human": body.get("requires_human"),
        "source_count": len(body.get("sources") or []),
        "mentions_product": PRODUCT in str(body.get("answer") or ""),
        "mentions_color": COLOR in str(body.get("answer") or ""),
        "mentions_cap": CAP in str(body.get("answer") or ""),
        "message_id_present": bool(body.get("message_id")),
    }


def read_sse(url: str, headers: dict, payload: dict, timeout: float = 180.0) -> tuple[int, list[dict], dict | None, int]:
    started = time.monotonic()
    frames: list[dict] = []
    final = None
    status = None
    with httpx.stream("POST", url, headers=headers, json=payload, timeout=timeout, trust_env=False) as resp:
        status = resp.status_code
        if status != 200:
            return status, [], {"raw": resp.read().decode("utf-8", "replace")[:400]}, round((time.monotonic() - started) * 1000)
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:]
            try:
                event = json.loads(raw)
            except Exception:
                frames.append({"raw": raw[:200]})
                continue
            frames.append({"event": event.get("event"), "keys": sorted(event.keys())[:12]})
            if event.get("event") == "result" and isinstance(event.get("response"), dict):
                final = event["response"]
            if event.get("event") == "result":
                break
    return status, frames, redact(final) if isinstance(final, dict) else final, round((time.monotonic() - started) * 1000)


def main() -> None:
    global quota_stop
    runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    demo = runtime["demo_url"]
    data_dir = Path(runtime["data_dir"])
    api = f"http://{runtime['host_api']['listen']}"
    creds = json.loads((data_dir / CREDS_NAME).read_text(encoding="utf-8"))
    headers = {
        "X-Client-Id": creds["client_id"],
        "X-Client-Key": creds["client_key"],
        "X-Subject-Id": "followup-buyer-1",
    }
    health = httpx.get(f"{demo}/api/health", timeout=30.0, trust_env=False)
    health_body = redact(health.json())
    (LIVE / "health-demo.json").write_text(json.dumps(health_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    api_health = httpx.get(f"{api}/v1/health", timeout=30.0, trust_env=False)
    (LIVE / "health-host.json").write_text(json.dumps(redact(api_health.json()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record(
        {
            "id": "L05-health",
            "level": "L3",
            "status": "PASS" if health_body.get("ok") and health_body.get("model_mode") == "live" else "FAIL",
            "demo": health_body,
            "host_ok": api_health.status_code == 200,
            "notes": ["health labels only; not full L05"],
        }
    )
    if health_body.get("model_mode") != "live":
        record({"id": "LIVE-GATE", "status": "BLOCKED", "notes": ["model_mode is not live"]})
        return

    txt = write_fixture()
    with txt.open("rb") as fh:
        imported = httpx.post(
            f"{demo}/api/knowledge/import",
            files={"file": (txt.name, fh, "text/plain")},
            data={"intent": "after_sales"},
            timeout=120.0,
            trust_env=False,
        )
    import_body = imported.json()
    (LIVE / "import-txt.json").write_text(json.dumps(import_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record(
        {
            "id": "E-import-txt",
            "status": "PASS" if imported.status_code == 200 and import_body.get("count") else "FAIL",
            "status_code": imported.status_code,
            "count": import_body.get("count"),
        }
    )

    unauth = httpx.post(f"{api}/v1/chat", json={"session_id": "i01-unauth", "message": "ping"}, timeout=20.0, trust_env=False)
    wrong = httpx.post(
        f"{api}/v1/chat",
        headers={"X-Client-Id": creds["client_id"], "X-Client-Key": "definitely-wrong-key-000000", "X-Subject-Id": "x"},
        json={"session_id": "i01-wrong", "message": "ping"},
        timeout=20.0,
        trust_env=False,
    )
    missing_subject = httpx.post(
        f"{api}/v1/chat",
        headers={"X-Client-Id": creds["client_id"], "X-Client-Key": creds["client_key"]},
        json={"session_id": "i01-nosub", "message": "ping"},
        timeout=20.0,
        trust_env=False,
    )
    i01_ok = unauth.status_code == 401 and wrong.status_code == 401 and missing_subject.status_code == 401
    record(
        {
            "id": "I01",
            "level": "L3",
            "status": "PASS" if i01_ok else "FAIL",
            "unauth": unauth.status_code,
            "wrong_key": wrong.status_code,
            "missing_subject": missing_subject.status_code,
            "notes": ["expired/disabled client keys not matrixed this run"],
        }
    )

    bad_host = httpx.get(f"{demo}/api/health", headers={"Host": "example.com", "X-Forwarded-For": "8.8.8.8"}, timeout=20.0, trust_env=False)
    forwarded = httpx.get(f"{demo}/api/health", headers={"X-Forwarded-Host": "evil.example", "Forwarded": "for=8.8.8.8"}, timeout=20.0, trust_env=False)
    origin = httpx.get(f"{demo}/api/health", headers={"Origin": "https://evil.example"}, timeout=20.0, trust_env=False)
    local_ok = httpx.get(f"{demo}/api/health", timeout=20.0, trust_env=False)
    header_ok = (
        bad_host.status_code == 403
        and forwarded.status_code == 403
        and origin.status_code == 403
        and local_ok.status_code == 200
    )
    record(
        {
            "id": "I08",
            "level": "L3-header-only",
            "status": "INCOMPLETE" if header_ok else "FAIL",
            "bad_host": bad_host.status_code,
            "forwarded": forwarded.status_code,
            "origin": origin.status_code,
            "local": local_ok.status_code,
            "notes": [
                "header construction only; not a real reverse proxy",
                "handbook I08 requires actual proxy path; N03 remains BLOCKED",
            ],
        }
    )

    k11_empty = httpx.post(f"{api}/v1/chat", headers=headers, json={"session_id": "k11liveempty", "message": ""}, timeout=20.0, trust_env=False)
    k11_plain = httpx.post(
        f"{api}/v1/chat",
        headers={**headers, "Content-Type": "text/plain"},
        content="not-json",
        timeout=20.0,
        trust_env=False,
    )
    k11_bad = httpx.post(
        f"{api}/v1/chat/stream",
        headers={**headers, "Content-Type": "application/json"},
        content="{",
        timeout=20.0,
        trust_env=False,
    )
    record(
        {
            "id": "K11-live-host",
            "level": "L3",
            "status": "PASS" if {k11_empty.status_code, k11_plain.status_code, k11_bad.status_code} <= {400, 415, 422} else "FAIL",
            "empty": k11_empty.status_code,
            "plain": k11_plain.status_code,
            "malformed_stream": k11_bad.status_code,
            "notes": ["live socket schema; complements L1 K11"],
        }
    )

    q = f"{PRODUCT} \u989c\u8272\u548c\u5bb9\u91cf\uff1f"
    demo_sid = "k01d-" + uuid.uuid4().hex[:10]
    host_sid = "k01h-" + uuid.uuid4().hex[:10]
    t0 = time.monotonic()
    demo_sync = httpx.post(f"{demo}/api/chat", json={"session_id": demo_sid, "message": q}, timeout=180.0, trust_env=False)
    d_ms = round((time.monotonic() - t0) * 1000)
    add_cost("K01-demo-sync", d_ms, "model")
    demo_body = json_or_text(demo_sync)
    t0 = time.monotonic()
    host_sync = httpx.post(
        f"{api}/v1/chat",
        headers=headers,
        json={"session_id": host_sid, "message": q, "context": {"store_id": "followup-store"}},
        timeout=180.0,
        trust_env=False,
    )
    h_ms = round((time.monotonic() - t0) * 1000)
    add_cost("K01-host-sync", h_ms, "model")
    host_body = json_or_text(host_sync)
    demo_sse_status, demo_frames, demo_final, demo_sse_ms = read_sse(
        f"{demo}/api/chat/stream",
        {},
        {"session_id": "k01ds-" + uuid.uuid4().hex[:10], "message": q},
    )
    add_cost("K01-demo-sse", demo_sse_ms, "model")
    host_sse_status, host_frames, host_final, host_sse_ms = read_sse(
        f"{api}/v1/chat/stream",
        headers,
        {"session_id": "k01hs-" + uuid.uuid4().hex[:10], "message": q, "context": {"store_id": "followup-store"}},
    )
    add_cost("K01-host-sse", host_sse_ms, "model")
    fields = {
        "demo_sync": collect_fields(demo_body),
        "host_sync": collect_fields(host_body),
        "demo_sse": collect_fields(demo_final or {}),
        "host_sse": collect_fields(host_final or {}),
    }
    facts_ok = all(
        item.get("mentions_color") and item.get("mentions_cap")
        for item in fields.values()
        if item.get("has_answer")
    )
    all_http_ok = demo_sync.status_code == 200 and host_sync.status_code == 200 and demo_sse_status == 200 and host_sse_status == 200
    leaked = any("password" in json.dumps(frames).lower() or "\u94f6\u884c\u5361" in json.dumps(frames) for frames in (demo_frames, host_frames))
    record(
        {
            "id": "K01-host-demo-http",
            "level": "L3",
            "status": "PASS" if all_http_ok and facts_ok and not leaked else "INCOMPLETE",
            "demo_sync": demo_sync.status_code,
            "host_sync": host_sync.status_code,
            "demo_sse": demo_sse_status,
            "host_sse": host_sse_status,
            "fields": fields,
            "demo_sse_events": [f.get("event") for f in demo_frames],
            "host_sse_events": [f.get("event") for f in host_frames],
            "notes": [
                "in-process core not invoked on this DATA_DIR; handbook K01 still incomplete without core",
                "compared color/capacity/sources presence; IDs may differ",
            ],
        }
    )
    record(
        {
            "id": "K01-sse",
            "level": "L3",
            "status": "INCOMPLETE",
            "demo_frame_events": [f.get("event") for f in demo_frames],
            "host_frame_events": [f.get("event") for f in host_frames],
            "leaked_unverified_draft": leaked,
            "notes": [
                "handbook K01 requires core+Demo+host sync+SSE field compare",
                "this card is SSE frames only and must not close K01",
            ],
        }
    )

    if quota_stop:
        return

    b01_sid = "b01-" + uuid.uuid4().hex[:10]
    t0 = time.monotonic()
    b01 = httpx.post(
        f"{demo}/api/chat",
        json={"session_id": b01_sid, "message": "\u5982\u679c\u4ee5\u540e\u7533\u8bf7\u9000\u6b3e\uff0c\u9700\u8981\u4ec0\u4e48\u6750\u6599\uff1f"},
        timeout=180.0,
        trust_env=False,
    )
    add_cost("B01", round((time.monotonic() - t0) * 1000), "model")
    b01_body = json_or_text(b01)
    ans = str(b01_body.get("answer") or "")
    claimed = "\u5df2\u9000\u6b3e" in ans or "already refund" in ans.lower()
    explains = RECEIPT in ans and ("\u8ba2\u5355\u53f7" in ans or "\u8ba2\u5355" in ans) and ("7" in ans)
    synth = used_synthetic(b01_body, lookup(data_dir, b01_body.get("message_id")))
    if claimed:
        b01_status = "FAIL"
    elif explains and synth:
        b01_status = "PASS"
    else:
        b01_status = "INCOMPLETE"
    record(
        {
            "id": "B01",
            "level": "L3",
            "status": b01_status,
            "status_code": b01.status_code,
            "answer": ans,
            "used_synthetic": synth,
            "sources": b01_body.get("sources"),
            "requires_human": b01_body.get("requires_human"),
            "notes": ["independent this-run; 1739 PASS not inherited", "must cite synthetic refund materials"],
        }
    )

    c01_sid = "c01-" + uuid.uuid4().hex[:10]
    t0 = time.monotonic()
    c1 = httpx.post(f"{demo}/api/chat", json={"session_id": c01_sid, "message": f"{PRODUCT} \u662f\u4ec0\u4e48\u989c\u8272\u548c\u5bb9\u91cf\uff1f"}, timeout=180.0, trust_env=False)
    add_cost("C01-turn1", round((time.monotonic() - t0) * 1000), "model")
    t0 = time.monotonic()
    c2 = httpx.post(f"{demo}/api/chat", json={"session_id": c01_sid, "message": "\u8fd9\u4e2a\u989c\u8272\u786e\u8ba4\u4e00\u4e0b"}, timeout=180.0, trust_env=False)
    add_cost("C01-turn2", round((time.monotonic() - t0) * 1000), "model")
    c1b = json_or_text(c1)
    c2b = json_or_text(c2)
    ans2 = str(c2b.get("answer") or "")
    asked_which = ("\u54ea\u6b3e" in ans2) or ("\u54ea\u4e2a\u5546\u54c1" in ans2)
    c01_ok = c1.status_code == 200 and c2.status_code == 200 and COLOR in ans2 and CAP in ans2 and not asked_which
    record(
        {
            "id": "C01",
            "level": "L3",
            "status": "PASS" if c01_ok else "FAIL",
            "first_status": c1.status_code,
            "second_status": c2.status_code,
            "first_answer": c1b.get("answer"),
            "second_answer": ans2,
            "asked_which_product": asked_which,
            "used_synthetic": used_synthetic(c2b, lookup(data_dir, c2b.get("message_id"))),
            "notes": ["re-probe on digest 801e8ae1; historical REVIEW_PASS files kept"],
        }
    )

    idem = "idem-" + uuid.uuid4().hex
    k04_payload = {"session_id": "k04-" + uuid.uuid4().hex[:10], "message": f"{PRODUCT} {COLOR}\uff1f", "context": {"store_id": "followup-store"}}
    r1 = httpx.post(f"{api}/v1/chat", json=k04_payload, headers={**headers, "Idempotency-Key": idem}, timeout=180.0, trust_env=False)
    add_cost("K04-first", 0, "model")
    r2 = httpx.post(f"{api}/v1/chat", json=k04_payload, headers={**headers, "Idempotency-Key": idem}, timeout=180.0, trust_env=False)
    b1 = json_or_text(r1)
    b2 = json_or_text(r2)
    same = b1.get("message_id") and b1.get("message_id") == b2.get("message_id")
    sse_status, sse_frames, sse_final, sse_ms = read_sse(
        f"{api}/v1/chat/stream",
        {**headers, "Idempotency-Key": idem},
        k04_payload,
    )
    add_cost("K04-sse-replay", sse_ms, "model")
    sse_same = bool(sse_final and sse_final.get("message_id") == b1.get("message_id"))
    conc_key = "k04c-" + uuid.uuid4().hex
    conc_payload = {"session_id": "k04c-" + uuid.uuid4().hex[:10], "message": f"{PRODUCT} {CAP}\uff1f", "context": {"store_id": "followup-store"}}
    conc: list[dict] = []

    def _same() -> None:
        rr = httpx.post(f"{api}/v1/chat", json=conc_payload, headers={**headers, "Idempotency-Key": conc_key}, timeout=180.0, trust_env=False)
        conc.append({"status": rr.status_code, "message_id": json_or_text(rr).get("message_id")})

    t1 = threading.Thread(target=_same)
    t2 = threading.Thread(target=_same)
    t1.start()
    t2.start()
    t1.join(180)
    t2.join(180)
    ids = {item.get("message_id") for item in conc if item.get("status") == 200}
    conc_ok = len(conc) == 2 and all(item["status"] == 200 for item in conc) and len(ids) == 1
    record(
        {
            "id": "K04",
            "level": "L3",
            "status": "PASS" if r1.status_code == 200 and same and sse_same and conc_ok else "INCOMPLETE",
            "first": r1.status_code,
            "replay": r2.status_code,
            "same_message_id": same,
            "sse_replay_status": sse_status,
            "sse_same_message_id": sse_same,
            "concurrent": conc,
            "notes": ["host sync replay + SSE cross replay + concurrent same body", "process restart not this run"],
        }
    )

    k05_key = "k05l-" + uuid.uuid4().hex
    k05_session = "k05l-" + uuid.uuid4().hex[:10]
    k05_msg = {"session_id": k05_session, "message": f"{PRODUCT} {COLOR}\uff1f", "context": {"store_id": "store-a"}}
    first = httpx.post(f"{api}/v1/chat", json=k05_msg, headers={**headers, "Idempotency-Key": k05_key}, timeout=180.0, trust_env=False)
    add_cost("K05-live-first", 0, "model")
    first_body = json_or_text(first)

    def conflict(name: str, payload: dict, hdrs: dict) -> dict:
        resp = httpx.post(f"{api}/v1/chat", json=payload, headers=hdrs, timeout=60.0, trust_env=False)
        body = json_or_text(resp)
        code = None
        if isinstance(body.get("detail"), dict):
            code = body["detail"].get("code")
        ok = resp.status_code == 409 and not body.get("answer")
        return {
            "factor": name,
            "status_code": resp.status_code,
            "detail_code": code,
            "has_answer": bool(body.get("answer")),
            "status": "PASS" if ok else "FAIL",
            "body_preview": resp.text[:300],
        }

    k05_rows = [
        {
            "factor": "live_first",
            "status_code": first.status_code,
            "status": "PASS" if first.status_code == 200 else "FAIL",
        },
        conflict("different_message", {**k05_msg, "message": "different " + uuid.uuid4().hex}, {**headers, "Idempotency-Key": k05_key}),
        conflict("different_store_id", {**k05_msg, "context": {"store_id": "store-b"}}, {**headers, "Idempotency-Key": k05_key}),
        conflict(
            "add_image",
            {**k05_msg, "image": {"mime_type": "image/png", "data_base64": PNG_B64}},
            {**headers, "Idempotency-Key": k05_key},
        ),
        conflict(
            "different_subject_same_session",
            k05_msg,
            {**headers, "Idempotency-Key": k05_key, "X-Subject-Id": "followup-buyer-other"},
        ),
    ]
    second_id = "followup-l3-client-2"
    second_key = uuid.uuid4().hex + uuid.uuid4().hex
    try:
        insert_second_client(data_dir, second_id, second_key, creds["tenant_id"])
        h2 = {"X-Client-Id": second_id, "X-Client-Key": second_key, "X-Subject-Id": "followup-buyer-2"}
        c2 = httpx.post(
            f"{api}/v1/chat",
            json={"session_id": "k05c2-" + uuid.uuid4().hex[:10], "message": k05_msg["message"], "context": {"store_id": "store-a"}},
            headers={**h2, "Idempotency-Key": k05_key},
            timeout=180.0,
            trust_env=False,
        )
        add_cost("K05-second-client", 0, "model")
        c2b = json_or_text(c2)
        isolated = c2.status_code == 200 and c2b.get("message_id") and c2b.get("message_id") != first_body.get("message_id")
        k05_rows.append(
            {
                "factor": "second_host_client",
                "status_code": c2.status_code,
                "isolated": bool(isolated),
                "status": "PASS" if isolated else "FAIL",
                "body_preview": c2.text[:200],
            }
        )
        (data_dir / ".host-api-creds-2.json").write_text(
            json.dumps({"client_id": second_id, "tenant_id": creds["tenant_id"], "note": "key kept in DATA_DIR only"}) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        k05_rows.append({"factor": "second_host_client", "status": "INCOMPLETE", "error": f"{type(exc).__name__}: {exc}"})

    mid_key = "k05m-" + uuid.uuid4().hex
    mid_session = "k05m-" + uuid.uuid4().hex[:10]
    mid_payload = {"session_id": mid_session, "message": f"{PRODUCT} {CAP}\uff1f", "context": {"store_id": "store-a"}}
    started = threading.Event()
    frames_n = {"n": 0}

    def _stream() -> None:
        try:
            with httpx.stream(
                "POST",
                f"{api}/v1/chat/stream",
                headers={**headers, "Idempotency-Key": mid_key},
                json=mid_payload,
                timeout=180.0,
                trust_env=False,
            ) as resp:
                started.set()
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        frames_n["n"] += 1
                        break
        except Exception:
            started.set()

    th = threading.Thread(target=_stream)
    th.start()
    started.wait(30)
    time.sleep(0.2)
    mid = httpx.post(
        f"{api}/v1/chat",
        json={**mid_payload, "message": "different mid " + uuid.uuid4().hex},
        headers={**headers, "Idempotency-Key": mid_key},
        timeout=30.0,
        trust_env=False,
    )
    th.join(180)
    add_cost("K05-mid-sse", 0, "model")
    mid_body = json_or_text(mid)
    mid_code = (mid_body.get("detail") or {}).get("code") if isinstance(mid_body.get("detail"), dict) else None
    k05_rows.append(
        {
            "factor": "mid_sse_second_client_request",
            "frames": frames_n["n"],
            "status_code": mid.status_code,
            "detail_code": mid_code,
            "status": "PASS" if mid.status_code == 409 else "INCOMPLETE",
            "body_preview": mid.text[:300],
        }
    )
    conc_k = "k05x-" + uuid.uuid4().hex
    conc_s = "k05x-" + uuid.uuid4().hex[:10]
    conc_out: list[int] = []

    def _diff(msg: str) -> None:
        rr = httpx.post(
            f"{api}/v1/chat",
            json={"session_id": conc_s, "message": msg, "context": {"store_id": "store-a"}},
            headers={**headers, "Idempotency-Key": conc_k},
            timeout=180.0,
            trust_env=False,
        )
        conc_out.append(rr.status_code)

    u1 = threading.Thread(target=_diff, args=("conc-one " + uuid.uuid4().hex,))
    u2 = threading.Thread(target=_diff, args=("conc-two " + uuid.uuid4().hex,))
    u1.start()
    u2.start()
    u1.join(180)
    u2.join(180)
    add_cost("K05-concurrent", 0, "model")
    conc_ok = sorted(conc_out) in ([200, 409], [409, 200], [409, 409]) and conc_out.count(200) <= 1
    k05_rows.append({"factor": "concurrent_different_messages", "status_codes": conc_out, "status": "PASS" if conc_ok else "FAIL"})
    failed = [r for r in k05_rows if r.get("status") == "FAIL"]
    incomplete = [r for r in k05_rows if r.get("status") == "INCOMPLETE"]
    k05_status = "FAIL" if failed else ("INCOMPLETE" if incomplete else "PASS")
    record(
        {
            "id": "K05-live-factors",
            "level": "L3",
            "status": k05_status,
            "handbook_k05_claim": False,
            "rows": k05_rows,
            "notes": [
                "live host factors; table-model L1 also exists",
                "do not promote handbook K05 to PASS unless all factors and core digest are closed",
            ],
        }
    )

    fb_sid = "fb-" + uuid.uuid4().hex[:10]
    t0 = time.monotonic()
    chat = httpx.post(f"{demo}/api/chat", json={"session_id": fb_sid, "message": f"{PRODUCT} {CAP}\uff1f"}, timeout=180.0, trust_env=False)
    add_cost("L04-seed-chat", round((time.monotonic() - t0) * 1000), "model")
    chat_body = json_or_text(chat)
    mid = chat_body.get("message_id")
    if mid:
        fb = httpx.post(
            f"{demo}/api/feedback",
            json={
                "message_id": mid,
                "rating": -1,
                "corrected_answer": f"{PRODUCT} {COLOR} {CAP} {NO_MW} {RECEIPT}",
                "evidence_source": "upload://synthetic-QA-FU-11SEP26.txt",
                "submitted_by": "followup-qa",
            },
            timeout=60.0,
            trust_env=False,
        )
        fb_body = json_or_text(fb)
        (LIVE / "l04-seed-candidate.json").write_text(json.dumps(redact(fb_body), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        record(
            {
                "id": "L04-seed-candidate",
                "status": "PASS" if fb.status_code == 200 and (fb_body.get("candidate_id") or fb_body.get("id")) else "INCOMPLETE",
                "status_code": fb.status_code,
                "candidate_id": fb_body.get("candidate_id") or fb_body.get("id"),
                "notes": ["HTTP seed only; L04 requires browser evaluate/approve/rollback"],
            }
        )


if __name__ == "__main__":
    main()
