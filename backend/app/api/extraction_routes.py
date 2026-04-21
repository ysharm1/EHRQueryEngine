"""Extraction API routes."""
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, get_duckdb_connection
from app.services.auth import get_current_user
from app.services.extraction_manager import ExtractionManager
from app.models.user import User

# Directory for uploaded PDFs — uses Render persistent disk or local fallback
PDF_UPLOAD_DIR = os.environ.get("PDF_UPLOAD_DIR", "/var/data/pdfs")
MAX_UPLOAD_SIZE_MB = 50

router = APIRouter(prefix="/extraction", tags=["extraction"])

CONFIG_PATH = os.environ.get("EXTRACTION_CONFIG_PATH", "extraction_config.json")


def _get_manager(conn=None) -> ExtractionManager:
    return ExtractionManager(duckdb_conn=conn)


class ProcessRequest(BaseModel):
    file_path: str


class ConfigUpdate(BaseModel):
    watched_folders: list = []
    llm_provider: str = "openai"
    ocr_enabled: bool = True
    auto_process: bool = True
    extraction_hints: dict = {}
    sync: dict = {"mode": "local_only", "cloud_endpoint": None}
    retention_days: int = 90


@router.get("/status")
async def get_status(current_user: User = Depends(get_current_user)):
    """Overall extraction service status."""
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        stats = manager.get_stats()
        return {
            "status": "running",
            "total_jobs": stats.total_jobs,
            "completed_jobs": stats.completed_jobs,
            "failed_jobs": stats.failed_jobs,
            "pending_jobs": stats.pending_jobs,
        }
    finally:
        conn.close()


@router.get("/jobs")
async def list_jobs(
    limit: int = 50,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """List extraction jobs with pagination."""
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        jobs = manager.list_jobs(limit=limit, status=status)
        return {
            "jobs": [
                {
                    "job_id": j.job_id, "file_name": j.file_name,
                    "status": j.status, "created_at": j.created_at,
                    "completed_at": j.completed_at, "patient_id": j.patient_id,
                    "records_extracted": j.records_extracted,
                    "confidence": j.confidence, "error_message": j.error_message,
                }
                for j in jobs
            ],
            "total": len(jobs),
        }
    finally:
        conn.close()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, current_user: User = Depends(get_current_user)):
    """Get single job details."""
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        job = manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job.job_id, "file_path": job.file_path,
            "file_name": job.file_name, "status": job.status,
            "created_at": job.created_at, "completed_at": job.completed_at,
            "patient_id": job.patient_id, "records_extracted": job.records_extracted,
            "confidence": job.confidence, "error_message": job.error_message,
            "retry_count": job.retry_count,
        }
    finally:
        conn.close()


@router.post("/process")
async def process_pdf(
    request: ProcessRequest,
    current_user: User = Depends(get_current_user)
):
    """Manually trigger PDF processing."""
    if not Path(request.file_path).exists():
        raise HTTPException(status_code=400, detail=f"File not found: {request.file_path}")
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        job = manager.process_pdf(request.file_path)
        return {"job_id": job.job_id, "status": job.status, "file_name": job.file_name}
    finally:
        conn.close()


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF file and trigger extraction.

    Saves the file to persistent disk and runs the full extraction pipeline:
    parse → AI extract → store in DuckDB with encounter + provenance tracking.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Validate file size (read content once)
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Ensure upload directory exists
    upload_dir = Path(PDF_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file (add timestamp prefix to avoid collisions)
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = file.filename.replace(" ", "_").replace("/", "_")
    dest_path = upload_dir / f"{timestamp}_{safe_name}"

    with open(dest_path, "wb") as f:
        f.write(contents)

    # Run extraction pipeline
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        job = manager.process_pdf(str(dest_path))
        return {
            "job_id": job.job_id,
            "status": job.status,
            "file_name": job.file_name,
            "records_extracted": job.records_extracted,
            "confidence": job.confidence,
            "error_message": job.error_message,
        }
    finally:
        conn.close()


@router.post("/retry/{job_id}")
async def retry_job(job_id: str, current_user: User = Depends(get_current_user)):
    """Retry a failed extraction job."""
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        job = manager.retry_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job_id": job.job_id, "status": job.status}
    finally:
        conn.close()


@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """Extraction statistics."""
    conn = get_duckdb_connection()
    try:
        manager = _get_manager(conn)
        stats = manager.get_stats()
        return {
            "total_jobs": stats.total_jobs,
            "completed_jobs": stats.completed_jobs,
            "failed_jobs": stats.failed_jobs,
            "pending_jobs": stats.pending_jobs,
            "jobs_today": stats.jobs_today,
            "success_rate": round(stats.success_rate * 100, 1),
            "avg_confidence": round(stats.avg_confidence * 100, 1),
            "avg_records_per_job": round(stats.avg_records_per_job, 1),
        }
    finally:
        conn.close()


@router.get("/config")
async def get_config(current_user: User = Depends(get_current_user)):
    """Get extraction configuration."""
    if Path(CONFIG_PATH).exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return ConfigUpdate().dict()


@router.put("/config")
async def update_config(config: ConfigUpdate, current_user: User = Depends(get_current_user)):
    """Update extraction configuration."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config.dict(), f, indent=2)
    return {"status": "updated", "config": config.dict()}