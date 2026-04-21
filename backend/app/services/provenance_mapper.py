"""Provenance Mapper — tracks the lineage of every extracted data point.

Records which PDF, page, provider, and extraction job produced each
clinical data record, enabling full audit trail and source verification.

Implements Requirements 4.1, 4.2, 4.4, 4.5, 4.7
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ProvenanceMapper:
    """Maps clinical data records to their extraction provenance."""

    def record_provenance(
        self,
        conn,
        data_record_id: str,
        data_table: str,
        source_file: str,
        page_number: Optional[int] = None,
        provider_name: Optional[str] = None,
        provider_type: Optional[str] = None,
        extraction_confidence: float = 0.0,
        extraction_job_id: str = "",
        raw_snippet: Optional[str] = None,
    ) -> str:
        """Insert a provenance record and return the generated provenance_id.

        Parameters
        ----------
        conn : duckdb.DuckDBPyConnection
            Active DuckDB connection.
        data_record_id : str
            The ``id`` column value of the clinical data row.
        data_table : str
            Table name the data row lives in (e.g. ``"vital_signs"``).
        source_file : str
            Path/name of the source PDF.
        page_number : int | None
            1-indexed page in the PDF, or None when unknown.
        provider_name : str | None
            Name of the authoring provider, if identifiable.
        provider_type : str | None
            Controlled-vocabulary provider type, or None.
        extraction_confidence : float
            AI extraction confidence score (0.0–1.0).
        extraction_job_id : str
            ID of the extraction job that produced this data.
        raw_snippet : str | None
            Raw text snippet from the source for context.

        Returns
        -------
        str
            The generated ``provenance_id``.
        """
        provenance_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO data_provenance
               (provenance_id, data_record_id, data_table, source_file,
                page_number, provider_name, provider_type,
                extraction_confidence, extraction_job_id, raw_snippet)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                provenance_id,
                data_record_id,
                data_table,
                source_file,
                page_number,
                provider_name,
                provider_type,
                extraction_confidence,
                extraction_job_id,
                raw_snippet,
            ],
        )
        logger.debug(
            "Recorded provenance %s for %s.%s",
            provenance_id,
            data_table,
            data_record_id,
        )
        return provenance_id

    def get_provenance(self, conn, provenance_id: str) -> Optional[Dict]:
        """Retrieve full provenance detail by provenance_id.

        Returns a dict with all provenance fields, or ``None`` if not found.
        """
        row = conn.execute(
            """SELECT provenance_id, data_record_id, data_table, source_file,
                      page_number, provider_name, provider_type,
                      extraction_confidence, extraction_job_id, raw_snippet,
                      created_at
               FROM data_provenance
               WHERE provenance_id = ?""",
            [provenance_id],
        ).fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def get_provenance_by_record(
        self, conn, data_record_id: str, data_table: str
    ) -> List[Dict]:
        """Get all provenance entries for a clinical data record.

        Parameters
        ----------
        data_record_id : str
            The ``id`` of the clinical data row.
        data_table : str
            The table the data row belongs to.

        Returns
        -------
        list[dict]
            List of provenance dicts (may be empty).
        """
        rows = conn.execute(
            """SELECT provenance_id, data_record_id, data_table, source_file,
                      page_number, provider_name, provider_type,
                      extraction_confidence, extraction_job_id, raw_snippet,
                      created_at
               FROM data_provenance
               WHERE data_record_id = ? AND data_table = ?""",
            [data_record_id, data_table],
        ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a DuckDB result row to a provenance dict."""
        return {
            "provenance_id": row[0],
            "data_record_id": row[1],
            "data_table": row[2],
            "source_file": row[3],
            "page_number": row[4],
            "provider_name": row[5],
            "provider_type": row[6],
            "extraction_confidence": row[7],
            "extraction_job_id": row[8],
            "raw_snippet": row[9],
            "created_at": row[10],
        }
