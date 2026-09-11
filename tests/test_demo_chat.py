"""本机示例聊天页：页面可打开，对话走 `CustomerServiceCore`。"""

from __future__ import annotations

import base64
import json
from dataclasses import replace

from fastapi.testclient import TestClient

from yunpai_customer_service.demo.app import create_app
from yunpai_customer_service.demo.runtime import prepare_demo_settings
from yunpai_customer_service.schemas import ChatImageInput

from conftest import make_settings


def _png_image(suffix: bytes = b"test-image") -> ChatImageInput:
    return ChatImageInput(
        mime_type="image/png",
        data_base64=base64.b64encode(b"\x89PNG\r\n\x1a\n" + suffix).decode("ascii"),
    )


def test_prepare_demo_settings_enables_mock_without_api_key(tmp_path) -> None:
    settings = replace(
        make_settings(tmp_path),
        model_mock_mode=False,
        model_enabled=False,
        model_api_key="",
        bootstrap_client_key="",
        subject_hash_key="",
    )
    prepared = prepare_demo_settings(settings)
    assert prepared.model_mock_mode is True
    assert prepared.model_enabled is False
    assert prepared.bootstrap_client_key
    assert prepared.subject_hash_key


def test_demo_page_and_health(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "云派智能客服" in page.text
        assert 'id="messageInput"' in page.text

        health = client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
        assert body["ok"] is True
        assert body["model_mode"] == "mock"
        assert body["tenant_id"] == "tenant-test"
        assert body["business_domain"] == "ecommerce"
        assert body["business_domain_label"] == "电商销售"


def test_demo_chat_stream_answers_seed_question(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"session_id": "demo-stream-1", "message": "尺码怎么选"},
        ) as response:
            assert response.status_code == 200
            payload = "".join(response.iter_text())
        assert '"event": "delta"' in payload
        assert '"event": "result"' in payload
        assert "尺寸" in payload or "尺码" in payload


def test_demo_sync_and_stream_share_simulation_session_scope(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        sync_response = client.post(
            "/api/chat",
            json={
                "session_id": "demo-shared-source-1",
                "message": "尺码怎么选",
            },
        )
        assert sync_response.status_code == 200
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "session_id": "demo-shared-source-1",
                "message": "那这个呢？",
            },
        ) as stream_response:
            assert stream_response.status_code == 200
            payload = "".join(stream_response.iter_text())
        with app.state.runtime.db.connect() as conn:
            source = conn.execute(
                """
                SELECT source_type, source_reference FROM sessions
                WHERE external_session_id=?
                """,
                ("demo-shared-source-1",),
            ).fetchone()

    assert '"event": "result"' in payload
    assert dict(source) == {
        "source_type": "simulation",
        "source_reference": "local-demo",
    }


def test_demo_seeds_qingchuan_catalog(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        runtime = app.state.runtime
        with runtime.db.connect() as conn:
            skus = {
                row[0]
                for row in conn.execute(
                    "SELECT sku_id FROM catalog_items WHERE store_id=?",
                    ("demo-qingchuan-shop",),
                )
            }
            knowledge_keys = {
                row[0]
                for row in conn.execute(
                    "SELECT knowledge_key FROM knowledge WHERE source=?",
                    ("demo:qingchuan-catalog-v1",),
                )
            }
        health = client.get("/api/health").json()

    assert skus == {"QC-AF50", "QC-AF35", "QC-HM4", "QC-GS2"}
    assert "demo:qingchuan-airfryer-5l-capacity" in knowledge_keys
    assert health["store_name"] == "晴川小家电（模拟店）"


def test_demo_chat_answers_airfryer_capacity(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "session_id": "demo-airfryer-1",
                "message": "晴川空气炸锅 5L 容量是多少",
            },
        )
        assert response.status_code == 200
        body = response.json()
    assert "5L" in body["answer"]
    assert "QC-AF50" in body["answer"] or "空气炸锅" in body["answer"]
    assert body["customer_intent"] == "product_inquiry"
    assert body["intent_method"] == "model"


def test_demo_seed_clears_sku_scope_on_existing_knowledge(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        runtime = app.state.runtime
        with runtime.db._write_lock, runtime.db.connect() as conn:
            conn.execute(
                "UPDATE knowledge SET sku_id='QC-AF50' WHERE knowledge_key=?",
                ("demo:qingchuan-airfryer-5l-capacity",),
            )
        from yunpai_customer_service.demo.catalog import seed_demo_store

        seed_demo_store(runtime.core, tenant_id=runtime.principal.tenant_id)
        with runtime.db.connect() as conn:
            sku_id = conn.execute(
                "SELECT sku_id FROM knowledge WHERE knowledge_key=?",
                ("demo:qingchuan-airfryer-5l-capacity",),
            ).fetchone()[0]
        response = client.post(
            "/api/chat",
            json={
                "session_id": "demo-airfryer-refresh-1",
                "message": "晴川空气炸锅 5L 容量是多少",
            },
        )
    assert sku_id is None
    assert response.status_code == 200
    assert "5L" in response.json()["answer"]


def test_mock_model_gateway_ignores_ipv6_no_proxy(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,::1,::1/128,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,::1,::1/128,localhost")
    from yunpai_customer_service.llm import ModelGateway

    gateway = ModelGateway(make_settings(tmp_path))
    try:
        assert gateway.health() == (True, "mock")
    finally:
        gateway.close()


def test_demo_chat_rejects_empty_message(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"session_id": "demo-empty-1", "message": ""},
        )
        assert response.status_code == 422


def test_demo_seed_supports_second_tenant_on_same_db(tmp_path) -> None:
    """回归：同一库换租户重启时，固定主键曾在 catalog_items.id / knowledge.id 撞唯一约束。"""
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        runtime = app.state.runtime
        from yunpai_customer_service.demo.catalog import seed_demo_store

        written = seed_demo_store(runtime.core, tenant_id="another-tenant")
        assert written["catalog_items"] == 4
        assert written["knowledge_records"] > 0
        with runtime.db.connect() as conn:
            tenants = {
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT tenant_id FROM catalog_items WHERE store_id=?",
                    ("demo-qingchuan-shop",),
                )
            }
    assert "another-tenant" in tenants
    assert len(tenants) == 2


def test_demo_lists_sessions_for_current_identity(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        sent = client.post(
            "/api/chat",
            json={"session_id": "demo-list-sessions-1", "message": "尺码怎么选"},
        )
        assert sent.status_code == 200
        runtime = app.state.runtime
        with runtime.db.connect() as conn:
            row = conn.execute(
                "SELECT id FROM sessions WHERE external_session_id=?",
                ("demo-list-sessions-1",),
            ).fetchone()
        internal_id = row["id"]
        response = client.get("/api/sessions")
        assert response.status_code == 200
        text = response.text
        assert "subject_hash" not in text
        assert "client_id" not in text
        assert internal_id not in text
        items = response.json()["items"]
        match = next(
            item for item in items if item["session_id"] == "demo-list-sessions-1"
        )
        assert set(match) == {"session_id", "created_at", "last_seen_at", "status"}


def test_demo_session_history_serves_public_image_media(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        sent = client.post(
            "/api/chat",
            json={
                "session_id": "demo-history-image-1",
                "message": "请看这张图",
                "image": _png_image(b"demo-history").model_dump(),
            },
        )
        assert sent.status_code == 200
        history = client.get("/api/sessions/demo-history-image-1/messages")
        assert history.status_code == 200
        text = history.text
        assert "storage_ref" not in text
        assert "vision_description" not in text
        assert "chat-media" not in text
        user = next(item for item in history.json()["items"] if item["role"] == "user")
        media = user["media"][0]
        assert media["mime_type"] == "image/png"
        assert media["url"]
        media_response = client.get(media["url"])
        assert media_response.status_code == 200
        assert media_response.headers["content-type"].startswith("image/png")


def test_demo_page_has_paste_and_history_ui(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert 'addEventListener("paste"' in page.text
        assert "历史会话" in page.text


def test_demo_chat_response_includes_trace_and_decision_mode(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "session_id": "demo-trace-1",
                "message": "晴川空气炸锅 5L 容量是多少",
            },
        )
        assert response.status_code == 200
        body = response.json()
    assert isinstance(body["trace"], list)
    assert body["trace"]
    assert body["trace"][0] == "intake"
    assert "decision_mode" in body


def test_demo_health_includes_demo_context(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
    assert "context" in body
    assert body["context"]["store_id"] == "demo-qingchuan-shop"


def test_demo_page_has_diagnostic_ui_and_ime_safe_enter(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        text = page.text
        assert "isComposing" in text
        assert "决策详情" in text
        assert "命中来源" in text
        assert "本次接口原始输出" in text
        assert 'addEventListener("paste"' in text
        assert "历史会话" in text


def test_demo_page_has_release_notes_bell_and_feature_log(tmp_path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        text = page.text

    assert 'id="releaseBell"' in text
    assert 'aria-label="查看支持功能和版本更新"' in text
    assert 'aria-controls="releasePanel"' in text
    assert 'id="releasePanel"' in text
    assert "当前能力" in text
    assert "DeepSeek Flash 意图识别" in text
    assert "不依赖云端向量库" in text
    assert "Docling 解析版式与表格" in text
    assert "版本更新" in text
    assert "知识工作台" in text
    assert "2026-09-09" in text
    assert "2026-08-26" in text
