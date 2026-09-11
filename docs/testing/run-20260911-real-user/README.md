# 真实 DeepSeek 用户流程

执行器：本机 `.venv` + `env.md` 中的 DeepSeek 配置；真实 Key 只从环境读取，不写入证据。
数据目录：隔离的 `/private/tmp`，没有写入仓库 `data/`。

## 结果

- TXT、Markdown、PDF：均真实导入成功，HTTP 200。
- C01：真实 `deepseek-v4-flash` 完成首问和“这个颜色是什么”追问；两轮都回答同一商品“海盐白、6L”，第二轮 trace 含 `retrieve:contextual`，`intent_method=model`、`model_fallback=false`。
- L04：真实用户流程完成 feedback → evaluate → approve → rollback；回滚后 active knowledge 列表移除进化版本，candidate API 返回 `rolled_back`。
- 视觉修复前：真实 `deepseek-v4-flash-vision-exp` 三次均 HTTP 200 但 `vision_status=error`，上游响应只有 `reasoning_content`，`message.content` 为空。
- 视觉修复后：同一图片三次真实请求均 `vision_status=applied`，返回了图片内容描述。

## 证据

- `result.json`：导入、C01、视觉首次真实流程和 L04 后态。
- `vision-repeat-v2.json`：视觉修复后的三次真实请求。
- `vision-diagnostic.json`：视觉修复前上游 HTTP 200 空 content 诊断（如生成）。

K04 崩溃恢复、跨进程/SSE 完整幂等仍为待办，不在本次本机正常流程中宣称完成。
