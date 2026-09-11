# 7.2 怎么修的

证据是 5L，回答 `warranty is 5 years` 被 `review_output` 放行（数字 5 都在场）。

## 根因

`_normalized_numbers` 只比数字，不比单位。

## 修复

在已有 `review_output` 增加数字+单位对校验。回答出现证据没有的单位对则 `numeric_unit_mismatch`。

## 同信号

- 红：`docs/testing/run-20260911-1416-grok46/l1/priority.json` 7.2 FAIL shipped 5 years
- 绿：`after.json` reason=numeric_unit_mismatch，未外发 5 years
- frozen policy.py sha256 `7d05f60604b3121d4b360f0e14e07499450f1405ae8a13b1b427bfd892628014`

实现者自测不算验收。
独立审查：`../../reviews/72-review.md` — **PASS**（5 years vs 5L 被 numeric_unit_mismatch；序号仍过）。`5 yrs` / `five years` 仍会过。实现者自测不算验收。
