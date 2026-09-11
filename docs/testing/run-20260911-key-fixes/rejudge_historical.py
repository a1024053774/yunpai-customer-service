"""Rejudge the preserved direction-audit run with fail-closed contracts."""
from __future__ import annotations

import json
import re
from pathlib import Path

from oracle_red_evidence import (
    corrected_evolution_predicate,
    corrected_import_predicate,
    corrected_idempotency_predicate,
    corrected_model_dependence_predicate,
    corrected_preflight_predicate,
    corrected_pdf_fixture_predicate,
    corrected_vision_predicate,
)


ROOT = Path(__file__).resolve().parents[1] / "run-20260911-direction-audit"
OUT = Path(__file__).resolve().parent


def body(item: dict[str, object]) -> dict[str, object]:
    value = item.get("body")
    return value if isinstance(value, dict) else {}


def main() -> None:
    historical = json.loads((ROOT / "raw" / "probe-results.json").read_text(encoding="utf-8"))
    trials = {item["id"]: item for item in historical["trials"]}
    imports = body(trials["D07-import"])
    import_records = imports.get("imports")
    rows = json.loads((ROOT / "states" / "knowledge-after-import.json").read_text(encoding="utf-8"))["matched"]
    expected_filename = "DIR-AUDIT-20260911-ALPHA.txt"
    first = trials["D01-host-api"]
    raw_image = trials["D04-image"]
    raw_evo = json.loads((ROOT / "states" / "evolution-after.json").read_text(encoding="utf-8"))
    candidate = raw_evo.get("sqlite_candidate") or []
    knowledge = raw_evo.get("sqlite_knowledge") or []
    active_knowledge = []
    evolution_state = {
        "rollback": raw_evo.get("rollback") or {},
        "sqlite_candidate": candidate,
        "sqlite_knowledge": knowledge,
        # The historical run never captured the post-rollback knowledge API.  Keep
        # this absent rather than manufacturing an empty response.
        "api_active_knowledge": None,
    }

    # The historical raw file records the first body and only the replay status.  Do
    # not manufacture a replay message_id; missing replay JSON is itself incomplete.
    first_body = first.get("first") or {}
    replay_body: dict[str, object] = {}
    first_answer = str(trials["D03-multiturn"].get("first", {}).get("answer") or "")
    second_answer = str(trials["D03-multiturn"].get("second", {}).get("answer") or "")
    txt_import = next(
        (
            item
            for item in (import_records if isinstance(import_records, list) else [])
            if item.get("file") == expected_filename
        ),
        {},
    )
    txt_import_body = txt_import.get("body") if isinstance(txt_import, dict) else {}
    txt_items = txt_import_body.get("items") if isinstance(txt_import_body, dict) else []
    direction_text = (ROOT / "direction-matrix.json").read_text(encoding="utf-8")
    product_verdict = "NO_GO" if "未证明" in direction_text or "阻塞" in direction_text else "GO"
    checks = {
        "PREFLIGHT": corrected_preflight_predicate(
            trials["PREFLIGHT"].get("demo_health", {}),
            trials["PREFLIGHT"].get("host_health", {}),
            {
                "status_code": trials["PREFLIGHT"].get("ui_http", {}).get("status_code"),
                "required_markers": trials["PREFLIGHT"].get("ui_markers", {}),
            },
            {
                "status_code": trials["PREFLIGHT"].get("admin_http", {}).get("status_code"),
                "required_markers": trials["PREFLIGHT"].get("admin_markers", {}),
            },
        ),
        "D01-host-api": corrected_idempotency_predicate(
            {"status_code": first.get("status_code"), "body": first_body},
            {"status_code": first.get("replay_status"), "body": replay_body},
        ),
        "D03-D05": corrected_model_dependence_predicate(
            {"status_code": trials["D03-multiturn"].get("status_code"), "body": trials["D03-multiturn"].get("first", {})},
            {"status_code": trials["D03-multiturn"].get("status_code"), "body": trials["D03-multiturn"].get("second", {})},
            first_required_tokens=("薄荷绿", "7L"),
            second_required_tokens=("薄荷绿", "7L"),
            expected_first_intent="product_inquiry",
            expected_second_intent="product_inquiry",
            first_answer_pattern=r"\A" + re.escape(first_answer) + r"\Z",
            second_answer_pattern=r"\A" + re.escape(second_answer) + r"\Z",
        ),
        "D04-image": corrected_vision_predicate(
            {"status_code": raw_image.get("status_code"), "body": raw_image.get("response", {})}
        ),
        "D07-D08": corrected_import_predicate(
            {"status_code": txt_import.get("status_code"), "body": txt_import_body},
            expected_filename,
            "followup-l3-tenant",
            [
                row
                for row in rows
                if row.get("id") in {
                    item.get("id") for item in (txt_items if isinstance(txt_items, list) else [])
                }
            ],
        ),
        "D07-PDF-fixture": corrected_pdf_fixture_predicate("not_recorded", False),
        "D09-evolution": corrected_evolution_predicate(evolution_state),
    }
    all_checked_slices_passed = all(checks.values())
    output = {
        "status": "REJUDGED",
        "all_checked_slices_passed": all_checked_slices_passed,
        "verdict": "GO" if all_checked_slices_passed and product_verdict == "GO" else "NO_GO",
        "product_direction_verdict": product_verdict,
        "source": str(ROOT / "raw" / "probe-results.json"),
        "checks": checks,
        "notes": [
            "Historical artifacts were not overwritten.",
            "A false or missing contract is INCOMPLETE, never PASS.",
            "This rejudgment does not claim production or L4/L5 acceptance.",
        ],
    }
    (OUT / "rejudged-verdict.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
