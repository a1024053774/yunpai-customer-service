from __future__ import annotations

import math
import uuid
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from .database import Database
from .embeddings import EmbeddingProvider, HashEmbeddingProvider
from .intent import INTENT_ROUTING, routing_for_intent
from .schemas import RetrievedDocument
from .text_utils import (
    blob_to_vector,
    checksum,
    cosine_similarity,
    normalize_text,
    product_identifiers,
    search_terms,
    search_text,
    vector_to_blob,
)


class KnowledgeBase:
    def __init__(
        self, db: Database, *, embedding_provider: EmbeddingProvider | None = None
    ):
        self.db = db
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()

    def _embedding_identity(self) -> str:
        identity = getattr(self.embedding_provider, "identity", None)
        if identity:
            return str(identity)
        return str(self.embedding_provider.name)

    def count_active(self, tenant_id: str | None = None) -> int:
        where = "status='active'"
        params: tuple[Any, ...] = ()
        if tenant_id is not None:
            where += " AND (tenant_id IS NULL OR tenant_id=?)"
            params = (tenant_id,)
        with self.db.connect() as conn:
            return int(
                conn.execute(f"SELECT COUNT(*) FROM knowledge WHERE {where}", params).fetchone()[0]
            )

    def seed_if_empty(self, records: list[dict[str, Any]]) -> int:
        with self.db.connect() as conn:
            global_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM knowledge WHERE status='active' AND tenant_id IS NULL"
                ).fetchone()[0]
            )
        if global_count > 0:
            return 0
        for record in records:
            self.add_document(
                **record,
                status="active",
                approved_by="builtin",
                tenant_id=None,
            )
        self.db.audit("knowledge.seeded", "system", None, {"count": len(records)})
        return len(records)

    def add_document(
        self,
        *,
        category: str,
        intent: str,
        question: str,
        answer: str,
        keywords: str,
        risk_level: str,
        source: str,
        version: int = 1,
        id: str | None = None,
        status: str = "active",
        approved_by: str | None = None,
        tenant_id: str | None = None,
        knowledge_key: str | None = None,
        layer: str = "industry",
        store_id: str | None = None,
        sku_id: str | None = None,
        subject_hash: str | None = None,
        review_status: str | None = None,
    ) -> str:
        document_id = id or f"kb-{uuid.uuid4().hex}"
        document_key = knowledge_key or document_id
        indexed_text = search_text(question, answer, keywords, category, intent)
        embedding = vector_to_blob(
            self.embedding_provider.embed_document(f"{question} {keywords} {answer}")
        )
        embedding_model = self._embedding_identity()
        now = datetime.now(UTC).isoformat()
        digest = checksum(
            question, answer, source, str(version), tenant_id or "global",
            layer, store_id or "", sku_id or "", subject_hash or "",
        )
        lifecycle = review_status or ("approved" if status == "active" else "draft")
        with self.db._write_lock, self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge(
                    id, category, intent, question, answer, keywords, search_text,
                    embedding, embedding_model, risk_level, source, version, status, effective_from,
                    effective_to, approved_by, checksum, created_at, tenant_id,
                    knowledge_key, layer, store_id, sku_id, subject_hash, review_status,
                    record_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    document_id, category, intent, question, answer, keywords,
                    indexed_text, embedding, embedding_model, risk_level, source, version, status,
                    now, approved_by, digest, now, tenant_id,
                    document_key, layer, store_id, sku_id, subject_hash, lifecycle, now,
                ),
            )
            conn.execute(
                "INSERT INTO knowledge_fts(doc_id, search_text) VALUES (?, ?)",
                (document_id, indexed_text),
            )
        return document_id

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        min_score: float,
        intent: str | None = None,
        tenant_id: str | None = None,
        store_id: str | None = None,
        sku_id: str | None = None,
        rollout_unit: str | None = None,
    ) -> list[RetrievedDocument]:
        query_terms = set(search_terms(query))
        query_identifiers = product_identifiers(query)
        query_vector = self.embedding_provider.embed_query(query)
        normalized_query = normalize_text(query)
        now = datetime.now(UTC).isoformat()
        with self.db.connect() as conn:
            tenant_clause = (
                "AND tenant_id IS NULL"
                if tenant_id is None
                else "AND (tenant_id IS NULL OR tenant_id=?)"
            )
            scope_clauses = []
            scope_params: list[Any] = []
            if store_id is None:
                scope_clauses.append("AND store_id IS NULL")
            else:
                scope_clauses.append("AND (store_id IS NULL OR store_id=?)")
                scope_params.append(store_id)
            if sku_id is None:
                scope_clauses.append("AND sku_id IS NULL")
            else:
                scope_clauses.append("AND (sku_id IS NULL OR sku_id=?)")
                scope_params.append(sku_id)
            params: tuple[Any, ...] = (
                (now, now, *scope_params)
                if tenant_id is None
                else (now, now, tenant_id, *scope_params)
            )
            rows = conn.execute(
                f"""
                SELECT id, knowledge_key, category, intent, question, answer, keywords,
                       search_text, embedding, embedding_model, source, version, layer, store_id,
                       sku_id, tenant_id
                FROM knowledge
                WHERE status='active' AND effective_from <= ?
                  AND (effective_to IS NULL OR effective_to > ?)
                  AND subject_hash IS NULL
                  AND layer <> 'memory'
                  AND knowledge_key NOT LIKE 'kg-memory-%'
                  {tenant_clause}
                  {' '.join(scope_clauses)}
                """,
                params,
            ).fetchall()
        rows = self._apply_rollouts(
            [dict(row) for row in rows],
            tenant_id=tenant_id,
            rollout_unit=rollout_unit,
            scope_clauses=scope_clauses,
            scope_params=scope_params,
        )
        current_identity = self._embedding_identity()
        rows = [
            row
            for row in rows
            if not row.get("embedding_model") or row.get("embedding_model") == current_identity
        ]

        # BM25 supplies corpus-aware lexical relevance for short Chinese queries.  It is
        # combined with the persisted dense vector score below, so exact terms remain
        # useful without making a keyword table the semantic authority.
        document_frequency: Counter[str] = Counter()
        document_lengths: list[int] = []
        for row in rows:
            terms = row["search_text"].split()
            document_lengths.append(len(terms))
            document_frequency.update(set(terms))
        average_document_length = sum(document_lengths) / max(1, len(document_lengths))

        ranked: list[RetrievedDocument] = []
        for row in rows:
            score = self._score(
                query_terms,
                query_vector,
                row,
                intent,
                document_frequency=document_frequency,
                document_count=len(rows),
                average_document_length=average_document_length,
                query_identifiers=query_identifiers,
            )
            if score < min_score:
                continue
            ranked.append(
                RetrievedDocument(
                    id=row["id"], knowledge_key=row["knowledge_key"],
                    category=row["category"], intent=row["intent"],
                    question=row["question"], answer=row["answer"], source=row["source"],
                    version=row["version"], score=round(score, 4),
                    layer=row["layer"], store_id=row["store_id"], sku_id=row["sku_id"],
                    tenant_id=row["tenant_id"],
                )
            )
        ranked.sort(
            key=lambda item: (
                int(normalize_text(item["question"]) == normalized_query),
                item["score"],
                # ① 多租户 tiebreak：本租户行优先于全局行（影子编辑生效的前提）。
                # 此前本租户影子行与全局行同分同 store NULL 同 version 时排序
                # 不稳定，seen_answers 去重还可能把影子答案丢掉。
                int(item["tenant_id"] == tenant_id),
                int(item["sku_id"] is not None),
                int(item["store_id"] is not None),
                item["version"],
            ),
            reverse=True,
        )

        # Avoid returning three paraphrases with the exact same answer.
        unique: list[RetrievedDocument] = []
        seen_answers: set[str] = set()
        for item in ranked:
            if item["answer"] in seen_answers:
                continue
            seen_answers.add(item["answer"])
            unique.append(item)
            if len(unique) >= top_k:
                break
        return unique

    def _apply_rollouts(
        self,
        rows: list[dict[str, Any]],
        *,
        tenant_id: str | None,
        rollout_unit: str | None,
        scope_clauses: list[str],
        scope_params: list[Any],
    ) -> list[dict[str, Any]]:
        """Serve gray-release candidates to in-bucket units, baselines to the rest.

        Without a rollout unit every caller stays on the approved baseline, so
        evaluation and evolution paths never observe half-released knowledge.
        """
        if tenant_id is None or rollout_unit is None:
            return rows
        from .rollouts import active_rollouts, rollout_choice

        chosen: dict[str, str] = {}
        for rollout in active_rollouts(self.db, tenant_id, "knowledge"):
            candidate_id = rollout_choice(rollout, rollout_unit)
            if candidate_id is not None:
                chosen[str(rollout["subject_key"])] = candidate_id
        if not chosen:
            return rows
        placeholders = ",".join("?" for _ in chosen)
        with self.db.connect() as conn:
            candidates = conn.execute(
                f"""
                SELECT id, knowledge_key, category, intent, question, answer, keywords,
                       search_text, embedding, embedding_model, source, version, layer, store_id,
                       sku_id, tenant_id
                FROM knowledge
                WHERE status='candidate' AND tenant_id=? AND id IN ({placeholders})
                  AND subject_hash IS NULL
                  AND layer <> 'memory'
                  AND knowledge_key NOT LIKE 'kg-memory-%'
                  {' '.join(scope_clauses)}
                """,
                (tenant_id, *chosen.values(), *scope_params),
            ).fetchall()
        replaced = [
            row for row in rows if str(row["knowledge_key"]) not in chosen
        ]
        replaced.extend(dict(row) for row in candidates)
        return replaced

    def candidate_score(
        self,
        query: str,
        *,
        intent: str,
        query_intent: str | None = None,
        question: str,
        answer: str,
        keywords: str = "",
        category: str = "进化话术",
    ) -> float:
        record = {
            "intent": intent,
            "question": question,
            "answer": answer,
            "keywords": keywords,
            "search_text": search_text(question, answer, keywords, category, intent),
            "embedding": vector_to_blob(
                self.embedding_provider.embed_document(f"{question} {keywords} {answer}")
            ),
        }
        return round(
            self._score(
                set(search_terms(query)),
                self.embedding_provider.embed_query(query),
                record,
                query_intent if query_intent is not None else intent,
                document_frequency=None,
                document_count=1,
                average_document_length=None,
                query_identifiers=product_identifiers(query),
            ),
            4,
        )

    def rebuild_embeddings(self, *, tenant_id: str | None = None) -> int:
        """Re-encode existing rows after selecting a different embedding backend."""
        query = "SELECT id, question, keywords, answer FROM knowledge"
        params: tuple[Any, ...] = ()
        if tenant_id is not None:
            query += " WHERE tenant_id=?"
            params = (tenant_id,)
        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        updated = 0
        identity = self._embedding_identity()
        with self.db._write_lock, self.db.connect() as conn:
            for row in rows:
                text = f"{row['question']} {row['keywords']} {row['answer']}"
                embedding = vector_to_blob(
                    self.embedding_provider.embed_document(text)
                )
                conn.execute(
                    "UPDATE knowledge SET embedding=?, embedding_model=?, updated_at=? WHERE id=?",
                    (embedding, identity, datetime.now(UTC).isoformat(), row["id"]),
                )
                updated += 1
        return updated

    @staticmethod
    def _score(
        query_terms: set[str],
        query_vector: Sequence[float],
        document: Any,
        intent: str | None,
        *,
        document_frequency: Counter[str] | None = None,
        document_count: int = 1,
        average_document_length: float | None = None,
        query_identifiers: Sequence[str] = (),
    ) -> float:
        document_tokens = document["search_text"].split()
        if document_frequency is None:
            document_frequency = Counter({term: 1 for term in set(document_tokens)})
        average_document_length = average_document_length or float(max(1, len(document_tokens)))
        # Robertson/Sparck Jones BM25 with a bounded transform keeps the existing score
        # contract (0..1-ish) while accounting for term frequency and corpus rarity.
        k1, b = 1.2, 0.75
        frequencies = Counter(document_tokens)
        bm25 = 0.0
        for term in query_terms:
            tf = frequencies.get(term, 0)
            if not tf:
                continue
            df = document_frequency.get(term, 0)
            idf = math.log(1.0 + (document_count - df + 0.5) / (df + 0.5))
            norm = tf + k1 * (1.0 - b + b * len(document_tokens) / average_document_length)
            bm25 += idf * (tf * (k1 + 1.0) / norm)
        lexical = bm25 / (1.0 + bm25)
        stored_vector = blob_to_vector(document["embedding"])
        # A provider switch is safe before reindexing: incompatible dimensions must not
        # be compared by zip truncation, while BM25 can still retrieve the old rows.
        semantic = (
            max(0.0, cosine_similarity(query_vector, stored_vector))
            if len(query_vector) == len(stored_vector)
            else 0.0
        )
        stored_intent = document["intent"]
        if stored_intent in INTENT_ROUTING:
            stored_intent = routing_for_intent(stored_intent)["knowledge_intent"]
        intent_bonus = 0.12 if intent and stored_intent == intent else 0.0
        identifier_bonus = 0.0
        if query_identifiers:
            haystack = " ".join(
                str(document.get(key) or "")
                for key in ("question", "answer", "keywords", "search_text")
            ).lower()
            if any(identifier in haystack for identifier in query_identifiers):
                identifier_bonus = 0.2
        return 0.55 * semantic + 0.45 * lexical + intent_bonus + identifier_bonus

    def next_version(self, intent: str, tenant_id: str | None = None) -> int:
        # 多租户低项：版本命名空间按租户隔离——租户 evolution 的版本号
        # 不受全局同 intent 行影响（此前 NULL 分支混入全局行导致跳号/撞号）
        tenant_clause = (
            "tenant_id IS NULL" if tenant_id is None else "tenant_id=?"
        )
        params: tuple[Any, ...] = (intent,) if tenant_id is None else (intent, tenant_id)
        with self.db.connect() as conn:
            row = conn.execute(
                f"SELECT COALESCE(MAX(version), 0) + 1 FROM knowledge "
                f"WHERE intent=? AND {tenant_clause}",
                params,
            ).fetchone()
        return int(row[0])

    def find_by_knowledge_key(
        self, knowledge_key: str, tenant_id: str | None = None
    ) -> dict[str, Any] | None:
        query = "SELECT * FROM knowledge WHERE knowledge_key=?"
        params: tuple[Any, ...] = (knowledge_key,)
        if tenant_id is not None:
            query += " AND tenant_id=?"
            params = (knowledge_key, tenant_id)
        with self.db.connect() as conn:
            row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def get_document(
        self, document_id: str, tenant_id: str | None = None
    ) -> dict[str, Any] | None:
        query = "SELECT * FROM knowledge WHERE id = ?"
        params: tuple[Any, ...] = (document_id,)
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params = (document_id, tenant_id)
        with self.db.connect() as conn:
            row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def retire_document(
        self, document_id: str, actor: str, tenant_id: str | None = None
    ) -> bool:
        tenant_clause = "tenant_id IS NULL" if tenant_id is None else "tenant_id=?"
        params: tuple[Any, ...] = (
            (datetime.now(UTC).isoformat(), document_id)
            if tenant_id is None
            else (datetime.now(UTC).isoformat(), document_id, tenant_id)
        )
        with self.db._write_lock, self.db.connect() as conn:
            cursor = conn.execute(
                # 多租户低项：retire 递增 record_version（乐观锁可见性，
                # 对齐 knowledge_management 口径）
                f"UPDATE knowledge SET status='retired', effective_to=?, "
                f"record_version=record_version+1 "
                f"WHERE id=? AND status='active' AND {tenant_clause}",
                params,
            )
        changed = cursor.rowcount == 1
        if changed:
            self.db.audit("knowledge.retired", actor, document_id, {}, tenant_id)
        return changed
