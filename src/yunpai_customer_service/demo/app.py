"""本机示例聊天服务：`python -m yunpai_customer_service.demo`。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import Settings
from ..message_media import public_message_media
from ..schemas import ChatImageInput
from .runtime import DemoRuntime, build_demo_runtime

STATIC_DIR = Path(__file__).with_name("static")
INDEX_HTML = STATIC_DIR / "index.html"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


class DemoChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=8, max_length=128)
    message: str = Field(default="", max_length=2000)
    image: ChatImageInput | None = None

    @model_validator(mode="after")
    def require_message_or_image(self) -> "DemoChatRequest":
        if not self.message.strip() and self.image is None:
            raise ValueError("message or image is required")
        return self


def _require_loopback(request: Request) -> None:
    host = (request.client.host if request.client else "") or ""
    if host not in LOOPBACK_HOSTS:
        raise HTTPException(status_code=403, detail="demo UI is limited to loopback clients")


def _demo_internal_session(runtime: DemoRuntime, session_id: str) -> str | None:
    with runtime.db.connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM sessions
            WHERE external_session_id=? AND tenant_id=? AND subject_hash=?
            """,
            (
                session_id,
                runtime.principal.tenant_id,
                runtime.principal.subject_hash,
            ),
        ).fetchone()
    return str(row["id"]) if row is not None else None


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = build_demo_runtime(settings)
        app.state.runtime = runtime
        try:
            yield
        finally:
            runtime.close()

    app = FastAPI(title="Yunpai customer service demo", lifespan=lifespan)

    def runtime_of(request: Request) -> DemoRuntime:
        _require_loopback(request)
        return request.app.state.runtime

    @app.get("/", include_in_schema=False)
    def index(request: Request) -> FileResponse:
        _require_loopback(request)
        if not INDEX_HTML.is_file():
            raise HTTPException(status_code=404, detail="demo page is missing")
        return FileResponse(INDEX_HTML, media_type="text/html; charset=utf-8")

    @app.get("/api/health")
    def health(request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        return {
            "ok": True,
            "model_mode": runtime.model_mode,
            "model_name": runtime.settings.model_name,
            "model_provider": runtime.settings.model_provider,
            "vision_enabled": runtime.settings.vision_enabled,
            "vision_model": runtime.settings.vision_model_name,
            "store_name": runtime.store_name,
            "context": runtime.chat_context,
        }

    @app.post("/api/chat")
    def chat(payload: DemoChatRequest, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        response = runtime.core.chat(
            runtime.principal,
            payload.session_id,
            payload.message,
            context=runtime.chat_context,
            source_type="simulation",
            source_reference="local-demo",
            image=payload.image,
        )
        return response.model_dump()

    @app.post("/api/chat/stream")
    def chat_stream(payload: DemoChatRequest, request: Request) -> StreamingResponse:
        runtime = runtime_of(request)

        def events() -> Iterator[str]:
            for event in runtime.core.chat_stream(
                runtime.principal,
                payload.session_id,
                payload.message,
                context=runtime.chat_context,
                idempotency_key=None,
                source_type="simulation",
                source_reference="local-demo",
                image=payload.image,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/api/sessions")
    def list_sessions(request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        with runtime.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT external_session_id, created_at, last_seen_at, status
                FROM sessions
                WHERE tenant_id=? AND subject_hash=?
                ORDER BY last_seen_at DESC
                LIMIT 50
                """,
                (runtime.principal.tenant_id, runtime.principal.subject_hash),
            ).fetchall()
        return {
            "items": [
                {
                    "session_id": row["external_session_id"],
                    "created_at": row["created_at"],
                    "last_seen_at": row["last_seen_at"],
                    "status": row["status"],
                }
                for row in rows
            ]
        }

    @app.get("/api/sessions/{session_id}/messages")
    def session_messages(session_id: str, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        internal_id = _demo_internal_session(runtime, session_id)
        if internal_id is None:
            raise HTTPException(status_code=404, detail="session not found")
        page = runtime.db.paginated_messages(
            internal_id,
            None,
            100,
            tenant_id=runtime.principal.tenant_id,
            subject_hash=runtime.principal.subject_hash,
        )
        media_by_message = runtime.db.message_media_for_messages(
            [str(item["id"]) for item in page["items"]]
        )
        for item in page["items"]:
            item["media"] = public_message_media(
                media_by_message.get(str(item["id"]), []),
                url_prefix=(
                    f"/api/sessions/{quote(session_id, safe='')}"
                    f"/messages/{quote(str(item['id']), safe='')}/media"
                ),
            )
        return page

    @app.get(
        "/api/sessions/{session_id}/messages/{message_id}/media/{media_id}",
        response_class=FileResponse,
    )
    def session_message_media(
        session_id: str,
        message_id: str,
        media_id: str,
        request: Request,
    ) -> FileResponse:
        runtime = runtime_of(request)
        internal_id = _demo_internal_session(runtime, session_id)
        if internal_id is None:
            raise HTTPException(status_code=404, detail="session not found")
        result = runtime.core.message_media.resolve_for_message(
            runtime.db,
            tenant_id=runtime.principal.tenant_id,
            session_id=internal_id,
            message_id=message_id,
            media_id=media_id,
            subject_hash=runtime.principal.subject_hash,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="message media not found")
        path, mime_type = result
        return FileResponse(path, media_type=mime_type)

    return app


def main(argv: list[str] | None = None) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "缺少示例依赖。请先执行：pip install 'yunpai-customer-service[demo]'"
        ) from exc

    parser = argparse.ArgumentParser(description="启动智能客服示例聊天页")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("示例服务只允许绑定回环地址（127.0.0.1 / localhost / ::1）")

    print(f"智能客服示例：http://{args.host}:{args.port}/")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
