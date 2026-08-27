from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import Settings
from .database import Database, utc_now
from .message_media import (
    MessageMediaStore,
    clear_media_deletions,
    enqueue_media_deletions,
    mark_media_deletion_failed,
)


TERMINAL_HANDOFF_STATUSES = ("completed", "failed", "canceled", "rejected")


class MaintenanceService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        *,
        media_store: MessageMediaStore | None = None,
    ):
        self.db = db
        self.settings = settings
        self.media_store = media_store or MessageMediaStore(settings.data_dir)

    def purge_expired(self, *, actor: str, dry_run: bool) -> dict[str, Any]:
        now = datetime.now(UTC)
        message_cutoff = (now - timedelta(days=self.settings.message_retention_days)).isoformat()
        audit_cutoff = (now - timedelta(days=self.settings.audit_retention_days)).isoformat()
        terminal = TERMINAL_HANDOFF_STATUSES

        with self.db._write_lock, self.db.connect() as conn:
            messages_delete = conn.execute(
                """
                SELECT COUNT(*) FROM messages m
                WHERE m.created_at < ?
                  AND NOT EXISTS (SELECT 1 FROM feedback f WHERE f.message_id=m.id)
                  AND NOT EXISTS (
                      SELECT 1 FROM handoff_tasks h
                      WHERE h.session_id=m.session_id AND h.status NOT IN (?, ?, ?, ?)
                  )
                """,
                (message_cutoff, *terminal),
            ).fetchone()[0]
            messages_redact = conn.execute(
                """
                SELECT COUNT(*) FROM messages m
                WHERE m.created_at < ?
                  AND EXISTS (SELECT 1 FROM feedback f WHERE f.message_id=m.id)
                  AND m.content != '[PURGED_BY_RETENTION]'
                  AND NOT EXISTS (
                      SELECT 1 FROM handoff_tasks h
                      WHERE h.session_id=m.session_id AND h.status NOT IN (?, ?, ?, ?)
                  )
                """,
                (message_cutoff, *terminal),
            ).fetchone()[0]
            handoffs_redact = conn.execute(
                """
                SELECT COUNT(*) FROM handoff_tasks
                WHERE updated_at < ? AND status IN (?, ?, ?, ?)
                  AND payload_json != '{"purged":true}'
                """,
                (message_cutoff, *terminal),
            ).fetchone()[0]
            context_snapshots_delete = conn.execute(
                """
                SELECT COUNT(*) FROM context_snapshots c
                WHERE c.created_at < ?
                  AND NOT EXISTS (
                      SELECT 1 FROM handoff_tasks h
                      WHERE h.session_id=c.session_id AND h.status NOT IN (?, ?, ?, ?)
                  )
                """,
                (message_cutoff, *terminal),
            ).fetchone()[0]
            metrics_delete = conn.execute(
                "SELECT COUNT(*) FROM request_metrics WHERE created_at < ?", (message_cutoff,)
            ).fetchone()[0]
            audit_delete = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE created_at < ?", (audit_cutoff,)
            ).fetchone()[0]
            expired_sessions = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT s.id FROM sessions s
                    WHERE s.status='active' AND s.last_seen_at < ?
                      AND NOT EXISTS (
                          SELECT 1 FROM handoff_tasks h
                          WHERE h.session_id=s.id AND h.status NOT IN (?, ?, ?, ?)
                      )
                    """,
                    (message_cutoff, *terminal),
                ).fetchall()
            ]
            media_rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT mm.message_id, mm.id, mm.mime_type, mm.size_bytes,
                           mm.storage_ref, mm.vision_description, mm.created_at
                    FROM message_media mm
                    JOIN messages m ON m.id=mm.message_id
                    WHERE m.created_at < ?
                      AND NOT EXISTS (
                          SELECT 1 FROM handoff_tasks h
                          WHERE h.session_id=m.session_id
                            AND h.status NOT IN (?, ?, ?, ?)
                      )
                    """,
                    (message_cutoff, *terminal),
                ).fetchall()
            ]
            pending_media_deletions = int(
                conn.execute("SELECT COUNT(*) FROM media_deletion_queue").fetchone()[0]
            )

            report = {
                "dry_run": dry_run,
                "message_cutoff": message_cutoff,
                "audit_cutoff": audit_cutoff,
                "messages_deleted": int(messages_delete),
                "messages_redacted": int(messages_redact),
                "handoffs_redacted": int(handoffs_redact),
                "context_snapshots_deleted": int(context_snapshots_delete),
                "metrics_deleted": int(metrics_delete),
                "audit_events_deleted": int(audit_delete),
                "sessions_closed": len(expired_sessions),
                "expired_session_ids": expired_sessions,
                "media_files_selected": len(media_rows),
                "media_deletion_pending": pending_media_deletions,
            }
            if dry_run:
                return report

            queued_at = utc_now()
            enqueue_media_deletions(conn, media_rows, queued_at=queued_at)

            conn.execute(
                """
                DELETE FROM message_media
                WHERE message_id IN (
                    SELECT m.id FROM messages m
                    WHERE m.created_at < ?
                      AND NOT EXISTS (
                          SELECT 1 FROM handoff_tasks h
                          WHERE h.session_id=m.session_id
                            AND h.status NOT IN (?, ?, ?, ?)
                      )
                )
                """,
                (message_cutoff, *terminal),
            )

            conn.execute(
                """
                UPDATE messages SET content='[PURGED_BY_RETENTION]', sources_json='[]', redacted=1
                WHERE created_at < ?
                  AND EXISTS (SELECT 1 FROM feedback f WHERE f.message_id=messages.id)
                  AND NOT EXISTS (
                      SELECT 1 FROM handoff_tasks h
                      WHERE h.session_id=messages.session_id AND h.status NOT IN (?, ?, ?, ?)
                  )
                """,
                (message_cutoff, *terminal),
            )
            conn.execute(
                """
                UPDATE messages SET context_snapshot_id=NULL
                WHERE context_snapshot_id IN (
                    SELECT c.id FROM context_snapshots c
                    WHERE c.created_at < ?
                      AND NOT EXISTS (
                          SELECT 1 FROM handoff_tasks h
                          WHERE h.session_id=c.session_id AND h.status NOT IN (?, ?, ?, ?)
                      )
                )
                """,
                (message_cutoff, *terminal),
            )
            conn.execute(
                """
                DELETE FROM messages
                WHERE created_at < ?
                  AND NOT EXISTS (SELECT 1 FROM feedback f WHERE f.message_id=messages.id)
                  AND NOT EXISTS (
                      SELECT 1 FROM handoff_tasks h
                      WHERE h.session_id=messages.session_id AND h.status NOT IN (?, ?, ?, ?)
                  )
                """,
                (message_cutoff, *terminal),
            )
            conn.execute(
                """
                UPDATE handoff_tasks SET payload_json='{"purged":true}'
                WHERE updated_at < ? AND status IN (?, ?, ?, ?)
                """,
                (message_cutoff, *terminal),
            )
            conn.execute(
                """
                DELETE FROM context_snapshots
                WHERE created_at < ?
                  AND NOT EXISTS (
                      SELECT 1 FROM handoff_tasks h
                      WHERE h.session_id=context_snapshots.session_id
                        AND h.status NOT IN (?, ?, ?, ?)
                  )
                """,
                (message_cutoff, *terminal),
            )
            conn.execute("DELETE FROM request_metrics WHERE created_at < ?", (message_cutoff,))
            conn.execute("DELETE FROM audit_log WHERE created_at < ?", (audit_cutoff,))
            if expired_sessions:
                placeholders = ",".join("?" for _ in expired_sessions)
                conn.execute(
                    f"UPDATE sessions SET status='closed' WHERE id IN ({placeholders})",
                    tuple(expired_sessions),
                )
            run_id = f"retention-{uuid.uuid4().hex}"
            report["media_files_deleted"] = 0
            report["media_files_delete_failed"] = 0
            conn.execute(
                "INSERT INTO retention_runs VALUES (?, ?, ?, ?)",
                (run_id, actor, json.dumps(report, ensure_ascii=False), utc_now()),
            )
        deleted, failed = self._drain_media_deletion_queue()
        report["media_files_deleted"] = deleted
        report["media_files_delete_failed"] = failed
        with self.db._write_lock, self.db.connect() as conn:
            report["media_deletion_pending"] = int(
                conn.execute("SELECT COUNT(*) FROM media_deletion_queue").fetchone()[0]
            )
            conn.execute(
                "UPDATE retention_runs SET detail_json=? WHERE id=?",
                (json.dumps(report, ensure_ascii=False), run_id),
            )
        return report

    def _drain_media_deletion_queue(self) -> tuple[int, int]:
        with self.db.connect() as conn:
            jobs = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT storage_ref, media_id AS id, mime_type, size_bytes
                    FROM media_deletion_queue ORDER BY created_at, storage_ref
                    """
                ).fetchall()
            ]
        deleted = 0
        failed = 0
        for job in jobs:
            try:
                deleted += self.media_store.remove([job])
            except (OSError, ValueError) as exc:
                failed += 1
                with self.db._write_lock, self.db.connect() as conn:
                    mark_media_deletion_failed(
                        conn,
                        storage_ref=str(job["storage_ref"]),
                        error=exc,
                        updated_at=utc_now(),
                    )
                continue
            with self.db._write_lock, self.db.connect() as conn:
                clear_media_deletions(
                    conn,
                    [str(job["storage_ref"])],
                )
        return deleted, failed

    def close_idle_sessions(self) -> dict[str, Any]:
        run_at = utc_now()
        cutoff = (
            datetime.now(UTC)
            - timedelta(minutes=self.settings.session_idle_timeout_minutes)
        ).isoformat()
        terminal = TERMINAL_HANDOFF_STATUSES
        with self.db._write_lock, self.db.connect() as conn:
            session_ids = [
                str(row["id"])
                for row in conn.execute(
                    """
                    SELECT s.id FROM sessions s
                    WHERE s.status='active' AND s.last_seen_at < ?
                      AND NOT EXISTS (
                          SELECT 1 FROM handoff_tasks h
                          WHERE h.session_id=s.id
                            AND h.status NOT IN (?, ?, ?, ?)
                      )
                    """,
                    (cutoff, *terminal),
                ).fetchall()
            ]
            if session_ids:
                placeholders = ",".join("?" for _ in session_ids)
                conn.execute(
                    f"""
                    UPDATE sessions SET status='closed'
                    WHERE status='active' AND id IN ({placeholders})
                    """,
                    tuple(session_ids),
                )
        return {
            "run_at": run_at,
            "cutoff": cutoff,
            "closed": len(session_ids),
            "session_ids": session_ids,
        }
