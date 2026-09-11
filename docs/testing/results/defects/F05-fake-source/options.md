# F05 未修

evaluate 对非空伪 URL `https://totally-real.example/manual-page-99` 设 `source_traceable=true`，且 `gate_passed=true`。错误纠正含微波/仓库口头。

## 根因

`evolution.py` `source_traceable = bool(normalize_text(evidence_source))`；`semantic_alignment` 可被 `(source_traceable and candidate_score >= 0.35)` 击穿。

## 为何不在本轮修

手册要求核验内容/版本/范围/断言。现有测试依赖自由文本 evidence_source。正确修复超出当前授权范围；不加无调用方包装。

## 最小选项

1. 要求 evidence_source 命中本租户已有知识 source，并改现有测试
2. 去掉 semantic_alignment 的 source_traceable 击穿（仍可能因相似度独立过门）
3. 实现手册级内容/版本/范围核验
