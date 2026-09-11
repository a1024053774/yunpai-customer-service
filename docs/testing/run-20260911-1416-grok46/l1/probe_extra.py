"""Additional locally executable leftover probes. ASCII source."""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from fastapi.testclient import TestClient  # noqa: E402
from conftest import make_settings  # noqa: E402
from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core  # noqa: E402
from yunpai_customer_service.demo.app import create_app  # noqa: E402
from yunpai_customer_service.knowledge_ingest import DocumentIngestError, ingest_document  # noqa: E402

cases: list[dict] = []


def dump(name: str, payload: dict) -> None:
    (EVIDENCE / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def record(case: dict) -> None:
    cases.append(case)
    dump("extra.json", {"saved_utc": datetime.now(timezone.utc).isoformat(), "cases": cases})
    print(json.dumps({"id": case["id"], "status": case["status"]}, ensure_ascii=False), flush=True)


def probe_m03(tmp: Path) -> None:
    settings = make_settings(tmp)
    core = build_core(tmp, settings=settings, model=TableDrivenModel(settings), seed_knowledge=False)
    tid = core.settings.bootstrap_tenant_id
    # parser missing / corrupt index stand-ins
    results = {}
    try:
        ingest_document(core.knowledge, filename="ok.txt", content=b"sku AAA capacity 5L", tenant_id=tid)
        results["txt_ok"] = True
    except Exception as exc:
        results["txt_ok"] = False
        results["txt_err"] = f"{type(exc).__name__}: {exc}"
    try:
        ingest_document(core.knowledge, filename="broken.pdf", content=b"%PDF-1.4 garbage", tenant_id=tid)
        results["corrupt_ok"] = True
    except DocumentIngestError as exc:
        results["corrupt_ok"] = False
        results["corrupt_err"] = str(exc)
    except Exception as exc:
        results["corrupt_ok"] = False
        results["corrupt_err"] = f"{type(exc).__name__}: {exc}"
    idx = settings.app_db_path
    # query still works after a failed ingest
    hits = core.knowledge.retrieve("sku AAA capacity", top_k=3, min_score=0.01, intent="product", tenant_id=tid)
    results["retrieve_after_fail"] = [h["id"] if isinstance(h, dict) else h.id for h in hits]
    results["db_exists"] = idx.exists()
    m03 = "PASS" if results.get("txt_ok") and results.get("corrupt_ok") is False and results["retrieve_after_fail"] else "INCOMPLETE"
    record(
        {
            "id": "M03",
            "priority": "P1",
            "level": "L1",
            "status": m03,
            "expected": "parser/corrupt ingest fails closed; existing retrieve still works; no empty-success",
            "actual": results,
            "notes": ["Docling-missing and process-crash not injected; corrupt PDF + retrieve after fail"],
        }
    )
    core.close()


def probe_i12(tmp: Path) -> None:
    settings = make_settings(tmp)
    app = create_app(settings)
    with TestClient(app) as client:
        opt = client.options("/api/chat")
        over = client.post("/api/chat", json={"session_id": "x", "message": "m" * 20000})
        burst = [client.post("/api/chat", json={"session_id": f"s{i}", "message": "hi"}).status_code for i in range(20)]
        cors = client.options(
            "/api/chat",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
    i12 = "INCOMPLETE"
    if opt.status_code in {404, 405, 403} and over.status_code in {413, 422, 400}:
        i12 = "PASS"
    record(
        {
            "id": "I12",
            "priority": "P1",
            "level": "L1",
            "status": i12,
            "expected": "OPTIONS not an open CORS grant; oversize rejected before expensive work; burst recorded",
            "actual": {
                "options": opt.status_code,
                "options_headers": dict(opt.headers),
                "oversize": over.status_code,
                "burst_codes": burst,
                "cors_preflight": cors.status_code,
                "cors_headers": {k: v for k, v in cors.headers.items() if "access-control" in k.lower() or k.lower() == "allow"},
            },
            "notes": ["Demo TestClient; not a deployed CSRF cookie matrix"],
        }
    )


def probe_f04(tmp: Path) -> None:
    settings = make_settings(tmp)
    app = create_app(settings)
    with TestClient(app) as client:
        health = client.get("/api/health")
        ev = client.get("/api/evolution/candidates")
        # no role header required on evaluate/approve in Demo
    record(
        {
            "id": "F04",
            "priority": "P0",
            "level": "L1",
            "status": "INCOMPLETE",
            "expected": "customer / other-tenant admin cannot approve",
            "actual": {
                "health": health.status_code,
                "candidates": ev.status_code,
                "demo_loopback": True,
            },
            "notes": [
                "Demo has no customer vs admin principal split on evaluate/approve",
                "not treated as production RBAC PASS; delivery gap remains",
            ],
        }
    )


def probe_k03_reconnect(tmp: Path) -> None:
    settings = make_settings(tmp)
    model = TableDrivenModel(settings)
    core = build_core(tmp, settings=settings, model=model, seed_knowledge=True)
    principal = principal_for_core(core, "k03")
    events = []
    try:
        for ev in core.chat_stream(
            principal, "k03-sess", "k03-reconnect-marker", idempotency_key="k03-abort-1"
        ):
            events.append(getattr(ev, "event", None) or ev.get("event") if isinstance(ev, dict) else type(ev).__name__)
            if (getattr(ev, "event", None) or (ev.get("event") if isinstance(ev, dict) else None)) == "delta":
                break
    except Exception as exc:
        events.append(f"err:{type(exc).__name__}")
    with core.db.connect() as conn:
        mid = [
            dict(r)
            for r in conn.execute(
                "SELECT role, content FROM messages WHERE session_id IN "
                "(SELECT id FROM sessions WHERE external_session_id=?)",
                ("k03-sess",),
            ).fetchall()
        ]
    # reconnect/replay same session
    second = list(
        core.chat_stream(
            principal, "k03-sess", "k03-after-abort", idempotency_key="k03-after-2"
        )
    )
    with core.db.connect() as conn:
        after = [
            dict(r)
            for r in conn.execute(
                "SELECT role, substr(content,1,80) AS content FROM messages WHERE session_id IN "
                "(SELECT id FROM sessions WHERE external_session_id=?) ORDER BY created_at",
                ("k03-sess",),
            ).fetchall()
        ]
        assistants = [r for r in after if r["role"] == "assistant"]
    k03 = "INCOMPLETE"
    if len(assistants) <= 2:
        k03 = "PASS"
    record(
        {
            "id": "K03",
            "priority": "P1",
            "level": "L1",
            "status": k03,
            "expected": "abort after first delta then continue; no silent double-success on same turn",
            "actual": {
                "first_events": events[:8],
                "rows_after_abort": mid,
                "assistant_count": len(assistants),
                "after": after,
            },
            "notes": ["in-process stream abort; host socket reconnect still not run"],
        }
    )
    core.close()


def main() -> None:
    with TemporaryDirectory(prefix="yunpai-1416-extra-", dir="/tmp") as raw:
        root = Path(raw)
        for fn, name in (
            (probe_m03, "m03"),
            (probe_i12, "i12"),
            (probe_f04, "f04"),
            (probe_k03_reconnect, "k03"),
        ):
            try:
                fn(root / name)
            except Exception:
                traceback.print_exc()
                record({"id": name.upper(), "status": "INCOMPLETE", "notes": ["probe crashed"], "actual": {}})
    dump("extra-summary.json", {"summary": {c["id"]: c["status"] for c in cases}})
    print(json.dumps({c["id"]: c["status"] for c in cases}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
