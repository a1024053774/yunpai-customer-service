"""智能客服门面：对话、记忆、话术匹配与自沉淀的可独立构建入口。

`AgentService` 只做薄委托：所有协作对象由构造函数注入，
`CustomerServiceCore.build` 为独立使用场景装配默认协作对象。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from ..auth import Principal
from ..config import Settings
from ..context_builder import ContextBuilder
from ..database import Database, SessionScopeError, utc_now
from ..evolution import EvolutionService
from ..handoff import HandoffService
from ..llm import ModelError, ModelGateway
from ..message_media import (
    MessageMediaStore,
    attach_vision_description,
    clear_media_deletions,
    enqueue_media_deletions,
    mark_media_deletion_failed,
)
from ..policy import sanitize_context
from ..rag import KnowledgeBase
from ..schemas import ChatImageInput, ChatResponse, chat_response_from_state
from ..sops import SopService
from ..text_utils import redact_sensitive
from ..tools import ToolRegistry
from ..vision import VisionGateway, VisionResult
from .generation import (
    BRANCH_MODEL,
    GenerationPlan,
    plan_generation,
    recover_model_failure,
)

if TYPE_CHECKING:
    from ..knowledge_engine.memory_service import KnowledgeMemoryService


# 顾客提供的业务字段：未授权 principal 一律剥离（与 graph/policy 的授权边界一致）
UNTRUSTED_ORDER_FIELDS = (
    "order_id",
    "order_status",
    "logistics_status",
    "carrier",
    "tracking_last_event",
)


class CustomerServiceCore:
    def __init__(
        self,
        *,
        db: Database,
        settings: Settings,
        model: ModelGateway,
        tools: ToolRegistry,
        knowledge: KnowledgeBase,
        contexts: ContextBuilder,
        handoffs: HandoffService,
        sops: SopService,
        evolution: EvolutionService | None = None,
        memory: "KnowledgeMemoryService | None" = None,
        checkpointer: Any | None = None,
        graph: Any | None = None,
        vision: VisionGateway | None = None,
        message_media: MessageMediaStore | None = None,
    ):
        self.db = db
        self.settings = settings
        self.model = model
        self.tools = tools
        self.knowledge = knowledge
        self.contexts = contexts
        self.handoffs = handoffs
        self.sops = sops
        # 自沉淀属于客服闭环（feedback→candidate→approve→复用），默认自建、允许注入
        self.evolution = evolution or EvolutionService(db, knowledge)
        self.memory = memory
        self.checkpointer = checkpointer
        self._owned_closers: list[Callable[[], None]] = []
        if vision is None:
            vision = VisionGateway(settings)
            self._owned_closers.append(vision.close)
        self.vision = vision
        self.message_media = message_media or MessageMediaStore(settings.data_dir)
        self.graph = graph if graph is not None else self._compile_graph()

    @classmethod
    def build(
        cls,
        db: Database,
        settings: Settings,
        *,
        model: ModelGateway | None = None,
        tools: ToolRegistry | None = None,
        knowledge: KnowledgeBase | None = None,
        contexts: ContextBuilder | None = None,
        handoffs: HandoffService | None = None,
        sops: SopService | None = None,
        evolution: EvolutionService | None = None,
        memory: "KnowledgeMemoryService | None" = None,
        checkpointer: Any | None = None,
        vision: VisionGateway | None = None,
        message_media: MessageMediaStore | None = None,
    ) -> "CustomerServiceCore":
        """装配默认协作对象；未注入的部分由本方法创建并在 `close()` 中释放。"""
        owned: list[Callable[[], None]] = []
        if model is None:
            model = ModelGateway(settings)
            owned.append(model.close)
        if vision is None:
            vision = VisionGateway(settings)
            owned.append(vision.close)
        if tools is None:
            tools = ToolRegistry()
            owned.append(tools.close)
        knowledge = knowledge or KnowledgeBase(db)
        contexts = contexts or ContextBuilder(db)
        handoffs = handoffs or HandoffService(db)
        sops = sops or SopService(db, tools)
        message_media = message_media or MessageMediaStore(settings.data_dir)
        if memory is None:
            # 延迟导入：knowledge_engine 包 __init__ → graph_api → service 会成环
            from ..knowledge_engine.memory_service import KnowledgeMemoryService

            memory = KnowledgeMemoryService(knowledge)
        if checkpointer is None:
            from langgraph.checkpoint.sqlite import SqliteSaver

            connection = sqlite3.connect(
                settings.checkpoint_db_path,
                check_same_thread=False,
            )
            owned.append(connection.close)
            checkpointer = SqliteSaver(connection)
        core = cls(
            db=db,
            settings=settings,
            model=model,
            tools=tools,
            knowledge=knowledge,
            contexts=contexts,
            handoffs=handoffs,
            sops=sops,
            evolution=evolution,
            memory=memory,
            checkpointer=checkpointer,
            vision=vision,
            message_media=message_media,
        )
        core._owned_closers.extend(owned)
        return core

    def _compile_graph(self) -> Any:
        # 延迟导入：graph 消费本包的 generation（消灭双通道手抄），顶层导入会成环
        from ..graph import build_graph

        builder = build_graph(
            settings=self.settings,
            db=self.db,
            knowledge=self.knowledge,
            model=self.model,
            handoffs=self.handoffs,
            tools=self.tools,
            sops=self.sops,
            contexts=self.contexts,
            memory=self.memory,
        )
        return builder.compile(checkpointer=self.checkpointer)

    def close(self) -> None:
        """释放本实例自己创建的资源；注入的协作对象由宿主负责关闭。"""
        while self._owned_closers:
            self._owned_closers.pop()()

    def chat(
        self,
        principal: Principal,
        session_id: str,
        message: str,
        context: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        execution_mode: str = "live",
        source_type: str = "api",
        source_reference: str | None = None,
        image: ChatImageInput | None = None,
    ) -> ChatResponse:
        if execution_mode not in {"live", "shadow"}:
            raise ValueError("agent execution mode must be live or shadow")
        internal_session_id = self.db.resolve_session(
            tenant_id=principal.tenant_id,
            client_id=principal.client_id,
            external_session_id=session_id,
            subject_hash=principal.subject_hash,
            source_type=source_type,
            source_reference=source_reference,
        )
        safe_message, input_redacted, trusted_context, image_digest = (
            self._prepare_chat_content(principal, message, context, image)
        )

        invocation: dict[str, Any] | None = None
        if idempotency_key is not None:
            invocation = self.prepare_invocation(
                principal=principal,
                internal_session_id=internal_session_id,
                idempotency_key=idempotency_key,
                safe_message=safe_message,
                trusted_context=trusted_context,
                execution_mode=execution_mode,
                image_digest=image_digest,
            )
            if invocation["status"] == "completed":
                return self.invocation_response(invocation)
        user_message_id = (
            str(invocation["user_message_id"])
            if invocation
            else f"msg-user-{uuid.uuid4().hex}"
        )
        message_media: list[dict[str, Any]] = []
        started = time.perf_counter()
        trace_id = (
            str(invocation["trace_id"])
            if invocation
            else f"trace-{uuid.uuid4().hex}"
        )
        try:
            if image is not None:
                message_media = [self.message_media.persist(user_message_id, image)]
            vision_state = self._prepare_vision_state(
                image=image,
                safe_message=safe_message,
                trace_id=trace_id,
                tenant_id=principal.tenant_id,
                message_media=message_media,
            )
            state = self.graph.invoke(
                {
                    **self._graph_input(
                        principal=principal,
                        internal_session_id=internal_session_id,
                        session_id=session_id,
                        execution_mode=execution_mode,
                        invocation=invocation,
                        safe_message=safe_message,
                        input_redacted=input_redacted,
                        trusted_context=trusted_context,
                    ),
                    "trace_id": trace_id,
                    "user_message_id": user_message_id,
                    "message_media": message_media,
                    **vision_state,
                },
                config={"configurable": {"thread_id": internal_session_id}},
            )
        except Exception as exc:
            self._cleanup_unpersisted_message_media(user_message_id, message_media)
            duration_ms = (time.perf_counter() - started) * 1000
            failure_trace = f"trace-error-{uuid.uuid4().hex}"
            self.db.record_metric(
                trace_id=failure_trace,
                tenant_id=principal.tenant_id,
                session_id=internal_session_id,
                intent="unknown",
                route_reason="unhandled_error",
                success=False,
                model_fallback=False,
                requires_human=True,
                duration_ms=duration_ms,
            )
            self.db.audit(
                "chat.failed",
                principal.client_id,
                failure_trace,
                {"error_type": type(exc).__name__},
                principal.tenant_id,
            )
            if invocation is not None:
                with self.db._write_lock, self.db.connect() as conn:
                    conn.execute(
                        """
                        UPDATE agent_invocations SET last_error=?, updated_at=?
                        WHERE id=? AND tenant_id=? AND status='running'
                        """,
                        (
                            f"{type(exc).__name__}: {str(exc)[:300]}",
                            utc_now(),
                            invocation["id"],
                            principal.tenant_id,
                        ),
                    )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        self.db.record_metric(
            trace_id=state["trace_id"],
            tenant_id=principal.tenant_id,
            session_id=internal_session_id,
            intent=state["intent"],
            route_reason=state["route_reason"],
            success=True,
            model_fallback=state["model_fallback"],
            requires_human=state["requires_human"],
            duration_ms=duration_ms,
        )
        if invocation is not None:
            with self.db.connect() as conn:
                saved_invocation = conn.execute(
                    "SELECT * FROM agent_invocations WHERE id=? AND tenant_id=?",
                    (invocation["id"], principal.tenant_id),
                ).fetchone()
            if saved_invocation is None or saved_invocation["status"] != "completed":
                raise RuntimeError("idempotent agent invocation did not reach a durable result")
            return self.invocation_response(dict(saved_invocation))

        return self.response_from_state(state, session_id)

    def chat_stream(
        self,
        principal: Principal,
        session_id: str,
        message: str,
        context: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None,
        source_type: str = "api",
        source_reference: str | None = None,
        image: ChatImageInput | None = None,
    ) -> Iterator[dict[str, Any]]:
        # 延迟导入：见 _compile_graph
        from ..graph import verify_response

        internal_session_id = self.db.resolve_session(
            tenant_id=principal.tenant_id,
            client_id=principal.client_id,
            external_session_id=session_id,
            subject_hash=principal.subject_hash,
            source_type=source_type,
            source_reference=source_reference,
        )
        safe_message, input_redacted, trusted_context, image_digest = (
            self._prepare_chat_content(principal, message, context, image)
        )

        invocation: dict[str, Any] | None = None
        if idempotency_key is not None:
            invocation = self.prepare_invocation(
                principal=principal,
                internal_session_id=internal_session_id,
                idempotency_key=idempotency_key,
                safe_message=safe_message,
                trusted_context=trusted_context,
                execution_mode="live",
                image_digest=image_digest,
            )
            if invocation["status"] == "completed":
                response = self.invocation_response(invocation)
                yield {
                    "event": "meta",
                    "session_id": response.session_id,
                    "message_id": response.message_id,
                    "trace_id": response.trace_id,
                    "vision_status": response.vision_status,
                    "vision_model": response.vision_model,
                    "vision_latency_ms": response.vision_latency_ms,
                }
                yield {
                    "event": "delta",
                    "text": response.answer,
                    "replay": True,
                }
                yield {"event": "result", "response": response.model_dump()}
                return
        user_message_id = (
            str(invocation["user_message_id"])
            if invocation
            else f"msg-user-{uuid.uuid4().hex}"
        )
        message_media: list[dict[str, Any]] = []
        config = {"configurable": {"thread_id": internal_session_id}}
        started = time.perf_counter()
        trace_id = (
            str(invocation["trace_id"])
            if invocation
            else f"trace-{uuid.uuid4().hex}"
        )
        try:
            if image is not None:
                message_media = [self.message_media.persist(user_message_id, image)]
            vision_state = self._prepare_vision_state(
                image=image,
                safe_message=safe_message,
                trace_id=trace_id,
                tenant_id=principal.tenant_id,
                message_media=message_media,
            )
            state = self.graph.invoke(
                {
                    **self._graph_input(
                        principal=principal,
                        internal_session_id=internal_session_id,
                        session_id=session_id,
                        execution_mode="live",
                        invocation=invocation,
                        safe_message=safe_message,
                        input_redacted=input_redacted,
                        trusted_context=trusted_context,
                    ),
                    "trace_id": trace_id,
                    "user_message_id": user_message_id,
                    "message_media": message_media,
                    **vision_state,
                },
                config=config,
                interrupt_before=["generate"],
            )
            yield {
                "event": "meta",
                "session_id": session_id,
                "message_id": state["message_id"],
                "trace_id": state["trace_id"],
                "vision_status": state.get("vision_status", "not_applicable"),
                "vision_model": state.get("vision_model"),
                "vision_latency_ms": state.get("vision_latency_ms"),
            }

            if "generate" in self.graph.get_state(config).next:
                plan = self.plan_generation(state)
                parts: list[str] = []
                retry_advised = False
                try:
                    deltas, model_fallback, trace_step = self.generation_deltas(state)
                    for delta in deltas:
                        parts.append(delta)
                    draft = "".join(parts).strip()
                except ModelError as exc:
                    recovery = recover_model_failure(state, exc, db=self.db)
                    draft = recovery.draft
                    model_fallback = recovery.model_fallback
                    retry_advised = recovery.retry_advised
                    trace_step = recovery.trace_step
                generation_trace = [*state["trace"]]
                if plan.budget_trace:
                    generation_trace.append(plan.budget_trace)
                generation_trace.append(trace_step)
                generation_update = {
                    "draft": draft,
                    "model_fallback": model_fallback,
                    "model_retry_advised": retry_advised,
                    "trace": generation_trace,
                }
                if retry_advised:
                    self.graph.update_state(config, generation_update, as_node="generate")
                    state = self.graph.invoke(None, config=config)
                else:
                    verified = verify_response({**state, **generation_update})
                    self.graph.update_state(
                        config,
                        {**generation_update, **verified},
                        as_node="verify",
                    )
                    state = self.graph.invoke(None, config=config)
            yield {"event": "delta", "text": state["answer"]}
        except BaseException:
            self._cleanup_unpersisted_message_media(user_message_id, message_media)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        self.db.record_metric(
            trace_id=state["trace_id"],
            tenant_id=principal.tenant_id,
            session_id=internal_session_id,
            intent=state["intent"],
            route_reason=state["route_reason"],
            success=True,
            model_fallback=state["model_fallback"],
            requires_human=state["requires_human"],
            duration_ms=duration_ms,
        )
        response = self.response_from_state(state, session_id)
        yield {"event": "result", "response": response.model_dump()}

    def plan_generation(self, state: dict[str, Any]) -> GenerationPlan:
        """两条通道共用的生成分支决定（审计 P0-2）。"""
        return plan_generation(state, settings=self.settings, db=self.db)

    def generation_deltas(
        self,
        state: dict[str, Any],
    ) -> tuple[Iterator[str], bool, str]:
        plan = self.plan_generation(state)
        if plan.branch != BRANCH_MODEL:
            return iter((plan.text or "",)), plan.model_fallback, str(plan.trace_step)
        return self.model.stream_generate(plan.messages or []), False, "generate:stream"

    def _trusted_context(
        self,
        principal: Principal,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        untrusted_context = dict(context or {})
        untrusted_context.pop("authorized", None)
        trusted_context = sanitize_context(untrusted_context)
        if principal.can_supply_order_context:
            trusted_context["authorized"] = True
        else:
            for field in UNTRUSTED_ORDER_FIELDS:
                trusted_context.pop(field, None)
        return trusted_context

    def _prepare_chat_content(
        self,
        principal: Principal,
        message: str,
        context: dict[str, Any] | None,
        image: ChatImageInput | None,
    ) -> tuple[str, bool, dict[str, Any], str | None]:
        effective_message = message
        if not effective_message.strip():
            if image is None:
                raise ValueError("message or image is required")
            effective_message = "请根据我发送的图片说明相关信息。"
        safe_message, input_redacted = redact_sensitive(effective_message)
        trusted_context = self._trusted_context(principal, context)
        image_digest = (
            hashlib.sha256(image.decoded_bytes()).hexdigest()
            if image is not None
            else None
        )
        return safe_message, input_redacted, trusted_context, image_digest

    def _cleanup_unpersisted_message_media(
        self,
        user_message_id: str,
        media: list[dict[str, Any]],
    ) -> None:
        if not media:
            return
        with self.db._write_lock, self.db.connect() as conn:
            persisted = conn.execute(
                "SELECT 1 FROM messages WHERE id=?",
                (user_message_id,),
            ).fetchone()
            if persisted is not None:
                return
            enqueue_media_deletions(conn, media, queued_at=utc_now())
        storage_refs = [str(item["storage_ref"]) for item in media]
        try:
            self.message_media.remove(media)
        except (OSError, ValueError) as exc:
            with self.db._write_lock, self.db.connect() as conn:
                for storage_ref in storage_refs:
                    mark_media_deletion_failed(
                        conn,
                        storage_ref=storage_ref,
                        error=exc,
                        updated_at=utc_now(),
                    )
            return
        with self.db._write_lock, self.db.connect() as conn:
            clear_media_deletions(conn, storage_refs)

    def _prepare_vision_state(
        self,
        *,
        image: ChatImageInput | None,
        safe_message: str,
        trace_id: str,
        tenant_id: str,
        message_media: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if image is None:
            return {
                "media_evidence": {},
                "vision_status": "not_applicable",
                "vision_model": None,
                "vision_latency_ms": None,
                "vision_image_count": 0,
            }
        started = time.perf_counter()
        try:
            result = self.vision.describe(image=image, user_message=safe_message)
        except Exception as exc:
            result = VisionResult(
                description="",
                status="error",
                applied=False,
                latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
                model=(
                    self.settings.vision_model_name
                    if self.settings.vision_enabled
                    else None
                ),
                image_count=1,
                error_type=type(exc).__name__,
            )
        self.db.audit(
            "media.vision",
            "system",
            trace_id,
            result.audit_detail(),
            tenant_id,
        )
        if result.applied and result.description and message_media:
            # 观察随消息媒体元数据留存，后续轮次的历史可以带回图片内容
            attach_vision_description(message_media, result.description)
        return {
            "media_evidence": result.media_evidence(),
            "vision_status": result.status,
            "vision_model": result.model,
            "vision_latency_ms": result.latency_ms,
            "vision_image_count": result.image_count,
        }

    def purge_expired(self, *, actor: str, dry_run: bool) -> dict[str, Any]:
        from ..maintenance import MaintenanceService

        return MaintenanceService(
            self.db,
            self.settings,
            media_store=self.message_media,
        ).purge_expired(actor=actor, dry_run=dry_run)

    @staticmethod
    def _graph_input(
        *,
        principal: Principal,
        internal_session_id: str,
        session_id: str,
        execution_mode: str,
        invocation: dict[str, Any] | None,
        safe_message: str,
        input_redacted: bool,
        trusted_context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "session_id": internal_session_id,
            "external_session_id": session_id,
            "tenant_id": principal.tenant_id,
            "client_id": principal.client_id,
            "subject_hash": principal.subject_hash,
            "execution_mode": execution_mode,
            "invocation_id": invocation["id"] if invocation else None,
            "trace_id": invocation["trace_id"] if invocation else None,
            "message_id": invocation["assistant_message_id"] if invocation else None,
            "user_message_id": invocation["user_message_id"] if invocation else None,
            "user_input": safe_message,
            "input_redacted": input_redacted,
            "context": trusted_context,
        }

    @staticmethod
    def response_from_state(
        state: dict[str, Any],
        session_id: str,
    ) -> ChatResponse:
        return chat_response_from_state(state, session_id)

    def prepare_invocation(
        self,
        *,
        principal: Principal,
        internal_session_id: str,
        idempotency_key: str,
        safe_message: str,
        trusted_context: dict[str, Any],
        execution_mode: str,
        image_digest: str | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("agent idempotency key must contain 1 to 200 characters")
        request_hash = hashlib.sha256(
            json.dumps(
                {
                    "session_id": internal_session_id,
                    "message": safe_message,
                    "context": trusted_context,
                    "execution_mode": execution_mode,
                    "image_digest": image_digest,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        stable = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"yunpai:{principal.tenant_id}:{principal.client_id}:{idempotency_key}",
        ).hex
        now = utc_now()
        with self.db._write_lock, self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM agent_invocations
                WHERE tenant_id=? AND client_id=? AND idempotency_key=?
                """,
                (principal.tenant_id, principal.client_id, idempotency_key),
            ).fetchone()
            if row is None:
                invocation_id = f"invocation-{stable}"
                conn.execute(
                    """
                    INSERT INTO agent_invocations(
                        id, tenant_id, client_id, session_id, idempotency_key,
                        request_hash, trace_id, user_message_id, assistant_message_id,
                        status, response_json, attempt_count, last_error,
                        created_at, updated_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', NULL, 1, NULL,
                              ?, ?, NULL)
                    """,
                    (
                        invocation_id,
                        principal.tenant_id,
                        principal.client_id,
                        internal_session_id,
                        idempotency_key,
                        request_hash,
                        f"trace-{stable}",
                        f"msg-user-{stable}",
                        f"msg-{stable}",
                        now,
                        now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM agent_invocations WHERE id=?", (invocation_id,)
                ).fetchone()
            else:
                if (
                    row["session_id"] != internal_session_id
                    or row["request_hash"] != request_hash
                ):
                    raise SessionScopeError(
                        "agent idempotency key is already bound to another request",
                        code="idempotency_key_conflict",
                    )
                if row["status"] == "running":
                    conn.execute(
                        """
                        UPDATE agent_invocations
                        SET attempt_count=attempt_count+1, last_error=NULL, updated_at=?
                        WHERE id=? AND status='running'
                        """,
                        (now, row["id"]),
                    )
                    row = conn.execute(
                        "SELECT * FROM agent_invocations WHERE id=?", (row["id"],)
                    ).fetchone()
        if row is None:
            raise RuntimeError("agent invocation was not persisted")
        return dict(row)

    @staticmethod
    def invocation_response(invocation: dict[str, Any]) -> ChatResponse:
        payload = invocation.get("response_json")
        if not payload:
            raise RuntimeError("completed agent invocation has no response")
        return ChatResponse.model_validate(json.loads(str(payload)))
