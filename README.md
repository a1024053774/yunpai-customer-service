# yunpai-customer-service

独立可安装的智能客服模块：对话（同步 + 流式）、会话记忆、话术匹配（RAG / 审核精确复用）、自沉淀（反馈 → 评测门禁 → 审批 → 回滚）。

本仓库从 [yunpai-ecommerce-agent](https://github.com/a1024053774/yunpai-ecommerce-agent) 拆出，**两边互不依赖**。原仓库继续自己运转；其他项目用本包即可，不必引入整套电商运营 Agent。

不包含：HTTP API、淘宝渠道、商品/订单经营工具、润色模型、多模态。

## 安装

```bash
pip install "git+https://github.com/a1024053774/yunpai-customer-service.git"
```

需要 Python 3.11+。对话图用 LangGraph + SQLite。

## 用法

```python
from yunpai_customer_service import CustomerServiceCore
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
| 记忆 | 会话历史 + 上下文预算截断 + checkpoint |
| 话术匹配 | `KnowledgeBase` 检索；审核话术须 normalize 后完全相等才直出 |
| 自沉淀 | `EvolutionService`：feedback → evaluate → approve → 复用 → rollback |
| 安全 | 注入拒绝、租户隔离、未授权订单字段剥离 |

确定性代码不根据关键词做语义路由。绕过模型直出，必须是已审核内容且问题完全匹配。

## 测试

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
NO_PROXY=127.0.0.1,localhost ALL_PROXY=http://127.0.0.1:9 \
  .venv/bin/python -m pytest -q
```

单测全部直接构建 `CustomerServiceCore`，使用表驱动模型替身，不解读用户原文。
