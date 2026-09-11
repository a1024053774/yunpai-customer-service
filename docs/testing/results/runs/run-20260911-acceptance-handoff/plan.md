# 验收接管计划

- 目标：从原始用户需求开始，复核当前 dirty 候选的客服 Agent；覆盖真实入口、知识导入、意图、多轮、图片、歧义、路由、自进化、权限/安全、SSE、恢复和可用的发布边界；逐项保留证据。
- 非目标：不写生产、不猜凭据、不把缺账号/缺外部账本/缺独立站当 PASS；Skill 评估完成前不改 Skill。
- 门禁：手册 10.2；适用 P0/P1 必须 PASS，修复项必须先红后绿并由脱离上下文的 Grok 4.6 复核。
- 执行入口：Orca 中当前 Cursor Agent CLI；每条轨道独立 DATA_DIR/端口/证据目录。
- 当前基线：HEAD 8ea1329e + dirty tree；历史账本 161 cases，75 PASS、12 REVIEW_PASS、38 INCOMPLETE、20 BLOCKED、16 NOT_RUN、NO_GO。
- 停止线：凭据外泄、生产/非测试副作用、数据污染、服务无法隔离；保存现场后标 BLOCKED/INCOMPLETE。
- 完成顺序：冻结 -> 从头回归 -> 新发现登记 -> Skill 评估 -> 若授权则修 Skill -> 产品逐项修复 -> 每项 detached review -> 最终 verdict。
