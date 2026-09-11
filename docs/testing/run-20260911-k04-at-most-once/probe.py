"""Run the concurrent invocation contract with an exclusive evidence output path.

Uses isolated temporary data and a counted model double. This is L1 evidence;
no real model understanding, remote business write or crash recovery is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from conftest import make_settings
from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core
from yunpai_customer_service.customer_service import CustomerServiceCore


class CountingModel(TableDrivenModel):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls = 0
        self.entered = threading.Event()
        self.duplicate = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()

    def generate(self, messages):
        with self.lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            self.entered.set()
            if not self.release.wait(5):
                raise TimeoutError("coordinator did not release generation")
        else:
            self.duplicate.set()
        return super().generate(messages)


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="yunpai-k04-evidence-") as scratch:
        settings = make_settings(Path(scratch))
        model = CountingModel(settings)
        core = build_core(Path(scratch), settings=settings, model=model)
        principal = principal_for_core(core)
        request = {"session_id": "k04-concurrent", "message": "尺码怎么选",
                   "idempotency_key": "k04-concurrent-1"}

        def call():
            return core.chat(principal, **request).model_dump(mode="json")

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first_future = pool.submit(call)
                try:
                    if not model.entered.wait(5):
                        raise TimeoutError("first graph did not reach generation")
                    second_future = pool.submit(call)
                    model.duplicate.wait(0.75)
                finally:
                    model.release.set()
                first = first_future.result(timeout=10)
                second = second_future.result(timeout=35)
            sequential = call()
            with core.db.connect() as conn:
                invocation = dict(conn.execute("SELECT * FROM agent_invocations").fetchone())
                roles = dict(conn.execute("SELECT role, count(*) FROM messages GROUP BY role").fetchall())
            persisted = json.loads(invocation["response_json"])
            checks = {
                "single_generation": model.calls == 1,
                "full_responses_identical": first == second == sequential == persisted,
                "completed_durable": invocation["status"] == "completed",
                "single_message_pair": roles == {"user": 1, "assistant": 1},
                "nonempty_message_id": isinstance(first["message_id"], str) and bool(first["message_id"]),
            }
            return {
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks, "generate_calls": model.calls,
                "responses": [first, second, sequential],
                "invocation": invocation, "message_counts": roles,
                "request": {**request, "tenant_id": principal.tenant_id, "client_id": principal.client_id},
                "level": "L1", "python": sys.executable,
                "core_source": inspect.getfile(CustomerServiceCore),
                "core_sha256": hashlib.sha256(Path(inspect.getfile(CustomerServiceCore)).read_bytes()).hexdigest(),
                "limits": ["model double", "one process", "crash takeover unproved", "no remote business ledger"],
            }
        finally:
            core.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Exclusive creation is checked before any test or state mutation.
    with args.output.open("x", encoding="utf-8") as handle:
        result = run()
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "checks": result["checks"],
                      "generate_calls": result["generate_calls"]}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
