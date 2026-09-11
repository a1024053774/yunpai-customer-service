# Skill-fix-final diff summary

- skill: `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md`
- same inode: `/Users/luckye/.codex/skills/agent-acceptance-testing/SKILL.md`
- before sha256: `89ae938a9b3688c7bda9c30f955e795bdf2be89c32ea2a9b776f194b5f287bac`
- after sha256: `d386bbb116937d74caa241229210e26e6c935f19a8c18cf382c164fbda275213`
- abandoned skill-fix-2 sha (not restored, not oracle): `bd04be60031485c4c38181610f864e8655476eabfa97a13a281def361268272a`
- lines: 166 ? 191
- diff: 7 hunks, +59 / ?34 (`SKILL.diff`)

## Why this edit exists

Product acceptance continuation (`run-20260911-product-followup`) is complete and still **NO_GO**. Independent review already failed the Skill as a reusable cross-project skill. skill-fix-2 was abandoned as premature and the Skill was restored to `89ae938a`. This revision is the post-cycle Skill change only.

## What changed

1. **Identity.** Re-freeze at each phase and after every product-source drift. Record product digest, Skill sha, and review sha separately. This is the K05 `0016c55d`?`e268c2b3` and K04 `801e8ae1`?`340f188d` rule.
2. **Row vs slice.** A catalog row closes only with every required factor/entry/layer on the current digest. Host mapping, factor matrices, Demo-only SSE, header-only isolation, click paths without API/DB, and framework gates without a business ledger stay named slices. Historical `PASS`/`REVIEW_PASS` originals stay; current candidate may be `FAIL`/`INCOMPLETE`.
3. **Verifier.** New context, not implementer continuation, read-only, no product/Skill/ledger edits, no self-approve; launch method from project rules or run manifest; review receipt on disk before unique-ledger update.
4. **Live red/green.** In-process green does not close a live defect. Restart/reload the isolated live process, then detached review. Unclaimed parent-row parts stay `INCOMPLETE` (K04 concurrent 500 slice vs handbook K04).
5. **Layers / cost / safety.** L4 and L5 split; local demo ? production; framework ? ledger; unknown cost is incomplete evidence; safety stop outranks continue; page/API/DB must agree after rollback.
6. **Portability.** Removed this-repo appendix and leftover vendor/editor/bootstrap/filename pins. Isolation, credentials, executor, and capture/test tools live in project rules or the run manifest.
7. **Skill eval.** Behavioral counterexample or independent review. Substring checkers are auxiliary only. Skill revision is not product GO. Premature Skill-fix evidence is kept.

## What did not change

Product source, tests, `CASES.json`, `INDEX.json`, `README.md`, historical review originals, skill-fix/, skill-fix-2/. No commit, branch, or push.

## Remaining gate

A later independent read-only task must review Skill sha `d386bbb1` plus this pack. Until then, Skill reusable PASS is **not** claimed. Product 10.2 remains **NO_GO**.
