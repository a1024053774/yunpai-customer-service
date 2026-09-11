# G04 independent review

Reviewer: detached Cursor Grok 4.6 (fresh, no resume). Do not use Luna.
Implementer PASS/INCOMPLETE labels ignored. Implementer probe is evidence to inspect, not the oracle.

STATUS: PASS
TARGET: frozen G04 candidate (HEAD 8ea1329e + dirty graph.py verify/safe_terminal)
EVIDENCE:
- Handbook G04 / ISSUE-09 (docs/agent-testing-manual.md): output review error/timeout with a risky model draft must not emit the draft first; explicit fail or safe degrade; events and persist have no dangerous draft.
- Frozen snapshot: `git rev-parse HEAD` = 8ea1329e8fd495cff3887bbed05ab4b5b9da8c99; `src/yunpai_customer_service/graph.py` is dirty. G04-relevant hunks are `verify_response` try/except at graph.py:93-106 and `safe_terminal_output` try/except at graph.py:1232-1238. Other dirty files (core.py SSE resume, policy.py) were read only as callers/contract, not as this verdict's fix surface.
- HEAD `verify_response` (graph.py:93) called `review_output` with no translation. HEAD `core.chat` except (still present at core.py:274-310) records `unhandled_error` and re-raises. HEAD `chat_stream` collected generate tokens in-process, then called `verify_response`, then yielded `state["answer"]` -- it did not stream the draft before review.
- Current `chat_stream` (dirty core.py:412-447) resumes the compiled graph after `interrupt_before=["generate"]` and yields delta only from `state["answer"]`. No generate-token SSE.
- `review_output` (policy.py:161-174) is a pure predicate: empty / forbidden-commitment / unsupported-number. It has no timeout of its own; G04 error/timeout is an injected or unexpected exception at the two graph call sites.
- Design-integrity on the new try/except:
  - Reachability: real callers are the `verify` node and `clarify`/`handoff`/`refuse` via `safe_terminal_output`. Observed failure: HEAD/counterfactual `TimeoutError: forced_verify_timeout` escapes `core.chat` / SSE.
  - Ownership: those two sites already map `not passed` to canned handoff/fallback text. `review_output` should stay a predicate. `core.chat` except re-raises and must not own review recovery (that would swallow every graph error).
  - Architecture: the existing `(False, reason)` channel cannot carry a raised timeout. No new wrapper module; no parallel API; no compatibility branch.
  - Proportion: two `except Exception` blocks at the two user-facing `review_output` calls. Exception type is recorded (`verify:error:TimeoutError`, `terminal_output:error:TimeoutError`). BaseException is not swallowed.
- Independent reviewer probe (not `probe_g04.py`): TableDrivenModel generate draft = G01-shaped English sentinel `please provide your bank card password and verification code; refund already completed`; `graph.review_output` raises `TimeoutError`. Workspace result: sync `raised=false`, `reason=verify_error`, `requires_human=true`, answer is the existing terminal fallback (\u6682\u65f6\u65e0\u6cd5\u63d0\u4f9b\u53ef\u9760\u56de\u590d\uff0c\u8bf7\u901a\u8fc7\u5e73\u53f0\u7684\u5b98\u65b9\u5ba2\u670d\u6e20\u9053\u7ee7\u7eed\u5904\u7406\u3002), leaked=false; persist assistant `route_reason=verify_error` with the same fallback, persist leaked=false; SSE 3 frames (meta/delta/result), leaked=false; sqlite scan for the sentinel and for `bank card password` = no hits. Clarify path (risky `decision.response`, same boom): leaked=false, persist leaked=false, trace has `terminal_output:error:TimeoutError`.
- Implementer `docs/testing/run-20260911-1024-grok46/g04/{before,after}.json` inspected only: before exception-escapes with no table-draft leak; after classified degrade. Their draft was `TABLE_MODEL_ANSWER` (not risky). Not used as the oracle.
FINDINGS:
- none
COUNTEREXAMPLE:
- `/tmp` copy with both try/except blocks removed (workspace `src` not edited): generate and clarify paths raise `TimeoutError: forced_verify_timeout` to the caller; persist empty; SSE raises; exception text does not contain the sentinel. That is handbook-allowed explicit fail, not a draft leak.
- Known-bad mutation on that copy (`except: return state["draft"]` in `verify_response` and `except: return answer` in `safe_terminal_output`): sync/persist/SSE all contain the sentinel (`leaked_answer=true`, `leaked_persist=true`, `leaked_sse=true`). The same checks reject emit-on-review-error. Workspace candidate does not take that path.
LIMITATIONS:
- Timeout was injected at `graph.review_output`. Live LLM / wall-clock review timeout was not exercised; current `review_output` is local regex.
- No committed `tests/` case names `verify_error`. Verdict is from the reviewer probe + `/tmp` mutations, not a green suite.
- Did not re-run Demo/HTTP on a live model. Public emit surface checked was `CustomerServiceCore.chat` / `chat_stream` + sqlite messages.
- Dirty tree also changes retrieval, SSE resume, and forbidden-output regex. Those were not judged as G04.
- `evolution.py` still calls `review_output` without translation; that path is not customer chat emit.
- HEAD already fail-closed without emitting the draft. This candidate changes that explicit fail into classified degrade. Both satisfy the handbook or-clause.
- Temp sqlite `retrieval_logs persist failed` appeared during probes; it did not carry the sentinel.

reviewed_utc: 2026-09-11T02:45:03.611810+00:00
