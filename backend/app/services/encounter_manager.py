"""Encounter Manager for Clinical Query Intelligence.

Creates and manages encounter/visit records, linking all clinical data
to a specific visit. Supports deduplication and resolution logic.

Implements Requirements 1.3, 1.4, 1.6
"""
import logging
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EncounterManager:
    """Manage encounter/visit records in DuckDB."""

    def find_or_create_encounter(
        self,
        conn,
        patient_id: str,
        encounter_date: Optional[str] = None,
        encounter_type: Optional[str] = None,
        source_file: str = "",
        encounter_id_hint: Optional[str] = None,
    ) -> str:
        """Find an existing encounter or create a new one.

        3-step resolution logic:
        (a) If encounter_id_hint provided and exists in DB, return it.
        (b) If encounter_date provided, deduplicate by (patient_id, date, type).
        (c) Create a new encounter.

        Returns the encounter_id.
        """
        # Step (a): Check explicit encounter_id hint
        if encounter_id_hint:
            existing = conn.execute(
                "SELECT encounter_id FROM encounters WHERE encounter_id = ?",
                [encounter_id_hint],
            ).fetchone()
            if existing:
                return existing[0]

        # Step (b): Deduplicate by (patient_id, encounter_date, encounter_type)
        if encounter_date:
            if encounter_type:
                match = conn.execute(
                    "SELECT encounter_id FROM encounters "
                    "WHERE patient_id = ? AND encounter_date = ? "
                    "AND encounter_type = ? LIMIT 1",
                    [patient_id, encounter_date, encounter_type],
                ).fetchone()
            else:
                match = conn.execute(
                    "SELECT encounter_id FROM encounters "
                    "WHERE patient_id = ? AND encounter_date = ? "
                    "AND encounter_type IS NULL LIMIT 1",
                    [patient_id, encounter_date],
                ).fetchone()
            if match:
                return match[0]

        # Step (c): Create new encounter
        new_id = encounter_id_hint or str(uuid.uuid4())
        conn.execute(
            "INSERT INTO encounters "
            "(encounter_id, patient_id, encounter_date, encounter_type, source_file) "
            "VALUES (?, ?, ?, ?, ?)",
            [new_id, patient_id, encounter_date, encounter_type, source_file],
        )
        logger.info("Created new encounter %s for patient %s", new_id, patient_id)
        return new_id

    def list_encounters(
        self,
        conn,
        patient_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict]:
        """List encounters for a patient within an optional date range.

        Returns encounter dicts ordered by encounter_date DESC.
        """
        where_clauses = ["patient_id = ?"]
        params: list = [patient_id]

        if date_from:
            where_clauses.append("encounter_date >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("encounter_date <= ?")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses)
        rows = conn.execute(
            f"SELECT encounter_id, patient_id, encounter_date, encounter_type, "
            f"primary_provider, primary_provider_type, facility, source_file, created_at "
            f"FROM encounters WHERE {where_sql} "
            f"ORDER BY encounter_date DESC",
            params,
        ).fetchall()

        columns = [
            "encounter_id", "patient_id", "encounter_date", "encounter_type",
            "primary_provider", "primary_provider_type", "facility",
            "source_file", "created_at",
        ]
        return [dict(zip(columns, row)) for row in rows]

    def get_encounter_summary(self, conn, encounter_id: str) -> Optional[Dict]:
        """Return encounter details with counts of associated clinical data.

        Returns None if the encounter does not exist.
        """
        row = conn.execute(
            "SELECT encounter_id, patient_id, encounter_date, encounter_type, "
            "primary_provider, primary_provider_type, facility, source_file, created_at "
            "FROM encounters WHERE encounter_id = ?",
            [encounter_id],
        ).fetchone()

        if not row:
            return None

        columns = [
            "encounter_id", "patient_id", "encounter_date", "encounter_type",
            "primary_provider", "primary_provider_type", "facility",
            "source_file", "created_at",
        ]
        summary = dict(zip(columns, row))

        # Count associated clinical data from each table
        clinical_tables = {
            "vitals": "vital_signs",
            "labs": "lab_results",
            "diagnoses": "diagnoses",
            "procedures": "procedures_extracted",
            "medications": "medications",
            "notes": "clinical_notes",
            "imaging": "imaging_reports",
        }

        counts = {}
        for key, table in clinical_tables.items():
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE encounter_id = ?",
                [encounter_id],
            ).fetchone()[0]
            counts[key] = count

        summary["data_counts"] = counts
        return summary
