"""Evidence that listed BLOCKED cases still lack prerequisites. No fake PASS."""
from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent


def listen(port: int) -> bool:
    sock = socket.socket()
    try:
        sock.settimeout(0.3)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def main() -> None:
    dist = WORKSPACE / "dist"
    wheels = list(dist.glob("*.whl")) if dist.is_dir() else []
    scan_pdfs = []
    for folder in (
        WORKSPACE / "docs",
        WORKSPACE / "tests",
        WORKSPACE / "fixtures",
    ):
        if folder.is_dir():
            scan_pdfs.extend(str(p.relative_to(WORKSPACE)) for p in folder.rglob("*scan*.pdf"))
    nginx = shutil.which("nginx")
    caddy = shutil.which("caddy")
    site_login = {
        "independent_site_url": None,
        "user_a_credentials": False,
        "user_b_credentials": False,
        "note": "no authorized independent-site login pair in this workspace",
    }
    hr_docs = []
    for name in ("docs/domain-reuse-contract.md", "src/yunpai_customer_service/domain_profiles.py"):
        path = WORKSPACE / name
        if path.is_file():
            hr_docs.append(name)
    cases = [
        {
            "id": "N03",
            "priority": "P0",
            "status": "BLOCKED",
            "reason": "no authorized reverse-proxy / TLS / public ingress in this environment",
            "actual": {
                "nginx": nginx,
                "caddy": caddy,
                "listen_80": listen(80),
                "listen_443": listen(443),
                "listen_8080": listen(8080),
            },
            "unblock": "authorized pre-prod gateway with real Host/TLS and Demo not exposed",
        },
        {
            "id": "N04",
            "priority": "P0",
            "status": "BLOCKED",
            "reason": "no independent-site login A/B accounts",
            "actual": site_login,
            "unblock": "two real website users plus host backend that binds X-Subject-Id",
        },
        {
            "id": "O02-O06",
            "priority": "P0/P1",
            "status": "BLOCKED",
            "reason": "HR is profile tags only; no authorized HR policy/SOP/roles",
            "actual": {"profile_files": hr_docs, "hr_business_delivered": False},
            "unblock": "business-accepted HR corpus, roles, and region rules",
        },
        {
            "id": "K06-K13-L4",
            "priority": "P0/P1",
            "status": "BLOCKED",
            "reason": "no sandbox business ledger / real write tools",
            "actual": {"tool_registry_has_external_ledger": False},
            "unblock": "authorized sandbox order/refund/notify ledger with independent readback",
        },
        {
            "id": "M08",
            "priority": "P1",
            "status": "BLOCKED",
            "reason": "8h soak not scheduled; no load contract / budget / dedicated env",
            "actual": {"soak_hours": 0, "load_contract": None},
            "unblock": "dedicated env, frozen load contract, 8h window, stop thresholds",
        },
        {
            "id": "A06",
            "priority": "P1",
            "status": "BLOCKED",
            "reason": "no frozen clean-dir wheel/image install off repo src",
            "actual": {"dist_wheels": [str(p.name) for p in wheels], "editable_src_used": True},
            "unblock": "build wheel/image, install in clean venv with repo src off PYTHONPATH",
        },
        {
            "id": "E03",
            "priority": "P1",
            "status": "BLOCKED",
            "reason": "no real scanned PDF with independent human page truth",
            "actual": {"scan_pdf_matches": scan_pdfs, "docling_importable": True},
            "unblock": "authorized Chinese scan PDF plus page-level human transcript",
        },
        {
            "id": "N01",
            "priority": "P1",
            "status": "BLOCKED",
            "reason": "same as A06: clean-env frozen package not installed",
            "actual": {"dist_wheels": [str(p.name) for p in wheels]},
            "unblock": "same as A06 plus extras/model files smoke",
        },
    ]
    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": "run-20260911-0131-grok46",
        "cases": cases,
    }
    (EVIDENCE / "blocked.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# BLOCKED evidence", ""]
    for case in cases:
        lines.append(f"- {case['id']}: BLOCKED - {case['reason']}")
    (EVIDENCE / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"blocked": [c["id"] for c in cases]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
