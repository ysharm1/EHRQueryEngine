"""Unit test for the warehouse-ingestion audit trail (deid-to-warehouse Task 4.2).

Verifies that ``AuditLogService.log_warehouse_ingestion`` writes an audit entry
whose stored ``integrity_checksum`` recomputes from the entry's stored fields
(and that ``verify_integrity`` agrees), following the round-trip convention of
``test_deidentifier_audit.py``.

The ``AuditLogService`` is exercised against an isolated in-memory SQLite
database so the test never touches the real ``metadata.db``.

_Requirements: 5.4_
"""
import hashlib
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.metadata import AuditLog  # noqa: F401 - registers table on Base
from app.services.audit_log import AuditLogService


@pytest.fixture
def db_session():
    """Yield a SQLAlchemy session bound to a fresh in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _recompute(entry: AuditLog) -> str:
    """Recompute the SHA-256 checksum from an entry's stored fields.

    Mirrors ``AuditLogService._generate_checksum`` exactly so the assertion is an
    independent recomputation rather than a call to the helper under test.
    """
    data_string = (
        f"{entry.log_id}|{entry.timestamp.isoformat()}|{entry.user_id}|"
        f"{entry.action}|{json.dumps(entry.details, sort_keys=True)}|{entry.status}"
    )
    return hashlib.sha256(data_string.encode("utf-8")).hexdigest()


def test_warehouse_ingestion_audit_checksum_round_trip(db_session):
    """A warehouse-ingestion audit entry round-trips its checksum (Req 5.4)."""
    service = AuditLogService(db_session)

    log_id = service.log_warehouse_ingestion(
        user_id="test-user",
        job_id="job-123",
        source_id="default-clinic",
        target_table="clinical_notes",
        record_count=1,
    )

    entry = db_session.query(AuditLog).filter(AuditLog.log_id == log_id).first()
    assert entry is not None
    assert entry.action == "warehouse_ingest"
    assert entry.details["job_id"] == "job-123"
    assert entry.details["source_id"] == "default-clinic"
    assert entry.details["target_table"] == "clinical_notes"
    assert entry.details["record_count"] == 1

    # Recomputed-from-stored-fields checksum matches the stored value.
    assert _recompute(entry) == entry.integrity_checksum
    # And the service's own verification agrees.
    assert service.verify_integrity(log_id) is True
