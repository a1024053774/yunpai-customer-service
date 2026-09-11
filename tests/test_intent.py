from __future__ import annotations

import inspect
import json
from dataclasses import dataclass

from yunpai_customer_service.intent import classify
from yunpai_customer_service.llm import ModelGateway


@dataclass
class RecordingSharedModel:
    result: dict[str, object]
    calls: int = 0
    messages: list[dict[str, str]] | None = None

    @property
    def settings(self):
        return self

    intent_classify_timeout_seconds: float = 1.0

    def generate_json(self, messages, *, timeout_seconds):
        self.calls += 1
        self.messages = messages
        return self.result


def test_intent_keywords_do_not_bypass_shared_flash_model() -> None:
    model = RecordingSharedModel({"intent": "chitchat", "confidence": 0.77})

    result = classify("这款多少钱？", model=model)

    assert result.intent == "chitchat"
    assert result.method == "model"
    assert result.confidence == 0.77
    assert model.calls == 1
    task = json.loads(model.messages[-1]["content"])
    assert task["message"] == "这款多少钱？"
    assert "advisory_signals" not in task


def test_intent_model_receives_negation_as_complete_message() -> None:
    model = RecordingSharedModel({"intent": "chitchat", "confidence": 0.91})

    result = classify("不用办理退货了，多谢", model=model)

    assert result.intent == "chitchat"
    assert model.calls == 1
    task = json.loads(model.messages[-1]["content"])
    assert task["message"] == "不用办理退货了，多谢"


def test_gateway_has_no_separate_intent_model_override() -> None:
    parameters = inspect.signature(ModelGateway.generate_json).parameters

    assert "model_name" not in parameters
