# K04 concurrent HTTP 500 — design-integrity review

- Reviewer: independent read-only (fresh context; not the implementer)
- Skill: design-integrity-review (reachability, ownership, architecture, proportion)
- Scope: handbook K04 slice only — same Idempotency-Key + same body, concurrent host `/v1/chat`: both HTTP 200, same `message_id`, never HTTP 500
- Candidate: HEAD `8ea1329e8fd495cff3887bbed05ab4b5b9da8c99` + dirty tree frozen at `docs/testing/run-20260911-product-followup/freeze-after-k04.json`
- Verdict: **PASS**

This review does not treat `how-fixed.md` as proof. Product code, tests, Skills, git, and other reviews were not edited.

## Snapshot

| Item | Observed |
| --- | --- |
| HEAD | `8ea1329e8fd495cff3887bbed05ab4b5b9da8c99` (matches freeze.json and freeze-after-k04.json) |
| Worktree | dirty; freeze.json stage0 candidate sha256 `801e8ae1…`; after K04 `340f188d…` |
| Product delta vs stage0 | **only** `src/yunpai_customer_service/graph.py` (`5667a637…` → `165f8f4a…`); current file hash matches freeze-after-k04 |
| `core.py` | unchanged vs stage0 (`fcea71c4…`) |
| `api.py` | unchanged vs stage0 (`e268c2b3…`) |
| Skill | `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md` sha256 `89ae938a…` unchanged |

`git diff HEAD -- src/yunpai_customer_service/graph.py` contains other hunks besides `persist_response`. Those other hunks are already in the stage0 freeze (only `graph.py` hash moved after K04). The K04-specific persist change vs the committed `persist_response` is the loser SELECT after `UPDATE … status='running'` `rowcount != 1`.

## What was opened

Red (not overwritten):

- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/before.json`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/before.html`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/error.png`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/probe_red.py`
- `docs/testing/run-20260911-product-followup/live/live-results.json` case id `K04`

Green:

- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/after.json`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/after.html`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/success.png`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/probe_green.py`
- `docs/testing/run-20260911-product-followup/live/k04-after-restart.json`
- `docs/testing/run-20260911-product-followup/live/restart-after-k04.json` (PID change only; corroboration)

Inspected, not treated as oracle: `how-fixed.md`.

Code opened:

- `src/yunpai_customer_service/graph.py` `persist_response` (lines 138–282) and persist node (1391–1392)
- `src/yunpai_customer_service/customer_service/core.py` `chat()` after persist (323–331), `prepare_invocation` running path (720–734), `_graph_input` (619–633), `invocation_response` (737–741)
- `src/yunpai_customer_service/api.py` `/v1/chat` (78–94) — only `SessionScopeError` is translated; `RuntimeError` is unhandled → HTTP 500

Not re-run: `probe_green.py` writes `after.json` in place. Re-running it would overwrite the frozen green artifact. Existing `after.json` and live-after-restart files were used instead.

No new servers started. No credentials guessed. No production writes.

## 1. Red evidence is 200+500 on the persist completion path, not a setup failure

**Live L3 (before the fix),** `live/live-results.json` saved 2026-09-11T09:26:16Z, case `K04`:

- sequential replay: HTTP 200, `same_message_id: true`
- SSE replay: HTTP 200, `sse_same_message_id: true`
- concurrent same body: `[{status: 200, message_id: "msg-c4aac619b4605d628508a47b4f248798"}, {status: 500, message_id: null}]`
- case status `INCOMPLETE` because of that concurrent 500

A setup/auth/key failure would not produce a 200 winner plus a 500 loser after sequential and SSE replay already succeeded on the same host process.

**TestClient red,** `before.json` saved 2026-09-11T09:27:47Z, `probe_red.py` (`raise_server_exceptions=False`):

- `status_codes: [200, 500]`, `has_500: true`
- first body is a full `/v1/chat` JSON with `message_id` `msg-1c165c52a6f65349956ff27d607f401e` and the table-driven stand-in answer
- second body is the Starlette default `"Internal Server Error"`

`before.html` / `error.png` additionally quote `RuntimeError: agent invocation completion was not persisted` as `live_log`. That string is **implementer-authored HTML**, not a saved uvicorn traceback file (none exists under this run’s defect or live folders). The exception class on the live 500 is therefore inferred, not captured as a raw log.

The inference is still the persist path, not setup:

- committed/stage0 `persist_response` does `UPDATE … WHERE status='running'` then `if cursor.rowcount != 1: raise RuntimeError("agent invocation completion was not persisted")` (`graph.py` 223–251; HEAD raised immediately at rowcount 0)
- `prepare_invocation` returns `status == "running"` for a second in-flight same key (`core.py` 720–734), so both requests invoke the graph
- `api.py` `/v1/chat` (78–94) does not catch `RuntimeError`

**Confirmed:** red is 200+500 on the exclusive-UPDATE loser path. Missing raw live traceback is an evidence-packaging gap, not a different failure mode.

## 2. Root-cause layer is `persist_response`, not a wrapper API

Reachability: concurrent same key + same body → both see `running` → both run the graph → winner’s `UPDATE … status='running'` returns rowcount 1 → loser’s same UPDATE returns 0 → previously raised → HTTP 500.

Ownership: `persist_response` already owns the completion UPDATE and the “was this invocation durably completed?” check. Interpreting rowcount 0 as “winner already stored `completed` + `response_json`” belongs here. HTTP mapping stays in `api.py`; response reconstruction stays in `core.chat` / `invocation_response`.

Architecture: no second persist API, no HTTP retry, no compatibility `/v1/chat` branch, no `core.py` change. The exclusive UPDATE remains the single writer. The loser only **observes** the winner row.

Proportion: the after-K04 product delta vs stage0 is this `graph.py` function. Added control flow (`graph.py` 238–251):

```
if cursor.rowcount != 1:
    saved = SELECT status, response_json …
    if saved is None or saved["status"] != "completed" or not saved["response_json"]:
        raise RuntimeError("agent invocation completion was not persisted")
```

That is not a fallback that writes a second completion. Loser INSERT of messages remains `INSERT OR IGNORE` (already present).

## 3. After the change, loser does not 500; `core.chat` still returns the stored invocation

`core.py` was not part of the K04 delta. After `graph.invoke` returns, `chat()` still does (`core.py` 323–331):

- SELECT the invocation row
- raise `RuntimeError("idempotent agent invocation did not reach a durable result")` if missing or not `completed`
- `return self.invocation_response(dict(saved_invocation))` which requires non-empty `response_json` (`core.py` 737–741)

So the HTTP body is the **durable stored** payload, not the loser’s in-memory graph state. Stable ids come from `prepare_invocation` (`msg-{stable}` / `trace-{stable}`) via `_graph_input` (`core.py` 626–629).

No new `except` was added around persist. If the row is absent, still `running`, or `completed` with empty `response_json`, `persist_response` still raises the same `RuntimeError`. `chat()` still re-raises graph exceptions after recording `last_error` (`core.py` 274–310) — it does not swallow an unpersisted failure into HTTP 200.

## 4. Green TestClient and live-after-restart

**TestClient** `after.json` (2026-09-11T09:31:17Z): statuses `[200, 200]`, `message_ids` both `msg-dc12bfef691b5ea79285eb2ee1ce96ae`, `has_500: false`. `success.png` matches that JSON. Probe is in-process `TestClient` + `TableDrivenModel`, not the live host.

**Live after process restart** `live/k04-after-restart.json` (2026-09-11T09:37:21Z): host `127.0.0.1:55723`, `runtime_pid` 37044, statuses `[200, 200]`, `message_ids` both `msg-83d415062a7e5db9aa4a20cb317d6081`, `has_500: false`.

`live/restart-after-k04.json` records `pid_before` 11189 → `pid_after` 37044, same `DATA_DIR` `/private/tmp/yunpai-followup-20260911`, health 200 on demo and host. `runtime-start.json` documents the original isolated PID 11189 before that restart.

These two greens are **independent**:

- different transport (in-process TestClient vs loopback host HTTP)
- different `message_id` values
- different clocks (09:31 vs 09:37)
- live green required a new uvicorn PID to load `graph.py` (original process 11189 could not have been the TestClient)

Neither is pytest-only, retrieve-only, or a keyword checker. This is not a product GO; it is GO only for this concurrent HTTP slice.

## Confirmed findings

**None** in the contracted slice.

No confirmed swallowed-exception finding: the new branch still raises when completion is not durable (`graph.py` 246–251). `core.chat` still refuses a non-completed invocation (`core.py` 329–330).

## Remaining unclaimed (must not be treated as closed)

1. **Crash-recovery restart retry.** A `running` row after a process crash is still retried by `prepare_invocation` (`core.py` 720–728). This fix does not define restart semantics.
2. **At-most-once side effects.** Both in-flight requests can still execute the full graph (model/tools). Loser `persist_response` still runs `db.audit("chat.completed")` and may call `sops.mark_handoff` (`graph.py` 252–281) after observing the winner. Handbook “side effects at most once” is open.
3. **Full handbook K04** beyond concurrent same-key HTTP 200 / same `message_id` / never 500. Sequential and SSE replay were already 200 before this fix (`live-results.json` K04) and are not re-proven here as a full-row close.
4. **Product GO.** Out of scope.

## Structural gates (summary)

| Gate | Result |
| --- | --- |
| Reachability | Concurrent same key, both `running`, UPDATE rowcount 0 → previous 500. Red 200+500 on live host and TestClient. |
| Ownership | Persist layer owns exclusive completion UPDATE; chat owns returning stored `response_json`. |
| Architecture | Existing UPDATE + `invocation_response` carry the behavior; no parallel API. |
| Proportion | Isolated `persist_response` loser observe path; `core.py` / `api.py` / Skill unchanged. |

## Verdict

**PASS** for the contracted K04 concurrent host `/v1/chat` slice: both 200, same `message_id`, never 500, root-cause persist UPDATE loser path, durable stored response, live restart evidence independent of TestClient. Gaps listed above stay unclaimed.
