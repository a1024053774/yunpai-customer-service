# K04 how-fixed

- defect: Host `/v1/chat` concurrent same Idempotency-Key + same body returned HTTP 500 `Internal Server Error` instead of both 200 with the same `message_id`.
- red: live `live/live-results.json` concurrent `[{200, msg-c4aac619...}, {500, null}]`; server log `RuntimeError: agent invocation completion was not persisted`; TestClient `before.json` statuses `[200, 500]`.
- root cause: both requests see invocation `running` and both run the graph; winner UPDATEs `running` to `completed`; loser UPDATE `WHERE status='running'` has rowcount 0 and raised.
- fix: `src/yunpai_customer_service/graph.py` `persist_response` — if completion UPDATE rowcount != 1, SELECT; if already `completed` with `response_json`, continue; `core.chat` still returns the stored invocation response. Otherwise still raise.
- green TestClient: `after.json` both 200 same `message_id` (4/4 in probe_green). Live green requires process restart; see `live/k04-after-restart.json`.
- remaining: both requests can still execute the graph (double model cost); handbook "side effects at most once" and crash-restart retry are not closed. Not a product GO.
Independent review: `../../reviews/K04-review.md` and `defects/K04-concurrent-500/review.md` — **PASS** (concurrent same-key /v1/chat 200 + same message_id; live restart independent of TestClient). Crash-recovery, at-most-once graph, full handbook K04, and product GO remain unclaimed.
