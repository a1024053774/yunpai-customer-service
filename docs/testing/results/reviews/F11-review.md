# F11 independent review

Reviewer: detached Cursor Grok 4.6 (fresh epoch, no resume of 38f47030 / d67d6978 / aee7ee28 / 3a096236 / 661d8cf3). Did not use Luna. Product code, tests, git, and CASES.json were not edited. Only these two review files were written.

STATUS: PASS
TARGET: frozen F11 candidate evolution.py sha256 7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310
EVIDENCE:
- Handbook F11 (`docs/agent-testing-manual.md`): after evaluate, change candidate text, source, knowledge version, or approval scope, then approve. Pass if evaluate binds concrete candidate content and dependency versions; a change requires re-eval; old `gate_passed` must not publish new content.
- Reviewer contract (handbook, not implementer labels): after evaluate passes, changing candidate text/source/scope must not approve/publish on the old `gate_passed`. Evaluate must bind concrete candidate content. A change requires re-eval.
- Implementer `docs/testing/results/defects/F11-mutate-after-eval/after.json` and `how-fixed.md` are labeled PASS. Inspected only; not accepted.
- Freeze check at review start, after probes, and immediately before this write: `src/yunpai_customer_service/evolution.py` UTF-8 sha256 `7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310` (match). Snapshot did not move.
- Frozen bind: `_candidate_content_bind` checksums `question`, `proposed_answer`, `evidence_source`, `intent`. `evaluate()` stores that digest in `gate_report.bound_content`. `approve()` raises `EvolutionError: candidate changed after evaluation` when the digest is missing or mismatches the current row. Check runs inside `db._write_lock` before leftover reuse and before `knowledge.add_document`.
- Independent in-process probes (reviewer-authored; not implementer after.json):
  - `/tmp/f11-review-20260911-epoch3/probe_f11.py` and `/tmp/f11-review-20260911-epoch3/probe_result.json`
  - `DATA_DIR` under `/tmp/f11-review-20260911-epoch3/data/`
  - Project `.venv/bin/python`; `TableDrivenModel` + `LEARNED_QUESTION` / `LEARNED_ANSWER` from `tests/test_customer_service_module_knowledge.py`
  - Probe recorded `hash_start` = `hash_end` = `7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310`
- Control: evaluate then approve without mutate succeeded (`status=approved`). Setup is valid; bind is not a blanket approve-blocker.
- Required probe 1: after evaluate (`status=evaluated`, `gate_passed=1`), SQL-mutate `proposed_answer` to `MUTATED-AFTER-EVALUATE microwave allowed 99999 units`. `approve()` raised `EvolutionError: candidate changed after evaluation`. Candidate stayed `evaluated`. Knowledge scan for `MUTATED-AFTER-EVALUATE` and for `MUTATED-AFTER-EVALUATE 99999` returned no rows.
- Required probe 2: after evaluate, SQL-mutate `evidence_source` to `MUTATED-SOURCE-AFTER-EVALUATE 99999`. `approve()` raised the same error. Candidate stayed `evaluated`.
- Extra cheap probes: mutate `question` after evaluate → rejected; mutate `intent` after evaluate → rejected. Re-evaluate after a benign answer suffix wrote a new `bound_content` (`a196a0c6...` → `03fc60eb...`).
- F09 leftover vs F11 bind: pre-seeded an active leftover knowledge row with `source=evolution:{id}` then SQL-mutated `proposed_answer`. `approve()` still raised the bind error; candidate stayed `evaluated`; mutated text was not in knowledge. Leftover reuse / approve lock / reject CAS do not skip the bind check.
- Known-bad still rejected: after evaluate, strip `bound_content` from `gate_report_json` and SQL-mutate the answer. `approve()` still raised (missing bind is treated as changed). Mutated text not published.
- Residual scope probe (not the required text/source probes): SQL-mutate `tenant_id` after evaluate. `approve(..., tenant_id=original)` raised `candidate not found`. `approve(..., tenant_id=other-tenant-f11)` succeeded and inserted active knowledge under that tenant with the originally evaluated answer (not the mutated sentinel).
FINDINGS:
- [P3] `src/yunpai_customer_service/evolution.py` `_candidate_content_bind` (lines 20-26) and `approve()` (lines 296-298) — bind omits `tenant_id` and any knowledge/dependency version. After evaluate, changing the row `tenant_id` and calling `approve` with the new tenant published the already-evaluated answer under `other-tenant-f11` on the old `gate_passed`. This does not publish unevaluated mutated text and does not break the required text/source bind. Simpler completeness fix: include `tenant_id` (and a cheap knowledge-state digest if dependency versions are in scope) in the same bind.
COUNTEREXAMPLE:
- Known-bad implementation that must be rejected: `approve()` checks only `status==evaluated` and `gate_passed==1` after candidate text/source change. Rejected on this frozen file. Mutated answer and mutated source both raise; knowledge does not contain `MUTATED-AFTER-EVALUATE 99999`.
- Historical `before.json` (pre-bind HEAD): same SQL mutate of `proposed_answer` approved and published the mutated text (`leaked_mutated=true`). That is the red counterexample; it does not replay on `7589cda0`.
- `/tmp` strip of `bound_content` plus mutate is also rejected by the current `if not bound` check, so a missing-fingerprint row cannot publish on the old gate either.
LIMITATIONS:
- No live HTTP/UI. Not required for this L1 service-gate case.
- Implementer `after.json` PASS ignored.
- Knowledge-version mutation after evaluate was not separately executed; tenant/scope residual is the measured completeness gap.
- Prior `F11-review-epoch2-incomplete.md` INCOMPLETE verdict was not copied.
- F09 approve lock / leftover reuse / reject CAS were judged only against the F11 bind; they were not re-litigated as F09.
