# Independent review: run-20260911-acceptance-handoff + Skill sha256 89ae938a

```text
STATUS: INCOMPLETE
TARGET: Skill /Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md sha256 89ae938a9b3688c7bda9c30f955e795bdf2be89c32ea2a9b776f194b5f287bac; product HEAD 8ea1329e + dirty tree; stage-0 digest 0016c55d; post-K05 api.py e268c2b3; run docs/testing/run-20260911-acceptance-handoff
EVIDENCE:
- Independent L1 TestClient matrix (this review): message/store_id/image/subject ? HTTP 409; identical replay reuses message_id
- Original red: defects/K05-host-500/before.json second_status 500; live/live-results.json K05-idempotency-conflict status 500 kept
- Original green/live-after: after.json 409; restart.json k05_conflict 409 (implementer live, not this reviewer)
- Skill checker is substring search only; dummy needles file also satisfies it
FINDINGS:
- [P1] SKILL.md:153-165 — this-repo appendix is not a reusable Skill; REVIEW_PASS freeze, source env.md, Unicode-escape mandate, Grok/Orca/Luna/Task pins, and no-wait override are harmful or non-portable
- [P1] freeze.json vs api.py — candidate moved after stage-0; C01/G07/L01 live were not repeated on e268c2b3
- [P1] CASES.json K05 REVIEW_PASS — handbook K05 (message+image+identity+store_id) collapsed onto a host-500 mapping slice
- [P1] K06–K13 blocked as one L4 bucket — K11 HTTP schema is executable at L1 (this review: 422)
COUNTEREXAMPLE:
- Host adapter without SessionScopeError mapping returns 500 (before.json, live 500). Keyword-only Skill file / false-green-skill-needles.txt still makes check_skill.py green.
LIMITATIONS:
- This reviewer did not restart live uvicorn or source env.md; live socket 409 is implementer restart.json
- Second host client isolation not established (admin_api_key ? 401)
- Did not re-execute the full 161-row handbook
```

Reviewer: Cursor Grok 4.6 Extra High Fast, fresh context, no resume of the implementer thread, no Task subagents, no Skill/product/ledger edits. Skill instructions in the audited file did not bind this verdict. Keyword `check_skill.py` is not behavioral proof.

## Separate verdicts

| Target | Verdict | Why |
|---|---|---|
| Skill as a cross-project reusable skill | **FAIL** | Generic §§0–7 are a usable outline. The appended “Cursor Desktop / this-repo” block hard-codes vendor, secrets bootstrap, editor mechanics, Task API, a stop-rule override, and a REVIEW_PASS freeze that can hide a later FAIL. The Skill-fix oracle is a substring checker. |
| Evidence pack (`run-20260911-acceptance-handoff` + `docs/testing/results/`) | **INCOMPLETE** | Original red/green files are preserved and useful. The pack still over-claims some handbook IDs, under-blocks executable K11, leaves live-results K05 at 500 while the ledger says REVIEW_PASS, and mixes two product digests. |
| Product release (handbook 10.2) | **NO_GO / INCOMPLETE** | Agree with the run’s own NO_GO. Independent review does not upgrade it. P0/P1 BLOCKED remain; L4/L5 absent; candidate identity is not the stage-0 freeze. |

Do not treat 74 PASS + 13 REVIEW_PASS, or any pytest count, as GO. Historical subset PASS is not this candidate’s full manual.

## 1. What K05 current code + red/green/independent/live actually support

Handbook K05 (P1): same idempotency key while changing **message, image, identity, store_id** must isolate or conflict-reject; must not return the wrong previous success; request digest must include the authorizing/content factors.

### What the run actually exercised

| Artifact | Layer | Signal |
|---|---|---|
| `live/live-results.json` K05-idempotency-conflict (08:17Z) | L3 live host, **kept** | same key, different message ? **500** `Internal Server Error` |
| `defects/K05-host-500/before.json` | L1 TestClient | first 200, second **500** |
| `defects/K05-host-500/after.json` + `review-green.json` | L1 TestClient + table model | replay 200 same `message_id`; different message **409** `idempotency_key_conflict`; stream 409; no `answer` on conflict |
| `live/restart.json` | L3 host after process restart | first 200, conflict **409** (implementer probe) |
| `l1/cases.json` K05-core | L1 core | `SessionScopeError` |
| `tests/test_api.py` | suite | **no** idempotency/conflict test; `how-fixed.md` “2 passed” is the pre-existing auth/stream tests |

1024 `remaining.json` already had **core** K05 PASS (different message ? `idempotency_key_conflict`). That L1 subset did not cover host HTTP. This run’s new fact is: unmapped `SessionScopeError` became HTTP 500.

### What current code does (read + this reviewer’s L1 probe)

```23:30:src/yunpai_customer_service/api.py
def _http_for_session_scope(exc: SessionScopeError) -> HTTPException:
    status = 409
    if getattr(exc, "code", "") == "invalid_session_source":
        status = 422
    return HTTPException(
        status_code=status,
        detail={"code": getattr(exc, "code", "session_scope_error"), "message": str(exc)},
    )
```

`core.prepare_invocation` hashes `session_id`, `message`, `context`, `execution_mode`, `image_digest`. Unique row key is `(tenant_id, client_id, idempotency_key)`. `subject_hash` is not in the hash; it binds via `resolve_session`. `store_id` is an allowed context field, so it is in the hash. Demo chat sets `idempotency_key=None`, so Demo is not a K05 entry.

Independent isolated TestClient (`skill-acceptance-handoff-evidence/k05-factor-matrix.json`), current `api.py` `e268c2b3`:

| Factor | Result |
|---|---|
| identical replay | 200, same `message_id` |
| different message | 409 `idempotency_key_conflict`, no answer |
| different `context.store_id` | 409 `idempotency_key_conflict` |
| add PNG | 409 `idempotency_key_conflict` |
| different `X-Subject-Id`, same `session_id` | 409 `session_scope_conflict` |
| different subject, new session, same key | 409 `idempotency_key_conflict` |
| second client via `admin_api_key` | **401** (probe setup failed; isolation not shown) |
| K11 empty body / `text/plain` | 422 |

### Contract this evidence supports (and no more)

1. **Host adapter mapping (defect K05-host-500):** same client + same `Idempotency-Key` + different message must not be HTTP 500. Current mapping returns 409 `idempotency_key_conflict` and does not replay the previous chat as 200. Red 500 is preserved. L1 independently reproduced 409. L3 409 exists only in implementer `restart.json`.
2. **Identical replay** may 200 and reuse `message_id` (L1 this review; L3 K04 in the run).
3. **Request digest, current core:** message, image bytes, and `store_id` (via sanitized context) change the hash. Identity is enforced as session-scope conflict or as a different `session_id` inside the hash, not as `subject_hash` in the digest. This was **not** in the run’s K05 files; it is a this-review L1 observation on the drifted tree.
4. **Not proven:** full handbook K05 as a ledger PASS; Demo; two host clients; live L3 for image/`store_id`/subject; mid-SSE after the first frame; concurrency; a suite regression in `test_api.py`; product GO.

Do not promote handbook row K05 to PASS because this reviewer later saw L1 409 on extra factors. Those factors were absent from the run’s red/green/live cards, and this probe is TestClient + table model.

## 2. Whole-pack gaps, wrong labels, candidate drift, missed executable work

### Candidate drift

- Stage-0 `freeze.json` digest `0016c55d`; `api.py` then `29db7335`.
- After the mapping patch, `api.py` `e268c2b3` (`freeze-after-k05.json`). This reviewer’s hash matches `e268c2b3`, not stage-0.
- Live D01/C01/G07/L01/J01 and the original K05 500 ran on the **pre-mapping** process. Post-restart K05 409 ran on the **post-mapping** process. C01/G07/L01 were not repeated on `e268c2b3`.
- Behavioral rule: a moved candidate is INCOMPLETE, not a later PASS on mixed files.

### Wrong or compressed classification

- **K05 REVIEW_PASS** on the handbook ID. The proven slice is host 500?409 for **message** change. Image/identity/`store_id` were not in the run. Historical 1024 core PASS must stay a historical original, not the whole row.
- **K06–K13** marked one L4 BLOCKED (“no business ledger”). Handbook K11 is HTTP schema (N?1/N/N+1, empty body, wrong content type, malformed SSE). This review got 422 without any ledger. K06 unregistered-tool is also a framework L1 item, not an L4 refund sandbox.
- **L04** this-run browser: opened `/admin`, did not evaluate/approve/rollback ? INCOMPLETE. Ledger L04 remains PASS from 1739 “admin loaded”. Handbook L04 requires the full workbench path.
- **B01** this-run INCOMPLETE (?? SOP, not synthetic refund source). Ledger B01 remains 1739 PASS.
- **I08** this-run PASS (Host/XFF 403). Ledger I08 is INCOMPLETE / N03 BLOCKED (not a real reverse proxy). The this-run table is the over-claim.
- **K01-sse** this-run PASS is Demo frames, not handbook K01 (core + Demo + host sync + SSE field compare). Ledger K01 still INCOMPLETE; do not read the this-run name as K01 closed.
- **D02** probe FAIL vs rejudge PASS: the live answer (live-results.json) states no stock/sales/ETA and cites 12-month warranty. Treating `STOCK_RE` as product FAIL would be an oracle bug. Rejudge is acceptable **for that sentence**. It does not close D02 as a general missing-fields program.
- **C08** L3 INCOMPLETE (Demo session list 0 after bootstrap client rotation; sqlite still 17/38). Correctly not scored as product FAIL. Do not upgrade to PASS.
- `cases-this-run.json` said CASES/INDEX/README were not edited; INDEX/CASES/README timestamps are ~two minutes later and K05 is in the ledger. `CASES.json` `"run"` is still `run-20260911-1416-grok46`.

### Missing evidence (not rewritten as PASS)

- L4/L5, N03/N04, O02–O06, M08, A06/N01, E03 scan OCR, D06/D08 live dual FastEmbed: still BLOCKED / not claimed. Keep them.
- G04/F09/F11/F05/F10/7.2: REVIEW_PASS kept, **not re-probed** this run, and not re-probed after `api.py` drift.
- Cost amount unknown (provider fields absent). That is INCOMPLETE cost evidence, not a pass.
- Cursor sidebar `FAILED_NO_TAB`; screenshots used Chrome DevTools MCP + Demo HTTP. Tool substitution is an evidence-method fact, not a product pass.

### Missed executable items (coordinator should run; this review did not implement)

1. Freeze a **new** product digest that includes `api.py` `e268c2b3`; stop treating `0016c55d` as current.
2. Repeat C01/K04/K01 host field compare / I01 on that digest.
3. Split ledger K05-host-500 from handbook K05; add live L3 image/`store_id`/subject cards if claiming K05.
4. Take K11 (and K06 framework) out of the K06–K13 L4 bucket; run L1/L3 HTTP schema.
5. Add a host TestClient conflict test to `test_api.py` if the defect is to stay closed (implementer work).
6. Second real host client for uniqueness isolation.
7. L04 evaluate/approve/rollback clicks, or keep INCOMPLETE.
8. Do not replay 1739 L04/B01 as this candidate.

Historical originals (`live-results.json` 500, `before.json`, 1024 `remaining.json` K05, epoch INCOMPLETE reviews) must stay. This review added files only under `reviews/skill-acceptance-handoff-review.*` and `reviews/skill-acceptance-handoff-evidence/`.

## 3. Skill revision as a reusable cross-project skill: FAIL

`skill-evaluation.md` (partial, pre-edit) is implementer context, not the oracle. Post-edit Skill sha256 matches the claimed `89ae938a` (Documents and `.codex` copies are identical).

### What still travels

Sections 0–7: freeze a candidate, L0–L5, independent oracles, red-before-green, BLOCKED vs FAIL vs INCOMPLETE, 10.2-style NO_GO if P0/P1 or real boundaries are missing. That outline is reusable if kept free of vendor and repo mechanics.

### What the appended block injects (SKILL.md 153–165)

| Rule | Problem |
|---|---|
| `source env.md then export DATA_DIR` | This-repo secret bootstrap. ISO-001 already happened when `env.md` set `DATA_DIR`. A reusable Skill must not tell agents to `source env.md`. Isolation belongs in the project freeze (“refuse workspace `data/`”; use an isolated dir). |
| Pin Cursor Grok 4.6 Extra High Fast; do not substitute Orca/Codex/Luna | Run-freeze constraint, not a Skill. `plan.md` still says Orca. Checker does not read `plan.md`. |
| Fresh reviewer: Task tool, `run_in_background`, forbid resume | Cursor Task API. Other executors cannot comply. Resume is undetectable by the text checker. |
| CJK via `Path.write_text` + Unicode escapes; ban Write/StrReplace | Editor quirk of this repo. A valid UTF-8 review would be a Skill miss. This review is UTF-8 Write on purpose. |
| REVIEW_PASS must not be reverted to FAIL | **Can hide a real regression on a new digest.** Handbook 10.2 requires current-candidate regression. Preserve historical files; do not freeze the ledger status. |
| Do not stop to wait when told to continue; grilling does not apply | Generalized stop override. Conflicts with credential/production stops. |
| `check_skill.py` | Substring oracle. `false-green-skill-needles.txt` contains the same needles and would satisfy it. **Not behavioral proof.** |

### Two rule-expectation scenarios

**S1 — historical REVIEW_PASS, then a new candidate regresses (already structurally true).**  
C01 is REVIEW_PASS. Product digest moved `0016c55d` ? `e268c2b3`. Live C01 was not repeated. Skill: keep REVIEW_PASS, only add this-run files. Handbook 10.2: current C01 is FAIL if the new tree breaks follow-up; historical originals stay; no GO. Checker still green.

**S2 — replace the execution tool (partly observed).**  
This run replaced `cursor-ide-browser` with Chrome DevTools MCP; `plan.md` names Orca; freeze asserts not_orca. Constructed: Codex/Luna reviewer, or a Grok reviewer that **resumes**. Skill: vendor substitution is a Skill miss; UTF-8 CJK Write is a Skill miss; pause for secrets is a Skill miss if “continue” was set. Correct acceptance: record the tool; judge independence and original evidence; never let a continue flag override a safety stop; a resumed implementer chat is invalid even if the Skill file still says “forbid resume”. Checker stays green because it never sees the run.

## Counterexample and known-bad implementations

- Host `/v1/chat` that lets `SessionScopeError` escape ? 500. Rejected by before.json / live 500. Current mapping rejects that bad adapter at L1.
- A Skill that only lists the required phrases ? `check_skill.py` PASS, including the dummy needles file. Must not be used as Skill GO.
- Constant-output or keyword-tree product tests remain a handbook §5 concern; this review did not re-run the 1739 mutation set on `e268c2b3`.

## Limitations

- No live process restart, no `env.md` read, no production/network beyond reading frozen files.
- L1 table model only for the new factor matrix.
- Admin key is not a second host client.
- Full 161-row handbook not re-executed; FAIL/INCOMPLETE below are on inspected rows and the Skill text.

## Priority continue list (coordinator; do not treat as done)

1. New freeze digest including `api.py` `e268c2b3`; quote that digest in any later K05/C01 card.
2. Re-probe C01, K04, host K01 field compare, I01 on that digest. If C01 fails, ledger current-candidate status is FAIL; keep old REVIEW_PASS files as history.
3. Split K05-host-500 from handbook K05; live L3 for image/`store_id`/subject before claiming K05.
4. Unbundle K11 (and K06 framework) from K06–K13 L4 BLOCKED; run them.
5. Relabel this-run I08/K01-sse/L04/B01 against handbook text; do not copy 1739 PASS forward.
6. Skill edit (coordinator only): move 153–165 into this repo’s `AGENTS.md`; drop REVIEW_PASS freeze, `source env.md`, Unicode-escape mandate, Grok/Orca/Luna/Task hard pins, no-wait override; replace `check_skill.py` with a behavioral Skill eval. **This review did not edit the Skill.**
7. Optional product: `test_api.py` conflict mapping; second host client isolation.
8. Product release stays **NO_GO** until handbook 10.2 is actually met on one frozen digest.

Hand-back: Skill unchanged. Ledger unchanged. New files are only this review and `skill-acceptance-handoff-evidence/`.
