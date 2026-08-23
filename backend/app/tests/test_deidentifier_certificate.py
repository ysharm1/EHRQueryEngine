"""Property-based test for the de-identification certificate (Task 10.2).

Covers:
- Property 14: Certificate contents and checksum round-trip — for any finalized
  Deidentification_Job, the generated Deidentification_Certificate contains the
  job_id, source reference, method "HIPAA Safe Harbor", per-category counts,
  reviewer identity, completion timestamp, and an integrity checksum; and
  recomputing the checksum over the certificate's canonical contents equals the
  stored checksum.

Finalized jobs are produced through the real DuckDB repository path
(insert -> finalize -> fetch) against an isolated in-memory DuckDB, so the
certificate is built from a genuinely persisted, finalized job rather than a
hand-constructed dict. The checksum is recomputed independently in the test so
the property is a true round-trip check rather than a call to the code under
test.
"""
import hashlib
import json

import duckdb
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.deid_repository import (
    CERTIFICATE_METHOD,
    build_certificate,
    finalize_job,
    get_job,
    init_deid_tables,
    insert_job,
)


# ---------------------------------------------------------------------------
# Generators
#
# Smart generator for a finalized job: a unique-enough job_id, an arbitrary
# source reference, a non-empty reviewer identity, and per-category counts whose
# total is consistent. Category keys are drawn from the Safe Harbor category
# values so counts serialise cleanly to the JSON column.
# ---------------------------------------------------------------------------

_CATEGORY_NAMES = [
    "NAME", "GEO", "DATE", "AGE", "PHONE", "EMAIL", "SSN", "ZIP", "MRN",
    "HEALTH_PLAN", "ACCOUNT", "LICENSE", "VEHICLE", "DEVICE", "URL", "IP",
    "BIOMETRIC", "OTHER",
]

_job_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=40
)
_source_ref = st.text(min_size=0, max_size=60)
_reviewer_id = st.text(min_size=1, max_size=30)
_category_counts = st.dictionaries(
    keys=st.sampled_from(_CATEGORY_NAMES),
    values=st.integers(min_value=0, max_value=50),
    max_size=len(_CATEGORY_NAMES),
)


def _recompute_certificate_checksum(cert: dict) -> str:
    """Recompute the SHA-256 checksum from a certificate's canonical contents.

    Mirrors ``compute_certificate_checksum`` independently so the property is an
    independent recomputation rather than a call to the helper under test. The
    ``integrity_checksum`` field is excluded (it is derived from the others).
    """
    canonical = json.dumps(
        {
            "job_id": cert["job_id"],
            "source_ref": cert["source_ref"],
            "method": cert["method"],
            "category_counts": cert["category_counts"],
            "total_redactions": cert["total_redactions"],
            "reviewer_id": cert["reviewer_id"],
            "finalized_at": cert["finalized_at"],
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Property 14: Certificate contents and checksum round-trip
# Feature: deidentification-service, Property 14: Certificate contents and
# checksum round-trip
# Validates: Requirements 8.2, 8.3
# ---------------------------------------------------------------------------

class TestProperty14CertificateContentsAndChecksumRoundTrip:
    """Property 14 — certificate has all required fields and its checksum
    recomputed over the canonical contents equals the stored checksum."""

    @settings(max_examples=5, deadline=None)
    @given(
        job_id=_job_id,
        source_ref=_source_ref,
        reviewer_id=_reviewer_id,
        category_counts=_category_counts,
    )
    def test_certificate_fields_and_checksum_round_trip(
        self, job_id, source_ref, reviewer_id, category_counts
    ):
        total = sum(category_counts.values())

        # Persist and finalize a job through the real repository path, so the
        # certificate is built from a genuinely finalized job record.
        conn = duckdb.connect(":memory:")
        try:
            init_deid_tables(conn)
            insert_job(
                conn,
                job_id=job_id,
                user_id="user-1",
                source_type="text",
                source_ref=source_ref,
                status="needs_review",
                total_redactions=total,
                category_counts=category_counts,
                deidentified_text="[REDACTED]",
                redactions=[],
            )
            finalize_job(
                conn,
                job_id=job_id,
                status="deidentified",
                reviewer_id=reviewer_id,
            )
            job = get_job(conn, job_id)
        finally:
            conn.close()

        assert job is not None
        assert job["status"] == "deidentified"

        cert = build_certificate(job)

        # --- required fields are present (Req 8.2) ---
        assert cert["job_id"] == job_id
        assert cert["source_ref"] == source_ref
        assert cert["method"] == CERTIFICATE_METHOD == "HIPAA Safe Harbor"
        assert cert["category_counts"] == category_counts
        assert cert["total_redactions"] == total
        assert cert["reviewer_id"] == reviewer_id
        # Completion timestamp stamped at finalization.
        assert cert["finalized_at"] is not None
        # Integrity checksum present.
        assert isinstance(cert["integrity_checksum"], str)
        assert len(cert["integrity_checksum"]) == 64  # SHA-256 hex digest

        # --- checksum round-trip (Req 8.3) ---
        assert (
            _recompute_certificate_checksum(cert) == cert["integrity_checksum"]
        )


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__, "-v"])
