"""Pluggable document/query embeddings for the knowledge base.

The demo uses a deterministic hash encoder so tests are offline and reproducible.  Hosts
can select FastEmbed with ``RAG_EMBEDDING_PROVIDER=fastembed`` and a multilingual model;
the knowledge-base API stays unchanged and can rebuild existing rows after switching.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .text_utils import hash_embedding


class EmbeddingProvider(Protocol):
    name: str
    identity: str

    def embed_query(self, text: str) -> Sequence[float]: ...

    def embed_document(self, text: str) -> Sequence[float]: ...


class HashEmbeddingProvider:
    name = "hash"
    identity = "hash"

    def embed_query(self, text: str) -> Sequence[float]:
        return hash_embedding(text)

    def embed_document(self, text: str) -> Sequence[float]:
        return hash_embedding(text)


class FastEmbedProvider:
    """Lazy FastEmbed adapter; model downloads happen only when explicitly selected."""

    name = "fastembed"

    def __init__(self, model_name: str):
        self.model_name = model_name
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "RAG_EMBEDDING_PROVIDER=fastembed requires the optional 'fastembed' package"
            ) from exc
        self._model = TextEmbedding(model_name=model_name)

    @property
    def identity(self) -> str:
        return f"fastembed:{self.model_name}"

    def _embed(self, text: str) -> Sequence[float]:
        vector = next(iter(self._model.embed([text])))
        return tuple(float(value) for value in vector)

    def embed_query(self, text: str) -> Sequence[float]:
        return self._embed(text)

    def embed_document(self, text: str) -> Sequence[float]:
        return self._embed(text)


def build_embedding_provider(provider: str, model_name: str) -> EmbeddingProvider:
    normalized = provider.strip().lower()
    if normalized in {"", "hash", "demo"}:
        return HashEmbeddingProvider()
    if normalized == "fastembed":
        return FastEmbedProvider(model_name)
    raise ValueError(f"unsupported RAG embedding provider: {provider}")
