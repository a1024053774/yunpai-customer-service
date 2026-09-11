# knowledge-pdf run-20260910-1739-grok46

Executor: Cursor Grok 4.6 (not Luna). Candidate `/tmp/yunpai-test-candidate-grok46-pZG5r3`. Original `src/` was not modified. No paid chat models. No public servers.

## Pytest

- Command: `pytest -q --tb=short` on `tests/test_customer_service_module_knowledge.py`, `tests/test_embeddings.py`, `tests/test_knowledge_ingest.py`
- Env: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=/tmp/yunpai-test-candidate-grok46-pZG5r3/src`, `ALL_PROXY=http://127.0.0.1:9`, `NO_PROXY=127.0.0.1,localhost`
- Result: **15 passed, 0 failed, 0 skipped**, exit 0, 112.83s
- Warnings show real Docling 2.126.0 on the two PDF import tests (`force_full_page_ocr` / RapidOCR)

## Counts (handbook + ISSUE + 7.4–7.7)

| Status | Count | IDs |
|---|---|---|
| PASS | 7 | D05, E01, F02, F03, F07, ISSUE-12, ISSUE-13 |
| FAIL | 2 | **D07**, **7.6** (same mix-acceptance finding) |
| INCOMPLETE | 15 | D03, D06, D08, E02, E03, E07, E08, E10, I09, F01, F08, A04, 7.4, 7.5, 7.7 |

Partial coverage is INCOMPLETE, not PASS.

## FAIL

**D07 / 7.6 step 3:** same-dimension different-model vectors are not rejected.

- `FastEmbedProvider.name` is the family string `fastembed`, not a concrete model id.
- Knowledge rows persist only an embedding BLOB; no provider/model/dimension/index version columns.
- L1 probe: store `(1,0,0,0)` as model-a, switch to model-b `(0,1,0,0)`, `retrieve()` still returns the document; `rebuild_embeddings()` also runs with no identity check.
- Score path: equal vector length then cosine, else semantic=0. Matching dimension is treated as comparable.
- No product fix in this run.

## Mapped claims that passed

- D03 tenant isolation L1 assertion passed; missing/forged `store_id` not run → ID remains INCOMPLETE
- D05 exact reuse vs near-miss L1 PASS
- F02 repeated correction idempotent L1 PASS
- F03 `gate=false` cannot `approve` L1 PASS
- F07 learn/reuse L1 PASS; F08 in-process rollback passed but restart not run → F08 INCOMPLETE
- E01 **L2-parser PASS for electronic PDF only**: opened `fixture-catalog.pdf` with pdfplumber and `pdftotext`; Chinese is real (`空气炸锅容量 5L`, `适合 3-4 人家庭`, `售后保修一年`), not `nnnn`. ingest_document kept those phrases and the 容量/5L table. ISSUE-13 PASS.
- E02 mixed order is monkeypatched L1 (ISSUE-12 PASS). Not scanned-OCR. E03 INCOMPLETE (no real scan PDF with human truth).
- E10/I09: knowledge-row prompt injection dropped L1; other channels not run → INCOMPLETE
- A04/D07 partial: hash provider explicit and unknown provider fails at config; model identity not persisted → A04 INCOMPLETE, D07 FAIL

## Extra probes

- Docling importable: **2.126.0** (`DocumentConverter` ok). Electronic ingest tests used it. That is L2 parser for electronic/synthetic PDF, not E03.
- Embedding identity: not persisted. Same-dim mix accepted (D07 FAIL).
- Chinese PDF artifacts: `fixture-catalog.pdf`, `fixture-catalog.extracted.txt`, `fixture-catalog.pdftotext.txt`

## Not in this pytest set

- FastEmbed restart (D06) — `test_demo_restart_keeps_the_selected_embedding_backend` is in `test_framework_audit.py`
- Cross-tenant original files (full E08) — also `test_framework_audit.py`
- Rebuild half-failure / two-process (D08)
- Paid chat Q&A after import
