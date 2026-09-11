"""G04 focused signal: review_output raise must not leak draft; caller gets degrade.

Same procedure as run-20260911-0131 remaining-l1 probe_g04.
ASCII source. Write evidence as UTF-8 JSON.
"""
from __future__ import annotations

import argparse
import json
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
    TABLE_MODEL_ANSWER,
    TableDrivenModel,
    build_core,
    principal_for_core,
)


def persist_rows(core, session_id: str) -> list[dict]:
    with core.db.connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, route_reason FROM messages
            WHERE session_id IN (
                SELECT id FROM sessions WHERE external_session_id=?
            )
            ORDER BY created_at
            """,
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def run_phase(phase: str) -> dict:
    with TemporaryDirectory(prefix="yunpai-g04-", dir="/tmp") as raw:
        tmp = Path(raw)
        settings = make_settings(tmp)
        model = TableDrivenModel(settings)
        core = build_core(tmp, settings=settings, model=model, seed_knowledge=True)
        import yunpai_customer_service.graph as graph

        original = graph.review_output

        def boom(draft, evidence):
            raise RuntimeError("forced_verify_timeout")

        graph.review_output = boom
        raised = False
        answer = ""
        reason = ""
        requires_human = None
        route_reason = None
        trace = []
        persisted = []
        sse_events = []
        sse_error = None
        try:
            principal = principal_for_core(core, "g04-user")
            try:
                sync = core.chat(principal, "g04-session-aaaa", "what is the capacity?")
                answer = sync.answer or ""
                reason = str(getattr(sync, "route_reason", None) or getattr(sync, "reason", None))
                requires_human = sync.requires_human
                route_reason = getattr(sync, "route_reason", None)
                trace = list(getattr(sync, "trace", None) or [])
                persisted = persist_rows(core, "g04-session-aaaa")
            except Exception as exc:
                raised = True
                reason = f"{type(exc).__name__}: {exc}"
            try:
                events = list(
                    core.chat_stream(
                        principal,
                        "g04-session-sse",
                        "what is the capacity?",
                        idempotency_key=None,
                    )
                )
                sse_events = [
                    {
                        "event": ev.get("event"),
                        "text": ev.get("text"),
                        "answer": (ev.get("response") or {}).get("answer")
                        if isinstance(ev.get("response"), dict)
                        else None,
                    }
                    for ev in events
                ]
            except Exception as exc:
                sse_error = f"{type(exc).__name__}: {exc}"
        finally:
            graph.review_output = original
            core.close()

        leaked = TABLE_MODEL_ANSWER in (answer or "")
        leaked_persist = any(TABLE_MODEL_ANSWER in str(row.get("content") or "") for row in persisted)
        leaked_sse = TABLE_MODEL_ANSWER in json.dumps(sse_events, ensure_ascii=False)
        handled = (not raised) and bool(answer) and (not leaked)
        if leaked or leaked_persist or leaked_sse:
            status = "FAIL"
        elif raised:
            status = "INCOMPLETE"
        elif handled:
            status = "PASS"
        else:
            status = "INCOMPLETE"
        case = {
            "id": "G04",
            "priority": "P1",
            "level": "L1",
            "phase": phase,
            "status": status,
            "expected": "verify error/timeout does not emit risky draft; explicit fail or safe degrade",
            "actual": {
                "raised_to_caller": raised,
                "answer": answer,
                "reason": reason,
                "requires_human": requires_human,
                "route_reason": route_reason,
                "trace": trace,
                "leaked_table_draft": leaked,
                "leaked_persist": leaked_persist,
                "leaked_sse": leaked_sse,
                "persisted": persisted,
                "sse_error": sse_error,
                "sse_event_count": len(sse_events),
                "sse_events": sse_events[:20],
            },
            "notes": [
                "same monkeypatch as 0131: graph.review_output raises RuntimeError forced_verify_timeout",
                "INCOMPLETE if exception escapes without classified degrade",
                "PASS only if no draft leak and caller gets a handled response",
            ],
            "saved_utc": datetime.now(timezone.utc).isoformat(),
        }
        out = EVIDENCE / f"{phase}.json"
        out.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        html = (
            "<!doctype html><meta charset=utf-8><title>G04 "
            + phase
            + "</title><pre>"
            + json.dumps(case, ensure_ascii=False, indent=2)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            + "</pre>\n"
        )
        (EVIDENCE / f"{phase}.html").write_text(html, encoding="utf-8")
        print(json.dumps({"phase": phase, "status": status, "raised": raised, "leaked": leaked}, ensure_ascii=False))
        return case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["before", "after"])
    args = parser.parse_args()
    run_phase(args.phase)


if __name__ == "__main__":
    main()
