# 7.2 independent review

Reviewer: detached Cursor Grok 4.6 [7.2 审查](93832a6f-bab4-4e4d-9203-97fc95d54c36). Fresh, no resume. Did not use Luna.
Told not to write files; parent landed this report from the returned verdict.
Implementer after.json / 72-unit-mismatch/ inspected only.

STATUS: PASS
TARGET: frozen policy.py sha256 7d05f60604b3121d4b360f0e14e07499450f1405ae8a13b1b427bfd892628014

## EVIDENCE
- policy.py hash matched before probes, after a failed retrieve typo, and after the completed /tmp chat probe.
- Independent review_output("QA-72 kettle warranty is 5 years.", "QA-72 kettle capacity is 5L rice-white.") -> (False, numeric_unit_mismatch). Pairs: answer {(5, year)}, evidence {(5, L)}. Number-only subtraction is empty, so the pre-fix rule would still pass.
- Independent core.chat with TableDrivenModel draft=5-years, fixture evidence 5L: user-visible handoff fallback; reason=numeric_unit_mismatch; requires_human=true; trace verify:numeric_unit_mismatch then postcondition:handoff. Answer and persist omit "5 year".
- Variants also fail against 5L: Chinese 5年, hyphen 5-year warranty. Evidenced 5L still passes.
- G05 ordinal still passes. Unevidenced 1.99 / 95% still fail numeric_claim_without_evidence.
- Structural: unit check lives in review_output plus helpers in the same policy.py. No new wrapper module.

## FINDINGS
- none in handbook 7.2 step 5 scope

## COUNTEREXAMPLE
- Known-bad number-only gate accepts 5-years against 5L; frozen candidate rejects it. Legal ordinals still accepted.

## LIMITATIONS
- Isolated fixture + review_output pair, not live host/SSE/L3.
- Matcher is bag-of-(number, unit) pairs. "5 yrs" and spelled-out "five years" still pass review_output against 5L evidence. A retrieved chunk that already contains "5 years" would also satisfy the pair set.
- Frozen policy.py also widens FORBIDDEN_OUTPUT_PATTERNS; G01/G04/G07 were not re-audited.
