"""Unit tests for ProvenanceMapper.

Covers record_provenance, get_provenance, and get_provenance_by_record.
"""
import duckdb
import pytest

from app.services.provenance_mapper import ProvenanceMapper
from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration


def _make_conn():
    """Create an in-memory DuckDB with all required tables."""
    conn = duckdb.connect(":memory:")
    init_extraction_tables(conn)
    run_clinical_schema_migration(conn)
    return conn


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def mapper():
    return ProvenanceMapper()


class TestRecordProvenance:
    def test_returns_provenance_id(self, conn, mapper):
        pid = mapper.record_provenance(
            conn,
            data_record_id="rec-1",
            data_table="vital_signs",
            source_file="test.pdf",
            page_number=2,
            provider_name="Dr. Smith",
            provider_type="physician",
            extraction_confidence=0.95,
            extraction_job_id="job-1",
            raw_snippet="BP 120/80",
        )
        assert pid is not None
        assert isinstance(pid, str)
        assert len(pid) > 0

    def test_inserts_row_into_table(self, conn, mapper):
        mapper.record_provenance(
            conn,
            data_record_id="rec-2",
            data_table="lab_results",
            source_file="labs.pdf",
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM data_provenance"
        ).fetchone()[0]
        assert count == 1

    def test_nullable_fields_default_to_none(self, conn, mapper):
        pid = mapper.record_provenance(
            conn,
            data_record_id="rec-3",
            data_table="diagnoses",
            source_file="diag.pdf",
        )
        row = mapper.get_provenance(conn, pid)
        assert row["page_number"] is None
        assert row["provider_name"] is None
        assert row["provider_type"] is None
        assert row["raw_snippet"] is None

    def test_unique_ids_per_call(self, conn, mapper):
        id1 = mapper.record_provenance(
            conn, data_record_id="r1", data_table="vital_signs", source_file="a.pdf"
        )
        id2 = mapper.record_provenance(
            conn, data_record_id="r2", data_table="vital_signs", source_file="a.pdf"
        )
        assert id1 != id2


class TestGetProvenance:
    def test_returns_full_dict(self, conn, mapper):
        pid = mapper.record_provenance(
            conn,
            data_record_id="rec-10",
            data_table="vital_signs",
            source_file="vitals.pdf",
            page_number=3,
            provider_name="Dr. Jones",
            provider_type="surgeon",
            extraction_confidence=0.88,
            extraction_job_id="job-5",
            raw_snippet="HR 72",
        )
        result = mapper.get_provenance(conn, pid)
        assert result is not None
        assert result["provenance_id"] == pid
        assert result["data_record_id"] == "rec-10"
        assert result["data_table"] == "vital_signs"
        assert result["source_file"] == "vitals.pdf"
        assert result["page_number"] == 3
        assert result["provider_name"] == "Dr. Jones"
        assert result["provider_type"] == "surgeon"
        assert result["extraction_confidence"] == 0.88
        assert result["extraction_job_id"] == "job-5"
        assert result["raw_snippet"] == "HR 72"
        assert result["created_at"] is not None

    def test_returns_none_for_missing_id(self, conn, mapper):
        result = mapper.get_provenance(conn, "nonexistent-id")
        assert result is None


class TestGetProvenanceByRecord:
    def test_returns_matching_entries(self, conn, mapper):
        mapper.record_provenance(
            conn, data_record_id="rec-20", data_table="vital_signs", source_file="a.pdf"
        )
        mapper.record_provenance(
            conn, data_record_id="rec-20", data_table="vital_signs", source_file="b.pdf"
        )
        results = mapper.get_provenance_by_record(conn, "rec-20", "vital_signs")
        assert len(results) == 2
        assert all(r["data_record_id"] == "rec-20" for r in results)
        assert all(r["data_table"] == "vital_signs" for r in results)

    def test_filters_by_data_table(self, conn, mapper):
        mapper.record_provenance(
            conn, data_record_id="rec-30", data_table="vital_signs", source_file="a.pdf"
        )
        mapper.record_provenance(
            conn, data_record_id="rec-30", data_table="lab_results", source_file="b.pdf"
        )
        results = mapper.get_provenance_by_record(conn, "rec-30", "vital_signs")
        assert len(results) == 1
        assert results[0]["data_table"] == "vital_signs"

    def test_returns_empty_list_when_no_match(self, conn, mapper):
        results = mapper.get_provenance_by_record(conn, "no-such-id", "vital_signs")
        assert results == []
