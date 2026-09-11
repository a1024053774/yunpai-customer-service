# L01 独立审查

STATUS: PASS
TARGET: workspace `text_utils.product_identifiers` + `rag._score` identifier_bonus=0.2；`tests/test_l01_product_identifier.py`（FastEmbed retrieve top-1，非 live LLM 成文）

## 结论

工作区聚焦测试绿，且 `/tmp` 反证能按声称根因变红。L01 检索排名修复在 **FastEmbed 检索层** 可验收。本审查 **没有** live LLM 成文复测；FastEmbed retrieve top-1 **不是** 对话成文证明。实现者 `green.txt` / `success.png` / `after.html` 不作为验收。

## EVIDENCE

- 工作区命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_l01_product_identifier.py tests/test_product_id_retrieval.py`
- 结果：`4 passed in 3.09s`，`EXIT:0`。见 `L01-pytest.txt`。
- 测试种子与 live 问句形状一致：
  - `PRODUCT_ID == "QA-GROK-2C2668E3"`
  - `CAPACITY_Q` 解码后为 `QA-GROK-2C2668E3 容量和颜色是什么？`
  - 与 `defects/L01-id-lookup/before-l01-browser.json` 的 `question` **完全相等**
  - `seed_demo_store(...)` 写入晴川目录；`ingest_document(..., intent="product_inquiry")`
  - `retrieve(..., intent=routing_for_intent("product_inquiry")["knowledge_intent"]` 即 `product`，`store_id=DEMO_STORE_ID`
  - 显式 `FastEmbedProvider("BAAI/bge-small-zh-v1.5")` 后 `rebuild_embeddings()`
- 审查者独立核对：`search_terms` 把 `QA-GROK-2C2668E3` 拆成 `qa/grok/2/c/2668/e/3`，完整 SKU 不在词面里；`product_identifiers` 保留 `qa-grok-2c2668e3`。
- 源码确有声称改动：`text_utils.product_identifiers` 用连字符正则；`rag._score` 若问句型号出现在文档 `question`/`answer`/`keywords`/`search_text` 原文，加 0.2。
- 历史 live 包（本审查未复探 LLM）：问同一句，答「这个编号我这边没法对应到具体商品」并推晴川 AF50 5L/米白/329；sources `seed-0007` / `qingchuan-airfryer-5l-capacity` / `seed-0014`。不信任实现者绿态。

## COUNTEREXAMPLE

- 仅在 `/tmp/l01-counterfactual-review` 恢复：`_score` **不再** 加 `identifier_bonus`（保留 `product_identifiers` 与 G07 intent 映射）。工作区 `src` 未改。
- 只跑 `tests/test_l01_product_identifier.py::test_fastembed_id_and_spec_query_ranks_imported_product_first`：`1 failed`，`EXIT:1`。见 `L01-counterfactual-red.txt`。
- 失败原因与声称一致：第一名 `seed-0007` score `0.8465`；导入行 `0.8167`；晴川 `demo:qingchuan-airfryer-5l-capacity:15b07900` `0.8139`。
- `PYTHONPATH` 指向 `/tmp/l01-counterfactual-review/src`；该副本 `KnowledgeBase._score` 无 `identifier_bonus`。工作区 `rag.py` sha256 仍为 `553ca920c6c994e472e4d8935cf531431e96e01f0e67a7af1d521fc0b5c2e112`。

## FINDINGS

- 无 P1：聚焦 FastEmbed 测试能打败去掉型号加成的旧打分，且修复后同一信号变绿。
- [P3] 加成是原文子串 +0.2，并未改 `search_terms` 拆连字符型号；词面 BM25 仍看不到完整 SKU。对本合同（top-1）足够，不是词面层修复。
- [P3] `tests/test_product_id_retrieval.py` 用 `QA-FIX-G07A1` + 默认 hash，覆盖 G07 意图映射，不是本 live FastEmbed 缺口的独立反证。

## LIMITATIONS

- 未重跑 live LLM 成文 / 对话探针。合同是 FastEmbed retrieve top-1。
- 实现者 `green.txt`、`after.html`、`success.png` 不作为验收证据。
- 工作区 `src` 未在本审查中被修改。
