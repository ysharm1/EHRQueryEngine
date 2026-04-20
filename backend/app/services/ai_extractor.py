"""
AI Clinical Extractor
Uses LLM (OpenAI GPT-4 or Anthropic Claude) to extract structured clinical data
from raw PDF text. Flexible — handles any PDF format without rigid templates.
"""

import json
import logging
from typing import Optional

from app.services.clinical_models import (
    ClinicalRecord, PatientInfo, VitalSign, LabResult,
    Diagnosis, Procedure, Medication, ClinicalNote, ImagingReport, ExtractionHints
)

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are a clinical data extraction specialist. Extract ALL structured clinical data from the provided medical document text.

Return ONLY valid JSON matching this exact schema:
{
  "patient": {
    "patient_id": "string or null",
    "mrn": "string or null",
    "date_of_birth": "YYYY-MM-DD or null",
    "sex": "M/F/Other or null",
    "encounter_date": "YYYY-MM-DD or null",
    "encounter_type": "inpatient/outpatient/ED or null",
    "provider": "string or null",
    "facility": "string or null"
  },
  "vitals": [
    {"name": "GCS", "value": 15, "unit": "points", "timestamp": null, "context": null}
  ],
  "labs": [
    {"test_name": "Hemoglobin", "value": "13.5", "unit": "g/dL", "reference_range": "12-16", "flag": null, "timestamp": null}
  ],
  "diagnoses": [
    {"description": "Type 2 Diabetes", "icd_code": "E11", "diagnosis_type": "primary", "timestamp": null}
  ],
  "procedures": [
    {"description": "MRI Brain", "cpt_code": null, "procedure_date": null, "provider": null}
  ],
  "medications": [
    {"drug_name": "Metformin", "dose": "500mg", "route": "oral", "frequency": "twice daily", "start_date": null, "end_date": null}
  ],
  "notes": [
    {"note_type": "nursing", "content": "Patient alert and oriented x3", "author": null, "recorded_at": null}
  ],
  "imaging": [
    {"modality": "MRI", "body_part": "Brain", "findings": "No acute findings", "impression": "Normal", "report_date": null}
  ],
  "confidence": 0.92
}

Rules:
- Extract ALL data present, do not omit anything
- For vitals, always use numeric values (convert if needed)
- For GCS: extract total score AND components if present (GCS_eye, GCS_verbal, GCS_motor)
- If a field is not present in the document, use null
- confidence: your overall confidence in the extraction quality (0.0-1.0)
- Return ONLY the JSON object, no markdown, no explanation"""


class AIClinicalExtractor:
    """
    Extracts structured clinical data from raw text using LLM.
    Supports OpenAI GPT-4 and Anthropic Claude.
    Falls back to pattern-based extraction if no API key is configured.
    """

    def __init__(self, llm_provider: str = "openai") -> None:
        self.llm_provider = llm_provider
        self._client = None
        self._demo_mode = False
        self._init_client()

    def _init_client(self) -> None:
        from app.config import settings
        if self.llm_provider == "openai" and settings.openai_api_key:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.openai_api_key)
        elif self.llm_provider == "anthropic" and settings.anthropic_api_key:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=settings.anthropic_api_key)
        else:
            logger.warning("No LLM API key found, using demo extraction mode")
            self._demo_mode = True

    def extract(self, raw_text: str, hints: Optional[ExtractionHints] = None, source_file: str = "") -> ClinicalRecord:
        """Extract all clinical data from raw text. Returns a ClinicalRecord."""
        if not raw_text or not raw_text.strip():
            return ClinicalRecord(patient=PatientInfo(), source_file=source_file, extraction_confidence=0.0)

        if self._demo_mode:
            return self._demo_extract(raw_text, source_file)

        try:
            prompt = self._build_prompt(raw_text, hints)
            if self.llm_provider == "openai":
                response_text = self._call_openai(prompt)
            else:
                response_text = self._call_anthropic(prompt)
            return self._parse_response(response_text, raw_text, source_file)
        except Exception as exc:
            logger.exception("AI extraction failed, falling back to demo mode")
            return self._demo_extract(raw_text, source_file)

    def _build_prompt(self, raw_text: str, hints: Optional[ExtractionHints]) -> str:
        hint_str = ""
        if hints:
            if hints.facility:
                hint_str += f"\nFacility: {hints.facility}"
            if hints.ehr_system:
                hint_str += f"\nEHR System: {hints.ehr_system}"
        return f"Extract all clinical data from this medical document.{hint_str}\n\nDOCUMENT TEXT:\n{raw_text[:12000]}"

    def _call_openai(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        response = self._client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _parse_response(self, response_text: str, raw_text: str, source_file: str) -> ClinicalRecord:
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        patient_data = data.get("patient", {}) or {}
        patient = PatientInfo(
            patient_id=patient_data.get("patient_id"),
            mrn=patient_data.get("mrn"),
            date_of_birth=patient_data.get("date_of_birth"),
            sex=patient_data.get("sex"),
            encounter_date=patient_data.get("encounter_date"),
            encounter_type=patient_data.get("encounter_type"),
            provider=patient_data.get("provider"),
            facility=patient_data.get("facility"),
        )

        vitals = [VitalSign(**v) for v in (data.get("vitals") or [])]
        labs = [LabResult(**l) for l in (data.get("labs") or [])]
        diagnoses = [Diagnosis(**d) for d in (data.get("diagnoses") or [])]
        procedures = [Procedure(**p) for p in (data.get("procedures") or [])]
        medications = [Medication(**m) for m in (data.get("medications") or [])]
        notes = [ClinicalNote(**n) for n in (data.get("notes") or [])]
        imaging = [ImagingReport(**i) for i in (data.get("imaging") or [])]

        return ClinicalRecord(
            patient=patient,
            vitals=vitals, labs=labs, diagnoses=diagnoses,
            procedures=procedures, medications=medications,
            notes=notes, imaging=imaging,
            raw_text=raw_text, source_file=source_file,
            extraction_confidence=confidence,
        )

    def _demo_extract(self, raw_text: str, source_file: str) -> ClinicalRecord:
        """Pattern-based fallback extraction when no LLM is available."""
        import re
        vitals = []
        text_lower = raw_text.lower()

        # GCS
        gcs_match = re.search(r'gcs[:\s]+(\d+)', text_lower)
        if gcs_match:
            vitals.append(VitalSign(name="GCS", value=float(gcs_match.group(1)), unit="points"))

        # BP
        bp_match = re.search(r'bp[:\s]+(\d+)/(\d+)', text_lower)
        if bp_match:
            vitals.append(VitalSign(name="BP_systolic", value=float(bp_match.group(1)), unit="mmHg"))
            vitals.append(VitalSign(name="BP_diastolic", value=float(bp_match.group(2)), unit="mmHg"))

        # HR
        hr_match = re.search(r'hr[:\s]+(\d+)|heart rate[:\s]+(\d+)', text_lower)
        if hr_match:
            val = hr_match.group(1) or hr_match.group(2)
            vitals.append(VitalSign(name="HR", value=float(val), unit="bpm"))

        return ClinicalRecord(
            patient=PatientInfo(),
            vitals=vitals,
            raw_text=raw_text,
            source_file=source_file,
            extraction_confidence=0.4,
        )
