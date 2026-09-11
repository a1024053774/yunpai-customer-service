"""7.4 color-update experiment on isolated live DATA_DIR. No secrets."""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from customer_service_fixtures import principal_for_core  # noqa: E402
from yunpai_customer_service.config import Settings  # noqa: E402
from yunpai_customer_service.customer_service.core import CustomerServiceCore  # noqa: E402
from yunpai_customer_service.database import Database  # noqa: E402


def main() -> None:
    os.environ.setdefault("BOOTSTRAP_CLIENT_KEY", secrets.token_hex(16))
    os.environ.setdefault("SUBJECT_HASH_KEY", secrets.token_hex(16))
    os.environ.setdefault("ADMIN_API_KEY", secrets.token_hex(16))
    os.environ["KG_IMPORT_ENABLED"] = "false"
    os.environ["KG_DREAM_WORKER_ENABLED"] = "false"
    settings = Settings.from_env()
    data_dir = settings.data_dir.resolve()
    if not (str(data_dir).startswith("/tmp") or str(data_dir).startswith("/private/tmp")):
        raise SystemExit("DATA_DIR must be /tmp")
    db = Database(settings.app_db_path)
    db.initialize()
    core = CustomerServiceCore.build(db, settings)
    principal = principal_for_core(core, "live-74")
    sku = "QA-1416-74"
    v1 = core.knowledge.add_document(
        category="product",
        intent="product",
        question=f"{sku} color",
        answer=f"{sku} authorized color is rice-white. Capacity 4L.",
        keywords=f"{sku} color rice-white",
        risk_level="low",
        source="fixture:74-v1",
        tenant_id=principal.tenant_id,
    )
    before = core.chat(principal, "s74-old", f"{sku} color?")
    core.knowledge.retire_document(v1, "qa", principal.tenant_id)
    core.knowledge.add_document(
        category="product",
        intent="product",
        question=f"{sku} color",
        answer=f"{sku} authorized color is black after authorized update. Capacity 4L.",
        keywords=f"{sku} color black",
        risk_level="low",
        source="fixture:74-v2",
        tenant_id=principal.tenant_id,
    )
    after_new = core.chat(principal, "s74-new", f"{sku} color?")
    after_old = core.chat(principal, "s74-old", f"{sku} color again?")
    rewrite = core.chat(principal, "s74-rw", f"what colour is {sku}?")
    before_white = "rice-white" in before.answer.lower() or "\u7c73\u767d" in before.answer
    after_black = "black" in after_new.answer.lower() or "\u9ed1" in after_new.answer
    still_white = ("rice-white" in after_new.answer.lower() or "\u7c73\u767d" in after_new.answer) and not after_black
    status = "FAIL" if still_white else ("PASS" if before_white and after_black else "INCOMPLETE")
    case = {
        "id": "7.4",
        "status": status,
        "level": "L2",
        "actual": {
            "v1": v1,
            "before": before.answer,
            "after_new": after_new.answer,
            "after_old_session": after_old.answer,
            "rewrite": rewrite.answer,
            "before_white": before_white,
            "after_black": after_black,
            "still_white": still_white,
        },
        "notes": ["retire+add as authorized update stand-in; no UI publish workflow"],
        "saved_utc": datetime.now(timezone.utc).isoformat(),
    }
    (EVIDENCE / "74.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"id": "7.4", "status": status}, ensure_ascii=False))
    core.close()


if __name__ == "__main__":
    main()
