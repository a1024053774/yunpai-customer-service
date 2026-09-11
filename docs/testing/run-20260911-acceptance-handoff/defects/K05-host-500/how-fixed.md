# K05 how-fixed

- defect: Host `/v1/chat` and `/v1/chat/stream` did not catch `SessionScopeError`. Same idempotency key + different message returned HTTP 500 instead of a conflict status.
- red: `before.json` TestClient first=200 second=500; live continue_l3 also 500 `Internal Server Error`.
- root cause: `src/yunpai_customer_service/api.py` let core raise through Starlette.
- fix: map `SessionScopeError` to HTTP 409 (422 for invalid_session_source); prime the SSE generator so conflict still sets status.
- green: `after.json` replay same message 200+same id; different message 409 `idempotency_key_conflict`; stream 409. `tests/test_api.py` 2 passed.
- not a product GO. Live host process must be restarted to pick up the mapping.
independent review: review.md STATUS PASS (2e7f5c48). implementer self-test is not acceptance.
