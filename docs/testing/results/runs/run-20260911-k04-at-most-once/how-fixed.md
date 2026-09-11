# K04 graph execution at-most-once slice

规范化红证据 `evidence-v4/before.json` showed two concurrent requests with the same idempotency key
returned the same durable `message_id` but executed model generation twice. That was a
side-effect/cost duplication hidden by response-level idempotency.

The root fix is in `src/yunpai_customer_service/customer_service/core.py`:

- a request that finds the same invocation in `running` waits for the existing owner;
- once the row becomes `completed`, it returns the stored response;
- if the owner does not complete within the bounded wait, it returns an explicit
  `idempotency_in_progress` conflict instead of starting a second graph execution;
- the first request still owns the graph and durable completion write.

`evidence-v4/after.json` records one generation call and two identical message IDs. This closes the
same-process concurrent graph-duplication slice. A process crash that leaves a `running`
row still requires a separate recovery policy and remains unclaimed for full K04.

The earlier top-level `before.json` is marked superseded in
`overwritten-evidence-note.json`; it was accidentally overwritten by a green rerun.

The focused broader regression command and raw output are recorded in
`evidence-v4/pytest-targeted.log` with `exit_code=0`; it reports 33 passed and one warning.
The full current-candidate `./.venv/bin/pytest -q` output is recorded in
`evidence-v4/pytest-full.log` with `exit_code=0`: 117 passed and 10 warnings.

The remaining crash-owner red state is preserved in `crash-recovery-before-v3.json`:
after an isolated owner disappears with a durable `running` row, a restarted core waits
30 seconds and returns `idempotency_in_progress`, leaving the row `running`. No recovery
policy was invented in this turn because taking over could repeat unknown side effects.

The evidence probe now catches only `SessionScopeError`, requires code
`idempotency_in_progress`, requires `running + last_error=null`, and exits nonzero for
unexpected outcomes. `crash-probe-contract.json` is the deterministic static check for
that boundary; it reports zero broad exception handlers.
