# run-20260911-direction-audit 结果摘要

结论：**NO_GO / INCOMPLETE**。原始产品方向继续保持：本机客服工作台、DeepSeek Flash 意图/回答、FastEmbed/BM25/SQLite 本地检索、多轮、图片入口、资料导入和受控经验沉淀都存在可运行实现；本轮没有证据支持把它升级为 10.2 完整交付。

本轮独立回环服务使用当前工作区 `.venv` 和隔离 `DATA_DIR=/private/tmp/yunpai-direction-audit-20260911-rerun1`，Demo `127.0.0.1:58722`、host API `127.0.0.1:58723`，实际模式为 live DeepSeek `deepseek-v4-flash`，视觉配置为 `deepseek-v4-flash-vision-exp`，检索为 FastEmbed `BAAI/bge-small-zh-v1.5`、BM25、SQLite。云模型可能收费，但响应没有 token/cost 字段，费用记为 **unknown**；本地检索没有发现收费向量库依赖。

本轮结果：

- **已证明的本机切片**：FastEmbed/BM25/SQLite 检索；TXT/Markdown/PDF 导入形成来源、版本、租户和 embedding 后态；同一 session 多轮追问；一个歧义问题由模型路径返回澄清；一个非关键词问法走模型意图并检索；host API 认证调用及相同幂等键重放；自进化 API/SQLite 的 evaluate→approve→rollback 后态。
- **仅切片或 INCOMPLETE**：文本/视觉配置与文本调用已见，但视觉请求本次 `vision_status=error`，未证明成功识图；图片目标、歧义识别、非关键词路由、语料库和自进化页面一致性都只有命名样本或 API/SQLite 切片。
- **本轮仍未满足的 10.2 边界**：L3 仍是本机回环 HTTP/页面切片；L4/L5 真实认证网关、渠道、沙箱/生产业务账本和生产灰度；独立站真实接入；HR 真实资料/SOP/eval；真实反代；clean wheel/image runtime；8h soak、崩溃恢复与长稳；真实成本门禁。

现有 `CASES.json`、follow-up verdict、freeze-after-k04 和历史审查文件均只作输入，未被修改；pytest/旧报告/UI 标签未被当作产品 GO。服务已停止，端口清理状态记录在 `cleanup.json`。

详见 `direction-matrix.json`、`raw/probe-results.json`、`states/knowledge-after-import.json`、`states/evolution-after.json` 和 `raw/10.2-remaining.json`。
