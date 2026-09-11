"""K03 reconnect after abort. ASCII source."""
from __future__ import annotations

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
from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core  # noqa: E402


def main() -> None:
    with TemporaryDirectory(prefix="yunpai-k03-", dir="/tmp") as raw:
        tmp = Path(raw)
        settings = make_settings(tmp)
        core = build_core(tmp, settings=settings, model=TableDrivenModel(settings), seed_knowledge=True)
        principal = principal_for_core(core, "k03")
        events = []
        for ev in core.chat_stream(
            principal, "k03-sess", "k03-reconnect-marker", idempotency_key="k03-abort-1"
        ):
            name = ev.get("event") if isinstance(ev, dict) else getattr(ev, "event", type(ev).__name__)
            events.append(name)
            if name == "delta":
                break
        with core.db.connect() as conn:
            mid = [
                dict(r)
                for r in conn.execute(
                    "SELECT role, content FROM messages WHERE session_id IN "
                    "(SELECT id FROM sessions WHERE external_session_id=?)",
                    ("k03-sess",),
                ).fetchall()
            ]
        second = list(
            core.chat_stream(
                principal, "k03-sess", "k03-after-abort", idempotency_key="k03-after-2"
            )
        )
        second_events = [
            ev.get("event") if isinstance(ev, dict) else getattr(ev, "event", type(ev).__name__)
            for ev in second
        ]
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
        status = "PASS" if len(assistants) <= 2 and "result" in second_events else "INCOMPLETE"
        case = {
            "id": "K03",
            "priority": "P1",
            "level": "L1",
            "status": status,
            "expected": "abort after first delta then continue; no silent double-success on same turn",
            "actual": {
                "first_events": events,
                "rows_after_abort": mid,
                "second_events": second_events[:12],
                "assistant_count": len(assistants),
                "after": after,
            },
            "notes": ["in-process stream abort; host socket reconnect still not run"],
            "saved_utc": datetime.now(timezone.utc).isoformat(),
        }
        (EVIDENCE / "k03.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"id": "K03", "status": status, "assistant_count": len(assistants)}, ensure_ascii=False))
        core.close()


if __name__ == "__main__":
    main()
