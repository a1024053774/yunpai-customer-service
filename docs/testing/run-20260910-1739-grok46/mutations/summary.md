# Mutation evidence — run-20260910-1739-grok46

Executor: Cursor Grok 4.6 (not Luna). Candidate (read/copy only): `/tmp/yunpai-test-candidate-grok46-pZG5r3`. Mutate copy: `/tmp/yunpai-mutate-grok46-29943`. Workspace `src/` was never written. After each mutation, `src/` was restored from the candidate; the mutate copy is not the default Python import path.

Target tests (L1): `test_framework_audit` graph/policy/keyword/terminal cases, `test_customer_service_module` answer-identity cases, `test_demo_chat_answers_airfryer_capacity`.

## Baseline (clean candidate)

22 passed, exit 0. **No product defect** on this target set: the unmutated copy is green. A red baseline would have been a product FAIL; that did not happen.

## Caught (tests reject the wrong implementation)

| ID | Wrong implementation | Catching assertions | Exit |
|---|---|---|---|
| **P01 / mut-A** | `generate` always returns `??????-??` | `TABLE_MODEL_ANSWER` mismatch; `'5L' in answer` fails | 1 (3 failed) |
| **P01 / mut-B** | `decision_gate` always handoff | `requires_human is False` / `decision_mode == answer`; 5L knowledge answer | 1 (7 failed) |
| **P02 / mut-C** | skip verify node + passthrough terminal review | `calls == ['generate']` not `['generate','verify']`; `?????` / `??????` in user text | 1 (10 failed) |
| **P02 / mut-D** | `review_output` / `verify_response` always accept | same unsafe terminal strings; `(True, output_policy_passed) != (False, numeric_claim_without_evidence)` | 1 (12 failed) |
| **P02 / mut-E** | lexical if-refund / if-price / ?? intercept | mock refund ? chitchat; `business_action_requires_verified_execution`; competitor skips `agent_decision` | 1 (3 failed) |
| **P06 / mut-F** | wrong path / zero collection | pytest exit **4** (missing path) and **5** (0 collected / 109 deselected). Neither is exit 0. No `passed` line. | 4 / 5 |
| **7.1 step 5 / mut-G** | historical SSE: generate outside graph, `verify_response` + `update_state(as_node='verify')` | `SSE bypassed registered graph nodes`; SSE `calls == []` after sync | 1 (1 failed) |

Manual **7.2 steps 1–2 and 4** are covered by mut-C/D (unsafe terminal branches + unsupported numbers). mut-G matches historical `framework-red.txt` for ISSUE-01.

## Gaps (a test stayed green under the fault)

These are **test gaps**, not product PASS:

1. **`test_sync_and_sse_execute_the_registered_generate_and_verify_nodes` vs constant answers (mut-A).** It wraps `generate` and overwrites `draft` with its own sentinel, so a constant generate still looks like the graph “owns” the text. P01 is still CAUGHT by table-answer and 5L tests.
2. **`test_core_answers_a_knowledge_question_without_agent_service` vs constant answers (mut-A).** Only checks `response.answer` is truthy and `requires_human is False`. A fixed Chinese sentence satisfies it.
3. **`test_sync_and_sse_...` vs always-true verifier (mut-D).** It counts node calls, not review outcomes. Output-policy tests still fail, so P02-always-true is CAUGHT overall.
4. **Manual 7.2 step 5 (semantic 5L ? 5 years).** No existing test asserts that evidence containing `5` / `5L` cannot justify “?? 5 ?”. `test_business_numbers_still_require_evidence` is lexical/numeric, not relation/unit. Status: **GAP / INCOMPLETE** for that counterexample, not a product defect.

## Product defect on clean candidate?

**None** for the frozen target set. Baseline red did not occur.

## How 0 tests ? PASS (P06)

- Missing path: `pytest --collect-only tests/this_path_does_not_exist_p06` ? `ERROR: file or directory not found`, `no tests collected`, **exit 4**.
- Empty selection: `pytest -q -k p06_zero_collection_sentinel_no_such_test` ? `109 deselected`, **exit 5**, no passed count.

A report that treats collect-only success or a zero-test run as product PASS is invalid. Pytest only uses exit 0 when tests actually ran and passed.

Evidence: `commands.log`, `baseline/`, `mut-A` … `mut-G` (`diff.txt`, `fail.log`, `cases.json`).
