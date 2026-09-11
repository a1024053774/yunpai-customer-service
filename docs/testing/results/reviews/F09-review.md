STATUS: PASS
TARGET: frozen F09 candidate evolution.py sha256 7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310
EVIDENCE:
- Reviewer: detached Cursor Grok 4.6. Fresh context. Did not resume 3a096236 / aee7ee28 / d67d6978 / 38f47030. Did not use Luna. Product code, tests, git, and CASES.json were not edited.
- Handbook F09 (`docs/agent-testing-manual.md`): input `两人并发批准/拒绝/回滚；发布途中断库`; pass `不出现互斥状态同时成立、重复版本或批准但不可检索的静默状态`. Full contract used here: concurrent approve/reject/rollback must not make mutually exclusive states true, must not create duplicate versions, and must not silently approve something that cannot be retrieved. Epoch1 `F09-review-epoch1-two-approve.md` PASS is two-approve only and is not the oracle.
- Frozen `src/yunpai_customer_service/evolution.py` UTF-8 sha256 `7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310` matched before probes, after probes, and immediately before this write.
- Implementer `review-fail-after.json` / `how-fixed.md` labeled green. Inspected only; not accepted.
- Historical `review-fail-before.json`: approve+reject `rejected_plus_active=8` and `both_ok=8`; leftover `duplicate_active=true` (orphan plus a new active row). Known-bad shape, not after-fix proof.
- Independent probes imported workspace `evolution.py` (not implementer scripts). `/tmp` `DATA_DIR`. `TableDrivenModel` + `LEARNED_QUESTION` / `LEARNED_ANSWER`. Unique core/tempdir per approve+reject trial. Public entry: `EvolutionService.approve` / `reject` (same methods as Demo `POST /api/evolution/candidates/{id}/approve` and `/reject`).
- Probe 1 `/tmp/f09-review-epoch2/probe_f09.py` two-thread approve: evaluate_passed=true; successes=`[b:approved]`; errors=`[a:EvolutionError:candidate must pass evaluation before approval]`; active_count=1 id `kb-18a09393a1594fdb9ebb1398798cbc17`; candidate.status=`approved`; `resulting_knowledge_id` equals that id; `get_document` status=`active`; `retrieve()` hit the same id (score 0.8801). Verdict PASS.
- Probe 2 same script, 8 unique-core approve+reject trials: `rejected_plus_active=0`, `both_ok=0`. All 8 were reject-first (`reject-ok` + `approve:EvolutionError`, status=`rejected`, active=0). Scheduling follow-up `/tmp/f09-review-epoch2/probe_f09_sched.py` forced both orders (4 delay-reject, 4 delay-approve): approve_wins=4 (status=`approved`, active=1, reject `EvolutionError`); reject_wins=4 (status=`rejected`, active=0); `rejected_plus_active=0`; `both_ok=0`. Verdict PASS.
- Probe 3 leftover: inserted active `kb-018988bd671b4456abaa1027a5d4cefa` with `source=evolution:{id}` while status was still `evaluated`, then one `approve()`. active_count=1; candidate attached the leftover id; `reused_orphan=true`; `duplicate_active=false`. Verdict PASS.
- Structural gates: reachability is the real approve/reject callers. Ownership stays on `EvolutionService` plus existing `Database._write_lock` (RLock at `database.py`). No new wrapper module, fallback API, or second approve/reject path. `approve()` (lines 287-351) holds the RLock around get + leftover reuse-or-`add_document` + `UPDATE ... WHERE id=? AND status='evaluated' AND gate_passed=1`; `rowcount != 1` retires only a row this call inserted. `reject()` (lines 356-374) holds the same RLock and CAS `UPDATE ... WHERE id=? AND status IN ('pending','evaluated')`. `add_document` / `retire_document` / `audit` re-enter the RLock.
FINDINGS:
- none confirmed on the frozen full handbook F09 path
COUNTEREXAMPLE:
- `/tmp/f09-review-epoch2/counterfactual/src` copy only; workspace product source was not edited. Copy removed leftover reuse (always `add_document`) and restored unlocked reject (`get` then `UPDATE` with no status predicate). Same leftover and approve-then-reject probes imported that copy (`/private/tmp/f09-review-epoch2/counterfactual/src/yunpai_customer_service/evolution.py`).
- Leftover without reuse: evaluate_passed=true; approve ok; candidate pointed at new `kb-a6f2c600035c4091ad584909ec063cb6`; leftover `kb-1fb559ffaa024a29b1c61f8f671f39cb` stayed active; `duplicate_active=true`; `reused_orphan=false`. Matches `review-fail-before.json` leftover shape.
- Unlocked reject window (check-then-act, no predicate): events=`[approve-ok, reject-ok]`; candidate.status=`rejected` with `resulting_knowledge_id` set; active_count=1; `both_ok=true`; `rejected_plus_active=true`. Matches `review-fail-before.json` approve+reject shape. Frozen lock+CAS rejected this implementation.
LIMITATIONS:
- Mid-publish crash was not injected; leftover insert is the retry stand-in for a row written before the claim `UPDATE`.
- Concurrent rollback was inspected (`retire_document` CAS) but not independently raced. No reproduced rollback violation.
- `_write_lock` is process-local. Two OS processes were not probed. The claim `UPDATE`s are the cross-process backstop.
- L1 in-process threads + table-driven model + hash embedding. Not L3 HTTP/UI.
- Implementer after JSON IDs differ from these probes and were ignored as acceptance.
