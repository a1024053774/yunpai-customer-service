"""Optional production HTTP adapter for hosts embedding the customer-service core.

The adapter deliberately contains no business routing.  It authenticates the caller,
passes the request to the injected ``CustomerServiceCore`` and exposes the same response
metadata used by the demo, including model-based intent classification.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from .auth import AuthError, AuthenticationService, Principal
from .customer_service import CustomerServiceCore
from .database import SessionScopeError
from .schemas import ChatRequest


def _http_for_session_scope(exc: SessionScopeError) -> HTTPException:
    status = 409
    if getattr(exc, "code", "") == "invalid_session_source":
        status = 422
    return HTTPException(
        status_code=status,
        detail={"code": getattr(exc, "code", "session_scope_error"), "message": str(exc)},
    )


def create_api_app(
    core: CustomerServiceCore,
    *,
    auth: AuthenticationService | None = None,
) -> FastAPI:
    """Build a host-owned HTTP app around an already configured core."""
    if not core.settings.auth_required:
        raise ValueError("host API requires authentication; use the loopback demo separately")
    auth_service = auth or AuthenticationService(core.db, core.settings)
    if not auth_service.settings.auth_required or not auth_service.configured:
        raise ValueError("host API requires configured client authentication")
    app = FastAPI(title="Yunpai customer service API")

    def principal_for(request: Request) -> Principal:
        try:
            return auth_service.authenticate(
                request.headers.get("X-Client-Id"),
                request.headers.get("X-Client-Key"),
                request.headers.get("X-Subject-Id"),
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=401,
                detail=str(exc),
                headers={"WWW-Authenticate": "ClientCredentials"},
            ) from exc

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        health_check = getattr(core.model, "health", None)
        if callable(health_check):
            healthy, reason = health_check()
        else:
            healthy = bool(core.settings.model_enabled or core.settings.model_mock_mode)
            reason = "injected_model"
        return {
            "ok": healthy or core.settings.model_mock_mode,
            "model_mode": "mock" if core.settings.model_mock_mode else reason,
            "model_provider": core.settings.model_provider,
            "model_name": core.settings.model_name,
            "vision_model": core.settings.vision_model_name,
            "embedding_provider": core.knowledge.embedding_provider.name,
            "business_domain": core.settings.business_domain,
        }

    @app.post("/v1/chat")
    def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
        principal = principal_for(request)
        try:
            response = core.chat(
                principal,
                payload.session_id,
                payload.message,
                context=payload.context,
                idempotency_key=request.headers.get("Idempotency-Key"),
                source_type="api",
                source_reference="host-api",
                image=payload.image,
            )
        except SessionScopeError as exc:
            raise _http_for_session_scope(exc) from exc
        return response.model_dump()

    @app.post("/v1/chat/stream")
    def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
        principal = principal_for(request)
        idempotency_key = request.headers.get("Idempotency-Key")

        try:
            stream = iter(
                core.chat_stream(
                    principal,
                    payload.session_id,
                    payload.message,
                    context=payload.context,
                    idempotency_key=idempotency_key,
                    source_type="api",
                    source_reference="host-api",
                    image=payload.image,
                )
            )
            first = next(stream)
        except StopIteration:
            first = None
        except SessionScopeError as exc:
            raise _http_for_session_scope(exc) from exc

        def events() -> Iterator[str]:
            if first is not None:
                yield f"data: {json.dumps(first, ensure_ascii=False, default=str)}\n\n"
            for event in stream:
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return app
