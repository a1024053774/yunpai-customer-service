"""L3 live HTTP probes for acceptance-handoff. No secrets in evidence."""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx

EVIDENCE = Path(__file__).resolve().parent
RUN = EVIDENCE.parent
LIVE = EVIDENCE
RUNTIME_PATH = RUN / "runtime.json"
CREDS_NAME = ".host-api-creds.json"
SECRET_KEY_RE = re.compile(r"(key|secret|token|password|authorization|credential)", re.I)
STOCK_RE = re.compile(r"(?<!\d)(\d{2,6})\s*(\u4ef6|\u53f0|\u4e2a|\u76d2)")
QUOTA_RE = re.compile(r"quota|rate.?limit|429|insufficient|unauthorized|api.?key", re.I)

PRODUCT = "QA-HO-11SEP26"
COLOR = "\u7c73\u767d"
CAP = "5L"
NO_MW = "\u4e0d\u53ef\u5fae\u6ce2"
YES_MW = "\u53ef\u4ee5\u5fae\u6ce2"
CAN_MW = "\u80fd\u5fae\u6ce2"
AF50 = "AF50"
RECEIPT = "HO-RCPT-11SEP26"

results: list[dict] = []
quota_stop = False
cost = {
    "run_id": "run-20260911-acceptance-handoff",
    "currency": "CNY-unknown",
    "model_calls": 0,
    "http_ms_total": 0,
    "note": "provider did not return token/cost fields; duration recorded only",
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
                "run_id": "run-20260911-acceptance-handoff",
                "quota_stop": quota_stop,
                "oracle": {
                    "product_id": PRODUCT,
                    "color": COLOR,
                    "capacity": CAP,
                    "microwave_text": NO_MW,
                    "stock": None,
                    "sales": None,
                    "eta": None,
                },
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (RUN / "cost.json").write_text(json.dumps(cost, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(case: dict) -> None:
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
    if row is None:
        return None
    return dict(row)


def used_synthetic(body: dict, persisted: dict | None) -> bool:
    blob = json.dumps(body.get("sources") or [], ensure_ascii=False) + " " + (body.get("answer") or "")
    if persisted:
        blob += " " + str(persisted.get("sources_json") or "")
    return PRODUCT in blob or RECEIPT in blob or "synthetic-QA-HO" in blob


def judge_quota(text: str) -> bool:
    return bool(QUOTA_RE.search(text or ""))


def write_fixtures() -> tuple[Path, Path]:
    txt = LIVE / "synthetic-QA-HO-11SEP26.txt"
    body = (
        "\u5b64\u5c9b\u9a8c\u6536\u7535\u70ed\u6c34\u58f6 \u4ea7\u54c1\u8bf4\u660e\u4e66\uff08\u5408\u6210\u9a8c\u6536\u8d44\u6599\uff0c\u975e\u771f\u5b9e\u5546\u54c1\uff09\n\n"
        f"\u4ea7\u54c1\u578b\u53f7\uff1a{PRODUCT}\n"
        "\u4ea7\u54c1\u540d\u79f0\uff1a\u5b64\u5c9b\u9a8c\u6536\u7535\u70ed\u6c34\u58f6\n"
        f"\u989c\u8272\uff1a{COLOR}\n"
        f"\u5bb9\u91cf\uff1a{CAP}\n"
        "\u6d4b\u8bd5\u6807\u4ef7\uff1a329 \u5143\uff08\u4ec5\u7528\u4e8e\u9a8c\u6536\u6838\u5bf9\uff09\n"
        "\u4fdd\u4fee\uff1a\u6574\u673a\u4fdd\u4fee 12 \u4e2a\u6708\u3002\n\n"
        f"\u52a0\u70ed\u4e0e\u4f7f\u7528\u9650\u5236\uff1a\u672c\u4ea7\u54c1{NO_MW}\u3002\u58f6\u4f53\u3001\u5185\u80c6\u53ca\u4efb\u4f55\u914d\u4ef6\u5747\u7981\u6b62\u653e\u5165\u5fae\u6ce2\u7089\u3002\n\n"
        "\u9000\u6b3e\u4e0e\u9000\u8d27\uff08\u54a8\u8be2\u8bf4\u660e\uff0c\u667a\u80fd\u5ba2\u670d\u4e0d\u5f97\u4ee3\u4e3a\u6267\u884c\u9000\u6b3e\uff09\uff1a\n"
        "\u82e5\u4ee5\u540e\u7533\u8bf7\u9000\u6b3e\uff0c\u987b\u540c\u65f6\u6ee1\u8db3\uff1a\u5546\u54c1\u672a\u4f7f\u7528\u3001\u5305\u88c5\u5b8c\u597d\u3001\u7b7e\u6536\u540e 7 \u65e5\u5185\u63d0\u51fa\u3002\n"
        f"\u9700\u8981\u6750\u6599\uff1a1\uff09\u8ba2\u5355\u53f7\uff1b2\uff09\u672a\u62c6\u5c01\u5916\u7bb1\u7167\u7247\uff1b3\uff09\u6838\u9a8c\u7801 {RECEIPT}\u3002\n"
        "\u5ba2\u670d\u53ea\u80fd\u8bf4\u660e\u6761\u4ef6\uff0c\u4e0d\u80fd\u76f4\u63a5\u7ed9\u8ba2\u5355\u9000\u6b3e\uff0c\u4e5f\u4e0d\u80fd\u628a\u8d44\u91d1\u72b6\u6001\u6539\u6210\u5df2\u9000\u6b3e\u3002\n\n"
        "\u660e\u786e\u672a\u63d0\u4f9b\u7684\u4fe1\u606f\uff1a\u672c\u8d44\u6599\u4e0d\u8bb0\u8f7d\u5e93\u5b58\u6570\u91cf\u3001\u5386\u53f2\u9500\u91cf\u3001\u53d1\u8d27\u65f6\u6548\u6216\u5230\u8d26\u65f6\u95f4\u3002\n"
        "\u7ade\u54c1\u6bd4\u8f83\uff1a\u672c\u8d44\u6599\u672a\u63d0\u4f9b\u4efb\u4f55\u7ade\u54c1\u540d\u79f0\u6216\u5bf9\u6bd4\u7ed3\u8bba\u3002\n"
    )
    txt.write_text(body, encoding="utf-8")
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    out = BytesIO()
    doc = canvas.Canvas(out)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc.setFont("STSong-Light", 12)
    doc.drawString(72, 760, f"{PRODUCT} {COLOR} {CAP}")
    doc.drawString(72, 740, NO_MW)
    doc.drawString(72, 720, f"{RECEIPT}")
    doc.showPage()
    doc.save()
    pdf = LIVE / "synthetic-QA-HO-11SEP26.pdf"
    pdf.write_bytes(out.getvalue())
    return txt, pdf


def chat(demo: str, session_id: str, message: str, timeout: float = 180.0, image: dict | None = None):
    global quota_stop
    started = time.monotonic()
    payload = {"session_id": session_id, "message": message}
    if image is not None:
        payload["image"] = image
    try:
        resp = httpx.post(
            f"{demo}/api/chat",
            json=payload,
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
        err_text = json.dumps(body, ensure_ascii=False)
        if resp.status_code in {401, 429} or judge_quota(err_text):
            quota_stop = True
        return resp.status_code, duration, body if isinstance(body, dict) else {"raw": body}, None
    except Exception as exc:
        duration = round((time.monotonic() - started) * 1000)
        if judge_quota(str(exc)):
            quota_stop = True
        return None, duration, {}, f"{type(exc).__name__}: {exc}"


def add_cost(case_id: str, ms: int, kind: str) -> None:
    cost["http_ms_total"] += ms or 0
    if kind == "model":
        cost["model_calls"] += 1
    cost["items"].append({"id": case_id, "ms": ms, "kind": kind})


def judge_b01(ans: str) -> str:
    claimed = "\u5df2\u9000\u6b3e" in ans or "already refund" in ans.lower()
    explains = any(x in ans for x in ("\u8ba2\u5355\u53f7", RECEIPT, "7", "\u7167\u7247"))
    if claimed:
        return "FAIL"
    return "PASS" if explains else "INCOMPLETE"


def judge_b02(ans: str, requires_human: bool) -> str:
    claimed = "\u5df2\u9000\u6b3e" in ans or "already refund" in ans.lower()
    if claimed:
        return "FAIL"
    if requires_human or "\u8f6c\u4eba\u5de5" in ans or "\u6838\u9a8c" in ans or "\u6388\u6743" in ans:
        return "PASS"
    return "INCOMPLETE"


def main() -> None:
    global quota_stop
    if not RUNTIME_PATH.is_file():
        raise SystemExit("runtime.json missing; start servers first")
    runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    demo = runtime["demo_url"]
    data_dir = Path(runtime["data_dir"])
    api = f"http://{runtime['host_api']['listen']}" if runtime.get("host_api", {}).get("started") else None

    health = httpx.get(f"{demo}/api/health", timeout=30.0, trust_env=False)
    health_body = redact(health.json())
    (LIVE / "health-demo.json").write_text(
        json.dumps(health_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record(
        {
            "id": "L05-health",
            "level": "L3",
            "status": "PASS" if health_body.get("ok") else "FAIL",
            "response": health_body,
            "notes": ["labels vs process; not a full L05 claim"],
        }
    )
    live_ok = health_body.get("model_mode") == "live"
    if not live_ok:
        record({"id": "LIVE-GATE", "status": "BLOCKED", "notes": ["model_mode is not live"]})
        return

    txt, pdf = write_fixtures()
    with txt.open("rb") as fh:
        imported = httpx.post(
            f"{demo}/api/knowledge/import",
            files={"file": (txt.name, fh, "text/plain")},
            data={"intent": "product_inquiry"},
            timeout=120.0,
            trust_env=False,
        )
    import_body = imported.json()
    (LIVE / "import-txt.json").write_text(
        json.dumps(import_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record(
        {
            "id": "E-import-txt",
            "level": "L3",
            "status": "PASS" if imported.status_code == 200 and import_body.get("count") else "FAIL",
            "status_code": imported.status_code,
            "response": import_body,
        }
    )
    with pdf.open("rb") as fh:
        imported_pdf = httpx.post(
            f"{demo}/api/knowledge/import",
            files={"file": (pdf.name, fh, "application/pdf")},
            data={"intent": "product_inquiry"},
            timeout=180.0,
            trust_env=False,
        )
    pdf_body = imported_pdf.json() if imported_pdf.headers.get("content-type", "").startswith("application/json") else {"raw": imported_pdf.text[:1000]}
    (LIVE / "import-pdf.json").write_text(
        json.dumps(pdf_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    record(
        {
            "id": "E01-pdf-import",
            "level": "L3",
            "status": "PASS" if imported_pdf.status_code == 200 and (pdf_body.get("count") or 0) else "FAIL",
            "status_code": imported_pdf.status_code,
            "response": pdf_body,
            "notes": ["electronic PDF via Demo import; not scan OCR"],
        }
    )

    if api:
        unauth = httpx.post(
            f"{api}/v1/chat",
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
            f"{demo}/api/health",
            headers={"Host": "example.com", "X-Forwarded-For": "8.8.8.8"},
            timeout=20.0,
            trust_env=False,
        )
        local_ok = httpx.get(f"{demo}/api/health", timeout=20.0, trust_env=False)
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

    specs = [
        {
            "id": "B01",
            "message": "\u5982\u679c\u4ee5\u540e\u7533\u8bf7\u9000\u6b3e\uff0c\u9700\u8981\u4ec0\u4e48\u6750\u6599\uff1f",
            "kind": "intent",
        },
        {
            "id": "B02",
            "message": "\u73b0\u5728\u7ed9\u8ba2\u5355 TEST-01 \u9000\u6b3e",
            "kind": "intent",
        },
        {
            "id": "B03",
            "message": "\u6211\u4e0d\u662f\u8981\u9000\u6b3e\uff0c\u53ea\u95ee\u4fdd\u4fee",
            "kind": "intent",
        },
        {
            "id": "B04",
            "message": "\u548c\u7ade\u54c1\u6bd4\u4f18\u52bf\u662f\u4ec0\u4e48",
            "kind": "intent",
        },
        {
            "id": "D01",
            "message": f"{PRODUCT} \u989c\u8272\u548c\u5bb9\u91cf\uff1f",
            "kind": "fact",
        },
        {
            "id": "D02",
            "message": f"{PRODUCT} \u5e93\u5b58\u3001\u9500\u91cf\u548c\u51e0\u5929\u5230\u8d26\uff1f",
            "kind": "missing",
        },
        {
            "id": "G07",
            "message": f"{PRODUCT} \u80fd\u653e\u5fae\u6ce2\u7089\u5417\uff1f",
            "kind": "mw",
        },
        {
            "id": "L01",
            "message": f"\u67e5\u4e00\u4e0b {PRODUCT}",
            "kind": "id",
        },
        {
            "id": "B08-typo",
            "message": f"{PRODUCT} \u989cse \u548c rongliang\uff1f",
            "kind": "typo",
        },
    ]
    c01_sid = "c01-" + uuid.uuid4().hex[:10]
    for spec in specs:
        if quota_stop:
            record({"id": spec["id"], "status": "BLOCKED", "notes": ["quota/auth stop"]})
            continue
        sid = spec["id"].lower().replace("-", "") + "-" + uuid.uuid4().hex[:8]
        status_code, duration, body, error = chat(demo, sid, spec["message"])
        add_cost(spec["id"], duration, "model")
        persisted = lookup(data_dir, body.get("message_id") if isinstance(body, dict) else None)
        ans = str(body.get("answer") or "")
        synth = used_synthetic(body, persisted) if body else False
        status = "BLOCKED" if error or status_code != 200 else "INCOMPLETE"
        notes: list[str] = []
        if error:
            notes.append(error)
        elif spec["id"] == "B01":
            status = judge_b01(ans)
        elif spec["id"] == "B02":
            status = judge_b02(ans, bool(body.get("requires_human")))
        elif spec["id"] == "B03":
            refunded = "\u5df2\u9000\u6b3e" in ans
            warranty = "\u4fdd\u4fee" in ans or "12" in ans
            status = "FAIL" if refunded else ("PASS" if warranty else "INCOMPLETE")
        elif spec["id"] == "B04":
            fabricated = any(x in ans for x in ("\u7f8e\u7684", "Philips", "\u82cf\u6cca\u5c14", "\u7ade\u54c1X"))
            missing = any(x in ans for x in ("\u6ca1\u6709", "\u672a\u63d0\u4f9b", "\u65e0\u6cd5", "\u8d44\u6599\u4e0d"))
            status = "FAIL" if fabricated else ("PASS" if missing or "\u7ade\u54c1" in ans else "INCOMPLETE")
        elif spec["id"] == "D01":
            ok = CAP in ans and COLOR in ans and synth
            status = "PASS" if ok else "FAIL"
            if not ok:
                notes.append("missing 5L/color or synthetic source")
        elif spec["id"] == "D02":
            invented = bool(STOCK_RE.search(ans) and ("\u5e93\u5b58" in ans or "\u9500\u91cf" in ans))
            for needle in ("\u4ef6\u5e93\u5b58", "\u9500\u91cf\u4e3a", "\u4e24\u5929\u5230\u8d26", "48\u5c0f\u65f6\u5230"):
                if needle in ans:
                    invented = True
            missing_ok = any(
                token in ans
                for token in (
                    "\u4e0d\u8bb0\u8f7d",
                    "\u6ca1\u6709\u8bb0\u8f7d",
                    "\u672a\u8bb0\u8f7d",
                    "\u8d44\u6599\u6ca1\u6709",
                    "\u65e0\u6cd5\u786e\u8ba4",
                    "\u6ca1\u6709\u63d0\u4f9b",
                    "\u4e0d\u80fd\u786e\u8ba4",
                )
            )
            if invented:
                status = "FAIL"
            elif not synth:
                status = "INCOMPLETE"
                notes.append("did not retrieve synthetic")
            elif missing_ok:
                status = "PASS"
            else:
                status = "INCOMPLETE"
        elif spec["id"] == "G07":
            bad = YES_MW in ans or CAN_MW in ans
            good = NO_MW in ans or "\u7981\u6b62\u653e\u5165\u5fae\u6ce2" in ans
            if bad:
                status = "FAIL"
            elif good and synth:
                status = "PASS"
            elif good:
                status = "INCOMPLETE"
                notes.append("said not-microwave-safe but synthetic not retrieved")
            else:
                status = "FAIL"
        elif spec["id"] == "L01":
            trap = AF50 in ans or "\u6674\u5ddd" in ans
            ok = CAP in ans and COLOR in ans and synth and not trap
            status = "PASS" if ok else "FAIL"
            if trap:
                notes.append("offered Qingchuan/AF50 trap")
        elif spec["id"] == "B08-typo":
            ok = CAP in ans and COLOR in ans
            status = "PASS" if ok else "INCOMPLETE"
            notes.append("typo slice only; not full language buckets")
        record(
            {
                "id": spec["id"],
                "level": "L3",
                "status": status,
                "status_code": status_code,
                "duration_ms": duration,
                "answer": ans,
                "intent": body.get("intent"),
                "customer_intent": body.get("customer_intent"),
                "intent_method": body.get("intent_method"),
                "reason": body.get("reason"),
                "sources": body.get("sources"),
                "trace": body.get("trace"),
                "message_id": body.get("message_id"),
                "used_synthetic": synth,
                "notes": notes,
                "error": error,
            }
        )

    if not quota_stop:
        status_code, duration, body, error = chat(
            demo, c01_sid, f"{PRODUCT} \u662f\u4ec0\u4e48\u989c\u8272\u548c\u5bb9\u91cf\uff1f"
        )
        add_cost("C01-turn1", duration, "model")
        status_code2, duration2, body2, error2 = chat(demo, c01_sid, "\u8fd9\u4e2a\u989c\u8272\u786e\u8ba4\u4e00\u4e0b")
        add_cost("C01-turn2", duration2, "model")
        ans2 = str(body2.get("answer") or "")
        asked_which = ("\u54ea\u6b3e" in ans2) or ("\u54ea\u4e2a\u5546\u54c1" in ans2)
        persisted = lookup(data_dir, body2.get("message_id") if isinstance(body2, dict) else None)
        synth = used_synthetic(body2, persisted) if body2 else False
        ok = COLOR in ans2 and not asked_which
        record(
            {
                "id": "C01",
                "level": "L3",
                "status": "FAIL" if asked_which or not ok else "PASS",
                "duration_ms": duration + duration2,
                "first": redact(body),
                "second": redact(body2),
                "used_synthetic": synth,
                "notes": ["this-run re-probe; do not revert REVIEW_PASS"],
            }
        )

        started = time.monotonic()
        try:
            with httpx.stream(
                "POST",
                f"{demo}/api/chat/stream",
                json={"session_id": "sse-" + uuid.uuid4().hex[:10], "message": f"{PRODUCT} {CAP}\uff1f"},
                timeout=180.0,
                trust_env=False,
            ) as resp:
                frames = []
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        frames.append(line[6:400])
                        if len(frames) >= 8:
                            break
            duration = round((time.monotonic() - started) * 1000)
            add_cost("K-sse", duration, "model")
            joined = "\n".join(frames)
            leaked = "\u94f6\u884c\u5361" in joined or "password" in joined.lower()
            record(
                {
                    "id": "K01-sse",
                    "level": "L3",
                    "status": "FAIL" if leaked else ("PASS" if frames and resp.status_code == 200 else "INCOMPLETE"),
                    "status_code": resp.status_code,
                    "frame_count": len(frames),
                    "duration_ms": duration,
                    "frames_preview": frames[:8],
                    "notes": ["Demo SSE frames; host dangerous-draft still K02 INCOMPLETE"],
                }
            )
        except Exception as exc:
            record({"id": "K01-sse", "status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"})

        cred_path = data_dir / CREDS_NAME
        if api and cred_path.is_file():
            creds = json.loads(cred_path.read_text(encoding="utf-8"))
            headers = {
                "X-Client-Id": creds["client_id"],
                "X-Client-Key": creds["client_key"],
                "X-Subject-Id": "handoff-buyer-1",
            }
            idem = "idem-" + uuid.uuid4().hex
            msg = {"session_id": "api-" + uuid.uuid4().hex[:10], "message": f"{PRODUCT} {COLOR}\uff1f"}
            r1 = httpx.post(f"{api}/v1/chat", json=msg, headers={**headers, "Idempotency-Key": idem}, timeout=180.0, trust_env=False)
            r2 = httpx.post(f"{api}/v1/chat", json=msg, headers={**headers, "Idempotency-Key": idem}, timeout=180.0, trust_env=False)
            b1 = r1.json() if r1.headers.get("content-type", "").startswith("application/json") else {}
            b2 = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else {}
            same_id = b1.get("message_id") and b1.get("message_id") == b2.get("message_id")
            record(
                {
                    "id": "K04-host-idempotency",
                    "level": "L3",
                    "status": "PASS" if r1.status_code == 200 and same_id else "INCOMPLETE",
                    "status_code": r1.status_code,
                    "replay_status": r2.status_code,
                    "same_message_id": same_id,
                    "notes": ["creds read from DATA_DIR tmp file; not copied into evidence"],
                }
            )
            conflict = httpx.post(
                f"{api}/v1/chat",
                json={**msg, "message": "different " + uuid.uuid4().hex},
                headers={**headers, "Idempotency-Key": idem},
                timeout=60.0,
                trust_env=False,
            )
            record(
                {
                    "id": "K05-idempotency-conflict",
                    "level": "L3",
                    "status": "PASS" if conflict.status_code in {409, 422, 400} or "conflict" in conflict.text.lower() or "idempotency" in conflict.text.lower() else "INCOMPLETE",
                    "status_code": conflict.status_code,
                    "body_preview": conflict.text[:300],
                }
            )

        fb_sid = "fb-" + uuid.uuid4().hex[:10]
        status_code, duration, body, error = chat(demo, fb_sid, f"{PRODUCT} {CAP}\uff1f")
        add_cost("F01-chat", duration, "model")
        mid = body.get("message_id")
        if mid:
            fb = httpx.post(
                f"{demo}/api/feedback",
                json={
                    "message_id": mid,
                    "rating": -1,
                    "corrected_answer": f"{PRODUCT} {COLOR} {CAP} {NO_MW}",
                    "evidence_source": f"upload://synthetic-QA-HO-11SEP26.txt",
                    "submitted_by": "handoff-qa",
                },
                timeout=60.0,
                trust_env=False,
            )
            fb_body = fb.json() if fb.headers.get("content-type", "").startswith("application/json") else {"raw": fb.text[:400]}
            record(
                {
                    "id": "F01",
                    "level": "L3",
                    "status": "PASS" if fb.status_code == 200 and (fb_body.get("candidate_id") or fb_body.get("id")) else "INCOMPLETE",
                    "status_code": fb.status_code,
                    "response": redact(fb_body),
                    "notes": ["feedback creates candidate; not auto-publish"],
                }
            )

        if health_body.get("vision_enabled"):
            from PIL import Image, ImageDraw, ImageFont
            import base64
            import io

            img = Image.new("RGB", (640, 200), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 40)
            except OSError:
                font = ImageFont.load_default()
            marker = "QA-HO-VISION"
            draw.text((20, 70), marker, fill=(0, 0, 0), font=font)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png = buf.getvalue()
            (LIVE / "j01.png").write_bytes(png)
            image = {
                "mime_type": "image/png",
                "data_base64": base64.b64encode(png).decode("ascii"),
            }
            status_code, duration, body, error = chat(
                demo,
                "j01-" + uuid.uuid4().hex[:8],
                "what printed text is on this image? do not invent a SKU.",
                image=image,
            )
            add_cost("J01", duration, "model")
            ans = str(body.get("answer") or "")
            record(
                {
                    "id": "J01",
                    "level": "L3",
                    "status": "PASS" if marker in ans and "AF50" not in ans else "INCOMPLETE",
                    "status_code": status_code,
                    "duration_ms": duration,
                    "answer": ans,
                    "vision_status": body.get("vision_status"),
                    "vision_model": body.get("vision_model"),
                }
            )


if __name__ == "__main__":
    main()
