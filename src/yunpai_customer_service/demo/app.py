"""本机示例聊天服务：`python -m yunpai_customer_service.demo`。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import Settings
from ..domain_profiles import profile_for_domain
from ..knowledge_ingest import DocumentIngestError, ingest_document
from ..message_media import public_message_media
from ..schemas import ChatImageInput, FeedbackRequest
from .runtime import DemoRuntime, build_demo_runtime

STATIC_DIR = Path(__file__).with_name("static")
INDEX_HTML = STATIC_DIR / "index.html"
ADMIN_HTML = STATIC_DIR / "admin.html"
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
    request_host = request.url.hostname or ""
    test_host = host == "testclient" and request_host == "testserver"
    forwarded = any(name in request.headers for name in (
        "Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Real-IP"
    ))
    origin = request.headers.get("Origin")
    try:
        local_origin = not origin or urlsplit(origin).hostname in LOOPBACK_HOSTS
    except ValueError:
        local_origin = False
    if (host not in LOOPBACK_HOSTS or forwarded or not local_origin
            or (request_host not in LOOPBACK_HOSTS and not test_host)):
        raise HTTPException(status_code=403, detail="demo UI is limited to direct loopback clients")


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
            "embedding_provider": runtime.core.knowledge.embedding_provider.name,
            "embedding_model": runtime.settings.rag_embedding_model,
            "store_name": runtime.store_name,
            "tenant_id": runtime.principal.tenant_id,
            "business_domain": runtime.settings.business_domain,
            "business_domain_label": profile_for_domain(runtime.settings.business_domain)["label"],
            "context": runtime.chat_context,
        }

    @app.get("/admin", include_in_schema=False)
    def admin(request: Request) -> FileResponse:
        _require_loopback(request)
        if not ADMIN_HTML.is_file():
            raise HTTPException(status_code=404, detail="admin page is missing")
        return FileResponse(ADMIN_HTML, media_type="text/html; charset=utf-8")

    def owns_original(runtime: DemoRuntime, stored_name: str) -> bool:
        digest, separator, filename = stored_name.partition("-")
        if not separator or len(digest) != 16 or any(ch not in "0123456789abcdef" for ch in digest):
            return False
        prefix = f"upload://{filename}?sha256={digest}#"
        with runtime.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM knowledge WHERE tenant_id=? AND category='uploaded_document' "
                "AND substr(source, 1, ?)=? LIMIT 1",
                (runtime.principal.tenant_id, len(prefix), prefix),
            ).fetchone()
        return row is not None

    @app.get("/api/knowledge/files")
    def knowledge_files(request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        root = runtime.settings.data_dir / "knowledge_uploads"
        if not root.is_dir():
            return {"items": []}
        items = []
        for path in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if path.is_file() and not path.is_symlink() and owns_original(runtime, path.name):
                stat = path.stat()
                items.append({"name": path.name, "size_bytes": stat.st_size, "modified_at": stat.st_mtime})
        return {"items": items[:100]}

    @app.get("/api/knowledge/files/{stored_name}")
    def knowledge_file(stored_name: str, request: Request) -> FileResponse:
        runtime = runtime_of(request)
        root = (runtime.settings.data_dir / "knowledge_uploads").resolve()
        path = (root / stored_name).resolve()
        if path.parent != root or not path.is_file() or not owns_original(runtime, stored_name):
            raise HTTPException(status_code=404, detail="knowledge file not found")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    @app.get("/api/knowledge")
    def knowledge_list(request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        with runtime.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, knowledge_key, category, intent, question, source, version,
                       review_status, created_at, updated_at
                FROM knowledge
                WHERE tenant_id=? AND layer <> 'memory' AND status='active'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 200
                """,
                (runtime.principal.tenant_id,),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.post("/api/knowledge/reindex")
    def knowledge_reindex(request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        updated = runtime.core.knowledge.rebuild_embeddings(
            tenant_id=runtime.principal.tenant_id
        )
        return {
            "updated": updated,
            "embedding_provider": runtime.core.knowledge.embedding_provider.name,
        }

    @app.get("/api/evolution/candidates")
    def evolution_candidates(request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        candidates = runtime.core.evolution.list_candidates(tenant_id=runtime.principal.tenant_id)
        return {"items": [item.model_dump() for item in candidates]}

    @app.post("/api/knowledge/import")
    async def knowledge_import(
        request: Request,
        file: UploadFile = File(...),
        intent: str = Form("product_inquiry"),
    ) -> dict[str, Any]:
        runtime = runtime_of(request)
        if intent not in {"product_inquiry", "after_sales", "complaint", "chitchat"}:
            raise HTTPException(status_code=422, detail="不支持的意图分类")
        content = await file.read()
        try:
            imported = ingest_document(
                runtime.core.knowledge,
                filename=file.filename or "",
                content=content,
                tenant_id=runtime.principal.tenant_id,
                intent=intent,
                source_prefix="upload",
                storage_dir=runtime.settings.data_dir / "knowledge_uploads",
            )
        except DocumentIngestError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "filename": file.filename,
            "count": len(imported),
            "items": [asdict(item) for item in imported],
        }

    @app.post("/api/evolution/candidates/{candidate_id}/evaluate")
    def evaluate_candidate(candidate_id: str, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        try:
            result = runtime.core.evolution.evaluate(candidate_id, tenant_id=runtime.principal.tenant_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump()

    @app.post("/api/evolution/candidates/{candidate_id}/approve")
    async def approve_candidate(candidate_id: str, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        payload = await request.json()
        try:
            result = runtime.core.evolution.approve(
                candidate_id,
                operator=runtime.principal.client_id,
                note=str(payload.get("note") or "demo 管理员批准"),
                tenant_id=runtime.principal.tenant_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump()

    @app.post("/api/evolution/candidates/{candidate_id}/rollback")
    def rollback_candidate(candidate_id: str, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        with runtime.db.connect() as conn:
            row = conn.execute(
                "SELECT resulting_knowledge_id FROM evolution_candidates WHERE id=? AND tenant_id=?",
                (candidate_id, runtime.principal.tenant_id),
            ).fetchone()
        if row is None or not row["resulting_knowledge_id"]:
            raise HTTPException(status_code=422, detail="候选尚未生成可回滚的知识版本")
        try:
            changed = runtime.core.evolution.rollback(
                str(row["resulting_knowledge_id"]),
                operator=runtime.principal.client_id,
                note="demo 管理员回滚",
                tenant_id=runtime.principal.tenant_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"candidate_id": candidate_id, "rolled_back": changed}

    @app.post("/api/evolution/candidates/{candidate_id}/reject")
    async def reject_candidate(candidate_id: str, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        payload = await request.json()
        try:
            result = runtime.core.evolution.reject(
                candidate_id,
                operator=runtime.principal.client_id,
                note=str(payload.get("note") or "demo 管理员驳回"),
                tenant_id=runtime.principal.tenant_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump()

    @app.post("/api/feedback")
    def feedback(payload: FeedbackRequest, request: Request) -> dict[str, Any]:
        runtime = runtime_of(request)
        try:
            result = runtime.core.evolution.submit_feedback(
                payload,
                tenant_id=runtime.principal.tenant_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump()

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

    parser = argparse.ArgumentParser(description="启动云派智能客服本机演示")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("示例服务只允许绑定回环地址（127.0.0.1 / localhost / ::1）")

    print(f"云派智能客服：http://{args.host}:{args.port}/")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
