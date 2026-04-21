"""Clinical Query API routes.

Exposes the query engine, encounter manager, and provenance mapper
via REST endpoints for the clinical query frontend.

Implements Requirements 5.1, 5.2, 5.3, 5.6, 5.7, 3.4, 1.6
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_duckdb_connection
from app.services.auth import get_current_user
from app.services.clinical_query_engine import (
    AggregationRequest,
    ClinicalQueryFilters,
    QueryEngine,
    validate_query_filters,
)
from app.services.encounter_manager import EncounterManager
from app.services.provenance_mapper import ProvenanceMapper
from app.models.user import User

router = APIRouter(prefix="/clinical", tags=["clinical"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ClinicalQueryRequest(BaseModel):
    patient_id: Optional[str] = None
    encounter_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    provider_types: Optional[List[str]] = None
    data_types: Optional[List[str]] = None
    vital_names: Optional[List[str]] = None
    lab_names: Optional[List[str]] = None
    limit: int = 100
    offset: int = 0


class AggregateRequest(BaseModel):
    patient_id: Optional[str] = None
    encounter_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    provider_types: Optional[List[str]] = None
    metric_name: str
    data_type: str  # "vitals" | "labs"
    aggregations: List[str] = ["min", "max", "avg"]
    group_by: str = "encounter"


# ---------------------------------------------------------------------------
# POST /api/clinical/query
# ---------------------------------------------------------------------------

@router.post("/query")
async def clinical_query(
    request: ClinicalQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Query clinical data with flexible filters."""
    filters = ClinicalQueryFilters(
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        date_from=request.date_from,
        date_to=request.date_to,
        provider_types=request.provider_types,
        data_types=request.data_types,
        vital_names=request.vital_names,
        lab_names=request.lab_names,
        limit=request.limit,
        offset=request.offset,
    )

    errors = validate_query_filters(filters)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    conn = get_duckdb_connection()
    try:
        engine = QueryEngine()
        result = engine.query(conn, filters)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# POST /api/clinical/aggregate
# ---------------------------------------------------------------------------

@router.post("/aggregate")
async def clinical_aggregate(
    request: AggregateRequest,
    current_user: User = Depends(get_current_user),
):
    """Compute aggregated metrics per group."""
    filters = ClinicalQueryFilters(
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        date_from=request.date_from,
        date_to=request.date_to,
        provider_types=request.provider_types,
    )

    errors = validate_query_filters(filters)
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    agg = AggregationRequest(
        metric_name=request.metric_name,
        data_type=request.data_type,
        aggregations=request.aggregations,
        group_by=request.group_by,
    )

    conn = get_duckdb_connection()
    try:
        engine = QueryEngine()
        result = engine.aggregate(conn, filters, agg)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/clinical/encounters/{patient_id}
# ---------------------------------------------------------------------------

@router.get("/encounters/{patient_id}")
async def list_encounters(
    patient_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """List encounters for a patient within an optional date range."""
    conn = get_duckdb_connection()
    try:
        manager = EncounterManager()
        encounters = manager.list_encounters(
            conn, patient_id, date_from=date_from, date_to=date_to
        )
        return {"encounters": encounters, "total": len(encounters)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/clinical/encounters/{encounter_id}/summary
# ---------------------------------------------------------------------------

@router.get("/encounters/{encounter_id}/summary")
async def get_encounter_summary(
    encounter_id: str,
    current_user: User = Depends(get_current_user),
):
    """Full summary of a single encounter with all data and provenance."""
    conn = get_duckdb_connection()
    try:
        engine = QueryEngine()
        summary = engine.get_encounter_summary(conn, encounter_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return summary
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/clinical/provenance/{provenance_id}
# ---------------------------------------------------------------------------

@router.get("/provenance/{provenance_id}")
async def get_provenance(
    provenance_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve full provenance detail for a data point."""
    conn = get_duckdb_connection()
    try:
        mapper = ProvenanceMapper()
        provenance = mapper.get_provenance(conn, provenance_id)
        if provenance is None:
            raise HTTPException(status_code=404, detail="Provenance not found")
        return provenance
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /api/clinical/providers
# ---------------------------------------------------------------------------

@router.get("/providers")
async def list_providers(
    current_user: User = Depends(get_current_user),
):
    """Return distinct provider types from the database."""
    conn = get_duckdb_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT provider_type FROM data_provenance "
            "WHERE provider_type IS NOT NULL"
        ).fetchall()
        provider_types = [row[0] for row in rows]
        return {"provider_types": provider_types}
    finally:
        conn.close()
