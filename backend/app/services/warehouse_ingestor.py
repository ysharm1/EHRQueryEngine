"""Warehouse ingestion for finalized De-identification Jobs.

Copies a **finalized** Deidentification_Job's de-identified content into the
queryable DuckDB Warehouse (the same ``clinical_notes`` / ``data_provenance``
tables read by the clinical query API and cohort search), attributes every
ingested row to a source clinic/tenant, records lineage back to the originating
job and its certificate, and is idempotent so re-ingesting a job never
duplicates rows.

Governed by one non-negotiable compliance invariant: **only de-identified data
may enter the Warehouse.** Ingestion is hard-gated on ``status == "deidentified"``
and the queryable content of every ingested row is drawn exclusively from the
job's ``deidentified_text``. Redaction ``original_text`` is never read.

The connection is dependency-injected (matching ``deid_repository``) so the
service can be exercised against an in-memory DuckDB in tests. All DDL is
idempotent so ``init_tables`` is safe to run on every request.

Implements the deid-to-warehouse spec. _Requirements: 1-7._
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Status a job must have before it can be ingested (reused from deid_repository).
FINALIZED_STATUS = "deidentified"

# note_type marker for de-identified notes ingested from a deid job (Req 7.2).
INGESTED_NOTE_TYPE = "deidentified_note"

# Table the free-text primary path writes to.
TARGET_TABLE = "clinical_notes"


# ---------------------------------------------------------------------------
# Schema (matches design.md "Data Models" DDL)
# ---------------------------------------------------------------------------

DEID_INGESTIONS_SQL = """
CREATE TABLE IF NOT EXISTS deid_ingestions (
    job_id VARCHAR PRIMARY KEY,
    source_id VARCHAR NOT NULL,
    target_table VARCHAR NOT NULL,
    record_ids JSON NOT NULL,
    certificate_checksum VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ingested_by VARCHAR
);
"""

# Ensure clinical_notes carries a source_id column for clinic/tenant
# attribution (Req 3.1). Idempotent, matching schema_migration.py's approach.
CLINICAL_NOTES_SOURCE_ID_SQL = (
    "ALTER TABLE clinical_notes ADD COLUMN IF NOT EXISTS source_id VARCHAR;"
)


# ---------------------------------------------------------------------------
# Errors and results
# ---------------------------------------------------------------------------

class JobNotIngestableError(Exception):
    """Raised when ingestion is attempted for a non-finalized job (Req 2.1)."""

    def __init__(self, job_id: str, status: Optional[str]) -> None:
        self.job_id = job_id
        self.status = status
        super().__init__(
            f"Job {job_id!r} is not finalized (status={status!r}); "
            f"only jobs with status {FINALIZED_STATUS!r} may be ingested."
        )


@dataclass
class IngestionResult:
    """The outcome of an ``ingest_job`` call."""

    job_id: str
    source_id: str
    table: str                 # e.g. "clinical_notes"
    record_ids: list[str]      # ids of Ingested_Records
    certificate_checksum: str
    already_ingested: bool     # True when this was a no-op repeat ingestion


class WarehouseIngestor:
    """Ingests finalized de-identification jobs into the queryable Warehouse."""

    def __init__(self, default_source_id: str):
        self.default_source_id = default_source_id

    # -- schema -------------------------------------------------------------

    def init_tables(self, conn) -> None:
        """Idempotent DDL: create ``deid_ingestions`` and ensure the
        ``clinical_notes.source_id`` column exists (Req 3.1, 3.3, 4.2).

        Safe to run on every request, matching ``repo.init_deid_tables``.
        """
        try:
            conn.execute(DEID_INGESTIONS_SQL)
            self._ensure_source_id_column(conn)
            logger.info("Warehouse ingestion tables initialized successfully")
        except Exception as exc:
            logger.error("Failed to initialize warehouse ingestion tables: %s", exc)
            raise

    @staticmethod
    def _ensure_source_id_column(conn) -> None:
        """Add ``clinical_notes.source_id`` if it is missing (idempotent).

        DuckDB refuses ``ALTER TABLE ... ADD COLUMN`` while an index depends on
        the table, and the clinical schema migration creates indexes on
        ``clinical_notes``. To add the column safely we drop the dependent
        indexes, add the column, then recreate the indexes from their captured
        DDL. When the column already exists this is a no-op that never touches
        the indexes, so repeat runs stay cheap and safe.
        """
        existing_columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'clinical_notes'"
            ).fetchall()
        }
        if "source_id" in existing_columns:
            return

        # Capture user-created indexes on clinical_notes (constraint-backed
        # indexes have a NULL sql and are left untouched).
        index_defs = conn.execute(
            "SELECT index_name, sql FROM duckdb_indexes() "
            "WHERE table_name = 'clinical_notes' AND sql IS NOT NULL"
        ).fetchall()

        for index_name, _sql in index_defs:
            conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        conn.execute(CLINICAL_NOTES_SOURCE_ID_SQL)
        for _index_name, sql in index_defs:
            conn.execute(sql)

    # -- deterministic id helpers ------------------------------------------

    @staticmethod
    def note_id_for_job(job_id: str) -> str:
        """Deterministic ``clinical_notes.id`` derived from ``job_id``.

        Deriving the id from the job id (rather than a fresh UUID) is what makes
        ingestion idempotent: a repeat ingestion would target the same row id.
        """
        return f"deid-note:{job_id}"

    @staticmethod
    def patient_id_for_job(job_id: str) -> str:
        """Deterministic synthetic patient id for a de-identified note.

        The source has no real patient identity (it is de-identified), so a
        stable pseudonymous id is derived from the ``job_id`` to satisfy the
        NOT NULL ``clinical_notes.patient_id`` column.
        """
        return f"deid-patient:{job_id}"

    # -- idempotency lookup -------------------------------------------------

    def already_ingested(self, conn, job_id: str) -> Optional[list[str]]:
        """Return existing record ids if ``job_id`` was already ingested.

        Returns ``None`` when the job has not been ingested yet (Req 6).
        """
        row = conn.execute(
            "SELECT record_ids FROM deid_ingestions WHERE job_id = ?",
            [job_id],
        ).fetchone()
        if row is None:
            return None
        record_ids = row[0]
        if isinstance(record_ids, str):
            try:
                record_ids = json.loads(record_ids)
            except (json.JSONDecodeError, ValueError):
                record_ids = []
        return list(record_ids) if record_ids is not None else []

    # -- ingestion ----------------------------------------------------------

    def ingest_job(
        self,
        conn,
        *,
        job: dict,                     # as returned by deid_repository.get_job
        certificate: dict,             # as returned by build_certificate
        source_id: Optional[str] = None,
        ingested_by: Optional[str] = None,
    ) -> IngestionResult:
        """Ingest a finalized job's de-identified text into the Warehouse.

        Raises :class:`JobNotIngestableError` if
        ``job['status'] != FINALIZED_STATUS`` (Req 2.1), before any write.

        Idempotent: a repeat ingestion of the same ``job_id`` is a no-op that
        returns the existing record ids with ``already_ingested=True`` (Req 6).

        Content of the ``clinical_notes`` row is taken ONLY from
        ``job['deidentified_text']`` (Req 2.2, 2.3); redaction ``original_text``
        is never accessed.
        """
        job_id = job["job_id"]
        status = job.get("status")

        # --- compliance gate (Req 2.1) — before any write ---
        if status != FINALIZED_STATUS:
            raise JobNotIngestableError(job_id, status)

        resolved_source_id = source_id or self.default_source_id
        certificate_checksum = certificate.get("integrity_checksum")

        # --- idempotent return path (Req 6.1, 6.2, 6.3) ---
        existing = self.already_ingested(conn, job_id)
        if existing is not None:
            return IngestionResult(
                job_id=job_id,
                source_id=resolved_source_id,
                table=TARGET_TABLE,
                record_ids=existing,
                certificate_checksum=certificate_checksum,
                already_ingested=True,
            )

        # --- first ingestion: single transaction (Req 1, 2.2, 3, 4, 7) ---
        note_id = self.note_id_for_job(job_id)
        patient_id = self.patient_id_for_job(job_id)
        # Content is drawn EXCLUSIVELY from the de-identified text (Req 2.2).
        content = job.get("deidentified_text")
        source_file = job.get("source_ref")
        recorded_at = job.get("finalized_at")
        record_ids = [note_id]

        try:
            conn.execute("BEGIN TRANSACTION")

            # Ingested_Record: clinical_notes row (Req 1.1, 1.2, 7.1, 7.2).
            conn.execute(
                """
                INSERT INTO clinical_notes (
                    id, patient_id, note_type, content, author,
                    recorded_at, source_file, source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    note_id,
                    patient_id,
                    INGESTED_NOTE_TYPE,
                    content,
                    None,
                    recorded_at,
                    source_file,
                    resolved_source_id,
                ],
            )

            # Lineage: data_provenance row (Req 4.3). raw_snippet is left NULL
            # so no original PHI is ever stored.
            conn.execute(
                """
                INSERT INTO data_provenance (
                    provenance_id, data_record_id, data_table, source_file,
                    extraction_job_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    note_id,
                    TARGET_TABLE,
                    source_file,
                    job_id,
                ],
            )

            # Lineage: deid_ingestions row (Req 3.3, 4.2, 4.4).
            conn.execute(
                """
                INSERT INTO deid_ingestions (
                    job_id, source_id, target_table, record_ids,
                    certificate_checksum, ingested_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    job_id,
                    resolved_source_id,
                    TARGET_TABLE,
                    json.dumps(record_ids),
                    certificate_checksum,
                    ingested_by,
                ],
            )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        return IngestionResult(
            job_id=job_id,
            source_id=resolved_source_id,
            table=TARGET_TABLE,
            record_ids=record_ids,
            certificate_checksum=certificate_checksum,
            already_ingested=False,
        )
