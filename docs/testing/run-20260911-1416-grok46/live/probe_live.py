"""Live L2 semantic probes. No secrets in output. DATA_DIR must be /tmp."""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from customer_service_fixtures import principal_for_core  # noqa: E402
from yunpai_customer_service.config import Settings  # noqa: E402
from yunpai_customer_service.customer_service.core import CustomerServiceCore  # noqa: E402
from yunpai_customer_service.database import Database  # noqa: E402
from yunpai_customer_service.knowledge_seed import seed_records  # noqa: E402


def refuse_workspace(data_dir: Path) -> None:
    ws_data = (WORKSPACE / "data").resolve()
    resolved = data_dir.resolve()
    if resolved == ws_data or (WORKSPACE in resolved.parents and resolved.name == "data"):
        raise SystemExit("refusing to use workspace data/; set DATA_DIR under /tmp")
    if not (str(resolved).startswith("/tmp") or str(resolved).startswith("/private/tmp")):
        raise SystemExit("DATA_DIR must be under /tmp")


def pack(resp) -> dict:
    return {
        "answer": resp.answer,
        "sources": [s.source for s in resp.sources],
        "requires_human": resp.requires_human,
        "reason": getattr(resp, "reason", None),
        "message_id": resp.message_id,
    }


def main() -> None:
    os.environ.setdefault("BOOTSTRAP_CLIENT_KEY", secrets.token_hex(16))
    os.environ.setdefault("SUBJECT_HASH_KEY", secrets.token_hex(16))
    os.environ.setdefault("ADMIN_API_KEY", secrets.token_hex(16))
    os.environ["KG_IMPORT_ENABLED"] = "false"
    os.environ["KG_DREAM_WORKER_ENABLED"] = "false"
    os.environ.setdefault("MODEL_RETRY_ATTEMPTS", "0")
    settings = Settings.from_env()
    refuse_workspace(settings.data_dir)
    settings.ensure_directories()
    db = Database(settings.app_db_path)
    db.initialize()
    core = CustomerServiceCore.build(db, settings)
    core.knowledge.seed_if_empty(seed_records())
    core.handoffs.ensure_default_queues(settings.bootstrap_tenant_id)
    principal = principal_for_core(core, "live-1416")
    tid = principal.tenant_id
    nonce = "QA-1416-ALPHA"
    nonce_b = "QA-1416-BRAVO"
    core.knowledge.add_document(
        category="product",
        intent="product",
        question=f"{nonce} color capacity",
        answer=f"{nonce} is rice-white, capacity 5L, not microwave-safe.",
        keywords=f"{nonce} color capacity rice-white 5L",
        risk_level="low",
        source="fixture:live-alpha",
        tenant_id=tid,
    )
    core.knowledge.add_document(
        category="product",
        intent="product",
        question=f"{nonce_b} color capacity",
        answer=f"{nonce_b} is black, capacity 7L, microwave-safe lid only.",
        keywords=f"{nonce_b} color capacity black 7L",
        risk_level="low",
        source="fixture:live-bravo",
        tenant_id=tid,
    )
    core.knowledge.add_document(
        category="policy",
        intent="product",
        question="shipping fee and return conditions",
        answer="Shipping is 12 CNY in-city. Returns allowed within 7 days if unused; opened food jars are excluded.",
        keywords="shipping freight return refund conditions",
        risk_level="low",
        source="fixture:live-policy",
        tenant_id=tid,
    )
    d10_id = core.knowledge.add_document(
        category="product",
        intent="product",
        question="QA-1416-D10 5L headline",
        answer="QA-1416-D10 body fact: capacity is 7L black. The title 5L is wrong and must not be used.",
        keywords="QA-1416-D10 5L",
        risk_level="low",
        source="fixture:live-d10",
        tenant_id=tid,
    )
    cases = []

    r1 = core.chat(principal, "b07", f"tell me about {nonce}")
    r2 = core.chat(principal, "b07", f"now I mean {nonce_b} only, ignore {nonce}. what color and capacity?")
    b07_ok = nonce_b in r2.answer and "7L" in r2.answer and not (
        nonce in r2.answer and "5L" in r2.answer and nonce_b not in r2.answer
    )
    hijack = nonce in r2.answer and nonce_b not in r2.answer
    cases.append(
        {
            "id": "B07",
            "status": "FAIL" if hijack else ("PASS" if b07_ok else "INCOMPLETE"),
            "level": "L2",
            "actual": {"first": pack(r1), "second": pack(r2), "hijack": hijack},
            "notes": ["live model; current BRAVO must override ALPHA history"],
        }
    )

    r9 = core.chat(
        principal,
        "b09",
        "first tell shipping fee, then return conditions. do not expand into a refund.",
    )
    has_ship = "12" in r9.answer or "shipping" in r9.answer.lower() or "freight" in r9.answer.lower()
    has_ret = "7 day" in r9.answer.lower() or "return" in r9.answer.lower()
    claimed_refund = "already refund" in r9.answer.lower() or "refunded" in r9.answer.lower()
    cases.append(
        {
            "id": "B09",
            "status": "FAIL" if claimed_refund else ("PASS" if has_ship and has_ret else "INCOMPLETE"),
            "level": "L2",
            "actual": {"resp": pack(r9), "has_ship": has_ship, "has_ret": has_ret, "claimed_refund": claimed_refund},
        }
    )

    r10 = core.chat(principal, "d10", "QA-1416-D10 capacity?")
    says_5_as_fact = "5L" in r10.answer and "7L" not in r10.answer
    says_7 = "7L" in r10.answer
    cases.append(
        {
            "id": "D10",
            "status": "FAIL" if says_5_as_fact else ("PASS" if says_7 else "INCOMPLETE"),
            "level": "L2",
            "actual": {"resp": pack(r10), "says_5_as_fact": says_5_as_fact, "says_7": says_7, "doc": d10_id},
        }
    )

    pref = core.memory.record(
        "store-h02",
        fact="customer prefers rice-white only",
        category="buyer_preference",
        tenant_id=tid,
        subject_hash=principal.subject_hash,
    )
    rh = core.chat(
        principal,
        "h02",
        f"this time I want {nonce_b} black, do not use my rice-white preference",
        {"store_id": "store-h02"},
    )
    prefers_old = "rice-white" in rh.answer.lower() and "black" not in rh.answer.lower()
    cases.append(
        {
            "id": "H02",
            "status": "FAIL" if prefers_old else ("PASS" if "black" in rh.answer.lower() else "INCOMPLETE"),
            "level": "L2",
            "actual": {"pref_id": pref, "resp": pack(rh), "prefers_old": prefers_old},
        }
    )

    rb = core.chat(principal, "b08", f"hei, {nonce} colr? capcacity?? thx")
    cases.append(
        {
            "id": "B08",
            "status": "PASS" if nonce in rb.answer or "5L" in rb.answer or "rice-white" in rb.answer.lower() else "INCOMPLETE",
            "level": "L2",
            "actual": {"resp": pack(rb)},
            "notes": ["typo bucket only; not a full language matrix"],
        }
    )

    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": "run-20260911-1416-grok46",
        "level": "L2-live",
        "data_dir": str(settings.data_dir),
        "model_name": settings.model_name,
        "model_enabled": settings.model_enabled,
        "model_mock": settings.model_mock_mode,
        "embedding": settings.rag_embedding_provider,
        "cases": cases,
    }
    (EVIDENCE / "live.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({c["id"]: c["status"] for c in cases}, ensure_ascii=False, indent=2))
    core.close()


if __name__ == "__main__":
    main()
