# yunpai-customer-service

独立可安装的智能客服模块：对话（同步 + 流式）、会话记忆、话术匹配（RAG / 审核精确复用）、自沉淀（反馈 → 评测门禁 → 审批 → 回滚）。

本仓库从 [yunpai-ecommerce-agent](https://github.com/a1024053774/yunpai-ecommerce-agent) 拆出，**两边互不依赖**。原仓库继续自己运转；其他项目用本包即可，不必引入整套电商运营 Agent。

不包含：生产 HTTP API、淘宝渠道、商品/订单经营工具、润色模型。

文本决策默认走 DeepSeek `deepseek-v4-flash`；顾客图片由 `deepseek-v4-flash-vision-exp` 做非权威观察，再交给文本模型决策/生成。图片不能授权退款、改地址等业务动作。

## 安装

```bash
pip install "git+https://github.com/a1024053774/yunpai-customer-service.git"
```

需要 Python 3.11+。对话图用 LangGraph + SQLite。

## 启动示例聊天页

在仓库根目录操作。这是 zsh/bash 脚本流程，不要把命令包进 Markdown 代码块后再 `source`。

**第一次：**

```bash
cd /path/to/yunpai-customer-service
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[demo]"
cp env.example.md env.md
chmod 600 env.md
```

`env.example.md` 是仓库内可提交的无密钥模板；`env.md` 是你自己的本地配置，已被 `.gitignore` 忽略。编辑 `env.md`，填入 `MODEL_API_KEY` 后即可调用真实模型；留空则 Demo 自动使用 mock，不影响页面和预置问答体验。视觉模型默认复用文本模型的地址和 Key，也可以在 `env.md` 中单独设置 `VISION_BASE_URL`、`VISION_API_KEY` 和 `VISION_MODEL_NAME`。

**以后每次：**

```bash
cd /path/to/yunpai-customer-service
source env.md          # 激活 .venv，并导出本地模型配置
yunpai-cs-demo
```

浏览器打开 http://127.0.0.1:8765/ 。示例只监听回环地址，并预装「晴川小家电」模拟店（空气炸锅 / 加湿器 / 挂烫机）。

`env.md` 必须保持为可被 zsh/bash `source` 的 shell 文件：使用 `export KEY=value` 设置变量、使用 `#` 写注释，不要加入 Markdown 代码围栏。不要强制添加或提交该文件。

单独激活虚拟环境也可以：

```bash
source .venv/bin/activate
```

## 用法

```python
from yunpai_customer_service import ChatImageInput, CustomerServiceCore
from yunpai_customer_service.auth import AuthenticationService
from yunpai_customer_service.config import Settings
from yunpai_customer_service.database import Database

settings = Settings.from_env()
settings.ensure_directories()
db = Database(settings.app_db_path)
db.initialize()

core = CustomerServiceCore.build(db, settings)
principal = AuthenticationService(db, settings).authenticate(
    settings.bootstrap_client_id,
    settings.bootstrap_client_key,
    "buyer-1",
)
response = core.chat(principal, session_id="web-1", message="这个怎么保养？")
print(response.answer)
# 带图片时传入 ChatImageInput（PNG/JPEG/WebP，≤5 MiB）
```

宿主只需要注入自己的模型、工具或知识库；不注入时 `build()` 会装配默认协作对象。

```python
core = CustomerServiceCore.build(db, settings, model=your_model, tools=your_tools)
```

`/v1/chat` 与 `/v1/chat/stream` 在原仓库里共用同一份 `plan_generation`。本包同样以此为生成分支的唯一事实源。

## 能力边界

| 能力 | 入口 |
|---|---|
| 对话 | `CustomerServiceCore.chat` / `chat_stream` |
| 图片 | `ChatImageInput`：Vision 观察 → 非权威 `media_evidence` → DeepSeek 决策/生成 |
| 记忆 | 会话历史 + checkpoint；`core.memory.record/recall` 管理店铺长期记忆与买家偏好 |
| 话术匹配 | `KnowledgeBase` 检索；精确问法优先排序，审核话术仍须 normalize 后完全相等才直出 |
| 自沉淀 | `EvolutionService`：feedback → evaluate → approve → 复用 → rollback；重复纠错复用同一候选 |
| 安全 | 注入拒绝、租户隔离、未授权订单字段剥离 |

确定性代码不根据关键词做语义路由。绕过模型直出，必须是已审核内容且问题完全匹配。

多轮短追问只有在当前问法没有召回、且包含“它 / 这个 / 这款”等明确指代时，
才会把上一轮用户问题作为检索语境；该检索词会贯穿后续精化检索，不改变原始用户消息。

长期记忆使用独立的 `memory` layer，不会混入普通 RAG。`recall()` 按相关度排序；
`buyer_preference` 必须绑定认证后的 `subject_hash`，避免同一店铺不同顾客之间泄漏偏好。

```python
memory_id = core.memory.record(
    store_id="store-1",
    fact="顾客偏好静音款。",
    category="buyer_preference",
    tenant_id=principal.tenant_id,
    subject_hash=principal.subject_hash,
)
```

## 测试

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium
NO_PROXY=127.0.0.1,localhost ALL_PROXY=http://127.0.0.1:9 \
  .venv/bin/python -m pytest -q
```

核心模块单测直接构建 `CustomerServiceCore` 并使用模型替身；Demo 交互测试通过 Playwright Chromium 和本地 HTTP 服务验证页面行为。
