"""DuckDB schema for clinical data extraction tables."""
import logging

logger = logging.getLogger(__name__)

EXTRACTION_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id VARCHAR PRIMARY KEY,
    mrn VARCHAR,
    date_of_birth DATE,
    sex VARCHAR,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vital_signs (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    vital_name VARCHAR NOT NULL,
    value DOUBLE NOT NULL,
    unit VARCHAR,
    recorded_at TIMESTAMP,
    encounter_date DATE,
    source_file VARCHAR,
    context VARCHAR
);

CREATE TABLE IF NOT EXISTS lab_results (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    test_name VARCHAR NOT NULL,
    value VARCHAR,
    unit VARCHAR,
    reference_range VARCHAR,
    flag VARCHAR,
    recorded_at TIMESTAMP,
    source_file VARCHAR
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    icd_code VARCHAR,
    diagnosis_type VARCHAR,
    encounter_date DATE,
    source_file VARCHAR
);

CREATE TABLE IF NOT EXISTS procedures_extracted (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    cpt_code VARCHAR,
    procedure_date DATE,
    provider VARCHAR,
    source_file VARCHAR
);

CREATE TABLE IF NOT EXISTS medications (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    drug_name VARCHAR NOT NULL,
    dose VARCHAR,
    route VARCHAR,
    frequency VARCHAR,
    start_date DATE,
    end_date DATE,
    source_file VARCHAR
);

CREATE TABLE IF NOT EXISTS clinical_notes (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    note_type VARCHAR,
    content TEXT,
    author VARCHAR,
    recorded_at TIMESTAMP,
    source_file VARCHAR
);

CREATE TABLE IF NOT EXISTS imaging_reports (
    id VARCHAR PRIMARY KEY,
    patient_id VARCHAR NOT NULL,
    modality VARCHAR,
    body_part VARCHAR,
    findings TEXT,
    impression TEXT,
    report_date DATE,
    source_file VARCHAR
);

CREATE TABLE IF NOT EXISTS extraction_jobs (
    job_id VARCHAR PRIMARY KEY,
    file_path VARCHAR,
    file_name VARCHAR,
    file_hash VARCHAR,
    status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT now(),
    completed_at TIMESTAMP,
    patient_id VARCHAR,
    records_extracted INTEGER DEFAULT 0,
    confidence DOUBLE,
    error_message VARCHAR,
    raw_text TEXT,
    retry_count INTEGER DEFAULT 0
);
"""


def init_extraction_tables(conn) -> None:
    """Create all extraction tables in DuckDB if they don't exist."""
    try:
        for statement in EXTRACTION_TABLES_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
        logger.info("Extraction tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize extraction tables: {e}")
        raise
