"""
Property-based tests for AI Clinical Extractor.
Validates P-4 (schema consistency) and P-6 (confidence bounds).
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.ai_extractor import AIClinicalExtractor
from app.services.clinical_models import ClinicalRecord, VitalSign


class TestConfidenceBoundsProperty:
    """P-6: Extraction confidence scores MUST always be in range [0.0, 1.0].

    **Validates: Requirements P-6**
    """

    @given(text=st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_confidence_always_in_bounds(self, text: str):
        extractor = AIClinicalExtractor(llm_provider="openai")
        extractor._demo_mode = True  # Force demo mode, no API call
        record = extractor.extract(text, source_file="test.pdf")
        assert 0.0 <= record.extraction_confidence <= 1.0, (
            f"Confidence {record.extraction_confidence} out of bounds [0.0, 1.0]"
        )


class TestSchemaConsistencyProperty:
    """P-4: All extracted vital signs MUST have non-null vital_name and numeric value.

    **Validates: Requirements P-4**
    """

    @given(text=st.text(min_size=1, max_size=500))
    @settings(max_examples=50)
    def test_vitals_have_name_and_numeric_value(self, text: str):
        extractor = AIClinicalExtractor(llm_provider="openai")
        extractor._demo_mode = True
        record = extractor.extract(text, source_file="test.pdf")
        for vital in record.vitals:
            assert vital.name is not None and vital.name != "", (
                f"VitalSign has null/empty name: {vital}"
            )
            assert isinstance(vital.value, (int, float)), (
                f"VitalSign value is not numeric: {vital.value}"
            )


class TestClinicalRecordUnit:
    def test_empty_text_returns_empty_record(self):
        extractor = AIClinicalExtractor()
        extractor._demo_mode = True
        record = extractor.extract("", source_file="empty.pdf")
        assert record.extraction_confidence == 0.0
        assert record.vitals == []

    def test_gcs_extracted_in_demo_mode(self):
        extractor = AIClinicalExtractor()
        extractor._demo_mode = True
        record = extractor.extract("Patient GCS: 14 on admission", source_file="test.pdf")
        gcs_vitals = [v for v in record.vitals if v.name == "GCS"]
        assert len(gcs_vitals) == 1
        assert gcs_vitals[0].value == 14.0

    def test_bp_extracted_in_demo_mode(self):
        extractor = AIClinicalExtractor()
        extractor._demo_mode = True
        record = extractor.extract("BP: 120/80 mmHg", source_file="test.pdf")
        bp = [v for v in record.vitals if "BP" in v.name]
        assert len(bp) == 2
