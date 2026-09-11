# K05 how-fixed

- defect: Host `/v1/chat` and `/v1/chat/stream` did not catch `SessionScopeError`. Same idempotency key + different message returned HTTP 500 instead of a conflict status.
- red: `before.json` TestClient first=200 second=500; live continue_l3 also 500 `Internal Server Error`.
- root cause: `src/yunpai_customer_service/api.py` let core raise through Starlette.
- fix: map `SessionScopeError` to HTTP 409 (422 for invalid_session_source); prime the SSE generator so conflict still sets status.
- green: `after.json` replay same message 200+same id; different message 409 `idempotency_key_conflict`; stream 409. `tests/test_api.py` 2 passed.
- not a product GO. Live host process must be restarted to pick up the mapping.
独立审查：`../../reviews/K05-review.md` — **PASS**（冲突 409；相同请求复用 message_id；live 重启后亦 409）。审查者 TestClient 不是 live L3 主 oracle。实现者自测不算验收。
