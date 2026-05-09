"""
DuckDB Cohort Searcher

Searches uploaded/ingested DuckDB tables for cohort matches when the
SQLAlchemy subjects table is empty. Heuristically finds a patient-like
primary table and joins with diagnosis/demographics tables when available.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Column name candidates for different concepts
_ID_COLS = ("patient_id", "subject_id", "id", "mrn", "person_id")
_SEX_COLS = ("sex", "gender", "sex_at_birth", "patient_sex")
_DOB_COLS = ("date_of_birth", "dob", "birth_date", "anchor_age")
_DIAG_COLS = ("diagnosis", "icd_code", "icd10_code", "icd9_code", "diagnosis_code",
              "description", "long_title", "short_title", "condition")

# Map common diagnosis keywords/ICD codes to searchable terms
_DIAG_SEARCH_TERMS = {
    "diabetes": ["diabetes", "e11", "e10", "250"],
    "e11": ["diabetes", "e11"],
    "e10": ["diabetes", "e10"],
    "hypertension": ["hypertension", "i10", "401"],
    "i10": ["hypertension", "i10"],
    "heart failure": ["heart failure", "i50"],
    "parkinson": ["parkinson", "g20", "332"],
    "copd": ["chronic obstructive", "j44"],
    "sepsis": ["sepsis", "a41"],
    "kidney": ["kidney", "renal", "n18"],
    "anemia": ["anemia", "d64"],
    "pneumonia": ["pneumonia", "j18"],
    "cancer": ["neoplasm", "malignant", "cancer", "tumor"],
    "stroke": ["cerebrovascular", "stroke", "i63"],
}


def _first_matching_col(columns: List[str], candidates) -> Optional[str]:
    """Find the first column matching any candidate (case-insensitive)."""
    lower_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    # Partial match fallback
    for cand in candidates:
        for col_l, col_orig in lower_map.items():
            if cand in col_l:
                return col_orig
    return None


def _list_tables(conn) -> List[Tuple[str, List[str], int]]:
    """Return (table_name, columns, row_count) for all non-system DuckDB tables."""
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        out = []
        for (tname,) in tables:
            cols = conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                [tname]
            ).fetchall()
            col_names = [c[0] for c in cols]
            try:
                row_count = conn.execute(f"SELECT COUNT(*) FROM \"{tname}\"").fetchone()[0]
            except Exception:
                row_count = 0
            out.append((tname, col_names, row_count))
        return out
    except Exception as e:
        logger.warning(f"Could not list DuckDB tables: {e}")
        return []


def _find_patient_table(tables: List[Tuple[str, List[str], int]]) -> Optional[Tuple[str, Dict[str, str]]]:
    """Find the best patient-like table and its key columns.

    Prefers tables with actual data. Empty tables are deprioritized so that
    user uploads win over system-created empty tables.
    """
    best = None
    best_score = 0
    for tname, cols, row_count in tables:
        id_col = _first_matching_col(cols, _ID_COLS)
        if not id_col:
            continue
        # Skip empty tables entirely — they can't contain matches
        if row_count == 0:
            continue
        sex_col = _first_matching_col(cols, _SEX_COLS)
        dob_col = _first_matching_col(cols, _DOB_COLS)
        score = 1 + (2 if sex_col else 0) + (1 if dob_col else 0)
        # Bonus for obvious patient table names
        tl = tname.lower()
        if "patient" in tl or "subject" in tl or "demograph" in tl:
            score += 5
        # Strong bonus for tables with lots of rows (user's actual data)
        if row_count > 0:
            score += min(5, row_count // 1000 + 1)
        if score > best_score:
            best_score = score
            best = (tname, {"id": id_col, "sex": sex_col, "dob": dob_col})
    return best


def _find_diagnosis_table(
    tables: List[Tuple[str, List[str], int]],
    patient_id_col: str,
) -> Optional[Tuple[str, Dict[str, str]]]:
    """Find a diagnosis-like table that can be joined on patient_id.

    Prefers non-empty tables with obvious diagnosis names.
    """
    candidates = []
    for tname, cols, row_count in tables:
        if row_count == 0:
            continue
        id_col = _first_matching_col(cols, _ID_COLS)
        diag_col = _first_matching_col(cols, _DIAG_COLS)
        if not (id_col and diag_col):
            continue
        tl = tname.lower()
        score = 1 + min(5, row_count // 1000 + 1)
        if "diag" in tl or "condition" in tl or "icd" in tl:
            score += 5
        candidates.append((score, tname, {"id": id_col, "diag": diag_col}))

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return (candidates[0][1], candidates[0][2])


def _build_sex_where(sex_col: str, value: str) -> Tuple[str, List[Any]]:
    """Build WHERE clause for sex filter. Matches F/Female/f/female variants."""
    v = value.strip().lower()
    if v in ("female", "f"):
        return f"LOWER(CAST(p.\"{sex_col}\" AS VARCHAR)) IN (?, ?, ?)", ["f", "female", "woman"]
    if v in ("male", "m"):
        return f"LOWER(CAST(p.\"{sex_col}\" AS VARCHAR)) IN (?, ?, ?)", ["m", "male", "man"]
    return f"LOWER(CAST(p.\"{sex_col}\" AS VARCHAR)) = ?", [v]


def _expand_diagnosis_terms(value: str) -> List[str]:
    """Expand a diagnosis filter value into searchable terms."""
    v = value.strip().lower()
    if not v:
        return []
    terms = [v]
    for key, expansions in _DIAG_SEARCH_TERMS.items():
        if key in v or v in key:
            terms.extend(expansions)
    # Dedupe while preserving order
    seen = set()
    result = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def search_duckdb_cohort(
    conn,
    criteria: List[Dict[str, Any]],
    limit: int = 5000,
) -> Dict[str, Any]:
    """
    Search uploaded DuckDB tables for subjects matching the cohort criteria.

    Returns a dict with:
      - subjects: list of matching rows (as dicts)
      - table_name: the primary patient table found
      - sql: the SQL executed (for debugging)
      - message: explanation if no match
    """
    tables = _list_tables(conn)
    if not tables:
        return {"subjects": [], "table_name": None, "sql": "", "message": "No tables in DuckDB"}

    patient_info = _find_patient_table(tables)
    if not patient_info:
        return {
            "subjects": [],
            "table_name": None,
            "sql": "",
            "message": "No patient-like table found (need a table with patient_id/subject_id)",
        }

    patient_table, p_cols = patient_info
    id_col = p_cols["id"]
    sex_col = p_cols["sex"]

    # Separate criteria by type
    where_clauses: List[str] = []
    params: List[Any] = []
    diag_filters: List[str] = []

    for c in criteria:
        ftype = (c.get("filter_type") or "").lower()
        field = (c.get("field") or "").lower()
        value = str(c.get("value") or "").strip()

        if ftype == "demographics" and field in ("sex", "gender") and sex_col and value:
            clause, p = _build_sex_where(sex_col, value)
            where_clauses.append(clause)
            params.extend(p)
        elif ftype == "diagnosis" and value:
            diag_filters.append(value)

    # Build the JOIN if there are diagnosis filters
    diag_table = None
    diag_cols = None
    if diag_filters:
        d_info = _find_diagnosis_table(tables, id_col)
        if d_info:
            diag_table, diag_cols = d_info

    # Build SQL
    if diag_table and diag_cols:
        sql_parts = [
            f"SELECT DISTINCT p.* FROM \"{patient_table}\" p",
            f"INNER JOIN \"{diag_table}\" d ON CAST(p.\"{id_col}\" AS VARCHAR) = CAST(d.\"{diag_cols['id']}\" AS VARCHAR)",
        ]
        # OR together diagnosis terms
        all_diag_terms = []
        for df in diag_filters:
            all_diag_terms.extend(_expand_diagnosis_terms(df))
        if all_diag_terms:
            diag_ors = []
            for term in all_diag_terms:
                diag_ors.append(f"LOWER(CAST(d.\"{diag_cols['diag']}\" AS VARCHAR)) LIKE ?")
                params.append(f"%{term}%")
            where_clauses.append("(" + " OR ".join(diag_ors) + ")")
        sql_parts.append("WHERE " + " AND ".join(where_clauses) if where_clauses else "")
    else:
        sql_parts = [f"SELECT * FROM \"{patient_table}\" p"]
        if where_clauses:
            sql_parts.append("WHERE " + " AND ".join(where_clauses))
        if diag_filters and not diag_table:
            # No diagnosis table found but diagnosis was requested
            return {
                "subjects": [],
                "table_name": patient_table,
                "sql": " ".join(sql_parts),
                "message": (
                    f"Found patient table '{patient_table}' but no diagnosis table to filter by "
                    f"'{', '.join(diag_filters)}'. Upload a diagnoses/icd table with a "
                    f"{id_col} column to enable diagnosis filters."
                ),
            }

    sql_parts.append(f"LIMIT {limit}")
    sql = " ".join(p for p in sql_parts if p)

    try:
        rows = conn.execute(sql, params).fetchall()
        col_names = [d[0] for d in conn.description] if conn.description else []
        subjects = [dict(zip(col_names, r)) for r in rows]
        return {
            "subjects": subjects,
            "table_name": patient_table,
            "sql": sql,
            "message": f"Found {len(subjects)} matching subjects in '{patient_table}'",
        }
    except Exception as e:
        logger.error(f"DuckDB cohort search failed: {e}")
        return {
            "subjects": [],
            "table_name": patient_table,
            "sql": sql,
            "message": f"Query failed: {e}",
        }
