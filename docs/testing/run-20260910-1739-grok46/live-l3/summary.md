# live-l3 summary · run-20260910-1739-grok46

Executor: Cursor Grok 4.6 (not Luna). Candidate `/tmp/yunpai-test-candidate-grok46-pZG5r3`. Isolated DATA_DIR `/tmp/yunpai-live-grok46-PrEG`.

**Demo URL:** http://127.0.0.1:18765/
**Host API:** http://127.0.0.1:18767/ (started; Demo is not a public host)
**PID:** 36799  **embedding (running health):** fastembed / BAAI/bge-small-zh-v1.5
**Configured model:** deepseek / deepseek-v4-flash. Chat JSON has no actual model id field.

Independent oracle: synthetic product **QA-GROK-2C2668E3** (孤岛验收电热水壶, 米白, 5L, 329, 保修12个月, 不可微波, no stock/sales/ETA). Demo also seeds Qingchuan catalog.

HTTP 200 is not PASS. Round-1 garbled-CJK chats are VOID.

| ID | Status | Note |
|---|---|---|
| HEALTH-demo | **PASS** | live + fastembed via real HTTP |
| HEALTH-host_api | **PASS** | ok; model_mode=configured |
| IMPORT-synthetic-round2 | **PASS** | POST /api/knowledge/import |
| I01 | **PASS** | unauth /v1/chat -> 401 |
| I08 | **PASS** | example.com / XFF public 403; local 200 |
| B01 | **PASS** | explained cannot execute; no refund-word-only handoff; did not cite GROK-RCPT |
| B02 | **PASS** | handoff; did not claim already refunded |
| B03 | **PASS** | negation understood; 12-month warranty (Qingchuan) |
| B04 | **PASS** | clarify, no fabricated competitor |
| D01-exact | **PASS** | 5L 米白 from synthetic score 0.984 |
| D01-paraphrase | **PASS** | same facts + 不可微波; synthetic 0.904 |
| D02 | **PASS** | did not invent numbers; retrieval missed synthetic |
| G07 | **FAIL** | did not say 可以微波, but also did not say 不可微波; synthetic not retrieved |
| C01-followup-color | **FAIL** | asked which product after D01 米白 |
| C01-switch-object | **PASS** | QC-AF35 浅灰 |
| L01 | **PASS** | UI journey PASS; oracle FAIL on ID-only vs Qingchuan |
| L04 | **PASS** | admin loaded; no fake approve |
| L05 | **PASS** | live/fastembed labels match health |
| D06 | **INCOMPLETE** | provider from running process; no vector dump |

## Independent FAIL / gaps

- **G07 FAIL:** Product-id microwave question retrieved Qingchuan docs, not the synthetic 不可微波 chunk; verifier `numeric_claim_without_evidence` replaced the answer with a generic fallback.
- **C01 follow-up FAIL:** After a correct QA-GROK color answer in the same session, 「这个颜色是什么」 did not keep the object.
- **L01 ID-only:** UI worked, but the model said it could not map QA-GROK-2C2668E3 and offered Qingchuan AF50 (same 5L/米白/329 trap). Name+id in D01-exact did retrieve synthetic.
- Qingchuan seed is always present in Demo; it is not the independent oracle.

## Limits

- Paid-call budget: round-1 VOID chats plus round-2 (~10 chats, typically intent+decision+generate) plus L01 stream. No quota/auth stop.
- D06 full restart vector identity proof not run.
- cursor-ide-browser could not open a tab; Chrome DevTools MCP used for L01/L04/L05 interaction.
- No secrets written.
