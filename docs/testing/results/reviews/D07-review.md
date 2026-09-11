# D07 独立审查

**裁决为 PASS**

审查者与实现者隔离，不采信 `green.txt` / `success.png` / `after.html` 作为通过证据。以工作区独立重跑聚焦测试 + `/tmp` 反事实为准。

## 跑了什么

工作区命令：

```
cd /Users/luckye/Documents/Code/yunpai-customer-service
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_embedding_identity.py tests/test_embeddings.py
```

结果：`5 passed`，**pytest_exit=0**。原始输出：`docs/testing/results/reviews/D07-pytest.txt`。这是审查者重跑，不是实现者自测。

源码与 schema 核对（不采信实现者 how-fixed.md）：

- `embeddings.py`：`HashEmbeddingProvider.identity = "hash"`；`FastEmbedProvider` 保存 `self.model_name`，`identity` 为 `fastembed:{model}`；`name` 仍是家族字面量 `fastembed`。
- `database.py`：`SCHEMA_VERSION = 39`；`initialize` 调 `_apply_v39`；`_apply_v39` 给 `knowledge` 加 `TEXT` 列 `embedding_model`；`_validate_schema` 的 `knowledge` 必填含 `embedding_model`。
- 真实 SQLite：`Database.initialize()` 后 `PRAGMA user_version=39`，`PRAGMA table_info(knowledge)` 含 `embedding_model`，`schema_migrations` 含 39。
- `rag.py`：`add_document` / `rebuild_embeddings` 写入身份；`retrieve` 在打分前丢弃「已有身份且与当前 provider 不同」的行。
- `demo/catalog.py`：`_refresh_demo_knowledge` 的 `UPDATE` 写入 `embedding_model`。

## 反事实

副本：`/tmp/d07-counterfactual-12971`（仅复制 `src/` `tests/` `pyproject.toml`；**工作区产品源码未改**）。

只删 `retrieve` 身份过滤，保留 `add_document` 写 `embedding_model`，使测试能越过落库断言。

只跑 `tests/test_embedding_identity.py::test_same_dimension_different_model_is_not_retrieved`。

结果：**失败，exit 1**。失败点为 `assert doc_id not in {item["id"] for item in rows}`。落库断言 `embedding_model == "model-a"` 已通过，因此是声称的「同维不同模型行仍被检索」红因，不是装配/导入错误。本次实例：`assert 'kb-1f98d0ac89f64369afc32a3f68f1b57f' not in {'kb-1f98d0ac89f64369afc32a3f68f1b57f'}`。输出：`docs/testing/results/reviews/D07-counterfactual-red.txt`。

## 结构比例

- 没有第二套 embedding 检索 API。`graph.retrieve` / `core.knowledge` 都走 `KnowledgeBase.retrieve`；唯一工厂 `build_embedding_provider`。
- `_score` 仍只按向量长度做余弦；身份门在 `retrieve` 预过滤。已打标且与当前 provider 不一致的行不进入打分，不会静默以同维余弦混模。
- NULL 旧行：`embedding_model` 为空仍检索（BM25+同维余弦）。审查者独立探测：把已写身份置 NULL 后切换 provider，行仍命中。这是声称的兼容，不是新身份过滤的静默绕过。
- `FastEmbedProvider.name` 仍是 `fastembed`；比较用 `identity`，不靠 `name`。`_embedding_identity` 在 `identity` 为空时退回 `name`，若自定义 provider 只有家族名仍可能混模。当前 `FastEmbedProvider.identity` 常有值，此退回不会走到生产 FastEmbed 路径。
- catalog 刷新用 `getattr(identity) or name`，与 `KnowledgeBase._embedding_identity` 重复了一小段，不是平行向量栈。

## 测试能否被绕过

混模测试走真实 `KnowledgeBase.add_document` / `retrieve` / `rebuild_embeddings`。正交向量下 BM25+意图加成仍会命中，因此只把余弦关掉不够绿；必须整行跳过。反事实去掉过滤后仍命中，说明合同锁的是身份过滤，不是「向量不同就不检索」。rebuild 后身份改为 `model-b` 且必须再命中，避免「 retrieve 永远为空」混过。

`test_fastembed_provider_keeps_concrete_model_identity` 是源码检查，不实例化 FastEmbed。混模用 `FixedProvider`，不下载真模型。

## 剩余缺口

- **未做 live 双 FastEmbed 模型下载对照**。`live_fastembed_two_models=false`。同维混模合同由 `FixedProvider` + 反事实锁住；真 FastEmbed 向量几何未跑。
- NULL 旧行仍可与当前 provider 做同维余弦；这是声称行为，不把 PASS 改成 FAIL。
- 实现者 `green.txt` / `after.html` 不算验收。

按任务规则：工作区聚焦测试通过 **且** `/tmp` 反事实因混模行仍被检索而失败 → **PASS**。
