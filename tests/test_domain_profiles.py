from __future__ import annotations

import pytest

from yunpai_customer_service.domain_profiles import profile_for_domain


def test_hr_profile_maps_the_same_control_buckets_without_keyword_routing() -> None:
    profile = profile_for_domain("hr")

    assert profile["label"] == "员工服务"
    assert profile["intents"]["after_sales"] == "请假、报销或入职事项办理"
    assert set(profile["intents"]) == {
        "product_inquiry",
        "after_sales",
        "complaint",
        "chitchat",
    }


def test_unknown_domain_fails_before_demo_startup() -> None:
    with pytest.raises(ValueError, match="unsupported business domain"):
        profile_for_domain("unknown")


def test_demo_health_exposes_selected_hr_profile(tmp_path) -> None:
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from conftest import make_settings
    from yunpai_customer_service.demo.app import create_app

    settings = replace(make_settings(tmp_path), business_domain="hr")
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")

    assert health.status_code == 200
    assert health.json()["business_domain"] == "hr"
    assert health.json()["business_domain_label"] == "员工服务"
