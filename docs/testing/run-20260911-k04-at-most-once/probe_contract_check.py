"""Deterministic contract check for the crash probe's exception boundary."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def main(output: Path) -> None:
    source = Path(__file__).with_name("crash_recovery_red.py")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    broad_handlers = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "Exception"
    ]
    text = source.read_text(encoding="utf-8")
    checks = {
        "no_broad_exception_handler": not broad_handlers,
        "catches_session_scope_error": "except SessionScopeError" in text,
        "checks_expected_error_code": 'error["code"] == "idempotency_in_progress"' in text,
        "checks_running_without_last_error": 'row["last_error"] is None' in text,
        "non_target_errors_are_not_swallowed": "raise SystemExit" in text,
    }
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "broad_handler_lines": broad_handlers}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output)
