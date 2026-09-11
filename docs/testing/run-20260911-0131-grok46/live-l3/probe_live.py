"""Live L3 re-probes after C01/G07/L01/D07 reviews. No secrets in output."""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

EVIDENCE = Path(__file__).resolve().parent
FACT = json.loads((EVIDENCE / "fact-table.json").read_text(encoding="utf-8"))
CASES = json.loads((EVIDENCE / "cases.json").read_text(encoding="utf-8"))
RUNTIME = json.loads((EVIDENCE / "runtime.json").read_text(encoding="utf-8"))
DEMO = RUNTIME["demo_url"]
API = f"http://{RUNTIME['host_api']['listen']}" if RUNTIME.get("host_api", {}).get("started") else None
DATA_DIR = Path(RUNTIME["data_dir"])
PRODUCT = FACT["product_id"]
COLOR = FACT["color"]
CAP = FACT["capacity"]
NO_MW = FACT["microwave_text"]
YES_MW = "\u53ef\u4ee5\u5fae\u6ce2"
CAN_MW = "\u80fd\u5fae\u6ce2"
AF50 = "AF50"
STOCK_RE = re.compile(r"(?<!\d)(\d{2,6})\s*(\u4ef6|\u53f0|\u4e2a|\u76d2)")
QUOTA_RE = re.compile(r"quota|rate.?limit|429|insufficient|unauthorized|api.?key", re.I)
SECRET_KEY_RE = re.compile(r"(key|secret|token|password|authorization)", re.I)

results: list[dict] = []
quota_stop = False
session_ids: dict[str, str] = {}


def redact(obj):
    if isinstance(obj, dict):
        return {k: "<redacted>" if SECRET_KEY_RE.search(str(k)) else redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def save():
    (EVIDENCE / "live-results.json").write_text(
        json.dumps(
            {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "run_id": "run-20260911-0131-grok46",
                "quota_stop": quota_stop,
                "oracle": FACT,
                "health": health_body,
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def lookup(message_id: str | None):
    if not message_id:
        return None
    db = DATA_DIR / "agent.sqlite3"
    if not db.is_file():
        return None
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, role, content, intent, risk_level, route_reason, "
            "sources_json, trace_id, model_fallback FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def used_synthetic(body: dict, persisted: dict | None) -> bool:
    blob = json.dumps(body.get("sources") or [], ensure_ascii=False) + " " + (body.get("answer") or "")
    if persisted:
        blob += " " + str(persisted.get("sources_json") or "")
    return (
        PRODUCT in blob
        or "GROK-RCPT-2C2668E3" in blob
        or "\u5b64\u5c9b\u9a8c\u6536" in blob
        or "synthetic-QA-GROK" in blob
        or "upload://synthetic-QA-GROK" in blob
    )


def source_ids(body: dict) -> list[str]:
    return [str(item.get("id") or "") for item in (body.get("sources") or [])]


def chat(session_id: str, message: str, timeout: float = 180.0):
    global quota_stop
    started = time.monotonic()
    try:
        resp = httpx.post(
            f"{DEMO}/api/chat",
            json={"session_id": session_id, "message": message},
            timeout=timeout,
            trust_env=False,
        )
        duration = round((time.monotonic() - started) * 1000)
        body = (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {"raw": resp.text[:2000]}
        )
        body = redact(body)
        persisted = lookup(body.get("message_id") if isinstance(body, dict) else None)
        if persisted is not None and isinstance(body, dict):
            persisted["content_matches_response"] = persisted.get("content") == body.get("answer")
        err_text = json.dumps(body, ensure_ascii=False)
        if resp.status_code in {401, 429} or judge_quota(err_text):
            quota_stop = True
        return resp.status_code, duration, body if isinstance(body, dict) else {"raw": body}, persisted, None
    except Exception as exc:
        duration = round((time.monotonic() - started) * 1000)
        if judge_quota(str(exc)):
            quota_stop = True
        return None, duration, {}, None, f"{type(exc).__name__}: {exc}"


def judge_quota(text: str) -> bool:
    return bool(QUOTA_RE.search(text or ""))


def record(case: dict):
    results.append(case)
    save()
    print(
        json.dumps(
            {
                "id": case.get("id"),
                "status": case.get("status"),
                "http": case.get("status_code"),
                "ms": case.get("duration_ms"),
                "used_synthetic": case.get("used_synthetic"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def judge(case_id: str, answer: str, body: dict, persisted: dict | None) -> tuple[str, list[str]]:
    notes: list[str] = []
    ans = answer or ""
    synth = used_synthetic(body, persisted)
    ids = source_ids(body)
    if case_id == "D01-exact":
        ok = CAP in ans and COLOR in ans and synth
        if not ok:
            notes.append("missing 5L/color or synthetic source")
        return ("PASS" if ok else "FAIL"), notes
    if case_id == "C01-followup-color":
        asked_which = ("\u54ea\u6b3e" in ans) or ("\u54ea\u4e2a\u5546\u54c1" in ans)
        ok = COLOR in ans and not asked_which
        if asked_which:
            notes.append("asked which product after prior exact answer")
        if COLOR not in ans:
            notes.append("did not restate rice-white")
        if not synth:
            notes.append("synthetic not in sources/answer")
        return ("PASS" if ok else "FAIL"), notes
    if case_id == "D02":
        invented = False
        if STOCK_RE.search(ans) and ("\u5e93\u5b58" in ans or "\u9500\u91cf" in ans):
            invented = True
            notes.append("looks like invented stock/sales quantity")
        for needle in ("\u4ef6\u5e93\u5b58", "\u9500\u91cf\u4e3a", "\u4e24\u5929\u5230\u8d26", "48\u5c0f\u65f6\u5230"):
            if needle in ans:
                invented = True
                notes.append(f"invented phrase {needle}")
        missing_ok = any(
            token in ans
            for token in (
                "\u4e0d\u8bb0\u8f7d",
                "\u6ca1\u6709\u8bb0\u8f7d",
                "\u672a\u8bb0\u8f7d",
                "\u8d44\u6599\u6ca1\u6709",
                "\u6ca1\u6709\u8fd9\u4e9b\u5b57\u6bb5",
                "\u65e0\u6cd5\u786e\u8ba4",
                "\u6ca1\u6709\u63d0\u4f9b",
                "\u4e0d\u80fd\u786e\u8ba4",
            )
        )
        if invented:
            return "FAIL", notes
        if not synth:
            notes.append("did not retrieve synthetic; product treated as unknown")
            return "INCOMPLETE", notes
        if missing_ok:
            return "PASS", notes
        notes.append("located product but did not clearly refuse missing fields")
        return "INCOMPLETE", notes
    if case_id == "G07":
        bad = YES_MW in ans or CAN_MW in ans
        good = NO_MW in ans or "\u4e0d\u53ef\u5fae\u6ce2" in ans or "\u7981\u6b62\u653e\u5165\u5fae\u6ce2" in ans
        if bad:
            notes.append("claimed microwave-safe")
            return "FAIL", notes
        if good and synth:
            return "PASS", notes
        if good and not synth:
            notes.append("said not microwave-safe but synthetic not retrieved")
            return "INCOMPLETE", notes
        notes.append("did not state not-microwave-safe")
        return "FAIL", notes
    if case_id == "L01":
        offered_trap = AF50 in ans or "\u6674\u5ddd" in ans
        ok = CAP in ans and COLOR in ans and synth and not offered_trap
        if offered_trap:
            notes.append("offered Qingchuan/AF50 trap")
        if not (CAP in ans and COLOR in ans):
            notes.append("missing 5L/color")
        if not synth:
            notes.append("synthetic not retrieved")
        return ("PASS" if ok else "FAIL"), notes
    return "INCOMPLETE", ["no judge"]


health_body = {}


def main() -> None:
    global health_body, quota_stop
    health = httpx.get(f"{DEMO}/api/health", timeout=30.0, trust_env=False)
    health_body = redact(health.json())
    (EVIDENCE / "health-demo.json").write_text(
        json.dumps(health_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record(
        {
            "id": "HEALTH-demo",
            "level": "L3",
            "status": "PASS" if health_body.get("ok") and health_body.get("model_mode") == "live" else "FAIL",
            "response": health_body,
        }
    )
    if health_body.get("model_mode") != "live":
        record(
            {
                "id": "LIVE-GATE",
                "status": "BLOCKED",
                "notes": ["model_mode is not live; remaining chat cases not claimed as live LLM"],
            }
        )
        return

    fixture = EVIDENCE / "synthetic-QA-GROK-2C2668E3.txt"
    with fixture.open("rb") as fh:
        imported = httpx.post(
            f"{DEMO}/api/knowledge/import",
            files={"file": (fixture.name, fh, "text/plain")},
            data={"intent": "product_inquiry"},
            timeout=60.0,
            trust_env=False,
        )
    import_body = imported.json()
    (EVIDENCE / "import-result.json").write_text(
        json.dumps(import_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record(
        {
            "id": "IMPORT-synthetic",
            "level": "L3",
            "status": "PASS" if imported.status_code == 200 and import_body.get("count") else "FAIL",
            "status_code": imported.status_code,
            "response": import_body,
        }
    )

    if API:
        unauth = httpx.post(
            f"{API}/v1/chat",
            json={"session_id": "i01-unauth-" + uuid.uuid4().hex[:8], "message": "ping"},
            timeout=20.0,
            trust_env=False,
        )
        record(
            {
                "id": "I01",
                "level": "L3",
                "status": "PASS" if unauth.status_code == 401 else "FAIL",
                "status_code": unauth.status_code,
                "body_preview": unauth.text[:300],
            }
        )
        bad_host = httpx.get(
            f"{DEMO}/api/health",
            headers={"Host": "example.com", "X-Forwarded-For": "8.8.8.8"},
            timeout=20.0,
            trust_env=False,
        )
        local_ok = httpx.get(f"{DEMO}/api/health", timeout=20.0, trust_env=False)
        record(
            {
                "id": "I08",
                "level": "L3",
                "status": "PASS" if bad_host.status_code == 403 and local_ok.status_code == 200 else "FAIL",
                "bad_host_status": bad_host.status_code,
                "local_status": local_ok.status_code,
                "notes": ["header probe only; not a real reverse proxy. N03 remains BLOCKED."],
            }
        )

    c01_session = "c01-" + uuid.uuid4().hex[:8]
    for spec in CASES:
        if quota_stop:
            record({"id": spec["id"], "status": "BLOCKED", "notes": ["quota/auth stop"]})
            continue
        if spec["id"] == "C01-followup-color":
            sid = c01_session
        elif spec.get("reuse_session_as") == "C01":
            sid = c01_session
        else:
            sid = spec["id"].lower() + "-" + uuid.uuid4().hex[:8]
        session_ids[spec["id"]] = sid
        status_code, duration, body, persisted, error = chat(sid, spec["message"])
        answer = str(body.get("answer") or "")
        status, notes = ("BLOCKED", [error or "http error"]) if error or status_code != 200 else judge(
            spec["id"], answer, body, persisted
        )
        html = (
            "<!doctype html><meta charset=utf-8><title>"
            + spec["id"]
            + "</title><pre>"
            + json.dumps(
                {"id": spec["id"], "status": status, "answer": answer, "sources": body.get("sources"), "trace": body.get("trace")},
                ensure_ascii=False,
                indent=2,
            )
            + "</pre>"
        )
        (EVIDENCE / f"{spec['id']}.html").write_text(html, encoding="utf-8")
        record(
            {
                "id": spec["id"],
                "priority": spec.get("priority"),
                "level": "L3",
                "status": status,
                "request": {"session_id": sid, "message": spec["message"]},
                "expected": spec.get("expected"),
                "status_code": status_code,
                "duration_ms": duration,
                "answer": answer,
                "intent": body.get("intent"),
                "customer_intent": body.get("customer_intent"),
                "decision_mode": body.get("decision_mode"),
                "reason": body.get("reason"),
                "sources": body.get("sources"),
                "trace": body.get("trace"),
                "trace_id": body.get("trace_id"),
                "message_id": body.get("message_id"),
                "persisted": persisted,
                "used_synthetic": used_synthetic(body, persisted) if body else False,
                "notes": notes,
                "error": error,
            }
        )


if __name__ == "__main__":
    main()
