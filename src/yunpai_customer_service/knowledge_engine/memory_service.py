"""知识库 memory 层写入服务（P1-2：让长期记忆真正可用）。

设计（对齐 KnowledgeScope.MEMORY 语义"默认隔离，显式查询才进"）：
- memory 知识 = 店铺级长期记忆（售后高频问题归纳、买家偏好、历史决策结论）
- 写入：layer='memory' + store_id=店铺；买家偏好额外绑定 subject_hash
- 读取：只通过 `recall()` 显式召回（对齐"默认隔离"）
- 幂等：同租户 / 店铺 / 买家作用域的同内容不重复写

与 evolution.py 的区别：
- evolution 是"反馈→候选→门禁→批准"的治理链路（需审批）
- 本服务是"运营/系统直接记录长期记忆"（低风险事实，直接写 active）
  适合：高频问题归纳、买家偏好（已脱敏）、运营决策结论
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ..rag import KnowledgeBase
from ..text_utils import normalize_text, redact_sensitive

logger = logging.getLogger("knowledge_engine.memory")

# memory 使用独立 layer；KnowledgeBase.retrieve 默认排除，只能显式召回。
MEMORY_LAYER = "memory"
# 记忆类别（业务语义）
MEMORY_CATEGORIES = {
    "buyer_preference": "买家偏好",
    "frequent_issue": "高频问题",
    "decision_note": "决策记录",
}
# 长期记忆默认 TTL：到期后不再被检索命中（P1-2 防事实过期后误答）
MEMORY_DEFAULT_TTL_DAYS = 180
MEMORY_MIN_RECALL_SCORE = 0.08


class KnowledgeMemoryService:
    """店铺级长期记忆写入/查询服务。"""

    def __init__(self, knowledge: KnowledgeBase) -> None:
        self.knowledge = knowledge

    def record(
        self,
        store_id: str,
        *,
        fact: str,
        category: str = "frequent_issue",
        source: str = "",
        tenant_id: str | None = None,
        subject_hash: str | None = None,
        ttl_days: int = MEMORY_DEFAULT_TTL_DAYS,
    ) -> str:
        """记录一条店铺级长期记忆（写 layer=memory，普通检索默认隔离）。

        参数：
            store_id: 店铺 id（记忆按店铺隔离）
            fact: 记忆内容（如"本店退货高峰在周三"）
            category: 记忆类别（buyer_preference/frequent_issue/decision_note）
            source: 证据来源（如"feedback://..."、"chat://..."）
            tenant_id: 租户
            subject_hash: 顾客匿名作用域；buyer_preference 必填
            ttl_days: 有效期天数（默认 180 天，到期后 recall/检索不再命中）

        返回：knowledge 行 id。
        """
        normalized_fact, _ = redact_sensitive(normalize_text(fact))
        if not store_id or not normalized_fact:
            raise ValueError("store_id 和 fact 必填")
        if ttl_days <= 0:
            raise ValueError("ttl_days 必须为正数")
        if category not in MEMORY_CATEGORIES:
            raise ValueError("unsupported memory category")
        if category == "buyer_preference" and not subject_hash:
            raise ValueError("buyer_preference requires subject_hash")
        now = datetime.now(UTC)
        expires = now + timedelta(days=ttl_days)
        now_iso = now.isoformat()
        expires_iso = expires.isoformat()
        # 同一作用域重复记录时复用原 ID 并续期；否则过期 active 行会被去重命中，
        # 但又永远无法被 recall 返回。
        dedup_sql = (
            "SELECT id, knowledge_key, effective_from, effective_to FROM knowledge "
            "WHERE layer=? AND store_id=? AND answer=? AND status='active' "
        )
        dedup_params: list[Any] = [MEMORY_LAYER, store_id, normalized_fact]
        if tenant_id is None:
            dedup_sql += " AND tenant_id IS NULL"
        else:
            dedup_sql += " AND tenant_id=?"
            dedup_params.append(tenant_id)
        if subject_hash is None:
            dedup_sql += " AND subject_hash IS NULL"
        else:
            dedup_sql += " AND subject_hash=?"
            dedup_params.append(subject_hash)
        dedup_sql += " LIMIT 1"
        with self.knowledge.db._write_lock:
            with self.knowledge.db.connect() as conn:
                existing_row = conn.execute(
                    dedup_sql, tuple(dedup_params)
                ).fetchone()
                if existing_row:
                    current_to = (
                        datetime.fromisoformat(str(existing_row["effective_to"]))
                        if existing_row["effective_to"]
                        else None
                    )
                    renewed_to = (
                        current_to.isoformat()
                        if current_to is not None and current_to > expires
                        else expires_iso
                    )
                    renewed_from = (
                        now_iso
                        if current_to is not None and current_to <= now
                        else str(existing_row["effective_from"] or now_iso)
                    )
                    conn.execute(
                        """
                        UPDATE knowledge
                        SET effective_from=?, effective_to=?, updated_at=?,
                            record_version=record_version+1
                        WHERE id=?
                        """,
                        (renewed_from, renewed_to, now_iso, existing_row["id"]),
                    )
                    return str(existing_row["knowledge_key"])

            category_label = MEMORY_CATEGORIES[category]
            memory_id = f"kg-memory-{uuid.uuid4().hex[:12]}"
            row_id = self.knowledge.add_document(
                category=category_label,
                intent=f"memory-{category}",
                question=normalized_fact[:100],
                answer=normalized_fact,
                keywords=f"{category_label} {normalized_fact[:100]}",
                risk_level="low",
                source=source or "memory://manual",
                status="active",
                approved_by="memory-service",
                tenant_id=tenant_id,
                knowledge_key=memory_id,
                layer=MEMORY_LAYER,
                store_id=store_id,
                subject_hash=subject_hash,
            )
            # 记忆是时效性事实，写 effective_to；add_document 返回行主键而非 memory_id。
            with self.knowledge.db.connect() as conn:
                conn.execute(
                    """
                    UPDATE knowledge SET effective_from=?, effective_to=?, updated_at=?
                    WHERE id=?
                    """,
                    (now_iso, expires_iso, now_iso, row_id),
                )
        return memory_id

    def recall(
        self,
        store_id: str,
        *,
        query: str = "",
        limit: int = 10,
        tenant_id: str | None = None,
        subject_hash: str | None = None,
    ) -> list[dict[str, Any]]:
        """显式召回店铺记忆（默认隔离：普通检索不命中 memory）。

        参数：
            store_id: 店铺 id
            query: 相关度查询（空=按时间返回全部）
            limit: 条数

        返回：记忆行列表。
        """
        if limit <= 0:
            return []
        params: list[Any] = [MEMORY_LAYER, store_id]
        sql = (
            "SELECT id, knowledge_key, category, intent, question, answer, keywords, "
            "source, store_id, layer, tenant_id, subject_hash, version, created_at "
            "FROM knowledge "
            "WHERE layer=? AND store_id=? AND status='active'"
        )
        # P1-2 过期过滤：不返回已过有效期的记忆（record 写入 effective_to）
        now = datetime.now(UTC).isoformat()
        sql += " AND (effective_to IS NULL OR effective_to > ?)"
        params.append(now)
        if tenant_id is None:
            sql += " AND tenant_id IS NULL"
        else:
            sql += " AND (tenant_id IS NULL OR tenant_id=?)"
            params.append(tenant_id)
        if subject_hash is None:
            sql += " AND subject_hash IS NULL"
        else:
            sql += " AND (subject_hash IS NULL OR subject_hash=?)"
            params.append(subject_hash)
        sql += " ORDER BY created_at DESC"
        with self.knowledge.db.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        ranked: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            score = 0.0
            if query:
                score = self.knowledge.candidate_score(
                    query,
                    intent=str(item["intent"]),
                    query_intent="",
                    question=str(item["question"]),
                    answer=str(item["answer"]),
                    keywords=str(item["keywords"] or ""),
                    category=str(item["category"] or ""),
                )
                if score < MEMORY_MIN_RECALL_SCORE:
                    continue
            item["score"] = score
            ranked.append(item)
        ranked.sort(
            key=lambda item: (float(item["score"]), str(item["created_at"])),
            reverse=True,
        )
        return ranked[:limit]

    def forget(
        self,
        memory_id: str,
        *,
        tenant_id: str | None = None,
        subject_hash: str | None = None,
    ) -> bool:
        """删除一条记忆（或停用）。

        参数：
            memory_id: memory 的 knowledge_key（如 kg-memory-xxx）或行 id

        返回：是否删除。
        """
        where = "layer=? AND (id=? OR knowledge_key=?)"
        params: list[Any] = [MEMORY_LAYER, memory_id, memory_id]
        # 多租户修复（P3-5）：精确租户匹配——租户只能删本租户记忆；
        # 全局记忆只可由全局（tenant_id=None）删除。此前 NULL 分支让
        # 任意租户（知道 memory_id 时）可删全局记忆。
        if tenant_id is None:
            where += " AND tenant_id IS NULL"
        else:
            where += " AND tenant_id=?"
            params.append(tenant_id)
        if subject_hash is not None:
            where += " AND (subject_hash IS NULL OR subject_hash=?)"
            params.append(subject_hash)
        with self.knowledge.db.connect() as conn:
            cur = conn.execute(f"DELETE FROM knowledge WHERE {where}", tuple(params))
            return cur.rowcount > 0
