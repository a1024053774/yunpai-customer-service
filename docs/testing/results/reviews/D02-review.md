# D02 independent review

Reviewer: detached Cursor Grok 4.6 (fresh, no resume). Agent `d5400c8a-4e26-4099-8192-e0dfc523e1cd`.
Implementer labels ignored.

STATUS: PASS
TARGET: HEAD 8ea1329e + dirty tree; D02 live 2026-09-11
EVIDENCE:
- docs/testing/results/defects/D02-missing-fields/before-live.json — same ask; sources SOP + Qingchuan; used_synthetic false; answer cannot locate the id; mode clarify.
- docs/testing/results/defects/D02-missing-fields/after-live.json — synthetic top-1 0.9733; answer names QA-GROK / 孤岛验收电热水壶; no invented stock/sales/ETA numbers; hedge has no quantity.
- docs/testing/results/defects/D02-missing-fields/after-live.html — same payload.
- docs/agent-testing-manual.md D02 + 3.1 — judged live JSON, not a green suite.
FINDINGS:
- none
COUNTEREXAMPLE:
- before-live treats QA-GROK as unknown and ranks Qingchuan/SOP; after-live retrieves the synthetic product first and refuses numeric stock/sales/ETA.
LIMITATIONS:
- One L3 live turn on isolated Demo; not L4. Does not prove other D0x questions, dual-embedding, or later LLM samples. HEAD alone is not the candidate.
