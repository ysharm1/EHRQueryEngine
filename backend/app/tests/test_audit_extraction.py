"""
Property-based tests for extraction audit logging (P-3).
P-3: For every PDF processed, exactly one extraction job record MUST exist.
"""
import duckdb
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.extraction_schema import init_extraction_tables
from app.services.extraction_manager import ExtractionManager


class TestAuditCompletenessProperty:
    """P-3: For every PDF processed, exactly one extraction_jobs record MUST exist."""

    def test_job_record_created_for_nonexistent_file(self):
        """Even for a failed extraction, a job record must be created."""
        conn = duckdb.connect(":memory:")
        init_extraction_tables(conn)
        manager = ExtractionManager(duckdb_conn=conn)
        job = manager.process_pdf("/nonexistent/path/test.pdf")
        # Job should be recorded even if it failed
        rows = conn.execute(
            "SELECT job_id FROM extraction_jobs WHERE job_id=?", [job.job_id]
        ).fetchall()
        assert len(rows) == 1, "Exactly one job record must exist"

    @given(job_count=st.integers(min_value=1, max_value=5))
    @settings(max_examples=10, deadline=None)
    def test_one_record_per_pdf_processed(self, job_count: int):
        """For N PDFs processed, exactly N job records must exist."""
        conn = duckdb.connect(":memory:")
        init_extraction_tables(conn)
        manager = ExtractionManager(duckdb_conn=conn)
        for i in range(job_count):
            manager.process_pdf(f"/nonexistent/chart_{i}.pdf")
        count = conn.execute("SELECT COUNT(*) FROM extraction_jobs").fetchone()[0]
        assert count == job_count, f"Expected {job_count} job records, got {count}"