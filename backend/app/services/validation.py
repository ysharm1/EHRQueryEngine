from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator, Field
import re


class ValidationError(Exception):
    """Custom validation error."""
    pass


class SubjectValidator(BaseModel):
    """Validator for Subject records."""
    subject_id: str = Field(..., min_length=1)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    diagnosis_codes: List[str] = Field(default_factory=list)
    study_group: Optional[str] = None
    enrollment_date: Optional[date] = None
    
    @validator('subject_id')
    def validate_subject_id(cls, v):
        """Validate subject_id is non-empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("subject_id must be non-empty")
        return v
    
    @validator('sex')
    def validate_sex(cls, v):
        """Validate sex is M, F, O, or None."""
        if v is not None and v not in ['M', 'F', 'O']:
            raise ValueError("sex must be one of: M, F, O, or null")
        return v
    
    @validator('diagnosis_codes')
    def validate_diagnosis_codes(cls, v):
        """Validate diagnosis codes are valid ICD-10 or SNOMED codes."""
        # Basic validation - ICD-10 format: A00-Z99.999
        # SNOMED codes are numeric
        for code in v:
            if not (cls._is_valid_icd10(code) or cls._is_valid_snomed(code)):
                raise ValueError(f"Invalid diagnosis code: {code}")
        return v
    
    @validator('enrollment_date')
    def validate_enrollment_date(cls, v, values):
        """Validate enrollment_date is after date_of_birth."""
        if v is not None and 'date_of_birth' in values and values['date_of_birth'] is not None:
            if v < values['date_of_birth']:
                raise ValueError("enrollment_date must be after date_of_birth")
        return v
    
    @staticmethod
    def _is_valid_icd10(code: str) -> bool:
        """Check if code matches ICD-10 format."""
        pattern = r'^[A-Z][0-9]{2}(\.[0-9]{1,3})?$'
        return bool(re.match(pattern, code))
    
    @staticmethod
    def _is_valid_snomed(code: str) -> bool:
        """Check if code is numeric (SNOMED format)."""
        return code.isdigit() and len(code) >= 6


class ProcedureValidator(BaseModel):
    """Validator for Procedure records."""
    procedure_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    procedure_code: str = Field(..., min_length=1)
    procedure_name: str = Field(..., min_length=1)
    procedure_date: date
    performed_by: Optional[str] = None
    
    @validator('procedure_id', 'subject_id', 'procedure_code', 'procedure_name')
    def validate_non_empty(cls, v):
        """Validate fields are non-empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Field must be non-empty")
        return v
    
    @validator('procedure_code')
    def validate_procedure_code(cls, v):
        """Validate procedure code is valid CPT or SNOMED code."""
        # CPT codes are 5 digits
        # SNOMED codes are numeric with 6+ digits
        if not (cls._is_valid_cpt(v) or cls._is_valid_snomed(v)):
            raise ValueError(f"Invalid procedure code: {v}")
        return v
    
    @staticmethod
    def _is_valid_cpt(code: str) -> bool:
        """Check if code matches CPT format (5 digits)."""
        return code.isdigit() and len(code) == 5
    
    @staticmethod
    def _is_valid_snomed(code: str) -> bool:
        """Check if code is numeric SNOMED format."""
        return code.isdigit() and len(code) >= 6


class ObservationValidator(BaseModel):
    """Validator for Observation records."""
    observation_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    observation_type: str = Field(..., min_length=1)
    observation_value: str = Field(..., min_length=1)
    observation_unit: Optional[str] = None
    observation_date: datetime
    
    @validator('observation_id', 'subject_id', 'observation_type', 'observation_value')
    def validate_non_empty(cls, v):
        """Validate fields are non-empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Field must be non-empty")
        return v
    
    @validator('observation_type')
    def validate_observation_type(cls, v):
        """Validate observation type is valid LOINC code."""
        # LOINC codes format: NNNNN-N
        pattern = r'^\d{4,5}-\d$'
        if not re.match(pattern, v):
            raise ValueError(f"Invalid LOINC code: {v}")
        return v
    
    @validator('observation_unit')
    def validate_observation_unit(cls, v, values):
        """Validate observation unit is present for numeric observations."""
        if 'observation_value' in values:
            try:
                float(values['observation_value'])
                # It's numeric, unit should be present
                if v is None or len(v.strip()) == 0:
                    raise ValueError("observation_unit required for numeric observations")
            except ValueError:
                # Not numeric, unit is optional
                pass
        return v


class ImagingFeatureValidator(BaseModel):
    """Validator for ImagingFeature records."""
    imaging_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    study_date: date
    modality: str
    features: Dict[str, float]
    study_description: Optional[str] = None
    
    @validator('imaging_id', 'subject_id')
    def validate_non_empty(cls, v):
        """Validate fields are non-empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Field must be non-empty")
        return v
    
    @validator('modality')
    def validate_modality(cls, v):
        """Validate modality is one of supported types."""
        valid_modalities = ['MRI', 'CT', 'PET', 'Ultrasound', 'XRay']
        if v not in valid_modalities:
            raise ValueError(f"modality must be one of: {', '.join(valid_modalities)}")
        return v
    
    @validator('features')
    def validate_features(cls, v):
        """Validate features is non-empty and all values are valid floats."""
        if not v or len(v) == 0:
            raise ValueError("features must be non-empty")
        
        for feature_name, feature_value in v.items():
            if not isinstance(feature_value, (int, float)):
                raise ValueError(f"Feature value for '{feature_name}' must be a number")
        
        return v


class ValidationService:
    """Service for validating data records."""
    
    @staticmethod
    def validate_subject(data: Dict[str, Any]) -> SubjectValidator:
        """
        Validate subject record.
        
        Args:
            data: Subject data dictionary
        
        Returns:
            Validated SubjectValidator object
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            return SubjectValidator(**data)
        except Exception as e:
            raise ValidationError(f"Subject validation failed: {str(e)}")
    
    @staticmethod
    def validate_procedure(data: Dict[str, Any]) -> ProcedureValidator:
        """
        Validate procedure record.
        
        Args:
            data: Procedure data dictionary
        
        Returns:
            Validated ProcedureValidator object
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            return ProcedureValidator(**data)
        except Exception as e:
            raise ValidationError(f"Procedure validation failed: {str(e)}")
    
    @staticmethod
    def validate_observation(data: Dict[str, Any]) -> ObservationValidator:
        """
        Validate observation record.
        
        Args:
            data: Observation data dictionary
        
        Returns:
            Validated ObservationValidator object
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            return ObservationValidator(**data)
        except Exception as e:
            raise ValidationError(f"Observation validation failed: {str(e)}")
    
    @staticmethod
    def validate_imaging_feature(data: Dict[str, Any]) -> ImagingFeatureValidator:
        """
        Validate imaging feature record.
        
        Args:
            data: ImagingFeature data dictionary
        
        Returns:
            Validated ImagingFeatureValidator object
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            return ImagingFeatureValidator(**data)
        except Exception as e:
            raise ValidationError(f"ImagingFeature validation failed: {str(e)}")
