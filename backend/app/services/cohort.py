"""
Cohort Identification Service

Identifies cohorts based on multiple criteria including diagnosis, procedures,
demographics, and observations.
Implements Requirements 4.1-4.7.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.models.canonical import Subject, Procedure, Observation
import logging


logger = logging.getLogger(__name__)


class CohortIdentifier:
    """
    Cohort Identification service.
    
    Implements:
    - Requirement 4.1: Evaluate all subjects against all criteria
    - Requirement 4.2: Include only subjects matching ALL criteria (AND logic)
    - Requirement 4.3: Check diagnosis codes
    - Requirement 4.4: Verify procedure codes
    - Requirement 4.5: Compare demographic fields
    - Requirement 4.6: Check observation matches
    - Requirement 4.7: Return list of matching subjects
    """
    
    def __init__(self, db: Session):
        """
        Initialize cohort identifier.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def identify_cohort(
        self,
        criteria: List[Dict[str, Any]],
        subjects: Optional[List[Subject]] = None
    ) -> List[Subject]:
        """
        Identify cohort based on filter criteria.
        
        Args:
            criteria: List of filter criteria
            subjects: Optional list of subjects to filter (if None, queries all)
        
        Returns:
            List of subjects matching ALL criteria
        
        Implements Requirements 4.1, 4.2, 4.7
        """
        # Get all subjects if not provided
        if subjects is None:
            subjects = self.db.query(Subject).all()
        
        matching_subjects = []
        
        # Evaluate each subject (Req 4.1)
        for subject in subjects:
            matches_all = True
            
            # Check each criterion (Req 4.2 - AND logic)
            for criterion in criteria:
                if not self.evaluate_filter(subject, criterion):
                    matches_all = False
                    break
            
            if matches_all:
                matching_subjects.append(subject)
        
        return matching_subjects
    
    def evaluate_filter(
        self,
        subject: Subject,
        criterion: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single filter criterion against a subject.
        
        Args:
            subject: Subject to evaluate
            criterion: Filter criterion with type, field, operator, value
        
        Returns:
            True if subject matches criterion, False otherwise
        
        Implements Requirements 4.3-4.6
        """
        filter_type = criterion.get("filter_type")
        
        if filter_type == "Diagnosis":
            return self._evaluate_diagnosis_filter(subject, criterion)
        
        elif filter_type == "Procedure":
            return self._evaluate_procedure_filter(subject, criterion)
        
        elif filter_type == "Demographics":
            return self._evaluate_demographic_filter(subject, criterion)
        
        elif filter_type == "Observation":
            return self._evaluate_observation_filter(subject, criterion)
        
        elif filter_type == "Medication":
            return self._evaluate_medication_filter(subject, criterion)
        
        else:
            logger.warning(f"Unknown filter type: {filter_type}, treating as match")
            return True  # Unknown filter types don't block subjects
            return False
    
    def _evaluate_diagnosis_filter(
        self,
        subject: Subject,
        criterion: Dict[str, Any]
    ) -> bool:
        """
        Evaluate diagnosis filter.
        
        Implements Requirement 4.3
        """
        value = criterion.get("value", "")
        
        # Check if diagnosis code exists in subject's diagnosis codes
        if not subject.diagnosis_codes:
            return False
        
        return value in subject.diagnosis_codes
    
    def _evaluate_procedure_filter(self, subject: Subject, criterion: Dict[str, Any]) -> bool:
        """Evaluate procedure filter. Matches on code OR partial name."""
        procedure_value = criterion.get("value", "").lower().strip()

        # Empty value = match all subjects that have any procedure
        if not procedure_value:
            return self.db.query(Procedure).filter(
                Procedure.subject_id == subject.subject_id
            ).count() > 0

        procedures = self.db.query(Procedure).filter(
            Procedure.subject_id == subject.subject_id
        ).all()

        for procedure in procedures:
            code_match = procedure.procedure_code.lower() == procedure_value
            name_match = procedure_value in (procedure.procedure_name or "").lower()
            # Also match common abbreviations: DBS → Deep Brain Stimulation
            abbrev_map = {"dbs": "deep brain stimulation", "cabg": "coronary artery bypass"}
            expanded = abbrev_map.get(procedure_value, procedure_value)
            expanded_match = expanded in (procedure.procedure_name or "").lower()
            if code_match or name_match or expanded_match:
                return True

        return False
    
    def _evaluate_demographic_filter(
        self,
        subject: Subject,
        criterion: Dict[str, Any]
    ) -> bool:
        """
        Evaluate demographic filter.
        
        Implements Requirement 4.5
        """
        field = criterion.get("field", "")
        operator = criterion.get("operator", "Equals")
        value = criterion.get("value", "")
        
        # Get subject's field value
        subject_value = getattr(subject, field, None)
        
        if subject_value is None:
            return False
        
        # Apply comparison operator
        return self._apply_comparison(subject_value, operator, value, field)
    
    def _evaluate_observation_filter(
        self,
        subject: Subject,
        criterion: Dict[str, Any]
    ) -> bool:
        """
        Evaluate observation filter.
        
        Implements Requirement 4.6
        """
        observation_type = criterion.get("field", "")
        operator = criterion.get("operator", "Equals")
        value = criterion.get("value", "")
        
        # Query observations for this subject
        observations = self.db.query(Observation).filter(
            Observation.subject_id == subject.subject_id,
            Observation.observation_type == observation_type
        ).all()
        
        # Check if any observation matches the value criteria
        for observation in observations:
            if self._apply_comparison(observation.observation_value, operator, value, "observation_value"):
                return True
        
        return False
    
    def _evaluate_medication_filter(
        self,
        subject: Subject,
        criterion: Dict[str, Any]
    ) -> bool:
        """
        Evaluate medication filter.
        
        Note: Medication data would be in a separate table in full implementation.
        For now, we check observations with medication-related types.
        """
        medication_code = criterion.get("value", "")
        
        # Query observations with medication-related types
        observations = self.db.query(Observation).filter(
            Observation.subject_id == subject.subject_id,
            Observation.observation_type.like("%medication%")
        ).all()
        
        for observation in observations:
            if medication_code in observation.observation_value:
                return True
        
        return False
    
    def _apply_comparison(
        self,
        subject_value: Any,
        operator: str,
        filter_value: str,
        field_name: str
    ) -> bool:
        """
        Apply comparison operator to values.
        
        Supports: Equals, Contains, GreaterThan, LessThan, Between
        """
        if operator == "Equals":
            return str(subject_value) == filter_value
        
        elif operator == "Contains":
            return filter_value.lower() in str(subject_value).lower()
        
        elif operator == "GreaterThan":
            return self._compare_numeric_or_date(subject_value, filter_value, ">")
        
        elif operator == "LessThan":
            return self._compare_numeric_or_date(subject_value, filter_value, "<")
        
        elif operator == "Between":
            # Expect filter_value to be "min,max"
            parts = filter_value.split(",")
            if len(parts) == 2:
                min_val, max_val = parts
                return (
                    self._compare_numeric_or_date(subject_value, min_val, ">=") and
                    self._compare_numeric_or_date(subject_value, max_val, "<=")
                )
            return False
        
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    
    def _compare_numeric_or_date(
        self,
        subject_value: Any,
        filter_value: str,
        operator: str
    ) -> bool:
        """
        Compare numeric or date values.
        """
        try:
            # Try numeric comparison first
            subject_num = float(subject_value)
            filter_num = float(filter_value)
            
            if operator == ">":
                return subject_num > filter_num
            elif operator == "<":
                return subject_num < filter_num
            elif operator == ">=":
                return subject_num >= filter_num
            elif operator == "<=":
                return subject_num <= filter_num
        
        except (ValueError, TypeError):
            pass
        
        try:
            # Try date comparison
            if isinstance(subject_value, (date, datetime)):
                subject_date = subject_value
            else:
                subject_date = datetime.fromisoformat(str(subject_value))
            
            filter_date = datetime.fromisoformat(filter_value)
            
            if operator == ">":
                return subject_date > filter_date
            elif operator == "<":
                return subject_date < filter_date
            elif operator == ">=":
                return subject_date >= filter_date
            elif operator == "<=":
                return subject_date <= filter_date
        
        except (ValueError, TypeError):
            pass
        
        # If neither numeric nor date, fall back to string comparison
        if operator == ">":
            return str(subject_value) > filter_value
        elif operator == "<":
            return str(subject_value) < filter_value
        elif operator == ">=":
            return str(subject_value) >= filter_value
        elif operator == "<=":
            return str(subject_value) <= filter_value
        
        return False
    
    def calculate_age(self, date_of_birth: Optional[date]) -> Optional[int]:
        """
        Calculate age from date of birth.
        
        Args:
            date_of_birth: Date of birth
        
        Returns:
            Age in years, or None if date_of_birth is None
        """
        if date_of_birth is None:
            return None
        
        today = date.today()
        age = today.year - date_of_birth.year
        
        # Adjust if birthday hasn't occurred this year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        
        return age
