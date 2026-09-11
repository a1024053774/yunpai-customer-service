"""Regression evidence for real graph ownership and trust-boundary defects."""
from dataclasses import replace
import json

import pytest

from conftest import make_settings
from customer_service_fixtures import TableDrivenModel, build_core, principal_for_core
from yunpai_customer_service.api import create_api_app
from yunpai_customer_service.auth import AuthenticationService
from yunpai_customer_service.demo.catalog import seed_demo_store, DEMO_SOURCE
from yunpai_customer_service.llm import ModelGateway
from yunpai_customer_service.text_utils import blob_to_vector


def test_sync_and_sse_execute_the_registered_generate_and_verify_nodes(tmp_path, monkeypatch):
    import yunpai_customer_service.graph as graph_module
    original_build = graph_module.build_graph
    calls = []

    def instrumented_graph(**kwargs):
        builder = original_build(**kwargs)
        for name in ('generate', 'verify'):
            runnable = builder.nodes.pop(name).runnable
            def instrument(state, config, node=name, original=runnable):
                calls.append(node)
                result = original.invoke(state, config)
                if node == 'generate':
                    result['draft'] = '图节点提供的保养说明，请按说明书操作。'
                return result
            builder.add_node(name, instrument)
        return builder

    monkeypatch.setattr(graph_module, 'build_graph', instrumented_graph)
    settings = make_settings(tmp_path)
    core = build_core(tmp_path, settings=settings, model=TableDrivenModel(settings))
    try:
        principal = principal_for_core(core)
        sync = core.chat(principal, 'audit-sync', '尺码怎么选')
        assert calls == ['generate', 'verify']
        calls.clear()
        events = list(core.chat_stream(principal, 'audit-sse', '尺码怎么选', idempotency_key=None))
        assert calls == ['generate', 'verify'], 'SSE bypassed registered graph nodes'
        assert events[-1]['response']['answer'] == sync.answer
        assert '图节点提供的保养说明' in sync.answer
    finally:
        core.close()


@pytest.mark.parametrize('question', [
    '如果要申请退款，需要什么材料？',
    '你们和竞品相比，有哪些功能优势？',
])
def test_model_policy_answer_is_not_overridden_by_lexical_routing(tmp_path, question):
    settings = make_settings(tmp_path)
    model = TableDrivenModel(settings, answer='请参考已发布的商品与售后说明。')
    core = build_core(tmp_path, settings=settings, model=model)
    try:
        response = core.chat(principal_for_core(core), 'audit-policy', question)
        assert 'agent_decision' in model.json_tasks
        assert response.requires_human is False, response.reason
        assert response.decision_mode == 'answer'
    finally:
        core.close()


def test_mock_agent_decision_does_not_parse_customer_keywords():
    def decision(text):
        messages = [{'role':'user', 'content':json.dumps({
            'task_type':'agent_decision','user_question':text,
            'current_tool_catalog':[], 'trusted_context':{},
        }, ensure_ascii=False)}]
        return json.loads(ModelGateway._mock_generate(messages))
    assert decision('请马上给我退款') == decision('今天心情很好')


@pytest.mark.parametrize('disabled_layer', ['core', 'injected_auth'])
def test_host_api_cannot_silently_inherit_anonymous_demo_auth(tmp_path, disabled_layer):
    settings = make_settings(tmp_path)
    core_settings = replace(settings, auth_required=False) if disabled_layer == 'core' else settings
    core = build_core(tmp_path, settings=core_settings, model=TableDrivenModel(core_settings))
    try:
        auth_settings = replace(settings, auth_required=False)
        auth = AuthenticationService(core.db, auth_settings) if disabled_layer == 'injected_auth' else None
        with pytest.raises(ValueError, match='authentication'):
            create_api_app(core, auth=auth)
    finally:
        core.close()


def test_demo_restart_keeps_the_selected_embedding_backend(tmp_path):
    class RecordingEncoder:
        name = 'audit-encoder'
        def embed_query(self, text): return (1.0, 0.0, 0.0)
        def embed_document(self, text): return (1.0, 0.0, 0.0)
    core = build_core(tmp_path, seed_knowledge=False)
    try:
        core.knowledge.embedding_provider = RecordingEncoder()
        tenant = principal_for_core(core).tenant_id
        seed_demo_store(core, tenant_id=tenant)
        seed_demo_store(core, tenant_id=tenant)
        with core.db.connect() as conn:
            vectors = [blob_to_vector(row['embedding']) for row in conn.execute(
                'SELECT embedding FROM knowledge WHERE source=? AND tenant_id=?', (DEMO_SOURCE, tenant)
            )]
        assert vectors
        assert all(vector == (1.0, 0.0, 0.0) for vector in vectors)
    finally:
        core.close()


def test_intent_classifier_receives_history_and_current_image_observation(tmp_path):
    from yunpai_customer_service.schemas import ChatImageInput
    from yunpai_customer_service.vision import VisionResult
    import base64
    settings = make_settings(tmp_path)
    model = TableDrivenModel(settings)
    classification_inputs = []
    original = model.generate_json
    def record(messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        if payload['task_type'] == 'intent_classification':
            classification_inputs.append(payload)
        return original(messages, **kwargs)
    model.generate_json = record
    core = build_core(tmp_path, settings=settings, model=model)
    try:
        principal = principal_for_core(core)
        core.chat(principal, 'audit-context', '空气炸锅的保养方式')
        core.vision.describe = lambda **kwargs: VisionResult(
            description='图片可见电源线外皮破损。', status='applied', applied=True,
            latency_ms=1, model='audit-vision', image_count=1,
        )
        image = ChatImageInput(mime_type='image/png', data_base64=base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode())
        core.chat(principal, 'audit-context', '这个呢？', image=image)
        payload = classification_inputs[-1]
        assert any('空气炸锅' in row['content'] for row in payload.get('history', []))
        assert '电源线' in payload.get('media_observation', {}).get('description', '')
    finally:
        core.close()


def test_demo_does_not_list_or_serve_other_tenants_original_files(tmp_path):
    from fastapi.testclient import TestClient
    from yunpai_customer_service.demo.app import create_app
    from yunpai_customer_service.knowledge_ingest import ingest_document
    with TestClient(create_app(make_settings(tmp_path))) as client:
        runtime = client.app.state.runtime
        ingest_document(runtime.core.knowledge, filename='other-private.md',
                        content='属于另一个租户的内部资料。'.encode(), tenant_id='other-tenant',
                        storage_dir=tmp_path / 'knowledge_uploads')
        stored = next((tmp_path / 'knowledge_uploads').iterdir()).name
        assert client.get('/api/knowledge/files').json()['items'] == []
        assert client.get('/api/knowledge/files/' + stored).status_code == 404


@pytest.mark.parametrize('headers', [
    {'X-Forwarded-For':'203.0.113.10'},
    {'Host':'public.example'},
    {'Origin':'https://public.example'},
])
def test_loopback_demo_rejects_forwarded_public_requests(tmp_path, headers):
    from fastapi.testclient import TestClient
    from yunpai_customer_service.demo.app import create_app
    with TestClient(create_app(make_settings(tmp_path))) as client:
        response = client.post('/api/knowledge/reindex', headers=headers)
        assert response.status_code == 403


@pytest.mark.parametrize('mode,intent,unsafe', [
    ('clarify','after_sales','请提供银行卡密码以便继续处理。'),
    ('handoff','after_sales','已经退款成功，款项会马上到账。'),
    ('handoff','complaint','请提供银行卡密码以便继续处理。'),
    ('refuse','after_sales','已经退款成功，款项会马上到账。'),
])
@pytest.mark.parametrize('transport', ['sync','sse'])
def test_terminal_model_responses_cannot_bypass_output_policy(tmp_path, mode, intent, unsafe, transport):
    settings = make_settings(tmp_path)
    model = TableDrivenModel(settings, intent='after_sales', decision_mode=mode, decision_intent=intent)
    model._table['agent_decision'].update(response=unsafe, missing_fields=['银行卡密码'] if mode == 'clarify' else [])
    core = build_core(tmp_path, settings=settings, model=model)
    try:
        principal = principal_for_core(core)
        if transport == 'sync':
            response = core.chat(principal, 'audit-terminal', '退款进度怎么查？').model_dump()
        else:
            response = list(core.chat_stream(principal, 'audit-terminal', '退款进度怎么查？', idempotency_key=None))[-1]['response']
        assert '银行卡密码' not in response['answer']
        assert '已经退款成功' not in response['answer']
        with core.db.connect() as conn:
            persisted = conn.execute('SELECT content FROM messages WHERE id=?',(response['message_id'],)).fetchone()['content']
        assert persisted == response['answer']
        assert any('terminal_output:' in step for step in response['trace'])
        assert response['model_fallback'] is True
    finally:
        core.close()


def test_explicitly_injected_model_is_used_for_intent_even_with_gateway_disabled(tmp_path):
    settings = replace(make_settings(tmp_path), model_enabled=False, model_mock_mode=False)
    model = TableDrivenModel(settings, intent='product_inquiry')
    core = build_core(tmp_path, settings=settings, model=model)
    try:
        response = core.chat(principal_for_core(core), 'audit-injected', '商品有什么颜色？')
        assert response.customer_intent == 'product_inquiry'
        assert response.intent_method == 'model'
    finally:
        core.close()


def test_clarification_missing_fields_are_untrusted_too(tmp_path):
    settings = make_settings(tmp_path)
    model = TableDrivenModel(settings, intent='after_sales', decision_mode='clarify')
    model._table['agent_decision'].update(response=None, missing_fields=['银行卡密码'])
    core = build_core(tmp_path, settings=settings, model=model)
    try:
        response = core.chat(principal_for_core(core), 'audit-fields', '怎样核对退款进度？')
        assert '银行卡密码' not in response.answer
    finally:
        core.close()


@pytest.mark.parametrize('answer', [
    '请提供以下信息：1）订单号；2）机器型号；3）故障现象。',
    '请补充：\n1. 订单号\n2. 商品名称\n3. 故障现象',
])
def test_output_evidence_does_not_treat_list_ordinals_as_business_claims(answer):
    from yunpai_customer_service.policy import review_output
    assert review_output(answer, '需核对订单和商品信息。')[0] is True


@pytest.mark.parametrize('answer', ['价格：1.99元', '1. 价格为999元', '退款比例为95%'])
def test_business_numbers_still_require_evidence(answer):
    from yunpai_customer_service.policy import review_output
    assert review_output(answer, '仅有商品名称。') == (False, 'numeric_claim_without_evidence')
