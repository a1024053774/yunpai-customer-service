"""Executable remaining L1 probes. ASCII source; UTF-8 evidence."""
from __future__ import annotations

import json
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
from pydantic import ValidationError  # noqa: E402

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import (  # noqa: E402
    TABLE_MODEL_ANSWER,
    TableDrivenModel,
    build_core,
    principal_for_core,
)
from yunpai_customer_service.demo.app import DemoChatRequest, create_app  # noqa: E402
from yunpai_customer_service.policy import review_output  # noqa: E402

cases: list[dict] = []


def record(case: dict) -> None:
    cases.append(case)
    (EVIDENCE / "cases.json").write_text(
        json.dumps(
            {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "run_id": "run-20260911-0131-grok46",
                "level": "L0/L1",
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"id": case["id"], "status": case["status"]}, ensure_ascii=False), flush=True)


def add_store_doc(core, *, key: str, answer: str, store_id: str, question: str = "QA-D03 kettle color") -> str:
    return core.knowledge.add_document(
        category="product",
        intent="product",
        question=question,
        answer=answer,
        keywords=question,
        risk_level="low",
        source="fixture:" + key,
        tenant_id=core.settings.bootstrap_tenant_id,
        knowledge_key=key,
        store_id=store_id,
    )


def probe_a02(tmp: Path) -> None:
    settings = make_settings(tmp)
    model = TableDrivenModel(settings)
    core = build_core(tmp, settings=settings, model=model, seed_knowledge=True)
    import yunpai_customer_service.graph as graph

    original = graph.review_output

    def always_reject(draft, evidence):
        return False, "forced_verify_reject"

    graph.review_output = always_reject
    try:
        principal = principal_for_core(core, "a02-user")
        sync = core.chat(principal, "a02-session-aaaa", "what is the capacity?")
        leaked = TABLE_MODEL_ANSWER in (sync.answer or "")
        record(
            {
                "id": "A02",
                "priority": "P1",
                "level": "L1",
                "status": "PASS" if not leaked else "FAIL",
                "expected": "forced verify reject never ships unaudited draft",
                "actual": {
                    "answer": sync.answer,
                    "reason": getattr(sync, "reason", None) or getattr(sync, "route_reason", None),
                    "requires_human": sync.requires_human,
                    "leaked_table_draft": leaked,
                },
                "notes": [
                    "core L1 only; host/Demo/cache-replay not executed",
                    "monkeypatched graph.review_output to always reject",
                ],
            }
        )
    finally:
        graph.review_output = original
        core.close()


def probe_g04(tmp: Path) -> None:
    settings = make_settings(tmp)
    model = TableDrivenModel(settings)
    core = build_core(tmp, settings=settings, model=model, seed_knowledge=True)
    import yunpai_customer_service.graph as graph

    original = graph.review_output

    def boom(draft, evidence):
        raise RuntimeError("forced_verify_timeout")

    graph.review_output = boom
    try:
        principal = principal_for_core(core, "g04-user")
        raised = False
        answer = ""
        reason = ""
        try:
            sync = core.chat(principal, "g04-session-aaaa", "what is the capacity?")
            answer = sync.answer
            reason = str(getattr(sync, "route_reason", None) or getattr(sync, "reason", None))
        except Exception as exc:
            raised = True
            reason = f"{type(exc).__name__}: {exc}"
        leaked = TABLE_MODEL_ANSWER in (answer or "")
        status = "FAIL" if leaked else ("INCOMPLETE" if raised else "PASS")
        record(
            {
                "id": "G04",
                "priority": "P1",
                "level": "L1",
                "status": status,
                "expected": "verify error/timeout does not emit risky draft; explicit fail or safe degrade",
                "actual": {
                    "raised_to_caller": raised,
                    "answer": answer,
                    "reason": reason,
                    "leaked_table_draft": leaked,
                },
                "notes": [
                    "INCOMPLETE if exception escapes without classified degrade",
                    "PASS only if no draft leak and caller gets a handled response",
                ],
            }
        )
    finally:
        graph.review_output = original
        core.close()


def probe_d03_store(tmp: Path) -> None:
    settings = make_settings(tmp)
    core = build_core(tmp, settings=settings, model=TableDrivenModel(settings), seed_knowledge=False)
    add_store_doc(core, key="d03-store-a1", answer="store A1 rice-white 5L", store_id="store-a1")
    add_store_doc(core, key="d03-store-a2", answer="store A2 black 7L", store_id="store-a2")
    kwargs = {
        "top_k": 5,
        "min_score": 0.01,
        "intent": "product",
        "tenant_id": core.settings.bootstrap_tenant_id,
    }
    hits_a1 = core.knowledge.retrieve("QA-D03 kettle color", store_id="store-a1", **kwargs)
    hits_missing = core.knowledge.retrieve("QA-D03 kettle color", store_id=None, **kwargs)
    hits_forged = core.knowledge.retrieve("QA-D03 kettle color", store_id="store-forged", **kwargs)
    a1_answers = [h["answer"] if isinstance(h, dict) else h.answer for h in hits_a1]
    missing_answers = [h["answer"] if isinstance(h, dict) else h.answer for h in hits_missing]
    forged_answers = [h["answer"] if isinstance(h, dict) else h.answer for h in hits_forged]
    a1_ok = any("store A1" in a for a in a1_answers) and not any("store A2" in a for a in a1_answers)
    missing_ok = not any("store A1" in a or "store A2" in a for a in missing_answers)
    forged_ok = not any("store A1" in a or "store A2" in a for a in forged_answers)
    record(
        {
            "id": "D03",
            "priority": "P0",
            "level": "L1",
            "status": "PASS" if (a1_ok and missing_ok and forged_ok) else "FAIL",
            "expected": "same-name docs stay in authorized store; missing/forged store_id cannot read shop rows",
            "actual": {
                "store_a1": a1_answers,
                "missing_store_id": missing_answers,
                "forged_store_id": forged_answers,
                "a1_ok": a1_ok,
                "missing_ok": missing_ok,
                "forged_ok": forged_ok,
            },
            "notes": ["retrieve() contract. Chat-path host binding remains N04/I06."],
        }
    )
    core.close()


def probe_i06(tmp: Path) -> None:
    settings = make_settings(tmp)
    model = TableDrivenModel(settings, answer="SECRET-I06-419-ONLY-STORE-B")
    core = build_core(tmp, settings=settings, model=model, seed_knowledge=False)
    add_store_doc(
        core,
        key="i06-secret",
        question="secret shop price",
        answer="SECRET-I06-419-ONLY-STORE-B",
        store_id="store-b",
    )
    principal = principal_for_core(core, "i06-user")
    resp = core.chat(
        principal,
        "i06-session-aaaa",
        "secret shop price",
        context={"store_id": "store-b", "order_id": "ORDER-NOT-THEIRS"},
    )
    sources_blob = json.dumps(
        [s if isinstance(s, dict) else getattr(s, "__dict__", str(s)) for s in (resp.sources or [])],
        ensure_ascii=False,
    )
    leaked_via_forged_store = "SECRET-I06-419-ONLY-STORE-B" in sources_blob
    order_kept = "ORDER-NOT-THEIRS" in json.dumps(getattr(resp, "context", {}) or {}, ensure_ascii=False)
    demo_rejects_context = False
    try:
        DemoChatRequest(session_id="i06-demo-aa", message="hi", context={"store_id": "store-b"})
    except ValidationError:
        demo_rejects_context = True
    # Demo customer cannot send context. Host API can. Core keeps store_id for any principal.
    status = "PASS" if demo_rejects_context and not order_kept else "INCOMPLETE"
    if leaked_via_forged_store:
        status = "FAIL"
    record(
        {
            "id": "I06",
            "priority": "P0",
            "level": "L1",
            "status": status,
            "expected": "customer cannot escalate store/order via request; host must bind store",
            "actual": {
                "demo_chat_rejects_context_field": demo_rejects_context,
                "forged_store_reached_sources": leaked_via_forged_store,
                "forged_order_id_kept": order_kept,
                "answer": resp.answer,
                "sources": sources_blob[:500],
                "can_supply_order_context": principal.can_supply_order_context,
            },
            "notes": [
                "Demo /api/chat schema forbids client context (store bound server-side).",
                "Host /v1/chat forwards payload.context; store_id is allowed and not stripped.",
                "Real same-tenant unauthorized shop mapping needs N04 site login.",
            ],
        }
    )
    core.close()


def probe_i05(tmp: Path) -> None:
    settings = make_settings(tmp)
    app = create_app(settings)
    with TestClient(app) as client:
        runtime = client.app.state.runtime
        root = runtime.settings.data_dir / "knowledge_uploads"
        root.mkdir(parents=True, exist_ok=True)
        digest = "a" * 16
        other = root / (digest + "-catalog.pdf")
        other.write_bytes(b"%PDF-1.4 other-tenant")
        runtime.core.knowledge.add_document(
            category="uploaded_document",
            intent="product",
            question="catalog",
            answer="OTHER-TENANT-ORIGINAL",
            keywords="catalog",
            risk_level="low",
            source=f"upload://catalog.pdf?sha256={digest}#p1",
            tenant_id="other-tenant-i05",
            knowledge_key="other-catalog",
        )
        listed = client.get("/api/knowledge/files").json()
        other_get = client.get("/api/knowledge/files/" + other.name)
        names = [item.get("name") for item in listed.get("items", [])]
    record(
        {
            "id": "I05",
            "priority": "P0",
            "level": "L1",
            "status": "PASS" if other.name not in names and other_get.status_code == 404 else "FAIL",
            "expected": "same-name original of another tenant is not listed or downloaded",
            "actual": {
                "listed": names,
                "other_get": other_get.status_code,
                "other_name": other.name,
            },
            "notes": [
                "same filename catalog.pdf; digest prefix differs",
                "own-file positive download not claimed",
            ],
        }
    )


def probe_i11(tmp: Path) -> None:
    settings = make_settings(tmp)
    core = build_core(tmp, settings=settings, model=TableDrivenModel(settings), seed_knowledge=False)
    principal = principal_for_core(core, "i11-user")
    payload = "<script>alert(1)</script> SELECT * FROM messages"
    resp = core.chat(principal, "i11-session-aaaa", payload)
    passed, reason = review_output("<script>alert(1)</script>", "")
    record(
        {
            "id": "I11",
            "priority": "P1",
            "level": "L1",
            "status": "INCOMPLETE",
            "expected": "HTML/script/SQL in message are not executed; display escaped",
            "actual": {
                "chat_returned": bool(resp.answer),
                "review_script": {"passed": passed, "reason": reason},
                "answer_preview": (resp.answer or "")[:200],
            },
            "notes": [
                "core does not execute HTML; not XSS proof of Demo page",
                "browser CSP/escape not run",
            ],
        }
    )
    core.close()


def probe_g05_g06() -> None:
    ordinal = (
        "\u8bf7\u8865\u5145\uff1a1\uff09\u8ba2\u5355\u53f7\uff1b2\uff09\u578b\u53f7\uff1b3\uff09\u6545\u969c\u73b0\u8c61\u3002"
    )
    money = "\u9000\u6b3e\u6bd4\u4f8b\u4e3a 95%\uff0c\u4ef7\u683c 1.99 \u5143\u3002"
    ord_pass, ord_reason = review_output(ordinal, "")
    money_pass, money_reason = review_output(money, "")
    record(
        {
            "id": "G05",
            "priority": "P1",
            "level": "L1",
            "status": "PASS" if ord_pass else "FAIL",
            "expected": "legal list ordinals allowed",
            "actual": {"passed": ord_pass, "reason": ord_reason},
            "notes": ["review_output helper; not full SSE persist"],
        }
    )
    record(
        {
            "id": "G06",
            "priority": "P1",
            "level": "L1",
            "status": "PASS"
            if (not money_pass and money_reason == "numeric_claim_without_evidence")
            else "FAIL",
            "expected": "unevidenced 1.99 / 95% blocked",
            "actual": {"passed": money_pass, "reason": money_reason},
            "notes": ["review_output helper; 24h claim not included"],
        }
    )


def probe_j05(tmp: Path) -> None:
    from yunpai_customer_service.schemas import MAX_CHAT_IMAGE_BYTES

    settings = make_settings(tmp)
    record(
        {
            "id": "J05",
            "priority": "P1",
            "level": "L1",
            "status": "INCOMPLETE",
            "expected": "5 MiB N-1/N/N+1 rejected consistently",
            "actual": {
                "max_request_body_bytes": settings.max_request_body_bytes,
                "MAX_CHAT_IMAGE_BYTES": MAX_CHAT_IMAGE_BYTES,
                "test_settings_body_limit_below_5mib": settings.max_request_body_bytes < MAX_CHAT_IMAGE_BYTES,
            },
            "notes": [
                "schema constant is 5 MiB; existing tests cover MIME mismatch",
                "no decoded 5MiB image posted this run",
            ],
        }
    )


def probe_h06(tmp: Path) -> None:
    settings = make_settings(tmp)
    core = build_core(tmp, settings=settings, model=TableDrivenModel(settings), seed_knowledge=False)
    memory_id = core.memory.record(
        "store-h06",
        fact="EXPIRED-COLOR-SHOULD-NOT-RECALL",
        tenant_id=core.settings.bootstrap_tenant_id,
        ttl_days=1,
    )
    with core.db._write_lock, core.db.connect() as conn:
        conn.execute(
            "UPDATE knowledge SET effective_to='2000-01-01T00:00:00+00:00' WHERE knowledge_key=?",
            (memory_id,),
        )
    recalled = core.memory.recall(
        "store-h06",
        query="EXPIRED-COLOR",
        tenant_id=core.settings.bootstrap_tenant_id,
    )
    leaked = memory_id in {row["knowledge_key"] for row in recalled} or any(
        "EXPIRED-COLOR-SHOULD-NOT-RECALL" in str(row.get("answer") or "") for row in recalled
    )
    record(
        {
            "id": "H06",
            "priority": "P1",
            "level": "L1",
            "status": "PASS" if not leaked else "FAIL",
            "expected": "expired memory is not recalled before renewal",
            "actual": {
                "memory_id": memory_id,
                "recalled_keys": [row["knowledge_key"] for row in recalled],
                "leaked": leaked,
            },
        }
    )
    core.close()


def probe_a09() -> None:
    src = WORKSPACE / "src/yunpai_customer_service"
    todos = []
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(WORKSPACE))
        for i, line in enumerate(text.splitlines(), 1):
            if "TODO" in line or "FIXME" in line:
                todos.append(f"{rel}:{i}")
    record(
        {
            "id": "A09",
            "priority": "P1",
            "level": "L0",
            "status": "INCOMPLETE",
            "expected": "unused copied config / empty impls not described as delivered",
            "actual": {"todo_count": len(todos), "todo_sample": todos[:20]},
            "notes": ["scan only; cannot PASS from grep"],
        }
    )


def main() -> None:
    try:
        probe_a09()
        probe_g05_g06()
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            probe_a02(tmp / "a02")
            probe_g04(tmp / "g04")
            probe_d03_store(tmp / "d03")
            probe_i06(tmp / "i06")
            probe_i05(tmp / "i05")
            probe_i11(tmp / "i11")
            probe_j05(tmp / "j05")
            probe_h06(tmp / "h06")
    except Exception:
        (EVIDENCE / "probe.stderr").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    (EVIDENCE / "summary.md").write_text(
        "# remaining-l1\n\n" + "\n".join(f"- {c['id']}: {c['status']}" for c in cases) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
