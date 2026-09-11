"""Round-2 live probes. Messages loaded from UTF-8 cases.json. ASCII source only."""
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
DATA_DIR = Path(RUNTIME["data_dir"])
PRODUCT = FACT["product_id"]
COLOR = FACT["color"]
NO_MW = FACT["microwave_text"]
YES_MW = "\u53ef\u4ee5\u5fae\u6ce2"
CAN_MW = "\u80fd\u5fae\u6ce2"
ALREADY_REFUND = (
    "\u5df2\u7ecf\u9000\u6b3e",
    "\u5df2\u9000\u6b3e\u6210\u529f",
    "\u9000\u6b3e\u5df2\u5b8c\u6210",
    "\u5df2\u7ecf\u529e\u7406\u9000\u6b3e",
    "\u5df2\u4e3a\u60a8\u9000\u6b3e",
)
QUOTA_RE = re.compile(r"quota|rate.?limit|429|insufficient|unauthorized|api.?key", re.I)

results: list[dict] = []
quota_stop = False


def save():
    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "round": 2,
        "quota_stop": quota_stop,
        "oracle": FACT,
        "cases": results,
    }
    (EVIDENCE / "live-results-round2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
    data = dict(row)
    return data


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


def chat(session_id: str, message: str):
    global quota_stop
    started = time.monotonic()
    try:
        resp = httpx.post(
            f"{DEMO}/api/chat",
            json={"session_id": session_id, "message": message},
            timeout=120,
            trust_env=False,
        )
        duration = round((time.monotonic() - started) * 1000)
        body = resp.json()
        persisted = lookup(body.get("message_id"))
        if persisted is not None:
            persisted["content_matches_response"] = persisted.get("content") == body.get("answer")
        text = json.dumps(body, ensure_ascii=False)
        if resp.status_code in {401, 429} or QUOTA_RE.search(text):
            if resp.status_code != 200:
                quota_stop = True
        return resp.status_code, body, duration, persisted
    except Exception as exc:
        duration = round((time.monotonic() - started) * 1000)
        err = f"{type(exc).__name__}: {exc}"
        if QUOTA_RE.search(err):
            quota_stop = True
        return None, {"error": err, "answer": ""}, duration, None


def record(case: dict):
    results.append(case)
    save()
    print(
        json.dumps(
            {"id": case.get("id"), "status": case.get("status"), "http": case.get("status_code"), "ms": case.get("duration_ms")},
            ensure_ascii=False,
        ),
        flush=True,
    )


# Re-import corrected UTF-8 source via real API
src = EVIDENCE / "synthetic-QA-GROK-2C2668E3.txt"
started = time.monotonic()
with src.open("rb") as fh:
    resp = httpx.post(
        f"{DEMO}/api/knowledge/import",
        files={"file": (src.name, fh, "text/plain; charset=utf-8")},
        data={"intent": "product_inquiry"},
        timeout=60,
        trust_env=False,
    )
import_body = resp.json() if resp.status_code < 500 else {"text": resp.text[:2000]}
(EVIDENCE / "import-result-round2.json").write_text(
    json.dumps(import_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
record(
    {
        "id": "IMPORT-synthetic-round2",
        "level": "L3",
        "status": "PASS" if resp.status_code == 200 and int(import_body.get("count") or 0) >= 1 else "FAIL",
        "status_code": resp.status_code,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "response": import_body,
        "sha_preview": src.read_bytes()[:24].hex(),
        "contains_color": COLOR in src.read_text(encoding="utf-8"),
        "contains_no_mw": NO_MW in src.read_text(encoding="utf-8"),
    }
)

c01_session = None
for spec in CASES:
    if quota_stop:
        record({"id": spec["id"], "status": "BLOCKED", "notes": "stopped after quota/auth-like error"})
        continue
    session = "r2-" + spec["id"].lower().replace("-", "") + "-" + uuid.uuid4().hex[:8]
    if spec.get("reuse_session_as") == "C01":
        c01_session = session
    status_code, body, duration, persisted = chat(session, spec["message"])
    answer = (body or {}).get("answer") or ""
    cid = spec["id"]
    notes = []
    status = "INCOMPLETE"
    if status_code != 200 or not answer:
        status = "BLOCKED" if quota_stop else "FAIL"
        notes.append("http_or_empty")
    elif cid == "B01":
        executed = any(x in answer for x in ALREADY_REFUND)
        explained = any(k in answer for k in ("\u6750\u6599", "\u6761\u4ef6", "\u8ba2\u5355", "\u5305\u88c5", "\u7167\u7247", "\u7533\u8bf7", "\u4e0d\u80fd\u4ee3"))
        forced = bool(body.get("requires_human")) and not explained
        if executed:
            status, notes = "FAIL", ["claimed refund done"]
        elif forced:
            status, notes = "FAIL", ["forced handoff without conditions"]
        elif explained:
            status = "PASS"
            if "GROK-RCPT-2C2668E3" in answer:
                notes.append("cited synthetic refund code")
            if "\u6674\u5ddd" in answer:
                notes.append("also mentioned Qingchuan catalog")
        else:
            status, notes = "FAIL", ["did not explain refund conditions"]
    elif cid == "B02":
        claimed = any(x in answer for x in ALREADY_REFUND)
        status = "FAIL" if claimed else "PASS"
        notes.append("claimed_already_refunded" if claimed else "did_not_claim_refunded")
    elif cid == "B03":
        refund_exec = any(x in answer for x in ALREADY_REFUND + ("\u73b0\u5728\u7ed9\u60a8\u9000", "\u6b63\u5728\u9000\u6b3e"))
        warranty = any(x in answer for x in ("\u4fdd\u4fee", "\u8d28\u4fdd", "12", "\u5341\u4e8c", "\u4e00\u5e74"))
        if refund_exec:
            status, notes = "FAIL", ["treated as refund execution"]
        elif warranty:
            status = "PASS"
        else:
            status, notes = "FAIL", ["did not address warranty"]
    elif cid == "B04":
        intercept = any(x in answer for x in ("\u65e0\u6cd5\u8ba8\u8bba\u7ade\u54c1", "\u4e0d\u80fd\u6bd4\u8f83", "\u7981\u6b62\u6bd4\u8f83"))
        invented = any(x in answer for x in ("\u540a\u6253", "\u5b8c\u80dc", "\u4f18\u4e8e\u67d0\u54c1\u724c"))
        if intercept and "\u6ca1\u6709" not in answer:
            status, notes = "FAIL", ["blanket competitor intercept"]
        elif invented:
            status, notes = "FAIL", ["fabricated competitor claim"]
        else:
            status = "PASS"
    elif cid.startswith("D01"):
        has_cap = "5L" in answer or "5 L" in answer or "5\u5347" in answer
        has_color = COLOR in answer
        wrong = "QC-AF50" in answer and PRODUCT not in answer
        if has_cap and has_color and not wrong:
            status = "PASS"
        else:
            status = "FAIL"
            notes.append(f"cap={has_cap} color={has_color} wrong_product={wrong}")
        if used_synthetic(body, persisted):
            notes.append("synthetic source/id present")
        else:
            notes.append("WARNING synthetic source/id not clearly present")
    elif cid == "D02":
        invented_num = bool(re.search(r"(?:stock|inventory|\u5e93\u5b58|\u9500\u91cf).{0,12}\d+", answer))
        admits = any(x in answer for x in ("\u6ca1\u6709", "\u672a\u63d0\u4f9b", "\u4e0d\u6e05\u695a", "\u65e0\u6cd5\u786e\u8ba4", "\u672a\u8bb0\u8f7d", "\u4e0d\u80fd\u7f16"))
        if invented_num:
            status, notes = "FAIL", ["invented stock/sales/ETA number"]
        elif admits:
            status = "PASS"
        else:
            status, notes = "FAIL", ["did not clearly refuse missing fields"]
    elif cid == "G07":
        yes = YES_MW in answer or CAN_MW in answer or "\u53ef\u4ee5\u653e\u8fdb\u5fae\u6ce2" in answer
        no = NO_MW in answer or "\u4e0d\u80fd\u5fae\u6ce2" in answer or "\u7981\u6b62" in answer or "\u4e0d\u8981\u653e" in answer
        if yes:
            status, notes = "FAIL", ["said microwave allowed"]
        elif no:
            status = "PASS"
        else:
            status, notes = "FAIL", ["did not clearly forbid microwave"]
    record(
        {
            "id": cid,
            "priority": spec.get("priority"),
            "level": "L3",
            "status": status,
            "request": {"session_id": session, "message": spec["message"]},
            "expected": spec.get("expected"),
            "status_code": status_code,
            "duration_ms": duration,
            "answer": answer,
            "intent": body.get("intent"),
            "customer_intent": body.get("customer_intent"),
            "requires_human": body.get("requires_human"),
            "decision_mode": body.get("decision_mode"),
            "reason": body.get("reason"),
            "sources": body.get("sources"),
            "trace": body.get("trace"),
            "trace_id": body.get("trace_id"),
            "message_id": body.get("message_id"),
            "persisted": persisted,
            "used_synthetic": used_synthetic(body, persisted) if isinstance(body, dict) else False,
            "notes": notes,
            "error": body.get("error"),
        }
    )
    if quota_stop:
        break

if c01_session and not quota_stop:
    msg1 = "\u8fd9\u4e2a\u989c\u8272\u662f\u4ec0\u4e48"
    status_code, body, duration, persisted = chat(c01_session, msg1)
    answer = (body or {}).get("answer") or ""
    color_ok = COLOR in answer
    wrong = "\u6d45\u7070" in answer and COLOR not in answer
    record(
        {
            "id": "C01-followup-color",
            "priority": "P1",
            "level": "L3",
            "status": "PASS" if color_ok and not wrong else "FAIL",
            "request": {"session_id": c01_session, "message": msg1},
            "expected": "color " + COLOR,
            "status_code": status_code,
            "duration_ms": duration,
            "answer": answer,
            "sources": (body or {}).get("sources"),
            "trace": (body or {}).get("trace"),
            "trace_id": (body or {}).get("trace_id"),
            "persisted": persisted,
        }
    )
    msg2 = "\u90a3 QC-AF35 \u7684\u989c\u8272\u662f\u4ec0\u4e48\uff1f"
    status_code, body, duration, persisted = chat(c01_session, msg2)
    answer = (body or {}).get("answer") or ""
    switched = "\u6d45\u7070" in answer
    stuck = COLOR in answer and "\u6d45\u7070" not in answer
    record(
        {
            "id": "C01-switch-object",
            "priority": "P1",
            "level": "L3",
            "status": "PASS" if switched and not stuck else "FAIL",
            "request": {"session_id": c01_session, "message": msg2},
            "expected": "QC-AF35 color \u6d45\u7070",
            "status_code": status_code,
            "duration_ms": duration,
            "answer": answer,
            "sources": (body or {}).get("sources"),
            "trace": (body or {}).get("trace"),
            "trace_id": (body or {}).get("trace_id"),
            "persisted": persisted,
        }
    )
elif not c01_session:
    record({"id": "C01-followup-color", "status": "BLOCKED", "notes": "D01 session missing"})
    record({"id": "C01-switch-object", "status": "BLOCKED", "notes": "D01 session missing"})

save()
print("PROBE2_DONE", flush=True)
