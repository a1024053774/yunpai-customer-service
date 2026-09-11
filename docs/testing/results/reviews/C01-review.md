# C01 独立审查

**裁决为 PASS**

审查者与实现者隔离，不采信 `green.txt` / `green-memory-suite.txt` / `success.png` / `after-chat.json` / `after.html` 作为通过证据。以工作区独立重跑聚焦测试 + `/tmp` 反事实为准。

## 跑了什么

工作区当前 `src/yunpai_customer_service/graph.py` `retrieve()`（hint 命中时无论首次检索是否为空都拼上一轮 OTHER 用户句；有命中则替换 documents）：

```
cd /Users/luckye/Documents/Code/yunpai-customer-service
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_customer_service_module_memory.py::test_color_follow_up_uses_previous_product_when_generic_color_docs_also_match \
  tests/test_customer_service_module_memory.py::test_follow_up_retrieval_uses_the_previous_user_turn_when_needed
```

结果：`2 passed`，**pytest_exit=0**。原始输出：`docs/testing/results/reviews/C01-pytest.txt`。这是审查者重跑，不是实现者自测。

`retrieve()` 当前块（约 443-466 行）与声称一致：`if _CONTEXT_REFERENCE_HINTS.search(retrieval_query):`（无 `not documents` 门）；`previous_user` 跳过与当前问句相同的 user 轮；上下文检索有命中才写 `retrieval_query` / `contextual_retrieval` 并替换 `documents`。

## 反事实

副本：`/tmp/c01-counterfactual-99736`（仅复制 `src/` `tests/` `pyproject.toml`；**工作区产品源码未改**）。

将副本 `retrieve()` 恢复为修复前块：

- 条件：`if not documents and _CONTEXT_REFERENCE_HINTS.search(retrieval_query):`
- 有上一轮 user 句时先赋 `retrieval_query` / `contextual_retrieval = True` 再 `search(contextual_query)`

只跑新测试 `test_color_follow_up_uses_previous_product_when_generic_color_docs_also_match`。

结果：**失败，exit 1**。失败点为 `assert product_id in follow_ids`（追问 sources 里没有产品 id，只有通用颜色文档 id）。前置 `competing retrieve`（追问句命中 generic、不含 product）与首轮 product sources 均已通过，因此是声称的 C01 红因，不是装配/导入错误。输出：`docs/testing/results/reviews/C01-counterfactual-red.txt`。

本次实例：`assert 'kb-3325c45d0ac44c2986e7e9934ffddb4e' in {'kb-bbf4c5e4b7fb4459add5d517695193f4'}`。

## 截图

- `error.png`：与 `before.html` / `before-live.json` 一致。Live Grok 4.6，会话 `r2-d01exact-6cbd8a33`。D01 exact 答 5L / 米白；追问「这个颜色是什么」改问哪款商品；sources `seed-0014, seed-0007, seed-0004`；trace `kept2`。这是原始 live 红态。
- `success.png`：实现者 dump。横幅写明 TableDrivenModel 固定回复，承诺的是 sources / `retrieve:contextual`，**不是 live 成文**。与 `after.html` / `after-chat.json` 一致。**Live L3 未重跑**。不能当作米白成文已修好。

## 测试能否被绕过

新测试在 `core.chat` 之前用 `core.knowledge.retrieve`（不经 `graph.retrieve`）断言：追问句已命中 `generic_id`、且 `product_id` 不在 competing hits；`rag_top_k=1`。因此：

- 不能靠把 generic 藏掉、或靠 top_k 把产品混进追问单句首次检索来混过前置条件。
- 不能只打 `retrieve:contextual` 旗标而不把产品放进 follow-up sources。
- 旧测试 `test_follow_up_retrieval_uses_the_previous_user_turn_when_needed` 用 `rag_min_score=0.3` 制造首次空检索，覆盖不到 C01。

「无条件拼接历史」会让新测试变绿：那是比 hint 门更宽的实现，仍满足 C01 合同（追问 sources 含产品），不是用 top_k 藏 generic。测试锁的是「首次检索非空时仍要上下文替换」，不是「仅在 hint 命中时才拼」。

`TableDrivenModel` 按 `task_type` 表驱动，不解读用户原文，无法用改写问句把产品名塞进精化检索。反事实失败说明合同依赖初始 `retrieve()` 替换，而非 `refine_retrieval` 救场。

## 剩余缺口

- **未对 `r2-d01exact` / live Grok 4.6 做 L3 再探测**。真实缺陷是内置 SOP（seed-0014/0007/0004）上追问改 clarify；当前绿态是隔离 fixture + 替身模型。`retrieve:contextual` 与产品 id 合同已被单测+反事实锁住，但「有产品证据时模型仍可能选澄清」没有 live 复证。
- `success.png` 回答是替身固定句，不是「米白」。
- 测试语料库不含内置 ecommerce SOP；与 live 的竞争文档集不同，仅复制「generic 首次非空→ 跳过上下文检索」这一门。

按任务规则：工作区聚焦测试通过 **且** `/tmp` 反事实按产品 id 缺失失败 → **PASS**。Live 未复跑不把 PASS 改成 INCOMPLETE，但必须记为缺口。
