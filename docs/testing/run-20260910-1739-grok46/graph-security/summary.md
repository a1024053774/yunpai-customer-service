# graph-security evidence — run-20260910-1739-grok46

Executor: Cursor Grok 4.6 (`cursor-grok-4.6`). Not Luna / gpt-5.6-luna.
Candidate: `/tmp/yunpai-test-candidate-grok46-pZG5r3` (imported module `/private/tmp/yunpai-test-candidate-grok46-pZG5r3/src/yunpai_customer_service/__init__.py`).
Python: `/Users/luckye/Documents/Code/yunpai-customer-service/.venv/bin/python`
Original repo product code: not modified.

## Counts (manual IDs + L0 factory, n=34)

| Status | Count | IDs |
|---|---|---|
| PASS | 3 | L0-API-FACTORY, A01 (L1 core), B11 (L1) |
| FAIL | 0 | — |
| INCOMPLETE | 24 | A03, A04, A05, B05, B06, B10, D06, E08, G01, G02, G03, G05, G06, I01, I02, I03, I04, I08, J03, K01, K02, 7.1, 7.2, 7.3 |
| NOT_RUN | 7 | A02, A09, G04, I05, I06, I07, I11 |
| BLOCKED | 0 | — |
| N/A | 0 | — |

Pytest on the three files: **32 passed, 0 failed, exit 0** in 45.40s. That is **not** 32 manual-case PASS. Pytest green on TestClient is **L1, not L3**.

## Pytest

```
cd /tmp/yunpai-test-candidate-grok46-pZG5r3
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.../src
python -m pytest -q --tb=short --junitxml=$EVIDENCE/pytest-junit.xml \
  tests/test_framework_audit.py tests/test_api.py tests/test_intent.py
```

Isolation: `DATA_DIR` unset; tests used pytest `tmp_path`. `ALL_PROXY=http://127.0.0.1:9` is isolation only and is **not** proof of offline.

## L0 factory (PASS)

- `create_api_app(core: CustomerServiceCore, *, auth=None)` — `core` is required (`api.py:22-26`). Calling it with no args raises `TypeError`.
- Host API does **not** default to anonymous demo auth (`api.py:28-32`). It raises if `core.settings.auth_required` is false, or if injected auth is unconfigured.
- Anonymous `anonymous-local` exists only in `AuthenticationService` when `auth_required` is false (`auth.py:74-82`, `114-120`).
- Empty `subject_hash_key` => `configured=False` (`auth.py:85-89`); probe `create_api_app` raises `ValueError: host API requires configured client authentication`.
- `prepare_demo_settings` (`demo/runtime.py:22-39`) is demo-only and is not used by `create_api_app`.

## Mapped pytest ? manual (why most are INCOMPLETE)

| Tests | Manual | Why not PASS |
|---|---|---|
| instrumented generate/verify | A01 PASS L1; K01 INCOMPLETE | Core sync+SSE only; no Demo/host field comparison; not a socket |
| lexical + mock decision | A05/B10 INCOMPLETE | Keyword override absent in mock; no model disable/disconnect; no live understanding |
| host inherit anonymous | I02 INCOMPLETE | Two disable layers + empty hash-key probe pass; Demo-as-public-entry not proven |
| encoder re-seed | D06 INCOMPLETE | Injected encoder, in-process double seed; not FastEmbed process restart |
| intent history+image | B05/B06/J03 INCOMPLETE | Wiring only; stub vision; no image B; no live referent |
| other-tenant originals | E08/I04 INCOMPLETE | List empty + 404; no digest/traversal/same-name/own-file/other object types |
| forwarded headers | I08 INCOMPLETE | Three TestClient header 403s; not reverse proxy; not all header names |
| terminal policy + missing_fields | G01-G03 INCOMPLETE; G04 NOT_RUN | Last SSE event only; no host frames; no verify timeout |
| injected model + gateway off | A04 INCOMPLETE; B11 PASS | B11 fully matched; A04 needs embedding/parser/timeout too |
| ordinals vs numbers | G05/G06 INCOMPLETE | `review_output` helper only, not chat/SSE |
| test_api TestClient | I01/K02 INCOMPLETE | Missing-header 401 + authorized stream `data:`/`persist`; not wrong/disabled keys; not every SSE frame |
| test_intent.py | B10/B11 wiring | Supports B11 PASS; B10 still needs live |

## Limitations (do not over-claim)

- No public Demo was started.
- No L3 socket/browser/reverse-proxy evidence.
- No L4/L5, HR, or live model claims.
- Mutations / graph-outside-generate counterexample (7.1 step 5) not run.
- Same-tenant shop isolation (I06) not run; cross-tenant file 404 does not substitute.
- Starlette TestClient deprecation warning only; not a product FAIL.
