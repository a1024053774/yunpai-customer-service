# 验收结论

- run: `run-20260911-acceptance-handoff`
- 执行体: Cursor Grok 4.6 Extra High Fast（`cursor-grok-4.6-xhigh-fast`）。本轮未使用 Orca / Codex / Luna / gpt-5.6-luna。
- 候选: HEAD `8ea1329e8fd495cff3887bbed05ab4b5b9da8c99` + 完整 dirty tree。HEAD 单独不能标识候选。
- 阶段 0 digest: `0016c55d33fe645d01843de11fe56e451f4569e06f9df54e3b7c63db01bc8156`
- K05 修复后 `api.py`: `e268c2b30b3f19e002dba8539894617afd29728855ced4607da1779d2fb0cfee`（相对冻结 digest 已漂移；`freeze.json` 未覆盖）
- 放行: **NO_GO / INCOMPLETE**
- 原因: 手册 10.2 未完整满足。本轮 live/L1 切片不是产品通过。**不把 109 pytest 写成产品通过**（本轮亦未把全量 pytest 当放行证据）。未直接改 `docs/testing/results/CASES.json` / `INDEX.json` / `README.md`。

## 10.2 对照

1. 范围内所有 P0/P1 必须 PASS：**未满足**。仍有 BLOCKED 的 P0/P1；大量手册项为 NOT_RUN / INCOMPLETE。
2. 承诺真实边界须有 L3/L4/L5 证据：本轮仅局部 L3；**L4/L5 未做**。
3. 知识真值、权限、关键动作后置、容量门槛：未测满，也未在本 run 冻结完整门槛。
4. 非 PASS 项有处置：见 `cases-this-run.json`；历史账本本轮不改。
5. 安装、配置、备份、回滚、告警、密钥轮换：**未做**。
6. 独立验收：K05 有脱离上下文 fresh reviewer PASS；**整包无独立放行审查**。

## Skill 评估

- 评估文件: `skill-evaluation.md`
- 评估结论: **部分有效，有可执行缺口**
- 评估完成前 **未改 Skill**
- 评估后: 独立 `skill-fix/` 红绿链，修订 `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md`
- skill sha: `6ec9c4f5...1427` → `89ae938a...7bac`；产品 digest 与 Skill 分开冻结
- 有效约束: HEAD+完整 dirty 冻结、L0–L5、BLOCKED/INCOMPLETE、先红后绿文本、禁止把 pytest 绿当 GO
- 缺口已补: 执行体/模型针、ISO-001 `source env.md` 再 `export DATA_DIR`、fresh reviewer Task/禁止 resume/background、CJK 落盘、禁 file:// 截图、REVIEW_PASS 不得改回 FAIL、禁止跑次中途改 CASES、与 grilling 等待冲突、不完整 10.2 即 NO_GO

## 阶段 0 基线

- 目录: `docs/testing/run-20260911-acceptance-handoff/baseline/`
- 汇总: `freeze.json` `runtime.json` `manifest.json`
- ISO-001 refuse: `baseline/iso-001-refuse.json` **PASS**（拒绝仓库 `data/`）
- 启动顺序: 先 source `env.md` 再 `export DATA_DIR=/tmp/yunpai-handoff-20260911`（实际 `/private/tmp/yunpai-handoff-20260911`）
- schema: 39
- env.md: 仅 23 个变量名；含 `DATA_DIR`；sha256 `2aa41532...dad94`；**未写密钥**
- 依赖: Python 3.11.14；fastapi 0.141.1；fastembed 0.8.0；docling 2.126.0
- 实际模型: deepseek / `deepseek-v4-flash` / `model_mode=live` / FastEmbed `BAAI/bge-small-zh-v1.5` / vision `deepseek-v4-flash-vision-exp` / OCR `pdfplumber+optional-docling`
- 服务（启动时）: Demo `127.0.0.1:53120` pid 18059；重启后 Demo `127.0.0.1:57707` pid 32505

## 本轮 10.2 实探摘要

### L3 live（`live/live-results.json` 保留原探测行，不覆盖红态）

| ID | 本轮 | 说明 |
|---|---|---|
| L05-health | PASS | live/fastembed 标签；不是完整 L05 产品声明 |
| E-import-txt / E01-pdf | PASS | 电子 PDF；**非扫描 OCR** |
| I01 | PASS | 未认证 `/v1/chat` → 401 |
| I08 | PASS | Host/XFF 403；**不是真实反代**；N03 仍 BLOCKED |
| B01 | INCOMPLETE | 用了晴川 SOP，未引用合成退款材料；未承诺已退款 |
| B02 | PASS | 不执行退款/不称已退款 |
| B03 | PASS | 否定理解，答保修 |
| B04 | PASS | 竞品无证据 |
| D01 | PASS | 5L/米白 + synthetic |
| D02 | rejudge PASS | 探针 FAIL 是 `STOCK_RE` 误把「12 个月」当库存；答案明确无库存/销量/到账 |
| G07 | PASS | 不可微波；REVIEW_PASS 不改回 |
| L01 | PASS | 无 AF50/晴川陷阱 |
| B08-typo | PASS | 仅 typo 切片 |
| C01 | PASS | 多轮颜色 HTTP + 浏览器 |
| K01-sse | PASS | Demo SSE 帧 |
| K04 | PASS | 同键同文复用 message_id |
| K05 | REVIEW_PASS | 原 live 500；修复后 409 + 独立审查 PASS |
| F01 | PASS | pending candidate |
| J01 | PASS | 读出 `QA-HO-VISION`；vision_status=applied |

### L1

D07 schema 39 PASS（本轮是 hash 身份，**不是 live 双 FastEmbed**）；D07-other INCOMPLETE；F01/F03/K04/K05-core/C08-reopen/A08 PASS。

### 浏览器

- **Cursor 侧边 `cursor-ide-browser`：FAILED_NO_TAB**（list 空，navigate 报 no tab）。
- 改用 Chrome DevTools MCP 对 Demo 真实点击：L05/L01/C01 PASS；L04 打开 `/admin` 但 **未点 evaluate/approve/rollback** → INCOMPLETE。
- 截图走临时 localhost HTTP（Demo），非 `file://`。

### 重启 C08 / K05 live

- 同 `DATA_DIR` 重启后 Host K05：首次 200、冲突 **409** `idempotency_key_conflict`（`live/restart.json`），补 reviewer 「未重打 live」局限。
- C08 L3 **INCOMPLETE**: Demo `/api/sessions` 为 0；原因是 `start_servers.py` 轮换 bootstrap 客户端。sqlite 仍有 17 会话 / 38 消息。L1 同库 reopen PASS。**不当产品 FAIL 闭环**。

## 缺陷

### 本轮新 P1：K05-host-500

- 红: Host 同 `Idempotency-Key` 不同 message → HTTP 500（`before.json` + live 500）
- 根因: `api.py` 未映射 `SessionScopeError`
- 绿: 409 `idempotency_key_conflict`；SSE 亦 409
- 审查: fresh `cursor-grok-4.6-xhigh-fast`，禁止 resume，`review.json` verdict PASS，`edited_code: false`
- 目录: `defects/K05-host-500/`

### 已 REVIEW_PASS（不改回 FAIL）

C01 / G07 / L01 / D07 / D02 / G04 / F09 / F11 / F05 / F10 / 7.2。本轮复探：C01 G07 L01 D02 D07。G04/F09/F11/F05/F10/7.2 本轮未再开缺陷审查。

## BLOCKED（本轮再确认）

N03（真反代）、N04（独立站登录）、O02–O06（HR）、K06–K13（业务账本写工具）、M08（8h soak）、A06/N01（干净包）、E03（扫描件真值）。

## 本轮 NOT_RUN / 不得声称已过

- 账本 NOT_RUN: L03 L06 L08 M04 M05 M06 M07 M09 M10 N05 N06 N07 N08 P05 P08 7.9
- 未做且不得声称: L4、L5、HR 业务、8h soak、干净包安装、扫描 OCR、真实反代、独立站登录、D06/D08 live 双 FastEmbed
- L04 完整审批 UI、B01 合成退款材料主来源、Cursor 侧边浏览器本身：INCOMPLETE

## 成本

`docs/testing/run-20260911-acceptance-handoff/cost.json`。提供方未返回 token/费用字段；记录了模型调用次数与 HTTP 耗时。费用金额本轮 **不可知**。

## 清理

- 停止隔离 Demo/API 进程（见 `cleanup.json`）
- 不删除本 run 证据、不覆盖旧证据
- 不碰仓库 `data/`
- 隔离 `DATA_DIR` 保留 sqlite 供核对，凭证仍在 DATA_DIR 临时文件中、未拷进 evidence

## GO / NO_GO

**NO_GO / INCOMPLETE**

可限定范围的观察：隔离 DATA_DIR + live DeepSeek + FastEmbed 下，合成货号 QA-HO-11SEP26 的颜色/容量/不可微波/缺字段拒绝虚构、多轮、图片、SSE、幂等重放、未认证 401、loopback Host 抢头 403、K05 冲突不再 500。这 **不等于** 手册 10.2 放行。
