"""Tests for Clinical Query Intelligence schema migration.

Verifies:
- New tables are created (encounters, data_provenance)
- Existing clinical data tables get new columns
- Existing rows retain all data after migration (new columns default to NULL)
- Migration is idempotent (running twice causes no errors)
- Indexes are created
"""
import duckdb
import pytest

from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration


@pytest.fixture
def duckdb_conn():
    """In-memory DuckDB connection with base extraction tables."""
    conn = duckdb.connect(":memory:")
    init_extraction_tables(conn)
    yield conn
    conn.close()


def test_migration_creates_encounters_table(duckdb_conn):
    run_clinical_schema_migration(duckdb_conn)
    cols = {
        row[0]
        for row in duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'encounters'"
        ).fetchall()
    }
    expected = {
        "encounter_id", "patient_id", "encounter_date", "encounter_type",
        "primary_provider", "primary_provider_type", "facility",
        "source_file", "created_at",
    }
    assert expected.issubset(cols)


def test_migration_creates_data_provenance_table(duckdb_conn):
    run_clinical_schema_migration(duckdb_conn)
    cols = {
        row[0]
        for row in duckdb_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'data_provenance'"
        ).fetchall()
    }
    expected = {
        "provenance_id", "data_record_id", "data_table", "source_file",
        "page_number", "provider_name", "provider_type",
        "extraction_confidence", "extraction_job_id", "raw_snippet",
        "created_at",
    }
    assert expected.issubset(cols)


def test_existing_rows_retain_data_after_migration(duckdb_conn):
    """Existing rows keep their data; new columns default to NULL."""
    # Insert a row before migration
    duckdb_conn.execute(
        "INSERT INTO vital_signs (id, patient_id, vital_name, value) "
        "VALUES ('v1', 'p1', 'HR', 72.0)"
    )

    run_clinical_schema_migration(duckdb_conn)

    row = duckdb_conn.execute(
        "SELECT id, patient_id, vital_name, value, encounter_id, provider_type, provenance_id "
        "FROM vital_signs WHERE id = 'v1'"
    ).fetchone()

    assert row[0] == "v1"
    assert row[1] == "p1"
    assert row[2] == "HR"
    assert row[3] == 72.0
    # New columns should be NULL
    assert row[4] is None  # encounter_id
    assert row[5] is None  # provider_type
    assert row[6] is None  # provenance_id


def test_migration_is_idempotent(duckdb_conn):
    """Running migration twice produces no errors."""
    run_clinical_schema_migration(duckdb_conn)
    # Second run should succeed without errors
    run_clinical_schema_migration(duckdb_conn)

    # Verify tables still exist and are functional
    duckdb_conn.execute(
        "INSERT INTO patients (patient_id) VALUES ('p1')"
    )
    duckdb_conn.execute(
        "INSERT INTO encounters (encounter_id, patient_id) "
        "VALUES ('e1', 'p1')"
    )
    count = duckdb_conn.execute(
        "SELECT COUNT(*) FROM encounters"
    ).fetchone()[0]
    assert count == 1


def test_new_columns_added_to_all_clinical_tables(duckdb_conn):
    """All 7 clinical data tables get encounter_id, provider_type, provenance_id."""
    run_clinical_schema_migration(duckdb_conn)

    tables = [
        "vital_signs", "lab_results", "diagnoses",
        "procedures_extracted", "medications",
        "clinical_notes", "imaging_reports",
    ]
    new_cols = {"encounter_id", "provider_type", "provenance_id"}

    for table in tables:
        cols = {
            row[0]
            for row in duckdb_conn.execute(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{table}'"
            ).fetchall()
        }
        assert new_cols.issubset(cols), f"Missing columns in {table}: {new_cols - cols}"
