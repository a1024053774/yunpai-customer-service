"""D07: same-dimension vectors from different embedding models must not mix."""

from __future__ import annotations

import inspect
from pathlib import Path

from yunpai_customer_service.database import Database
from yunpai_customer_service.embeddings import FastEmbedProvider, build_embedding_provider
from yunpai_customer_service.rag import KnowledgeBase


class FixedProvider:
    def __init__(self, identity: str, vector: tuple[float, ...]) -> None:
        self.name = identity
        self.identity = identity
        self.model_name = identity
        self._vector = vector

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._vector

    def embed_document(self, text: str) -> tuple[float, ...]:
        return self._vector


def test_fastembed_provider_keeps_concrete_model_identity() -> None:
    init_src = inspect.getsource(FastEmbedProvider.__init__)
    assert "self.model_name" in init_src
    identity_src = inspect.getsource(FastEmbedProvider)
    assert "identity" in identity_src


def test_same_dimension_different_model_is_not_retrieved(tmp_path: Path) -> None:
    db = Database(tmp_path / "agent.sqlite3")
    db.initialize()
    kb = KnowledgeBase(db, embedding_provider=FixedProvider("model-a", (1.0, 0.0, 0.0, 0.0)))
    doc_id = kb.add_document(
        category="probe",
        intent="product",
        question="\u7a7a\u6c14\u70b8\u9505\u5bb9\u91cf",
        answer="\u5bb9\u91cf 5L",
        keywords="\u5bb9\u91cf",
        risk_level="low",
        source="probe:model-a",
        tenant_id="tenant-a",
    )
    stored = kb.get_document(doc_id, tenant_id="tenant-a")
    assert stored is not None
    assert stored.get("embedding_model") == "model-a"

    kb.embedding_provider = FixedProvider("model-b", (0.0, 1.0, 0.0, 0.0))
    rows = kb.retrieve(
        "\u7a7a\u6c14\u70b8\u9505\u5bb9\u91cf",
        top_k=5,
        min_score=0.01,
        intent="product",
        tenant_id="tenant-a",
    )
    assert doc_id not in {item["id"] for item in rows}

    rebuilt = kb.rebuild_embeddings(tenant_id="tenant-a")
    assert rebuilt >= 1
    after = kb.get_document(doc_id, tenant_id="tenant-a")
    assert after is not None
    assert after.get("embedding_model") == "model-b"
    rows_after = kb.retrieve(
        "\u7a7a\u6c14\u70b8\u9505\u5bb9\u91cf",
        top_k=5,
        min_score=0.01,
        intent="product",
        tenant_id="tenant-a",
    )
    assert doc_id in {item["id"] for item in rows_after}


def test_hash_provider_identity_is_explicit() -> None:
    provider = build_embedding_provider("hash", "unused-model-id")
    assert getattr(provider, "identity", None) == "hash"
