# 执行边界

- 目标：对照原始 Codex 目标和 handbook 10.2，在当前 dirty 候选上完成本机最小 live 行为验收。
- 非目标：不改产品源代码、测试、Skill、CASES/INDEX/README/历史审查；不提交、建分支、推送、生产写入或新登录；不调用 Cursor Desktop/Orca。
- 执行器：当前本地工作区 `.venv`，回环 Demo + host API，隔离 SQLite；DeepSeek 仅按已有 `env.md` 配置调用，密钥不入证据。
- 停止条件：凭据暴露、工作区数据写入、生产写入、隔离破坏、进程不稳定或费用/配额异常。
- 判据：真实响应、SQLite/文件后态和源码调用链分别记录；命名切片不能关闭完整目标，缺少 L4/L5/成本/独立审查证据保持 NO_GO/INCOMPLETE。
