STATUS: PASS
TARGET: frozen F09 candidate (dirty evolution.py approve lock, sha256 9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf)
EVIDENCE:
- Handbook F09 (`docs/agent-testing-manual.md`): two concurrent approve/reject/rollback must not make mutually exclusive states true at once, must not create duplicate versions, and must not silently approve something that cannot be retrieved. Required probe for this review: two threads approve the same evaluated candidate; PASS only if at most one success and at most one active knowledge row.
- Frozen file `src/yunpai_customer_service/evolution.py` sha256 UTF-8 text `9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf` matched before the probe, after the probe, and immediately before writing this report.
- Implementer `docs/testing/results/defects/F09-concurrent-approve/after.json`, `how-fixed.md`, and `success.png` are labeled PASS. Inspected only; not accepted as the oracle.
- Historical `before.json`: successes `[op-b, op-a]`, two active knowledge rows, `duplicate=true`. Used as the known-bad shape, not as after-fix proof.
- Independent probe `/tmp/f09-review-probe/probe_f09.py` imported workspace `evolution.py` (not the implementer script). Isolated `DATA_DIR`, `TableDrivenModel`, unique session/evidence nonce, `threading.Barrier`, two threads calling `EvolutionService.approve` on one evaluated candidate.
- Locked result: evaluate_passed=true; successes=`[op-b:approved]`; errors=`[op-a:EvolutionError:candidate must pass evaluation before approval]`; active_count=1; knowledge id `kb-39aabf74ce4a4f179c5b17ff3b12f101`; candidate.status=`approved`; `resulting_knowledge_id` equals that id; `get_document` status=`active`; `retrieve()` hit the same id (score 0.8801). Verdict PASS.
- Public entry exercised: `EvolutionService.approve`, the same method as Demo `POST /api/evolution/candidates/{candidate_id}/approve`.
- Structural gates on the lock: reachability is the real approve caller; ownership stays on `EvolutionService` plus existing `Database._write_lock` (RLock); no new wrapper, fallback, compatibility branch, or second approve API. `approve()` holds `_write_lock` around get + `add_document` + conditional `UPDATE ... WHERE id=? AND status='evaluated' AND gate_passed=1`; `rowcount != 1` retires the just-written document. `add_document` / `retire_document` / `audit` re-enter the same RLock, which is why RLock is required.
FINDINGS:
- none confirmed on the frozen concurrent-approve path
COUNTEREXAMPLE:
- `/tmp/f09-counterfactual/src` copy only; workspace product source was not edited. `approve()` outer lock and claim `UPDATE` removed; bind check left in place. Same two-thread probe imported `/tmp/f09-counterfactual/src/yunpai_customer_service/evolution.py`.
- Unlocked result: evaluate_passed=true; successes=`[op-b:approved, op-a:approved]`; errors=`[]`; active_count=2; ids `kb-39f4d250c24b4b3d9b234d25e30b129a` and `kb-d1822004492c4ab18dc312721ff35c32`; both `status=active`, both `version=1`, same `evolution:` source. Candidate points at only one row. Verdict FAIL. This is the known-bad implementation the lock/claim must reject, and it matches `before.json`.
LIMITATIONS:
- Handbook F09 also names concurrent reject/rollback and mid-publish DB crash; those were not re-probed.
- `reject()` still reads status outside the lock and `UPDATE`s without a status predicate. That is pre-existing, not introduced by this approve lock, and was not scored as FAIL on this approve-only snapshot.
- `_write_lock` is process-local. Two OS processes were not probed. The claim `UPDATE` plus retire is the cross-process backstop and was not independently executed (the in-process loser failed at the status check before `add_document`).
- L1 in-process threads + table-driven model + hash embedding. Not L3 HTTP/UI.
- Implementer `after.json` IDs differ from this probe and were ignored as acceptance.
