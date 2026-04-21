"""
Clinical Data Mapper
Maps ClinicalRecord objects to DuckDB tables.
Handles upsert logic and ensures all records link to a valid patient_id.
Enhanced with encounter resolution and provenance tracking.
"""
import logging
import uuid
from typing import Optional

from app.services.clinical_models import ClinicalRecord, PatientInfo
from app.services.encounter_manager import EncounterManager
from app.services.provenance_mapper import ProvenanceMapper

logger = logging.getLogger(__name__)


def _gen_id() -> str:
    return str(uuid.uuid4())


class ClinicalDataMapper:
    """Maps a ClinicalRecord to DuckDB tables with upsert logic."""

    def __init__(self) -> None:
        self._encounter_manager = EncounterManager()
        self._provenance_mapper = ProvenanceMapper()

    def map_and_insert(
        self,
        conn,
        record: ClinicalRecord,
        source_file: str = "",
        extraction_job_id: Optional[str] = None,
    ) -> str:
        """
        Insert all data from a ClinicalRecord into DuckDB.
        Returns the patient_id used.
        Raises ValueError if patient_id cannot be determined.
        """
        patient_id = self._upsert_patient(conn, record.patient)
        if not patient_id:
            raise ValueError("Cannot insert clinical record: patient_id is null")

        sf = source_file or record.source_file
        job_id = extraction_job_id or ""
        confidence = record.extraction_confidence

        # Resolve encounter
        encounter_id = self._encounter_manager.find_or_create_encounter(
            conn,
            patient_id=patient_id,
            encounter_date=record.patient.encounter_date,
            encounter_type=record.encounter_type or record.patient.encounter_type,
            source_file=sf,
            encounter_id_hint=record.encounter_id,
        )

        self._insert_vitals(conn, patient_id, record.vitals, sf, encounter_id, job_id, confidence)
        self._insert_labs(conn, patient_id, record.labs, sf, encounter_id, job_id, confidence)
        self._insert_diagnoses(conn, patient_id, record.diagnoses, sf, encounter_id, job_id, confidence)
        self._insert_procedures(conn, patient_id, record.procedures, sf, encounter_id, job_id, confidence)
        self._insert_medications(conn, patient_id, record.medications, sf, encounter_id, job_id, confidence)
        self._insert_notes(conn, patient_id, record.notes, sf, encounter_id, job_id, confidence)
        self._insert_imaging(conn, patient_id, record.imaging, sf, encounter_id, job_id, confidence)

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

    def _insert_vitals(self, conn, patient_id: str, vitals, source_file: str,
                       encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for v in vitals:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO vital_signs
                   (id, patient_id, vital_name, value, unit, recorded_at,
                    source_file, context, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, v.name, v.value, v.unit, v.timestamp,
                 source_file, v.context, encounter_id,
                 getattr(v, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="vital_signs",
                source_file=source_file,
                page_number=getattr(v, 'source_page', None),
                provider_name=getattr(v, 'provider_name', None),
                provider_type=getattr(v, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE vital_signs SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )

    def _insert_labs(self, conn, patient_id: str, labs, source_file: str,
                     encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for l in labs:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO lab_results
                   (id, patient_id, test_name, value, unit, reference_range,
                    flag, recorded_at, source_file, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, l.test_name, l.value, l.unit,
                 l.reference_range, l.flag, l.timestamp, source_file,
                 encounter_id, getattr(l, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="lab_results",
                source_file=source_file,
                page_number=getattr(l, 'source_page', None),
                provider_name=getattr(l, 'provider_name', None),
                provider_type=getattr(l, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE lab_results SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )

    def _insert_diagnoses(self, conn, patient_id: str, diagnoses, source_file: str,
                          encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for d in diagnoses:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO diagnoses
                   (id, patient_id, description, icd_code, diagnosis_type,
                    source_file, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, d.description, d.icd_code,
                 d.diagnosis_type, source_file, encounter_id,
                 getattr(d, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="diagnoses",
                source_file=source_file,
                page_number=getattr(d, 'source_page', None),
                provider_name=getattr(d, 'provider_name', None),
                provider_type=getattr(d, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE diagnoses SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )

    def _insert_procedures(self, conn, patient_id: str, procedures, source_file: str,
                           encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for p in procedures:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO procedures_extracted
                   (id, patient_id, description, cpt_code, procedure_date,
                    provider, source_file, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, p.description, p.cpt_code,
                 p.procedure_date, p.provider, source_file, encounter_id,
                 getattr(p, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="procedures_extracted",
                source_file=source_file,
                page_number=getattr(p, 'source_page', None),
                provider_name=getattr(p, 'provider_name', None),
                provider_type=getattr(p, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE procedures_extracted SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )

    def _insert_medications(self, conn, patient_id: str, medications, source_file: str,
                            encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for m in medications:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO medications
                   (id, patient_id, drug_name, dose, route, frequency,
                    start_date, end_date, source_file, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, m.drug_name, m.dose, m.route,
                 m.frequency, m.start_date, m.end_date, source_file,
                 encounter_id, getattr(m, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="medications",
                source_file=source_file,
                page_number=getattr(m, 'source_page', None),
                provider_name=getattr(m, 'provider_name', None),
                provider_type=getattr(m, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE medications SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )

    def _insert_notes(self, conn, patient_id: str, notes, source_file: str,
                      encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for n in notes:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO clinical_notes
                   (id, patient_id, note_type, content, author, recorded_at,
                    source_file, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, n.note_type, n.content, n.author,
                 n.recorded_at, source_file, encounter_id,
                 getattr(n, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="clinical_notes",
                source_file=source_file,
                page_number=getattr(n, 'source_page', None),
                provider_name=getattr(n, 'provider_name', None),
                provider_type=getattr(n, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE clinical_notes SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )

    def _insert_imaging(self, conn, patient_id: str, imaging, source_file: str,
                        encounter_id: str, extraction_job_id: str, confidence: float) -> None:
        for i in imaging:
            record_id = _gen_id()
            conn.execute(
                """INSERT INTO imaging_reports
                   (id, patient_id, modality, body_part, findings, impression,
                    report_date, source_file, encounter_id, provider_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [record_id, patient_id, i.modality, i.body_part, i.findings,
                 i.impression, i.report_date, source_file, encounter_id,
                 getattr(i, 'provider_type', None)]
            )
            provenance_id = self._provenance_mapper.record_provenance(
                conn,
                data_record_id=record_id,
                data_table="imaging_reports",
                source_file=source_file,
                page_number=getattr(i, 'source_page', None),
                provider_name=getattr(i, 'provider_name', None),
                provider_type=getattr(i, 'provider_type', None),
                extraction_confidence=confidence,
                extraction_job_id=extraction_job_id,
            )
            conn.execute(
                "UPDATE imaging_reports SET provenance_id = ? WHERE id = ?",
                [provenance_id, record_id]
            )
