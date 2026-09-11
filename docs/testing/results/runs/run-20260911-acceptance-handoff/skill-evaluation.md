# Skill 评估：agent-acceptance-testing

- run: `run-20260911-acceptance-handoff`
- skill: `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md`
- skill_sha256_at_eval: `6ec9c4f5aa274d8ec4791b55d4ce6ce0bd8a29ed06e7ea4ea4724d3593751427`
- evaluator: Cursor Grok 4.6 Extra High Fast（本轮禁止 Orca / Codex / Luna）
- 评估时间: 阶段 0 基线已落盘、产品 10.2 执行前
- 结论: **部分有效，存在可执行缺口**。本文件写完前 **未修订 Skill**。

## 本轮真实执行中 Skill 约束了什么

| 约束点 | 是否生效 | 本 run 证据 |
|---|---|---|
| 候选冻结（HEAD + dirty） | 是 | `freeze.json` `head=8ea1329e` + `dirty_diff_sha256=c0ea53fa...`；HEAD 单独不能标识候选 |
| 独立 oracle | 部分 | Skill 要求业务真值不能由被测实现生成；手册 4.2 / 7.4 nonce 资料可执行 |
| 先红后绿 | 是（文本层） | 第 5 节有完整顺序；与 evidence-first-testing 一致 |
| 反事实 | 部分 | 第 3 节变异表 + 第 5 节「修复已先发生则恢复」；缺乏操作化回退步骤 |
| fresh-context verifier | 弱 | 第 4 节只写「一个 fresh-context、只读 verifier」，未规定 Task / model / 禁止 resume / background |
| L0-L5 | 是 | 第 1 节五层表；禁止 L1 冒充 L4 |
| BLOCKED/INCOMPLETE | 是 | 第 7 节状态集；缺账号不得改 PASS |
| 截图 | 部分 | 要求截图不能单独升级为验收；**未禁 file://**、未要求临时 localhost HTTP |
| 成本 | 部分 | live trial schema 有 total_cost；未强制本 run `cost.json` |
| 清理 | 部分 | 轨道回执要求清理；未绑 ISO-001 / 隔离 DATA_DIR 顺序 |
| 账本一致 | 部分 | 要求唯一事实源；**未禁止阶段 0 直接改 CASES.json**，也未冻结 REVIEW_PASS 不得改回 FAIL |

## 缺口（本 run 已观测，评估前未改 Skill）

1. **执行体/模型针**：Skill 不禁止 Orca/Codex/Luna。本 run 预置 `plan.md` 写「Orca 中当前 Cursor Agent CLI」，与用户硬约束冲突。
2. **ISO-001**：`env.md` 含 `DATA_DIR`。Skill 未要求「source env.md 再 export DATA_DIR 到 /tmp」，也未要求启动拒绝仓库 `data/`。历史 0131 已发生 clobber。
3. **fresh reviewer 操作化**：未写明 Cursor Task、`cursor-grok-4.6-xhigh-fast`、禁止 resume、`run_in_background`、只读候选+原始证据、不读实现者摘要、不自我批准。
4. **CJK 文档落盘**：本仓库要求 Python `Path.write_text` + `\uXXXX`；Skill 未记。
5. **截图 file://**：Cursor 侧边浏览器常拦 `file://`；Skill 未要求临时 localhost HTTP 并关闭。
6. **REVIEW_PASS 冻结**：账本 C01/G07/L01/D07/D02/G04/F09/F11/F05/F10/7.2 已 REVIEW_PASS；Skill 未禁止改回 FAIL。
7. **Skill 与产品候选分开冻结**：操作模板有 product digest，没有 skill_sha256 与产品 digest 分离字段。
8. **不得停下来等用户**：用户本轮禁止等待；grilling skill 要求等用户回答。Acceptance skill 未解决与 grilling 的冲突。
9. **账本写入时机**：Skill 第 7 节说阶段文档应进唯一事实源，容易误导致跑次中途改 `CASES.json`。
10. **109 pytest 禁令**：Skill 写了绿色单测不能单独代表产品通过，但未明确「没有完整 10.2 就 NO_GO / INCOMPLETE」。

## 对 10.2 放行的影响

Skill 足以阻止「109 passed = GO」和「缺环境写 PASS」。不足以单独保证：隔离数据目录、执行体模型、detached reviewer 真正脱离上下文、REVIEW_PASS 稳定、侧边浏览器截图可复现。

## Skill-fix 决定

评估完成后建立独立 `skill-fix` 红绿证据链，再修订 Skill。产品代码与 Skill 版本分开冻结。不因 Skill 缺口改产品行为。

## 限制

本评估基于 Skill 正文 + 本 run 阶段 0 产物 + 历史 ISO-001 / REVIEW_PASS 账本。不是产品 GO。
