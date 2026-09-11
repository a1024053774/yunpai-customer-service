"""智能客服模块的记忆（会话历史 / 上下文预算 / 会话隔离）独立验收。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from yunpai_customer_service.customer_service import BRANCH_MODEL, plan_generation
from yunpai_customer_service.database import Database

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


def test_follow_up_retrieval_uses_the_previous_user_turn_when_needed(tmp_path) -> None:
    settings = replace(make_settings(tmp_path), rag_min_score=0.3)
    model = TableDrivenModel(settings)
    core = build_core(
        tmp_path, settings=settings, model=model, seed_knowledge=False
    )
    try:
        document_id = add_fixture_document(
            core,
            question=f"{FIXTURE_MARKER}的保修政策是什么",
            answer=f"{FIXTURE_MARKER}提供十二个月保修，具体范围按商品说明核对。",
            tenant_id=settings.bootstrap_tenant_id,
            keywords=f"{FIXTURE_MARKER} 保修 质保 十二个月",
        )
        principal = principal_for_core(core)

        first = core.chat(
            principal, "memory-contextual-retrieval", f"{FIXTURE_MARKER}的保修政策是什么"
        )
        follow_up = core.chat(
            principal, "memory-contextual-retrieval", "那这个呢？"
        )

        assert document_id in {item.id for item in first.sources}
        assert document_id in {item.id for item in follow_up.sources}
        assert "retrieve:contextual" in follow_up.trace
    finally:
        core.close()


def test_color_follow_up_uses_previous_product_when_generic_color_docs_also_match(
    tmp_path,
) -> None:
    # C01: "this color?" still retrieves generic color FAQs (score > min_score),
    # so contextual retrieval must not wait for an empty first search.
    color_follow_up = "\u8fd9\u4e2a\u989c\u8272\u662f\u4ec0\u4e48"
    product_name = "QA-FIX-C01"
    settings = replace(make_settings(tmp_path), rag_top_k=1)
    model = TableDrivenModel(settings)
    core = build_core(
        tmp_path, settings=settings, model=model, seed_knowledge=False
    )
    try:
        product_id = add_fixture_document(
            core,
            question=f"{product_name} \u5b64\u5c9b\u9a8c\u6536\u58f6\u7684\u5bb9\u91cf\u548c\u989c\u8272",
            answer=f"{product_name} \u5bb9\u91cf 5L\uff0c\u989c\u8272\u7c73\u767d\u3002",
            tenant_id=settings.bootstrap_tenant_id,
            keywords=f"{product_name} \u5bb9\u91cf \u989c\u8272 \u7c73\u767d 5L",
        )
        generic_id = add_fixture_document(
            core,
            question=color_follow_up,
            answer="\u4e0d\u540c\u5546\u54c1\u989c\u8272\u4e0d\u540c\uff0c\u8bf7\u63d0\u4f9b\u5546\u54c1\u540d\u79f0\u3002",
            tenant_id=settings.bootstrap_tenant_id,
            keywords="\u989c\u8272 \u5546\u54c1 \u770b",
        )
        principal = principal_for_core(core)
        session = "c01-color-followup"
        competing = core.knowledge.retrieve(
            color_follow_up,
            top_k=settings.rag_top_k,
            min_score=settings.rag_min_score,
            intent="product",
            tenant_id=settings.bootstrap_tenant_id,
        )
        assert any(item["id"] == generic_id for item in competing), (
            "follow-up query must already hit generic color docs"
        )
        assert all(item["id"] != product_id for item in competing)
        first = core.chat(
            principal,
            session,
            f"{product_name} \u5b64\u5c9b\u9a8c\u6536\u58f6\u7684\u5bb9\u91cf\u548c\u989c\u8272\u662f\u4ec0\u4e48",
        )
        follow_up = core.chat(principal, session, color_follow_up)
        follow_ids = {item.id for item in follow_up.sources}
        assert product_id in {item.id for item in first.sources}
        assert product_id in follow_ids
        assert "retrieve:contextual" in follow_up.trace
    finally:
        core.close()



def test_standard_knowledge_retrieval_does_not_mix_in_long_term_memory(
    tmp_path,
) -> None:
    core = build_core(tmp_path, seed_knowledge=False)
    try:
        assert core.memory is not None
        memory_id = core.memory.record(
            "store-memory-isolation",
            fact="本店退货高峰集中在周三。",
            tenant_id=core.settings.bootstrap_tenant_id,
        )

        documents = core.knowledge.retrieve(
            "本店退货高峰集中在周三",
            top_k=5,
            min_score=0.01,
            tenant_id=core.settings.bootstrap_tenant_id,
            store_id="store-memory-isolation",
        )

        assert memory_id not in {item["knowledge_key"] for item in documents}
    finally:
        core.close()


def test_long_term_memory_recall_uses_relevance_instead_of_full_sentence_like(
    tmp_path,
) -> None:
    core = build_core(tmp_path, seed_knowledge=False)
    try:
        assert core.memory is not None
        relevant_id = core.memory.record(
            "store-memory-ranking",
            fact="本店退货高峰集中在周三。",
            tenant_id=core.settings.bootstrap_tenant_id,
        )
        core.memory.record(
            "store-memory-ranking",
            fact="本店换货通常在周五完成。",
            tenant_id=core.settings.bootstrap_tenant_id,
        )

        recalled = core.memory.recall(
            "store-memory-ranking",
            query="退货最多是哪一天",
            limit=1,
            tenant_id=core.settings.bootstrap_tenant_id,
        )

        assert recalled[0]["knowledge_key"] == relevant_id
        assert recalled[0]["score"] > 0
    finally:
        core.close()


def test_buyer_preference_memory_is_scoped_to_the_authenticated_subject(
    tmp_path,
) -> None:
    core = build_core(tmp_path, seed_knowledge=False)
    try:
        assert core.memory is not None
        buyer_a = principal_for_core(core, "buyer-a")
        buyer_b = principal_for_core(core, "buyer-b")

        with pytest.raises(ValueError, match="subject_hash"):
            core.memory.record(
                "store-buyer-memory",
                fact="顾客偏好静音款。",
                category="buyer_preference",
                tenant_id=buyer_a.tenant_id,
            )
        with pytest.raises(ValueError, match="unsupported memory category"):
            core.memory.record(
                "store-buyer-memory",
                fact="顾客偏好静音款。",
                category="买家偏好",
                tenant_id=buyer_a.tenant_id,
            )

        preference_id = core.memory.record(
            "store-buyer-memory",
            fact="顾客偏好静音款。",
            category="buyer_preference",
            tenant_id=buyer_a.tenant_id,
            subject_hash=buyer_a.subject_hash,
        )
        shared_id = core.memory.record(
            "store-buyer-memory",
            fact="本店周末咨询量较高。",
            category="frequent_issue",
            tenant_id=buyer_a.tenant_id,
        )

        buyer_a_rows = core.memory.recall(
            "store-buyer-memory",
            tenant_id=buyer_a.tenant_id,
            subject_hash=buyer_a.subject_hash,
        )
        buyer_b_rows = core.memory.recall(
            "store-buyer-memory",
            tenant_id=buyer_b.tenant_id,
            subject_hash=buyer_b.subject_hash,
        )

        assert {row["knowledge_key"] for row in buyer_a_rows} >= {
            preference_id,
            shared_id,
        }
        assert preference_id not in {row["knowledge_key"] for row in buyer_b_rows}
        assert shared_id in {row["knowledge_key"] for row in buyer_b_rows}
    finally:
        core.close()


def test_subject_scoped_memory_survives_refined_retrieval_in_chat(tmp_path) -> None:
    settings = make_settings(tmp_path)
    model = TableDrivenModel(settings)
    core = build_core(
        tmp_path, settings=settings, model=model, seed_knowledge=False
    )
    try:
        assert core.memory is not None
        buyer_a = principal_for_core(core, "buyer-memory-owner")
        buyer_b = principal_for_core(core, "buyer-memory-other")
        memory_id = core.memory.record(
            "store-memory-chat",
            fact="顾客偏好静音款空气炸锅。",
            category="buyer_preference",
            tenant_id=buyer_a.tenant_id,
            subject_hash=buyer_a.subject_hash,
        )
        context = {"store_id": "store-memory-chat"}

        owner_response = core.chat(
            buyer_a, "memory-owner-chat", "静音款适合我吗？", context
        )
        other_response = core.chat(
            buyer_b, "memory-other-chat", "静音款适合我吗？", context
        )

        memory_source = f"memory:{memory_id}"
        assert memory_source in {item.source for item in owner_response.sources}
        assert memory_source not in {item.source for item in other_response.sources}
    finally:
        core.close()


def test_memory_is_redacted_before_storage_and_prompt_use(tmp_path) -> None:
    settings = make_settings(tmp_path)
    model = TableDrivenModel(settings)
    core = build_core(
        tmp_path, settings=settings, model=model, seed_knowledge=False
    )
    try:
        assert core.memory is not None
        principal = principal_for_core(core, "buyer-memory-redaction")
        memory_id = core.memory.record(
            "store-memory-redaction",
            fact="顾客偏好静音款，联系电话是 13812345678。",
            category="buyer_preference",
            tenant_id=principal.tenant_id,
            subject_hash=principal.subject_hash,
        )

        response = core.chat(
            principal,
            "memory-redaction-chat",
            "静音款适合我吗？",
            {"store_id": "store-memory-redaction"},
        )
        with core.db.connect() as conn:
            stored = conn.execute(
                "SELECT answer FROM knowledge WHERE knowledge_key=?",
                (memory_id,),
            ).fetchone()[0]

        assert "13812345678" not in stored
        assert "13812345678" not in model.generation_prompts[-1][-1]["content"]
        assert f"memory:{memory_id}" in {item.source for item in response.sources}
    finally:
        core.close()


def test_migration_retires_legacy_unscoped_buyer_preferences(tmp_path) -> None:
    core = build_core(tmp_path, seed_knowledge=False)
    try:
        legacy_id = core.knowledge.add_document(
            category="买家偏好",
            intent="memory-buyer_preference",
            question="顾客偏好静音款。",
            answer="顾客偏好静音款。",
            keywords="买家偏好 静音款",
            risk_level="low",
            source="memory://legacy",
            tenant_id=core.settings.bootstrap_tenant_id,
            knowledge_key="kg-memory-legacy-buyer",
            layer="evolution",
            store_id="store-legacy-buyer",
        )
        with core.db._write_lock, core.db.connect() as conn:
            Database._apply_v36(conn)
            row = conn.execute(
                "SELECT layer, status FROM knowledge WHERE id=?",
                (legacy_id,),
            ).fetchone()

        assert dict(row) == {"layer": "memory", "status": "retired"}
    finally:
        core.close()


def test_recording_an_expired_memory_renews_its_ttl(tmp_path) -> None:
    core = build_core(tmp_path, seed_knowledge=False)
    try:
        assert core.memory is not None
        memory_id = core.memory.record(
            "store-memory-renewal",
            fact="本店周三咨询量较高。",
            tenant_id=core.settings.bootstrap_tenant_id,
            ttl_days=1,
        )
        with core.db._write_lock, core.db.connect() as conn:
            conn.execute(
                "UPDATE knowledge SET effective_to='2000-01-01T00:00:00+00:00' "
                "WHERE knowledge_key=?",
                (memory_id,),
            )

        renewed_id = core.memory.record(
            "store-memory-renewal",
            fact="本店周三咨询量较高。",
            tenant_id=core.settings.bootstrap_tenant_id,
            ttl_days=30,
        )
        recalled = core.memory.recall(
            "store-memory-renewal",
            query="周几咨询量高",
            tenant_id=core.settings.bootstrap_tenant_id,
        )

        assert renewed_id == memory_id
        assert memory_id in {row["knowledge_key"] for row in recalled}
    finally:
        core.close()
