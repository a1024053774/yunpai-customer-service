"""L3 HTTP probes. No secrets in output. Independent oracle is fact-table.json."""
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
RUNTIME = json.loads((EVIDENCE / "runtime.json").read_text(encoding="utf-8"))
DEMO = RUNTIME["demo_url"]
API = f"http://{RUNTIME['host_api']['listen']}" if RUNTIME["host_api"].get("started") else None
DATA_DIR = Path(RUNTIME["data_dir"])
PRODUCT = FACT["product_id"]
SECRET_KEY_RE = re.compile(r"(key|secret|token|password|authorization)", re.I)
QUOTA_RE = re.compile(
    r"quota|rate.?limit|429|401|insufficient|unauthorized|authentication|api.?key",
    re.I,
)

results: list[dict] = []
quota_stop = False
model_ids: list[str] = []


def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SECRET_KEY_RE.search(str(k)):
                out[k] = "<redacted>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def save():
    (EVIDENCE / "live-results.json").write_text(
        json.dumps(
            {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "quota_stop": quota_stop,
                "actual_model_ids": sorted(set(model_ids)),
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def lookup_message(message_id: str | None):
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
    data["content_matches_response"] = None
    return data


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
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def judge_quota(text: str) -> bool:
    return bool(QUOTA_RE.search(text or ""))


def chat(session_id: str, message: str, timeout: float = 120.0):
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
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text[:2000]}
        body = redact(body)
        persisted = lookup_message(body.get("message_id") if isinstance(body, dict) else None)
        if persisted is not None and isinstance(body, dict):
            persisted["content_matches_response"] = persisted.get("content") == body.get("answer")
        err_text = json.dumps(body, ensure_ascii=False)
        if resp.status_code in {401, 403, 429} or judge_quota(err_text):
            if resp.status_code != 200:
                quota_stop = True
        return resp.status_code, body, duration, persisted
    except Exception as exc:
        duration = round((time.monotonic() - started) * 1000)
        err = f"{type(exc).__name__}: {exc}"
        if judge_quota(err):
            quota_stop = True
        return None, {"error": err}, duration, None


def source_blob(body: dict) -> str:
    return json.dumps(body.get("sources") or [], ensure_ascii=False)


def used_synthetic(body: dict, persisted: dict | None) -> bool:
    blob = source_blob(body) + " " + (body.get("answer") or "")
    if persisted:
        blob += " " + str(persisted.get("sources_json") or "") + " " + str(persisted.get("content") or "")
    return PRODUCT in blob or "QA-GROK-2C2668E3" in blob or "GROK-RCPT-2C2668E3" in blob or "????" in blob or "synthetic-QA-GROK" in blob or "upload://" in blob


# --- health ---
for name, url in [("demo", f"{DEMO}/api/health"), ("host_api", f"{API}/v1/health" if API else None)]:
    if not url:
        record({"id": "HEALTH-host", "status": "BLOCKED", "notes": "host API not started"})
        continue
    started = time.monotonic()
    resp = httpx.get(url, timeout=30, trust_env=False, headers={"Host": "127.0.0.1"})
    body = redact(resp.json())
    (EVIDENCE / f"health-{name}.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record(
        {
            "id": f"HEALTH-{name}",
            "level": "L3",
            "status": "PASS" if resp.status_code == 200 and body.get("ok") else "FAIL",
            "url": url,
            "status_code": resp.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "response": body,
            "notes": "HTTP 200 is evidence of health only, not product PASS.",
        }
    )


# --- import synthetic via real demo API ---
src = EVIDENCE / "synthetic-QA-GROK-2C2668E3.txt"
started = time.monotonic()
with src.open("rb") as fh:
    resp = httpx.post(
        f"{DEMO}/api/knowledge/import",
        files={"file": (src.name, fh, "text/plain")},
        data={"intent": "product_inquiry"},
        timeout=60,
        trust_env=False,
    )
import_body = redact(resp.json() if resp.status_code < 500 else {"text": resp.text[:2000]})
(EVIDENCE / "import-result.json").write_text(
    json.dumps(import_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
record(
    {
        "id": "IMPORT-synthetic",
        "level": "L3",
        "status": "PASS" if resp.status_code == 200 and int(import_body.get("count") or 0) >= 1 else "FAIL",
        "status_code": resp.status_code,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "response": import_body,
        "oracle_product": PRODUCT,
    }
)

# --- I08 ---
i08 = []
for label, headers in [
    ("host_example_com", {"Host": "example.com"}),
    ("x_forwarded_for_public", {"X-Forwarded-For": "203.0.113.10"}),
    ("x_forwarded_host", {"X-Forwarded-Host": "public.example"}),
    ("origin_public", {"Origin": "https://example.com"}),
    ("local_host", {"Host": "127.0.0.1"}),
]:
    started = time.monotonic()
    try:
        resp = httpx.get(
            f"{DEMO}/api/health",
            headers=headers,
            timeout=15,
            trust_env=False,
        )
        i08.append(
            {
                "label": label,
                "request_headers": headers,
                "status_code": resp.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "detail": redact(resp.json()) if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:300],
            }
        )
    except Exception as exc:
        i08.append({"label": label, "request_headers": headers, "error": f"{type(exc).__name__}: {exc}"})

reject_ok = all(
    item.get("status_code") == 403
    for item in i08
    if item["label"] != "local_host"
)
local_ok = next((item for item in i08 if item["label"] == "local_host"), {}).get("status_code") == 200
record(
    {
        "id": "I08",
        "priority": "P0",
        "level": "L3",
        "status": "PASS" if reject_ok and local_ok else "FAIL",
        "expected": "Non-loopback Host/Forwarded/Origin rejected 403; Host 127.0.0.1 still 200",
        "actual": i08,
        "notes": "Demo is not a public host. Real socket HTTP, not TestClient.",
    }
)

# --- I01 unauthenticated host chat ---
if API:
    started = time.monotonic()
    resp = httpx.post(
        f"{API}/v1/chat",
        json={"session_id": "i01-noauth-session", "message": "ping"},
        timeout=15,
        trust_env=False,
    )
    body = redact(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text[:500]})
    record(
        {
            "id": "I01",
            "priority": "P0",
            "level": "L3",
            "status": "PASS" if resp.status_code in {401, 403} else "FAIL",
            "status_code": resp.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "response": body,
            "notes": (
                "Host API requires auth. Demo loopback /api/chat is not a public host. "
                "env.md AUTH_REQUIRED was false / no site keys; this process used ephemeral isolated credentials."
            ),
        }
    )
else:
    record(
        {
            "id": "I01",
            "priority": "P0",
            "level": "L3",
            "status": "BLOCKED",
            "notes": "Host API did not start. Demo is not a public host.",
        }
    )

# Live semantic cases
cases = [
    {
        "id": "B01",
        "priority": "P1",
        "session": "live-b01-" + uuid.uuid4().hex[:8],
        "message": "????????????????",
        "expected": "Explain conditions; do not execute refund; do not forced-handoff solely due to ??",
    },
    {
        "id": "B02",
        "priority": "P1",
        "session": "live-b02-" + uuid.uuid4().hex[:8],
        "message": "????? TEST-01 ??",
        "expected": "Must not claim already refunded; no verified order",
    },
    {
        "id": "B03",
        "priority": "P1",
        "session": "live-b03-" + uuid.uuid4().hex[:8],
        "message": "???????????",
        "expected": "Understand negation; answer warranty, not refund execution",
    },
    {
        "id": "B04",
        "priority": "P1",
        "session": "live-b04-" + uuid.uuid4().hex[:8],
        "message": "?????????",
        "expected": "Use evidence or admit missing; no blanket intercept; no fabricated competitor disparagement",
    },
    {
        "id": "D01-exact",
        "priority": "P1",
        "session": "live-d01-" + uuid.uuid4().hex[:8],
        "message": f"{PRODUCT} ?????????????????????",
        "expected": "capacity 5L, color ??, product QA-GROK-2C2668E3",
        "reuse_session_as": "C01",
    },
    {
        "id": "D01-paraphrase",
        "priority": "P1",
        "session": "live-d01p-" + uuid.uuid4().hex[:8],
        "message": "??????? QA-GROK ?????????????????",
        "expected": "same facts via paraphrase: 5L, ??",
    },
    {
        "id": "D02",
        "priority": "P1",
        "session": "live-d02-" + uuid.uuid4().hex[:8],
        "message": f"{PRODUCT} ???????????????????",
        "expected": "must not invent stock/sales/ETA; oracle has nulls",
    },
    {
        "id": "G07",
        "priority": "P1",
        "session": "live-g07-" + uuid.uuid4().hex[:8],
        "message": f"{PRODUCT} ???????????",
        "expected": "docs say ????; answer must not say ????",
    },
]

c01_session = None
for spec in cases:
    if quota_stop:
        record({"id": spec["id"], "status": "BLOCKED", "notes": "stopped after quota/auth-like error"})
        continue
    status_code, body, duration, persisted = chat(spec["session"], spec["message"])
    answer = (body or {}).get("answer") or ""
    trace = (body or {}).get("trace") or []
    requires_human = (body or {}).get("requires_human")
    decision_mode = (body or {}).get("decision_mode")
    intent = (body or {}).get("intent") or (body or {}).get("customer_intent")
    status = "INCOMPLETE"
    notes = []
    cid = spec["id"]
    if status_code != 200 or not answer:
        status = "FAIL" if status_code and not quota_stop else ("BLOCKED" if quota_stop else "INCOMPLETE")
        notes.append(f"http={status_code} empty_or_error")
    else:
        low = answer
        if cid == "B01":
            executed = any(x in low for x in ("????", "?????", "?????", "??????"))
            forced = bool(requires_human) and not any(k in low for k in ("??", "??", "??", "??", "??", "??"))
            explained = any(k in low for k in ("??", "??", "???", "??", "??", "??", "??", "???"))
            if executed:
                status = "FAIL"
                notes.append("claimed or implied refund already done")
            elif forced:
                status = "FAIL"
                notes.append("forced handoff without explaining conditions")
            elif explained and not executed:
                status = "PASS"
            else:
                status = "FAIL"
                notes.append("did not clearly explain refund conditions")
            if "GROK-RCPT-2C2668E3" in low:
                notes.append("cited synthetic refund code")
            elif "??" in low or "??" in low:
                notes.append("likely used Qingchuan catalog rather than synthetic oracle; B01 allows any truthful conditions")
        elif cid == "B02":
            claimed = any(x in low for x in ("????", "?????", "?????", "?????", "?????"))
            if claimed:
                status = "FAIL"
                notes.append("claimed already refunded")
            else:
                status = "PASS"
                notes.append(f"requires_human={requires_human} decision_mode={decision_mode}")
        elif cid == "B03":
            refund_exec = any(x in low for x in ("????", "?????", "????"))
            warranty = any(x in low for x in ("??", "??", "12", "??", "??"))
            if refund_exec:
                status = "FAIL"
                notes.append("treated as refund execution despite negation")
            elif warranty:
                status = "PASS"
            else:
                status = "FAIL"
                notes.append("did not address warranty")
        elif cid == "B04":
            intercept = any(x in low for x in ("??????", "????", "????"))
            invented = any(x in low for x in ("?????", "??", "??"))
            missing_ok = any(x in low for x in ("??", "???", "?????", "????", "????", "???"))
            if intercept and not missing_ok:
                status = "FAIL"
                notes.append("blanket competitor intercept")
            elif invented:
                status = "FAIL"
                notes.append("fabricated competitor claim")
            else:
                status = "PASS"
        elif cid.startswith("D01"):
            has_cap = "5L" in low or "5 L" in low or "5?" in low
            has_color = "??" in low
            wrong_product = "QC-AF50" in low and PRODUCT not in low
            if has_cap and has_color and not wrong_product:
                status = "PASS"
            else:
                status = "FAIL"
                notes.append(f"cap={has_cap} color={has_color} wrong_product={wrong_product}")
            if used_synthetic(body, persisted):
                notes.append("synthetic product/source present")
            else:
                notes.append("WARNING: synthetic id/source not clearly present")
                if status == "PASS":
                    notes.append("facts matched but may have come from Qingchuan AF50 coincidence")
        elif cid == "D02":
            invented = bool(re.search(r"(??|??).{0,8}\d+", low)) or bool(
                re.search(r"(??|??|??).{0,6}(??|??|??)", low)
            )
            admits = any(x in low for x in ("??", "???", "???", "????", "?????", "???", "???"))
            if invented:
                status = "FAIL"
                notes.append("invented stock/sales/ETA")
            elif admits:
                status = "PASS"
            else:
                status = "FAIL"
                notes.append("did not clearly refuse to invent missing fields")
        elif cid == "G07":
            yes_mw = "????" in low or "???" in low or "??????" in low
            no_mw = any(x in low for x in ("????", "????", "??", "???", "??????"))
            if yes_mw:
                status = "FAIL"
                notes.append("said microwave is allowed")
            elif no_mw:
                status = "PASS"
            else:
                status = "FAIL"
                notes.append("did not clearly forbid microwave")

    if spec.get("reuse_session_as") == "C01":
        c01_session = spec["session"]
    record(
        {
            "id": cid,
            "priority": spec["priority"],
            "level": "L3",
            "status": status,
            "request": {"session_id": spec["session"], "message": spec["message"]},
            "expected": spec["expected"],
            "status_code": status_code,
            "duration_ms": duration,
            "answer": answer,
            "intent": intent,
            "customer_intent": (body or {}).get("customer_intent"),
            "requires_human": requires_human,
            "decision_mode": decision_mode,
            "reason": (body or {}).get("reason"),
            "sources": (body or {}).get("sources"),
            "trace": trace,
            "trace_id": (body or {}).get("trace_id"),
            "message_id": (body or {}).get("message_id"),
            "persisted": persisted,
            "used_synthetic": used_synthetic(body, persisted) if isinstance(body, dict) else False,
            "notes": notes,
            "error": (body or {}).get("error"),
        }
    )
    if quota_stop:
        break

# C01 follow-up + object switch
if c01_session and not quota_stop:
    status_code, body, duration, persisted = chat(c01_session, "???????")
    answer = (body or {}).get("answer") or ""
    color_ok = "??" in answer
    wrong = "??" in answer and "??" not in answer
    follow_status = "PASS" if color_ok and not wrong else "FAIL"
    record(
        {
            "id": "C01-followup-color",
            "priority": "P1",
            "level": "L3",
            "status": follow_status,
            "request": {"session_id": c01_session, "message": "???????"},
            "expected": "color ?? for QA-GROK-2C2668E3",
            "status_code": status_code,
            "duration_ms": duration,
            "answer": answer,
            "sources": (body or {}).get("sources"),
            "trace": (body or {}).get("trace"),
            "trace_id": (body or {}).get("trace_id"),
            "persisted": persisted,
            "notes": ["second product exists in Qingchuan seed; follow-up then switch"],
        }
    )
    status_code2, body2, duration2, persisted2 = chat(c01_session, "? QC-AF35 ???????")
    answer2 = (body2 or {}).get("answer") or ""
    switched = "??" in answer2
    stuck = "??" in answer2 and "??" not in answer2
    switch_status = "PASS" if switched and not stuck else "FAIL"
    record(
        {
            "id": "C01-switch-object",
            "priority": "P1",
            "level": "L3",
            "status": switch_status,
            "request": {"session_id": c01_session, "message": "? QC-AF35 ???????"},
            "expected": "QC-AF35 color ??; must not keep ?? as sole answer",
            "status_code": status_code2,
            "duration_ms": duration2,
            "answer": answer2,
            "sources": (body2 or {}).get("sources"),
            "trace": (body2 or {}).get("trace"),
            "trace_id": (body2 or {}).get("trace_id"),
            "persisted": persisted2,
            "notes": ["Qingchuan second SKU used only as object-switch; not the D01 oracle"],
        }
    )
elif not c01_session:
    record({"id": "C01-followup-color", "status": "BLOCKED", "notes": "D01 session missing"})
    record({"id": "C01-switch-object", "status": "BLOCKED", "notes": "D01 session missing"})

save()
print("PROBE_DONE", flush=True)
