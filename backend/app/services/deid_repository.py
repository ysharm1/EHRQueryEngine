"""DuckDB persistence for the De-identification Service.

Defines the ``deid_jobs`` and ``deid_redactions`` tables and the repository
functions used to persist and retrieve Deidentification_Jobs and their
Redactions. Mirrors the DuckDB schema/repository conventions used elsewhere in
this backend (see ``extraction_schema.py`` and ``schema_migration.py``): all
DDL is idempotent (``CREATE TABLE IF NOT EXISTS``) so it is safe to run on every
startup, and connections are supplied by the caller (dependency-injected) so
the functions can be exercised against an in-memory DuckDB in tests.

Implements the de-identification-service spec (Tasks 9.1). _Requirements: 6.5, 9.3._
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema (matches design.md "Data Models" DDL)
# ---------------------------------------------------------------------------

DEID_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS deid_jobs (
    job_id VARCHAR PRIMARY KEY,
    user_id VARCHAR,
    source_type VARCHAR,
    source_ref VARCHAR,
    status VARCHAR NOT NULL,
    method VARCHAR DEFAULT 'HIPAA Safe Harbor',
    total_redactions INTEGER,
    category_counts JSON,
    deidentified_text VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMP,
    reviewer_id VARCHAR,
    integrity_checksum VARCHAR
);

CREATE TABLE IF NOT EXISTS deid_redactions (
    redaction_id VARCHAR PRIMARY KEY,
    job_id VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    original_text VARCHAR,
    token VARCHAR,
    method VARCHAR,
    confidence FLOAT,
    review_action VARCHAR,
    review_replacement VARCHAR
);
"""


def init_deid_tables(conn) -> None:
    """Create the de-identification tables in DuckDB if they don't exist.

    Idempotent — safe to call on every application startup.
    """
    try:
        for statement in DEID_TABLES_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
        logger.info("De-identification tables initialized successfully")
    except Exception as exc:
        logger.error("Failed to initialize de-identification tables: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Redaction id helper
#
# Redactions are persisted with a deterministic, order-preserving id of the
# form ``"{job_id}:{index:04d}"``. This keeps the stored ordering identical to
# the in-memory ``result.redactions`` list (which review decisions reference by
# index) without adding a column beyond the design DDL.
# ---------------------------------------------------------------------------

def _redaction_id(job_id: str, index: int) -> str:
    """Return the deterministic redaction id for the ``index``-th redaction."""
    return f"{job_id}:{index:04d}"


def _redaction_to_row(job_id: str, index: int, redaction: Any) -> list:
    """Flatten a ``Redaction`` (or duck-typed object) into an insert row."""
    category = redaction.category
    # Accept either an IdentifierCategory enum or a plain string category.
    category_value = getattr(category, "value", category)
    return [
        _redaction_id(job_id, index),
        job_id,
        category_value,
        int(redaction.start),
        int(redaction.end),
        redaction.original_text,
        redaction.token,
        redaction.method,
        float(redaction.confidence),
        None,  # review_action
        None,  # review_replacement
    ]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def insert_job(
    conn,
    *,
    job_id: str,
    user_id: Optional[str],
    source_type: str,
    source_ref: str,
    status: str,
    total_redactions: int,
    category_counts: dict[str, int],
    deidentified_text: str,
    redactions: Iterable[Any],
    method: str = "HIPAA Safe Harbor",
    integrity_checksum: Optional[str] = None,
) -> str:
    """Insert a Deidentification_Job together with all of its Redactions.

    The job row and its redaction rows are written in a single transaction so a
    job is never persisted without its redactions. Redactions are stored in the
    supplied order with order-preserving ids so review decisions (which target a
    redaction by index) map back to the correct stored row.

    Args:
        conn: An open DuckDB connection.
        job_id: Unique job identifier.
        user_id: The authenticated user who ran the operation (may be ``None``).
        source_type: ``"text"`` or ``"pdf"``.
        source_ref: Filename or ``"inline-text"``.
        status: ``"needs_review"`` or ``"deidentified"``.
        total_redactions: Total number of redactions applied.
        category_counts: Per-category redaction counts.
        deidentified_text: The output text with identifiers replaced.
        redactions: The applied redactions (``Redaction`` objects).
        method: De-identification method (always "HIPAA Safe Harbor").
        integrity_checksum: Optional integrity checksum for the job.

    Returns:
        The ``job_id`` that was inserted.
    """
    redaction_rows = [
        _redaction_to_row(job_id, index, redaction)
        for index, redaction in enumerate(redactions)
    ]

    try:
        conn.execute("BEGIN TRANSACTION")
        conn.execute(
            """
            INSERT INTO deid_jobs (
                job_id, user_id, source_type, source_ref, status, method,
                total_redactions, category_counts, deidentified_text,
                reviewer_id, integrity_checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                job_id,
                user_id,
                source_type,
                source_ref,
                status,
                method,
                int(total_redactions),
                json.dumps(category_counts, sort_keys=True),
                deidentified_text,
                None,
                integrity_checksum,
            ],
        )
        for row in redaction_rows:
            conn.execute(
                """
                INSERT INTO deid_redactions (
                    redaction_id, job_id, category, start_offset, end_offset,
                    original_text, token, method, confidence,
                    review_action, review_replacement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return job_id


def update_redaction_review(
    conn,
    *,
    job_id: str,
    redaction_index: int,
    review_action: Optional[str],
    review_replacement: Optional[str] = None,
) -> None:
    """Record a reviewer's decision on a single redaction.

    Updates the ``review_action`` and ``review_replacement`` columns of the
    redaction identified by ``(job_id, redaction_index)`` (Req 6.5).
    """
    conn.execute(
        """
        UPDATE deid_redactions
        SET review_action = ?, review_replacement = ?
        WHERE redaction_id = ?
        """,
        [review_action, review_replacement, _redaction_id(job_id, redaction_index)],
    )


def finalize_job(
    conn,
    *,
    job_id: str,
    status: str,
    reviewer_id: Optional[str],
    deidentified_text: Optional[str] = None,
    integrity_checksum: Optional[str] = None,
) -> None:
    """Update a job's review/finalize fields (Req 6.5).

    Sets the final ``status`` (typically ``"deidentified"``), records the
    reviewer, stamps ``finalized_at`` to the current time, and optionally
    updates the (possibly re-reviewed) de-identified text and integrity
    checksum.
    """
    conn.execute(
        """
        UPDATE deid_jobs
        SET status = ?,
            reviewer_id = ?,
            finalized_at = CURRENT_TIMESTAMP,
            deidentified_text = COALESCE(?, deidentified_text),
            integrity_checksum = COALESCE(?, integrity_checksum)
        WHERE job_id = ?
        """,
        [status, reviewer_id, deidentified_text, integrity_checksum, job_id],
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def _iso(value: Any) -> Optional[str]:
    """Render a timestamp value as an ISO string, or ``None``."""
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)


def _row_to_redaction_dict(row: tuple) -> dict:
    """Map a ``deid_redactions`` row to a serialisable dict."""
    return {
        "redaction_id": row[0],
        "job_id": row[1],
        "category": row[2],
        "start": row[3],
        "end": row[4],
        "original_text": row[5],
        "token": row[6],
        "method": row[7],
        "confidence": float(row[8]) if row[8] is not None else None,
        "review_action": row[9],
        "review_replacement": row[10],
    }


def get_redactions(conn, job_id: str) -> list[dict]:
    """Return a job's redactions in stored (index) order."""
    rows = conn.execute(
        """
        SELECT redaction_id, job_id, category, start_offset, end_offset,
               original_text, token, method, confidence,
               review_action, review_replacement
        FROM deid_redactions
        WHERE job_id = ?
        ORDER BY redaction_id
        """,
        [job_id],
    ).fetchall()
    return [_row_to_redaction_dict(row) for row in rows]


def get_job(conn, job_id: str) -> Optional[dict]:
    """Fetch a single Deidentification_Job (with its redactions) by id.

    Returns ``None`` when no job with that id exists (Req 9.6 — the route layer
    turns this into a 404).
    """
    row = conn.execute(
        """
        SELECT job_id, user_id, source_type, source_ref, status, method,
               total_redactions, category_counts, deidentified_text,
               created_at, finalized_at, reviewer_id, integrity_checksum
        FROM deid_jobs
        WHERE job_id = ?
        """,
        [job_id],
    ).fetchone()

    if row is None:
        return None

    category_counts = row[7]
    if isinstance(category_counts, str):
        try:
            category_counts = json.loads(category_counts)
        except (json.JSONDecodeError, ValueError):
            category_counts = {}
    elif category_counts is None:
        category_counts = {}

    return {
        "job_id": row[0],
        "user_id": row[1],
        "source_type": row[2],
        "source_ref": row[3],
        "status": row[4],
        "method": row[5],
        "total_redactions": row[6],
        "category_counts": category_counts,
        "deidentified_text": row[8],
        "created_at": _iso(row[9]),
        "finalized_at": _iso(row[10]),
        "reviewer_id": row[11],
        "integrity_checksum": row[12],
        "redactions": get_redactions(conn, job_id),
    }


def list_jobs(conn, limit: int = 100) -> list[dict]:
    """List Deidentification_Jobs, most recent first (Req 9.3).

    Each entry contains the ``job_id``, ``source_ref``, ``status``, and
    ``created_at`` timestamp (plus ``total_redactions`` for convenience).
    """
    rows = conn.execute(
        """
        SELECT job_id, source_ref, status, created_at, total_redactions
        FROM deid_jobs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return [
        {
            "job_id": row[0],
            "source_ref": row[1],
            "status": row[2],
            "created_at": _iso(row[3]),
            "total_redactions": row[4],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# De-identification certificate (Req 8.1-8.4)
#
# A Deidentification_Certificate proves what identifier categories were removed
# from a source document, for the clinic's compliance records. It is available
# only for a FINALIZED job (status == "deidentified"); requesting one for any
# other status is rejected with JobNotFinalizedError so the API layer can turn
# it into a 409/400 (Req 8.4).
#
# The certificate carries an integrity checksum computed with SHA-256 over the
# canonical (sorted-key) JSON of its contents, mirroring the
# AuditLogService._generate_checksum approach (Req 8.3).
# ---------------------------------------------------------------------------

# Status a job must have before a certificate can be issued (Req 8.1).
FINALIZED_STATUS = "deidentified"

# De-identification method recorded on every certificate (Req 8.2).
CERTIFICATE_METHOD = "HIPAA Safe Harbor"


class JobNotFinalizedError(Exception):
    """Raised when a certificate is requested for a non-finalized job.

    A certificate is available only when the job's status is
    ``"deidentified"`` (Req 8.1, 8.4). The API layer catches this and responds
    with a 409/400 indicating the job is not finalized.
    """

    def __init__(self, job_id: str, status: Optional[str]) -> None:
        self.job_id = job_id
        self.status = status
        super().__init__(
            f"Job {job_id!r} is not finalized (status={status!r}); "
            "a de-identification certificate is only available for jobs with "
            f"status {FINALIZED_STATUS!r}."
        )


def compute_certificate_checksum(
    *,
    job_id: str,
    source_ref: Optional[str],
    method: str,
    category_counts: dict[str, int],
    total_redactions: int,
    reviewer_id: Optional[str],
    finalized_at: Optional[str],
) -> str:
    """Compute the SHA-256 integrity checksum for a certificate (Req 8.3).

    The checksum is taken over the canonical JSON of the certificate's
    contents with keys sorted, so it is stable regardless of dict ordering.
    This mirrors ``AuditLogService._generate_checksum``'s use of
    ``json.dumps(..., sort_keys=True)`` for a reproducible integrity value.

    The checksum deliberately excludes the ``integrity_checksum`` field itself
    (it is derived from the other fields), so recomputing it over the
    certificate's remaining contents reproduces the stored value.
    """
    canonical = json.dumps(
        {
            "job_id": job_id,
            "source_ref": source_ref,
            "method": method,
            "category_counts": category_counts,
            "total_redactions": total_redactions,
            "reviewer_id": reviewer_id,
            "finalized_at": finalized_at,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_certificate(job: dict) -> dict:
    """Build a Deidentification_Certificate from a finalized job (Req 8.1-8.3).

    Args:
        job: A job record as returned by :func:`get_job`.

    Returns:
        A certificate dict with the ``job_id``, ``source_ref``, de-identification
        ``method`` (always "HIPAA Safe Harbor"), per-category ``category_counts``,
        ``total_redactions``, ``reviewer_id``, ``finalized_at`` completion
        timestamp, and the SHA-256 ``integrity_checksum`` over those contents.

    Raises:
        JobNotFinalizedError: if the job's status is not ``"deidentified"``
            (Req 8.4).
    """
    status = job.get("status")
    if status != FINALIZED_STATUS:
        raise JobNotFinalizedError(job.get("job_id"), status)

    job_id = job["job_id"]
    source_ref = job.get("source_ref")
    category_counts = job.get("category_counts") or {}
    total_redactions = job.get("total_redactions") or 0
    reviewer_id = job.get("reviewer_id")
    finalized_at = job.get("finalized_at")

    checksum = compute_certificate_checksum(
        job_id=job_id,
        source_ref=source_ref,
        method=CERTIFICATE_METHOD,
        category_counts=category_counts,
        total_redactions=total_redactions,
        reviewer_id=reviewer_id,
        finalized_at=finalized_at,
    )

    return {
        "job_id": job_id,
        "source_ref": source_ref,
        "method": CERTIFICATE_METHOD,
        "category_counts": category_counts,
        "total_redactions": total_redactions,
        "reviewer_id": reviewer_id,
        "finalized_at": finalized_at,
        "integrity_checksum": checksum,
    }


def get_certificate(conn, job_id: str) -> Optional[dict]:
    """Fetch a job and build its certificate (Req 8.1, 8.4).

    Returns ``None`` when the job does not exist (the route layer turns this
    into a 404, Req 9.6). Raises :class:`JobNotFinalizedError` when the job
    exists but is not finalized (Req 8.4).
    """
    job = get_job(conn, job_id)
    if job is None:
        return None
    return build_certificate(job)
