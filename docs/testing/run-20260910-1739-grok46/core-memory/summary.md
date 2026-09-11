# core-memory L1 — run-20260910-1739-grok46

Executor: Cursor Grok 4.6 (not Luna). Candidate: `/tmp/yunpai-test-candidate-grok46-pZG5r3`. Original `src/` was not modified.

## Pytest

- Command: `pytest -q --tb=short` on `test_customer_service_module.py`, `test_customer_service_module_memory.py`, `test_vision.py`, `test_demo_chat.py`, `test_domain_profiles.py`
- Env: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=/tmp/yunpai-test-candidate-grok46-pZG5r3/src`, `ALL_PROXY=http://127.0.0.1:9`, `NO_PROXY=127.0.0.1,localhost`
- Python: `/Users/luckye/Documents/Code/yunpai-customer-service/.venv/bin/python` (3.11.14)
- Result: **62 passed, 0 failed, 0 skipped**, exit **0**, 51.32s
- FAIL tests: **none**

## Case counts

| Status | Count |
|---|---|
| PASS | 13 |
| FAIL | **0** |
| INCOMPLETE | 9 |
| NOT_RUN | 1 |
| N/A | 1 |
| BLOCKED | 0 |

## Mapped results

| ID | Status | What this run proved |
|---|---|---|
| A01 | PASS | L1 sync/stream share answer; stream follows plan_generation branches |
| K01 | PASS | L1 core + Demo sync/stream consistency (no host `/v1`) |
| I09 | PASS | L1 user-message prompt-injection refuse |
| K04 | PASS | L1 in-process idempotent replay (not crash recovery) |
| B12 | INCOMPLETE | Stream `ModelUnavailableError` persist/retry only |
| M01 | INCOMPLETE | Same partial stream-failure evidence |
| C02 | PASS | L1 history does not leak across session ids (not two-customer same session_id) |
| C04 | INCOMPLETE | Drops oldest under tight budget; **authorization-not-dropped not proven** |
| H01 | PASS | buyer_preference scoped to authenticated subject |
| H04 | PASS | Phone redacted before storage and prompt |
| H05 | PASS | Standard RAG retrieve does not mix memory layer |
| H06 | INCOMPLETE | TTL renewal proven; expired-before-renewal exclusion not asserted |
| J03 | PASS | L1 follow-up receives previous image observation |
| J04 | INCOMPLETE | Partial: unverified `order_candidate` does not become trusted `order_id` |
| J05 | INCOMPLETE | MIME mismatch/GIF reject passed; **5 MiB size not tested** |
| J07 | INCOMPLETE | History hides internal media fields; **other user cannot see media not tested** |
| J08 | PASS | Audit-failure cleanup, queued delete, idempotent retry reclaim |
| L05 | PASS | L0/L1 TestClient: `/` + `/api/health` + bell markup. **Not a browser PASS** |
| L07 | PASS | L0/L1 HTML `isComposing`/keyCode 229. **Not a browser PASS** |
| O01 | PASS | HR profile labels / four control buckets only |
| O01-business | N/A | Real HR leave/onboarding/reimbursement not delivered |
| A06 | NOT_RUN | Clean-dir package install not run |
| A07 | INCOMPLETE | L0 README/health: SQLite, HR tags; packaging-from-clean-dir missing |
| N01 | INCOMPLETE | Same: not a frozen-package clean install |

## L0 README vs health

- README states LangGraph + **SQLite**. It does not claim PostgreSQL as the current store.
- README states ecommerce plus **HR domain tags**, and that HR prompts/SOP/knowledge are **not** business-accepted.
- Demo `/api/health` returns `business_domain` / `business_domain_label` from `domain_profiles`; tests show `ecommerce`/`????` and `hr`/`????`. Health does not advertise PostgreSQL.
- A06/N01 packaging from a clean directory was not run, so A07/N01 stay INCOMPLETE.

## FAIL

**0.** No pytest failure. Remaining gaps are INCOMPLETE / NOT_RUN / N/A, not product FAIL in this suite.

HR is **not** delivered. Browser L3 was **not** executed.
