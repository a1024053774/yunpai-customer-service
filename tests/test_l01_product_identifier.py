"""L01: FastEmbed still ranks generic SOP / Qingchuan above an ID+spec query.

G07 intent mapping is not enough. Hyphenated product IDs are split by search_terms,
so BM25 never sees the full SKU, and FastEmbed prefers ??/?? language in SOP.
"""

from __future__ import annotations

import pytest

from yunpai_customer_service.demo.catalog import DEMO_STORE_ID, seed_demo_store
from yunpai_customer_service.embeddings import FastEmbedProvider
from yunpai_customer_service.intent import routing_for_intent
from yunpai_customer_service.knowledge_ingest import ingest_document
from yunpai_customer_service.text_utils import product_identifiers

from customer_service_fixtures import build_core, principal_for_core

pytest.importorskip("fastembed")

PRODUCT_ID = "QA-GROK-2C2668E3"
CAPACITY_Q = f"{PRODUCT_ID} \u5bb9\u91cf\u548c\u989c\u8272\u662f\u4ec0\u4e48\uff1f"
SYNTHETIC_BODY = "\n".join(
    [
        "\u5b64\u5c9b\u9a8c\u6536\u7535\u70ed\u6c34\u58f6 \u4ea7\u54c1\u8bf4\u660e\u4e66",
        f"\u4ea7\u54c1\u578b\u53f7\uff1a{PRODUCT_ID}",
        "\u4ea7\u54c1\u540d\u79f0\uff1a\u5b64\u5c9b\u9a8c\u6536\u7535\u70ed\u6c34\u58f6",
        "\u989c\u8272\uff1a\u7c73\u767d",
        "\u5bb9\u91cf\uff1a5L",
        "\u6d4b\u8bd5\u6807\u4ef7\uff1a329 \u5143",
        "\u672c\u4ea7\u54c1\u4e0d\u53ef\u5fae\u6ce2\u3002",
    ]
)


def test_product_identifiers_keep_hyphenated_sku() -> None:
    assert "qa-grok-2c2668e3" in product_identifiers(CAPACITY_Q)
    assert product_identifiers("\u5bb9\u91cf\u548c\u989c\u8272\u662f\u4ec0\u4e48") == []


def test_fastembed_id_and_spec_query_ranks_imported_product_first(tmp_path) -> None:
    core = build_core(tmp_path, seed_knowledge=True)
    try:
        core.knowledge.embedding_provider = FastEmbedProvider("BAAI/bge-small-zh-v1.5")
        core.knowledge.rebuild_embeddings()
        principal = principal_for_core(core)
        seed_demo_store(core, tenant_id=principal.tenant_id)
        imported = ingest_document(
            core.knowledge,
            filename=f"synthetic-{PRODUCT_ID}.txt",
            content=SYNTHETIC_BODY.encode("utf-8"),
            tenant_id=principal.tenant_id,
            intent="product_inquiry",
        )
        doc_id = imported[0].id
        rows = core.knowledge.retrieve(
            CAPACITY_Q,
            top_k=3,
            min_score=core.settings.rag_min_score,
            intent=routing_for_intent("product_inquiry")["knowledge_intent"],
            tenant_id=principal.tenant_id,
            store_id=DEMO_STORE_ID,
        )
        assert rows, CAPACITY_Q
        ranked = [(item["id"], item["score"]) for item in rows]
        assert rows[0]["id"] == doc_id, ranked
        assert all(item["id"] != "seed-0007" or item["score"] < rows[0]["score"] for item in rows)
    finally:
        core.close()
