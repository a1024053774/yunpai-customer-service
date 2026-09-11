"""Reproduce the remaining crash-recovery gap without production I/O."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from conftest import make_settings
from customer_service_fixtures import build_core, principal_for_core
from yunpai_customer_service.database import SessionScopeError


def main(output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="yunpai-k04-crash-") as scratch:
        data_dir = Path(scratch)
        settings = make_settings(data_dir)
        owner = build_core(data_dir, settings=settings)
        principal = principal_for_core(owner)
        internal = owner.db.resolve_session(
            tenant_id=principal.tenant_id,
            client_id=principal.client_id,
            external_session_id="k04-crash-recovery",
            subject_hash=principal.subject_hash,
            source_type="api",
            source_reference="crash-red",
        )
        safe_message, _, trusted_context, image_digest = owner._prepare_chat_content(
            principal, "尺码怎么选", {}, None
        )
        invocation = owner.prepare_invocation(
            principal=principal,
            internal_session_id=internal,
            idempotency_key="k04-crash-recovery-1",
            safe_message=safe_message,
            trusted_context=trusted_context,
            execution_mode="live",
            image_digest=image_digest,
        )
        owner.close()

        restarted = build_core(data_dir, settings=make_settings(data_dir))
        restarted_principal = principal_for_core(restarted)
        started = time.monotonic()
        error = None
        try:
            restarted.chat(
                restarted_principal,
                "k04-crash-recovery",
                "尺码怎么选",
                idempotency_key="k04-crash-recovery-1",
                source_type="api",
                source_reference="crash-red",
            )
        except SessionScopeError as exc:
            error = {
                "type": type(exc).__name__,
                "code": exc.code,
                "message": str(exc),
            }
        elapsed = round(time.monotonic() - started, 3)
        with restarted.db.connect() as conn:
            row = dict(conn.execute("SELECT status, last_error FROM agent_invocations").fetchone())
        restarted.close()
    result = {
        "status": (
            "INCOMPLETE"
            if error
            and error["code"] == "idempotency_in_progress"
            and row["status"] == "running"
            and row["last_error"] is None
            else "UNEXPECTED"
        ),
        "invocation_created": invocation["id"],
        "restart_error": error,
        "elapsed_seconds": elapsed,
        "after_state": row,
        "expected_next_step": "define and test an explicit crash-owner recovery/lease policy",
        "scope": "isolated L1; no production or external business writes",
    }
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "INCOMPLETE" else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output)
