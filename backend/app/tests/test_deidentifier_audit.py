"""Property-based test for the de-identification audit trail.

Covers Task 9.3:
- Property 13: Audit checksum round-trip — for any de-identification audit log
  entry, recomputing the SHA-256 checksum from the entry's stored fields equals
  the stored ``integrity_checksum``.

The ``AuditLogService`` is exercised against an isolated in-memory SQLite
database so the test never touches the real ``metadata.db``. Both the
de-identify and finalize log methods are covered by the same property, since
both persist their entry via the shared checksum path.
"""
import hashlib
import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.metadata import AuditLog  # noqa: F401 - registers table on Base
from app.services.audit_log import AuditLogService


# ---------------------------------------------------------------------------
# Isolated in-memory SQLite session
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

_CATEGORY_NAMES = [
    "NAME", "GEO", "DATE", "PHONE", "EMAIL", "SSN", "MRN", "ZIP", "URL",
    "IP", "ACCOUNT", "LICENSE", "VEHICLE", "DEVICE", "BIOMETRIC", "OTHER",
]

_category_counts = st.dictionaries(
    keys=st.sampled_from(_CATEGORY_NAMES),
    values=st.integers(min_value=0, max_value=50),
    max_size=len(_CATEGORY_NAMES),
)

_optional_user = st.one_of(st.none(), st.text(min_size=1, max_size=30))
_source_ref = st.text(min_size=0, max_size=60)
_job_id = st.text(min_size=1, max_size=40)


def _recompute(service: AuditLogService, entry: AuditLog) -> str:
    """Recompute the SHA-256 checksum from an entry's stored fields.

    Mirrors ``AuditLogService._generate_checksum`` exactly so the property is an
    independent recomputation rather than a call to the same helper under test.
    """
    data_string = (
        f"{entry.log_id}|{entry.timestamp.isoformat()}|{entry.user_id}|"
        f"{entry.action}|{json.dumps(entry.details, sort_keys=True)}|{entry.status}"
    )
    return hashlib.sha256(data_string.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Property 13: Audit checksum round-trip
# ---------------------------------------------------------------------------

# Feature: deidentification-service, Property 13: For any de-identification
# audit log entry, recomputing the SHA-256 checksum from the entry's stored
# fields SHALL produce a value equal to the stored integrity_checksum.
# Validates: Requirements 7.3, 7.4
class TestProperty13AuditChecksumRoundTrip:
    """Property 13 — recomputed checksum equals the stored checksum."""

    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        user_id=_optional_user,
        source_ref=_source_ref,
        category_counts=_category_counts,
        job_id=st.one_of(st.none(), _job_id),
    )
    def test_deidentify_entry_checksum_round_trip(
        self, db_session, user_id, source_ref, category_counts, job_id
    ):
        """A logged de-identify operation round-trips its checksum (Req 7.1)."""
        service = AuditLogService(db_session)
        total = sum(category_counts.values())

        log_id = service.log_deidentification(
            user_id=user_id,
            source_ref=source_ref,
            category_counts=category_counts,
            total_redactions=total,
            job_id=job_id,
        )

        entry = db_session.query(AuditLog).filter(AuditLog.log_id == log_id).first()
        assert entry is not None
        # Recomputed-from-stored-fields checksum matches the stored value.
        assert _recompute(service, entry) == entry.integrity_checksum
        # And the service's own verification agrees (Req 7.4).
        assert service.verify_integrity(log_id) is True

    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        user_id=_optional_user,
        job_id=_job_id,
        approved=st.integers(min_value=0, max_value=100),
        rejected=st.integers(min_value=0, max_value=100),
        edited=st.integers(min_value=0, max_value=100),
    )
    def test_finalize_entry_checksum_round_trip(
        self, db_session, user_id, job_id, approved, rejected, edited
    ):
        """A logged finalize action round-trips its checksum (Req 7.2)."""
        service = AuditLogService(db_session)

        log_id = service.log_deidentification_finalize(
            user_id=user_id,
            job_id=job_id,
            approved=approved,
            rejected=rejected,
            edited=edited,
        )

        entry = db_session.query(AuditLog).filter(AuditLog.log_id == log_id).first()
        assert entry is not None
        assert _recompute(service, entry) == entry.integrity_checksum
        assert service.verify_integrity(log_id) is True
