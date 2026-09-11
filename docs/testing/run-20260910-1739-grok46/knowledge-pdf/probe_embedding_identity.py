# -*- coding: utf-8 -*-
"""L0/L1 probe: embedding model identity persistence and same-dimension mix."""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path("/tmp/yunpai-test-candidate-grok46-pZG5r3")
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from yunpai_customer_service.database import Database  # noqa: E402
from yunpai_customer_service.embeddings import (  # noqa: E402
    FastEmbedProvider,
    HashEmbeddingProvider,
    build_embedding_provider,
)
from yunpai_customer_service.rag import KnowledgeBase  # noqa: E402
from yunpai_customer_service.text_utils import blob_to_vector  # noqa: E402

Q_CAPACITY = "\u7a7a\u6c14\u70b8\u9505\u5bb9\u91cf"
A_CAPACITY = "\u5bb9\u91cf 5L"
KW_CAPACITY = "\u5bb9\u91cf"


def _class_source(path: Path, class_name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.get_source_segment(text, node) or ""
    return ""


def inspect_static() -> dict:
    embeddings_path = SRC / "yunpai_customer_service" / "embeddings.py"
    rag_path = SRC / "yunpai_customer_service" / "rag.py"
    db_path = SRC / "yunpai_customer_service" / "database.py"
    rag_src = rag_path.read_text(encoding="utf-8")
    db_src = db_path.read_text(encoding="utf-8")
    fastembed_src = _class_source(embeddings_path, "FastEmbedProvider")
    hash_src = _class_source(embeddings_path, "HashEmbeddingProvider")
    identity_tokens = (
        "embedding_model",
        "embedding_provider TEXT",
        "vector_dim",
        "index_version",
    )
    return {
        "embeddings_py": str(embeddings_path),
        "fastembed_name_is_literal_fastembed": 'name = "fastembed"' in fastembed_src,
        "fastembed_stores_model_name_attribute": (
            "self.model_name" in fastembed_src or "self._model_name" in fastembed_src
        ),
        "hash_name_is_literal_hash": 'name = "hash"' in hash_src,
        "knowledge_table_columns_mention_model_identity": any(
            token in db_src for token in identity_tokens
        ),
        "rebuild_checks_model_identity": (
            "embedding_model" in rag_src or "model identity" in rag_src.lower()
        ),
        "score_behavior": (
            "len(query_vector)==len(stored_vector) then cosine; else semantic=0. "
            "No model-id check."
        ),
        "notes": (
            "FastEmbedProvider.name is the backend family string fastembed, not the "
            "concrete model id. Knowledge rows persist only the embedding BLOB."
        ),
    }


class FixedProvider:
    def __init__(self, name: str, vector: tuple[float, ...]):
        self.name = name
        self._vector = vector

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._vector

    def embed_document(self, text: str) -> tuple[float, ...]:
        return self._vector


def probe_same_dimension_mix() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "agent.sqlite3"
        db = Database(db_path)
        db.initialize()
        kb = KnowledgeBase(
            db,
            embedding_provider=FixedProvider("model-a", (1.0, 0.0, 0.0, 0.0)),
        )
        doc_id = kb.add_document(
            category="probe",
            intent="product",
            question=Q_CAPACITY,
            answer=A_CAPACITY,
            keywords=KW_CAPACITY,
            risk_level="low",
            source="probe:model-a",
            tenant_id="tenant-a",
        )
        with db.connect() as conn:
            stored = blob_to_vector(
                conn.execute(
                    "SELECT embedding FROM knowledge WHERE id=?",
                    (doc_id,),
                ).fetchone()[0]
            )
        kb.embedding_provider = FixedProvider("model-b", (0.0, 1.0, 0.0, 0.0))
        rejected = False
        error = None
        rows = []
        try:
            rows = kb.retrieve(
                Q_CAPACITY,
                top_k=5,
                min_score=0.01,
                intent="product",
                tenant_id="tenant-a",
            )
        except Exception as exc:
            rejected = True
            error = f"{type(exc).__name__}: {exc}"
        hit_ids = [row["id"] for row in rows]
        rebuilt = False
        rebuild_error = None
        try:
            kb.rebuild_embeddings(tenant_id="tenant-a")
            rebuilt = True
        except Exception as exc:
            rebuild_error = f"{type(exc).__name__}: {exc}"
        return {
            "stored_vector": list(stored),
            "query_vector_after_switch": [0.0, 1.0, 0.0, 0.0],
            "same_dimension": True,
            "different_model_names": ["model-a", "model-b"],
            "retrieve_raised": rejected,
            "error": error,
            "hit_ids": hit_ids,
            "document_still_retrievable": doc_id in hit_ids,
            "rebuild_without_identity_check": rebuilt,
            "rebuild_error": rebuild_error,
            "mix_rejected_or_migrated": rejected or (rebuild_error is not None and not rebuilt),
        }


def probe_hash_provider_contract() -> dict:
    provider = build_embedding_provider("hash", "unused-model-id")
    unknown_failed = False
    unknown_error = None
    try:
        build_embedding_provider("unknown", "unused")
    except ValueError as exc:
        unknown_failed = True
        unknown_error = str(exc)
    return {
        "hash_type": type(provider).__name__,
        "hash_is_HashEmbeddingProvider": isinstance(provider, HashEmbeddingProvider),
        "hash_name": getattr(provider, "name", None),
        "hash_ignores_model_argument": True,
        "unknown_provider_raises_value_error": unknown_failed,
        "unknown_error": unknown_error,
        "fastembed_class_name_attr": FastEmbedProvider.name,
    }


def main() -> int:
    out = {
        "static": inspect_static(),
        "hash_contract": probe_hash_provider_contract(),
        "same_dimension_mix": probe_same_dimension_mix(),
    }
    mix = out["same_dimension_mix"]
    static = out["static"]
    identity_persisted = (
        static["fastembed_stores_model_name_attribute"]
        and static["knowledge_table_columns_mention_model_identity"]
    )
    out["conclusions"] = {
        "model_identity_persisted": identity_persisted,
        "same_dimension_mix_rejected": bool(mix["mix_rejected_or_migrated"]),
        "d07_from_this_probe": "FAIL" if not mix["mix_rejected_or_migrated"] else "PASS",
        "reason": (
            "Same-dimension different-model vectors were retrieved without rejection "
            "or controlled migration. Model identity is not persisted on knowledge rows."
            if not mix["mix_rejected_or_migrated"]
            else "Mix was rejected at retrieve/rebuild."
        ),
    }
    dest = Path(__file__).with_name("probe_embedding_identity.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["conclusions"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
