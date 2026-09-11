# 测试结果汇总

本目录对照 `docs/agent-testing-manual.md` 逐条记账。综合 Codex 161645、Grok 4.6 1739 / 0131 / 1024 / 1416 / acceptance-handoff / product-followup。不把 109 pytest 写成产品通过。逐条见 `CASES.json`。

## 放行

**NO_GO** / 不放行。手册 10.2 未满足。

当前限定交付范围与正式发布待测门禁见 [`RELEASE_SCOPE.md`](RELEASE_SCOPE.md)。这份记录保留本机内部试用版可以交付的能力，以及 C01、L04、K04 四项必须补齐的证据。

## 手册覆盖（CASES.json）

| 状态 | 条数 | 含义 |
|---|---:|---|
| PASS | 73 | 该层级适用断言通过；不等于产品放行 |
| REVIEW_PASS | 11 | 缺陷项独立审查 PASS |
| FAIL | 0 | 环境满足但产品违约 |
| INCOMPLETE | 43 | 只做了部分步骤或证据不够 |
| BLOCKED | 18 | 缺账号/资料/环境，有证据 |
| NOT_RUN | 16 | 尚未执行 |

## 2026-09-11 1416

- 新 PASS：C08 E04 I13 F08 C07 H08 E09 M02 M03 G02 K03 B07 B09 D10 H02 G08 J01 7.4
- F05 / F10 / 7.2：REVIEW_PASS
- 7.7：INCOMPLETE（挂 F05 URL 前缀；自由文本伪来源仍可过）
- F09 / F11 / G04 等 REVIEW_PASS 不改回 FAIL
- ISO-001 / L4 / L5 / HR / 8h / 干净包 / 扫描 OCR / 真实反代 / 独立站登录：不声称已过
- 109 pytest / retrieve-only 绿不是产品放行

证据根：`../run-20260911-1416-grok46/`

## 2026-09-11 acceptance-handoff

- 放行：**NO_GO / INCOMPLETE**（手册 10.2 未满）
- K05 host 500->409：REVIEW_PASS
- Cursor 侧边浏览器 FAILED_NO_TAB；改用 Chrome DevTools MCP
- Skill 评估后修订 `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/`；与产品 digest 分开冻结
- L4/L5 / HR / 8h / 干净包 / 扫描 OCR / 真反代 / 独立站登录：不声称已过

证据根：`../run-20260911-acceptance-handoff/`
## 最新接管跑次

- `run-20260911-product-followup/`：当前候选；阶段 0 digest 含 K05 `api.py`，随后 K04 使 `graph.py` 再漂移。Skill **未改**。
- K05：历史 `REVIEW_PASS` 保留；本轮 L1+L3 因子矩阵已跑，**不**升手册 K05 PASS。
- K04：并发同键同正文 500 切片独立审查 **PASS**；手册 K04 仍 INCOMPLETE（崩溃恢复 / 副作用最多一次未关）。
- 本轮明确未过：手册 K01/K05/L04、真反代、L4/L5、HR、8h、干净包、扫描 OCR、独立站登录、真实业务账本、C01 纠正对象轮。


## 独立总包审查

- `reviews/skill-acceptance-handoff-review.md`：Skill **FAIL**；证据包 **INCOMPLETE**；产品 **NO_GO**。
- 关键纠正：历史 `REVIEW_PASS` 必须保留原件，但当前候选允许重新判 `FAIL/INCOMPLETE`；K11 不应与 L4 业务账本一起整桶 BLOCKED；阶段 0 后候选漂移必须新冻结。

## 2026-09-11 product-followup

- 放行：**NO_GO / INCOMPLETE**（手册 10.2 未满）
- 候选：HEAD `8ea1329e` + dirty；阶段 0 digest `801e8ae1`（含 K05 `api.py`）；K04 后 digest `340f188d`（`graph.py` persist_response）
- Skill：**本轮未修订**；SHA256 仍 `89ae938a…`；历史总包审查 FAIL 原件不动
- 本轮执行：C01 颜色追问切片无回归；K11/K06 framework 从 L4 桶拆出实跑；K05 因子矩阵 L1+L3（不冒充手册 K05 PASS）；I01 PASS；I08 非真反代；K01-sse 不闭 K01；B01 不继承 1739；L04 侧边浏览器评测/批准/回滚点击完成但页面与库不一致
- K04 P1：并发同键同正文 500 → persist_response 修复；TestClient + live 重启后 200/同 message_id；独立审查 **PASS**（切片）；手册整行仍 INCOMPLETE
- 费用金额：unknown
- 未执行：L4/L5、真反代、独立站登录、崩溃恢复、C01 纠正对象轮、生产写入

证据根：`../run-20260911-product-followup/`

## 2026-09-11 real user follow-up

- 使用 `env.md` 的 DeepSeek 配置，在隔离 `/private/tmp` 数据目录模拟导入 TXT/Markdown/PDF、C01 多轮追问、L04 反馈/评测/批准/回滚和真实图片请求。
- C01 当前真实同对象追问通过；完整对象切换/纠正轮仍未关闭。
- L04 回滚后候选 API 已返回 `rolled_back`，active knowledge 列表移除 retired 版本；完整真实浏览器文件选择/页面回归仍未关闭。
- 视觉上游诊断为 HTTP 200 + 空 `message.content` + `reasoning_content`；关闭 DeepSeek thinking 后三次真实请求均 `vision_status=applied`。
- 证据根：`runs/run-20260911-real-user/`。

## 2026-09-11 continued follow-up

- 验收判定层：6 类、7 个假阳性已用 fail-closed 探针重判；独立终审 PASS，产品仍 `NO_GO`。
- K04 at-most-once slice：旧实现 counterfactual `generate_calls=2` / exit 1；当前实现 `generate_calls=1` / exit 0，并核对完整响应、`response_json` 和消息计数。
- K04 手册行仍 `INCOMPLETE`：崩溃恢复、跨进程 owner、SSE 交叉重放和业务副作用账本未证明。
- 本轮代码回归：目标模块/API/视觉 33 passed；此前完整 `.venv pytest -q` 117 passed，均保留当前候选证据边界。
- 证据根：`runs/run-20260911-key-fixes/`、`runs/run-20260911-k04-at-most-once/`。


## 2026-09-11 final validation

- 最新候选完整 `.venv/bin/pytest -q`：`120 passed, 10 warnings`；警告为第三方依赖弃用提示。
- Archify 架构图 validate/deliver/visual-check：PASS；证据与产物见 `runs/run-20260911-final/` 和 `../../architecture/yunpai-customer-service.html`。
- 最新架构图已按源码补充 FastAPI、CustomerServiceCore、LangGraph 18 节点、VisionGateway、KnowledgeIngest、FastEmbed/BM25、SQLite checkpoint 和 EvolutionService；1440×900 至 2048×1320 明暗视口均通过 visual-check。
- 这次收口只确认回归和结构图产物，不改变手册 10.2 的 `NO_GO / INCOMPLETE`。

## 最终收口

- 产品验收：**NO_GO / INCOMPLETE**。当前候选在 `graph.py` 修复后为 digest `340f188d`；手册 10.2 仍受 K04 崩溃恢复与副作用至多一次、完整 K05、C01 纠正对象轮、L04 后态一致性、B01、真反代、L4/L5、独立站登录、扫描 OCR、8h soak 等边界限制。
- Skill：依据本次真实产品案例修订，SHA256 `d386bbb1…`；独立 fresh-context 只读审查 **PASS**。修订证据位于 `runs/run-20260911-acceptance-handoff/skill-fix-final/`，审查位于 `reviews/skill-fix-final-review/`。
- 提前进行的 `skill-fix-2` 已标记为 `ABANDONED_PREMATURE`，原始红绿证据保留；它不参与最终 Skill 判定。
- 本轮隔离服务已清理，临时数据目录保留用于审计；未提交、未建分支、未推送。

## 2026-09-11 direction-audit

- 原始方向判定：**一致**。DeepSeek Flash 文本/视觉、本地 FastEmbed/BM25/SQLite 检索、非关键词意图路由、资料导入、语料库和自进化仍是当前实现主线。
- 本地方向核验：`.venv` 下 51 个意图、视觉、知识导入、向量、Demo 对话和领域复用测试通过；这只是实现层辅助证据，不等于手册 10.2 放行。
- 仍未闭环：完整多轮纠正对象、真实图片 K05 全矩阵、L04 页面/API/数据库后态一致、B01、真反代、L4/L5、HR、独立站和 clean runtime。
- 证据：`../run-20260911-direction-audit/`；最终 digest 见 `evidence-digest.json`。
