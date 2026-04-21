"""Tests for EncounterManager.

Covers:
- find_or_create_encounter: deduplication, new creation, explicit encounter_id
- list_encounters: ordering, date filtering
- get_encounter_summary: counts of associated clinical data
"""
import duckdb
import pytest

from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration
from app.services.encounter_manager import EncounterManager


@pytest.fixture
def conn():
    """In-memory DuckDB with base + migration tables."""
    c = duckdb.connect(":memory:")
    init_extraction_tables(c)
    run_clinical_schema_migration(c)
    # Seed a patient
    c.execute("INSERT INTO patients (patient_id) VALUES ('p1')")
    yield c
    c.close()


@pytest.fixture
def mgr():
    return EncounterManager()


# --- find_or_create_encounter -------------------------------------------------

class TestFindOrCreateEncounter:
    def test_creates_new_encounter_when_none_exists(self, conn, mgr):
        eid = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "inpatient", "f.pdf")
        assert eid is not None
        row = conn.execute("SELECT * FROM encounters WHERE encounter_id = ?", [eid]).fetchone()
        assert row is not None

    def test_deduplicates_by_patient_date_type(self, conn, mgr):
        eid1 = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "inpatient", "a.pdf")
        eid2 = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "inpatient", "b.pdf")
        assert eid1 == eid2

    def test_different_type_creates_new(self, conn, mgr):
        eid1 = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "inpatient", "a.pdf")
        eid2 = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "outpatient", "b.pdf")
        assert eid1 != eid2

    def test_explicit_encounter_id_hint_returns_existing(self, conn, mgr):
        eid = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "ED", "a.pdf", encounter_id_hint="enc-100")
        assert eid == "enc-100"
        # Second call with same hint should return existing
        eid2 = mgr.find_or_create_encounter(conn, "p1", "2024-07-01", "ED", "b.pdf", encounter_id_hint="enc-100")
        assert eid2 == "enc-100"
        # Only one encounter row
        count = conn.execute("SELECT COUNT(*) FROM encounters WHERE encounter_id = 'enc-100'").fetchone()[0]
        assert count == 1

    def test_no_date_creates_new_each_time(self, conn, mgr):
        eid1 = mgr.find_or_create_encounter(conn, "p1", None, None, "a.pdf")
        eid2 = mgr.find_or_create_encounter(conn, "p1", None, None, "b.pdf")
        assert eid1 != eid2

    def test_null_type_deduplicates_correctly(self, conn, mgr):
        eid1 = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", None, "a.pdf")
        eid2 = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", None, "b.pdf")
        assert eid1 == eid2


# --- list_encounters ----------------------------------------------------------

class TestListEncounters:
    def test_returns_encounters_ordered_desc(self, conn, mgr):
        mgr.find_or_create_encounter(conn, "p1", "2024-01-01", "inpatient", "a.pdf")
        mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "outpatient", "b.pdf")
        mgr.find_or_create_encounter(conn, "p1", "2024-03-15", "ED", "c.pdf")

        results = mgr.list_encounters(conn, "p1")
        dates = [str(r["encounter_date"]) for r in results]
        assert dates == ["2024-06-01", "2024-03-15", "2024-01-01"]

    def test_filters_by_date_range(self, conn, mgr):
        mgr.find_or_create_encounter(conn, "p1", "2024-01-01", "inpatient", "a.pdf")
        mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "outpatient", "b.pdf")
        mgr.find_or_create_encounter(conn, "p1", "2024-12-01", "ED", "c.pdf")

        results = mgr.list_encounters(conn, "p1", date_from="2024-02-01", date_to="2024-07-01")
        assert len(results) == 1
        assert str(results[0]["encounter_date"]) == "2024-06-01"

    def test_empty_for_unknown_patient(self, conn, mgr):
        results = mgr.list_encounters(conn, "unknown-patient")
        assert results == []


# --- get_encounter_summary ----------------------------------------------------

class TestGetEncounterSummary:
    def test_returns_none_for_missing_encounter(self, conn, mgr):
        assert mgr.get_encounter_summary(conn, "nonexistent") is None

    def test_returns_encounter_with_zero_counts(self, conn, mgr):
        eid = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "inpatient", "a.pdf")
        summary = mgr.get_encounter_summary(conn, eid)
        assert summary["encounter_id"] == eid
        assert summary["patient_id"] == "p1"
        assert all(v == 0 for v in summary["data_counts"].values())

    def test_counts_associated_clinical_data(self, conn, mgr):
        eid = mgr.find_or_create_encounter(conn, "p1", "2024-06-01", "inpatient", "a.pdf")

        # Insert some clinical data linked to this encounter
        conn.execute(
            "INSERT INTO vital_signs (id, patient_id, vital_name, value, encounter_id) "
            "VALUES ('v1', 'p1', 'HR', 72, ?), ('v2', 'p1', 'BP', 120, ?)",
            [eid, eid],
        )
        conn.execute(
            "INSERT INTO lab_results (id, patient_id, test_name, encounter_id) "
            "VALUES ('l1', 'p1', 'CBC', ?)",
            [eid],
        )
        conn.execute(
            "INSERT INTO diagnoses (id, patient_id, description, encounter_id) "
            "VALUES ('d1', 'p1', 'Flu', ?)",
            [eid],
        )

        summary = mgr.get_encounter_summary(conn, eid)
        assert summary["data_counts"]["vitals"] == 2
        assert summary["data_counts"]["labs"] == 1
        assert summary["data_counts"]["diagnoses"] == 1
        assert summary["data_counts"]["procedures"] == 0
        assert summary["data_counts"]["medications"] == 0
        assert summary["data_counts"]["notes"] == 0
        assert summary["data_counts"]["imaging"] == 0
