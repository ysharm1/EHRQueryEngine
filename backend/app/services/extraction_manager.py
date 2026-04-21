"""
Extraction Manager
Orchestrates the full PDF extraction pipeline: watch → parse → extract → store.
Tracks job status, handles retries with exponential backoff.
"""
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

JOB_STATUS_PENDING = "pending"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

MAX_RETRIES = 3


@dataclass
class ExtractionJob:
    job_id: str
    file_path: str
    file_name: str
    file_hash: str = ""
    status: str = JOB_STATUS_PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    patient_id: Optional[str] = None
    records_extracted: int = 0
    confidence: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class ExtractionStats:
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    pending_jobs: int = 0
    jobs_today: int = 0
    success_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_records_per_job: float = 0.0


class ExtractionManager:
    """
    Orchestrates the full PDF extraction pipeline.
    Manages job lifecycle: pending → processing → completed/failed.
    Supports retry with exponential backoff.
    """

    def __init__(self, duckdb_conn=None, llm_provider: str = "openai") -> None:
        self._conn = duckdb_conn
        self._llm_provider = llm_provider
        self._jobs: Dict[str, ExtractionJob] = {}  # in-memory cache

    def process_pdf(self, file_path: str) -> ExtractionJob:
        """Process a single PDF file through the full extraction pipeline."""
        from app.services.pdf_parser import PDFParser
        from app.services.ai_extractor import AIClinicalExtractor
        from app.services.clinical_data_mapper import ClinicalDataMapper
        from app.services.pdf_watcher import FileHashTracker

        job_id = str(uuid.uuid4())
        file_name = Path(file_path).name

        # Compute hash
        tracker = FileHashTracker()
        try:
            file_hash = tracker._compute_hash(file_path)
        except Exception:
            file_hash = ""

        job = ExtractionJob(
            job_id=job_id,
            file_path=file_path,
            file_name=file_name,
            file_hash=file_hash,
        )
        self._jobs[job_id] = job
        self._persist_job(job)

        self._execute_with_retry(job)
        return job

    def _execute_with_retry(self, job: ExtractionJob) -> None:
        """Execute extraction with exponential backoff retry."""
        from app.services.pdf_parser import PDFParser
        from app.services.ai_extractor import AIClinicalExtractor
        from app.services.clinical_data_mapper import ClinicalDataMapper

        for attempt in range(MAX_RETRIES + 1):
            try:
                job.status = JOB_STATUS_PROCESSING
                job.retry_count = attempt
                self._persist_job(job)

                # Step 1: Parse PDF (returns ParsedPDFWithPages)
                parser = PDFParser()
                parsed = parser.extract_text(job.file_path)
                if parsed.extraction_method == "failed":
                    raise ValueError(f"PDF parsing failed: {parsed.error}")

                # Step 2: AI extraction with per-page text
                extractor = AIClinicalExtractor(llm_provider=self._llm_provider)
                pages = getattr(parsed, 'pages', None)
                record = extractor.extract(
                    parsed.raw_text,
                    source_file=job.file_path,
                    pages=pages,
                )

                # Step 3: Map to DuckDB with extraction_job_id for provenance
                if self._conn:
                    mapper = ClinicalDataMapper()
                    patient_id = mapper.map_and_insert(
                        self._conn,
                        record,
                        source_file=job.file_path,
                        extraction_job_id=job.job_id,
                    )
                    job.patient_id = patient_id

                # Count records
                job.records_extracted = (
                    len(record.vitals) + len(record.labs) + len(record.diagnoses) +
                    len(record.procedures) + len(record.medications) +
                    len(record.notes) + len(record.imaging)
                )
                job.confidence = record.extraction_confidence
                job.status = JOB_STATUS_COMPLETED
                job.completed_at = datetime.now().isoformat()
                self._persist_job(job)
                logger.info("Extraction completed: %s (%d records)", job.file_name, job.records_extracted)
                return

            except Exception as exc:
                job.error_message = str(exc)
                if attempt < MAX_RETRIES:
                    wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                    logger.warning("Extraction attempt %d failed for %s, retrying in %ds: %s",
                                   attempt + 1, job.file_name, wait, exc)
                    time.sleep(wait)
                else:
                    job.status = JOB_STATUS_FAILED
                    job.completed_at = datetime.now().isoformat()
                    self._persist_job(job)
                    logger.error("Extraction failed after %d attempts: %s — %s",
                                 MAX_RETRIES + 1, job.file_name, exc)

    def retry_job(self, job_id: str) -> Optional[ExtractionJob]:
        """Retry a failed job."""
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = JOB_STATUS_PENDING
        job.error_message = None
        job.retry_count = 0
        self._execute_with_retry(job)
        return job

    def get_job(self, job_id: str) -> Optional[ExtractionJob]:
        """Get job by ID (from memory cache or DuckDB)."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        return self._load_job_from_db(job_id)

    def list_jobs(self, limit: int = 50, status: Optional[str] = None) -> List[ExtractionJob]:
        """List jobs from DuckDB."""
        if not self._conn:
            return list(self._jobs.values())
        try:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM extraction_jobs WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    [status, limit]
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM extraction_jobs ORDER BY created_at DESC LIMIT ?",
                    [limit]
                ).fetchall()
            return [self._row_to_job(r) for r in rows]
        except Exception:
            return []

    def get_stats(self) -> ExtractionStats:
        """Aggregate extraction statistics."""
        if not self._conn:
            jobs = list(self._jobs.values())
            total = len(jobs)
            completed = sum(1 for j in jobs if j.status == JOB_STATUS_COMPLETED)
            failed = sum(1 for j in jobs if j.status == JOB_STATUS_FAILED)
            pending = sum(1 for j in jobs if j.status in (JOB_STATUS_PENDING, JOB_STATUS_PROCESSING))
            avg_conf = sum(j.confidence for j in jobs if j.status == JOB_STATUS_COMPLETED) / max(completed, 1)
            return ExtractionStats(
                total_jobs=total, completed_jobs=completed, failed_jobs=failed,
                pending_jobs=pending, success_rate=completed / max(total, 1),
                avg_confidence=avg_conf
            )
        try:
            row = self._conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status IN ('pending','processing') THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN DATE(created_at)=CURRENT_DATE THEN 1 ELSE 0 END) as today,
                    AVG(CASE WHEN status='completed' THEN confidence END) as avg_conf,
                    AVG(CASE WHEN status='completed' THEN records_extracted END) as avg_records
                FROM extraction_jobs
            """).fetchone()
            total = row[0] or 0
            completed = row[1] or 0
            return ExtractionStats(
                total_jobs=total, completed_jobs=completed,
                failed_jobs=row[2] or 0, pending_jobs=row[3] or 0,
                jobs_today=row[4] or 0,
                success_rate=completed / max(total, 1),
                avg_confidence=row[5] or 0.0,
                avg_records_per_job=row[6] or 0.0,
            )
        except Exception:
            return ExtractionStats()

    def _persist_job(self, job: ExtractionJob) -> None:
        """Upsert job record to DuckDB extraction_jobs table."""
        if not self._conn:
            return
        try:
            existing = self._conn.execute(
                "SELECT job_id FROM extraction_jobs WHERE job_id=?", [job.job_id]
            ).fetchone()
            if existing:
                self._conn.execute("""
                    UPDATE extraction_jobs SET status=?, completed_at=?, patient_id=?,
                    records_extracted=?, confidence=?, error_message=?, retry_count=?
                    WHERE job_id=?
                """, [job.status, job.completed_at, job.patient_id,
                      job.records_extracted, job.confidence, job.error_message,
                      job.retry_count, job.job_id])
            else:
                self._conn.execute("""
                    INSERT INTO extraction_jobs
                    (job_id, file_path, file_name, file_hash, status, created_at,
                     completed_at, patient_id, records_extracted, confidence, error_message, retry_count)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, [job.job_id, job.file_path, job.file_name, job.file_hash,
                      job.status, job.created_at, job.completed_at, job.patient_id,
                      job.records_extracted, job.confidence, job.error_message, job.retry_count])
        except Exception as e:
            logger.warning("Failed to persist job %s: %s", job.job_id, e)

    def _load_job_from_db(self, job_id: str) -> Optional[ExtractionJob]:
        if not self._conn:
            return None
        try:
            row = self._conn.execute(
                "SELECT * FROM extraction_jobs WHERE job_id=?", [job_id]
            ).fetchone()
            return self._row_to_job(row) if row else None
        except Exception:
            return None

    def _row_to_job(self, row) -> ExtractionJob:
        return ExtractionJob(
            job_id=row[0], file_path=row[1] or "", file_name=row[2] or "",
            file_hash=row[3] or "", status=row[4] or JOB_STATUS_PENDING,
            created_at=str(row[5]) if row[5] else datetime.now().isoformat(),
            completed_at=str(row[6]) if row[6] else None,
            patient_id=row[7], records_extracted=row[8] or 0,
            confidence=row[9] or 0.0, error_message=row[10], retry_count=row[11] or 0,
        )