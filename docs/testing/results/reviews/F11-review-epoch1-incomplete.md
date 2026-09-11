# F11 independent review

Reviewer: detached Cursor Grok 4.6 (fresh, no resume). Did not use Luna. Product code, tests, git, and CASES.json were not edited.

STATUS: INCOMPLETE
TARGET: frozen F11 candidate (dirty evolution.py bind)
EVIDENCE:
- Handbook F11 (`docs/agent-testing-manual.md`): after evaluate, change candidate text, source, knowledge version, or approval scope, then approve. Pass only if evaluate binds the concrete candidate content and dependency versions; a change requires re-eval; old `gate_passed` must not publish new content.
- Reviewer contract (handbook, not implementer labels): after evaluate passes, changing candidate text/source/scope must not approve/publish on the old `gate_passed`.
- Implementer `docs/testing/results/defects/F11-mutate-after-eval/after.json` and `how-fixed.md` are labeled PASS. Inspected only; not accepted. `docs/testing/results/CASES.json` still has F11 `NOT_RUN`.
- First dirty snapshot inspected: `src/yunpai_customer_service/evolution.py` sha256 `d50cec8efa31c71a209bb931f6691c3ec830b8aa7aa62e1d0e9912187da34b90`. `_candidate_content_bind` hashed `question`, `proposed_answer`, `evidence_source`, `intent`. `evaluate()` wrote `bound_content` into `gate_report_json`. `approve()` rejected when the stored bind was missing or mismatched.
- The same dirty file moved during this review:
  1. sha256 `7a014cbe08451f3d032c8461edfab617bfe17aa99de90ef620558558e2a1231f` - `IndentationError` in `approve()` (duplicate `with self.db._write_lock:`, broken `_approve_locked`). Independent in-process probe aborted on import.
  2. sha256 `9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf` - AST parses again; `approve()` now also holds `_write_lock` and claims the row with `AND status='evaluated' AND gate_passed=1`. This is not the snapshot first inspected.
- Reviewer probe `/tmp/f11-review-probe/probe_f11.py` never executed `evaluate()`/`approve()` against a frozen bind. No reviewer pytest. No `/tmp` counterfactual on a frozen copy.
- `before.json` (historical red only): evaluate passed; SQL-mutated `proposed_answer` to `MUTATED-AFTER-EVALUATE microwave allowed 99999 units`; `approve` succeeded; `leaked_mutated=true`. Not after-fix evidence.
FINDINGS:
- [P1] `src/yunpai_customer_service/evolution.py` - candidate not frozen. Dirty bind hash changed `d50cec8e...` -> `7a014cbe...` (unparseable) -> `9d260930...` during this review. Acceptance and structural gates require one snapshot; this review does not chase the later tree.
- [P2] First inspected bind (`d50cec8e`) omitted `tenant_id` and knowledge/dependency versions from `_candidate_content_bind`. Handbook F11 names knowledge version and approval scope. Not independently executed; not scored as FAIL on a moving file.
COUNTEREXAMPLE:
- Not executed on a frozen after-fix candidate.
- Historical known-bad (`before.json`): mutate `proposed_answer` after evaluate, keep `gate_passed=1`, approve published the mutated text. That is pre-bind HEAD behavior, not a replay of the current dirty file.
- The known-bad implementation that must be rejected is `approve()` checking only `status==evaluated` and `gate_passed==1`. A `/tmp` revert of the bind was not run because the workspace file kept changing.
LIMITATIONS:
- No independent behavioral probe of text, source, intent, tenant/scope, or knowledge-version mutation after evaluate.
- Implementer `after.json` PASS ignored.
- Current `9d260930` tree was not re-reviewed.
- Live HTTP/UI was not required for this L1 service-gate case and was not run.
