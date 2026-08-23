"""Unit tests for the de-identification DuckDB repository (Task 9.1).

Exercises table creation and the job repository round-trip (insert a job with
its redactions, fetch it, list jobs, record review decisions, and finalize)
against an isolated in-memory DuckDB so no real warehouse is touched.

_Requirements: 6.5, 9.3_
"""
import duckdb
import pytest

from app.services.deid_repository import (
    finalize_job,
    get_job,
    init_deid_tables,
    insert_job,
    list_jobs,
    update_redaction_review,
)
from app.services.deidentifier import (
    IdentifierCategory,
    REDACTION_TOKENS,
    Redaction,
)


@pytest.fixture
def conn():
    """In-memory DuckDB with the de-identification tables initialized."""
    c = duckdb.connect(":memory:")
    init_deid_tables(c)
    yield c
    c.close()


def _sample_redactions():
    return [
        Redaction(
            category=IdentifierCategory.NAME,
            start=0,
            end=8,
            original_text="John Doe",
            token=REDACTION_TOKENS[IdentifierCategory.NAME],
            method="llm",
            confidence=0.7,
        ),
        Redaction(
            category=IdentifierCategory.SSN,
            start=20,
            end=31,
            original_text="123-45-6789",
            token=REDACTION_TOKENS[IdentifierCategory.SSN],
            method="regex",
            confidence=1.0,
        ),
    ]


def test_init_is_idempotent(conn):
    """Re-running init does not error and leaves both tables present."""
    init_deid_tables(conn)  # second call
    tables = {
        row[0]
        for row in conn.execute("SHOW TABLES").fetchall()
    }
    assert {"deid_jobs", "deid_redactions"}.issubset(tables)


def test_insert_and_get_job_round_trip(conn):
    """A job and its redactions survive an insert -> fetch round-trip."""
    redactions = _sample_redactions()
    insert_job(
        conn,
        job_id="job-1",
        user_id="user-1",
        source_type="text",
        source_ref="inline-text",
        status="needs_review",
        total_redactions=len(redactions),
        category_counts={"NAME": 1, "SSN": 1},
        deidentified_text="[NAME] xxx [SSN]",
        redactions=redactions,
        integrity_checksum="abc123",
    )

    job = get_job(conn, "job-1")
    assert job is not None
    assert job["job_id"] == "job-1"
    assert job["user_id"] == "user-1"
    assert job["status"] == "needs_review"
    assert job["method"] == "HIPAA Safe Harbor"
    assert job["total_redactions"] == 2
    assert job["category_counts"] == {"NAME": 1, "SSN": 1}
    assert job["deidentified_text"] == "[NAME] xxx [SSN]"
    assert job["integrity_checksum"] == "abc123"
    assert job["created_at"] is not None
    assert job["finalized_at"] is None

    # Redactions preserved in order with correct fields.
    assert len(job["redactions"]) == 2
    first = job["redactions"][0]
    assert first["category"] == "NAME"
    assert first["start"] == 0
    assert first["end"] == 8
    assert first["original_text"] == "John Doe"
    assert first["method"] == "llm"
    assert first["confidence"] == pytest.approx(0.7)
    assert first["review_action"] is None


def test_get_job_missing_returns_none(conn):
    """Fetching an unknown job id returns None (route layer -> 404)."""
    assert get_job(conn, "does-not-exist") is None


def test_list_jobs_returns_created_jobs(conn):
    """list_jobs returns each created job with summary fields."""
    for i in range(3):
        insert_job(
            conn,
            job_id=f"job-{i}",
            user_id="user-1",
            source_type="text",
            source_ref=f"doc-{i}.txt",
            status="deidentified",
            total_redactions=0,
            category_counts={},
            deidentified_text="clean",
            redactions=[],
        )

    jobs = list_jobs(conn)
    assert len(jobs) == 3
    ids = {j["job_id"] for j in jobs}
    assert ids == {"job-0", "job-1", "job-2"}
    for j in jobs:
        assert set(j.keys()) == {
            "job_id", "source_ref", "status", "created_at", "total_redactions"
        }


def test_update_review_and_finalize(conn):
    """Review decisions and finalization update the stored job/redactions."""
    redactions = _sample_redactions()
    insert_job(
        conn,
        job_id="job-x",
        user_id="user-1",
        source_type="text",
        source_ref="inline-text",
        status="needs_review",
        total_redactions=len(redactions),
        category_counts={"NAME": 1, "SSN": 1},
        deidentified_text="[NAME] xxx [SSN]",
        redactions=redactions,
    )

    update_redaction_review(
        conn,
        job_id="job-x",
        redaction_index=0,
        review_action="edit",
        review_replacement="[PATIENT]",
    )
    finalize_job(
        conn,
        job_id="job-x",
        status="deidentified",
        reviewer_id="reviewer-9",
        deidentified_text="[PATIENT] xxx [SSN]",
        integrity_checksum="final-checksum",
    )

    job = get_job(conn, "job-x")
    assert job["status"] == "deidentified"
    assert job["reviewer_id"] == "reviewer-9"
    assert job["finalized_at"] is not None
    assert job["deidentified_text"] == "[PATIENT] xxx [SSN]"
    assert job["integrity_checksum"] == "final-checksum"

    reviewed = job["redactions"][0]
    assert reviewed["review_action"] == "edit"
    assert reviewed["review_replacement"] == "[PATIENT]"
    # Untouched redaction has no decision.
    assert job["redactions"][1]["review_action"] is None
