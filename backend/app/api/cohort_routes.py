"""Cohort Search API routes.

Provides embedding-based semantic search over clinical notes,
reindexing, and stats endpoints.

Implements Requirements 3.2, 3.9, 1.4
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, get_duckdb_connection
from app.services.audit_log import AuditLogService
from app.services.auth import get_current_user
from app.services.cohort_search_engine import CohortSearchEngine
from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cohort", tags=["cohort"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CohortSearchRequest(BaseModel):
    query: str
    top_k: int = 20
    threshold: float = 0.3
    patient_id: Optional[str] = None


class CohortSearchResult(BaseModel):
    patient_id: str
    relevant_sentence: str
    note_date: Optional[str] = None
    similarity_score: float
    note_id: str
    encounter_id: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /api/cohort/search
# ---------------------------------------------------------------------------

@router.post("/search")
async def cohort_search(
    request: CohortSearchRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search clinical notes by semantic similarity."""
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Cohort search unavailable.",
        )

    conn = get_duckdb_connection()
    try:
        engine = CohortSearchEngine(conn)
        results = engine.search(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold,
            patient_id=request.patient_id,
        )

        # Audit logging
        audit = AuditLogService(db)
        audit.log_query_submission(
            user_id=current_user.id,
            query_text=json.dumps({
                "action": "cohort_search",
                "query": request.query,
                "top_k": request.top_k,
                "threshold": request.threshold,
                "result_count": len(results),
            }),
            ip_address=req.client.host if req.client else None,
            user_agent=req.headers.get("user-agent"),
        )

        return {"results": results, "total": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cohort search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST /api/cohort/reindex
# ---------------------------------------------------------------------------

@router.post("/reindex")
async def reindex_embeddings(
    current_user: User = Depends(get_current_user),
):
    """Regenerate all note embeddings."""
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key not configured. Reindex unavailable.",
        )

    conn = get_duckdb_connection()
    try:
        engine = CohortSearchEngine(conn)
        stats = engine.reindex_all()
        return stats
    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/cohort/stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def cohort_stats(
    current_user: User = Depends(get_current_user),
):
    """Return embedding index statistics."""
    conn = get_duckdb_connection()
    try:
        row = conn.execute("SELECT COUNT(*) FROM note_embeddings").fetchone()
        embedding_count = row[0] if row else 0

        patient_row = conn.execute(
            "SELECT COUNT(DISTINCT patient_id) FROM note_embeddings"
        ).fetchone()
        patient_count = patient_row[0] if patient_row else 0

        note_row = conn.execute(
            "SELECT COUNT(DISTINCT note_id) FROM note_embeddings"
        ).fetchone()
        note_count = note_row[0] if note_row else 0

        return {
            "embedding_count": embedding_count,
            "patient_count": patient_count,
            "note_count": note_count,
        }
    except Exception as e:
        logger.error(f"Stats query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")
    finally:
        conn.close()
