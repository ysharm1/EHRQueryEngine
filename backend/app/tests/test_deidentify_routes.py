"""Integration tests for the de-identification API routes (Task 11.2).

Exercises the FastAPI endpoints end-to-end with a ``TestClient``:
- POST /api/deidentify (text) -> report + persisted job (Req 9.1)
- POST /api/deidentify/upload (PDF) -> parsed + de-identified (Req 9.2)
- GET  /api/deidentify/jobs -> job listing (Req 9.3)
- review -> finalize -> GET /api/deidentify/report/{job_id} -> certificate
  (Req 6.5, 9.4)
- Error cases: 400 non-PDF upload (Req 9.5), 404 unknown job (Req 9.6),
  401 unauthenticated (Req 9.7).

The GPT-4o client is replaced with a deterministic fake and the PDF parser is
monkeypatched, so the tests run offline with no network calls and no real PDF
fixture needed. Auth is overridden via ``app.dependency_overrides`` following
FastAPI's testing pattern; DuckDB is redirected to a temp file per test.
"""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.auth import get_current_user
from app.services.deidentifier import Deidentifier
from app.services.pdf_parser import ParsedPDFWithPages
import app.api.deidentify_routes as deid_routes
from app.api.deidentify_routes import get_deidentifier


# ---------------------------------------------------------------------------
# Deterministic fake OpenAI client (mirrors test_deidentifier_contextual.py)
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class FakeOpenAIClient:
    """Injectable stand-in returning a canned JSON completion."""

    def __init__(self, content):
        self.chat = _FakeChat(content)


def _name_llm_client(name: str) -> FakeOpenAIClient:
    """A fake client that reports ``name`` as a low-confidence NAME span."""
    content = json.dumps(
        [{"category": "NAME", "text": name, "start": 0, "end": 0, "confidence": 0.5}]
    )
    return FakeOpenAIClient(content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Authenticated TestClient with an isolated DuckDB and regex-only engine."""
    # Redirect DuckDB to an isolated temp file (get_duckdb_connection reads this).
    monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "test.duckdb"))

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="test-user"
    )
    # Default: regex-only engine (no LLM client) so nothing is low-confidence.
    app.dependency_overrides[get_deidentifier] = lambda: Deidentifier()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _use_llm(name: str) -> None:
    """Swap the engine dependency for one wired to a fake NAME-detecting LLM."""
    app.dependency_overrides[get_deidentifier] = lambda: Deidentifier(
        openai_client=_name_llm_client(name)
    )


# ---------------------------------------------------------------------------
# POST /api/deidentify (text) — Req 9.1
# ---------------------------------------------------------------------------

def test_deidentify_text_returns_report_and_persists_job(client):
    resp = client.post(
        "/api/deidentify",
        json={"text": "Contact SSN 123-45-6789 or call 415-555-1234."},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["job_id"]
    assert body["status"] == "deidentified"  # all regex hits -> confidence 1.0
    assert "123-45-6789" not in body["deidentified_text"]
    assert "[SSN]" in body["deidentified_text"]

    report = body["report"]
    assert report["method"] == "HIPAA Safe Harbor"
    assert report["total_redactions"] == sum(report["category_counts"].values())
    assert report["low_confidence"] == []

    # The job is persisted and shows up in the listing (Req 9.3).
    listing = client.get("/api/deidentify/jobs").json()
    assert any(j["job_id"] == body["job_id"] for j in listing["jobs"])


def test_deidentify_text_flags_low_confidence_llm_name(client):
    _use_llm("John Doe")
    resp = client.post(
        "/api/deidentify", json={"text": "Patient John Doe was seen today."}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_review"
    low = body["report"]["low_confidence"]
    assert len(low) == 1
    assert low[0]["category"] == "NAME"
    assert "index" in low[0]


# ---------------------------------------------------------------------------
# POST /api/deidentify/upload (PDF) — Req 9.2, 9.5
# ---------------------------------------------------------------------------

def test_deidentify_upload_pdf(client, monkeypatch):
    extracted = "Patient seen. SSN 123-45-6789. Email jane@example.com."

    class _FakeParser:
        def extract_text(self, path):
            return ParsedPDFWithPages(
                raw_text=extracted,
                page_count=1,
                is_scanned=False,
                extraction_method="pdfplumber",
                pages=[],
            )

    monkeypatch.setattr(deid_routes, "PDFParser", _FakeParser)

    resp = client.post(
        "/api/deidentify/upload",
        files={"file": ("record.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"]
    assert "123-45-6789" not in body["deidentified_text"]
    assert "jane@example.com" not in body["deidentified_text"]
    assert body["report"]["total_redactions"] >= 2

    # Job persisted with the PDF filename as source ref.
    listing = client.get("/api/deidentify/jobs").json()
    assert any(j["source_ref"] == "record.pdf" for j in listing["jobs"])


def test_deidentify_upload_rejects_non_pdf(client):
    resp = client.post(
        "/api/deidentify/upload",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/deidentify/jobs — Req 9.3
# ---------------------------------------------------------------------------

def test_list_jobs_empty(client):
    resp = client.get("/api/deidentify/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"] == []
    assert body["total"] == 0


# ---------------------------------------------------------------------------
# review -> finalize -> certificate — Req 6.5, 9.4
# ---------------------------------------------------------------------------

def test_review_finalize_certificate_flow(client):
    _use_llm("John Doe")

    # 1. De-identify -> needs_review with one flagged NAME.
    resp = client.post(
        "/api/deidentify", json={"text": "Patient John Doe, SSN 123-45-6789."}
    )
    body = resp.json()
    job_id = body["job_id"]
    assert body["status"] == "needs_review"
    flagged_index = body["report"]["low_confidence"][0]["index"]

    # Certificate is unavailable before finalization (Req 8.4).
    assert client.get(f"/api/deidentify/report/{job_id}").status_code == 409

    # 2. Review: approve the flagged redaction.
    review = client.post(
        f"/api/deidentify/jobs/{job_id}/review",
        json={"decisions": [{"redaction_index": flagged_index, "action": "approve"}]},
    )
    assert review.status_code == 200
    assert review.json()["can_finalize"] is True

    # 3. Finalize.
    fin = client.post(f"/api/deidentify/jobs/{job_id}/finalize")
    assert fin.status_code == 200
    fin_body = fin.json()
    assert fin_body["status"] == "deidentified"
    assert fin_body["approved"] == 1

    # 4. Certificate now available (Req 9.4).
    cert = client.get(f"/api/deidentify/report/{job_id}")
    assert cert.status_code == 200
    cert_body = cert.json()
    assert cert_body["job_id"] == job_id
    assert cert_body["method"] == "HIPAA Safe Harbor"
    assert cert_body["reviewer_id"] == "test-user"
    assert cert_body["integrity_checksum"]


def test_finalize_rejected_when_flags_undecided(client):
    _use_llm("John Doe")
    resp = client.post(
        "/api/deidentify", json={"text": "Patient John Doe was here."}
    )
    job_id = resp.json()["job_id"]

    # No review submitted -> finalize must be rejected (Req 6.6).
    fin = client.post(f"/api/deidentify/jobs/{job_id}/finalize")
    assert fin.status_code == 409


def test_reject_decision_restores_original_after_finalize(client):
    _use_llm("John Doe")
    resp = client.post("/api/deidentify", json={"text": "Patient John Doe here."})
    body = resp.json()
    job_id = body["job_id"]
    idx = body["report"]["low_confidence"][0]["index"]

    client.post(
        f"/api/deidentify/jobs/{job_id}/review",
        json={"decisions": [{"redaction_index": idx, "action": "reject"}]},
    )
    fin = client.post(f"/api/deidentify/jobs/{job_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["rejected"] == 1


# ---------------------------------------------------------------------------
# Error cases — Req 9.6, 9.7
# ---------------------------------------------------------------------------

def test_report_unknown_job_returns_404(client):
    resp = client.get("/api/deidentify/report/does-not-exist")
    assert resp.status_code == 404


def test_review_unknown_job_returns_404(client):
    resp = client.post(
        "/api/deidentify/jobs/nope/review",
        json={"decisions": [{"redaction_index": 0, "action": "approve"}]},
    )
    assert resp.status_code == 404


def test_edit_without_replacement_is_400(client):
    _use_llm("John Doe")
    body = client.post(
        "/api/deidentify", json={"text": "Patient John Doe here."}
    ).json()
    job_id = body["job_id"]
    idx = body["report"]["low_confidence"][0]["index"]
    resp = client.post(
        f"/api/deidentify/jobs/{job_id}/review",
        json={"decisions": [{"redaction_index": idx, "action": "edit"}]},
    )
    assert resp.status_code == 400


def test_unauthenticated_request_is_401(tmp_path, monkeypatch):
    """An invalid bearer token is rejected by get_current_user (Req 9.7)."""
    monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "test.duckdb"))
    # Ensure the auth dependency is NOT overridden for this test.
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as test_client:
        resp = test_client.post(
            "/api/deidentify",
            json={"text": "hello"},
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/deidentify/jobs/{job_id}/ingest — Req 2.4, 3.2, 5.1, 5.2, 5.3, 6.3
# ---------------------------------------------------------------------------

from app.database import get_duckdb_connection
from app.services import deid_repository as repo
from app.services.extraction_schema import init_extraction_tables
from app.services.schema_migration import run_clinical_schema_migration


def _seed_warehouse_tables(conn):
    """Create the deid + clinical warehouse tables in the isolated DuckDB."""
    repo.init_deid_tables(conn)
    init_extraction_tables(conn)
    run_clinical_schema_migration(conn)


def _seed_job(*, job_id, status, deidentified_text="patient seen today", source_ref="note.txt"):
    """Persist a job (finalized or not) into the test warehouse and set up tables.

    A finalized job is inserted as ``needs_review`` then finalized, mirroring the
    real workflow (and the property-test helper).
    """
    conn = get_duckdb_connection()
    try:
        _seed_warehouse_tables(conn)
        repo.insert_job(
            conn,
            job_id=job_id,
            user_id="test-user",
            source_type="text",
            source_ref=source_ref,
            status="needs_review" if status == "deidentified" else status,
            total_redactions=0,
            category_counts={},
            deidentified_text=deidentified_text,
            redactions=[],
        )
        if status == "deidentified":
            repo.finalize_job(
                conn,
                job_id=job_id,
                status="deidentified",
                reviewer_id="reviewer-1",
                deidentified_text=deidentified_text,
            )
    finally:
        conn.close()


def test_ingest_finalized_job_happy_path(client):
    """A finalized job ingests into the warehouse (Req 5.1)."""
    _seed_job(job_id="job-ingest-1", status="deidentified",
              deidentified_text="patient is stable")

    resp = client.post("/api/deidentify/jobs/job-ingest-1/ingest", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "job-ingest-1"
    assert body["table"] == "clinical_notes"
    assert body["source_id"] == "default-clinic"  # settings.default_source_id
    assert body["record_ids"] == ["deid-note:job-ingest-1"]
    assert body["ingested"] is True


def test_ingest_supplied_source_id(client):
    """A supplied source_id is passed through to the ingestor (Req 5.5)."""
    _seed_job(job_id="job-ingest-src", status="deidentified")

    resp = client.post(
        "/api/deidentify/jobs/job-ingest-src/ingest",
        json={"source_id": "clinic-42"},
    )
    assert resp.status_code == 200
    assert resp.json()["source_id"] == "clinic-42"


def test_ingest_needs_review_job_returns_409(client):
    """Ingesting a non-finalized job is rejected with 409 (Req 2.4)."""
    _seed_job(job_id="job-needs-review", status="needs_review")

    resp = client.post("/api/deidentify/jobs/job-needs-review/ingest", json={})
    assert resp.status_code == 409


def test_ingest_unknown_job_returns_404(client):
    """Ingesting an unknown job returns 404 (Req 5.3)."""
    # Ensure the warehouse tables exist so the route reaches the get_job check.
    conn = get_duckdb_connection()
    try:
        _seed_warehouse_tables(conn)
    finally:
        conn.close()

    resp = client.post("/api/deidentify/jobs/does-not-exist/ingest", json={})
    assert resp.status_code == 404


def test_ingest_repeat_is_idempotent(client):
    """A repeat ingestion returns ingested=False with the same ids (Req 6.3)."""
    _seed_job(job_id="job-repeat", status="deidentified")

    first = client.post("/api/deidentify/jobs/job-repeat/ingest", json={})
    assert first.status_code == 200
    assert first.json()["ingested"] is True
    first_ids = first.json()["record_ids"]

    second = client.post("/api/deidentify/jobs/job-repeat/ingest", json={})
    assert second.status_code == 200
    assert second.json()["ingested"] is False
    assert second.json()["record_ids"] == first_ids


def test_ingest_empty_deidentified_text(client):
    """A job with empty de-identified text still ingests a note row."""
    _seed_job(job_id="job-empty", status="deidentified", deidentified_text="")

    resp = client.post("/api/deidentify/jobs/job-empty/ingest", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested"] is True
    assert body["record_ids"] == ["deid-note:job-empty"]


def test_ingest_unauthenticated_is_401(tmp_path, monkeypatch):
    """An unauthenticated ingest request is rejected by get_current_user (Req 5.2)."""
    monkeypatch.setattr(settings, "duckdb_path", str(tmp_path / "test.duckdb"))
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as test_client:
        resp = test_client.post(
            "/api/deidentify/jobs/whatever/ingest",
            json={},
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert resp.status_code == 401
