"""智能客服模块的记忆（会话历史 / 上下文预算 / 会话隔离）独立验收。"""

from __future__ import annotations

from dataclasses import replace

from yunpai_customer_service.customer_service import BRANCH_MODEL, plan_generation

from conftest import make_settings
from customer_service_fixtures import (
    FIXTURE_MARKER,
    TableDrivenModel,
    add_fixture_document,
    build_core,
    internal_session_id,
    principal_for_core,
)


FIRST_TURN = f"{FIXTURE_MARKER}的清洁方式"
SECOND_TURN = f"{FIXTURE_MARKER}的收纳方式"
THIRD_TURN = f"{FIXTURE_MARKER}的保养周期"


def _core_with_shared_document(data_dir, *, settings=None):
    settings = settings or make_settings(data_dir)
    model = TableDrivenModel(settings)
    core = build_core(data_dir, settings=settings, model=model)
    add_fixture_document(
        core,
        question=f"{FIXTURE_MARKER}的清洁、收纳与保养",
        answer="清洁用中性清洁剂，收纳前彻底晾干，保养按季度检查一次。",
        tenant_id=settings.bootstrap_tenant_id,
        keywords="清洁 收纳 保养 方式 周期",
    )
    return core, model


def test_multi_turn_history_reaches_the_generation_prompt(tmp_path) -> None:
    core, model = _core_with_shared_document(tmp_path)
    try:
        principal = principal_for_core(core)
        core.chat(principal, "memory-multi-turn", FIRST_TURN)
        core.chat(principal, "memory-multi-turn", SECOND_TURN)

        latest_prompt = model.generation_prompts[-1][-1]["content"]
        assert SECOND_TURN in latest_prompt
        assert "清洁方式" in latest_prompt
    finally:
        core.close()


def test_small_context_budget_drops_the_oldest_turn(tmp_path) -> None:
    generous_core, generous_model = _core_with_shared_document(tmp_path / "generous")
    tight_settings = replace(
        make_settings(tmp_path / "tight"),
        model_context_limit_tokens=600,
    )
    tight_core, tight_model = _core_with_shared_document(
        tmp_path / "tight", settings=tight_settings
    )
    try:
        for core in (generous_core, tight_core):
            principal = principal_for_core(core)
            for message in (FIRST_TURN, SECOND_TURN, THIRD_TURN):
                core.chat(principal, "memory-budget", message)

        generous_prompt = generous_model.generation_prompts[-1][-1]["content"]
        tight_prompt = tight_model.generation_prompts[-1][-1]["content"]

        assert "清洁方式" in generous_prompt
        assert "收纳方式" in generous_prompt
        # 预算收紧后最旧一轮被截断，最近一轮仍在
        assert "清洁方式" not in tight_prompt
        assert "收纳方式" in tight_prompt

        tight_meta = plan_generation(
            {
                "session_id": internal_session_id(tight_core, "memory-budget"),
                "normalized_input": THIRD_TURN,
                "intent": "product",
                "retrieved": [
                    {
                        "id": "kb-fixture-budget",
                        "intent": "product",
                        "category": "虚拟验收知识",
                        "question": THIRD_TURN,
                        "answer": "保养按季度检查一次。",
                        "source": "fixture:customer-service-module",
                        "version": 1,
                        "score": 0.5,
                    }
                ],
                "context_bundle": {},
                "tool_result": {},
                "decision": {"reason": "knowledge_answer_allowed"},
                "intent_routing": {},
            },
            settings=tight_core.settings,
            db=tight_core.db,
        )
        assert tight_meta.branch == BRANCH_MODEL
        assert (tight_meta.history_meta or {})["dropped"] >= 1
        assert (tight_meta.history_meta or {})["kept"] >= 1
    finally:
        generous_core.close()
        tight_core.close()


def test_history_does_not_leak_between_sessions(tmp_path) -> None:
    core, model = _core_with_shared_document(tmp_path)
    try:
        principal = principal_for_core(core)
        core.chat(principal, "memory-session-a", FIRST_TURN)
        core.chat(principal, "memory-session-b", SECOND_TURN)

        latest_prompt = model.generation_prompts[-1][-1]["content"]
        assert SECOND_TURN in latest_prompt
        assert "清洁方式" not in latest_prompt
    finally:
        core.close()
