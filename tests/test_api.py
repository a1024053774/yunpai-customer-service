from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import make_settings
from customer_service_fixtures import TableDrivenModel, build_core
from yunpai_customer_service.api import create_api_app
from yunpai_customer_service.auth import AuthenticationService


def test_host_api_authenticates_and_exposes_model_intent(tmp_path) -> None:
    settings = make_settings(tmp_path)
    core = build_core(tmp_path, settings=settings, model=TableDrivenModel(settings))
    try:
        auth = AuthenticationService(core.db, settings)
        app = create_api_app(core, auth=auth)
        headers = {
            "X-Client-Id": settings.bootstrap_client_id,
            "X-Client-Key": settings.bootstrap_client_key,
            "X-Subject-Id": "site-buyer-1",
        }
        with TestClient(app) as client:
            unauthorized = client.post(
                "/v1/chat",
                json={"session_id": "site-session", "message": "商品容量是多少"},
            )
            response = client.post(
                "/v1/chat",
                headers=headers,
                json={"session_id": "site-session", "message": "商品容量是多少"},
            )
            health = client.get("/v1/health")

        assert unauthorized.status_code == 401
        assert response.status_code == 200
        assert response.json()["customer_intent"] == "product_inquiry"
        assert response.json()["intent_method"] == "model"
        assert health.json()["embedding_provider"] == "hash"
    finally:
        core.close()


def test_host_api_stream_reuses_core_stream_contract(tmp_path) -> None:
    settings = make_settings(tmp_path)
    core = build_core(tmp_path, settings=settings, model=TableDrivenModel(settings))
    try:
        auth = AuthenticationService(core.db, settings)
        app = create_api_app(core, auth=auth)
        headers = {
            "X-Client-Id": settings.bootstrap_client_id,
            "X-Client-Key": settings.bootstrap_client_key,
            "X-Subject-Id": "site-buyer-stream",
        }
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/stream",
                headers=headers,
                json={"session_id": "site-stream-session", "message": "你好"},
            )

        assert response.status_code == 200
        assert "data:" in response.text
        assert "persist" in response.text
    finally:
        core.close()
