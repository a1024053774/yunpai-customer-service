# 当前候选交付范围与待测门禁

更新日期：2026-09-11

## 当前可以交付的形式

当前候选只作为**限定范围的本机内部试用版**交付，范围是：

- 本机客服问答；
- DeepSeek 文本模型与已修复的真实视觉请求；
- 本地 PDF/TXT/Markdown 知识导入与检索；
- 普通同步对话；
- 已验证的同进程同键并发幂等切片。

依据：

- 完整回归：`120 passed, 10 warnings`，见 [`run-20260911-final/full-pytest.log`](runs/run-20260911-final/full-pytest.log)；
- 真实模型导入、C01 同对象追问、L04 API 回滚和视觉重复请求，见 [`run-20260911-real-user/`](runs/run-20260911-real-user/)；
- 同进程幂等切片与反例，见 [`run-20260911-k04-at-most-once/`](runs/run-20260911-k04-at-most-once/)；
- 当前代码结构图的 Archify 验证、交付和视觉检查，见 [`run-20260911-final/`](runs/run-20260911-final/)。

## 正式发布前必须完成的待测项

| 门禁 | 当前状态 | 必须补的证据 |
|---|---|---|
| C01 多轮纠正对象切换 | `INCOMPLETE` | 产品 A → 颜色追问 → 明确纠正到产品 B → 后续追问，证明检索、回答和 sources 全部切换到 B |
| L04 页面/API/数据库一致性 | `INCOMPLETE` | 文件选择器、导入、查看、下载、评测、批准、回滚全链路；页面状态、API 状态和 SQLite 后态逐步对账 |
| K04 崩溃恢复 | `INCOMPLETE` | invocation 处于 running 时进程退出，重启后证明恢复/重试完成且响应只持久化一次 |
| K04 跨进程与同步/SSE 交叉幂等 | `INCOMPLETE` | 独立进程 owner、同步与 SSE 交叉重放、真实工具副作用账本均证明至多一次 |

以上四项沿用当前验收结论，不能被 `120 passed`、局部真实模型成功或结构图通过替代。正式生产发布仍为 **NO_GO / INCOMPLETE**。
