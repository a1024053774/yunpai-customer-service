"""Executable red evidence for the six acceptance-oracle defects.

The fixtures model the weakest responses that the historical probe accepted.  This
file is evidence only; it does not call the product or alter product state.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def old_vision_predicate(response: dict[str, object]) -> bool:
    return response.get("status_code") == 200 and (
        "vision_status" in response.get("body", {})
        or "vision_model" in response.get("body", {})
    )


def corrected_vision_predicate(response: dict[str, object]) -> bool:
    body = response.get("body")
    return (
        response.get("status_code") == 200
        and isinstance(body, dict)
        and body.get("vision_status") == "applied"
        and isinstance(body.get("vision_model"), str)
        and bool(body.get("vision_model"))
        and body.get("vision_image_count") == 1
    )


def old_idempotency_predicate(first: dict[str, object], second: dict[str, object]) -> bool:
    return (
        first.get("status_code") == 200
        and second.get("status_code") == 200
        and first.get("body", {}).get("message_id")
        == second.get("body", {}).get("message_id")
    )


def corrected_idempotency_predicate(
    first: dict[str, object],
    second: dict[str, object],
    *,
    first_request: dict[str, object] | None = None,
    second_request: dict[str, object] | None = None,
) -> bool:
    first_body = first.get("body")
    second_body = second.get("body")
    first_id = first_body.get("message_id") if isinstance(first_body, dict) else None
    second_id = second_body.get("message_id") if isinstance(second_body, dict) else None
    required_request_fields = {
        "idempotency_key",
        "tenant_id",
        "client_id",
        "session_id",
        "message",
        "context",
    }
    requests_complete = (
        isinstance(first_request, dict)
        and isinstance(second_request, dict)
        and required_request_fields <= set(first_request)
        and required_request_fields <= set(second_request)
        and bool(first_request.get("idempotency_key"))
        and bool(first_request.get("tenant_id"))
        and bool(first_request.get("client_id"))
        and bool(first_request.get("session_id"))
        and isinstance(first_request.get("message"), str)
        and isinstance(first_request.get("context"), dict)
    )
    return (
        first.get("status_code") == 200
        and second.get("status_code") == 200
        and isinstance(first_id, str)
        and bool(first_id)
        and first_id == second_id
        and requests_complete
        and first_request == second_request
    )


def old_model_shape_predicate(response: dict[str, object]) -> bool:
    return response.get("status_code") == 200 and response.get("body", {}).get("intent_method") == "model"


def corrected_model_dependence_predicate(
    first: dict[str, object],
    second: dict[str, object],
    *,
    first_required_tokens: tuple[str, ...] = (),
    second_required_tokens: tuple[str, ...] = (),
    expected_first_intent: str | None = None,
    expected_second_intent: str | None = None,
    first_answer_pattern: str | None = None,
    second_answer_pattern: str | None = None,
) -> bool:
    first_body = first.get("body")
    second_body = second.get("body")
    if not isinstance(first_body, dict) or not isinstance(second_body, dict):
        return False
    if first.get("status_code") != 200 or second.get("status_code") != 200:
        return False
    if first_body.get("intent_method") != "model" or second_body.get("intent_method") != "model":
        return False
    if not first_required_tokens or not second_required_tokens:
        return False
    if (
        expected_first_intent is None
        or expected_second_intent is None
        or first_answer_pattern is None
        or second_answer_pattern is None
    ):
        return False
    if not (
        first_answer_pattern.startswith(r"\A")
        and first_answer_pattern.endswith(r"\Z")
        and second_answer_pattern.startswith(r"\A")
        and second_answer_pattern.endswith(r"\Z")
    ):
        return False
    if first_body.get("customer_intent") != expected_first_intent:
        return False
    if second_body.get("customer_intent") != expected_second_intent:
        return False
    first_answer = first_body.get("answer")
    second_answer = second_body.get("answer")
    return (
        isinstance(first_answer, str)
        and bool(first_answer.strip())
        and isinstance(second_answer, str)
        and bool(second_answer.strip())
        and all(token in first_answer for token in first_required_tokens)
        and all(token in second_answer for token in second_required_tokens)
        and re.fullmatch(first_answer_pattern, first_answer, flags=re.DOTALL) is not None
        and re.fullmatch(second_answer_pattern, second_answer, flags=re.DOTALL) is not None
    )


def old_import_predicate(response: dict[str, object]) -> bool:
    return response.get("status_code") == 200 and response.get("body", {}).get("count", 0) > 0


def corrected_import_predicate(
    response: dict[str, object],
    expected_filename: str,
    expected_tenant_id: str,
    rows: list[dict[str, object]],
) -> bool:
    body = response.get("body")
    items = body.get("items") if isinstance(body, dict) else None
    if response.get("status_code") != 200 or not isinstance(items, list) or not items:
        return False
    if body.get("count") != len(items):
        return False
    if any(
        not isinstance(item, dict)
        or item.get("filename") != expected_filename
        or not isinstance(item.get("id"), str)
        or not item["id"].strip()
        for item in items
    ):
        return False
    if any(not isinstance(row, dict) for row in rows):
        return False
    row_by_id = {row.get("id"): row for row in rows}
    item_ids = [item.get("id") for item in items]
    if (
        len(item_ids) != len(set(item_ids))
        or any(not isinstance(row_id, str) or not row_id.strip() for row_id in row_by_id)
        or set(item_ids) != set(row_by_id)
    ):
        return False
    return all(
        isinstance(row.get("status"), str)
        and row.get("status") == "active"
        and isinstance(row.get("tenant_id"), str)
        and row.get("tenant_id") == expected_tenant_id
        and isinstance(row.get("source"), str)
        and row["source"].startswith(f"upload://{expected_filename}?")
        and isinstance(row.get("version"), int)
        and not isinstance(row.get("version"), bool)
        and row.get("version") == 1
        for row in row_by_id.values()
    )


def old_preflight_predicate(demo: dict[str, object], host: dict[str, object]) -> bool:
    return demo.get("status_code") == 200 and host.get("status_code") == 200


def corrected_preflight_predicate(
    demo: dict[str, object], host: dict[str, object], ui: dict[str, object], admin: dict[str, object]
) -> bool:
    return (
        old_preflight_predicate(demo, host)
        and ui.get("status_code") == 200
        and admin.get("status_code") == 200
        and ui.get("required_markers") == {"product": True, "multiturn": True, "local_rag": True}
        and admin.get("required_markers") == {"import": True, "evolution": True}
    )


def old_pdf_fixture_predicate(generation_error: str | None, bytes_written: int) -> bool:
    return generation_error is None or bytes_written > 0


def corrected_pdf_fixture_predicate(generation_error: str | None, valid_pdf: bool) -> bool:
    return generation_error is None and valid_pdf


def old_evolution_predicate(state: dict[str, object]) -> bool:
    candidate = state["sqlite_candidate"][0]
    return (
        state["rollback"].get("status_code") == 200
        and candidate.get("status") == "approved"
    )


def corrected_evolution_predicate(state: dict[str, object]) -> bool:
    candidate_rows = state.get("sqlite_candidate")
    knowledge_rows = state.get("sqlite_knowledge")
    api_items = state.get("api_active_knowledge")
    candidate = candidate_rows[0] if isinstance(candidate_rows, list) and candidate_rows else {}
    knowledge = knowledge_rows[0] if isinstance(knowledge_rows, list) and knowledge_rows else {}
    resulting_id = candidate.get("resulting_knowledge_id")
    return (
        state.get("rollback", {}).get("status_code") == 200
        and state.get("rollback", {}).get("body", {}).get("rolled_back") is True
        and candidate.get("status") == "approved"
        and knowledge.get("id") == resulting_id
        and knowledge.get("status") == "retired"
        and isinstance(api_items, list)
        and all(item.get("id") != resulting_id for item in api_items)
    )


def main() -> None:
    valid_first = {
        "status_code": 200,
        "body": {
            "intent_method": "model",
            "customer_intent": "product_inquiry",
            "answer": "产品容量7L，颜色薄荷绿。",
        },
    }
    valid_second = {
        "status_code": 200,
        "body": {
            "intent_method": "model",
            "customer_intent": "after_sales",
            "answer": "产品容量7L，颜色薄荷绿。",
        },
    }
    valid_contract = dict(
        first_required_tokens=("薄荷绿", "7L"),
        second_required_tokens=("薄荷绿", "7L"),
        expected_first_intent="product_inquiry",
        expected_second_intent="after_sales",
        first_answer_pattern=r"\A产品容量7L，颜色薄荷绿。\Z",
        second_answer_pattern=r"\A产品容量7L，颜色薄荷绿。\Z",
    )
    appended_second = {
        "status_code": 200,
        "body": {
            **valid_second["body"],
            "answer": "产品容量7L，颜色薄荷绿。无关追加。",
        },
    }
    fixtures = {
        "D04-vision-error": {
            "historical_green": old_vision_predicate(
                {"status_code": 200, "body": {"vision_status": "error"}}
            ),
            "corrected_green": corrected_vision_predicate(
                {"status_code": 200, "body": {"vision_status": "error"}}
            ),
            "expected": "INCOMPLETE",
        },
        "D01-idempotency-missing-id": {
            "historical_green": old_idempotency_predicate(
                {"status_code": 200, "body": {"raw": "not-json"}},
                {"status_code": 200, "body": {"raw": "not-json"}},
            ),
            "corrected_green": corrected_idempotency_predicate(
                {"status_code": 200, "body": {"raw": "not-json"}},
                {"status_code": 200, "body": {"raw": "not-json"}},
            ),
            "expected": "INCOMPLETE",
        },
        "D03-D05-model-shape-only": {
            "historical_green": old_model_shape_predicate(
                {"status_code": 200, "body": {"intent_method": "model"}}
            ),
            "corrected_green": corrected_model_dependence_predicate(
                {"status_code": 200, "body": {"intent_method": "model", "customer_intent": "chitchat"}},
                {"status_code": 200, "body": {"intent_method": "model", "customer_intent": "chitchat"}},
            ),
            "expected": "INCOMPLETE",
        },
        "D07-D08-import-count-only": {
            "historical_green": old_import_predicate(
                {"status_code": 200, "body": {"count": 1}}
            ),
            "corrected_green": corrected_import_predicate(
                {"status_code": 200, "body": {"count": 1, "items": [{"filename": "wrong.txt", "id": "x"}]}},
                "expected.txt",
                "tenant-a",
                [],
            ),
            "expected": "INCOMPLETE",
        },
        "PREFLIGHT-ui-admin-ignored": {
            "historical_green": old_preflight_predicate(
                {"status_code": 200}, {"status_code": 200}
            ),
            "corrected_green": corrected_preflight_predicate(
                {"status_code": 200},
                {"status_code": 200},
                {"status_code": 200, "required_markers": {"product": False, "multiturn": False, "local_rag": False}},
                {"status_code": 200, "required_markers": {"import": False, "evolution": False}},
            ),
            "expected": "INCOMPLETE",
        },
        "D07-invalid-pdf-fallback": {
            "historical_green": old_pdf_fixture_predicate("PDF generation failed", 32),
            "corrected_green": corrected_pdf_fixture_predicate("PDF generation failed", False),
            "expected": "INCOMPLETE",
        },
        "D09-evolution-active-after-rollback": {
            "historical_green": old_evolution_predicate(
                {
                    "rollback": {"status_code": 200},
                    "sqlite_candidate": [{"status": "approved", "resulting_knowledge_id": "k1"}],
                }
            ),
            "corrected_green": corrected_evolution_predicate(
                {
                    "rollback": {"status_code": 200, "body": {"rolled_back": True}},
                    "sqlite_candidate": [{"status": "approved", "resulting_knowledge_id": "k1"}],
                    "sqlite_knowledge": [{"id": "k1", "status": "active"}],
                    "api_active_knowledge": [],
                }
            ),
            "expected": "INCOMPLETE",
        },
    }
    results = {
        key: {
            **value,
            "defect_proven": value["historical_green"] is True and value["corrected_green"] is False,
        }
        for key, value in fixtures.items()
    }
    output = {
        "status": "PASS" if all(item["defect_proven"] for item in results.values()) else "FAIL",
        "historical_probe_is_not_oracle": True,
        "results": results,
        "positive_contracts": {
            "D03-valid-anchored-answer": corrected_model_dependence_predicate(
                valid_first, valid_second, **valid_contract
            ),
        },
        "counterexamples": {
            "D03-unrelated-append-rejected": not corrected_model_dependence_predicate(
                valid_first, appended_second, **valid_contract
            ),
        },
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "oracle-red-evidence.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
