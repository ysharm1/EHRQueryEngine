from datetime import date, datetime
from typing import List, Optional, Dict, Any
import re


class ValidationError(Exception):
    """Custom validation error."""
    pass


class ValidationService:
    """
    Lightweight validation service for canonical data records.
    Validates structure and basic format — not strict code system enforcement
    (that would block real-world messy data).
    """

    @staticmethod
    def validate_subject(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate subject record. Returns cleaned data or raises ValidationError."""
        if not data.get("subject_id", "").strip():
            raise ValidationError("subject_id must be non-empty")

        sex = data.get("sex")
        if sex is not None and sex not in ("M", "F", "O"):
            raise ValidationError(f"sex must be M, F, O, or null — got '{sex}'")

        dob = data.get("date_of_birth")
        enroll = data.get("enrollment_date")
        if dob and enroll:
            if isinstance(dob, str):
                dob = date.fromisoformat(dob)
            if isinstance(enroll, str):
                enroll = date.fromisoformat(enroll)
            if enroll < dob:
                raise ValidationError("enrollment_date must be after date_of_birth")

        return data

    @staticmethod
    def validate_procedure(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate procedure record."""
        for field in ("procedure_id", "subject_id", "procedure_code", "procedure_name"):
            if not data.get(field, "").strip():
                raise ValidationError(f"{field} must be non-empty")
        return data

    @staticmethod
    def validate_observation(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate observation record."""
        for field in ("observation_id", "subject_id", "observation_type", "observation_value"):
            if not str(data.get(field, "")).strip():
                raise ValidationError(f"{field} must be non-empty")
        return data

    @staticmethod
    def validate_imaging_feature(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate imaging feature record."""
        for field in ("imaging_id", "subject_id"):
            if not data.get(field, "").strip():
                raise ValidationError(f"{field} must be non-empty")

        valid_modalities = {"MRI", "CT", "PET", "Ultrasound", "XRay"}
        if data.get("modality") not in valid_modalities:
            raise ValidationError(f"modality must be one of: {', '.join(valid_modalities)}")

        features = data.get("features", {})
        if not features:
            raise ValidationError("features must be non-empty")

        return data
