# Independent review: Skill sha256 d386bbb1 (skill-fix-final)

```text
STATUS: PASS
TARGET: Skill /Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md sha256 d386bbb116937d74caa241229210e26e6c935f19a8c18cf382c164fbda275213; not product HEAD 8ea1329e + dirty digest 340f188d
EVIDENCE:
- Measured Skill sha matches claimed d386bbb1; Documents and .codex copies share inode 180607586; SKILL.after.md is byte-identical
- Product followup verdict NO_GO; freeze.json 801e8ae1 then freeze-after-k04.json 340f188d
- K04 live red [200,500], TestClient after.json [200,200], live restart PID 37044 [200,200]; independent slice review PASS, handbook K04 INCOMPLETE
- L04 clicks done with db_after_rollback.candidate_status=approved; cost.json amount=null
- Old check_skill.py still PASSes dummy needles and FAILs the portable Skill (inverted oracle, not Skill GO)
FINDINGS:
- [P3] SKILL.md:191 — leftover optional Claude playbook URL with a do-not-copy fence; does not recreate the deleted this-repo appendix
COUNTEREXAMPLE:
- Dummy needles file + check_skill.py => PASS with no agent action. Mixed-digest current PASS, factor-matrix-as-K05, TestClient-as-live-K04, screenshot-as-L04, and Skill-edit-as-product-GO are rejected by the new rules.
LIMITATIONS:
- Artifact mapping, not a 161-row replay or live restart
- Future agent compliance is not proven
- Product 10.2 remains NO_GO
```

Reviewer: Cursor Grok 4.6 Extra High Fast, fresh context, no resume of the Skill-revision implementer thread, no Orca/Luna, no Task subagents. Skill, product code, `CASES.json`, `INDEX.json`, `README.md`, and historical evidence were not edited. Implementer `green.json` was inspected and is not the oracle. Keyword/substring presence is not a pass condition.

## Separate verdicts

| Target | Verdict | Why |
|---|---|---|
| Skill as a cross-project reusable skill | **PASS** | The twelve observed wrong actions from the completed product cycle are no longer compliant bookings if this text is followed. The this-repo appendix is gone. Skill eval now requires a behavioral counterexample or independent review. |
| Product release (handbook 10.2) | **NO_GO / INCOMPLETE** | Unchanged. P0/P1 not all PASS on digest `340f188d`. L4/L5 absent. Cost unknown. This Skill sha is not a product change. |
| Unique ledger | **not updated** | `CASES.json` still records `skill_sha256` `89ae938a`. Receipt-before-ledger held. This review does not write the ledger. |

Skill reusable PASS is **not** product GO.

## What was opened

Frozen Skill:

- `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md` (hashed)
- `references/operational-templates.md` (blank schemas, not vendor pins)
- `agents/openai.yaml` (Codex packaging only; not loaded by the Skill body)

Real-cycle evidence (read, not rewritten):

- `docs/testing/run-20260911-acceptance-handoff/skill-fix-final/{red,green,how-failed,how-fixed}.json`, `diff-summary.md`, `SKILL.diff`
- `docs/testing/run-20260911-product-followup/{verdict.md,cases-this-run.json,freeze.json,freeze-after-k04.json,cost.json}`
- `docs/testing/run-20260911-product-followup/defects/K04-concurrent-500/{before.json,after.json,how-fixed.md,review.md}`
- `docs/testing/run-20260911-product-followup/live/{live-results.json,k04-after-restart.json,l04-browser.json,c01-rejudge.json}`
- `docs/testing/run-20260911-product-followup/{k05/factor-matrix.json,k11/cases.json,k06/cases.json}`
- `docs/testing/results/reviews/skill-acceptance-handoff-review.md` and `.json`

Not treated as oracle: implementer `green.json`, `how-fixed.json`, `check_skill.py`.

Not re-run: `probe_green.py` (would overwrite frozen `after.json`), live uvicorn, full handbook.

## Behavioral walkthrough

Each item is: given the named artifacts, if an agent followed **only** the frozen Skill, could they still take the previously observed wrong action?

### 1. Candidate digest drift — blocked

Handoff mixed stage-0 `0016c55d` with later `api.py` `e268c2b3` and left C01/G07/L01 live on the old process. Followup froze `801e8ae1`, then `graph.py` moved and `freeze-after-k04.json` recorded `340f188d`.

Old Skill froze once. New Skill requires a new freeze at each phase and after every product-source/build drift, and forbids upgrading unre-run mixed-digest claims to current `PASS`. Product digest, Skill sha, and review sha are separate identities, so this Skill edit cannot masquerade as the K04 `graph.py` move.

### 2. Handbook row vs factor/slice — blocked

`k05/factor-matrix.json` is `summary.status=PASS` with `handbook_claim=false`. `k11/cases.json` is HTTP schema L1 (422/200), notes “not L4”. `k06/cases.json` is `L1-framework` with `l4_business_ledger=false`. `c01-rejudge.json` PASSes a color follow-up and says object-correction was not run. `l04-browser.json` is a click path with `handbook_claim=false`.

New Skill: a catalog row closes only when every required factor, entry, and layer exists on the **current** digest. Narrower results stay named slices. Framework/HTTP schema is not a business ledger. Followup already booked K05/C01/I08/K01-sse/L04 as INCOMPLETE and K06/K11 as layered slices; the Skill now requires that booking.

### 3. Historical REVIEW_PASS vs current rejudgment — blocked

Scenario S1: keep C01 `REVIEW_PASS` on a drifted digest. The deleted appendix forbade reverting `REVIEW_PASS` to FAIL. New Skill keeps historical originals and allows current `FAIL` or `INCOMPLETE`. Followup kept historical files and booked current C01 INCOMPLETE.

### 4. Fresh-context review and ledger timing — executable

K04 `review.md` is a detached read-only review of original red, TestClient green, live-after-restart, and post-fix digest. New Skill makes those properties mandatory and puts launch method in project rules or the run manifest, not a host Task API. Review receipt must land before unique-ledger update. This reviewer observed `CASES.json` still on Skill `89ae938a`, which matches that order.

Resuming the implementer thread would not count, even if a launcher phrase were present.

### 5. TestClient green, live restart, UI vs API/DB — layered

K04 live `live-results.json` concurrent `[200, 500]`; TestClient `before.json` `[200, 500]`; TestClient `after.json` `[200, 200]` `msg-dc12bfef…`; live `k04-after-restart.json` PID `37044` `[200, 200]` `msg-83d41506…`. Those greens are different transports and ids. Independent K04 review PASSed the concurrent slice only; crash-recovery and at-most-once stayed INCOMPLETE.

New Skill: in-process green does not close a live defect; restart/reload the isolated live process; detached review of red, live green, and post-fix digest; unclaimed parent parts stay INCOMPLETE. `success.png` is auxiliary.

L04: clicks completed, screenshots exist, `candidate_status` remained `approved`. New Skill: after approve/rollback, page, API, and database must agree; prior-status display is not `PASS`.

### 6. L1–L5, demo vs production, BLOCKED / INCOMPLETE / NO_GO, unknown cost, safety stop — clear

L4 and L5 are split. Local demo/workbench is not production ingress. Framework/registry/HTTP schema is not a business ledger. L1 or local L3 cannot be written as L4/L5. Followup I08/K06/K11/L4–L5 bookings match that split.

Statuses: `PASS` needs full assertions/post-state/layer/evidence; `FAIL` is reachable product breach; `BLOCKED` is missing environment/credentials and must not guess secrets or write production; `INCOMPLETE` includes named slices and unknown cost when a cost gate is in force; incomplete 10.2 is `NO_GO` / `NO_GO`.

`cost.json`: `amount=null`, `currency=unknown`, 14 model calls. Unknown cannot pass a cost gate and must not be invented.

Safety stops (credential exposure, production writes, unauthorized deploy, isolation break, data integrity) outrank a continue instruction. The old no-wait override is gone.

### 7. Isolation, credentials, executor, screenshots/browser — no this-repo hard pins in the Skill body

The deleted appendix pinned `source env.md`, `DATA_DIR`, Cursor Grok / Orca / Codex / Luna, Task/`run_in_background`, unicode-escape writes, `file://` workarounds, and `CASES.json` freeze wording. Those strings are absent from the current Skill body and from `operational-templates.md`. Followup already recorded executor and isolation in `freeze.json`, which is where the new Skill says they belong.

A valid UTF-8 review is therefore not a Skill miss. Recorded capture-tool substitution is an execution deviation, judged by independence.

### 8. Skill self-eval — behavioral, not a keyword checker

New Skill: validity is a behavioral counterexample or independent review; substring checkers are auxiliary and cannot be Skill `GO`. Known-bad implementation: paste the required phrases into a file.

This reviewer recomputed that `false-green-skill-needles.txt` still satisfies `check_skill.py`, while the portable Skill fails that checker because the harmful pins were removed. Treating that FAIL as Skill FAIL, or the dummy PASS as Skill GO, would invert the contract. This file is the independent review; the inverted checker result is not GO.

### 9. This revision is not product GO

Opening sentence, freeze identities, and section 7 all separate Skill revision from product release. Product followup ran on Skill `89ae938a` with `skill_edits=false` and remains **NO_GO**. This sha `d386bbb1` does not change digest `340f188d` and does not close handbook 10.2.

## Confirmed findings

None that reopen Skill FAIL.

One residual P3: the optional Claude playbook URL under ????, already fenced with “?????????”. It does not restore the deleted appendix and does not recreate S2.

## Remaining limits on reusable PASS

1. This PASS is for Skill sha `d386bbb1` against the completed handoff + followup counterexamples. It is not a new product cycle under the new Skill.
2. The 161-row handbook was not re-executed. Live processes were not restarted. K04 probes were not re-run.
3. Text-plus-artifact review can show the wrong actions are no longer compliant; it cannot guarantee a later agent will follow the text.
4. Re-freeze is mandatory after product-source/build drift. Prompt/config/embedding changes are freeze facts but are not named in that trigger sentence. The observed failures were `api.py` / `graph.py`.
5. Product 10.2, L4/L5, handbook K04/K05/C01/L04, unknown cost, and dirty digest `340f188d` still make **product NO_GO**.

Coordinator may later record this Skill sha in the unique ledger. This reviewer did not.
