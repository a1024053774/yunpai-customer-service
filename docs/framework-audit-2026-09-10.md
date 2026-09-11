# 框架与信任边界审计（2026-09-10）

本报告以当前工作区源码和可执行反例为依据。用户截图是需要防范的失效类型，不被当成本仓库已经存在同名实现的证据。旧的“81 passed / 目标已完成”不能代替这次审计。

## 范围与验收

目标：查明页面、宿主 API、认证、会话、LangGraph、意图、RAG、知识原件和数据持久化的实际关系，修复可复现的框架绕行与信任边界错误。

不做：迁移到 PostgreSQL、引入独立网关/认证微服务、修改服务器部署、发送外部业务消息或执行真实退款、扩展完整 HR 业务。现有未提交工作保留。

验收：真实注册图节点对同步与 SSE 都生效；正常语义不被关键词树覆盖；宿主接口不能继承匿名 Demo 配置；历史/图片送达分类器；原件按租户授权；本地 Demo 拒绝代理、公网 Host 和跨源请求；重启不覆盖语义向量。以先红后绿反例、全量测试和隔离真实模型调用共同证明，不以测试条数代替功能质量。

## 主要结论

当前不是截图所描述的“三节点 Studio 空壳 + YunpaiGraph.run 手写调度”：源码的 `build_graph()` 注册 18 个业务节点，核心同步与 SSE 都调用编译图。但审计发现了较小却同样真实的执行分叉，且不止这一个问题。

| 问题 | 修改前的可达行为 | 本轮修复 |
|---|---|---|
| SSE 绕过图节点 | core 暂停在 generate，图外生成并调用 verify_response，再用 update_state 声称 verify 已完成；修改注册的 generate/verify 不影响 SSE | SSE 只暂停以发出 meta，随后恢复图，让注册的 generate 和 verify 都真正执行。生成传输适配由共用 helper 提供 |
| 正常语义被正则覆盖 | “如果要申请退款，需要什么材料？”即使模型选择 answer，也被 business_action 正则强制 handoff；竞品比较被话题黑名单拦在决策前 | 移除这些业务语义覆盖；模型选择动作，工具注册、SOP、授权和后置条件继续决定能否执行。私密数据和输出保护保留 |
| mock 保留第二套分类树 | mock agent_decision 仍按退款/投诉/价格等中文词返回不同动作 | 删除 mock 语义树及价格关键词特例。mock 只验证结构契约，不作为真实意图证据 |
| 宿主 API 可匿名 | AUTH_REQUIRED=false 或注入匿名 auth 时 create_api_app 仍可启动 | 宿主 API 必须启用且配置客户端认证，否则拒绝创建。匿名仅保留在本机 Demo |
| 重启破坏 embedding | Demo 刷新已存在商品话术时，无论配置什么模型都重写为 hash 向量 | 使用 KnowledgeBase 当前 embedding provider 重新编码 |
| 分类器缺上下文 | 回答阶段能读历史/图片，但独立意图分类只收到当前一句话 | 同一模型分类调用增加有限历史与当前图片观察，保留非权威标记 |
| 原件跨租户可见 | 文件列表/下载只检查文件系统路径，没有核对知识来源所属租户 | 按 source 摘要与文件名回查租户知识记录；未归属文件返回 404，列表排除其他租户原件 |
| Demo 的 loopback 判断不足 | 反代连接来自 127.0.0.1 时可调用本机管理功能 | 同时拒绝转发头、非本机 Host、非本机 Origin。Demo 不可作为公网管理端反代部署 |
| 终止分支跳过输出检查 | 澄清、转人工、投诉、拒绝直接输出模型 response 或 missing_fields，能索要银行卡密码、谎称已退款 | 所有终止回复走共用输出策略；拒绝时输出固定安全文案，响应与持久化一致 |
| 注入模型与配置互相矛盾 | 宿主显式提供模型，旧 gateway 开关仍让意图分类跳过，回答与 intent 元数据不一致 | 分类器使用实际注入模型；默认 gateway 自身决定启用/禁用，不在图里再覆盖可用性 |
| 列表序号被当成业务数字 | 真实售后澄清中的“1）订单号；2）型号；3）现象”触发 numeric_claim_without_evidence | 数字证据检查先排除格式序号，金额/百分比/小数仍需证据；拦截通过 model_fallback 可观测 |
| 混合 PDF 阅读顺序错乱 | 原生提取只有后面的页面时，Docling 补回的扫描页追加在末尾 | 合并后按真实页码排序；保留扫描页内容 |

这些是 12 类根因；新增 28 个回归场景（含跨终止分支与同步/SSE 的输出检查、数字格式和混合 PDF），并补强了既有 PDF 测试的中文内容断言。第一批修改前失败记录为 `audit-2026-09-10/framework-red.txt`、`boundaries-red.txt` 和 `demo-origin-red.txt`；独立审查追加问题的红态见 `independent-findings-red.txt`、`missing-fields-red.txt`；最终专项记录为 `framework-green-final.txt`。

## 证据与边界

- 修改前相关既有测试：26 passed；新增反例仍能复现真实缺陷，说明旧绿灯不覆盖上述边界。
- 当前完整回归：109 passed，10 条既有上游弃用警告，详见 `audit-2026-09-10/final-regression.txt`。
- `tests/test_framework_audit.py` 替换编译图的真实注册节点并注入哨兵回答；同步与 SSE 均观察到 generate、verify，避免只检查 trace 文本的假证据。
- 隔离数据库、真实 DeepSeek + FastEmbed、启用认证的 `/v1/chat` 和 `/v1/chat/stream`：退款条件咨询、竞品比较、滤芯问答都返回正常 answer；注册节点计数均为 `[generate, verify]`。缺少凭据返回 401。详见 `audit-2026-09-10/live-request-probe.json`。
- 本次未将新源码发布到公网服务器。真实模型验证使用模拟产品，不等于真实商品/订单联调。

## 独立审查与跟进

按 behavioral-acceptance-review 在独立只读上下文审查冻结快照，结论为 **FAIL**，指出终止文案审核缺失（P1）和注入模型被设置开关跳过（P2）。详见 `audit-2026-09-10/independent-review.txt`，快照摘要见 `snapshot.json`。

两项发现随后都做了本机独立复现并修复；额外检查了恶意 missing_fields 生成的默认追问。追加修复后的框架专项 27 passed；连同混合 PDF 和既有测试，最终全量 109 passed。修复后的快照没有重新进行第二次独立审查，不把原 FAIL 伪装为最终独立 PASS。

## 其余框架事实与未覆盖范围

- **SQLite 是当前真实存储。** PostgreSQL、独立 API Gateway、认证微服务都不是当前实现。不能为了图漂亮把它们写成已部署组件。
- **HR profile 只是标签与说明。** 当前提示词、示例产品和默认 SOP 仍偏电商；单测里 HR label 正确不能证明 HR 业务已适配。
- **SSE 目前是审核后一次发出答案。** 这保持未审核内容不外泄；不能宣传为逐 token 即时可见。
- **知识治理尚非充分的事实审核。** 文档导入会直接建立 active/approved 条目；纠正经验评测的 source_traceable 主要看来源字符串，numeric 检查和相似度只能提供约束，不能证明资料权威或事实正确。生产审核必须另行验收。
- **embedding 仍缺模型身份的持久化契约。** 本轮修复了重启变回 hash 的直接缺陷；当前仅以维度不一致跳过比较，不能识别相同维度不同模型的混用。切换模型仍须统一后端并重建索引，不能把该路径当成无需治理的任意热切换。
- **PDF 样例的证据质量已修正。** 旧 ReportLab 样例未设置中文字体，输出曾出现 `nnnn`，页码和表格数检查仍能通过。本轮用真实中文断言复现该问题，修复样例字体，确认中文内容也通过；这是测试夹具修复，不冒充解析器解决了所有损坏字体。扫描件、跨页大表和导入事务/失败清理仍需专项验收。
- **认证不等于完整生产防护。** 网关限流、请求体上限、CSRF/CORS 策略、同租户店铺权限、部署凭据管理和长稳还不是本次测试覆盖的全部范围。服务端客户端密钥不能下发到公开网页。

## 公网部署历史与当前状态

已读旧 `yunpai-ecommerce-agent/.project-to-act/PROJECT_ACCEPTANCE.md` 的 E-20260811-001/002/003：旧电商一体机曾部署到 `ssh yunpai`，服务器 `129.211.3.209`，原实例 8767，新并行实例 8768；当时记录公网 `/health`、`/ready`、`/admin` 200。

2026-09-10 只读 SSH 实查：

- `/opt/yunpai-ecommerce-agent` 的 `yunpai-ecommerce-agent.service` 为 active，当前监听 **127.0.0.1:8767**，服务器内 `/health` 为 ok。
- 服务器现用 Qwen 模型，SQLite schema 41；这是旧完整电商项目，**不是本机独立客服的新代码**。
- `yunpai-ecommerce-agent-main.service`（8768）为 inactive/dead。
- 本次公网直接探测旧 8767/8768 均未得到有效 HTTP 响应；当前 Nginx 配置未找到转发 8767 的入口，因此只确认服务仍在服务器运行，不宣称当前有可用公网地址。
- 服务器的 8765 属于另一个应用，不应与本机 8765 客服 Demo 混淆。

现场摘要与外部探测见 `audit-2026-09-10/server-status.json`、`public-endpoints.json`。没有修改远程服务、端口、数据库或环境。

## Archify 图

- [用户指定的 Browser → API Gateway → Auth Service → PostgreSQL 目标示意](architecture/request-trust-boundaries.html)
- [当前客服真实执行链与信任边界](architecture/current-customer-service.html)

两张均由 Archify deliver 校验通过：9/9 showcase，0 composition errors / warnings，JSON 与 HTML 摘要记录于相邻 `.receipt.json`。

按“不使用 Chromium”约束，未运行技能内置 Chrome/Chromium visual-check。用 Codex 侧边浏览器补充检查了 1440×900、1600×1000、1920×1080、2048×1320，页面尺寸均无溢出，并观察浅/深主题。该记录是人工代理浏览器证据，不冒充内置自动化验收；见 `.manual-browser.json`。图可放大、切换主题并导出 PNG/SVG。

## 最终运行回查

本机 8765 启动了本轮修复后的源码，DeepSeek Flash / vision / FastEmbed 配置保持；直接本机 health 200、跨源请求 403、自有原件可列出。最终实测的编号式售后澄清为 `terminal_output:passed`，原始错误与修复后结果分别保存在 `live-terminal-probe-before.json` / `live-terminal-probe.json`。

所有改动仍在本机未提交工作区；未 commit、push 或部署到远程旧实例。
