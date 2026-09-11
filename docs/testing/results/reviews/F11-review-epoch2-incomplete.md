# F11 independent review

Reviewer: detached Cursor Grok 4.6 (fresh epoch, no resume of d67d6978 / aee7ee28 / 3a096236). Did not use Luna. Product code, tests, git, and CASES.json were not edited.

STATUS: INCOMPLETE
TARGET: frozen F11 candidate evolution.py sha256 9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf
EVIDENCE:
- Handbook F11 (`docs/agent-testing-manual.md`): after evaluate, change candidate text, source, knowledge version, or approval scope, then approve. Pass only if evaluate binds concrete candidate content and dependency versions; a change requires re-eval; old `gate_passed` must not publish new content.
- Reviewer contract (handbook, not implementer labels): after evaluate passes, changing candidate text/source/scope must not approve/publish on the old `gate_passed`.
- Implementer `docs/testing/results/defects/F11-mutate-after-eval/after.json` and `how-fixed.md` are labeled PASS. Inspected only; not accepted.
- Freeze check at review start: `src/yunpai_customer_service/evolution.py` UTF-8 sha256 `9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf` (match).
- Independent in-process probes ran only while that hash was still current:
  - `/tmp/f11-review-20260911-epoch2/probe_f11.py` and `probe_f11_clean.py`
  - `DATA_DIR` under `/tmp/f11-review-20260911-epoch2/`
  - TableDrivenModel + `LEARNED_QUESTION` / `LEARNED_ANSWER` from `tests/test_customer_service_module_knowledge.py`
  - Both probe scripts recorded `hash_start` = `hash_end` = `9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf`
- After those probes, before this review file was written, the workspace file moved. Re-hash of `evolution.py` UTF-8 text: `7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310`. Required freeze no longer present.
- This review does not inspect, import, or probe the later tree.
FINDINGS:
- [P1] `src/yunpai_customer_service/evolution.py` — candidate not frozen for this epoch. Required sha256 `9d260930c185cd61a4ebca3fb0d1925bbe499a8f3540f3ad32cf9bd2badef5bf` was present at start and through the reviewer probes, then the dirty file changed to `7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310` before the verdict was written. Acceptance and structural gates require one snapshot; this review does not chase the later file.
COUNTEREXAMPLE:
- Not scored. The known-bad implementation that must be rejected is `approve()` checking only `status==evaluated` and `gate_passed==1` after candidate text/source/scope change. A verdict on that counterexample requires the frozen `9d260930` bytes to still be the workspace file at write time.
- Historical `before.json` (pre-bind HEAD): SQL-mutate `proposed_answer` to `MUTATED-AFTER-EVALUATE microwave allowed 99999 units`, approve published the mutated text, `leaked_mutated=true`. That is not after-fix evidence for the current dirty tree.
LIMITATIONS:
- Workspace `evolution.py` moved after the reviewer probes and before this write. Probe outputs under `/tmp/f11-review-20260911-epoch2/` are not a verdict on the file now on disk.
- Implementer `after.json` PASS ignored.
- No live HTTP/UI. Not required for this L1 service-gate case.
- Prior `F11-review.md` INCOMPLETE verdict was not copied.
