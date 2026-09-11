"""K06 framework re-probe: registry + graph gates. Not L4 business ledger."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, ConfigDict, Field

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core  # noqa: E402
from yunpai_customer_service.tools import (  # noqa: E402
    EmptyToolInput,
    ToolExecutionContext,
    ToolResult,
    ToolSpec,
)


class RefundInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str = Field(min_length=1, max_length=64)
    amount: int = 1


class StoreBoundInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    rows: list[dict] = []
    with TemporaryDirectory(prefix="yunpai-followup-k06-", dir="/tmp") as raw:
        data_dir = Path(raw)
        settings = make_settings(data_dir)
        executions: list[str] = []

        def refund_handler(payload: RefundInput, _ctx: ToolExecutionContext) -> ToolResult:
            executions.append(payload.order_id)
            return ToolResult(
                status="success",
                output={"order_id": payload.order_id},
                postcondition_met=True,
            )

        model = TableDrivenModel(settings)
        core = build_core(data_dir, settings=settings, model=model, seed_knowledge=True)
        try:
            core.tools.register(
                ToolSpec(
                    name="sandbox_refund",
                    description="isolated write tool",
                    kind="write",
                    input_model=RefundInput,
                    handler=refund_handler,
                    required_context_fields=("store_id",),
                    idempotency_fields=("order_id",),
                    verifier=lambda _p, result, _c: bool(result.postcondition_met),
                )
            )
            core.tools.register(
                ToolSpec(
                    name="lookup_policy",
                    description="isolated read tool",
                    kind="read",
                    input_model=EmptyToolInput,
                    handler=lambda _p, _c: ToolResult(status="success", output={"ok": True}),
                )
            )
            core.tools.register(
                ToolSpec(
                    name="store_bound_lookup",
                    description="read tool that needs store_id",
                    kind="read",
                    input_model=StoreBoundInput,
                    handler=lambda _p, _c: ToolResult(status="success", output={"ok": True}),
                    required_context_fields=("store_id",),
                )
            )
            ctx = ToolExecutionContext(
                tenant_id="tenant-test",
                client_id="client-test",
                session_id="sess",
                trace_id="trace",
                trusted_context={"store_id": "store-a"},
            )
            empty_ctx = ToolExecutionContext(
                tenant_id="tenant-test",
                client_id="client-test",
                session_id="sess",
                trace_id="trace",
                trusted_context={},
            )

            def expect_raise(name: str, fn, needle: str) -> None:
                try:
                    fn()
                    rows.append({"name": name, "status": "FAIL", "error": "no exception"})
                except ValueError as exc:
                    ok = needle in str(exc)
                    rows.append(
                        {
                            "name": name,
                            "status": "PASS" if ok else "FAIL",
                            "error": str(exc),
                            "executed": list(executions),
                        }
                    )

            expect_raise(
                "registry_unregistered",
                lambda: core.tools.validate_selection(
                    name="not_registered",
                    arguments={},
                    requested_mode="observe",
                    context=ctx,
                ),
                "tool_not_registered",
            )
            expect_raise(
                "registry_observe_write",
                lambda: core.tools.validate_selection(
                    name="sandbox_refund",
                    arguments={"order_id": "ORD-1"},
                    requested_mode="observe",
                    context=ctx,
                ),
                "observe_cannot_call_write_tool",
            )
            expect_raise(
                "registry_fake_params",
                lambda: core.tools.validate_selection(
                    name="sandbox_refund",
                    arguments={"order_id": "ORD-1", "evil": True},
                    requested_mode="act",
                    context=ctx,
                ),
                "tool_arguments_invalid",
            )
            expect_raise(
                "registry_missing_store",
                lambda: core.tools.validate_selection(
                    name="sandbox_refund",
                    arguments={"order_id": "ORD-1"},
                    requested_mode="act",
                    context=empty_ctx,
                ),
                "trusted_context_missing",
            )
            spec, args = core.tools.validate_selection(
                name="sandbox_refund",
                arguments={"order_id": "ORD-OK"},
                requested_mode="act",
                context=ctx,
            )
            result = core.tools.execute(spec=spec, arguments=args, context=ctx)
            rows.append(
                {
                    "name": "registry_positive_execute",
                    "status": "PASS" if result.status == "success" and "ORD-OK" in executions else "FAIL",
                    "executed": list(executions),
                    "tool_status": result.status,
                }
            )

            principal = principal_for_core(core, "k06-buyer")

            def set_decision(mode: str, tool_name: str | None, arguments: dict, intent: str = "product") -> None:
                model._table["agent_decision"] = {
                    "intent": intent,
                    "mode": mode,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "missing_fields": [],
                    "expected_outcome": None,
                    "response": None,
                    "reason": "table_driven_k06",
                    "confidence": 0.9,
                }

            def graph_case(name: str, mode: str, tool_name: str, arguments: dict, context: dict, expect_exec: bool, needle: str | None, intent: str = "product") -> None:
                before = list(executions)
                set_decision(mode, tool_name, arguments, intent=intent)
                resp = core.chat(
                    principal,
                    "k06g-" + uuid.uuid4().hex[:10],
                    "k06 graph " + name,
                    context=context,
                    source_type="api",
                    source_reference="k06",
                )
                executed = executions[len(before) :]
                dump = resp.model_dump()
                blob = json.dumps(dump, ensure_ascii=False)
                no_exec = executed == []
                exec_ok = (not no_exec) if expect_exec else no_exec
                needle_ok = True if needle is None else needle in blob
                rows.append(
                    {
                        "name": name,
                        "status": "PASS" if exec_ok and needle_ok else "FAIL",
                        "executed": executed,
                        "reason": dump.get("reason"),
                        "requires_human": dump.get("requires_human"),
                        "trace_tail": (dump.get("trace") or [])[-5:],
                        "answer_preview": str(dump.get("answer") or "")[:200],
                    }
                )

            graph_case(
                "graph_unregistered_observe",
                "observe",
                "not_registered",
                {},
                {"store_id": "store-a"},
                False,
                "tool_not_registered",
            )
            graph_case(
                "graph_observe_write",
                "observe",
                "sandbox_refund",
                {"order_id": "ORD-OBS"},
                {"store_id": "store-a"},
                False,
                "observe_cannot_call_write_tool",
            )
            graph_case(
                "graph_observe_fake_params",
                "observe",
                "lookup_policy",
                {"evil": True},
                {"store_id": "store-a"},
                False,
                "tool_arguments_invalid",
            )
            graph_case(
                "graph_observe_missing_store",
                "observe",
                "store_bound_lookup",
                {},
                {},
                False,
                "trusted_context_missing",
            )
            graph_case(
                "graph_act_without_sop_does_not_execute",
                "act",
                "sandbox_refund",
                {"order_id": "ORD-ACT"},
                {"store_id": "store-a"},
                False,
                "active_sop_required_for_action",
                intent="refund",
            )
        finally:
            core.close()

    failed = [r for r in rows if r["status"] == "FAIL"]
    payload = {
        "saved_utc": utc_now(),
        "id": "K06",
        "level": "L1-framework",
        "l4_business_ledger": False,
        "summary": {
            "status": "PASS" if not failed else "FAIL",
            "fail_count": len(failed),
            "notes": [
                "registry authorizes tools; graph observe hits the same errors",
                "graph act without SOP handoff; write tool does not execute",
                "not a real refund sandbox ledger; K07-K13 remain L4 BLOCKED",
            ],
        },
        "rows": rows,
    }
    out = EVIDENCE / "k06" / "cases.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["summary"]["status"], "fail_count": len(failed)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
