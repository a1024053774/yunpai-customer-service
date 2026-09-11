# 2026-09-11 验收判定修复

这轮修复针对验收探针，不覆盖原始运行证据。原始证据仍保留在
`docs/testing/run-20260911-direction-audit/`，本目录只记录修正版判定和可复现的
红证据。

## 红证据

运行：

```text
./.venv/bin/python docs/testing/run-20260911-key-fixes/oracle_red_evidence.py
```

结果见 `oracle-red-evidence.json`。这是 6 类验收合同下的 7 个探针场景：它用最弱响应
构造出历史探针会判定为绿、但修正版必须判定为 `INCOMPLETE` 的场景，包括视觉错误状态、
缺失 message id、只返回 `intent_method=model`、只返回导入数量、忽略 UI/admin 标记、
无效 PDF 静默回退，以及回滚后缺少知识后态。

## 重判

运行：

```text
PYTHONPATH=docs/testing/run-20260911-key-fixes \
  ./.venv/bin/python docs/testing/run-20260911-key-fixes/rejudge_historical.py
```

结果见 `rejudged-verdict.json`。它只读历史运行文件，不覆盖历史结果。历史运行没有提供
PDF 夹具生成状态和回放 JSON，因此相应切片明确保持 `false`；总裁定为 `NO_GO`。

## 修复规则

1. 视觉必须是 `vision_status=applied`，并带非空模型名和单张图片计数。
2. 幂等回放必须是两个 200 JSON 对象，且有相同的非空 `message_id`；两次请求的幂等键、租户和请求内容也必须相同。
3. 多轮和语义路由必须声明预期意图、事实词和锚定答案契约，并对完整答案做匹配；只有 `intent_method=model`、文本有任意差异或追加无关内容都不够。
4. 导入必须核对返回文件名、条目数量、唯一且非空条目 ID，并逐条绑定租户、来源、版本和 active 后态。
5. UI 与 admin 的前置条件分别核验；HTTP 200 不代表页面能力存在。
6. PDF 夹具生成失败必须停在 `INCOMPLETE/BLOCKED`，不能写入伪 PDF 继续测试。
7. 回滚必须同时核对 API 后态和 SQLite 后态，知识版本必须是 retired 且不再出现在 active 列表。

这些规则修正的是验收证据的可信度；视觉真实上游仍返回过 `vision_status=error`，所以
不能把它升级成视觉能力通过。
