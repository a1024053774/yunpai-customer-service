"""Red evidence for duplicate graph execution under one idempotency key."""
from __future__ import annotations

import json
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core


ROOT = Path(__file__).resolve().parent


class CountingBlockingModel(TableDrivenModel):
    def __init__(self, settings):
        super().__init__(settings)
        self.generate_calls = 0
        self.first_generation_started = threading.Event()
        self.release_first_generation = threading.Event()
        self._count_lock = threading.Lock()

    def generate(self, messages):
        with self._count_lock:
            self.generate_calls += 1
            call_number = self.generate_calls
        if call_number == 1:
            self.first_generation_started.set()
            if not self.release_first_generation.wait(timeout=5):
                raise TimeoutError("red probe release was not signaled")
        return super().generate(messages)


def main() -> None:
    data_dir = ROOT / "data"
    shutil.rmtree(data_dir, ignore_errors=True)
    model = None
    core = None
    try:
        from conftest import make_settings

        settings = make_settings(data_dir)
        model = CountingBlockingModel(settings)
        core = build_core(data_dir, settings=settings, model=model)
        principal = principal_for_core(core)

        def call():
            return core.chat(
                principal,
                "k04-at-most-once",
                "尺码怎么选",
                idempotency_key="k04-at-most-once-1",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(call)
            if not model.first_generation_started.wait(timeout=5):
                raise TimeoutError("first graph generation did not start")
            second_future = pool.submit(call)
            time.sleep(0.2)
            model.release_first_generation.set()
            first = first_future.result(timeout=10)
            second = second_future.result(timeout=10)
        result = {
            "status": "FAIL" if model.generate_calls > 1 else "PASS",
            "generate_calls": model.generate_calls,
            "message_ids": [first.message_id, second.message_id],
            "same_message_id": first.message_id == second.message_id,
            "expected": "one graph execution and two durable identical responses",
        }
    finally:
        if core is not None:
            core.close()
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "before.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
