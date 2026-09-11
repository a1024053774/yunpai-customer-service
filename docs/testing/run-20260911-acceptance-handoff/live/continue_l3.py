"""Continue remaining L3 cases. Do not overwrite round1 file. Tight quota detector."""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

RUN = Path(__file__).resolve().parents[1]
LIVE = Path(__file__).resolve().parent
RUNTIME = json.loads((RUN / "runtime.json").read_text(encoding="utf-8"))
ROUND1 = json.loads((LIVE / "live-results-round1.json").read_text(encoding="utf-8"))
DEMO = RUNTIME["demo_url"]
DATA_DIR = Path(RUNTIME["data_dir"])
API = f"http://{RUNTIME['host_api']['listen']}" if RUNTIME.get("host_api", {}).get("started") else None
CREDS_NAME = ".host-api-creds.json"
PRODUCT = "QA-HO-11SEP26"
COLOR = "\u7c73\u767d"
CAP = "5L"
NO_MW = "\u4e0d\u53ef\u5fae\u6ce2"
YES_MW = "\u53ef\u4ee5\u5fae\u6ce2"
CAN_MW = "\u80fd\u5fae\u6ce2"
AF50 = "AF50"
RECEIPT = "HO-RCPT-11SEP26"
SECRET_KEY_RE = re.compile(r"(key|secret|token|password|authorization|credential)", re.I)
STOCK_RE = re.compile(r"(?<!\d)(\d{2,6})\s*(\u4ef6|\u53f0|\u4e2a|\u76d2)")
QUOTA_RE = re.compile(
    r"(quota exceeded|insufficient_quota|rate.?limit exceeded|invalid api key|401 unauthorized)",
    re.I,
)

results = [c for c in ROUND1["cases"] if c.get("id") not in {
    "B04", "D01", "D02", "G07", "L01", "B08-typo"
}]
cost = json.loads((RUN / "cost-round1.json").read_text(encoding="utf-8")) if (RUN / "cost-round1.json").is_file() else {
    "run_id": "run-20260911-acceptance-handoff",
    "currency": "CNY-unknown",
    "model_calls": 0,
    "http_ms_total": 0,
    "items": [],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(obj):
    if isinstance(obj, dict):
        return {k: "<redacted>" if SECRET_KEY_RE.search(str(k)) else redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def save() -> None:
    (LIVE / "live-results.json").write_text(
        json.dumps(
            {
                "saved_utc": utc_now(),
                "run_id": "run-20260911-acceptance-handoff",
                "continued_from": "live-results-round1.json",
                "quota_stop": False,
                "oracle": ROUND1["oracle"],
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
    print(json.dumps({"id": case.get("id"), "status": case.get("status"), "http": case.get("status_code"), "ms": case.get("duration_ms")}), flush=True)


def lookup(message_id: str | None):
    if not message_id:
        return None
    db = DATA_DIR / "agent.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, role, content, intent, risk_level, route_reason, sources_json, trace_id, model_fallback FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def used_synthetic(body: dict, persisted: dict | None) -> bool:
    blob = json.dumps(body.get("sources") or [], ensure_ascii=False) + " " + (body.get("answer") or "")
    if persisted:
        blob += " " + str(persisted.get("sources_json") or "")
    return PRODUCT in blob or RECEIPT in blob or "synthetic-QA-HO" in blob


def chat(session_id: str, message: str, timeout: float = 180.0, image: dict | None = None):
    started = time.monotonic()
    payload = {"session_id": session_id, "message": message}
    if image is not None:
        payload["image"] = image
    try:
        resp = httpx.post(f"{DEMO}/api/chat", json=payload, timeout=timeout, trust_env=False)
        duration = round((time.monotonic() - started) * 1000)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text[:2000]}
        body = redact(body)
        hard_quota = resp.status_code == 429 or (resp.status_code == 401 and QUOTA_RE.search(json.dumps(body)))
        return resp.status_code, duration, body if isinstance(body, dict) else {"raw": body}, None, hard_quota
    except Exception as exc:
        duration = round((time.monotonic() - started) * 1000)
        return None, duration, {}, f"{type(exc).__name__}: {exc}", False


def add_cost(case_id: str, ms: int) -> None:
    cost["http_ms_total"] += ms or 0
    cost["model_calls"] += 1
    cost["items"].append({"id": case_id, "ms": ms, "kind": "model"})


def main() -> None:
    save()
    specs = [
        ("B04", "\u548c\u7ade\u54c1\u6bd4\u4f18\u52bf\u662f\u4ec0\u4e48", "competitor"),
        ("D01", f"{PRODUCT} \u989c\u8272\u548c\u5bb9\u91cf\uff1f", "fact"),
        ("D02", f"{PRODUCT} \u5e93\u5b58\u3001\u9500\u91cf\u548c\u51e0\u5929\u5230\u8d26\uff1f", "missing"),
        ("G07", f"{PRODUCT} \u80fd\u653e\u5fae\u6ce2\u7089\u5417\uff1f", "mw"),
        ("L01", f"\u67e5\u4e00\u4e0b {PRODUCT}", "id"),
        ("B08-typo", f"{PRODUCT} \u989cse \u548c rongliang\uff1f", "typo"),
    ]
    for cid, message, kind in specs:
        sid = cid.lower().replace("-", "") + "-" + uuid.uuid4().hex[:8]
        status_code, duration, body, error, hard_quota = chat(sid, message)
        add_cost(cid, duration)
        if hard_quota:
            record({"id": cid, "status": "BLOCKED", "notes": ["hard 429/401 quota"], "duration_ms": duration})
            continue
        persisted = lookup(body.get("message_id") if isinstance(body, dict) else None)
        ans = str(body.get("answer") or "")
        synth = used_synthetic(body, persisted) if body else False
        notes: list[str] = []
        status = "INCOMPLETE"
        if error or status_code != 200:
            status = "BLOCKED"
            notes.append(error or f"http {status_code}")
        elif kind == "competitor":
            fabricated = any(x in ans for x in ("Philips", "\u82cf\u6cca\u5c14", "\u7ade\u54c1X"))
            missing = any(x in ans for x in ("\u6ca1\u6709", "\u672a\u63d0\u4f9b", "\u65e0\u6cd5", "\u8d44\u6599\u4e0d"))
            status = "FAIL" if fabricated else ("PASS" if missing or "\u7ade\u54c1" in ans else "INCOMPLETE")
        elif kind == "fact":
            status = "PASS" if CAP in ans and COLOR in ans and synth else "FAIL"
        elif kind == "missing":
            invented = bool(STOCK_RE.search(ans) and ("\u5e93\u5b58" in ans or "\u9500\u91cf" in ans))
            for needle in ("\u4ef6\u5e93\u5b58", "\u9500\u91cf\u4e3a", "\u4e24\u5929\u5230\u8d26"):
                if needle in ans:
                    invented = True
            missing_ok = any(token in ans for token in ("\u4e0d\u8bb0\u8f7d", "\u6ca1\u6709\u8bb0\u8f7d", "\u672a\u8bb0\u8f7d", "\u8d44\u6599\u6ca1\u6709", "\u65e0\u6cd5\u786e\u8ba4", "\u6ca1\u6709\u63d0\u4f9b", "\u4e0d\u80fd\u786e\u8ba4"))
            if invented:
                status = "FAIL"
            elif not synth:
                status = "INCOMPLETE"
                notes.append("did not retrieve synthetic")
            elif missing_ok:
                status = "PASS"
            else:
                status = "INCOMPLETE"
        elif kind == "mw":
            bad = YES_MW in ans or CAN_MW in ans
            good = NO_MW in ans or "\u7981\u6b62\u653e\u5165\u5fae\u6ce2" in ans
            if bad:
                status = "FAIL"
            elif good and synth:
                status = "PASS"
            elif good:
                status = "INCOMPLETE"
            else:
                status = "FAIL"
        elif kind == "id":
            trap = AF50 in ans or "\u6674\u5ddd" in ans
            status = "PASS" if CAP in ans and COLOR in ans and synth and not trap else "FAIL"
            if trap:
                notes.append("Qingchuan/AF50 trap")
        elif kind == "typo":
            status = "PASS" if CAP in ans and COLOR in ans else "INCOMPLETE"
            notes.append("typo slice only")
        record(
            {
                "id": cid,
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
                "message_id": body.get("message_id"),
                "used_synthetic": synth,
                "notes": notes,
                "error": error,
            }
        )

    c01_sid = "c01-" + uuid.uuid4().hex[:10]
    _, d1, b1, e1, _ = chat(c01_sid, f"{PRODUCT} \u662f\u4ec0\u4e48\u989c\u8272\u548c\u5bb9\u91cf\uff1f")
    add_cost("C01-turn1", d1)
    _, d2, b2, e2, _ = chat(c01_sid, "\u8fd9\u4e2a\u989c\u8272\u786e\u8ba4\u4e00\u4e0b")
    add_cost("C01-turn2", d2)
    ans2 = str(b2.get("answer") or "")
    asked_which = ("\u54ea\u6b3e" in ans2) or ("\u54ea\u4e2a\u5546\u54c1" in ans2)
    persisted = lookup(b2.get("message_id") if isinstance(b2, dict) else None)
    synth = used_synthetic(b2, persisted) if b2 else False
    ok = COLOR in ans2 and not asked_which
    record(
        {
            "id": "C01",
            "level": "L3",
            "status": "FAIL" if asked_which or not ok else "PASS",
            "duration_ms": d1 + d2,
            "first": redact(b1),
            "second": redact(b2),
            "used_synthetic": synth,
            "notes": ["this-run re-probe; do not revert REVIEW_PASS"],
        }
    )

    started = time.monotonic()
    try:
        with httpx.stream(
            "POST",
            f"{DEMO}/api/chat/stream",
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
        add_cost("K-sse", duration)
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
            }
        )
    except Exception as exc:
        record({"id": "K01-sse", "status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"})

    cred_path = DATA_DIR / CREDS_NAME
    if API and cred_path.is_file():
        creds = json.loads(cred_path.read_text(encoding="utf-8"))
        headers = {
            "X-Client-Id": creds["client_id"],
            "X-Client-Key": creds["client_key"],
            "X-Subject-Id": "handoff-buyer-1",
        }
        idem = "idem-" + uuid.uuid4().hex
        msg = {"session_id": "api-" + uuid.uuid4().hex[:10], "message": f"{PRODUCT} {COLOR}\uff1f"}
        r1 = httpx.post(f"{API}/v1/chat", json=msg, headers={**headers, "Idempotency-Key": idem}, timeout=180.0, trust_env=False)
        r2 = httpx.post(f"{API}/v1/chat", json=msg, headers={**headers, "Idempotency-Key": idem}, timeout=180.0, trust_env=False)
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
                "notes": ["creds not copied into evidence"],
            }
        )
        conflict = httpx.post(
            f"{API}/v1/chat",
            json={**msg, "message": "different " + uuid.uuid4().hex},
            headers={**headers, "Idempotency-Key": idem},
            timeout=60.0,
            trust_env=False,
        )
        preview = conflict.text[:300]
        ok = conflict.status_code in {409, 422, 400} or "conflict" in preview.lower() or "idempotency" in preview.lower()
        record(
            {
                "id": "K05-idempotency-conflict",
                "level": "L3",
                "status": "PASS" if ok else "INCOMPLETE",
                "status_code": conflict.status_code,
                "body_preview": preview,
            }
        )

    fb_sid = "fb-" + uuid.uuid4().hex[:10]
    _, duration, body, error, _ = chat(fb_sid, f"{PRODUCT} {CAP}\uff1f")
    add_cost("F01-chat", duration)
    mid = body.get("message_id")
    if mid:
        fb = httpx.post(
            f"{DEMO}/api/feedback",
            json={
                "message_id": mid,
                "rating": -1,
                "corrected_answer": f"{PRODUCT} {COLOR} {CAP} {NO_MW}",
                "evidence_source": "upload://synthetic-QA-HO-11SEP26.txt",
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
            }
        )

    health = httpx.get(f"{DEMO}/api/health", timeout=30.0, trust_env=False).json()
    if health.get("vision_enabled"):
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
        image = {"mime_type": "image/png", "data_base64": base64.b64encode(png).decode("ascii")}
        status_code, duration, body, error, _ = chat(
            "j01-" + uuid.uuid4().hex[:8],
            "what printed text is on this image? do not invent a SKU.",
            image=image,
        )
        add_cost("J01", duration)
        ans = str(body.get("answer") or "")
        record(
            {
                "id": "J01",
                "level": "L3",
                "status": "PASS" if marker in ans and AF50 not in ans else "INCOMPLETE",
                "status_code": status_code,
                "duration_ms": duration,
                "answer": ans,
                "vision_status": body.get("vision_status"),
                "vision_model": body.get("vision_model"),
            }
        )


if __name__ == "__main__":
    main()
