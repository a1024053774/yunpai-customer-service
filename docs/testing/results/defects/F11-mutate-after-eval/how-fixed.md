# F11 怎么修的

evaluate 通过后直接改 `proposed_answer`，approve 仍发布变造文本（含 99999）。

## 根因

`approve` 只看 `status=evaluated` 与 `gate_passed=1`，不绑定评测时的问题/答案/来源。

## 修复

evaluate 把内容指纹写入 `gate_report.bound_content`；approve 若指纹不一致则拒绝。不新增表字段。

## 同信号

- before：approve 成功且 leaked_mutated=true
- after：`EvolutionError: candidate changed after evaluation`；未发布
- pytest evolution cycle / failing-gate 仍绿

实现者自测不算验收。
独立审查：`../../reviews/F11-review.md` — **PASS**（冻结 sha256 9d260930；改文/改来源拒绝发布；/tmp 去掉 bind 后仍会发布变造文本）。
第一次审查 INCOMPLETE 保留在 `../../reviews/F11-review-1.md`。指纹未绑 tenant / 知识库版本（P3）。实现者自测不算验收。
