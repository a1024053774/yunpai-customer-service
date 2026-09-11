# F05 怎么修的

评测对非空伪 URL `https://totally-real.example/manual-page-99` 设 `source_traceable=true` 且 `gate_passed=true`。

## 根因

1. `source_traceable = bool(normalize_text(evidence_source))`，URL 自证。
2. 本条对齐 0.1693 已独立过 0.08，只拆 bypass 不够。

## 修复

`evaluate` 里 `_source_traceable`：`http(s)://` 开头不算可追溯。自由文本仍按非空通过。未做内容/版本/范围全量核验。

## 同信号

- 红：`docs/testing/run-20260911-1416-grok46/l1/f05-full.json` gate_passed=true source_traceable=true
- 绿：`after.json` gate_passed=false source_traceable=false
- 自由文本 `manual:wool-care` 仍 gate_passed=true
- frozen evolution.py sha256 `0973a53a8453518bd4dcfc212cc97120940d1f6a5ab3aace6acbd11f4b3c1137`

实现者自测不算验收。
独立审查：`../../reviews/F05-review.md` — **PASS**（伪 https 不再自证；自由文本仍可过门）。未做页面内容/版本/范围核验。实现者自测不算验收。
