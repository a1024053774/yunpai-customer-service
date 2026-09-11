"""Run a bounded real-model local user journey using configuration supplied by env.md."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from yunpai_customer_service.config import Settings
from yunpai_customer_service.demo.app import create_app


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
NONCE = "REAL-USER-20260911-C01"


def scrub(value):
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if any(mark in str(key).lower() for mark in ("key", "secret", "token", "password")) else scrub(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def response(response):
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:2000]}
    return {"status_code": response.status_code, "body": scrub(body)}


def main() -> None:
    output = ROOT / "result.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    data_dir = Path(Settings.from_env().data_dir)
    txt = ROOT / f"{NONCE}.txt"
    md = ROOT / f"{NONCE}.md"
    pdf = ROOT / f"{NONCE}.pdf"
    txt.write_text(
        f"{NONCE} 孤岛验收壶\n型号：{NONCE}\n颜色：海盐白\n容量：6L\n",
        encoding="utf-8",
    )
    md.write_text(
        f"# {NONCE}\n\n型号：{NONCE}\n颜色：海盐白\n容量：6L\n",
        encoding="utf-8",
    )
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 760, NONCE)
    c.drawString(72, 740, "型号：" + NONCE)
    c.drawString(72, 720, "颜色：海盐白；容量：6L")
    c.save()

    settings = Settings.from_env()
    app = create_app(settings)
    result = {
        "run_id": "run-20260911-real-user",
        "nonce": NONCE,
        "configured_model": settings.model_name,
        "configured_vision_model": settings.vision_model_name,
        "data_dir": str(data_dir),
        "model_key_present": bool(settings.model_api_key),
        "vision_key_present": bool(settings.vision_api_key),
        "flows": {},
    }
    with TestClient(app) as client:
        result["flows"]["preflight"] = {
            "home": response(client.get("/")),
            "admin": response(client.get("/admin")),
            "health": response(client.get("/api/health")),
        }
        imports = []
        for path, mime in ((txt, "text/plain"), (md, "text/markdown"), (pdf, "application/pdf")):
            with path.open("rb") as handle:
                imports.append(
                    {
                        "file": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "response": response(
                            client.post(
                                "/api/knowledge/import",
                                files={"file": (path.name, handle, mime)},
                                data={"intent": "product_inquiry"},
                            )
                        ),
                    }
                )
        result["flows"]["import"] = imports

        session = "real-user-c01"
        first = response(
            client.post(
                "/api/chat",
                json={"session_id": session, "message": f"{NONCE} 是什么颜色和容量？"},
            )
        )
        second = response(
            client.post(
                "/api/chat",
                json={"session_id": session, "message": "这个颜色是什么？"},
            )
        )
        result["flows"]["c01"] = {"first": first, "second": second}

        image_path = WORKSPACE / "docs/screenshots/verify-chat-home.png"
        image = {
            "mime_type": "image/png",
            "data_base64": base64.b64encode(image_path.read_bytes()).decode(),
        }
        result["flows"]["vision"] = response(
            client.post(
                "/api/chat",
                json={"session_id": "real-user-vision", "message": "请观察这张图片。", "image": image},
            )
        )

        first_body = first["body"] if isinstance(first["body"], dict) else {}
        message_id = first_body.get("message_id")
        feedback = response(
            client.post(
                "/api/feedback",
                json={
                    "message_id": message_id,
                    "rating": -1,
                    "corrected_answer": f"{NONCE} 的容量是 6L，颜色是海盐白。",
                    "note": "真实用户流程 L04 纠正",
                    "submitted_by": "real-user-run",
                    "evidence_source": f"local:{txt.name}",
                },
            )
        )
        candidates_before = response(client.get("/api/evolution/candidates"))
        candidate_id = None
        items = candidates_before["body"].get("items", []) if isinstance(candidates_before["body"], dict) else []
        for item in items:
            if NONCE in str(item.get("question")):
                candidate_id = item.get("id")
                break
        l04 = {"feedback": feedback, "candidates_before": candidates_before, "candidate_id": candidate_id}
        if candidate_id:
            l04["evaluate"] = response(client.post(f"/api/evolution/candidates/{candidate_id}/evaluate"))
            if l04["evaluate"]["status_code"] == 200 and l04["evaluate"]["body"].get("gate_passed"):
                l04["approve"] = response(client.post(f"/api/evolution/candidates/{candidate_id}/approve", json={"note": "real-user-run"}))
                l04["knowledge_after_approve"] = response(client.get("/api/knowledge"))
                l04["rollback"] = response(client.post(f"/api/evolution/candidates/{candidate_id}/rollback"))
                l04["knowledge_after_rollback"] = response(client.get("/api/knowledge"))
                l04["candidates_after_rollback"] = response(client.get("/api/evolution/candidates"))
        result["flows"]["l04"] = l04

    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": result["run_id"], "path": str(output), "vision_status": result["flows"]["vision"]["body"].get("vision_status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
