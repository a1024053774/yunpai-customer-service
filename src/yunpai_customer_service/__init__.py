"""Yunpai 智能客服：对话、记忆、话术匹配与自沉淀。"""

from .customer_service import (
    BRANCH_APPROVED_DIRECT,
    BRANCH_MODEL,
    BRANCH_NO_EVIDENCE,
    NO_EVIDENCE_DRAFT,
    CustomerServiceCore,
    GenerationPlan,
    approved_direct_document,
    budgeted_history,
    context_budgets,
    map_scene,
    plan_generation,
    verified_tool_result,
)

__version__ = "0.1.0"

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
