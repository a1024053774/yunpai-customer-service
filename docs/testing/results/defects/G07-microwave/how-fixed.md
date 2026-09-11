# G07 怎么修的

## 现象
Live 问 `QA-GROK-2C2668E3 可以放进微波炉加热吗？` 命中晴川加湿器/空气炸锅，没有合成资料「不可微波」。模型成文被 `numeric_claim_without_evidence` 换成万能句。

同一检索缺口也解释 L01（只报型号却推 QC-AF50）和 D02（已知型号当未知）。

## 根因
知识 `intent` 混用了两套词表：

- 导入 API / `ingest_document` 默认写入 customer intent `product_inquiry`
- 图检索传入 `routing_for_intent(... )["knowledge_intent"]`，商品问答是 `product`
- 晴川目录行本来就是 `product`，吃到 0.12 intent bonus
- 上传行对不上，被 5L/米白/329 近邻挤出第一名（live FastEmbed 时直接挤出 top-3）

## 改动
1. `knowledge_ingest.py`：customer intent 先映射成 knowledge intent 再入库。
2. `rag.py` `_score`：若库里仍是 customer intent，打分时映射后再比，避免已导入行要删了重传才生效。

未改 tokenizer。hyphenated SKU 仍会被拆开；hash 下 intent 对齐已足够让导入文档排第一。live FastEmbed 未复测。

## 证据
- 错误截图：`error.png`
- 成功截图：`success.png`
- 红态：`red.txt`（第一名是晴川清洗；入库 intent=product_inquiry）
- 实现者绿态（不算验收）：`green.txt`、`after-retrieve.json`
- live 原文：`before-live.json`
- 独立审查：`../../reviews/G07-review.md` — **PASS**（工作区 7 passed；/tmp 反证入库 product_inquiry且微波炉问句第一名是晴川清洗）
- 原审查合同不含 live 成文；2026-09-11 已补 live FastEmbed/LLM，见下节。hash 测试不是 live FastEmbed 证明

实现者自测不算通过。独立审查 PASS 不等于 live 成文已修好。
## 2026-09-11 live FastEmbed/LLM

问「可以放进微波炉加热吗」。合成资料第一名 1.052。回答不可微波 / 不能放进微波炉。证据 `after-live.json`。不改原独立审查合同。
