"""L04: management API must expose rollback state consistently with knowledge state."""
from __future__ import annotations

from customer_service_fixtures import build_core, principal_for_core
from yunpai_customer_service.schemas import FeedbackRequest


def test_candidate_list_marks_rolled_back_knowledge_as_rolled_back(tmp_path) -> None:
    core = build_core(tmp_path, seed_knowledge=True)
    try:
        principal = principal_for_core(core)
        answer = core.chat(principal, "l04-rollback", "虚拟测试商品的清洁方式")
        submitted = core.evolution.submit_feedback(
            FeedbackRequest(
                message_id=answer.message_id,
                rating=-1,
                corrected_answer="虚拟测试商品应使用中性清洁剂。",
                note="L04 rollback state contract",
                submitted_by="l04-test",
                evidence_source="fixture:l04",
            ),
            tenant_id=principal.tenant_id,
        )
        evaluated = core.evolution.evaluate(
            submitted.candidate_id, tenant_id=principal.tenant_id
        )
        assert evaluated.gate_passed is True
        approved = core.evolution.approve(
            submitted.candidate_id,
            operator="l04-test",
            note="L04 publish",
            tenant_id=principal.tenant_id,
        )
        assert approved.status == "approved"
        candidate = core.evolution._get_candidate(
            submitted.candidate_id, principal.tenant_id
        )
        resulting_id = str(candidate["resulting_knowledge_id"])
        assert core.evolution.rollback(
            resulting_id,
            operator="l04-test",
            note="L04 rollback",
            tenant_id=principal.tenant_id,
        ) is True
        listed = core.evolution.list_candidates(tenant_id=principal.tenant_id)
        current = next(item for item in listed if item.id == submitted.candidate_id)
        assert current.status == "rolled_back"
    finally:
        core.close()
