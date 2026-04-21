"""Tests for ClinicalQueryEngine.

Covers:
- ClinicalQueryFilters and AggregationRequest dataclasses (8.1)
- validate_query_filters (8.2)
- QueryEngine.query — filter combinations, pagination, empty results (8.3)
- QueryEngine.aggregate — min/max/avg/count/first/last correctness (8.4)
- QueryEngine.get_encounter_summary (8.5)
"""
import duckdb
import pytest

from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration
from app.services.clinical_query_engine import (
    AggregationRequest,
    ClinicalQueryFilters,
    QueryEngine,
    validate_query_filters,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """In-memory DuckDB with base + migration tables and seed data."""
    c = duckdb.connect(":memory:")
    init_extraction_tables(c)
    run_clinical_schema_migration(c)
    # Seed patient
    c.execute("INSERT INTO patients (patient_id) VALUES ('p1')")
    # Seed encounters
    c.execute(
        "INSERT INTO encounters (encounter_id, patient_id, encounter_date, encounter_type, source_file) "
        "VALUES ('enc1', 'p1', '2024-01-15', 'inpatient', 'a.pdf'), "
        "       ('enc2', 'p1', '2024-03-20', 'outpatient', 'b.pdf')"
    )
    # Seed vitals across encounters
    c.execute(
        "INSERT INTO vital_signs (id, patient_id, vital_name, value, unit, encounter_id, provider_type, recorded_at) VALUES "
        "('v1', 'p1', 'GCS', 12, 'score', 'enc1', 'surgeon', '2024-01-15 08:00:00'), "
        "('v2', 'p1', 'GCS', 14, 'score', 'enc1', 'surgeon', '2024-01-15 12:00:00'), "
        "('v3', 'p1', 'GCS', 15, 'score', 'enc2', 'neurologist', '2024-03-20 09:00:00'), "
        "('v4', 'p1', 'HR', 72, 'bpm', 'enc1', 'nurse', '2024-01-15 08:00:00')"
    )
    # Seed labs
    c.execute(
        "INSERT INTO lab_results (id, patient_id, test_name, value, unit, encounter_id, provider_type, recorded_at) VALUES "
        "('l1', 'p1', 'Hemoglobin', '13.5', 'g/dL', 'enc1', 'physician', '2024-01-15 09:00:00'), "
        "('l2', 'p1', 'Hemoglobin', '14.0', 'g/dL', 'enc2', 'physician', '2024-03-20 10:00:00')"
    )
    # Seed provenance
    c.execute(
        "INSERT INTO data_provenance (provenance_id, data_record_id, data_table, source_file, page_number, provider_type) VALUES "
        "('prov1', 'v1', 'vital_signs', 'a.pdf', 1, 'surgeon'), "
        "('prov2', 'v2', 'vital_signs', 'a.pdf', 2, 'surgeon'), "
        "('prov3', 'l1', 'lab_results', 'a.pdf', 3, 'physician')"
    )
    yield c
    c.close()


@pytest.fixture
def engine():
    return QueryEngine()


# ---------------------------------------------------------------------------
# 8.1 — Dataclass defaults
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_filters_defaults(self):
        f = ClinicalQueryFilters()
        assert f.patient_id is None
        assert f.limit == 100
        assert f.offset == 0
        assert f.data_types is None

    def test_aggregation_defaults(self):
        a = AggregationRequest()
        assert a.data_type == "vitals"
        assert a.group_by == "encounter"
        assert a.aggregations == ["min", "max", "avg"]


# ---------------------------------------------------------------------------
# 8.2 — validate_query_filters
# ---------------------------------------------------------------------------

class TestValidateQueryFilters:
    def test_valid_filters_returns_empty(self):
        f = ClinicalQueryFilters(
            patient_id="p1",
            date_from="2024-01-01",
            date_to="2024-12-31",
            provider_types=["surgeon"],
            data_types=["vitals", "labs"],
            limit=50,
            offset=0,
        )
        assert validate_query_filters(f) == []

    def test_invalid_date_from(self):
        f = ClinicalQueryFilters(date_from="01-2024-01")
        errors = validate_query_filters(f)
        assert any("date_from" in e for e in errors)

    def test_invalid_date_to(self):
        f = ClinicalQueryFilters(date_to="not-a-date")
        errors = validate_query_filters(f)
        assert any("date_to" in e for e in errors)

    def test_invalid_provider_type(self):
        f = ClinicalQueryFilters(provider_types=["wizard"])
        errors = validate_query_filters(f)
        assert any("provider_type" in e and "wizard" in e for e in errors)

    def test_invalid_data_type(self):
        f = ClinicalQueryFilters(data_types=["xrays"])
        errors = validate_query_filters(f)
        assert any("data_type" in e and "xrays" in e for e in errors)

    def test_limit_zero(self):
        f = ClinicalQueryFilters(limit=0)
        errors = validate_query_filters(f)
        assert any("limit" in e for e in errors)

    def test_negative_offset(self):
        f = ClinicalQueryFilters(offset=-1)
        errors = validate_query_filters(f)
        assert any("offset" in e for e in errors)

    def test_multiple_errors(self):
        f = ClinicalQueryFilters(
            date_from="bad", provider_types=["wizard"], limit=-5, offset=-1
        )
        errors = validate_query_filters(f)
        assert len(errors) >= 4


# ---------------------------------------------------------------------------
# 8.3 — QueryEngine.query
# ---------------------------------------------------------------------------

class TestQueryEngineQuery:
    def test_query_all_returns_rows(self, conn, engine):
        result = engine.query(conn, ClinicalQueryFilters(patient_id="p1"))
        assert result["total_count"] > 0
        assert len(result["rows"]) > 0

    def test_query_by_data_type_vitals(self, conn, engine):
        result = engine.query(conn, ClinicalQueryFilters(patient_id="p1", data_types=["vitals"]))
        for row in result["rows"]:
            assert row["_data_type"] == "vitals"

    def test_query_by_encounter(self, conn, engine):
        result = engine.query(conn, ClinicalQueryFilters(encounter_id="enc1"))
        for row in result["rows"]:
            assert row.get("encounter_id") == "enc1"

    def test_query_by_provider_type(self, conn, engine):
        result = engine.query(
            conn,
            ClinicalQueryFilters(patient_id="p1", provider_types=["surgeon"], data_types=["vitals"]),
        )
        for row in result["rows"]:
            assert row.get("provider_type") == "surgeon"

    def test_query_by_vital_names(self, conn, engine):
        result = engine.query(
            conn,
            ClinicalQueryFilters(patient_id="p1", data_types=["vitals"], vital_names=["GCS"]),
        )
        for row in result["rows"]:
            assert row.get("vital_name") == "GCS"

    def test_query_pagination(self, conn, engine):
        result_full = engine.query(conn, ClinicalQueryFilters(patient_id="p1", data_types=["vitals"], limit=100))
        result_page = engine.query(conn, ClinicalQueryFilters(patient_id="p1", data_types=["vitals"], limit=2, offset=0))
        assert len(result_page["rows"]) <= 2

    def test_query_empty_result(self, conn, engine):
        result = engine.query(conn, ClinicalQueryFilters(patient_id="nonexistent"))
        assert result["total_count"] == 0
        assert result["rows"] == []

    def test_query_provenance_refs(self, conn, engine):
        result = engine.query(
            conn,
            ClinicalQueryFilters(patient_id="p1", data_types=["vitals"], vital_names=["GCS"]),
        )
        # v1 and v2 have provenance records
        assert "v1" in result["provenance_refs"]
        assert result["provenance_refs"]["v1"] == "prov1"

    def test_query_date_range(self, conn, engine):
        result = engine.query(
            conn,
            ClinicalQueryFilters(patient_id="p1", date_from="2024-03-01", date_to="2024-04-01"),
        )
        # Only enc2 data should match
        for row in result["rows"]:
            assert row.get("encounter_id") == "enc2"


# ---------------------------------------------------------------------------
# 8.4 — QueryEngine.aggregate
# ---------------------------------------------------------------------------

class TestQueryEngineAggregate:
    def test_aggregate_min_max_avg_count(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="p1"),
            AggregationRequest(
                metric_name="GCS",
                data_type="vitals",
                aggregations=["min", "max", "avg", "count"],
                group_by="encounter",
            ),
        )
        groups = result["groups"]
        assert len(groups) >= 1
        # enc1 has GCS 12 and 14
        enc1_group = [g for g in groups if g["group_key"] == "enc1"]
        assert len(enc1_group) == 1
        g = enc1_group[0]
        assert g["metric_min"] == 12.0
        assert g["metric_max"] == 14.0
        assert g["metric_avg"] == 13.0
        assert g["metric_count"] == 2

    def test_aggregate_ordering_invariant(self, conn, engine):
        """min <= avg <= max for any group."""
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="p1"),
            AggregationRequest(
                metric_name="GCS",
                data_type="vitals",
                aggregations=["min", "max", "avg"],
                group_by="encounter",
            ),
        )
        for g in result["groups"]:
            assert g["metric_min"] <= g["metric_avg"] <= g["metric_max"]

    def test_aggregate_first_last(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="p1"),
            AggregationRequest(
                metric_name="GCS",
                data_type="vitals",
                aggregations=["first", "last"],
                group_by="encounter",
            ),
        )
        groups = result["groups"]
        enc1_group = [g for g in groups if g["group_key"] == "enc1"]
        assert len(enc1_group) == 1
        g = enc1_group[0]
        # enc1: first recorded GCS=12 (08:00), last=14 (12:00)
        assert g["metric_first"] == 12.0
        assert g["metric_last"] == 14.0

    def test_aggregate_by_patient(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="p1"),
            AggregationRequest(
                metric_name="GCS",
                data_type="vitals",
                aggregations=["min", "max", "count"],
                group_by="patient",
            ),
        )
        groups = result["groups"]
        assert len(groups) == 1
        assert groups[0]["group_key"] == "p1"
        assert groups[0]["metric_min"] == 12.0
        assert groups[0]["metric_max"] == 15.0
        assert groups[0]["metric_count"] == 3

    def test_aggregate_empty_result(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="nonexistent"),
            AggregationRequest(
                metric_name="GCS",
                data_type="vitals",
                aggregations=["min", "max"],
            ),
        )
        assert result["groups"] == []

    def test_aggregate_labs(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="p1"),
            AggregationRequest(
                metric_name="Hemoglobin",
                data_type="labs",
                aggregations=["min", "max", "count"],
                group_by="patient",
            ),
        )
        groups = result["groups"]
        assert len(groups) == 1
        assert groups[0]["metric_min"] == 13.5
        assert groups[0]["metric_max"] == 14.0
        assert groups[0]["metric_count"] == 2

    def test_aggregate_invalid_data_type(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(),
            AggregationRequest(data_type="diagnoses"),
        )
        assert result["groups"] == []

    def test_aggregate_provider_filter(self, conn, engine):
        result = engine.aggregate(
            conn,
            ClinicalQueryFilters(patient_id="p1", provider_types=["surgeon"]),
            AggregationRequest(
                metric_name="GCS",
                data_type="vitals",
                aggregations=["count"],
                group_by="patient",
            ),
        )
        groups = result["groups"]
        assert len(groups) == 1
        # Only surgeon GCS: v1 and v2
        assert groups[0]["metric_count"] == 2


# ---------------------------------------------------------------------------
# 8.5 — QueryEngine.get_encounter_summary
# ---------------------------------------------------------------------------

class TestGetEncounterSummary:
    def test_returns_none_for_missing(self, conn, engine):
        assert engine.get_encounter_summary(conn, "nonexistent") is None

    def test_returns_encounter_details(self, conn, engine):
        summary = engine.get_encounter_summary(conn, "enc1")
        assert summary is not None
        assert summary["encounter_id"] == "enc1"
        assert summary["patient_id"] == "p1"

    def test_includes_clinical_data(self, conn, engine):
        summary = engine.get_encounter_summary(conn, "enc1")
        assert "clinical_data" in summary
        # enc1 has 3 vitals (GCS x2 + HR) and 1 lab
        assert len(summary["clinical_data"]["vitals"]) == 3
        assert len(summary["clinical_data"]["labs"]) == 1

    def test_includes_provenance(self, conn, engine):
        summary = engine.get_encounter_summary(conn, "enc1")
        vitals = summary["clinical_data"]["vitals"]
        # v1 has provenance
        v1_row = [v for v in vitals if v["id"] == "v1"]
        assert len(v1_row) == 1
        assert v1_row[0]["provenance_id"] == "prov1"

    def test_empty_encounter_has_empty_clinical_data(self, conn, engine):
        # Create an encounter with no clinical data
        conn.execute(
            "INSERT INTO encounters (encounter_id, patient_id, encounter_date, source_file) "
            "VALUES ('enc_empty', 'p1', '2024-06-01', 'empty.pdf')"
        )
        summary = engine.get_encounter_summary(conn, "enc_empty")
        assert summary is not None
        for dtype_rows in summary["clinical_data"].values():
            assert dtype_rows == []
