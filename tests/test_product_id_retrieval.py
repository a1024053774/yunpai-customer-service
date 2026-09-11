"""G07/L01: imported product docs must beat overlapping catalog SKUs.

Live import stores customer intent ``product_inquiry`` while retrieve uses
knowledge intent ``product``. Catalog rows already use ``product``, so they
get the 0.12 intent bonus and crowd out the uploaded SKU (same 5L / color /
price trap).
"""

from __future__ import annotations

from yunpai_customer_service.demo.catalog import DEMO_STORE_ID, seed_demo_store
from yunpai_customer_service.intent import routing_for_intent
from yunpai_customer_service.knowledge_ingest import ingest_document

from customer_service_fixtures import build_core, principal_for_core

PRODUCT_ID = "QA-FIX-G07A1"
MICROWAVE_Q = f"{PRODUCT_ID} \u53ef\u4ee5\u653e\u8fdb\u5fae\u6ce2\u7089\u52a0\u70ed\u5417\uff1f"
CAPACITY_Q = f"{PRODUCT_ID} \u5bb9\u91cf\u548c\u989c\u8272\u662f\u4ec0\u4e48\uff1f"
SYNTHETIC_BODY = "\n".join(
    [
        "\u5b64\u5c9b\u9a8c\u6536\u7535\u70ed\u6c34\u58f6 \u4ea7\u54c1\u8bf4\u660e\u4e66",
        f"\u4ea7\u54c1\u578b\u53f7\uff1a{PRODUCT_ID}",
        "\u4ea7\u54c1\u540d\u79f0\uff1a\u5b64\u5c9b\u9a8c\u6536\u7535\u70ed\u6c34\u58f6",
        "\u989c\u8272\uff1a\u7c73\u767d",
        "\u5bb9\u91cf\uff1a5L",
        "\u6d4b\u8bd5\u6807\u4ef7\uff1a329 \u5143",
        "\u672c\u4ea7\u54c1\u4e0d\u53ef\u5fae\u6ce2\u3002\u8d44\u6599\u4e0d\u8bb0\u8f7d\u5e93\u5b58\u3002",
    ]
)


def _imported_product(tmp_path):
    core = build_core(tmp_path, seed_knowledge=True)
    principal = principal_for_core(core)
    seed_demo_store(core, tenant_id=principal.tenant_id)
    imported = ingest_document(
        core.knowledge,
        filename=f"synthetic-{PRODUCT_ID}.txt",
        content=SYNTHETIC_BODY.encode("utf-8"),
        tenant_id=principal.tenant_id,
        intent="product_inquiry",
    )
    return core, principal, imported[0].id


def test_import_stores_knowledge_intent_not_customer_intent(tmp_path) -> None:
    core, principal, doc_id = _imported_product(tmp_path)
    try:
        row = core.knowledge.get_document(doc_id, tenant_id=principal.tenant_id)
        expected = routing_for_intent("product_inquiry")["knowledge_intent"]
        assert expected == "product"
        assert row["intent"] == expected
    finally:
        core.close()


def test_product_id_queries_retrieve_imported_doc_ahead_of_qingchuan(tmp_path) -> None:
    core, principal, doc_id = _imported_product(tmp_path)
    try:
        knowledge_intent = routing_for_intent("product_inquiry")["knowledge_intent"]
        for query in (MICROWAVE_Q, CAPACITY_Q, PRODUCT_ID):
            rows = core.knowledge.retrieve(
                query,
                top_k=3,
                min_score=core.settings.rag_min_score,
                intent=knowledge_intent,
                tenant_id=principal.tenant_id,
                store_id=DEMO_STORE_ID,
            )
            assert rows, query
            assert rows[0]["id"] == doc_id, (
                query,
                [(item["id"], item["score"], item["intent"]) for item in rows],
            )
    finally:
        core.close()
