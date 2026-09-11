# D07 怎么修的

## 现象
同维不同 embedding 模型切换后，旧向量仍被检索。模型身份未落库。FastEmbedProvider.name 只是 `fastembed`。

## 根因
`_score` 只比较向量长度，长度相同就做余弦。知识表没有 embedding 模型列。

## 改动
- `embeddings.py`：Hash `identity=hash`；FastEmbed 保存 `model_name`，`identity=fastembed:{model}`。
- schema v39：`knowledge.embedding_model`。
- `add_document` / `rebuild_embeddings` / demo 刷新写入身份。
- `retrieve`：已有身份且与当前 provider 不同的行直接跳过。无身份的旧行仍可 BM25 检索。

## 证据
- 错误截图：`error.png`
- 成功截图：`success.png`
- 红态：`red.txt`
- 实现者绿态（不算验收）：`green.txt`
- 原 probe：`before-probe.json`
- 独立审查：`../../reviews/D07-review.md` — **PASS**（工作区 5 passed；/tmp 去掉 retrieve 身份过滤后混模行仍被检）
- schema v39 已确认；NULL 旧行仍可 BM25+同维余弦；未做 live 双 FastEmbed

实现者自测不算通过。独立审查 PASS 不等于 live 双模型已验证。
