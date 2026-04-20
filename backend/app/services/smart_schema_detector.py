"""
Smart Schema Detector

Automatically detects column types, nullable flags, and likely semantic categories
from a pandas DataFrame so uploaded files can be queried immediately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import pandas as pd


# Heuristic patterns for common biomedical field names.
# Column names are tokenised (split on non-alphanumeric / underscores) before
# matching so that compound names like "subject_id" or "patient-dob" work.
_TOKEN_SEP = re.compile(r"[\W_]+")

def _tokens(col_name: str) -> str:
    """Return a space-joined lowercase token string for easy regex matching."""
    return " " + " ".join(_TOKEN_SEP.split(col_name.lower())) + " "

_DATE_PATTERNS = re.compile(
    r" (date|dob|birth|admission|discharge|enrolled|visit|start|end|time|timestamp) ",
)
_ID_PATTERNS = re.compile(r" (id|identifier|mrn|subject|patient|code|key) ")
_DIAGNOSIS_PATTERNS = re.compile(r" (diagnosis|icd|snomed|condition|disease) ")
_NUMERIC_PATTERNS = re.compile(r" (age|score|count|value|amount|weight|height|bmi|dose) ")


@dataclass
class ColumnSchema:
    name: str
    data_type: str          # pandas dtype string
    nullable: bool
    unique_count: int
    sample_values: List[str]
    semantic_type: str      # id | date | numeric | categorical | text | unknown


@dataclass
class DetectedSchema:
    columns: List[ColumnSchema] = field(default_factory=list)
    row_count: int = 0
    inferred_subject_id_column: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "row_count": self.row_count,
            "inferred_subject_id_column": self.inferred_subject_id_column,
            "columns": [asdict(c) for c in self.columns],
        }


class SmartSchemaDetector:
    """
    Infers schema and semantic column types from a pandas DataFrame.

    Usage:
        detector = SmartSchemaDetector()
        schema = detector.detect_schema(df)
        print(schema.to_dict())
    """

    def detect_schema(self, df: pd.DataFrame) -> DetectedSchema:
        """
        Analyse the DataFrame and return a DetectedSchema.

        Args:
            df: pandas DataFrame to analyse

        Returns:
            DetectedSchema with per-column metadata
        """
        schema = DetectedSchema(row_count=len(df))
        best_id_col: Optional[str] = None
        best_id_score = -1

        for col in df.columns:
            series = df[col]
            dtype_str = str(series.dtype)
            nullable = bool(series.isna().any())
            unique_count = int(series.nunique(dropna=True))

            # Sample up to 3 non-null values for display
            samples = (
                series.dropna()
                .astype(str)
                .unique()[:3]
                .tolist()
            )

            semantic = self._infer_semantic_type(col, series, dtype_str, unique_count, len(df))

            col_schema = ColumnSchema(
                name=col,
                data_type=dtype_str,
                nullable=nullable,
                unique_count=unique_count,
                sample_values=samples,
                semantic_type=semantic,
            )
            schema.columns.append(col_schema)

            # Track best candidate for the subject/patient ID column
            if semantic == "id":
                score = unique_count  # prefer the column with most unique values
                if score > best_id_score:
                    best_id_score = score
                    best_id_col = col

        schema.inferred_subject_id_column = best_id_col
        return schema

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _infer_semantic_type(
        self,
        col: str,
        series: pd.Series,
        dtype_str: str,
        unique_count: int,
        total_rows: int,
    ) -> str:
        """Heuristically classify a column into a semantic type."""
        tok = _tokens(col)

        # 1. Try to parse as datetime
        if "datetime" in dtype_str or "date" in dtype_str:
            return "date"
        if _DATE_PATTERNS.search(tok):
            try:
                pd.to_datetime(series.dropna().astype(str).iloc[:10], format='mixed')
                return "date"
            except Exception:
                pass

        # 2. Numeric types
        if "int" in dtype_str or "float" in dtype_str:
            if _ID_PATTERNS.search(tok):
                return "id"
            return "numeric"

        # 3. Object / string columns
        if _ID_PATTERNS.search(tok):
            return "id"

        if _DIAGNOSIS_PATTERNS.search(tok):
            return "categorical"

        if _NUMERIC_PATTERNS.search(tok):
            # Try to coerce — might be stored as string
            try:
                pd.to_numeric(series.dropna().astype(str).iloc[:20])
                return "numeric"
            except Exception:
                pass

        # 4. High cardinality string → free text; low cardinality → categorical
        if total_rows > 0:
            cardinality_ratio = unique_count / total_rows
            if cardinality_ratio < 0.05 or unique_count <= 20:
                return "categorical"
            if cardinality_ratio > 0.8:
                return "text"

        return "unknown"
