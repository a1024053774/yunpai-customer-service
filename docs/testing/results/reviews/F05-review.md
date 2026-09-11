# F05 independent review

Reviewer: detached Cursor Grok 4.6 [F05/F10 审查](9cf2baf8-2bf3-49f1-96f1-a7ff726491e4). Fresh, no resume. Did not use Luna.
Told not to write files; parent landed this report from the returned verdict.
Implementer after.json / how-fixed / success.png inspected only, not the oracle.

STATUS: PASS
TARGET: frozen evolution.py sha256 0973a53a8453518bd4dcfc212cc97120940d1f6a5ab3aace6acbd11f4b3c1137

## EVIDENCE
- Hash before and after independent probes matched freeze; snapshot did not move.
- Public path: CustomerServiceCore.evolution.submit_feedback then EvolutionService.evaluate (same as Demo /api/feedback and /api/evolution/candidates/{id}/evaluate). Isolated /tmp DATA_DIR. TableDrivenModel + LEARNED_QUESTION/LEARNED_ANSWER.
- F05 unseen false microwave correction + `https://totally-real.example/manual-page-99`: gate_passed=false, source_traceable=false. Only boolean failure: source_traceable. semantic_alignment stayed true (0.1338).
- F05 sentinel: LEARNED_ANSWER + same fake URL: gate_passed=false, source_traceable=false.
- Counterfactual: LEARNED_ANSWER + nonempty non-URL free text: gate_passed=true, source_traceable=true.
- Structural: `_URL_EVIDENCE_SOURCE` + `_source_traceable()` in evolution.py, called only from evaluate(). No new wrapper/fallback/parallel API.

## FINDINGS
- none in F05 scoped contract

## COUNTEREXAMPLE
- Known-bad nonempty fake https source is rejected (source_traceable=false => gate_passed=false).
- Known-good free-text candidate still accepted.

## LIMITATIONS
- Implemented as `http(s)://` prefix is not traceable, not content/version/scope verification of a cited page.
- A nonempty free-text fake source such as a handbook-page string would still be source_traceable=true.
- L1 isolated /tmp + table-driven model, not live Demo click-through.
- F09/F11 remain on older evolution hash; not re-opened.
