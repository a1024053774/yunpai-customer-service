from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from .config import Settings
from .decision import extract_json_object


RATE_LIMIT_PROVIDER_CODES = frozenset({"1302", "1305", "1312"})


class ModelError(RuntimeError):
    pass


class ModelUnavailableError(ModelError):
    """Upstream model service was temporarily unreachable or rate limited.

    Distinguished from other model errors so the agent can invite the customer to
    retry instead of consuming a human handoff for an infrastructure hiccup.
    """


class ModelGateway:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self.settings = settings
        if (
            settings.model_enabled
            and "/api/coding/" in settings.model_base_url.lower()
            and not settings.model_allow_coding_plan
        ):
            raise ModelError(
                "GLM Coding Plan endpoint requires explicit local-test enablement; "
                "set MODEL_ALLOW_CODING_PLAN=true"
            )
        self._client = httpx.Client(
            timeout=settings.model_timeout_seconds,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            transport=transport,
            # mock 不访问外网；忽略 NO_PROXY 里的 `::1` 等条目，避免 httpx 把它们当成代理 URL
            trust_env=False if settings.model_mock_mode else True,
        )

    @property
    def _is_coding_plan_test(self) -> bool:
        return (
            self.settings.model_allow_coding_plan
            and "/api/coding/" in self.settings.model_base_url.lower()
        )

    @property
    def _uses_streaming(self) -> bool:
        # The Coding Plan test endpoint is invoked through Chat Completions,
        # but its long-lived SSE responses are not suitable for this local UI test.
        return self.settings.model_streaming and not self._is_coding_plan_test

    def generate(self, messages: list[dict[str, str]]) -> str:
        return self._generate_content(messages, json_mode=False)

    def stream_generate(self, messages: list[dict[str, str]]) -> Iterator[str]:
        if self.settings.model_mock_mode:
            yield from self._mock_generate(messages)
            return
        if not self.settings.model_enabled:
            raise ModelError("model integration is disabled")
        payload = self._chat_payload(messages, json_mode=False, stream=True)
        yield from self._stream_deltas(payload)

    def generate_json(
        self,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
        thinking_enabled: bool | None = None,
    ) -> dict[str, Any]:
        attempts = (
            1
            if timeout_seconds is not None
            else self.settings.model_retry_attempts + 1
        )
        last_error: ModelError | None = None
        for attempt in range(attempts):
            try:
                content = self._generate_content(
                    messages,
                    json_mode=True,
                    timeout_seconds=timeout_seconds,
                    max_tokens=max_tokens,
                    thinking_enabled=thinking_enabled,
                )
                return extract_json_object(content)
            except ValueError as exc:
                last_error = ModelError(str(exc))
            except ModelError as exc:
                last_error = exc
            if (
                last_error is None
                or attempt + 1 >= attempts
                or not self._should_retry_json_error(last_error)
            ):
                raise last_error
            time.sleep(min(0.2 * (attempt + 1), 0.5))
        raise AssertionError("structured generation retry loop did not return")

    @staticmethod
    def _should_retry_json_error(error: ModelError) -> bool:
        if isinstance(error, ModelUnavailableError):
            return False
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "empty content",
                "not valid json",
                "response did not match",
            )
        )

    def _generate_content(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
        thinking_enabled: bool | None = None,
    ) -> str:
        if self.settings.model_mock_mode:
            return self._mock_generate(messages)
        if not self.settings.model_enabled:
            raise ModelError("model integration is disabled")

        payload = self._chat_payload(
            messages,
            json_mode=json_mode,
            stream=self._uses_streaming,
            max_tokens=max_tokens,
            thinking_enabled=thinking_enabled,
        )
        if self._uses_streaming:
            try:
                return self._stream_request(payload, timeout_seconds=timeout_seconds)
            except ModelError as exc:
                # Retry only reasoning-only streams; other failures may follow output.
                if "empty content" not in str(exc).lower():
                    raise
                fallback_payload = {**payload, "stream": False}
                return self._content_from_response(
                    self._request(fallback_payload, timeout_seconds=timeout_seconds)
                )
        data = self._request(payload, timeout_seconds=timeout_seconds)
        try:
            return self._content_from_response(data)
        except ModelError as exc:
            if (
                "empty content" not in str(exc).lower()
                or self.settings.model_retry_attempts <= 0
            ):
                raise
            # Use the configured retry budget for transient empty responses.
            last_error = exc
            for attempt in range(self.settings.model_retry_attempts):
                time.sleep(min(0.2 * (attempt + 1), 0.5))
                try:
                    return self._content_from_response(
                        self._request(payload, timeout_seconds=timeout_seconds)
                    )
                except ModelError as retry_error:
                    last_error = retry_error
                    if "empty content" not in str(retry_error).lower():
                        raise
            raise last_error

    @staticmethod
    def _content_from_response(data: dict[str, Any]) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("model response did not match the chat completions schema") from exc
        if not isinstance(content, str) or not content.strip():
            raise ModelError("model returned empty content")
        return content.strip()

    def _chat_payload(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool,
        stream: bool,
        max_tokens: int | None = None,
        thinking_enabled: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model_name,
            "messages": messages,
            "temperature": self.settings.model_temperature,
            "max_tokens": (
                self.settings.model_max_output_tokens
                if max_tokens is None
                else max(1, int(max_tokens))
            ),
            "stream": stream,
        }
        if self.settings.model_provider == "glm":
            effective_thinking = (
                self.settings.model_thinking_enabled
                if thinking_enabled is None
                else thinking_enabled
            )
            payload["thinking"] = {
                "type": "enabled" if effective_thinking else "disabled"
            }
        elif self.settings.model_provider == "deepseek" and thinking_enabled is not None:
            payload["thinking"] = {
                "type": "enabled" if thinking_enabled else "disabled"
            }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def health(self) -> tuple[bool, str]:
        if self.settings.model_mock_mode:
            return True, "mock"
        if not self.settings.model_enabled:
            return False, "disabled"
        if not self.settings.model_api_key:
            return False, "api_key_missing"
        return True, "configured"

    def probe(self) -> dict[str, Any]:
        if not self.settings.model_enabled:
            raise ModelError("model integration is disabled")
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "model": self.settings.model_name,
            "messages": [
                {"role": "system", "content": "你是连通性探针。"},
                {"role": "user", "content": "只回复OK"},
            ],
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
        }
        if self.settings.model_provider in {"glm", "deepseek"}:
            payload["thinking"] = {"type": "disabled"}
        data = self._request(payload)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "ok": bool(str(content).strip()),
            "provider": self.settings.model_provider,
            "model": data.get("model", self.settings.model_name),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "usage": data.get("usage", {}),
        }

    def _request(
        self,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        attempts = (
            1
            if timeout_seconds is not None
            else self.settings.model_retry_attempts + 1
        )
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.post(
                    f"{self.settings.model_base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=(
                        timeout_seconds
                        if timeout_seconds is not None
                        else self.settings.model_timeout_seconds
                    ),
                )
                if self._is_retryable(response) and attempt + 1 < attempts:
                    time.sleep(min(0.2 * (attempt + 1), 0.5))
                    continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ModelError("model response is not a JSON object")
                return data
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < attempts and isinstance(
                    exc, (httpx.ConnectError, httpx.ConnectTimeout)
                ):
                    time.sleep(min(0.2 * (attempt + 1), 0.5))
                    continue
                break
        error_class = ModelUnavailableError if self._is_transient(last_error) else ModelError
        if isinstance(last_error, httpx.HTTPStatusError):
            status = last_error.response.status_code
            code = self._provider_code(last_error.response)
            raise error_class(
                f"model request failed with HTTP {status} (provider code {code})"
            ) from last_error
        raise error_class(f"model request failed: {type(last_error).__name__}") from last_error

    def _stream_request(
        self,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        return "".join(
            self._stream_deltas(payload, timeout_seconds=timeout_seconds)
        ).strip()

    def _stream_deltas(
        self,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> Iterator[str]:
        attempts = (
            1
            if timeout_seconds is not None
            else self.settings.model_retry_attempts + 1
        )
        last_error: Exception | None = None
        for attempt in range(attempts):
            emitted = False
            try:
                with self._client.stream(
                    "POST",
                    f"{self.settings.model_base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=(
                        timeout_seconds
                        if timeout_seconds is not None
                        else self.settings.model_timeout_seconds
                    ),
                ) as response:
                    if response.status_code >= 400:
                        # Error responses arrive as a regular JSON body instead of SSE.
                        # The stream must be consumed before the body can be inspected
                        # here or attached to the raised HTTPStatusError.
                        response.read()
                    if self._is_retryable(response) and attempt + 1 < attempts:
                        time.sleep(min(0.2 * (attempt + 1), 0.5))
                        continue
                    response.raise_for_status()
                    has_non_whitespace = False
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw_event = line.removeprefix("data:").strip()
                        if raw_event == "[DONE]":
                            break
                        event = json.loads(raw_event)
                        if "error" in event:
                            code = str(event.get("error", {}).get("code", "unknown"))
                            stream_error_class = (
                                ModelUnavailableError
                                if code in RATE_LIMIT_PROVIDER_CODES
                                else ModelError
                            )
                            raise stream_error_class(
                                f"model stream failed (provider code {code})"
                            )
                        delta = event.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            emitted = True
                            has_non_whitespace = has_non_whitespace or bool(
                                content.strip()
                            )
                            yield content
                    if not has_non_whitespace:
                        raise ModelError("model stream returned empty content")
                    return
            except ModelError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if not emitted and attempt + 1 < attempts and isinstance(
                    exc, (httpx.ConnectError, httpx.ConnectTimeout)
                ):
                    time.sleep(min(0.2 * (attempt + 1), 0.5))
                    continue
                break
        error_class = ModelUnavailableError if self._is_transient(last_error) else ModelError
        if isinstance(last_error, httpx.HTTPStatusError):
            status = last_error.response.status_code
            code = self._provider_code(last_error.response)
            raise error_class(
                f"model request failed with HTTP {status} (provider code {code})"
            ) from last_error
        raise error_class(f"model request failed: {type(last_error).__name__}") from last_error

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.model_api_key:
            headers["Authorization"] = f"Bearer {self.settings.model_api_key}"
        return headers

    def _is_transient(self, error: Exception | None) -> bool:
        """Rate limits, upstream 5xx and transport failures can succeed on a retry."""
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            return status >= 500 or (
                status == 429
                and self._provider_code(error.response) in RATE_LIMIT_PROVIDER_CODES
            )
        return isinstance(error, httpx.TransportError)

    def _is_retryable(self, response: httpx.Response) -> bool:
        if response.status_code in {500, 502, 503, 504}:
            return True
        return response.status_code == 429 and self._provider_code(response) in {
            "1305",
            "1312",
        }

    @staticmethod
    def _provider_code(response: httpx.Response) -> str:
        try:
            if not response.is_closed:
                response.read()
            return str(response.json().get("error", {}).get("code", "unknown"))
        except (AttributeError, ValueError, httpx.StreamError, httpx.HTTPError):
            return "unknown"

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _mock_generate(messages: list[dict[str, str]]) -> str:
        context = messages[-1]["content"]
        try:
            task = json.loads(context)
        except (TypeError, json.JSONDecodeError):
            task = {}
        if task.get("task_type") == "intent_classification":
            # Mock mode exercises the structured-model contract only.  It deliberately
            # does not inspect user text; semantic intent evidence must come from the live
            # shared model (or an injected table-driven test model).
            return json.dumps(
                {"intent": "product_inquiry", "confidence": 0.5},
                ensure_ascii=False,
            )
        if task.get("task_type") == "agent_decision":
            # A mock verifies wiring, not customer semantics; do not maintain a second
            # classifier or pretend a tool operation happened.
            return json.dumps({
                "intent": "general", "mode": "answer", "tool_name": None,
                "arguments": {}, "missing_fields": [], "expected_outcome": None,
                "response": None, "reason": "mock_contract_response", "confidence": 0.8,
            }, ensure_ascii=False)
        marker = "参考知识："
        if marker in context:
            knowledge = context.split(marker, 1)[1].split("\n\n当前会话", 1)[0]
            for line in knowledge.splitlines():
                if line.startswith("答案："):
                    return line.removeprefix("答案：").strip()
        return "当前信息不足，我会为您转人工客服进一步核对。"
