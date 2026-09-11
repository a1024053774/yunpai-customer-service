# C01 怎么修的

## 现象
Grok 4.6 live 同会话 `r2-d01exact-6cbd8a33`：第一轮已正确回答 QA-GROK-2C2668E3 为 5L / 米白；追问「这个颜色是什么」改问「哪款商品」，sources 变成 seed-0014/0007/0004。trace 有 `kept2`，历史到了生成，但检索没有带上上一轮。

## 根因
`graph.py` retrieve 只在**首次检索为空**时才拼上一轮用户问句。追问「这个颜色是什么」会命中通用颜色 FAQ / SOP，首次检索非空，上下文检索被跳过。

已有测试 `test_follow_up_retrieval_uses_the_previous_user_turn_when_needed` 用 `rag_min_score=0.3` 让首次检索为空，覆盖不到这条路径。

## 改动
`src/yunpai_customer_service/graph.py` retrieve：只要问句匹配 `_CONTEXT_REFERENCE_HINTS`，就取历史上一条**不同于当前问句**的用户消息，搜索 `{previous}\n{current}`；该搜索有命中则替换 documents，并打 `retrieve:contextual`。

## 证据
- 错误截图：`error.png`（live before HTML）
- 成功截图：`success.png`（focused contract after；替身模型，承诺 sources / contextual，不是 live 成文）
- 红态：`red.txt`
- 实现者绿态（不算验收）：`green.txt`、`green-memory-suite.txt`、`after-chat.json`
- live 原文：`before-live.json`、`before-d01-exact.json`
- 独立审查：`../../reviews/C01-review.md` — **PASS**（工作区 2 passed；/tmp 反事实在 product_id 不在追问 sources 处失败）
- 原审查合同不含 live 成文；2026-09-11 已补 live L3，见下节。success.png 仍是替身模型 dump

实现者自测不算通过。独立审查 PASS 不等于 live 成文已修好。
## 2026-09-11 live L3

同会话先 D01-exact 后问「这个颜色是什么」。答米白并点名 QA-GROK-2C2668E3。trace 有 retrieve:contextual 与 kept2。证据 `after-live.json`。不改原独立审查合同。
