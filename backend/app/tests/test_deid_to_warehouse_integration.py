"""End-to-end integration test for de-identified output reaching the warehouse.

Exercises the full slice for the deid-to-warehouse feature (Task 7.1):

    finalize a de-identification job
        -> POST /api/deidentify/jobs/{job_id}/ingest
            -> the de-identified note is present and queryable in the
               ``clinical_notes`` warehouse table.

The de-identified note is confirmed two ways: directly against the DuckDB
connection, and through the existing clinical query path (``QueryEngine`` with
``data_types=["notes"]``) that the clinical query API and cohort search read
from — proving the ingested record is discoverable via the same surface those
features already use (Req 1.4).

The test runs offline: auth is overridden via ``app.dependency_overrides`` and
DuckDB is redirected to a temp file per test, mirroring
``test_deidentify_routes.py``.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.database import get_duckdb_connection
from app.services.auth import get_current_user
from app.services.deidentifier import Deidentifier
from app.api.deidentify_routes import get_deidentifier
from app.services import deid_repository as repo
from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration
from app.services.warehouse_ingestor import WarehouseIngestor
from app.services.clinical_query_engine import QueryEngine, ClinicalQueryFilters


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Authenticated TestClient with an isolated DuckDB and regex-only engine."""
    monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "test.duckdb"))

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="test-user"
    )
    app.dependency_overrides[get_deidentifier] = lambda: Deidentifier()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _seed_finalized_job(*, job_id, deidentified_text, source_ref="note.pdf"):
    """Persist and finalize a de-identification job in the isolated warehouse.

    Mirrors the real workflow: the job is inserted as ``needs_review`` then
    finalized so ``build_certificate`` (the route's compliance gate) succeeds.
    """
    conn = get_duckdb_connection()
    try:
        repo.init_deid_tables(conn)
        init_extraction_tables(conn)
        run_clinical_schema_migration(conn)
        repo.insert_job(
            conn,
            job_id=job_id,
            user_id="test-user",
            source_type="text",
            source_ref=source_ref,
            status="needs_review",
            total_redactions=0,
            category_counts={},
            deidentified_text=deidentified_text,
            redactions=[],
        )
        repo.finalize_job(
            conn,
            job_id=job_id,
            status="deidentified",
            reviewer_id="reviewer-1",
            deidentified_text=deidentified_text,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# End-to-end: finalize -> ingest -> queryable in clinical_notes (Req 1.4)
# ---------------------------------------------------------------------------

def test_finalized_job_ingest_makes_note_queryable_in_warehouse(client):
    job_id = "job-e2e-ingest"
    deid_text = "patient presents with mild headache; vitals stable at [DATE-2023]."

    _seed_finalized_job(job_id=job_id, deidentified_text=deid_text, source_ref="visit.pdf")

    # 1. Ingest the finalized job via the API endpoint.
    resp = client.post(f"/api/deidentify/jobs/{job_id}/ingest", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested"] is True
    assert body["table"] == "clinical_notes"
    note_id = WarehouseIngestor.note_id_for_job(job_id)
    patient_id = WarehouseIngestor.patient_id_for_job(job_id)
    assert body["record_ids"] == [note_id]

    conn = get_duckdb_connection()
    try:
        # 2. The de-identified note is present directly in clinical_notes.
        row = conn.execute(
            "SELECT id, patient_id, note_type, content, source_file, source_id "
            "FROM clinical_notes WHERE id = ?",
            [note_id],
        ).fetchone()
        assert row is not None
        assert row[0] == note_id
        assert row[1] == patient_id
        assert row[2] == "deidentified_note"
        assert row[3] == deid_text          # content == de-identified text (Req 1.2, 2.2)
        assert row[4] == "visit.pdf"        # source_file from source_ref (Req 7.2)
        assert row[5] == "default-clinic"   # default source_id (Req 3.2)

        # 3. The note is discoverable through the existing clinical query path
        #    that the clinical query API / cohort search read from (Req 1.4).
        engine = QueryEngine()
        result = engine.query(
            conn,
            ClinicalQueryFilters(patient_id=patient_id, data_types=["notes"]),
        )
        note_rows = [r for r in result["rows"] if r.get("id") == note_id]
        assert len(note_rows) == 1
        assert note_rows[0]["content"] == deid_text

        # 4. Lineage back to the originating job is resolvable via provenance.
        prov = conn.execute(
            "SELECT extraction_job_id, data_table FROM data_provenance "
            "WHERE data_record_id = ?",
            [note_id],
        ).fetchone()
        assert prov is not None
        assert prov[0] == job_id
        assert prov[1] == "clinical_notes"
    finally:
        conn.close()


def test_ingested_note_survives_idempotent_repeat_and_stays_queryable(client):
    """A repeat ingestion leaves exactly one queryable note row (Req 1.4, 6)."""
    job_id = "job-e2e-repeat"
    deid_text = "follow-up visit, no acute distress"
    _seed_finalized_job(job_id=job_id, deidentified_text=deid_text)

    first = client.post(f"/api/deidentify/jobs/{job_id}/ingest", json={})
    assert first.status_code == 200
    assert first.json()["ingested"] is True

    second = client.post(f"/api/deidentify/jobs/{job_id}/ingest", json={})
    assert second.status_code == 200
    assert second.json()["ingested"] is False

    note_id = WarehouseIngestor.note_id_for_job(job_id)
    conn = get_duckdb_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM clinical_notes WHERE id = ?", [note_id]
        ).fetchone()[0]
        assert count == 1

        engine = QueryEngine()
        result = engine.query(
            conn,
            ClinicalQueryFilters(
                patient_id=WarehouseIngestor.patient_id_for_job(job_id),
                data_types=["notes"],
            ),
        )
        note_rows = [r for r in result["rows"] if r.get("id") == note_id]
        assert len(note_rows) == 1
        assert note_rows[0]["content"] == deid_text
    finally:
        conn.close()
