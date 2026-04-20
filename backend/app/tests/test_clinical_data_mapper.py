"""
Property-based tests for ClinicalDataMapper.
Validates P-5: every extracted record links to a valid patient_id.
"""
import duckdb
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.clinical_models import (
    ClinicalRecord, PatientInfo, VitalSign, LabResult, Diagnosis
)
from app.services.clinical_data_mapper import ClinicalDataMapper
from app.services.extraction_schema import init_extraction_tables


def make_conn():
    conn = duckdb.connect(":memory:")
    init_extraction_tables(conn)
    return conn


class TestPatientLinkageProperty:
    """P-5: Every extracted clinical record MUST be linked to a valid patient_id."""

    @given(
        vital_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
        vital_value=st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, deadline=None)
    def test_vitals_always_linked_to_patient(self, vital_name: str, vital_value: float):
        """**Validates: Requirements P-5**"""
        conn = make_conn()
        mapper = ClinicalDataMapper()
        record = ClinicalRecord(
            patient=PatientInfo(patient_id="test-patient-001"),
            vitals=[VitalSign(name=vital_name, value=vital_value, unit="units")],
        )
        patient_id = mapper.map_and_insert(conn, record, source_file="test.pdf")

        rows = conn.execute(
            "SELECT patient_id FROM vital_signs WHERE patient_id = ?", [patient_id]
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == patient_id

    def test_no_patient_id_generates_one(self):
        conn = make_conn()
        mapper = ClinicalDataMapper()
        record = ClinicalRecord(patient=PatientInfo())  # No patient_id
        patient_id = mapper.map_and_insert(conn, record, source_file="test.pdf")
        assert patient_id is not None and patient_id != ""

    def test_upsert_does_not_duplicate_patient(self):
        conn = make_conn()
        mapper = ClinicalDataMapper()
        record = ClinicalRecord(patient=PatientInfo(patient_id="pid-001", sex="M"))
        mapper.map_and_insert(conn, record)
        mapper.map_and_insert(conn, record)  # Second insert = upsert
        count = conn.execute("SELECT COUNT(*) FROM patients WHERE patient_id='pid-001'").fetchone()[0]
        assert count == 1
