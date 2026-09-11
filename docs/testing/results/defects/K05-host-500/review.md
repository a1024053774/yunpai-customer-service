# K05 host idempotency conflict — independent review

STATUS: PASS
TARGET: dirty tree `src/yunpai_customer_service/api.py` (untracked; HEAD `8ea1329e` has no this file)
REVIEWER: cursor-grok-4.6-xhigh-fast-fresh
EDITED_CODE: false

## Contract (rebuilt, not from implementer prose)

Same `Idempotency-Key` + different message on host `POST /v1/chat` must not be HTTP 500. It must refuse with a conflict status and must not return the previous answer as success. Replay of the identical request may reuse the original message id.

## Evidence

Red (original, pre-candidate live + TestClient):

- `before.json` (2026-09-11T08:19:00Z): first 200, second 500, body `"Internal Server Error"`.
- `error.png`: screenshot of that red JSON.
- `live/live-results.json` row `K05-idempotency-conflict` (saved 2026-09-11T08:17:36Z, before the TestClient red/green files): `status_code` 500, `body_preview` `"Internal Server Error"`, case marked `INCOMPLETE`. Live probe used a different message on the same key after a successful identical replay (K04 PASS).

Green (independent re-run on current dirty tree, not `after.json`):

- Command: `.venv/bin/python` TestClient against `create_api_app` with isolated `/tmp` data dir, `TableDrivenModel`, unique key `k05-review-key`.
- Result written to `review-green.json` (2026-09-11T08:22:25Z):
  - first `POST /v1/chat` ? 200, `message_id` `msg-ca8ab2b6a6de52a59ea72aafd843d198`
  - identical replay ? 200, same `message_id`
  - different message ? 409, `detail.code` `idempotency_key_conflict`, no `answer` field, `reused_previous_answer` false
  - `POST /v1/chat/stream` different message ? 409, same conflict body

Product mapping observed in current `api.py`: `core.chat` / first `next(core.chat_stream)` catch `SessionScopeError` and raise `HTTPException` via `_http_for_session_scope` (409 unless `invalid_session_source`). Core `prepare_invocation` raises `SessionScopeError(..., code="idempotency_key_conflict")` when session/request hash differs.

`after.json` also records 409/PASS; it was not used as the oracle.

## Counterexample

A host adapter that lets `SessionScopeError` escape produces HTTP 500 (`before.json`, live K05 row). The current adapter maps that exception to 409 with `idempotency_key_conflict` and does not replay the prior chat payload as 200.

## Findings

None that violate the contract on the current dirty-tree host adapter.

## Limitations

- Independent check is in-process FastAPI TestClient, not a restarted live L3 uvicorn process.
- The live K05 row is stale relative to this candidate (08:17Z, 500). That process was not re-hit.
- Model was the table-driven test double; the contract is HTTP status/body mapping, not answer quality.
- Stream conflicts after the first SSE frame are outside this defect’s observed failure mode.
