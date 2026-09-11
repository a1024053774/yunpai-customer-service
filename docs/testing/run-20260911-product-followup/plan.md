# product-followup plan

- 目标：在 K05 `api.py` 漂移后的当前 dirty 候选上继续产品验收；冻结新 digest；按手册 10.2 重判。
- 非目标：不修改任何 Skill；不修改历史审查原件；不写生产、不猜凭据、不新登录；不提交/建分支/推送。
- 验收条件：新 digest 含当前 `api.py`；优先项有原始证据；K05-host-500 不冒充完整 K05；K11/K06 framework 从 L4 桶拆出并实跑；L04 用 Cursor 侧边 Browser；B01 不继承旧 PASS；I08/K01-sse 按手册重判；结论为 NO_GO/完整 10.2 之前不能 GO。
- 未知：侧边 Browser 是否有 tab；第二 host client 是否能在活进程 sqlite 插入；费用字段是否可知。

不把 109 pytest、检索-only、旧报告或关键词 checker 当产品 GO。
