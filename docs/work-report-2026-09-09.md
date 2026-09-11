# 云派智能客服工作汇报（2026-09-09）

> 后续状态：2026-09-10 框架审计复现了本报告测试未覆盖的执行分叉与信任边界缺陷。请同时阅读 [后续审计](framework-audit-2026-09-10.md)；本文件保留当时复测记录，不作为当前生产放行结论。

对照 Codex 会话 `01a08146-10bc-72d2-b5e5-43eea3a8eb0e` 与你当时的目标，本轮做了独立核对、真实点击验收和缺口修补。密钥未写入本文件。

## 结论

目标里能在本机 Demo 验证的部分已经达到，并且不是收费云端 RAG。

- 意图识别与回答共用 DeepSeek `deepseek-v4-flash`，独立轻量意图模型接口已删除。
- 检索是本机 FastEmbed + BM25；PDF 用 Docling 解析版式、pdfplumber 补页。没有 Pinecone / Weaviate / Unstructured 云服务。
- 知识工作台可导入资料并下载原件；反馈可进入评测门禁，门禁不通过就不能发布。
- 多轮指代、售前歧义退款、立即退款转人工、真实图片，都在 Cursor 侧边浏览器里点过。

还没做完、也不能假装做完的部分：真实独立站渠道、HR 真实 SOP 与数据、生产权限隔离。这些需要接入方提供环境后才能验收。

## 收费库排查

| 组件 | 是否安装 | 费用与运行位置 |
|---|---|---|
| FastEmbed `BAAI/bge-small-zh-v1.5` | 是 | Apache-2.0，本机 ONNX。首次从 Hugging Face 下载到本机缓存，之后可离线。不是 Qdrant Cloud。 |
| Docling | 是 | MIT，本机解析 PDF 版式和表格。 |
| pdfplumber | 是 | 开源，本机轻量文本和表格。 |
| Pinecone / Weaviate / Chroma Cloud / Unstructured / OpenAI embedding / Cohere | 否 | 未引入。 |

`config.py` 里仍残留父仓库的 Neo4j / 淘宝字段，当前代码没有使用，也没有安装 neo4j 客户端。这不是 RAG 依赖。

运行参数在被 gitignore 的 `env.md`：文本 `deepseek-v4-flash`，视觉 `deepseek-v4-flash-vision-exp`，检索 `fastembed`。可提交模板是 `env.example.md`，不含密钥。

## 原目标对照

| 你当时说的 | 核对结果 |
|---|---|
| 不用小模型，用 DeepSeek Flash 做意图 | 达到。`classify()` 只调用共享 `ModelGateway.generate_json`，无 `INTENT_MODEL_NAME`。 |
| 删掉轻量意图模型接口 | 达到。测试已覆盖网关无独立意图模型参数。 |
| 路由不要关键词写死 | 基本达到。语义路由走模型四个控制桶；`intent_routing.json` 只把桶映射到 SOP/检索槽。注入检测和高风险退款仍用规则做安全边界，不替代意图分类。 |
| 多轮 / 带图 / 歧义 | 本轮侧边浏览器实测通过。过小 PNG 会让视觉报 error，正常 PNG 为 applied。 |
| 喂资料、知识库页面、语料 | 达到。`/admin` 可导入 PDF/TXT/Markdown，保留页码、表格数和原件。 |
| 自进化和经验沉淀 | 闭环真实存在：纠正到 pending，再评测。本轮一条颜色纠正因 numeric_claim_without_evidence 未过门禁，工作台不出现批准发布。这是门禁在起作用。此前已批准的滤芯经验仍可回滚。 |
| 智能问答不要落后 | 当前栈：模型意图、混合检索、流式回复、来源引用、视觉观察、受控发布。没有上云端向量库。 |
| PDF 结构而不只是 OCR | 达到。本轮导入两页 PDF：第 1 页识别到 1 张表。 |
| 前端不要太老气、铃铛对齐最新 | 本轮改成浅色工作台风格，铃铛写明 Flash 意图、本地 FastEmbed、Docling、独立站接口。 |

## 本轮真实点击（Cursor 侧边浏览器，非 Chromium）

健康接口当时为 live：DeepSeek Flash + 视觉模型 + FastEmbed。

| 操作 | 结果 |
|---|---|
| 点「5L 空气炸锅容量」并发送 | 意图 product_inquiry / model，答出 QC-AF50、5L、1500W、329 元 |
| 同一会话输入「这个有几种颜色？」 | 继承 QC-AF50，米白；提到 QC-AF35 浅灰 |
| 新会话问退款通常需要什么条件 | 意图仍是售前 product_inquiry，讲七天无理由条件，不执行退款 |
| 新会话「请马上给我退款」 | 意图 after_sales，已转人工，风险 high |
| 纠正颜色回答并提交 | 已记录，候选经验 candidate_pending |
| 工作台点评测 | 变为 evaluated，gate_passed=false |
| 导入两页产品 PDF | 2 个片段，第 1 页 tables=1 |

截图目录：`docs/screenshots/`。明细见 `docs/acceptance-2026-09-09.md`。

自动化：全量 pytest 81 passed。

## 本轮代码改动

- 客服页、知识工作台改为浅色商用布局；铃铛与 README / env.example.md 去掉过时说法。
- RAG 技术说明改为明确未采用任何收费云端向量库。
- 回复标签同时展示模型意图桶 customer_intent。

## 建议下一步（需你提供环境后才做）

1. 独立站真实租户、认证密钥和 store_id。
2. HR 制度 PDF 与 SOP，用 BUSINESS_DOMAIN=hr 另开租户验收。
3. 扫描件或跨页大表再单独评测 Docling；当前样例是可抽取的电子 PDF。
