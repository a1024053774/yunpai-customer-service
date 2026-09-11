# Design-integrity gate follow-up

The frozen review found one confirmed P1 in the crash probe: a broad `except Exception`
classified unrelated failures as the expected crash-recovery gap. The main agent corrected
the probe to catch only `SessionScopeError`, require
`code == "idempotency_in_progress"`, require `running + last_error is null`, and return a
nonzero exit for unexpected outcomes.

`crash-probe-contract.json` independently checks the source boundary and reports zero broad
exception handlers. The corrected reproduction is `crash-recovery-before-v3.json`.

The original review result remains **FAIL** for the frozen pre-fix candidate; this follow-up
does not upgrade full K04. Crash recovery itself remains **INCOMPLETE** because the product
still has no explicit owner lease/takeover policy.
