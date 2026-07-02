"""SQLite persistence for underwriting workflow state."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(os.getenv("UNDERWRITING_DB_PATH", "artifacts/underwriting.db"))


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, default=str)


def _loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


class UnderwritingRepository:
    """Small SQLite repository with JSON payload columns for workflow records."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    submitted_by TEXT NOT NULL,
                    applicant_json TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    requested_coverages_json TEXT NOT NULL,
                    assigned_to TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS enrichments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    decision_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    rating_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    review_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    quote_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bound_policies (
                    id TEXT PRIMARY KEY,
                    quote_id TEXT NOT NULL REFERENCES quotes(id),
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    policy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS unstructured_intake (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    batch_index INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    content_type TEXT,
                    file_extension TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    raw_preview_json TEXT NOT NULL,
                    extraction_json TEXT NOT NULL,
                    field_confidence_json TEXT NOT NULL,
                    source_evidence_json TEXT NOT NULL,
                    missing_fields_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    reviewer_edits_json TEXT,
                    review_notes TEXT,
                    reviewer TEXT,
                    application_id TEXT REFERENCES applications(id) ON DELETE SET NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create_application(self, application_id: str, payload: dict[str, Any], status: str = "submitted") -> dict[str, Any]:
        created = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO applications (
                    id, status, channel, submitted_by, applicant_json, policy_json,
                    requested_coverages_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    status,
                    payload["channel"],
                    payload["submitted_by"],
                    _dumps(payload["applicant"]),
                    _dumps(payload["policy"]),
                    _dumps(payload.get("requested_coverages", {})),
                    created,
                    created,
                ),
            )
        self.add_audit(application_id, "application.created", payload["submitted_by"], {"status": status})
        return self.get_case(application_id)

    def update_status(self, application_id: str, status: str, actor: str, payload: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_iso(), application_id),
            )
        self.add_audit(application_id, f"status.{status}", actor, payload or {})

    def assign(self, application_id: str, assignee: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE applications SET assigned_to = ?, updated_at = ? WHERE id = ?",
                (assignee, now_iso(), application_id),
            )
        self.add_audit(application_id, "review.assigned", assignee, {"assignee": assignee})

    def insert_enrichment(self, application_id: str, response: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO enrichments (application_id, provider, response_json, created_at) VALUES (?, ?, ?, ?)",
                (application_id, response["provider"], _dumps(response), now_iso()),
            )

    def insert_decision(self, application_id: str, decision: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO decisions (application_id, decision_json, created_at) VALUES (?, ?, ?)",
                (application_id, _dumps(decision), now_iso()),
            )
        self.add_audit(application_id, "underwriting.decision", "rules-engine", {"decision_bucket": decision["decision_bucket"]})

    def insert_rating(self, application_id: str, rating: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO ratings (application_id, rating_json, created_at) VALUES (?, ?, ?)",
                (application_id, _dumps(rating), now_iso()),
            )
        self.add_audit(application_id, "rating.created", "rating-engine", {"adjusted_premium_sar": rating.get("adjusted_premium_sar")})

    def insert_review(self, application_id: str, review: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO reviews (application_id, review_json, created_at) VALUES (?, ?, ?)",
                (application_id, _dumps(review), now_iso()),
            )
        self.add_audit(application_id, f"review.{review['action']}", review["underwriter"], review)

    def insert_quote(self, quote_id: str, application_id: str, quote: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO quotes (id, application_id, quote_json, created_at) VALUES (?, ?, ?, ?)",
                (quote_id, application_id, _dumps(quote), now_iso()),
            )
        self.add_audit(application_id, "quote.generated", quote.get("generated_by", "system"), {"quote_id": quote_id})

    def insert_bound_policy(self, policy_id: str, quote_id: str, application_id: str, policy: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO bound_policies (id, quote_id, application_id, policy_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (policy_id, quote_id, application_id, _dumps(policy), now_iso()),
            )
        self.add_audit(application_id, "policy.bound", policy.get("bound_by", "system"), {"policy_id": policy_id, "quote_id": quote_id})

    def add_audit(self, application_id: str, event_type: str, actor: str, payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_events (application_id, event_type, actor, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (application_id, event_type, actor, _dumps(payload), now_iso()),
            )

    def create_unstructured_record(self, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        created = now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO unstructured_intake (
                    id, parent_id, batch_index, status, original_filename, content_type, file_extension,
                    storage_path, raw_text, raw_preview_json, extraction_json, field_confidence_json,
                    source_evidence_json, missing_fields_json, warnings_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    payload.get("parent_id"),
                    int(payload.get("batch_index", 0)),
                    payload["status"],
                    payload["original_filename"],
                    payload.get("content_type"),
                    payload["file_extension"],
                    payload["storage_path"],
                    payload.get("raw_text", ""),
                    _dumps(payload.get("raw_preview", {})),
                    _dumps(payload.get("extraction", {})),
                    _dumps(payload.get("field_confidence", {})),
                    _dumps(payload.get("source_evidence", {})),
                    _dumps(payload.get("missing_fields", [])),
                    _dumps(payload.get("warnings", [])),
                    created,
                    created,
                ),
            )
        return self.get_unstructured_record(record_id)

    def update_unstructured_status(self, record_id: str, status: str, error_message: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE unstructured_intake SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
                (status, error_message, now_iso(), record_id),
            )

    def update_unstructured_extraction(
        self,
        record_id: str,
        *,
        status: str,
        extraction: dict[str, Any],
        field_confidence: dict[str, Any],
        source_evidence: dict[str, Any],
        missing_fields: list[str],
        warnings: list[str],
        error_message: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE unstructured_intake
                SET status = ?, extraction_json = ?, field_confidence_json = ?, source_evidence_json = ?,
                    missing_fields_json = ?, warnings_json = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    _dumps(extraction),
                    _dumps(field_confidence),
                    _dumps(source_evidence),
                    _dumps(missing_fields),
                    _dumps(warnings),
                    error_message,
                    now_iso(),
                    record_id,
                ),
            )
        return self.get_unstructured_record(record_id)

    def update_unstructured_review(
        self,
        record_id: str,
        *,
        status: str,
        reviewer: str,
        notes: str,
        reviewer_edits: dict[str, Any] | None = None,
        application_id: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE unstructured_intake
                SET status = ?, reviewer = ?, review_notes = ?, reviewer_edits_json = ?,
                    application_id = COALESCE(?, application_id), updated_at = ?
                WHERE id = ?
                """,
                (status, reviewer, notes, _dumps(reviewer_edits) if reviewer_edits is not None else None, application_id, now_iso(), record_id),
            )
        return self.get_unstructured_record(record_id)

    def get_unstructured_record(self, record_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM unstructured_intake WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise KeyError(record_id)
        return self._unstructured_from_row(row)

    def list_unstructured_records(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if status:
                rows = conn.execute("SELECT * FROM unstructured_intake WHERE status = ? ORDER BY updated_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM unstructured_intake ORDER BY updated_at DESC").fetchall()
        return [self._unstructured_from_row(row) for row in rows]

    def get_application(self, application_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        if row is None:
            raise KeyError(application_id)
        return self._application_from_row(row)

    def get_case(self, application_id: str) -> dict[str, Any]:
        app = self.get_application(application_id)
        with self.connect() as conn:
            enrichments = conn.execute("SELECT * FROM enrichments WHERE application_id = ? ORDER BY id", (application_id,)).fetchall()
            decisions = conn.execute("SELECT * FROM decisions WHERE application_id = ? ORDER BY id", (application_id,)).fetchall()
            ratings = conn.execute("SELECT * FROM ratings WHERE application_id = ? ORDER BY id", (application_id,)).fetchall()
            reviews = conn.execute("SELECT * FROM reviews WHERE application_id = ? ORDER BY id", (application_id,)).fetchall()
            quotes = conn.execute("SELECT * FROM quotes WHERE application_id = ? ORDER BY created_at", (application_id,)).fetchall()
            bound = conn.execute("SELECT * FROM bound_policies WHERE application_id = ? ORDER BY created_at", (application_id,)).fetchall()
            audit = conn.execute("SELECT * FROM audit_events WHERE application_id = ? ORDER BY id", (application_id,)).fetchall()
        app.update(
            {
                "enrichments": [_loads(row["response_json"], {}) for row in enrichments],
                "decisions": [_loads(row["decision_json"], {}) for row in decisions],
                "ratings": [_loads(row["rating_json"], {}) for row in ratings],
                "reviews": [_loads(row["review_json"], {}) for row in reviews],
                "quotes": [dict(id=row["id"], **_loads(row["quote_json"], {})) for row in quotes],
                "bound_policies": [dict(id=row["id"], **_loads(row["policy_json"], {})) for row in bound],
                "audit_events": [
                    {
                        "id": row["id"],
                        "event_type": row["event_type"],
                        "actor": row["actor"],
                        "payload": _loads(row["payload_json"], {}),
                        "created_at": row["created_at"],
                    }
                    for row in audit
                ],
            }
        )
        app["latest_decision"] = app["decisions"][-1] if app["decisions"] else None
        app["latest_rating"] = app["ratings"][-1] if app["ratings"] else None
        app["latest_review"] = app["reviews"][-1] if app["reviews"] else None
        app["latest_quote"] = app["quotes"][-1] if app["quotes"] else None
        return app

    def list_cases(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if status:
                rows = conn.execute("SELECT id FROM applications WHERE status = ? ORDER BY updated_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT id FROM applications ORDER BY updated_at DESC").fetchall()
        return [self.get_case(row["id"]) for row in rows]

    @staticmethod
    def _unstructured_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "parent_id": row["parent_id"],
            "batch_index": row["batch_index"],
            "status": row["status"],
            "original_filename": row["original_filename"],
            "content_type": row["content_type"],
            "file_extension": row["file_extension"],
            "storage_path": row["storage_path"],
            "raw_text": row["raw_text"],
            "raw_preview": _loads(row["raw_preview_json"], {}),
            "extraction": _loads(row["extraction_json"], {}),
            "field_confidence": _loads(row["field_confidence_json"], {}),
            "source_evidence": _loads(row["source_evidence_json"], {}),
            "missing_fields": _loads(row["missing_fields_json"], []),
            "warnings": _loads(row["warnings_json"], []),
            "reviewer_edits": _loads(row["reviewer_edits_json"], None),
            "review_notes": row["review_notes"],
            "reviewer": row["reviewer"],
            "application_id": row["application_id"],
            "error_message": row["error_message"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _application_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "status": row["status"],
            "channel": row["channel"],
            "submitted_by": row["submitted_by"],
            "assigned_to": row["assigned_to"],
            "applicant": _loads(row["applicant_json"], {}),
            "policy": _loads(row["policy_json"], {}),
            "requested_coverages": _loads(row["requested_coverages_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
