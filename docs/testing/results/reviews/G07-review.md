# G07 独立审查

STATUS: PASS
TARGET: workspace `knowledge_ingest._stored_knowledge_intent` + `rag._score` customer-intent 映射；`tests/test_product_id_retrieval.py`（hash embedding retrieve 排名，非 live FastEmbed / LLM 成文）

## 结论

工作区聚焦测试绿，且 `/tmp` 反证能按声称根因变红。G07 检索排名修复在 **hash embedding 检索层** 可验收。本审查 **没有** live FastEmbed / 对话 LLM 复测；hash 测试 **不是** live FastEmbed 证明。实现者 `green.txt` / `success.png` 不作为验收。

## EVIDENCE

- 工作区命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_product_id_retrieval.py tests/test_knowledge_ingest.py`
- 结果：`7 passed, 10 warnings in 40.32s`，`EXIT:0`。见 `G07-pytest.txt`。
- 测试种子与声称一致：
  - `seed_demo_store(...)` 写入晴川目录；`DEMO_STORE_ID == "demo-qingchuan-shop"`
  - 合成正文含 `5L` / `米白` / `329`，产品 ID `QA-FIX-G07A1`
  - `ingest_document(..., intent="product_inquiry")`
  - `retrieve(..., intent=routing_for_intent("product_inquiry")["knowledge_intent"]` 即 `product`，`store_id=DEMO_STORE_ID`
  - 问句覆盖微波炉、ID+容量颜色、仅 ID
- 源码确有声称改动：导入时 `intent=_stored_knowledge_intent(intent)`；`_score` 对 `INTENT_ROUTING` 里的 customer intent 先映成 `knowledge_intent` 再加 0.12 bonus。
- 历史 live 包 `before-live.json`（本审查未复探）：问 `QA-GROK-2C2668E3 可以放进微波炉加热吗？`，sources 全是晴川，`used_synthetic: false`。不信任实现者绿态图。

## COUNTEREXAMPLE

- 仅在 `/tmp/g07-counterfactual-review` 恢复：入库写入原始 `intent`；`_score` 改回 `intent_bonus = 0.12 if intent and document["intent"] == intent else 0.0`。工作区 `src` 未改。
- `tests/test_product_id_retrieval.py`：`2 failed`，`EXIT:1`。见 `G07-counterfactual-red.txt`。
- 失败原因与声称一致：
  1. 入库 `row["intent"] == "product_inquiry"`，预期 `"product"`
  2. 微波炉问句第一名 `demo:qingchuan-airfryer-clean:15b07900` score `0.6396` intent `product`；导入行 score `0.586` intent `product_inquiry`
- 旧代码下另做 hash 排名探针（pytest 在微波炉问句就断言，未跑到后两问）：
  - ID+容量颜色：导入也不是第一（`seed-0007` 0.7385，晴川 5L 0.6851，导入 0.6753）
  - 仅 ID：导入仍第一（0.6104 vs 晴川 0.5507）——**hash 下 ID-only 不能单独给出该根因的红态**

## FINDINGS

- 无 P1：聚焦测试能打败声称的旧实现，且修复后同一信号变绿。
- [P3] `tests/test_product_id_retrieval.py` 期望 knowledge intent 走生产 `routing_for_intent`，但同时 `assert expected == "product"`，不够以否定本次 PASS。
- [P3] 仅 ID 问句在 hash+旧 intent 比对下仍能排第一；L01 ID-only 的检索断言在本套上主要是绿路拓展，不是该根因的独立反证。ID+容量颜色会随旧代码失败。

## LIMITATIONS

- 未做 live FastEmbed 复测，也未重跑 live LLM 成文 / `numeric_claim_without_evidence`。
- 默认 `rag_embedding_provider=hash`。hash 测试 **不是** live FastEmbed 证明。历史 live `before-live.json` 里导入行被挤出 top-3，本次 hash 反证里导入行仍在 top-3 第二，只是输给晴川清洗话术。
- 实现者 `green.txt`、`after-retrieve.json`、`success.png` 不作为验收证据。
- 工作区 `src` 未在本审查中被修改。
