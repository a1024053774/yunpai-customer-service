"""J01/J02 live vision slices. No secrets. Isolated DATA_DIR required."""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "tests"))

from customer_service_fixtures import principal_for_core  # noqa: E402
from yunpai_customer_service.config import Settings  # noqa: E402
from yunpai_customer_service.customer_service.core import CustomerServiceCore  # noqa: E402
from yunpai_customer_service.database import Database  # noqa: E402
from yunpai_customer_service.schemas import ChatImageInput  # noqa: E402


def png_with_text(text: str, size: tuple[int, int] = (640, 200)) -> bytes:
    img = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 70), text, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def tiny_png() -> bytes:
    img = Image.new("RGB", (2, 2), (10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
    marker = "QA-1416-VISION"
    payload = png_with_text(marker)
    (EVIDENCE / "j01.png").write_bytes(payload)
    image = ChatImageInput(mime_type="image/png", data_base64=base64.b64encode(payload).decode("ascii"))
    db = Database(settings.app_db_path)
    db.initialize()
    core = CustomerServiceCore.build(db, settings)
    principal = principal_for_core(core, "vision-1416")
    r1 = core.chat(
        principal,
        "j01-sess",
        "what printed text is on this image? do not invent a model number.",
        image=image,
    )
    tiny = ChatImageInput(
        mime_type="image/png",
        data_base64=base64.b64encode(tiny_png()).decode("ascii"),
    )
    r2 = core.chat(
        principal,
        "j02-sess",
        "what damage do you see? name a SKU only if you can read it.",
        image=tiny,
    )
    saw = marker in r1.answer or "1416" in r1.answer
    invented = "AF50" in r1.answer or "QC-AF" in r1.answer
    j01 = "FAIL" if invented else ("PASS" if saw else "INCOMPLETE")
    unclear = any(
        x in r2.answer.lower()
        for x in ("cannot", "can't", "unable", "unclear", "\u65e0\u6cd5", "\u770b\u4e0d\u6e05", "\u65e0\u6cd5\u786e\u8ba4")
    )
    j02_invent = "AF50" in r2.answer
    j02 = "FAIL" if j02_invent else ("PASS" if unclear else "INCOMPLETE")
    out = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "vision_enabled": settings.vision_enabled,
        "vision_model": settings.vision_model_name if hasattr(settings, "vision_model_name") else None,
        "cases": [
            {
                "id": "J01",
                "status": j01,
                "level": "L2",
                "actual": {
                    "answer": r1.answer,
                    "saw_marker": saw,
                    "invented_sku": invented,
                    "vision_status": getattr(r1, "vision_status", None),
                },
                "notes": ["one synthetic PNG with printed marker; JPEG/WebP not run"],
            },
            {
                "id": "J02",
                "status": j02,
                "level": "L2",
                "actual": {
                    "answer": r2.answer,
                    "unclear": unclear,
                    "invented_sku": j02_invent,
                },
                "notes": ["2x2 PNG stand-in for blur; vision service failure not injected"],
            },
        ],
    }
    (EVIDENCE / "vision.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({c["id"]: c["status"] for c in out["cases"]}, ensure_ascii=False))
    core.close()


if __name__ == "__main__":
    main()
