"""Independent acceptance-review probes. Isolated /tmp. No env.md. No product edits."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
SKILL = Path("/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md")
FREEZE = WORKSPACE / "docs/testing/run-20260911-acceptance-handoff/freeze.json"
FREEZE_AFTER = WORKSPACE / "docs/testing/run-20260911-acceptance-handoff/freeze-after-k05.json"
CHECKER = (
    WORKSPACE
    / "docs/testing/run-20260911-acceptance-handoff/skill-fix/check_skill.py"
)

sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from conftest import make_settings  # noqa: E402
from customer_service_fixtures import TableDrivenModel, build_core  # noqa: E402
from yunpai_customer_service.api import create_api_app  # noqa: E402
from yunpai_customer_service.auth import AuthenticationService  # noqa: E402

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
PNG_1X1_B = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detail_code(response) -> str | None:
    try:
        body = response.json()
    except Exception:
        return None
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    return None


def write_json(name: str, payload: dict) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def probe_hashes() -> dict:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    after = json.loads(FREEZE_AFTER.read_text(encoding="utf-8"))
    api_now = sha256_file(WORKSPACE / "src/yunpai_customer_service/api.py")
    core_now = sha256_file(WORKSPACE / "src/yunpai_customer_service/customer_service/core.py")
    skill_now = sha256_file(SKILL)
    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "probe": "candidate-hashes",
        "head_freeze": freeze["head"],
        "stage0_candidate_sha256": freeze["candidate_sha256"],
        "api_py": {
            "now": api_now,
            "stage0": freeze["files"]["src/yunpai_customer_service/api.py"],
            "after_k05_note": after["api_py_sha256_after_k05"],
            "matches_stage0": api_now == freeze["files"]["src/yunpai_customer_service/api.py"],
            "matches_after_k05_note": api_now == after["api_py_sha256_after_k05"],
        },
        "core_py": {
            "now": core_now,
            "stage0": freeze["files"]["src/yunpai_customer_service/customer_service/core.py"],
            "matches_stage0": core_now
            == freeze["files"]["src/yunpai_customer_service/customer_service/core.py"],
        },
        "skill_sha256": {
            "now": skill_now,
            "claimed_review_target": "89ae938a9b3688c7bda9c30f955e795bdf2be89c32ea2a9b776f194b5f287bac",
            "stage0_eval": freeze["skill_sha256"],
            "matches_claimed": skill_now
            == "89ae938a9b3688c7bda9c30f955e795bdf2be89c32ea2a9b776f194b5f287bac",
        },
        "product_digest_drift": api_now != freeze["files"]["src/yunpai_customer_service/api.py"],
    }
    write_json("candidate-hashes.json", payload)
    return payload


def probe_skill_checker_is_text_only() -> dict:
    text = SKILL.read_text(encoding="utf-8")
    needles = [
        "source env.md then export DATA_DIR",
        "refuse workspace data/",
        "do not substitute Orca",
        "Codex",
        "Luna",
        "Task tool",
        "run_in_background",
        "forbid resume",
        "unicode escapes",
        "Path.write_text",
        "file://",
        "localhost HTTP",
        "REVIEW_PASS",
        "must not be reverted to FAIL",
        "do not edit CASES.json during freeze",
        "skill_sha256",
        "product candidate digest",
        "do not stop to wait for the user when instructed to continue",
        "incomplete 10.2",
        "NO_GO",
    ]
    dummy = "\n".join(needles) + "\n"
    dummy_path = EVIDENCE / "false-green-skill-needles.txt"
    dummy_path.write_text(dummy, encoding="utf-8")
    present_in_skill = [n for n in needles if n in text]
    present_in_dummy = [n for n in needles if n in dummy]
    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "probe": "skill-keyword-checker-is-not-behavior",
        "checker_path": str(CHECKER),
        "note": (
            "check_skill.py only searches SKILL.md + operational-templates.md "
            "for substrings. A file that concatenates the needles would satisfy "
            "the same oracle. This is not evidence that an agent followed the rules."
        ),
        "skill_all_needles_present": len(present_in_skill) == len(needles),
        "dummy_all_needles_present": len(present_in_dummy) == len(needles),
        "dummy_path": str(dummy_path.relative_to(WORKSPACE)),
        "missing_from_skill": [n for n in needles if n not in text],
        "behavioral_proof": False,
    }
    write_json("skill-checker-text-only.json", payload)
    return payload


def probe_k05_contract() -> dict:
    import base64

    png_b64 = base64.b64encode(PNG_1X1).decode("ascii")
    with TemporaryDirectory(prefix="yunpai-review-k05-", dir="/tmp") as raw:
        data_dir = Path(raw)
        settings = make_settings(data_dir)
        core = build_core(data_dir, settings=settings, model=TableDrivenModel(settings))
        try:
            auth = AuthenticationService(core.db, settings)
            app = create_api_app(core, auth=auth)
            base = {
                "X-Client-Id": settings.bootstrap_client_id,
                "X-Client-Key": settings.bootstrap_client_key,
                "X-Subject-Id": "review-buyer-a",
            }
            rows = []
            with TestClient(app, raise_server_exceptions=False) as client:
                def post(headers, body):
                    return client.post("/v1/chat", headers=headers, json=body)

                h1 = {**base, "Idempotency-Key": "rev-msg"}
                first = post(h1, {"session_id": "sess-msg-aaaaaaa", "message": "first question"})
                replay = post(h1, {"session_id": "sess-msg-aaaaaaa", "message": "first question"})
                conflict = post(
                    h1, {"session_id": "sess-msg-aaaaaaa", "message": "different question"}
                )
                stream = client.post(
                    "/v1/chat/stream",
                    headers=h1,
                    json={"session_id": "sess-msg-aaaaaaa", "message": "stream different"},
                )
                rows.append(
                    {
                        "factor": "message",
                        "first_status": first.status_code,
                        "replay_status": replay.status_code,
                        "same_message_id": (first.json() or {}).get("message_id")
                        == (replay.json() or {}).get("message_id")
                        if first.status_code == 200 and replay.status_code == 200
                        else False,
                        "conflict_status": conflict.status_code,
                        "conflict_code": detail_code(conflict),
                        "has_answer": "answer" in (conflict.json() if conflict.headers.get("content-type", "").startswith("application/json") else {}),
                        "stream_status": stream.status_code,
                        "stream_code": detail_code(stream),
                    }
                )

                h2 = {**base, "Idempotency-Key": "rev-store"}
                s1 = post(
                    h2,
                    {
                        "session_id": "sess-store-aaaaa",
                        "message": "same text",
                        "context": {"store_id": "store-a1"},
                    },
                )
                s2 = post(
                    h2,
                    {
                        "session_id": "sess-store-aaaaa",
                        "message": "same text",
                        "context": {"store_id": "store-a2"},
                    },
                )
                rows.append(
                    {
                        "factor": "store_id",
                        "first_status": s1.status_code,
                        "conflict_status": s2.status_code,
                        "conflict_code": detail_code(s2),
                        "has_answer": "answer"
                        in (
                            s2.json()
                            if s2.headers.get("content-type", "").startswith("application/json")
                            else {}
                        ),
                    }
                )

                h3 = {**base, "Idempotency-Key": "rev-image"}
                i1 = post(h3, {"session_id": "sess-image-aaaa", "message": "same text"})
                i2 = post(
                    h3,
                    {
                        "session_id": "sess-image-aaaa",
                        "message": "same text",
                        "image": {"mime_type": "image/png", "data_base64": png_b64},
                    },
                )
                rows.append(
                    {
                        "factor": "image",
                        "first_status": i1.status_code,
                        "conflict_status": i2.status_code,
                        "conflict_code": detail_code(i2),
                        "image_error_preview": i2.text[:240],
                    }
                )

                h4a = {**base, "Idempotency-Key": "rev-subject", "X-Subject-Id": "buyer-a"}
                h4b = {**base, "Idempotency-Key": "rev-subject", "X-Subject-Id": "buyer-b"}
                u1 = post(h4a, {"session_id": "sess-subject-aaa", "message": "same text"})
                u2 = post(h4b, {"session_id": "sess-subject-aaa", "message": "same text"})
                u3 = post(h4b, {"session_id": "sess-subject-bbb", "message": "same text"})
                rows.append(
                    {
                        "factor": "subject_same_session",
                        "first_status": u1.status_code,
                        "conflict_status": u2.status_code,
                        "conflict_code": detail_code(u2),
                    }
                )
                rows.append(
                    {
                        "factor": "subject_new_session_same_key",
                        "first_status": u1.status_code,
                        "conflict_status": u3.status_code,
                        "conflict_code": detail_code(u3),
                    }
                )

                h5a = {
                    **base,
                    "Idempotency-Key": "rev-client",
                    "X-Subject-Id": "buyer-client-a",
                }
                h5b = {
                    "X-Client-Id": settings.bootstrap_admin_id,
                    "X-Client-Key": settings.admin_api_key,
                    "X-Subject-Id": "buyer-client-b",
                    "Idempotency-Key": "rev-client",
                }
                c1 = post(h5a, {"session_id": "sess-client-aaaa", "message": "same text"})
                c2 = post(h5b, {"session_id": "sess-client-bbbb", "message": "same text"})
                rows.append(
                    {
                        "factor": "different_client_same_key",
                        "first_status": c1.status_code,
                        "second_status": c2.status_code,
                        "second_code": detail_code(c2),
                        "isolated_success": c1.status_code == 200 and c2.status_code == 200,
                    }
                )

                k11_empty = post(
                    {**base},
                    {"session_id": "sess-k11-emptyaa"},
                )
                k11_bad_ct = client.post(
                    "/v1/chat",
                    headers={**base, "Content-Type": "text/plain"},
                    content="not-json",
                )
                rows.append(
                    {
                        "factor": "K11-empty-message-no-image",
                        "status": k11_empty.status_code,
                        "note": "handbook K11 HTTP schema; executable without L4 ledger",
                    }
                )
                rows.append(
                    {
                        "factor": "K11-wrong-content-type",
                        "status": k11_bad_ct.status_code,
                        "preview": k11_bad_ct.text[:160],
                    }
                )

            payload = {
                "saved_utc": datetime.now(timezone.utc).isoformat(),
                "probe": "k05-handbook-factors",
                "level": "L1-TestClient",
                "model": "TableDrivenModel",
                "data_dir": str(data_dir),
                "not_live_l3": True,
                "rows": rows,
                "mapping_present": "_http_for_session_scope"
                in (WORKSPACE / "src/yunpai_customer_service/api.py").read_text(
                    encoding="utf-8"
                ),
            }
            write_json("k05-factor-matrix.json", payload)
            return payload
        finally:
            core.close()


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    hashes = probe_hashes()
    checker = probe_skill_checker_is_text_only()
    k05 = probe_k05_contract()
    summary = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "api_matches_after_k05": hashes["api_py"]["matches_after_k05_note"],
        "product_digest_drift": hashes["product_digest_drift"],
        "skill_sha_matches_claimed": hashes["skill_sha256"]["matches_claimed"],
        "checker_is_behavioral_proof": checker["behavioral_proof"],
        "dummy_needles_would_pass_text_oracle": checker["dummy_all_needles_present"],
        "k05_rows": [
            {
                "factor": row["factor"],
                "conflict_or_status": row.get("conflict_status", row.get("status", row.get("second_status"))),
                "code": row.get("conflict_code", row.get("second_code")),
            }
            for row in k05["rows"]
        ],
    }
    write_json("summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
