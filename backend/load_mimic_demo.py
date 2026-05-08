"""
MIMIC-IV Demo Data Loader

Downloads and loads the MIMIC-IV Clinical Database Demo (v2.2) into the
EHR Query Engine's DuckDB warehouse and SQLite metadata store.

Maps MIMIC-IV tables to the app's canonical schema:
  - patients.csv → patients table (DuckDB) + subjects table (SQLite)
  - admissions.csv → encounters table (DuckDB)
  - diagnoses_icd.csv + d_icd_diagnoses.csv → diagnoses table (DuckDB)
  - procedures_icd.csv + d_icd_procedures.csv → procedures_extracted (DuckDB) + procedures (SQLite)
  - labevents.csv + d_labitems.csv → lab_results table (DuckDB) + observations (SQLite)
  - prescriptions.csv → medications table (DuckDB)
  - chartevents.csv + d_items.csv → vital_signs table (DuckDB)

Data source: https://physionet.org/content/mimic-iv-demo/2.2/
License: Open access (PhysioNet Credentialed Health Data License for demo)

Citation:
  Johnson, A., et al. "MIMIC-IV Clinical Database Demo" (version 2.2).
  PhysioNet (2023). https://doi.org/10.13026/dp1f-ex47
"""

import os
import sys
import gzip
import uuid
import logging
from pathlib import Path
from datetime import date, datetime

import pandas as pd
import duckdb

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.database import get_duckdb_connection, engine, SessionLocal, Base
from app.init_db import init_database, create_sample_data, migrate_passwords
from app.models.canonical import Subject, Procedure, Observation

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MIMIC_DIR = "/tmp/mimic-iv-demo/mimic-iv-clinical-database-demo-2.2"


def read_mimic_csv(subdir: str, filename: str) -> pd.DataFrame:
    """Read a gzipped MIMIC CSV file."""
    path = os.path.join(MIMIC_DIR, subdir, f"{filename}.csv.gz")
    if not os.path.exists(path):
        logger.warning(f"File not found: {path}")
        return pd.DataFrame()
    logger.info(f"Reading {subdir}/{filename}.csv.gz ...")
    return pd.read_csv(path, compression="gzip", low_memory=False)


def load_patients(conn, db_session):
    """Load patients into DuckDB patients table and SQLite subjects table."""
    df = read_mimic_csv("hosp", "patients")
    if df.empty:
        return

    logger.info(f"  {len(df)} patients found")

    # Map to DuckDB patients table
    for _, row in df.iterrows():
        patient_id = str(row["subject_id"])
        sex = "Male" if row["gender"] == "M" else "Female"
        # anchor_year gives us a rough birth year
        birth_year = int(row["anchor_year"]) - int(row["anchor_age"])
        dob = f"{birth_year}-01-01"

        conn.execute("""
            INSERT OR REPLACE INTO patients (patient_id, mrn, date_of_birth, sex)
            VALUES (?, ?, ?, ?)
        """, [patient_id, f"MIMIC-{patient_id}", dob, sex])

    # Also load into SQLite subjects table for the NL query pipeline
    from app.models.canonical import Sex
    for _, row in df.iterrows():
        subject_id = str(row["subject_id"])
        sex_enum = Sex.MALE if row["gender"] == "M" else Sex.FEMALE
        birth_year = int(row["anchor_year"]) - int(row["anchor_age"])

        existing = db_session.query(Subject).filter(Subject.subject_id == subject_id).first()
        if not existing:
            subject = Subject(
                subject_id=subject_id,
                sex=sex_enum,
                date_of_birth=date(birth_year, 1, 1),
                enrollment_date=date(int(row["anchor_year"]), 1, 1),
                diagnosis_codes=[],
            )
            db_session.add(subject)

    db_session.commit()
    logger.info(f"  ✓ Loaded {len(df)} patients")


def load_admissions_as_encounters(conn):
    """Load admissions as encounters in DuckDB."""
    df = read_mimic_csv("hosp", "admissions")
    if df.empty:
        return

    logger.info(f"  {len(df)} admissions found")

    for _, row in df.iterrows():
        encounter_id = str(row["hadm_id"])
        patient_id = str(row["subject_id"])
        admit_time = str(row["admittime"])[:10] if pd.notna(row["admittime"]) else None
        encounter_type = row["admission_type"] if pd.notna(row.get("admission_type")) else "Unknown"
        facility = row["admission_location"] if pd.notna(row.get("admission_location")) else None

        conn.execute("""
            INSERT OR REPLACE INTO encounters 
            (encounter_id, patient_id, encounter_date, encounter_type, facility, source_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [encounter_id, patient_id, admit_time, encounter_type, facility, "mimic-iv-demo"])

    logger.info(f"  ✓ Loaded {len(df)} encounters")


def load_diagnoses(conn, db_session):
    """Load diagnoses with ICD code descriptions."""
    diag_df = read_mimic_csv("hosp", "diagnoses_icd")
    codes_df = read_mimic_csv("hosp", "d_icd_diagnoses")
    if diag_df.empty:
        return

    # Build code → description lookup
    code_lookup = {}
    if not codes_df.empty:
        for _, row in codes_df.iterrows():
            code_lookup[str(row["icd_code"])] = row["long_title"]

    logger.info(f"  {len(diag_df)} diagnosis records found")

    # Group diagnoses by patient for SQLite subject update
    patient_diagnoses = {}

    for _, row in diag_df.iterrows():
        diag_id = str(uuid.uuid4())
        patient_id = str(row["subject_id"])
        icd_code = str(row["icd_code"])
        description = code_lookup.get(icd_code, f"ICD-{row['icd_version']} {icd_code}")
        encounter_id = str(row["hadm_id"]) if pd.notna(row.get("hadm_id")) else None

        conn.execute("""
            INSERT INTO diagnoses (id, patient_id, description, icd_code, diagnosis_type, source_file, encounter_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [diag_id, patient_id, description, icd_code, f"ICD-{row['icd_version']}", "mimic-iv-demo", encounter_id])

        # Collect diagnosis descriptions per patient for SQLite
        if patient_id not in patient_diagnoses:
            patient_diagnoses[patient_id] = set()
        patient_diagnoses[patient_id].add(description.lower())

    # Update SQLite subjects with diagnosis codes (for NL query cohort filtering)
    for patient_id, diag_set in patient_diagnoses.items():
        subject = db_session.query(Subject).filter(Subject.subject_id == patient_id).first()
        if subject:
            subject.diagnosis_codes = list(diag_set)
    db_session.commit()

    logger.info(f"  ✓ Loaded {len(diag_df)} diagnoses")


def load_procedures(conn, db_session):
    """Load procedures with ICD code descriptions."""
    proc_df = read_mimic_csv("hosp", "procedures_icd")
    codes_df = read_mimic_csv("hosp", "d_icd_procedures")
    if proc_df.empty:
        return

    # Build code → description lookup
    code_lookup = {}
    if not codes_df.empty:
        for _, row in codes_df.iterrows():
            code_lookup[str(row["icd_code"])] = row["long_title"]

    logger.info(f"  {len(proc_df)} procedure records found")

    for _, row in proc_df.iterrows():
        proc_id = str(uuid.uuid4())
        patient_id = str(row["subject_id"])
        icd_code = str(row["icd_code"])
        description = code_lookup.get(icd_code, f"ICD-{row['icd_version']} {icd_code}")
        proc_date = str(row["chartdate"]) if pd.notna(row.get("chartdate")) else None
        encounter_id = str(row["hadm_id"]) if pd.notna(row.get("hadm_id")) else None

        conn.execute("""
            INSERT INTO procedures_extracted 
            (id, patient_id, description, cpt_code, procedure_date, source_file, encounter_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [proc_id, patient_id, description, icd_code, proc_date, "mimic-iv-demo", encounter_id])

        # Also add to SQLite procedures table for NL query pipeline
        if proc_date:
            existing = db_session.query(Procedure).filter(
                Procedure.subject_id == patient_id,
                Procedure.procedure_code == icd_code
            ).first()
            if not existing:
                procedure = Procedure(
                    procedure_id=proc_id,
                    subject_id=patient_id,
                    procedure_code=icd_code,
                    procedure_name=description,
                    procedure_date=datetime.strptime(proc_date, "%Y-%m-%d").date(),
                )
                db_session.add(procedure)

    db_session.commit()
    logger.info(f"  ✓ Loaded {len(proc_df)} procedures")


def load_lab_results(conn, db_session):
    """Load lab events with item descriptions."""
    lab_df = read_mimic_csv("hosp", "labevents")
    items_df = read_mimic_csv("hosp", "d_labitems")
    if lab_df.empty:
        return

    # Build itemid → label lookup
    item_lookup = {}
    if not items_df.empty:
        for _, row in items_df.iterrows():
            item_lookup[int(row["itemid"])] = row["label"]

    logger.info(f"  {len(lab_df)} lab results found (loading...)")

    count = 0
    batch_size = 1000
    obs_batch = []

    for _, row in lab_df.iterrows():
        lab_id = str(uuid.uuid4())
        patient_id = str(row["subject_id"])
        test_name = item_lookup.get(int(row["itemid"]), f"Lab Item {row['itemid']}")
        value = str(row["value"]) if pd.notna(row.get("value")) else None
        unit = str(row["valueuom"]) if pd.notna(row.get("valueuom")) else None
        ref_lower = str(row["ref_range_lower"]) if pd.notna(row.get("ref_range_lower")) else None
        ref_upper = str(row["ref_range_upper"]) if pd.notna(row.get("ref_range_upper")) else None
        ref_range = f"{ref_lower}-{ref_upper}" if ref_lower and ref_upper else None
        flag = str(row["flag"]) if pd.notna(row.get("flag")) else None
        charttime = str(row["charttime"]) if pd.notna(row.get("charttime")) else None

        conn.execute("""
            INSERT INTO lab_results 
            (id, patient_id, test_name, value, unit, reference_range, flag, recorded_at, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [lab_id, patient_id, test_name, value, unit, ref_range, flag, charttime, "mimic-iv-demo"])

        # Add to SQLite observations (sample — every 10th to keep it manageable)
        count += 1
        if count % 10 == 0 and pd.notna(row.get("valuenum")) and charttime:
            obs = Observation(
                observation_id=lab_id,
                subject_id=patient_id,
                observation_type=str(row["itemid"]),
                observation_value=str(row["valuenum"]),
                observation_unit=unit or "",
                observation_date=datetime.strptime(charttime[:19], "%Y-%m-%d %H:%M:%S") if len(charttime) >= 19 else datetime.strptime(charttime[:10], "%Y-%m-%d"),
            )
            obs_batch.append(obs)

        if len(obs_batch) >= batch_size:
            db_session.bulk_save_objects(obs_batch)
            db_session.commit()
            obs_batch = []

    if obs_batch:
        db_session.bulk_save_objects(obs_batch)
        db_session.commit()

    logger.info(f"  ✓ Loaded {count} lab results")


def load_medications(conn):
    """Load prescriptions as medications."""
    df = read_mimic_csv("hosp", "prescriptions")
    if df.empty:
        return

    logger.info(f"  {len(df)} prescription records found")

    for _, row in df.iterrows():
        med_id = str(uuid.uuid4())
        patient_id = str(row["subject_id"])
        drug_name = str(row["drug"]) if pd.notna(row.get("drug")) else "Unknown"
        dose = str(row["dose_val_rx"]) if pd.notna(row.get("dose_val_rx")) else None
        route = str(row["route"]) if pd.notna(row.get("route")) else None
        frequency = str(row["doses_per_24_hrs"]) if pd.notna(row.get("doses_per_24_hrs")) else None
        start_date = str(row["starttime"])[:10] if pd.notna(row.get("starttime")) else None
        stop_date = str(row["stoptime"])[:10] if pd.notna(row.get("stoptime")) else None

        conn.execute("""
            INSERT INTO medications 
            (id, patient_id, drug_name, dose, route, frequency, start_date, end_date, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [med_id, patient_id, drug_name, dose, route, frequency, start_date, stop_date, "mimic-iv-demo"])

    logger.info(f"  ✓ Loaded {len(df)} medications")


def load_vitals(conn):
    """Load ICU chart events as vital signs (filtered to common vitals)."""
    chart_df = read_mimic_csv("icu", "chartevents")
    items_df = read_mimic_csv("icu", "d_items")
    if chart_df.empty:
        return

    # Build itemid → (label, unit) lookup
    item_lookup = {}
    if not items_df.empty:
        for _, row in items_df.iterrows():
            item_lookup[int(row["itemid"])] = {
                "label": row["label"],
                "unit": row["unitname"] if pd.notna(row.get("unitname")) else None,
                "category": row["category"] if pd.notna(row.get("category")) else None,
            }

    # Common vital sign item IDs in MIMIC-IV
    vital_categories = {"Routine Vital Signs", "Hemodynamics", "Respiratory"}
    vital_items = {k for k, v in item_lookup.items() if v.get("category") in vital_categories}

    # Filter to numeric vital signs only
    vitals_df = chart_df[
        (chart_df["itemid"].isin(vital_items)) & 
        (chart_df["valuenum"].notna())
    ]

    logger.info(f"  {len(vitals_df)} vital sign records (from {len(chart_df)} total chart events)")

    count = 0
    for _, row in vitals_df.iterrows():
        vital_id = str(uuid.uuid4())
        patient_id = str(row["subject_id"])
        item_info = item_lookup.get(int(row["itemid"]), {"label": f"Item {row['itemid']}", "unit": None})
        vital_name = item_info["label"]
        value = float(row["valuenum"])
        unit = str(row["valueuom"]) if pd.notna(row.get("valueuom")) else item_info.get("unit")
        charttime = str(row["charttime"]) if pd.notna(row.get("charttime")) else None
        encounter_date = charttime[:10] if charttime else None

        conn.execute("""
            INSERT INTO vital_signs 
            (id, patient_id, vital_name, value, unit, recorded_at, encounter_date, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [vital_id, patient_id, vital_name, value, unit, charttime, encounter_date, "mimic-iv-demo"])
        count += 1

    logger.info(f"  ✓ Loaded {count} vital signs")


def main():
    """Main entry point for MIMIC-IV demo data loading."""
    print("=" * 60)
    print("  MIMIC-IV Demo Data Loader for EHR Query Engine")
    print("=" * 60)
    print()

    # Check if MIMIC data exists
    if not os.path.exists(MIMIC_DIR):
        print("ERROR: MIMIC-IV demo data not found at expected location.")
        print("Please download from: https://physionet.org/content/mimic-iv-demo/2.2/")
        print(f"Expected at: {MIMIC_DIR}")
        sys.exit(1)

    # Initialize database schema first
    print("\n[1/8] Initializing database schema...")
    init_database()
    create_sample_data()
    migrate_passwords()

    # Get connections
    conn = get_duckdb_connection()
    db_session = SessionLocal()

    try:
        print("\n[2/8] Loading patients...")
        load_patients(conn, db_session)

        print("\n[3/8] Loading admissions as encounters...")
        load_admissions_as_encounters(conn)

        print("\n[4/8] Loading diagnoses...")
        load_diagnoses(conn, db_session)

        print("\n[5/8] Loading procedures...")
        load_procedures(conn, db_session)

        print("\n[6/8] Loading lab results...")
        load_lab_results(conn, db_session)

        print("\n[7/8] Loading medications...")
        load_medications(conn)

        print("\n[8/8] Loading vital signs from ICU chart events...")
        load_vitals(conn)

        # Print summary
        print("\n" + "=" * 60)
        print("  LOAD COMPLETE — Summary")
        print("=" * 60)

        tables = ["patients", "encounters", "diagnoses", "procedures_extracted", 
                  "lab_results", "medications", "vital_signs"]
        for table in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  {table:25s} → {count:>8,} rows")
            except Exception:
                print(f"  {table:25s} → (table not found)")

        # SQLite summary
        subject_count = db_session.query(Subject).count()
        proc_count = db_session.query(Procedure).count()
        obs_count = db_session.query(Observation).count()
        print(f"\n  SQLite subjects           → {subject_count:>8,} rows")
        print(f"  SQLite procedures         → {proc_count:>8,} rows")
        print(f"  SQLite observations       → {obs_count:>8,} rows")

        print("\n✓ MIMIC-IV demo data loaded successfully!")
        print("  You can now query it with natural language, e.g.:")
        print('    "Find all patients with diabetes"')
        print('    "Show patients with heart failure and lab results"')
        print('    "Patients with surgical procedures"')

    except Exception as e:
        logger.error(f"Load failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        conn.close()
        db_session.close()


if __name__ == "__main__":
    main()
