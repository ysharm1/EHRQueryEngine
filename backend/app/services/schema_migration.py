"""Schema migration for Clinical Query Intelligence.

Creates new tables (encounters, data_provenance) and adds columns
to existing clinical data tables. All statements are idempotent —
safe to run on every deploy.

Implements Requirements 7.1, 7.2, 7.4, 7.5, 1.1, 1.2, 4.1, 4.6
"""
import logging

logger = logging.getLogger(__name__)

# --- Sub-task 1.1: New tables ------------------------------------------------

CREATE_ENCOUNTERS_TABLE = """
CREATE TABLE IF NOT EXISTS encounters (
    encounter_id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    encounter_date DATE,
    encounter_type VARCHAR,
    primary_provider VARCHAR,
    primary_provider_type VARCHAR,
    facility VARCHAR,
    source_file VARCHAR,
    created_at TIMESTAMP DEFAULT now(),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);
"""

CREATE_DATA_PROVENANCE_TABLE = """
CREATE TABLE IF NOT EXISTS data_provenance (
    provenance_id VARCHAR PRIMARY KEY,
    data_record_id VARCHAR NOT NULL,
    data_table VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    page_number INTEGER,
    provider_name VARCHAR,
    provider_type VARCHAR,
    extraction_confidence DOUBLE,
    extraction_job_id VARCHAR,
    raw_snippet TEXT,
    created_at TIMESTAMP DEFAULT now()
);
"""

# --- Sub-task 1.2: ALTER TABLE for existing clinical data tables --------------

CLINICAL_TABLES = [
    "vital_signs",
    "lab_results",
    "diagnoses",
    "procedures_extracted",
    "medications",
    "clinical_notes",
    "imaging_reports",
]

NEW_COLUMNS = [
    ("encounter_id", "VARCHAR"),
    ("provider_type", "VARCHAR"),
    ("provenance_id", "VARCHAR"),
]


def _build_alter_statements() -> list[str]:
    """Build ALTER TABLE ADD COLUMN IF NOT EXISTS statements."""
    stmts: list[str] = []
    for table in CLINICAL_TABLES:
        for col_name, col_type in NEW_COLUMNS:
            stmts.append(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
            )
    return stmts


# --- Sub-task 1.3: Indexes ----------------------------------------------------

def _build_index_statements() -> list[str]:
    """Build CREATE INDEX IF NOT EXISTS statements."""
    stmts: list[str] = []

    # Indexes on each clinical data table for encounter_id and provider_type
    for table in CLINICAL_TABLES:
        short = table.replace("_extracted", "")  # procedures_extracted -> procedures
        stmts.append(
            f"CREATE INDEX IF NOT EXISTS idx_{short}_encounter "
            f"ON {table}(encounter_id);"
        )
        stmts.append(
            f"CREATE INDEX IF NOT EXISTS idx_{short}_provider_type "
            f"ON {table}(provider_type);"
        )

    # Indexes on the new encounters table
    stmts.append(
        "CREATE INDEX IF NOT EXISTS idx_encounters_patient "
        "ON encounters(patient_id);"
    )
    stmts.append(
        "CREATE INDEX IF NOT EXISTS idx_encounters_date "
        "ON encounters(encounter_date);"
    )

    # Composite index on data_provenance
    stmts.append(
        "CREATE INDEX IF NOT EXISTS idx_provenance_record "
        "ON data_provenance(data_record_id, data_table);"
    )

    return stmts


# --- Public entry point -------------------------------------------------------

def run_clinical_schema_migration(conn) -> None:
    """Run the full Clinical Query Intelligence schema migration.

    Idempotent — safe to call on every application startup.
    """
    try:
        # 1. Create new tables
        conn.execute(CREATE_ENCOUNTERS_TABLE)
        conn.execute(CREATE_DATA_PROVENANCE_TABLE)
        logger.info("Created encounters and data_provenance tables (if not exist)")

        # 2. Add columns to existing clinical data tables
        for stmt in _build_alter_statements():
            conn.execute(stmt)
        logger.info("Added encounter_id, provider_type, provenance_id columns to clinical tables")

        # 3. Create indexes
        for stmt in _build_index_statements():
            conn.execute(stmt)
        logger.info("Created indexes for clinical query performance")

        logger.info("Clinical schema migration completed successfully")
    except Exception as e:
        logger.error(f"Clinical schema migration failed: {e}")
        raise
