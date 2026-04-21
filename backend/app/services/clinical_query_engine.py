"""Clinical Query Engine — translates structured filter requests into DuckDB SQL.

Supports filtered queries across clinical tables with JOINs to encounters
and data_provenance, per-visit aggregations, and encounter summaries.

Implements Requirements 2.1, 2.2, 2.3, 2.6, 3.3, 5.1, 5.2, 5.3, 5.4, 5.8
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

VALID_PROVIDER_TYPES = frozenset([
    "physician", "surgeon", "neurologist", "cardiologist",
    "nurse", "nurse_practitioner", "physician_assistant",
    "pharmacist", "therapist", "radiologist", "pathologist", "other",
])

VALID_DATA_TYPES = frozenset([
    "vitals", "labs", "diagnoses", "procedures",
    "medications", "notes", "imaging",
])

# Maps logical data_type names to (table_name, name_column) pairs
_TABLE_MAP: Dict[str, tuple[str, str]] = {
    "vitals": ("vital_signs", "vital_name"),
    "labs": ("lab_results", "test_name"),
    "diagnoses": ("diagnoses", "description"),
    "procedures": ("procedures_extracted", "description"),
    "medications": ("medications", "drug_name"),
    "notes": ("clinical_notes", "note_type"),
    "imaging": ("imaging_reports", "modality"),
}

# ISO 8601 date pattern (YYYY-MM-DD)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Sub-task 8.1 — Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClinicalQueryFilters:
    """Structured filter request for clinical data queries."""
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


@dataclass
class AggregationRequest:
    """Request for aggregated metrics over clinical data."""
    metric_name: str = ""
    data_type: str = "vitals"  # "vitals" or "labs"
    aggregations: List[str] = field(default_factory=lambda: ["min", "max", "avg"])
    group_by: str = "encounter"  # "encounter" | "patient" | "day"


# ---------------------------------------------------------------------------
# Sub-task 8.2 — Validation
# ---------------------------------------------------------------------------

def validate_query_filters(filters: ClinicalQueryFilters) -> List[str]:
    """Validate query filters and return a list of error strings.

    Returns an empty list when all filters are valid.
    """
    errors: List[str] = []

    # Date format checks
    if filters.date_from and not _ISO_DATE_RE.match(filters.date_from):
        errors.append(
            f"date_from '{filters.date_from}' is not valid ISO 8601 (YYYY-MM-DD)"
        )
    if filters.date_to and not _ISO_DATE_RE.match(filters.date_to):
        errors.append(
            f"date_to '{filters.date_to}' is not valid ISO 8601 (YYYY-MM-DD)"
        )

    # Provider type vocabulary
    if filters.provider_types:
        for pt in filters.provider_types:
            if pt not in VALID_PROVIDER_TYPES:
                errors.append(
                    f"provider_type '{pt}' is not in the controlled vocabulary"
                )

    # Data type vocabulary
    if filters.data_types:
        for dt in filters.data_types:
            if dt not in VALID_DATA_TYPES:
                errors.append(
                    f"data_type '{dt}' is not valid; expected one of {sorted(VALID_DATA_TYPES)}"
                )

    # Limit / offset bounds
    if filters.limit <= 0:
        errors.append(f"limit must be > 0, got {filters.limit}")
    if filters.offset < 0:
        errors.append(f"offset must be >= 0, got {filters.offset}")

    return errors


# ---------------------------------------------------------------------------
# Sub-task 8.3 / 8.4 / 8.5 — QueryEngine
# ---------------------------------------------------------------------------

class QueryEngine:
    """Translate structured filter requests into parameterized DuckDB SQL."""

    # -----------------------------------------------------------------------
    # 8.3 — query()
    # -----------------------------------------------------------------------

    def query(self, conn, filters: ClinicalQueryFilters) -> Dict[str, Any]:
        """Execute a filtered query across clinical tables.

        Returns ``{rows, total_count, provenance_refs}``.
        """
        target_types = list(filters.data_types) if filters.data_types else list(_TABLE_MAP.keys())
        all_rows: List[Dict[str, Any]] = []
        provenance_refs: Dict[str, str] = {}

        for dtype in target_types:
            if dtype not in _TABLE_MAP:
                continue
            table_name, name_col = _TABLE_MAP[dtype]

            where_clauses: List[str] = []
            params: List[Any] = []

            # Patient filter
            if filters.patient_id:
                where_clauses.append("d.patient_id = ?")
                params.append(filters.patient_id)

            # Encounter filter
            if filters.encounter_id:
                where_clauses.append("d.encounter_id = ?")
                params.append(filters.encounter_id)

            # Date range via encounter JOIN
            if filters.date_from:
                where_clauses.append("e.encounter_date >= ?")
                params.append(filters.date_from)
            if filters.date_to:
                where_clauses.append("e.encounter_date <= ?")
                params.append(filters.date_to)

            # Provider type filter
            if filters.provider_types:
                placeholders = ", ".join(["?"] * len(filters.provider_types))
                where_clauses.append(f"d.provider_type IN ({placeholders})")
                params.extend(filters.provider_types)

            # Vital name filter
            if filters.vital_names and table_name == "vital_signs":
                placeholders = ", ".join(["?"] * len(filters.vital_names))
                where_clauses.append(f"d.vital_name IN ({placeholders})")
                params.extend(filters.vital_names)

            # Lab name filter
            if filters.lab_names and table_name == "lab_results":
                placeholders = ", ".join(["?"] * len(filters.lab_names))
                where_clauses.append(f"d.test_name IN ({placeholders})")
                params.extend(filters.lab_names)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Count query (for total_count across this table)
            count_sql = (
                f"SELECT COUNT(*) FROM {table_name} d "
                f"LEFT JOIN encounters e ON d.encounter_id = e.encounter_id "
                f"LEFT JOIN data_provenance dp "
                f"  ON dp.data_record_id = d.id AND dp.data_table = ? "
                f"WHERE {where_sql}"
            )
            count_params = [table_name] + params
            table_total = conn.execute(count_sql, count_params).fetchone()[0]

            # Data query with pagination
            data_sql = (
                f"SELECT d.*, e.encounter_date AS enc_date, e.encounter_type AS enc_type, "
                f"  dp.provenance_id, dp.source_file AS prov_source_file, "
                f"  dp.page_number, dp.provider_name AS prov_provider_name, "
                f"  dp.provider_type AS prov_provider_type "
                f"FROM {table_name} d "
                f"LEFT JOIN encounters e ON d.encounter_id = e.encounter_id "
                f"LEFT JOIN data_provenance dp "
                f"  ON dp.data_record_id = d.id AND dp.data_table = ? "
                f"WHERE {where_sql} "
                f"ORDER BY e.encounter_date DESC NULLS LAST "
                f"LIMIT ? OFFSET ?"
            )
            data_params = [table_name] + params + [filters.limit, filters.offset]
            rows = conn.execute(data_sql, data_params).fetchall()
            col_names = [desc[0] for desc in conn.description]

            for row in rows:
                record = dict(zip(col_names, row))
                record["_data_type"] = dtype
                all_rows.append(record)
                prov_id = record.get("provenance_id")
                rec_id = record.get("id")
                if prov_id and rec_id:
                    provenance_refs[rec_id] = prov_id

        return {
            "rows": all_rows,
            "total_count": len(all_rows),
            "provenance_refs": provenance_refs,
        }


    # -----------------------------------------------------------------------
    # 8.4 — aggregate()
    # -----------------------------------------------------------------------

    def aggregate(
        self, conn, filters: ClinicalQueryFilters, agg: AggregationRequest
    ) -> Dict[str, Any]:
        """Compute aggregated metrics per group.

        Returns ``{groups: [{group_key, group_label, metrics}]}``.
        """
        if agg.data_type not in ("vitals", "labs"):
            return {"groups": []}

        table_name, name_col = _TABLE_MAP[agg.data_type]
        value_col = "value"

        # Determine GROUP BY expression and label column
        if agg.group_by == "patient":
            group_expr = "d.patient_id"
            group_label_expr = "d.patient_id"
        elif agg.group_by == "day":
            group_expr = "CAST(e.encounter_date AS VARCHAR)"
            group_label_expr = "CAST(e.encounter_date AS VARCHAR)"
        else:  # default: encounter
            group_expr = "e.encounter_id"
            group_label_expr = "CAST(e.encounter_date AS VARCHAR)"

        # Build standard aggregation SELECT clauses
        agg_selects: List[str] = []
        needs_first = "first" in agg.aggregations
        needs_last = "last" in agg.aggregations

        for a in agg.aggregations:
            if a == "min":
                agg_selects.append(
                    f"MIN(CAST(d.{value_col} AS DOUBLE)) AS metric_min"
                )
            elif a == "max":
                agg_selects.append(
                    f"MAX(CAST(d.{value_col} AS DOUBLE)) AS metric_max"
                )
            elif a == "avg":
                agg_selects.append(
                    f"AVG(CAST(d.{value_col} AS DOUBLE)) AS metric_avg"
                )
            elif a == "count":
                agg_selects.append("COUNT(*) AS metric_count")
            # first/last handled via subqueries below

        # WHERE clauses
        where_clauses: List[str] = [f"d.{name_col} = ?"]
        params: List[Any] = [agg.metric_name]

        if filters.patient_id:
            where_clauses.append("d.patient_id = ?")
            params.append(filters.patient_id)
        if filters.encounter_id:
            where_clauses.append("e.encounter_id = ?")
            params.append(filters.encounter_id)
        if filters.date_from:
            where_clauses.append("e.encounter_date >= ?")
            params.append(filters.date_from)
        if filters.date_to:
            where_clauses.append("e.encounter_date <= ?")
            params.append(filters.date_to)
        if filters.provider_types:
            placeholders = ", ".join(["?"] * len(filters.provider_types))
            where_clauses.append(f"d.provider_type IN ({placeholders})")
            params.extend(filters.provider_types)

        where_sql = " AND ".join(where_clauses)

        agg_select_sql = ", ".join(agg_selects) if agg_selects else "COUNT(*) AS metric_count"

        # For FIRST_VALUE / LAST_VALUE we run a separate query per group
        # to avoid correlated-subquery issues with GROUP BY in DuckDB.
        if not needs_first and not needs_last:
            sql = (
                f"SELECT {group_expr} AS group_key, "
                f"  {group_label_expr} AS group_label, "
                f"  {agg_select_sql} "
                f"FROM {table_name} d "
                f"LEFT JOIN encounters e ON d.encounter_id = e.encounter_id "
                f"WHERE {where_sql} "
                f"GROUP BY {group_expr}, {group_label_expr} "
                f"ORDER BY group_label DESC NULLS LAST"
            )

            rows = conn.execute(sql, params).fetchall()
            col_names = [desc[0] for desc in conn.description]

            groups: List[Dict[str, Any]] = []
            for row in rows:
                groups.append(dict(zip(col_names, row)))
            return {"groups": groups}

        # When first/last are requested, compute standard aggs first,
        # then compute first/last via ORDER BY + LIMIT per group.
        base_sql = (
            f"SELECT {group_expr} AS group_key, "
            f"  {group_label_expr} AS group_label, "
            f"  {agg_select_sql} "
            f"FROM {table_name} d "
            f"LEFT JOIN encounters e ON d.encounter_id = e.encounter_id "
            f"WHERE {where_sql} "
            f"GROUP BY {group_expr}, {group_label_expr} "
            f"ORDER BY group_label DESC NULLS LAST"
        )

        rows = conn.execute(base_sql, params).fetchall()
        col_names = [desc[0] for desc in conn.description]

        groups: List[Dict[str, Any]] = []
        for row in rows:
            record = dict(zip(col_names, row))
            gk = record["group_key"]

            # Build a WHERE clause scoped to this group
            group_where = where_clauses.copy()
            group_params = params.copy()
            if agg.group_by == "patient":
                group_where.append("d.patient_id = ?")
                group_params.append(gk)
            elif agg.group_by == "day":
                group_where.append("CAST(e.encounter_date AS VARCHAR) = ?")
                group_params.append(gk)
            else:
                group_where.append("e.encounter_id = ?")
                group_params.append(gk)

            group_where_sql = " AND ".join(group_where)

            if needs_first:
                first_sql = (
                    f"SELECT CAST(d.{value_col} AS DOUBLE) "
                    f"FROM {table_name} d "
                    f"LEFT JOIN encounters e ON d.encounter_id = e.encounter_id "
                    f"WHERE {group_where_sql} "
                    f"ORDER BY d.recorded_at ASC NULLS LAST LIMIT 1"
                )
                first_row = conn.execute(first_sql, group_params).fetchone()
                record["metric_first"] = first_row[0] if first_row else None

            if needs_last:
                last_sql = (
                    f"SELECT CAST(d.{value_col} AS DOUBLE) "
                    f"FROM {table_name} d "
                    f"LEFT JOIN encounters e ON d.encounter_id = e.encounter_id "
                    f"WHERE {group_where_sql} "
                    f"ORDER BY d.recorded_at DESC NULLS LAST LIMIT 1"
                )
                last_row = conn.execute(last_sql, group_params).fetchone()
                record["metric_last"] = last_row[0] if last_row else None

            groups.append(record)

        return {"groups": groups}


    # -----------------------------------------------------------------------
    # 8.5 — get_encounter_summary()
    # -----------------------------------------------------------------------

    def get_encounter_summary(self, conn, encounter_id: str) -> Optional[Dict[str, Any]]:
        """Return full encounter data with all associated clinical records and provenance.

        Returns ``None`` if the encounter does not exist.
        """
        # Fetch encounter row
        enc_row = conn.execute(
            "SELECT encounter_id, patient_id, encounter_date, encounter_type, "
            "primary_provider, primary_provider_type, facility, source_file, created_at "
            "FROM encounters WHERE encounter_id = ?",
            [encounter_id],
        ).fetchone()

        if enc_row is None:
            return None

        enc_cols = [
            "encounter_id", "patient_id", "encounter_date", "encounter_type",
            "primary_provider", "primary_provider_type", "facility",
            "source_file", "created_at",
        ]
        summary: Dict[str, Any] = dict(zip(enc_cols, enc_row))

        # Fetch all clinical data grouped by type
        clinical_data: Dict[str, List[Dict[str, Any]]] = {}
        for dtype, (table_name, _name_col) in _TABLE_MAP.items():
            rows = conn.execute(
                f"SELECT d.*, dp.provenance_id, dp.source_file AS prov_source_file, "
                f"  dp.page_number, dp.provider_name AS prov_provider_name, "
                f"  dp.provider_type AS prov_provider_type, "
                f"  dp.extraction_confidence, dp.raw_snippet "
                f"FROM {table_name} d "
                f"LEFT JOIN data_provenance dp "
                f"  ON dp.data_record_id = d.id AND dp.data_table = ? "
                f"WHERE d.encounter_id = ?",
                [table_name, encounter_id],
            ).fetchall()
            col_names = [desc[0] for desc in conn.description]
            clinical_data[dtype] = [dict(zip(col_names, r)) for r in rows]

        summary["clinical_data"] = clinical_data
        return summary
