"""Repeat the real DeepSeek vision request three times in an isolated data dir."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from yunpai_customer_service.config import Settings
from yunpai_customer_service.demo.app import create_app


def main(output: Path) -> None:
    image_path = Path(__file__).resolve().parents[3] / "docs/screenshots/verify-chat-home.png"
    encoded = base64.b64encode(image_path.read_bytes()).decode()
    settings = Settings.from_env()
    app = create_app(settings)
    rows = []
    with TestClient(app) as client:
        for index in range(1, 4):
            response = client.post(
                "/api/chat",
                json={
                    "session_id": f"real-vision-repeat-{index}",
                    "message": "请观察这张图片并说明需要确认什么。",
                    "image": {"mime_type": "image/png", "data_base64": encoded},
                },
            )
            try:
                body = response.json()
            except ValueError:
                body = {"raw": response.text[:1000]}
            rows.append(
                {
                    "attempt": index,
                    "status_code": response.status_code,
                    "vision_status": body.get("vision_status"),
                    "vision_model": body.get("vision_model"),
                    "vision_image_count": body.get("vision_image_count"),
                    "answer": str(body.get("answer") or "")[:500],
                }
            )
    statuses = [row["vision_status"] for row in rows]
    result = {
        "status": "PASS" if all(status == "applied" for status in statuses) else "INCOMPLETE",
        "attempts": rows,
        "image_sha256": __import__("hashlib").sha256(image_path.read_bytes()).hexdigest(),
        "configured_model": settings.vision_model_name,
        "note": "Three real-model attempts; an error is not treated as a product PASS.",
    }
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output)
