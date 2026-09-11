from __future__ import annotations

import pytest

from yunpai_customer_service.embeddings import HashEmbeddingProvider, build_embedding_provider


def test_hash_provider_is_reproducible_and_explicit() -> None:
    provider = build_embedding_provider("hash", "unused")
    assert isinstance(provider, HashEmbeddingProvider)
    assert provider.embed_query("同一条问题") == provider.embed_query("同一条问题")


def test_unknown_embedding_provider_fails_at_configuration_boundary() -> None:
    with pytest.raises(ValueError, match="unsupported RAG embedding provider"):
        build_embedding_provider("unknown", "unused")
