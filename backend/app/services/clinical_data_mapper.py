"""
Clinical Data Mapper
Maps ClinicalRecord objects to DuckDB tables.
Handles upsert logic and ensures all records link to a valid patient_id.
"""
import logging
import uuid
from typing import Optional

from app.services.clinical_models import ClinicalRecord, PatientInfo

logger = logging.getLogger(__name__)


def _gen_id() -> str:
    return str(uuid.uuid4())


class ClinicalDataMapper:
    """Maps a ClinicalRecord to DuckDB tables with upsert logic."""

    def map_and_insert(self, conn, record: ClinicalRecord, source_file: str = "") -> str:
        """
        Insert all data from a ClinicalRecord into DuckDB.
        Returns the patient_id used.
        Raises ValueError if patient_id cannot be determined.
        """
        patient_id = self._upsert_patient(conn, record.patient)
        if not patient_id:
            raise ValueError("Cannot insert clinical record: patient_id is null")

        sf = source_file or record.source_file

        self._insert_vitals(conn, patient_id, record.vitals, sf)
        self._insert_labs(conn, patient_id, record.labs, sf)
        self._insert_diagnoses(conn, patient_id, record.diagnoses, sf)
        self._insert_procedures(conn, patient_id, record.procedures, sf)
        self._insert_medications(conn, patient_id, record.medications, sf)
        self._insert_notes(conn, patient_id, record.notes, sf)
        self._insert_imaging(conn, patient_id, record.imaging, sf)

        return patient_id

    def _upsert_patient(self, conn, patient: PatientInfo) -> str:
        """Upsert patient record. Returns patient_id."""
        patient_id = patient.patient_id or patient.mrn
        if not patient_id:
            patient_id = _gen_id()

        existing = conn.execute(
            "SELECT patient_id FROM patients WHERE patient_id = ?", [patient_id]
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE patients SET mrn=?, date_of_birth=?, sex=?
                   WHERE patient_id=?""",
                [patient.mrn, patient.date_of_birth, patient.sex, patient_id]
            )
        else:
            conn.execute(
                """INSERT INTO patients (patient_id, mrn, date_of_birth, sex)
                   VALUES (?, ?, ?, ?)""",
                [patient_id, patient.mrn, patient.date_of_birth, patient.sex]
            )
        return patient_id

    def _insert_vitals(self, conn, patient_id: str, vitals, source_file: str) -> None:
        for v in vitals:
            conn.execute(
                """INSERT INTO vital_signs (id, patient_id, vital_name, value, unit, recorded_at, source_file, context)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, v.name, v.value, v.unit, v.timestamp, source_file, v.context]
            )

    def _insert_labs(self, conn, patient_id: str, labs, source_file: str) -> None:
        for l in labs:
            conn.execute(
                """INSERT INTO lab_results (id, patient_id, test_name, value, unit, reference_range, flag, recorded_at, source_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, l.test_name, l.value, l.unit, l.reference_range, l.flag, l.timestamp, source_file]
            )

    def _insert_diagnoses(self, conn, patient_id: str, diagnoses, source_file: str) -> None:
        for d in diagnoses:
            conn.execute(
                """INSERT INTO diagnoses (id, patient_id, description, icd_code, diagnosis_type, source_file)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, d.description, d.icd_code, d.diagnosis_type, source_file]
            )

    def _insert_procedures(self, conn, patient_id: str, procedures, source_file: str) -> None:
        for p in procedures:
            conn.execute(
                """INSERT INTO procedures_extracted (id, patient_id, description, cpt_code, procedure_date, provider, source_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, p.description, p.cpt_code, p.procedure_date, p.provider, source_file]
            )

    def _insert_medications(self, conn, patient_id: str, medications, source_file: str) -> None:
        for m in medications:
            conn.execute(
                """INSERT INTO medications (id, patient_id, drug_name, dose, route, frequency, start_date, end_date, source_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, m.drug_name, m.dose, m.route, m.frequency, m.start_date, m.end_date, source_file]
            )

    def _insert_notes(self, conn, patient_id: str, notes, source_file: str) -> None:
        for n in notes:
            conn.execute(
                """INSERT INTO clinical_notes (id, patient_id, note_type, content, author, recorded_at, source_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, n.note_type, n.content, n.author, n.recorded_at, source_file]
            )

    def _insert_imaging(self, conn, patient_id: str, imaging, source_file: str) -> None:
        for i in imaging:
            conn.execute(
                """INSERT INTO imaging_reports (id, patient_id, modality, body_part, findings, impression, report_date, source_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [_gen_id(), patient_id, i.modality, i.body_part, i.findings, i.impression, i.report_date, source_file]
            )
