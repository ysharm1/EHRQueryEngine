"""De-identification API routes (HIPAA Safe Harbor).

Exposes the Deidentifier service over REST, following the conventions in
``extraction_routes.py``: authentication via ``get_current_user`` on every
route, a DuckDB connection opened/closed per request, and audit logging through
``AuditLogService``.

Endpoints (mounted under ``/api`` in ``main.py``):
    POST   /api/deidentify                       de-identify raw text
    POST   /api/deidentify/upload                de-identify an uploaded PDF
    GET    /api/deidentify/jobs                  list de-identification jobs
    GET    /api/deidentify/report/{job_id}       certificate for a finalized job
    POST   /api/deidentify/jobs/{job_id}/review  submit review decisions
    POST   /api/deidentify/jobs/{job_id}/finalize finalize a reviewed job

All endpoints require an authenticated user (Req 9.7). The GPT-4o client used by
the Deidentifier is dependency-injected via ``get_deidentifier`` so it can be
replaced with a deterministic fake in tests (no network / no real PHI leaves the
process).

Implements the de-identification-service spec (Task 11.1).
_Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 8.1, 8.4._
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, get_duckdb_connection
from app.models.user import User
from app.services.audit_log import AuditLogService
from app.services.auth import get_current_user
from app.services import deid_repository as repo
from app.services.deid_repository import JobNotFinalizedError
from app.services.deidentifier import (
    Deidentifier,
    DeidentificationResult,
    IdentifierCategory,
    Redaction,
    ReviewDecision,
    _YEAR_PATTERN,
)
from app.services.pdf_parser import PDFParser

router = APIRouter(prefix="/deidentify", tags=["deidentify"])

# Directory for temporarily storing uploaded PDFs before parsing. Reuses the
# same persistent-disk-with-/tmp-fallback strategy as extraction_routes.
_preferred_dir = os.environ.get("PDF_UPLOAD_DIR", "/opt/render/project/data/pdfs")
try:
    os.makedirs(_preferred_dir, exist_ok=True)
    PDF_UPLOAD_DIR = _preferred_dir
except OSError:
    PDF_UPLOAD_DIR = "/tmp/pdfs"
    os.makedirs(PDF_UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE_MB = 50


# ---------------------------------------------------------------------------
# Dependency: the Deidentifier engine
#
# Constructed from settings so the GPT-4o key is picked up in production. In
# tests this dependency is overridden (app.dependency_overrides) with a factory
# that returns a Deidentifier wired to a fake OpenAI client, so contextual
# detection runs offline and no real PHI is sent anywhere.
# ---------------------------------------------------------------------------

def get_deidentifier() -> Deidentifier:
    """Provide a Deidentifier engine (overridable in tests)."""
    return Deidentifier(openai_api_key=settings.openai_api_key)


# ---------------------------------------------------------------------------
# Pydantic request / response models (design.md "API response shapes")
# ---------------------------------------------------------------------------

class DeidentifyTextRequest(BaseModel):
    text: str


class RedactionOut(BaseModel):
    index: int  # position in the job's redaction list (used for review)
    category: str
    start: int
    end: int
    token: str
    method: str
    confidence: float


class DeidentifyReportOut(BaseModel):
    method: str = "HIPAA Safe Harbor"
    category_counts: dict[str, int]
    total_redactions: int
    low_confidence: list[RedactionOut]


class DeidentifyResponse(BaseModel):
    job_id: str
    status: str  # 'needs_review' | 'deidentified'
    deidentified_text: str
    report: DeidentifyReportOut


class JobSummaryOut(BaseModel):
    job_id: str
    source_ref: Optional[str]
    status: str
    created_at: Optional[str]
    total_redactions: Optional[int]


class JobListResponse(BaseModel):
    jobs: list[JobSummaryOut]
    total: int


class ReviewDecisionIn(BaseModel):
    redaction_index: int
    action: str  # 'approve' | 'reject' | 'edit'
    replacement: Optional[str] = None


class ReviewRequest(BaseModel):
    decisions: list[ReviewDecisionIn]


class ReviewResponse(BaseModel):
    job_id: str
    status: str
    flagged: int
    decided: int
    can_finalize: bool


class FinalizeResponse(BaseModel):
    job_id: str
    status: str
    approved: int
    rejected: int
    edited: int


class CertificateOut(BaseModel):
    job_id: str
    source_ref: Optional[str]
    method: str = "HIPAA Safe Harbor"
    category_counts: dict[str, int]
    total_redactions: int
    reviewer_id: Optional[str]
    finalized_at: Optional[str]
    integrity_checksum: str


_VALID_REVIEW_ACTIONS = {"approve", "reject", "edit"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redaction_out(redaction: Redaction, index: int) -> RedactionOut:
    """Serialise a Redaction for the API, tagged with its list index."""
    return RedactionOut(
        index=index,
        category=redaction.category.value,
        start=redaction.start,
        end=redaction.end,
        token=redaction.token,
        method=redaction.method,
        confidence=redaction.confidence,
    )


def _report_out(result: DeidentificationResult) -> DeidentifyReportOut:
    """Build the report payload, tagging low-confidence items with their index."""
    index_by_id = {id(r): i for i, r in enumerate(result.redactions)}
    low = [
        _redaction_out(r, index_by_id[id(r)]) for r in result.report.low_confidence
    ]
    return DeidentifyReportOut(
        method=result.report.method,
        category_counts=dict(result.report.category_counts),
        total_redactions=result.report.total_redactions,
        low_confidence=low,
    )


def _persist_result(
    conn,
    *,
    user_id: Optional[str],
    source_type: str,
    source_ref: str,
    result: DeidentificationResult,
) -> str:
    """Persist a fresh de-identification result and return the new job_id."""
    job_id = str(uuid.uuid4())
    repo.insert_job(
        conn,
        job_id=job_id,
        user_id=user_id,
        source_type=source_type,
        source_ref=source_ref,
        status=result.status,
        total_redactions=result.report.total_redactions,
        category_counts=dict(result.report.category_counts),
        deidentified_text=result.deidentified_text,
        redactions=result.redactions,
    )
    return job_id


def _rebuild_result(job: dict, threshold: float) -> DeidentificationResult:
    """Reconstruct a DeidentificationResult from a persisted job.

    Redactions are rebuilt in stored (index) order. For DATE redactions the
    preserved year is recomputed from ``original_text`` exactly as detection
    did, so the reconstructed tokens match the stored de-identified text and the
    review re-application stays byte-aligned.
    """
    redactions: list[Redaction] = []
    for row in job["redactions"]:
        category = IdentifierCategory(row["category"])
        preserved_year: Optional[str] = None
        if category == IdentifierCategory.DATE:
            match = _YEAR_PATTERN.search(row["original_text"] or "")
            preserved_year = match.group() if match else None
        redactions.append(
            Redaction(
                category=category,
                start=int(row["start"]),
                end=int(row["end"]),
                original_text=row["original_text"] or "",
                token=row["token"],
                method=row["method"],
                confidence=float(row["confidence"]),
                preserved_year=preserved_year,
            )
        )
    report = Deidentifier.build_report(redactions, threshold)
    return DeidentificationResult(
        deidentified_text=job["deidentified_text"],
        redactions=redactions,
        report=report,
        status=job["status"],
    )


def _stored_decisions(job: dict) -> list[ReviewDecision]:
    """Collect the review decisions persisted on a job's redactions."""
    decisions: list[ReviewDecision] = []
    for index, row in enumerate(job["redactions"]):
        action = row.get("review_action")
        if action:
            decisions.append(
                ReviewDecision(
                    redaction_index=index,
                    action=action,
                    replacement=row.get("review_replacement"),
                )
            )
    return decisions


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=DeidentifyResponse)
async def deidentify_text(
    request: DeidentifyTextRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    deid: Deidentifier = Depends(get_deidentifier),
):
    """De-identify raw text, persist the job, and return the report (Req 9.1)."""
    result = deid.deidentify(request.text)

    conn = get_duckdb_connection()
    try:
        repo.init_deid_tables(conn)
        job_id = _persist_result(
            conn,
            user_id=current_user.id,
            source_type="text",
            source_ref="inline-text",
            result=result,
        )
    finally:
        conn.close()

    _audit_deidentify(db, current_user, req, "inline-text", result, job_id)

    return DeidentifyResponse(
        job_id=job_id,
        status=result.status,
        deidentified_text=result.deidentified_text,
        report=_report_out(result),
    )


@router.post("/upload", response_model=DeidentifyResponse)
async def deidentify_upload(
    file: UploadFile = File(...),
    req: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    deid: Deidentifier = Depends(get_deidentifier),
):
    """Parse an uploaded PDF, de-identify its text, and persist the job (Req 9.2).

    Rejects non-PDF uploads with a 400 (Req 9.5).
    """
    # Reject non-PDF files (Req 9.5).
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    upload_dir = Path(PDF_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = file.filename.replace(" ", "_").replace("/", "_")
    dest_path = upload_dir / f"{timestamp}_{safe_name}"
    with open(dest_path, "wb") as fh:
        fh.write(contents)

    try:
        parsed = PDFParser().extract_text(str(dest_path))
        result = deid.deidentify(parsed.raw_text or "")

        conn = get_duckdb_connection()
        try:
            repo.init_deid_tables(conn)
            job_id = _persist_result(
                conn,
                user_id=current_user.id,
                source_type="pdf",
                source_ref=file.filename,
                result=result,
            )
        finally:
            conn.close()
    finally:
        # The uploaded PDF has been parsed; do not retain the original PHI file.
        try:
            dest_path.unlink()
        except OSError:
            pass

    _audit_deidentify(db, current_user, req, file.filename, result, job_id)

    return DeidentifyResponse(
        job_id=job_id,
        status=result.status,
        deidentified_text=result.deidentified_text,
        report=_report_out(result),
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_deid_jobs(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """List de-identification jobs, most recent first (Req 9.3)."""
    conn = get_duckdb_connection()
    try:
        repo.init_deid_tables(conn)
        jobs = repo.list_jobs(conn, limit=limit)
    finally:
        conn.close()
    return JobListResponse(
        jobs=[JobSummaryOut(**j) for j in jobs],
        total=len(jobs),
    )


@router.get("/report/{job_id}", response_model=CertificateOut)
async def get_deid_report(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the certificate for a finalized job (Req 9.4).

    404 when the job is unknown (Req 9.6); 409 when it is not finalized
    (Req 8.4).
    """
    conn = get_duckdb_connection()
    try:
        repo.init_deid_tables(conn)
        try:
            certificate = repo.get_certificate(conn, job_id)
        except JobNotFinalizedError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    finally:
        conn.close()

    if certificate is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    return CertificateOut(**certificate)


@router.post("/jobs/{job_id}/review", response_model=ReviewResponse)
async def review_deid_job(
    job_id: str,
    request: ReviewRequest,
    current_user: User = Depends(get_current_user),
    deid: Deidentifier = Depends(get_deidentifier),
):
    """Persist reviewer decisions for a job's flagged redactions (Req 6.2-6.4).

    404 when the job is unknown (Req 9.6); 400 for an invalid decision.
    """
    conn = get_duckdb_connection()
    try:
        repo.init_deid_tables(conn)
        job = repo.get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

        redaction_count = len(job["redactions"])
        for decision in request.decisions:
            if not (0 <= decision.redaction_index < redaction_count):
                raise HTTPException(
                    status_code=400,
                    detail=f"redaction_index {decision.redaction_index} out of range",
                )
            if decision.action not in _VALID_REVIEW_ACTIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown review action {decision.action!r}",
                )
            if decision.action == "edit" and not decision.replacement:
                raise HTTPException(
                    status_code=400,
                    detail="Review action 'edit' requires a non-empty replacement",
                )

        for decision in request.decisions:
            repo.update_redaction_review(
                conn,
                job_id=job_id,
                redaction_index=decision.redaction_index,
                review_action=decision.action,
                review_replacement=decision.replacement,
            )

        # Recompute gating status from the freshly persisted decisions.
        updated = repo.get_job(conn, job_id)
    finally:
        conn.close()

    result = _rebuild_result(updated, deid.review_threshold)
    decisions = _stored_decisions(updated)
    flagged = {
        i
        for i, r in enumerate(result.redactions)
        if r.confidence < deid.review_threshold
    }
    decided = {d.redaction_index for d in decisions}

    return ReviewResponse(
        job_id=job_id,
        status=updated["status"],
        flagged=len(flagged),
        decided=len(flagged & decided),
        can_finalize=deid.can_finalize(result, decisions),
    )


@router.post("/jobs/{job_id}/finalize", response_model=FinalizeResponse)
async def finalize_deid_job(
    job_id: str,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    deid: Deidentifier = Depends(get_deidentifier),
):
    """Finalize a reviewed job, gating on decided flags (Req 6.5, 6.6).

    404 when the job is unknown (Req 9.6); 409 when flagged redactions remain
    undecided (Req 6.6).
    """
    conn = get_duckdb_connection()
    try:
        repo.init_deid_tables(conn)
        job = repo.get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

        result = _rebuild_result(job, deid.review_threshold)
        decisions = _stored_decisions(job)

        if not deid.can_finalize(result, decisions):
            raise HTTPException(
                status_code=409,
                detail="Cannot finalize: flagged redactions still require review",
            )

        reviewed = deid.apply_review(result, decisions)
        repo.finalize_job(
            conn,
            job_id=job_id,
            status="deidentified",
            reviewer_id=current_user.id,
            deidentified_text=reviewed.deidentified_text,
        )
    finally:
        conn.close()

    approved = sum(1 for d in decisions if d.action == "approve")
    rejected = sum(1 for d in decisions if d.action == "reject")
    edited = sum(1 for d in decisions if d.action == "edit")

    _audit_finalize(db, current_user, req, job_id, approved, rejected, edited)

    return FinalizeResponse(
        job_id=job_id,
        status="deidentified",
        approved=approved,
        rejected=rejected,
        edited=edited,
    )


# ---------------------------------------------------------------------------
# Audit logging (Req 7.1, 7.2) — never blocks the primary response.
# ---------------------------------------------------------------------------

def _audit_deidentify(
    db: Session,
    current_user: User,
    req: Optional[Request],
    source_ref: str,
    result: DeidentificationResult,
    job_id: str,
) -> None:
    """Record a de-identification audit entry (Req 7.1). Best-effort."""
    try:
        audit = AuditLogService(db)
        audit.log_deidentification(
            user_id=current_user.id,
            source_ref=source_ref,
            category_counts=dict(result.report.category_counts),
            total_redactions=result.report.total_redactions,
            job_id=job_id,
            ip_address=req.client.host if req and req.client else None,
            user_agent=req.headers.get("user-agent") if req else None,
        )
    except Exception:  # pragma: no cover - audit must not break the response
        import logging

        logging.getLogger(__name__).exception("Failed to write de-identify audit log")


def _audit_finalize(
    db: Session,
    current_user: User,
    req: Optional[Request],
    job_id: str,
    approved: int,
    rejected: int,
    edited: int,
) -> None:
    """Record a finalize audit entry (Req 7.2). Best-effort."""
    try:
        audit = AuditLogService(db)
        audit.log_deidentification_finalize(
            user_id=current_user.id,
            job_id=job_id,
            approved=approved,
            rejected=rejected,
            edited=edited,
            ip_address=req.client.host if req and req.client else None,
            user_agent=req.headers.get("user-agent") if req else None,
        )
    except Exception:  # pragma: no cover - audit must not break the response
        import logging

        logging.getLogger(__name__).exception("Failed to write finalize audit log")
