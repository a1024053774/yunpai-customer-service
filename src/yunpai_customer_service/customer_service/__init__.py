"""智能客服模块：对话、记忆、话术匹配与自沉淀的可复用封装。

叶子能力（rag / evolution / intent / policy / graph / context_builder / tokens）
与本门面同包分发，供其他项目直接安装使用。
"""

from __future__ import annotations

from .core import CustomerServiceCore
from .generation import (
    BRANCH_APPROVED_DIRECT,
    BRANCH_MODEL,
    BRANCH_NO_EVIDENCE,
    NO_EVIDENCE_DRAFT,
    GenerationPlan,
    approved_direct_document,
    budgeted_history,
    context_budgets,
    map_scene,
    plan_generation,
    verified_tool_result,
)

__all__ = [
    "BRANCH_APPROVED_DIRECT",
    "BRANCH_MODEL",
    "BRANCH_NO_EVIDENCE",
    "NO_EVIDENCE_DRAFT",
    "CustomerServiceCore",
    "GenerationPlan",
    "approved_direct_document",
    "budgeted_history",
    "context_budgets",
    "map_scene",
    "plan_generation",
    "verified_tool_result",
]
