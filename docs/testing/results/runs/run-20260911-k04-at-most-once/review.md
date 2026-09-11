# 独立定向复核

结论：**INCOMPLETE（切片有效，整行未关闭）**。

- 当前代码在 `running && last_error is null` 时等待 owner，不重复进入 graph。
- 已知 `last_error` 会走重试路径。
- `evidence-v4` 的 counterfactual 红态为退出 1、`generate_calls=2`；修复后绿态为退出 0、`generate_calls=1`。
- 完整 response、`response_json`、消息计数和相同 `message_id` 均被核对。
- `evidence-v4/pytest-targeted.log` 保存了 33 个相关测试通过和退出码 0；
  `evidence-v4/pytest-full.log` 保存了当前候选完整套件 117 passed、10 warnings、退出码 0。

保留未关闭边界：进程崩溃遗留 `running`、跨进程 ownership、SSE 交叉重放、完整业务副作用账本，以及完整 K04 手册行。
