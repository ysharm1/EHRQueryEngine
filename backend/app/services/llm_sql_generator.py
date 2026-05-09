"""
LLM-powered SQL Generator for DuckDB

Given a natural language query and the schema of all available DuckDB tables,
uses GPT to generate accurate SQL. Handles misspellings, scattered data across
multiple tables, and complex JOINs automatically.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a SQL expert. Given a user's natural language query and the schema of available DuckDB tables, generate a single SELECT query that answers their question.

Rules:
1. Use DuckDB SQL syntax.
2. Always return a single SELECT statement — no DDL, no INSERT, no UPDATE, no DELETE.
3. Use JOINs when data is spread across multiple tables (join on shared ID columns like subject_id, patient_id).
4. Handle common medical abbreviations and misspellings gracefully.
5. For diagnosis filtering, use ILIKE with wildcards for fuzzy matching.
6. For gender/sex filtering, handle variants: 'F'/'M'/'Female'/'Male'/'f'/'m'.
7. Limit results to 5000 rows max.
8. If you cannot answer the query from the available tables, return: SELECT 'NO_MATCH' AS error, 'explanation here' AS reason
9. Return ONLY the SQL query, no explanation, no markdown, no code fences.

Common medical knowledge:
- Diabetes: ICD-10 codes E10.x, E11.x; ICD-9 codes 250.x; keywords: diabetes, diabetic, DM
- Hypertension: ICD-10 I10; ICD-9 401.x; keywords: hypertension, HTN, high blood pressure
- Heart failure: ICD-10 I50.x; keywords: heart failure, CHF, HF
- COPD: ICD-10 J44.x; keywords: COPD, chronic obstructive
- Parkinson's: ICD-10 G20; keywords: parkinson, PD
"""


def _get_table_schemas(conn) -> Dict[str, List[Dict[str, str]]]:
    """Get schema info for all DuckDB tables with sample values."""
    schemas = {}
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        for (tname,) in tables:
            try:
                cols = conn.execute(f"DESCRIBE \"{tname}\"").fetchall()
                row_count = conn.execute(f"SELECT COUNT(*) FROM \"{tname}\"").fetchone()[0]
                if row_count == 0:
                    continue  # Skip empty tables
                col_info = []
                for col in cols:
                    col_info.append({
                        "name": col[0],
                        "type": col[1],
                    })
                # Get sample values for first few columns to help LLM understand data
                sample_cols = [c["name"] for c in col_info[:8]]
                quoted_cols = ", ".join('"' + c + '"' for c in sample_cols)
                sample_sql = f'SELECT {quoted_cols} FROM "{tname}" LIMIT 3'
                try:
                    sample_rows = conn.execute(sample_sql).fetchall()
                    samples = [dict(zip(sample_cols, row)) for row in sample_rows]
                except Exception:
                    samples = []

                schemas[tname] = {
                    "columns": col_info,
                    "row_count": row_count,
                    "sample_data": samples,
                }
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Failed to get table schemas: {e}")
    return schemas


def generate_sql(conn, query_text: str) -> Optional[Dict[str, Any]]:
    """
    Use LLM to generate SQL from natural language query.

    Returns dict with:
      - sql: the generated SQL
      - error: error message if generation failed
    """
    if not settings.openai_api_key:
        return {"sql": None, "error": "No OpenAI API key configured"}

    schemas = _get_table_schemas(conn)
    if not schemas:
        return {"sql": None, "error": "No tables with data found in database"}

    # Build schema description for the LLM
    schema_desc = "Available tables:\n\n"
    for tname, info in schemas.items():
        schema_desc += f"Table: {tname} ({info['row_count']} rows)\n"
        schema_desc += "Columns:\n"
        for col in info["columns"]:
            schema_desc += f"  - {col['name']} ({col['type']})\n"
        if info.get("sample_data"):
            schema_desc += f"Sample data: {json.dumps(info['sample_data'][:2], default=str)}\n"
        schema_desc += "\n"

    user_message = f"""Query: {query_text}

{schema_desc}

Generate a DuckDB SQL query that answers the user's question. Return ONLY the SQL."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=1000,
        )

        sql = response.choices[0].message.content.strip()

        # Clean up: remove markdown code fences if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        sql = sql.strip().rstrip(";")

        # Safety check: only allow SELECT
        sql_upper = sql.upper().strip()
        if not sql_upper.startswith("SELECT"):
            return {"sql": None, "error": f"LLM generated non-SELECT statement"}

        return {"sql": sql, "error": None}

    except Exception as e:
        logger.error(f"LLM SQL generation failed: {e}")
        return {"sql": None, "error": str(e)}


def execute_generated_sql(conn, sql: str) -> Dict[str, Any]:
    """
    Execute LLM-generated SQL and return results.

    Returns dict with:
      - rows: list of dicts
      - columns: list of column names
      - row_count: number of rows
      - error: error message if execution failed
    """
    try:
        result = conn.execute(sql)
        columns = [d[0] for d in result.description] if result.description else []
        rows = result.fetchall()
        row_dicts = [dict(zip(columns, row)) for row in rows]

        # Check for NO_MATCH sentinel
        if row_dicts and "error" in row_dicts[0] and row_dicts[0].get("error") == "NO_MATCH":
            return {
                "rows": [],
                "columns": [],
                "row_count": 0,
                "error": row_dicts[0].get("reason", "Query cannot be answered from available data"),
            }

        return {
            "rows": row_dicts,
            "columns": columns,
            "row_count": len(row_dicts),
            "error": None,
        }
    except Exception as e:
        logger.error(f"SQL execution failed: {e}\nSQL: {sql}")
        return {
            "rows": [],
            "columns": [],
            "row_count": 0,
            "error": f"SQL execution failed: {str(e)}",
        }
