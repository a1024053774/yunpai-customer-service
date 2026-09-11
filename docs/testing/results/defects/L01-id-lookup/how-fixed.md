# L01 怎么修的

## 现象
Live 问 `QA-GROK-2C2668E3 容量和颜色是什么？`（FastEmbed）。回答说对不上该编号，改推晴川 AF50 5L/米白/329。sources：seed-0007（这是什么材质）、qingchuan 5L、seed-0014（颜色和图片一样吗）。UI 旅程能走完，事实 oracle FAIL。

G07 的 intent 词表对齐之后，同一问句在 FastEmbed 下第一名仍是 seed-0007（0.8465），导入行第二（0.8167）。hash 下该问句已经能排第一，所以 G07 审查说「仅 ID 在 hash 旧代码不红」；L01 活体缺口是 FastEmbed 语义挤占。

## 根因
`search_terms` 把 `QA-GROK-2C2668E3` 拆成 qa/grok/2/c/2668/e/3。FastEmbed 对「容量和颜色」更接近材质/色差 SOP 和晴川 5L 话术，0.55 语义分压过残缺 BM25。

## 改动
`text_utils.product_identifiers` 保留连字符型号；`rag._score` 若问句型号出现在文档 question/answer/keywords/search_text 原文，加 0.2。无型号问句不加分。

## 证据
- 错误截图：`error.png`
- 成功截图：`success.png`
- 红态：`red.txt`（FastEmbed 第一名 seed-0007）
- 实现者绿态（不算验收）：`green.txt`
- live 原文：`before-l01-browser.json`
- 独立审查：`../../reviews/L01-review.md` — **PASS**（工作区 4 passed；/tmp 反证去掉 identifier_bonus 后 FastEmbed 第一名仍是 seed-0007 0.8465）
- 原审查合同是 FastEmbed retrieve top-1；2026-09-11 已补 live 成文，见下节

实现者自测不算通过。独立审查 PASS 不等于 live 成文已修好。
## 2026-09-11 live LLM

只报 QA-GROK-2C2668E3 问容量和颜色。答 5L / 米白，未推 AF50。合成资料第一名 0.9696。证据 `after-live.json`。不改原独立审查合同。
