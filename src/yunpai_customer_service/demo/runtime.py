"""示例运行时：补齐本地启动所需的密钥/模型开关，并装配 `CustomerServiceCore`。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..auth import AuthenticationService, Principal
from ..config import Settings
from ..customer_service import CustomerServiceCore
from ..database import Database
from ..domain_profiles import profile_for_domain
from ..knowledge_seed import seed_records
from ..schemas import MAX_CHAT_IMAGE_REQUEST_BODY_BYTES
from .catalog import DEMO_CONTEXT, DEMO_STORE_NAME, seed_demo_store

DEMO_CLIENT_KEY = "demo-client-key-not-for-production"
DEMO_ADMIN_KEY = "demo-admin-key-not-for-production"
DEMO_SUBJECT_HASH_KEY = "demo-subject-hash-key-not-for-production"


def prepare_demo_settings(settings: Settings | None = None) -> Settings:
    """让示例一定能启动：缺密钥时用占位值；没有模型 Key 时走 mock。"""
    settings = settings or Settings.from_env()
    updates: dict[str, Any] = {
        "kg_import_enabled": False,
        "kg_dream_worker_enabled": False,
        "handoff_sla_worker_enabled": False,
        "handoff_dispatch_worker_enabled": False,
        "outbox_worker_enabled": False,
        "channel_agent_worker_enabled": False,
        "competitive_monitor_worker_enabled": False,
    }
    if not settings.bootstrap_client_key:
        updates["bootstrap_client_key"] = DEMO_CLIENT_KEY
    if not settings.admin_api_key:
        updates["admin_api_key"] = DEMO_ADMIN_KEY
    if not settings.subject_hash_key:
        updates["subject_hash_key"] = DEMO_SUBJECT_HASH_KEY
    if not settings.model_mock_mode:
        if settings.model_api_key:
            updates["model_enabled"] = True
            updates["vision_enabled"] = True
            if not settings.vision_base_url:
                updates["vision_base_url"] = settings.model_base_url
            if not settings.vision_api_key:
                updates["vision_api_key"] = settings.model_api_key
        else:
            updates["model_mock_mode"] = True
            updates["model_enabled"] = False
    if settings.max_request_body_bytes < MAX_CHAT_IMAGE_REQUEST_BODY_BYTES:
        updates["max_request_body_bytes"] = MAX_CHAT_IMAGE_REQUEST_BODY_BYTES
    return replace(settings, **updates)


@dataclass
class DemoRuntime:
    settings: Settings
    db: Database
    core: CustomerServiceCore
    principal: Principal
    store_name: str = DEMO_STORE_NAME
    chat_context: dict[str, Any] | None = None

    def close(self) -> None:
        self.core.close()

    @property
    def model_mode(self) -> str:
        healthy, reason = self.core.model.health()
        if self.settings.model_mock_mode:
            return "mock"
        if healthy and self.settings.model_enabled:
            return "live"
        return reason


def build_demo_runtime(settings: Settings | None = None) -> DemoRuntime:
    settings = prepare_demo_settings(settings)
    profile_for_domain(settings.business_domain)
    settings.ensure_directories()
    db = Database(settings.app_db_path)
    db.initialize()
    core = CustomerServiceCore.build(db, settings)
    core.knowledge.seed_if_empty(seed_records())
    core.handoffs.ensure_default_queues(settings.bootstrap_tenant_id)
    auth = AuthenticationService(db, settings)
    principal = auth.authenticate(
        settings.bootstrap_client_id,
        settings.bootstrap_client_key,
        "demo-buyer",
    )
    seed_demo_store(core, tenant_id=principal.tenant_id)
    return DemoRuntime(
        settings=settings,
        db=db,
        core=core,
        principal=principal,
        chat_context=dict(DEMO_CONTEXT),
    )
