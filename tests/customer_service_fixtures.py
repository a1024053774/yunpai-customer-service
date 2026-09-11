"""`customer_service` 模块独立测试的构建辅助：全部不经 AgentService。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from yunpai_customer_service.auth import AuthenticationService, Principal
from yunpai_customer_service.config import Settings
from yunpai_customer_service.customer_service import CustomerServiceCore
from yunpai_customer_service.database import Database
from yunpai_customer_service.knowledge_seed import seed_records

from conftest import make_settings


# 测试数据显式虚拟标记（CONTRIBUTING 第 6 节：不混进真实业务数据集）
FIXTURE_MARKER = "虚拟测试商品"

TABLE_MODEL_ANSWER = "表驱动替身模型的固定回复，仅用于验收。"


class TableDrivenModel:
    """表驱动模型替身：按 prompt 载荷的 `task_type` 取固定结果。

    D-034 mock 纪律：不得复刻生产的关键词语义路由。这里的分派键是 prompt 载荷的
    结构字段，不解读用户原文；未登记的 task_type 直接 KeyError 暴露。
    """

    def __init__(
        self,
        settings: Settings,
        *,
        intent: str = "product_inquiry",
        decision_mode: str = "answer",
        decision_intent: str = "product",
        answer: str = TABLE_MODEL_ANSWER,
    ):
        self.settings = settings
        self.answer = answer
        self.generation_prompts: list[list[dict[str, str]]] = []
        self.json_tasks: list[str] = []
        self._table: dict[str, dict[str, Any]] = {
            "intent_classification": {
                # 真实模型可能把结果套信封，替身保持同样形状
                "answer": {"intent": intent, "confidence": 0.82}
            },
            "agent_decision": {
                "intent": decision_intent,
                "mode": decision_mode,
                "tool_name": None,
                "arguments": {},
                "missing_fields": [],
                "expected_outcome": None,
                "response": None,
                "reason": "table_driven_decision",
                "confidence": 0.9,
            },
        }

    def generate_json(
        self,
        messages: list[dict[str, str]],
        **_kwargs: Any,
    ) -> dict[str, Any]:
        task = str(json.loads(messages[-1]["content"])["task_type"])
        self.json_tasks.append(task)
        return dict(self._table[task])

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.generation_prompts.append(messages)
        return self.answer

    def stream_generate(self, messages: list[dict[str, str]]) -> Iterator[str]:
        self.generation_prompts.append(messages)
        yield self.answer

    def close(self) -> None:
        return None


def build_core(
    data_dir: Path,
    *,
    settings: Settings | None = None,
    model: Any | None = None,
    seed_knowledge: bool = True,
) -> CustomerServiceCore:
    """只用 db + settings（+ 可选替身模型）装配客服模块。"""
    settings = settings or make_settings(data_dir)
    settings.ensure_directories()
    db = Database(settings.app_db_path)
    db.initialize()
    core = CustomerServiceCore.build(db, settings, model=model)
    if seed_knowledge:
        core.knowledge.seed_if_empty(seed_records())
    core.handoffs.ensure_default_queues(settings.bootstrap_tenant_id)
    return core


def principal_for_core(core: CustomerServiceCore, subject_id: str = "buyer-1") -> Principal:
    auth = AuthenticationService(core.db, core.settings)
    return auth.authenticate(
        core.settings.bootstrap_client_id,
        core.settings.bootstrap_client_key,
        subject_id,
    )


def add_fixture_document(
    core: CustomerServiceCore,
    *,
    question: str,
    answer: str,
    tenant_id: str,
    intent: str = "product",
    source: str = "fixture:customer-service-module",
    keywords: str | None = None,
) -> str:
    return core.knowledge.add_document(
        category="虚拟验收知识",
        intent=intent,
        question=question,
        answer=answer,
        keywords=keywords or question,
        risk_level="low",
        source=source,
        tenant_id=tenant_id,
    )


def internal_session_id(core: CustomerServiceCore, external_session_id: str) -> str:
    with core.db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE external_session_id=?",
            (external_session_id,),
        ).fetchone()
    assert row is not None, external_session_id
    return str(row[0])


def stream_answer(events: list[dict[str, Any]]) -> str:
    return "".join(event["text"] for event in events if event["event"] == "delta")
