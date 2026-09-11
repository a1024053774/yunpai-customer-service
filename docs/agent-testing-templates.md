# Agent 测试执行与交付模板

配套规范：[Agent 产品完整测试手册](agent-testing-manual.md)。版本 1.0，2026-09-10。

每次执行复制所需模板到独立证据目录。保留失败、重试和变更记录，不覆盖上次结果。空白字段表示待填写，不能默认为通过。本文示例不会自动执行测试，也没有授予生产写入或付费调用授权。

## 1. 测试计划与候选冻结

```text
计划 ID：
负责人 / 独立验收人 / 业务真值确认人：
开始时间 / 计划结束时间 / 时区：
交付版本与范围：
用户群、租户、渠道、业务域：
承诺的回答 / 工具 / 资料 / 记忆 / 经验发布能力：
明确排除能力，以及关闭入口的验证方式：

代码 HEAD：
未提交 diff 摘要 / 未跟踪源码文件清单与摘要：
构建包或镜像 ID：
实际加载版本、进程启动时间与监听地址：
数据库 schema / 数据集版本 / 知识版本：
配置摘要（仅白名单，不含密钥）：
模型配置名 / 实际返回模型标识 / 提供方 / 时间窗口：
prompt / SOP / 工具目录版本：
embedding provider / 模型版本 / 维度 / 索引版本：
解析器版本 / OCR 模型 / 依赖清单摘要：
浏览器与操作系统：

用例集版本 / 开发-回归-封存集合划分 / 随机种子：
适用环境层级 L0-L5：
隔离数据目录 / 测试账号来源 / 沙箱业务对象：
允许访问的服务与付费预算：
可能影响既有数据的操作与隔离方法：
停止阈值 / 故障处置人 / 恢复方案：
尚缺的资料、规则、凭据或环境及责任人：
```

### 1.1 范围与证据追踪表

| 能力承诺 | 业务规则/真值来源 | 手册用例 ID | 必需层级 | 自动化入口/人工步骤 | 本次结果 | 证据 | 责任人 |
|---|---|---|---|---|---|---|---|
| 示例：售后条件咨询 | 已确认政策 v1 页 2 | B01、G07 | L2/L3 | 实际模型与页面提问 | NOT_RUN | 待补 | 待填 |
| 示例：经验发布 | 审批权限矩阵 v1 | F03–F09 | L1/L3/L4 | 直接接口与完整审批 | NOT_RUN | 待补 | 待填 |

不得用一条 happy path 代表整行能力。范围包含新版本策略时，须把相关用例拆成实际可执行 trial。

### 1.2 权限与事实矩阵

| 主体/角色 | 租户/店铺/顾客 | 可读资源 | 可写/审批动作 | 明确禁止 | 身份由谁确认 | 验收 ID |
|---|---|---|---|---|---|---|
| 测试顾客 A1 | T-A/S-A1/U-A1 | 自己的授权资料 | 普通反馈 | 他人订单、审批 | 网站后端 | 待填 |
| 测试审批人 | T-A | 指定候选与来源 | 经授权发布/回滚 | T-B 候选 | 服务端认证 | 待填 |

| 事实 ID | 来源文件摘要/版本 | 页码/行/单元格 | 原子事实及适用条件 | 不允许推断 | 生效/失效时间 | 确认人 |
|---|---|---|---|---|---|---|
| FACT-001 | 待填 | 待填 | 测试产品容量 5L，仅 T-A/S-A1 | 不可推断库存、销量 | 待填 | 待填 |

## 2. 单用例卡

```text
用例 ID / 标题：
来源：历史缺陷 / 新需求 / 风险 / 生产反馈
需求 ID / 业务合同或真值：
优先级：P0 / P1 / P2 / P3
适用范围与环境层级：
候选摘要 / 运行 ID / trial ID：

前置条件：
- 身份、权限、租户/店铺/顾客、会话初始状态：
- 文档、知识、模型、工具、外部账本初始状态：
- 功能开关与已知限制：

输入：
- 用户原话、图片/文件摘要、可信上下文、请求参数：
- 非可信内容及其来源：
- idempotency key / 业务对象 ID（仅测试数据）：

操作步骤：
1.
2.
3.

预期用户行为与可接受答案集合：
必须出现的事实/字段/动作：
禁止出现的事实/字段/动作：
预期节点、工具及副作用计数：
预期数据库/文件/外部业务状态：
独立判据及核验人：

错误实现反例：
该用例为什么能拒绝这个错误实现：

实际用户结果：
实际执行与后置状态：
耗时 / token / 成本 / 重试次数：
命令或操作记录 / 退出码：
证据文件及摘要：
结果：NOT_RUN / PASS / FAIL / BLOCKED / INCOMPLETE / N/A
缺陷 ID / 阻塞条件 / N/A 理由：
清理与恢复结果：
执行人 / 复核人 / 时间：
```

### 2.1 完整示例：能否绕过真实图节点

| 字段 | 示例内容 |
|---|---|
| 用例 | A01，L1，P1；以下仅为计划，不是结果 |
| 前置 | 隔离候选与临时库；固定结构模型；正常通过审核的安全哨兵 |
| 操作 | 构建前包装真实 generate/verify；同步与 SSE 各新建一个会话；记录计数、最终响应与消息表 |
| 预期 | 两条路径均实际执行注册节点；正常分支输出包含本轮安全哨兵；落库内容等于用户最终内容 |
| 反例 | 图外自行生成、伪写 verify trace；目标断言应因节点计数/哨兵缺失而失败 |
| 限制 | 固定模型不能证明自然语言理解；core 用例不能证明实际 HTTP 传输 |
| 当前状态 | NOT_RUN |

## 3. 缺陷与红绿证据

```text
缺陷 ID / 标题 / 等级：
影响用户、入口、数据/权限范围：
发现版本 / 复现环境 / 原始 run-case-trial：
违背的业务或技术合同：

最小复现：
1. 初始状态：
2. 原始输入与操作：
3. 预期：
4. 实际：

修改前命令 / 时间 / 退出码：
修改前日志、请求、截图、节点记录、账本读回：
为什么是该缺陷，而非环境/夹具错误：

根因位置与直接调用者：
修复概要与影响边界：
修复版本/文件摘要：
同一复现修复后命令 / 时间 / 退出码：
修复后用户结果与持久化/外部状态：
相关回归范围与结果：
独立复核结果与回执：

若修复先于复现：使用的旧版本或定向变异：
该反事实是否因目标行为断言失败：
无法恢复红态时的限制（不得写已证明回归有效）：
关闭人 / 关闭条件 / 剩余风险：
```

如果测试样例本身坏了，例如 PDF 字体损坏，应记录为夹具缺陷；不要把修复样例字体描述成解析器解决了任意坏字体问题。

## 4. 反例/变异实验记录

| 字段 | 填写内容 |
|---|---|
| 目标用例 | 待填 |
| 冻结副本摘要 | 待填 |
| 已知错误行为 | 固定回答 / 去掉租户过滤 / 跳过 verify / 总成功 / 其他 |
| 最小变异差异 | 待填，不能修改无关代码 |
| 预期失败断言 | 待填 |
| 实际命令与退出码 | 待填 |
| 失败原因是否正确 | 是/否；环境或导入错误不算识别成功 |
| 原实现恢复后结果 | 待填 |
| 原工作区/数据完整性 | 待填 |
| 结论 | NOT_RUN / REJECTED_BAD_IMPLEMENTATION / TEST_GAP / INCOMPLETE |

不要求每个文案或 UI 样式变更做变异；图、权限、关键副作用和测试可信度是优先对象。

## 5. 真实模型评测记录

### 5.1 Trial 数据格式示例

建议每次尝试保存一条 JSON；字段可按项目扩充。下例用合成标识，所有 null 均为待执行，不表示零失败。

```json
{
  "run_id": "RUN-YYYYMMDD-001",
  "case_id": "B01",
  "trial_id": "B01-01",
  "status": "NOT_RUN",
  "environment_level": "L2",
  "candidate_digest": "TO_FILL",
  "dataset_version": "TO_FILL",
  "truth_ids": ["FACT-001"],
  "model_configured": "TO_FILL",
  "model_reported": null,
  "prompt_digest": "TO_FILL",
  "knowledge_version": "TO_FILL",
  "embedding_identity": "TO_FILL",
  "tenant_fixture": "T-A",
  "store_fixture": "S-A1",
  "subject_fixture": "U-A1",
  "request_digest": "TO_FILL",
  "trace_id": null,
  "observed_nodes": [],
  "observed_tool_calls": [],
  "retrieved_evidence_ids": [],
  "outcome_verified": null,
  "hard_boundary_passed": null,
  "task_success": null,
  "fact_correct_count": null,
  "fact_checked_count": null,
  "first_event_ms": null,
  "first_usable_answer_ms": null,
  "completion_ms": null,
  "model_fallback": null,
  "retry_count": null,
  "input_tokens": null,
  "output_tokens": null,
  "total_cost": null,
  "currency": "TO_FILL",
  "grader_version": "TO_FILL",
  "human_review": null,
  "evidence_paths": [],
  "defect_ids": []
}
```

不要把模型隐藏推理内容、密钥和客户原始敏感资料放入该记录。业务必需原始记录放受控目录，分享报告仅放脱敏摘要与受控引用。

### 5.2 评测汇总表

| 分桶 | 计划任务数 | 已执行任务/尝试数 | PASS | FAIL | BLOCKED/INCOMPLETE/NOT_RUN | 首次成功率 | k 次全通过比例 | 误拒/误放 | p95 耗时 | 完整任务成本 |
|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| 普通咨询 | 待填 | 待填 | 待填 | 待填 | 待填 | 分子/分母 | k 与分子/分母 | 待填 | 待填 | 待填 |
| 售后办理 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 多轮/图片 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 注入/越权 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

另附原始失败全集、各比例区间、模型裁判与人工分歧及处理决定。不得只给总体平均分或挑最好一次。

## 6. 性能、故障与恢复报告

```text
场景 / 候选 / 环境：
机器 CPU / 内存 / 磁盘 / 系统 / 网络：
依赖真实/替身清单：
知识量 / 文档类型与页数 / 索引版本：
请求组成 / 会话长度 / 文本图片比例 / 工具比例：
到达率 / 并发 / 持续时间 / 冷暖状态：
费用上限 / token 上限 / 停止阈值：

请求数 / 完整任务数 / 成功 / 失败 / 降级 / 超时：
首事件与可用答案及最终完成 p50/p95/p99：
吞吐 / 队列峰值 / 拒绝数 / 重试数：
CPU / 内存 / 线程 / FD / 数据库锁等待趋势：
模型和工具调用成本 / 失败及人工成本：

故障注入点 / 时间 / 预期：
故障中用户结果与账本：
恢复步骤 / 完成时间 / 积压清理时间：
消息、原件、图片、知识与调用记录是否一致：
备份时间 / 恢复点 / RPO 目标与实际 / RTO 目标与实际：
恢复后用户入口复验：
结果 / 缺陷 / 限制 / 责任人：
```

## 7. 证据目录与命令

### 7.1 推荐目录

```text
RUN-YYYYMMDD-001/
  plan.md
  manifest.json
  case-results.md
  commands/
    collection.log
    focused.log
    focused.exit
    focused.junit.xml
  cases/
    A01/trial-01/       # 输入、调用记录、响应、落库核对
    E01/trial-01/       # 原件摘要、逐页真值、解析与引用结果
  defects/
    BUG-001/red/
    BUG-001/green/
  evals/
    trials.jsonl
    summary.md
  browser/
  load-and-recovery/
  release-decision.md
```

运行日志与证据中的客户内容应受权限/保留期限约束。共享前脱敏，不能把整个 `env.md`、shell 环境或生产数据库打包。

### 7.2 保存现有专项测试结果

从仓库根目录在专用测试 shell 执行。这些命令只保存和运行现有测试；新增用例仍需逐项实现或人工执行。临时目录在终端变量中显示，交付前复制到团队约定的受控存储，不依赖系统临时目录长期保存。

```bash
TEST_EVIDENCE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/yunpai-acceptance-XXXXXX")"
export TEST_EVIDENCE_DIR
mkdir -p "$TEST_EVIDENCE_DIR/commands"

.venv/bin/python -m pytest --collect-only -q > "$TEST_EVIDENCE_DIR/commands/collection.log" 2>&1
collection_exit=$?
printf '%s\n' "$collection_exit" > "$TEST_EVIDENCE_DIR/commands/collection.exit"

.venv/bin/python -m pytest -q tests/test_framework_audit.py tests/test_api.py tests/test_intent.py --junitxml="$TEST_EVIDENCE_DIR/commands/focused.junit.xml" > "$TEST_EVIDENCE_DIR/commands/focused.log" 2>&1
focused_exit=$?
printf '%s\n' "$focused_exit" > "$TEST_EVIDENCE_DIR/commands/focused.exit"

printf 'Evidence directory: %s\nCollection exit: %s\nFocused exit: %s\n' "$TEST_EVIDENCE_DIR" "$collection_exit" "$focused_exit"
```

退出码为 0 仍要检查实际用例数、skip/xfail 和目标断言；这些命令没有运行真实模型评测。若用于 CI，最终作业必须传播失败状态，例如在脚本末尾添加 `test "$collection_exit" -eq 0 && test "$focused_exit" -eq 0`，不能让最后一个 printf 把失败掩盖成成功。

### 7.3 候选快照最小清单

以下 Python 片段只读取工作区并写入上一节创建的证据目录；不会读取 `env.md`、数据目录或密钥。它保存源码/测试/文档配置的摘要及 Git 状态，不包含可用于恢复 dirty 工作区的完整补丁。需复现实验时，另外安全归档冻结候选副本，不能只靠摘要重建。

```bash
.venv/bin/python - <<'PY'
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd()
out = Path(os.environ["TEST_EVIDENCE_DIR"])
paths = []
for folder in ("src", "tests", "docs"):
    paths.extend(p for p in (root / folder).rglob("*")
                 if p.is_file() and not p.is_symlink()
                 and p.suffix in {".py", ".json", ".html", ".md"}
                 and "__pycache__" not in p.parts)
paths.extend(root / name for name in ("pyproject.toml", "README.md", "env.example.md"))
files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(set(paths)) if p.exists()}
manifest = {
    "time_utc": datetime.now(timezone.utc).isoformat(),
    "python": platform.python_version(),
    "platform": platform.platform(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "git_status": subprocess.check_output(["git", "status", "--porcelain=v1"], text=True),
    "files_sha256": files,
    "product_tests_executed_by_this_snapshot": False
}
(out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(out / "manifest.json")
PY
```

记录实际模型、知识版本、端口和运行进程还需单独补充；该清单不能证明运行服务加载了这些文件。只读外部账本截图/导出也必须绑定同一个业务对象、时间和请求 ID。

## 8. 发布决定模板

```text
发布候选 / 摘要 / 时间：
允许交付的能力、用户、租户、渠道与流量范围：
明确关闭的能力及关闭证据：

计划适用用例数：
PASS / FAIL / BLOCKED / INCOMPLETE / NOT_RUN / N/A 数量：
所有状态之和是否与计划用例数一致：
P0/P1 缺陷是否全部关闭并在该候选复测：
历史 18 项问题映射与当前回归结果：
真实模型质量与分桶指标是否达到冻结目标：
实际网站/业务平台/人工接管是否完成必要层级验收：
负载、费用、恢复与数据治理是否达到冻结目标：
关键错误实现是否被测试拒绝：
独立验收回执与结论：

未完成/未测试清单：
P2/P3 风险接受（影响、期限、负责人、复测人）：
升级 / 回滚 / 备份 / 告警 / 值守资料位置：
发布后 smoke 与灰度停止条件：

决定：允许指定范围发布 / 拒绝发布 / 等待补齐证据
决定依据：
业务负责人：
技术负责人：
验收负责人：
运维/数据负责人（按范围）：
下一次复核时间与触发条件：
```

冻结候选之后又改代码、模型、知识或关键配置时，重新建立相关证据。不能把旧报告日期改成今天继续沿用。
