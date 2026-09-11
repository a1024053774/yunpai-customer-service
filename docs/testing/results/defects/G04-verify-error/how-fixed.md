# G04 怎么修的

审核 `review_output` 抛错时异常漏到 `core.chat` / SSE 调用方。草稿未外发，但没有分类降级。

## 根因

`verify_response` 与 `safe_terminal_output` 是 `review_output` 的直接调用方，却不翻译意外异常。`CustomerServiceCore.chat` 只记 `unhandled_error` 然后再抛出。

## 修复

在两个已有调用点捕获 `Exception`，返回已有安全文案和 `verify_error` / `terminal_output:error:<Type>`。不新增 wrapper 模块，不改 `review_output` 本身。

## 同信号

命令：`.venv/bin/python docs/testing/run-20260911-1024-grok46/g04/probe_g04.py {before,after}`

- before：`raised_to_caller=true`，`RuntimeError: forced_verify_timeout`，草稿未漏
- after：调用方得到安全回复；trace 含 `verify:error:RuntimeError`；落库 `route_reason=verify_error`；SSE 三帧均无表驱动草稿

实现者自测不算验收。独立审查见 `../../reviews/G04-review.md`。
