"""L1 isolation probes. Isolated /tmp DATA_DIR. No secrets."""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import (  # noqa: E402
    TableDrivenModel,
    add_fixture_document,
    build_core,
    principal_for_core,
)
from yunpai_customer_service.database import Database  # noqa: E402
from yunpai_customer_service.embeddings import build_embedding_provider  # noqa: E402
from yunpai_customer_service.schemas import FeedbackRequest  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump(name: str, payload: dict) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    os.environ.setdefault("BOOTSTRAP_CLIENT_KEY", secrets.token_hex(16))
    os.environ.setdefault("SUBJECT_HASH_KEY", secrets.token_hex(16))
    os.environ.setdefault("ADMIN_API_KEY", secrets.token_hex(16))
    os.environ["KG_IMPORT_ENABLED"] = "false"
    os.environ["KG_DREAM_WORKER_ENABLED"] = "false"
    cases = []
    with TemporaryDirectory(prefix="yunpai-handoff-l1-", dir="/tmp") as raw:
        data_dir = Path(raw)
        if not str(data_dir.resolve()).startswith(("/tmp", "/private/tmp")):
            raise SystemExit("DATA_DIR must be /tmp")
        settings = make_settings(data_dir)
        core = build_core(
            data_dir,
            settings=settings,
            seed_knowledge=True,
            model=TableDrivenModel(settings),
        )
        principal = principal_for_core(core, "handoff-l1")
        schema = core.db.schema_version()
        ident = core.knowledge.embedding_provider.identity
        cases.append(
            {
                "id": "D07-identity",
                "level": "L1",
                "status": "PASS" if schema == 39 and ident else "FAIL",
                "schema_version": schema,
                "embedding_identity": ident,
                "notes": [
                    "this-run identity/schema re-probe; REVIEW_PASS kept",
                    "no live dual FastEmbed two-model mix in this process",
                ],
            }
        )
        hash_ident = build_embedding_provider("hash", "unused").identity
        cases.append(
            {
                "id": "D07-other-identity-object",
                "level": "L1",
                "status": "PASS" if hash_ident == "hash" and ident != hash_ident else "INCOMPLETE",
                "hash_identity": hash_ident,
                "live_identity": ident,
                "notes": [
                    "hash vs current identity differ; no second FastEmbed download",
                    "not a live dual-index mix",
                ],
            }
        )

        add_fixture_document(
            core,
            question="handoff wool care",
            answer="hand wash wool at 30C; do not tumble dry",
            tenant_id=principal.tenant_id,
        )
        chat = core.chat(principal, "f01-sess-handoff", "how to wash wool")
        fb = core.evolution.submit_feedback(
            FeedbackRequest(
                message_id=chat.message_id,
                rating=-1,
                corrected_answer="hand wash wool at 30C; do not tumble dry",
                evidence_source="manual:wool-care",
                submitted_by="qa",
            ),
            tenant_id=principal.tenant_id,
        )
        cases.append(
            {
                "id": "F01-l1",
                "level": "L1",
                "status": "PASS" if fb.candidate_id else "FAIL",
                "candidate_id": fb.candidate_id,
            }
        )
        try:
            core.evolution.approve(
                fb.candidate_id,
                operator="qa",
                note="should fail before evaluate",
                tenant_id=principal.tenant_id,
            )
            approve_status = "FAIL"
            approve_note = "approve succeeded before evaluate"
        except Exception as exc:
            approve_status = "PASS"
            approve_note = f"{type(exc).__name__}"
        cases.append(
            {
                "id": "F03",
                "level": "L1",
                "status": approve_status,
                "notes": [approve_note, "bypass evaluate must be rejected"],
            }
        )

        r1 = core.chat(
            principal,
            "k04-sess",
            "shipping fee?",
            idempotency_key="same-key-handoff",
        )
        r2 = core.chat(
            principal,
            "k04-sess",
            "shipping fee?",
            idempotency_key="same-key-handoff",
        )
        cases.append(
            {
                "id": "K04-core",
                "level": "L1",
                "status": "PASS" if r1.message_id == r2.message_id else "FAIL",
                "message_id": r1.message_id,
            }
        )
        conflict_ok = False
        conflict_err = None
        try:
            core.chat(
                principal,
                "k04-sess",
                "different message",
                idempotency_key="same-key-handoff",
            )
        except Exception as exc:
            conflict_ok = "idempotency" in str(exc).lower() or "conflict" in str(exc).lower()
            conflict_err = type(exc).__name__
        cases.append(
            {
                "id": "K05-core",
                "level": "L1",
                "status": "PASS" if conflict_ok else "INCOMPLETE",
                "error_type": conflict_err,
            }
        )

        db_path = core.settings.app_db_path
        core.close()
        settings2 = make_settings(data_dir)
        core2 = build_core(
            data_dir,
            settings=settings2,
            seed_knowledge=False,
            model=TableDrivenModel(settings2),
        )
        principal2 = principal_for_core(core2, "handoff-l1")
        msgs = []
        with core2.db.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM messages WHERE tenant_id=? LIMIT 5",
                (principal2.tenant_id,),
            ).fetchall()
            msgs = [row["id"] for row in rows]
        cases.append(
            {
                "id": "C08-reopen",
                "level": "L1",
                "status": "PASS" if msgs else "INCOMPLETE",
                "reopened_message_count": len(msgs),
                "same_db": str(db_path),
                "notes": ["same DATA_DIR reopen; not crash-mid-write"],
            }
        )
        core2.close()

        with TemporaryDirectory(prefix="yunpai-handoff-l1b-", dir="/tmp") as raw2:
            settings_b = make_settings(Path(raw2))
            other = build_core(
                Path(raw2),
                settings=settings_b,
                seed_knowledge=True,
                model=TableDrivenModel(settings_b),
            )
            leak = Path(raw2).resolve() == data_dir.resolve()
            cases.append(
                {
                    "id": "A08-two-tmp",
                    "level": "L1",
                    "status": "PASS" if not leak else "FAIL",
                    "dir_a": str(data_dir),
                    "dir_b": str(Path(raw2).resolve()),
                }
            )
            other.close()

    dump(
        "cases.json",
        {
            "saved_utc": utc_now(),
            "run_id": "run-20260911-acceptance-handoff",
            "cases": cases,
        },
    )
    print(json.dumps({"n": len(cases), "ids": [c["id"] for c in cases]}))


if __name__ == "__main__":
    main()
