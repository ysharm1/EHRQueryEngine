"""Clinical data models for PDF extraction."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VitalSign:
    name: str           # "GCS", "BP_systolic", "HR", "SpO2", "Temp", "RR", "Weight"
    value: float
    unit: str
    timestamp: Optional[str] = None
    context: Optional[str] = None  # "on admission", "post-op"


@dataclass
class LabResult:
    test_name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None   # "H", "L", "Critical"
    timestamp: Optional[str] = None


@dataclass
class Diagnosis:
    description: str
    icd_code: Optional[str] = None
    diagnosis_type: str = "secondary"  # "primary" | "secondary" | "history"
    timestamp: Optional[str] = None


@dataclass
class Procedure:
    description: str
    cpt_code: Optional[str] = None
    procedure_date: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class Medication:
    drug_name: str
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class ClinicalNote:
    note_type: str      # "nursing", "physician", "discharge", "progress"
    content: str
    author: Optional[str] = None
    recorded_at: Optional[str] = None


@dataclass
class ImagingReport:
    modality: str       # "MRI", "CT", "X-Ray", "Ultrasound"
    body_part: Optional[str] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    report_date: Optional[str] = None


@dataclass
class PatientInfo:
    patient_id: Optional[str] = None
    mrn: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[str] = None
    encounter_date: Optional[str] = None
    encounter_type: Optional[str] = None  # "inpatient" | "outpatient" | "ED"
    provider: Optional[str] = None
    facility: Optional[str] = None


@dataclass
class ExtractionHints:
    facility: Optional[str] = None
    ehr_system: Optional[str] = None   # "cerner" | "epic" | "unknown"
    extract_fields: List[str] = field(default_factory=lambda: [
        "vitals", "labs", "diagnoses", "procedures", "medications", "notes", "imaging"
    ])


@dataclass
class ClinicalRecord:
    patient: PatientInfo
    vitals: List[VitalSign] = field(default_factory=list)
    labs: List[LabResult] = field(default_factory=list)
    diagnoses: List[Diagnosis] = field(default_factory=list)
    procedures: List[Procedure] = field(default_factory=list)
    medications: List[Medication] = field(default_factory=list)
    notes: List[ClinicalNote] = field(default_factory=list)
    imaging: List[ImagingReport] = field(default_factory=list)
    raw_text: str = ""
    source_file: str = ""
    extraction_confidence: float = 0.0
