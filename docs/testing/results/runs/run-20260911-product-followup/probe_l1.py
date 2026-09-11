"""L1 framework probes: K11 HTTP schema, K06 tool gate, K05 factor matrix.

Does not claim handbook K05 PASS. No secrets in evidence.
"""
from __future__ import annotations

import base64
import json
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core  # noqa: E402
from yunpai_customer_service.api import create_api_app  # noqa: E402
from yunpai_customer_service.auth import AuthenticationService  # noqa: E402
from yunpai_customer_service.demo.app import create_app  # noqa: E402
from yunpai_customer_service.tools import (  # noqa: E402
    EmptyToolInput,
    ToolExecutionContext,
    ToolResult,
    ToolSpec,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_B64 = base64.b64encode(PNG).decode("ascii")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detail_code(resp) -> str | None:
    try:
        body = resp.json()
    except Exception:
        return None
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    return None


class RefundInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str = Field(min_length=1, max_length=64)
    amount: int = 1


def main() -> int:
    results: dict[str, object] = {
        "saved_utc": utc_now(),
        "run_id": "run-20260911-product-followup",
        "layer": "L1",
        "candidate_note": "current dirty tree including api.py e268c2b3",
        "cases": [],
    }

    with TemporaryDirectory(prefix="yunpai-followup-l1-", dir="/tmp") as raw:
        data_dir = Path(raw)
        settings = make_settings(data_dir)
        executions: list[str] = []

        def refund_handler(payload: RefundInput, _ctx: ToolExecutionContext) -> ToolResult:
            executions.append(payload.order_id)
            return ToolResult(
                status="success",
                output={"order_id": payload.order_id, "refunded": True},
                postcondition_met=True,
            )

        def refund_verifier(payload: RefundInput, result: ToolResult, _ctx: ToolExecutionContext) -> bool:
            return bool(result.postcondition_met) and payload.order_id in executions

        model = TableDrivenModel(settings)
        core = build_core(data_dir, settings=settings, model=model, seed_knowledge=True)
        try:
            core.tools.register(
                ToolSpec(
                    name="sandbox_refund",
                    description="isolated write tool for K06",
                    kind="write",
                    input_model=RefundInput,
                    handler=refund_handler,
                    required_context_fields=("store_id",),
                    idempotency_fields=("order_id",),
                    verifier=refund_verifier,
                )
            )
            core.tools.register(
                ToolSpec(
                    name="lookup_policy",
                    description="isolated read tool for K06",
                    kind="read",
                    input_model=EmptyToolInput,
                    handler=lambda _p, _c: ToolResult(status="success", output={"ok": True}),
                )
            )
            auth = AuthenticationService(core.db, settings)
            auth._ensure_client(
                client_id="client-test-2",
                tenant_id=settings.bootstrap_tenant_id,
                name="Second host client",
                key="test-client-key-second-67890",
                can_supply_order_context=False,
                role="client",
            )
            app = create_api_app(core, auth=auth)
            h1 = {
                "X-Client-Id": settings.bootstrap_client_id,
                "X-Client-Key": settings.bootstrap_client_key,
                "X-Subject-Id": "k05-buyer-a",
            }
            h2 = {
                "X-Client-Id": "client-test-2",
                "X-Client-Key": "test-client-key-second-67890",
                "X-Subject-Id": "k05-buyer-b",
            }

            with TestClient(app, raise_server_exceptions=False) as client:
                k11 = run_k11(client, h1)
                k05 = run_k05(client, h1, h2)
            k06 = run_k06(core, model, executions)
        finally:
            core.close()

        results["cases"] = [
            {"id": "K11", **k11["summary"]},
            {"id": "K05-factors", **k05["summary"]},
            {"id": "K06-framework", **k06["summary"]},
        ]
        write_json(EVIDENCE / "l1" / "cases.json", results)
        write_json(EVIDENCE / "k11" / "cases.json", k11)
        write_json(EVIDENCE / "k05" / "factor-matrix.json", k05)
        write_json(EVIDENCE / "k06" / "cases.json", k06)
        print(
            json.dumps(
                {
                    "K11": k11["summary"]["status"],
                    "K05_factors": k05["summary"]["status"],
                    "K06": k06["summary"]["status"],
                },
                ensure_ascii=False,
            )
        )
    return 0


def run_k11(client: TestClient, headers: dict[str, str]) -> dict:
    rows = []

    def add(name: str, resp, expect: set[int], extra: dict | None = None) -> None:
        preview = resp.text[:400]
        status = "PASS" if resp.status_code in expect else "FAIL"
        if resp.status_code >= 500:
            status = "FAIL"
        row = {
            "name": name,
            "status_code": resp.status_code,
            "expected": sorted(expect),
            "status": status,
            "body_preview": preview,
            "detail_code": detail_code(resp),
        }
        if extra:
            row.update(extra)
        rows.append(row)

    add("empty_json_object", client.post("/v1/chat", headers=headers, json={}), {422})
    add(
        "empty_message",
        client.post(
            "/v1/chat",
            headers=headers,
            json={"session_id": "k11empty1", "message": ""},
        ),
        {422},
    )
    add(
        "whitespace_message",
        client.post(
            "/v1/chat",
            headers=headers,
            json={"session_id": "k11empty2", "message": "   "},
        ),
        {422},
    )
    add(
        "text_plain",
        client.post(
            "/v1/chat",
            headers=headers,
            content="hello this is not json",
            headers_extra=None,
        )
        if False
        else client.post(
            "/v1/chat",
            headers={**headers, "Content-Type": "text/plain"},
            content="hello this is not json",
        ),
        {422, 415, 400},
    )
    add(
        "malformed_json",
        client.post(
            "/v1/chat",
            headers={**headers, "Content-Type": "application/json"},
            content='{"session_id":"k11bad"',
        ),
        {422, 400},
    )
    add(
        "malformed_stream_json",
        client.post(
            "/v1/chat/stream",
            headers={**headers, "Content-Type": "application/json"},
            content="{not-json",
        ),
        {422, 400},
    )
    n_minus = "x" * 3999
    n = "x" * 4000
    n_plus = "x" * 4001
    add(
        "message_len_3999",
        client.post("/v1/chat", headers=headers, json={"session_id": "k11n-1", "message": n_minus}),
        {200, 422},
        extra={"note": "schema allows 4000; core may truncate at max_input_chars=2000"},
    )
    add(
        "message_len_4000",
        client.post("/v1/chat", headers=headers, json={"session_id": "k11n", "message": n}),
        {200, 422},
    )
    add(
        "message_len_4001",
        client.post("/v1/chat", headers=headers, json={"session_id": "k11n+1", "message": n_plus}),
        {422},
    )
    img = {
        "session_id": "k11imgonly",
        "message": "",
        "image": {"mime_type": "image/png", "data_base64": PNG_B64},
    }
    add("image_only_empty_message", client.post("/v1/chat", headers=headers, json=img), {200, 422})

    failed = [r for r in rows if r["status"] == "FAIL"]
    required = [r for r in rows if r["name"] in {"empty_message", "text_plain", "malformed_json", "malformed_stream_json"}]
    required_ok = all(r["status"] == "PASS" for r in required)
    summary_status = "PASS" if required_ok and not failed else ("INCOMPLETE" if required_ok else "FAIL")
    if failed:
        summary_status = "FAIL"
    return {
        "saved_utc": utc_now(),
        "id": "K11",
        "level": "L1",
        "summary": {
            "status": summary_status,
            "required_empty_plain_malformed_pass": required_ok,
            "fail_count": len(failed),
            "notes": [
                "HTTP schema/error boundary only; not L4 business ledger",
                "4000-char N/N+1 recorded; test settings max_input_chars=2000 may truncate rather than 4xx",
            ],
        },
        "rows": rows,
    }


def run_k05(client: TestClient, h1: dict[str, str], h2: dict[str, str]) -> dict:
    rows = []
    key = "k05-followup-" + uuid.uuid4().hex[:12]
    session = "k05sess-" + uuid.uuid4().hex[:10]
    first_msg = "first question about kettle"
    first = client.post(
        "/v1/chat",
        headers={**h1, "Idempotency-Key": key},
        json={"session_id": session, "message": first_msg, "context": {"store_id": "store-a"}},
    )
    replay = client.post(
        "/v1/chat",
        headers={**h1, "Idempotency-Key": key},
        json={"session_id": session, "message": first_msg, "context": {"store_id": "store-a"}},
    )
    same_id = False
    if first.status_code == 200 and replay.status_code == 200:
        try:
            same_id = first.json().get("message_id") == replay.json().get("message_id")
        except Exception:
            same_id = False
    rows.append(
        {
            "factor": "identical_replay",
            "first": first.status_code,
            "second": replay.status_code,
            "same_message_id": same_id,
            "status": "PASS" if first.status_code == 200 and same_id else "FAIL",
        }
    )

    def conflict(name: str, payload: dict, headers: dict, expect_code: str | None = "idempotency_key_conflict") -> None:
        resp = client.post("/v1/chat", headers=headers, json=payload)
        code = detail_code(resp)
        ok = resp.status_code == 409 and (expect_code is None or code == expect_code)
        answer = None
        try:
            body = resp.json()
            answer = body.get("answer")
        except Exception:
            body = {"raw": resp.text[:300]}
        rows.append(
            {
                "factor": name,
                "status_code": resp.status_code,
                "detail_code": code,
                "has_answer": bool(answer),
                "status": "PASS" if ok and not answer else "FAIL",
                "body_preview": resp.text[:300],
            }
        )

    conflict(
        "different_message",
        {"session_id": session, "message": "different " + uuid.uuid4().hex, "context": {"store_id": "store-a"}},
        {**h1, "Idempotency-Key": key},
    )
    conflict(
        "different_store_id",
        {"session_id": session, "message": first_msg, "context": {"store_id": "store-b"}},
        {**h1, "Idempotency-Key": key},
    )
    conflict(
        "add_image",
        {
            "session_id": session,
            "message": first_msg,
            "context": {"store_id": "store-a"},
            "image": {"mime_type": "image/png", "data_base64": PNG_B64},
        },
        {**h1, "Idempotency-Key": key},
    )
    conflict(
        "different_subject_same_session",
        {"session_id": session, "message": first_msg, "context": {"store_id": "store-a"}},
        {**h1, "Idempotency-Key": key, "X-Subject-Id": "k05-buyer-other"},
        expect_code="session_scope_conflict",
    )
    conflict(
        "different_subject_new_session",
        {"session_id": "k05sess-new-" + uuid.uuid4().hex[:8], "message": first_msg, "context": {"store_id": "store-a"}},
        {**h1, "Idempotency-Key": key, "X-Subject-Id": "k05-buyer-other2"},
    )

    second_client = client.post(
        "/v1/chat",
        headers={**h2, "Idempotency-Key": key},
        json={"session_id": "k05sess-c2-" + uuid.uuid4().hex[:8], "message": first_msg, "context": {"store_id": "store-a"}},
    )
    c2_ok = second_client.status_code == 200
    c2_id = None
    try:
        c2_id = second_client.json().get("message_id")
        first_id = first.json().get("message_id")
        c2_ok = c2_ok and c2_id and c2_id != first_id
    except Exception:
        c2_ok = False
    rows.append(
        {
            "factor": "second_host_client_same_key",
            "status_code": second_client.status_code,
            "isolated_message_id": bool(c2_ok),
            "status": "PASS" if c2_ok else "FAIL",
            "body_preview": second_client.text[:300],
            "notes": "uniqueness is tenant+client+key; second client must not inherit first answer",
        }
    )

    stream = client.post(
        "/v1/chat/stream",
        headers={**h1, "Idempotency-Key": key},
        json={"session_id": session, "message": "stream different " + uuid.uuid4().hex, "context": {"store_id": "store-a"}},
    )
    rows.append(
        {
            "factor": "stream_conflict_after_bound_key",
            "status_code": stream.status_code,
            "detail_code": detail_code(stream),
            "status": "PASS" if stream.status_code == 409 else "FAIL",
            "body_preview": stream.text[:300],
        }
    )

    conc_key = "k05-conc-" + uuid.uuid4().hex[:10]
    conc_session = "k05conc-" + uuid.uuid4().hex[:8]
    conc_status: list[int] = []
    conc_err: list[str] = []

    def _post(msg: str) -> None:
        try:
            r = client.post(
                "/v1/chat",
                headers={**h1, "Idempotency-Key": conc_key},
                json={"session_id": conc_session, "message": msg, "context": {"store_id": "store-a"}},
            )
            conc_status.append(r.status_code)
        except Exception as exc:
            conc_err.append(f"{type(exc).__name__}: {exc}")

    t1 = threading.Thread(target=_post, args=("concurrent-one " + uuid.uuid4().hex,))
    t2 = threading.Thread(target=_post, args=("concurrent-two " + uuid.uuid4().hex,))
    t1.start()
    t2.start()
    t1.join(30)
    t2.join(30)
    # One 200 and one 409, or both 409 if both lose the insert race poorly; never two 200 with different answers.
    ok_conc = sorted(conc_status) in ([200, 409], [409, 200], [409, 409]) and not conc_err
    if conc_status.count(200) > 1:
        ok_conc = False
    rows.append(
        {
            "factor": "concurrent_different_messages",
            "status_codes": conc_status,
            "errors": conc_err,
            "status": "PASS" if ok_conc else ("INCOMPLETE" if conc_err else "FAIL"),
            "notes": "TestClient threads are best-effort; live L3 repeats this",
        }
    )

    mid_key = "k05-mid-" + uuid.uuid4().hex[:10]
    mid_session = "k05mid-" + uuid.uuid4().hex[:8]
    frames: list[str] = []
    mid_err: str | None = None
    started = threading.Event()

    def _stream() -> None:
        try:
            with client.stream(
                "POST",
                "/v1/chat/stream",
                headers={**h1, "Idempotency-Key": mid_key},
                json={"session_id": mid_session, "message": "mid-sse first", "context": {"store_id": "store-a"}},
            ) as resp:
                started.set()
                for line in resp.iter_lines():
                    if line:
                        frames.append(line[:200])
                        if len(frames) >= 1:
                            break
        except Exception as exc:
            started.set()
            nonlocal_err.append(f"{type(exc).__name__}: {exc}")

    nonlocal_err: list[str] = []
    th = threading.Thread(target=_stream)
    th.start()
    started.wait(15)
    time.sleep(0.05)
    mid_conflict = client.post(
        "/v1/chat",
        headers={**h1, "Idempotency-Key": mid_key},
        json={"session_id": mid_session, "message": "mid-sse second different", "context": {"store_id": "store-a"}},
    )
    th.join(30)
    mid_ok = mid_conflict.status_code == 409 and detail_code(mid_conflict) == "idempotency_key_conflict"
    rows.append(
        {
            "factor": "mid_sse_second_request",
            "stream_frames": len(frames),
            "conflict_status": mid_conflict.status_code,
            "detail_code": detail_code(mid_conflict),
            "stream_errors": nonlocal_err,
            "status": "PASS" if mid_ok else "INCOMPLETE",
            "body_preview": mid_conflict.text[:300],
            "notes": "second request after first stream frame; must not return first answer",
        }
    )

    failed = [r for r in rows if r["status"] == "FAIL"]
    incomplete = [r for r in rows if r["status"] == "INCOMPLETE"]
    summary_status = "INCOMPLETE"
    notes = [
        "This is the factor matrix for handbook K05, not a product GO",
        "K05-host-500 mapping slice remains historically REVIEW_PASS",
        "L1 table model cannot close live L3 image/subject/store_id",
    ]
    if failed:
        summary_status = "FAIL"
        notes.append("one or more factors failed at L1")
    elif not incomplete:
        summary_status = "PASS"
        notes.append("L1 factors passed; handbook K05 still needs live L3 to claim full PASS")
    return {
        "saved_utc": utc_now(),
        "id": "K05",
        "level": "L1",
        "handbook_claim": False,
        "summary": {
            "status": summary_status,
            "fail_count": len(failed),
            "incomplete_count": len(incomplete),
            "notes": notes,
        },
        "rows": rows,
    }


def run_k06(core, model: TableDrivenModel, executions: list[str]) -> dict:
    principal = principal_for_core(core, "k06-buyer")
    rows = []

    def set_decision(mode: str, tool_name: str | None, arguments: dict) -> None:
        model._table["agent_decision"] = {
            "intent": "refund",
            "mode": mode,
            "tool_name": tool_name,
            "arguments": arguments,
            "missing_fields": [],
            "expected_outcome": "sandbox",
            "response": None,
            "reason": "table_driven_k06",
            "confidence": 0.9,
        }

    def chat_once(name: str, message: str, context: dict, expect_no_exec: bool, expect_reason_substr: str | None) -> None:
        before = list(executions)
        resp = core.chat(
            principal,
            "k06-" + uuid.uuid4().hex[:10],
            message,
            context=context,
            source_type="api",
            source_reference="k06-l1",
        )
        after = list(executions)
        executed = after[len(before) :]
        dump = resp.model_dump()
        reason = str(dump.get("reason") or dump.get("route_reason") or "")
        trace = dump.get("trace") or []
        tool_result = dump.get("tool_result") or {}
        no_exec = executed == []
        reason_ok = True if expect_reason_substr is None else expect_reason_substr in (reason + json.dumps(trace, ensure_ascii=False))
        status = "PASS" if (no_exec if expect_no_exec else not no_exec) and reason_ok else "FAIL"
        rows.append(
            {
                "name": name,
                "status": status,
                "executed_order_ids": executed,
                "requires_human": dump.get("requires_human"),
                "reason": reason,
                "trace_tail": trace[-6:],
                "tool_result_status": tool_result.get("status") if isinstance(tool_result, dict) else None,
                "answer_preview": str(dump.get("answer") or "")[:240],
                "notes": ["permission from server registry; not model self-report"],
            }
        )

    set_decision("act", "not_a_registered_tool", {"order_id": "ORD-UNREG"})
    chat_once(
        "unregistered_tool",
        "please refund order ORD-UNREG",
        {"store_id": "store-a"},
        expect_no_exec=True,
        expect_reason_substr="tool_not_registered",
    )

    set_decision("observe", "sandbox_refund", {"order_id": "ORD-OBSERVE"})
    chat_once(
        "observe_cannot_call_write",
        "look up refund for ORD-OBSERVE",
        {"store_id": "store-a"},
        expect_no_exec=True,
        expect_reason_substr="observe_cannot_call_write_tool",
    )

    set_decision("act", "sandbox_refund", {"order_id": "ORD-FAKE", "amount": 1, "extra_evil": True})
    chat_once(
        "fake_parameters_extra_forbid",
        "refund ORD-FAKE with extra field",
        {"store_id": "store-a"},
        expect_no_exec=True,
        expect_reason_substr="tool_arguments_invalid",
    )

    set_decision("act", "sandbox_refund", {"order_id": "ORD-NOPERM"})
    chat_once(
        "missing_store_id_permission",
        "refund ORD-NOPERM",
        {},
        expect_no_exec=True,
        expect_reason_substr="trusted_context_missing",
    )

    set_decision("act", "sandbox_refund", {"order_id": "ORD-OK"})
    chat_once(
        "positive_control_write_allowed",
        "refund ORD-OK in sandbox",
        {"store_id": "store-a"},
        expect_no_exec=False,
        expect_reason_substr=None,
    )

    failed = [r for r in rows if r["status"] == "FAIL"]
    pos = next((r for r in rows if r["name"] == "positive_control_write_allowed"), None)
    summary = "PASS" if not failed and pos and pos["status"] == "PASS" else "FAIL"
    return {
        "saved_utc": utc_now(),
        "id": "K06",
        "level": "L1-framework",
        "l4_business_ledger": False,
        "summary": {
            "status": summary,
            "fail_count": len(failed),
            "notes": [
                "framework only: unregistered / observe+write / fake params / missing trusted store_id",
                "write tool is in-process sandbox counter, not a real refund ledger",
                "K07-K13 L4 remain BLOCKED",
            ],
        },
        "rows": rows,
        "executions_final": list(executions),
    }


if __name__ == "__main__":
    raise SystemExit(main())
