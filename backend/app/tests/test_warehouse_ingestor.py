"""Property-based tests for the Warehouse_Ingestor (deid-to-warehouse spec).

Each of the five correctness properties from the design maps to exactly one
property-based test here. Properties run against an isolated in-memory DuckDB
loaded with the de-identification tables (``repo.init_deid_tables``), the
clinical warehouse tables (``init_extraction_tables`` +
``run_clinical_schema_migration`` for ``clinical_notes`` / ``data_provenance``),
and the ingestion tables (``WarehouseIngestor.init_tables``) — mirroring the
``deid_repository`` test fixtures.

Finalized jobs are produced through the real repository path
(``insert_job`` -> ``finalize_job`` -> ``get_job``), and redactions carry
distinctive ``original_text`` markers so the no-PHI-leak property has concrete
values to scan the warehouse for.
"""
from __future__ import annotations

import duckdb
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.services import deid_repository as repo
from app.services.deid_repository import build_certificate
from app.services.deidentifier import IdentifierCategory, Redaction
from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration
from app.services.warehouse_ingestor import (
    FINALIZED_STATUS,
    INGESTED_NOTE_TYPE,
    TARGET_TABLE,
    IngestionResult,
    JobNotIngestableError,
    WarehouseIngestor,
)

DEFAULT_SOURCE_ID = "default-clinic"

# ---------------------------------------------------------------------------
# Generators
#
# Distinct alphabets keep the pieces non-overlapping so the no-PHI-leak scan is
# meaningful: de-identified text / source refs / ids are lowercase, while PHI
# markers are uppercase with a "PHI_" prefix, so a marker can never be an
# accidental substring of the de-identified text.
# ---------------------------------------------------------------------------

_LOWER = "abcdefghijklmnopqrstuvwxyz "
_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-"
_MARKER_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

_job_id = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=30)
_deidentified_text = st.text(alphabet=_LOWER, min_size=0, max_size=80)
_source_ref = st.text(alphabet="abcdefghijklmnopqrstuvwxyz-._", min_size=0, max_size=30)
_source_id = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=20)
# Distinctive PHI markers — uppercase so they cannot appear in the lowercase
# de-identified text / refs.
_marker = st.builds(lambda s: f"PHI_{s}", st.text(alphabet=_MARKER_ALPHABET, min_size=4, max_size=10))
_markers = st.lists(_marker, min_size=0, max_size=5, unique=True)

_NON_FINALIZED_STATUSES = ["needs_review", "processing", "failed", "pending"]
_status = st.sampled_from([FINALIZED_STATUS] + _NON_FINALIZED_STATUSES)


def _setup_conn():
    """In-memory DuckDB with deid + warehouse + ingestion tables initialized."""
    conn = duckdb.connect(":memory:")
    repo.init_deid_tables(conn)
    init_extraction_tables(conn)
    run_clinical_schema_migration(conn)
    WarehouseIngestor(DEFAULT_SOURCE_ID).init_tables(conn)
    return conn


def _build_redactions(markers):
    """Build Redaction objects whose original_text are the distinctive markers."""
    redactions = []
    for i, marker in enumerate(markers):
        redactions.append(
            Redaction(
                category=IdentifierCategory.NAME,
                start=i,
                end=i + 1,
                original_text=marker,
                token="[NAME]",
                method="regex",
                confidence=1.0,
            )
        )
    return redactions


def _insert_job(conn, *, job_id, status, source_ref, deidentified_text, markers):
    """Persist a job (and its marker redactions) through the repository path.

    When ``status`` is the finalized status, the job is inserted as
    ``needs_review`` then finalized (mirroring the real workflow); otherwise it
    is inserted directly with the given non-finalized status.
    """
    redactions = _build_redactions(markers)
    repo.insert_job(
        conn,
        job_id=job_id,
        user_id="user-1",
        source_type="text",
        source_ref=source_ref,
        status="needs_review" if status == FINALIZED_STATUS else status,
        total_redactions=len(redactions),
        category_counts={"NAME": len(redactions)} if redactions else {},
        deidentified_text=deidentified_text,
        redactions=redactions,
    )
    if status == FINALIZED_STATUS:
        repo.finalize_job(
            conn,
            job_id=job_id,
            status=FINALIZED_STATUS,
            reviewer_id="reviewer-1",
            deidentified_text=deidentified_text,
        )
    return repo.get_job(conn, job_id)


def _all_warehouse_cells(conn):
    """Return every cell (as string) written to the warehouse by ingestion."""
    cells = []
    for table in ("clinical_notes", "data_provenance", "deid_ingestions"):
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in rows:
            for cell in row:
                if cell is not None:
                    cells.append(str(cell))
    return cells


def _warehouse_row_snapshot(conn):
    """A comparable snapshot of the warehouse rows relevant to ingestion."""
    return {
        "clinical_notes": sorted(
            str(r) for r in conn.execute(
                "SELECT id, patient_id, note_type, content, source_file, source_id "
                "FROM clinical_notes"
            ).fetchall()
        ),
        "data_provenance": sorted(
            str(r) for r in conn.execute(
                "SELECT data_record_id, data_table, source_file, extraction_job_id "
                "FROM data_provenance"
            ).fetchall()
        ),
        "deid_ingestions": sorted(
            str(r) for r in conn.execute(
                "SELECT job_id, source_id, target_table, record_ids, "
                "certificate_checksum FROM deid_ingestions"
            ).fetchall()
        ),
    }


# ---------------------------------------------------------------------------
# Property 1: De-identified-only ingestion gate
# Feature: deid-to-warehouse, Property 1: De-identified-only ingestion gate
# Validates: Requirements 2.1
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(
    job_id=_job_id,
    status=_status,
    source_ref=_source_ref,
    deidentified_text=_deidentified_text,
    markers=_markers,
)
def test_property_1_ingestion_gate(job_id, status, source_ref, deidentified_text, markers):
    """Non-finalized jobs raise and write nothing; finalized jobs write rows."""
    conn = _setup_conn()
    try:
        job = _insert_job(
            conn,
            job_id=job_id,
            status=status,
            source_ref=source_ref,
            deidentified_text=deidentified_text,
            markers=markers,
        )
        ingestor = WarehouseIngestor(DEFAULT_SOURCE_ID)

        if status != FINALIZED_STATUS:
            # Non-finalized: raise and leave the warehouse untouched.
            try:
                ingestor.ingest_job(conn, job=job, certificate={})
                raised = False
            except JobNotIngestableError:
                raised = True
            assert raised, f"expected JobNotIngestableError for status {status!r}"

            assert conn.execute("SELECT COUNT(*) FROM clinical_notes").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM data_provenance").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM deid_ingestions").fetchone()[0] == 0
        else:
            certificate = build_certificate(job)
            result = ingestor.ingest_job(conn, job=job, certificate=certificate)
            assert isinstance(result, IngestionResult)
            assert len(result.record_ids) >= 1
            assert conn.execute("SELECT COUNT(*) FROM clinical_notes").fetchone()[0] == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Property 2: No PHI leaks into the Warehouse
# Feature: deid-to-warehouse, Property 2: No PHI leaks into the Warehouse
# Validates: Requirements 2.2, 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(
    job_id=_job_id,
    source_ref=_source_ref,
    deidentified_text=_deidentified_text,
    markers=st.lists(_marker, min_size=1, max_size=5, unique=True),
)
def test_property_2_no_phi_leak(job_id, source_ref, deidentified_text, markers):
    """content == deidentified_text and no warehouse cell contains a marker."""
    # Markers must not coincidentally appear in the de-identified text/refs.
    assume(all(m not in deidentified_text for m in markers))
    assume(all(m not in source_ref for m in markers))
    assume(all(m not in job_id for m in markers))

    conn = _setup_conn()
    try:
        job = _insert_job(
            conn,
            job_id=job_id,
            status=FINALIZED_STATUS,
            source_ref=source_ref,
            deidentified_text=deidentified_text,
            markers=markers,
        )
        certificate = build_certificate(job)
        WarehouseIngestor(DEFAULT_SOURCE_ID).ingest_job(
            conn, job=job, certificate=certificate
        )

        content = conn.execute(
            "SELECT content FROM clinical_notes WHERE id = ?",
            [WarehouseIngestor.note_id_for_job(job_id)],
        ).fetchone()[0]
        assert content == deidentified_text

        cells = _all_warehouse_cells(conn)
        for marker in markers:
            for cell in cells:
                assert marker not in cell, (
                    f"PHI marker {marker!r} leaked into warehouse cell {cell!r}"
                )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Property 3: Idempotent ingestion
# Feature: deid-to-warehouse, Property 3: Idempotent ingestion
# Validates: Requirements 6.1, 6.2, 6.3
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(
    job_id=_job_id,
    source_ref=_source_ref,
    deidentified_text=_deidentified_text,
    markers=_markers,
    n=st.integers(min_value=1, max_value=5),
)
def test_property_3_idempotent(job_id, source_ref, deidentified_text, markers, n):
    """N ingestions leave the same rows as one; repeats report already_ingested."""
    conn = _setup_conn()
    try:
        job = _insert_job(
            conn,
            job_id=job_id,
            status=FINALIZED_STATUS,
            source_ref=source_ref,
            deidentified_text=deidentified_text,
            markers=markers,
        )
        certificate = build_certificate(job)
        ingestor = WarehouseIngestor(DEFAULT_SOURCE_ID)

        first = ingestor.ingest_job(conn, job=job, certificate=certificate)
        assert first.already_ingested is False
        snapshot_after_first = _warehouse_row_snapshot(conn)

        for _ in range(n - 1):
            repeat = ingestor.ingest_job(conn, job=job, certificate=certificate)
            assert repeat.already_ingested is True
            assert repeat.record_ids == first.record_ids

        # Row sets after N ingestions are identical to after one.
        assert _warehouse_row_snapshot(conn) == snapshot_after_first
        # No duplicate rows for the job.
        assert conn.execute("SELECT COUNT(*) FROM clinical_notes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM data_provenance").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM deid_ingestions").fetchone()[0] == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Property 4: Lineage and source completeness
# Feature: deid-to-warehouse, Property 4: Lineage and source completeness
# Validates: Requirements 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 5.5
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(
    job_id=_job_id,
    source_ref=_source_ref,
    deidentified_text=_deidentified_text,
    markers=_markers,
    supplied_source_id=st.one_of(st.none(), _source_id),
)
def test_property_4_lineage_and_source(
    job_id, source_ref, deidentified_text, markers, supplied_source_id
):
    """Every record carries the resolved source_id + job_id; lineage rows exist."""
    conn = _setup_conn()
    try:
        job = _insert_job(
            conn,
            job_id=job_id,
            status=FINALIZED_STATUS,
            source_ref=source_ref,
            deidentified_text=deidentified_text,
            markers=markers,
        )
        certificate = build_certificate(job)
        result = WarehouseIngestor(DEFAULT_SOURCE_ID).ingest_job(
            conn, job=job, certificate=certificate, source_id=supplied_source_id
        )

        expected_source = supplied_source_id or DEFAULT_SOURCE_ID
        assert result.source_id == expected_source

        # Every Ingested_Record carries the resolved source_id (Req 3.1).
        note_source = conn.execute(
            "SELECT source_id FROM clinical_notes WHERE id = ?",
            [WarehouseIngestor.note_id_for_job(job_id)],
        ).fetchone()[0]
        assert note_source == expected_source

        # Single deid_ingestions lineage row (Req 4.2, 4.4, 3.3).
        ing = conn.execute(
            "SELECT source_id, target_table, record_ids, certificate_checksum "
            "FROM deid_ingestions WHERE job_id = ?",
            [job_id],
        ).fetchall()
        assert len(ing) == 1
        ing_source, ing_table, ing_record_ids, ing_checksum = ing[0]
        assert ing_source == expected_source
        assert ing_table == TARGET_TABLE
        import json as _json
        stored_ids = _json.loads(ing_record_ids) if isinstance(ing_record_ids, str) else ing_record_ids
        assert list(stored_ids) == result.record_ids
        assert ing_checksum == certificate["integrity_checksum"]

        # data_provenance linkage back to the job (Req 4.1, 4.3).
        prov = conn.execute(
            "SELECT extraction_job_id, data_table FROM data_provenance "
            "WHERE data_record_id = ?",
            [WarehouseIngestor.note_id_for_job(job_id)],
        ).fetchall()
        assert len(prov) == 1
        assert prov[0][0] == job_id
        assert prov[0][1] == TARGET_TABLE
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Property 5: Ingestion produces a faithful, queryable note record
# Feature: deid-to-warehouse, Property 5: Ingestion produces a faithful,
# queryable note record
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.4
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(
    job_id=_job_id,
    source_ref=_source_ref,
    deidentified_text=_deidentified_text,
    markers=_markers,
)
def test_property_5_faithful_note_record(job_id, source_ref, deidentified_text, markers):
    """Exactly one clinical_notes row with the expected shape; ids match rows."""
    conn = _setup_conn()
    try:
        job = _insert_job(
            conn,
            job_id=job_id,
            status=FINALIZED_STATUS,
            source_ref=source_ref,
            deidentified_text=deidentified_text,
            markers=markers,
        )
        certificate = build_certificate(job)
        result = WarehouseIngestor(DEFAULT_SOURCE_ID).ingest_job(
            conn, job=job, certificate=certificate
        )

        rows = conn.execute(
            "SELECT id, note_type, source_file, content FROM clinical_notes"
        ).fetchall()
        assert len(rows) == 1
        note_id, note_type, note_source_file, content = rows[0]
        assert note_id == WarehouseIngestor.note_id_for_job(job_id)
        assert note_type == INGESTED_NOTE_TYPE
        assert note_source_file == source_ref
        assert content == deidentified_text

        # IngestionResult names the target table and lists exactly the rows
        # present in that table.
        assert result.table == TARGET_TABLE
        table_ids = [
            r[0] for r in conn.execute("SELECT id FROM clinical_notes").fetchall()
        ]
        assert sorted(result.record_ids) == sorted(table_ids)
    finally:
        conn.close()
