"""
Schema Mapper Service

Maps between source schemas (FHIR, REDCap, CSV) and canonical research schema.
Implements Requirements 5.1-5.7.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re


class TransformationType(str, Enum):
    """Types of field transformations."""
    DATE_PARSE = "DateParse"
    CODE_LOOKUP = "CodeLookup"
    UNIT_CONVERSION = "UnitConversion"
    STRING_NORMALIZE = "StringNormalize"


@dataclass
class FieldMapping:
    """Mapping for a single field from source to target schema."""
    source_path: str
    target_field: str
    transform: Optional[str] = None
    transform_params: Optional[Dict[str, Any]] = None


@dataclass
class SchemaMapping:
    """Complete schema mapping from source to target."""
    source_schema: str
    target_schema: str
    field_mappings: List[FieldMapping]


class SchemaMapper:
    """
    Schema Mapper service for data transformation.
    
    Implements:
    - Requirement 5.1: Apply schema mappings during ingestion
    - Requirement 5.2: Apply transformation functions
    - Requirement 5.3: Transform dates to ISO 8601
    - Requirement 5.4: Lookup codes in code systems
    - Requirement 5.5: Convert units
    - Requirement 5.6: Normalize strings
    - Requirement 5.7: Infer field mappings
    """
    
    # Common date formats to try when parsing
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S"
    ]
    
    # Common code system mappings
    CODE_SYSTEMS = {
        "ICD10": "http://hl7.org/fhir/sid/icd-10",
        "SNOMED": "http://snomed.info/sct",
        "LOINC": "http://loinc.org",
        "CPT": "http://www.ama-assn.org/go/cpt"
    }
    
    # Unit conversion factors (to standard units)
    UNIT_CONVERSIONS = {
        ("lb", "kg"): 0.453592,
        ("kg", "lb"): 2.20462,
        ("in", "cm"): 2.54,
        ("cm", "in"): 0.393701,
        ("F", "C"): lambda f: (f - 32) * 5/9,
        ("C", "F"): lambda c: c * 9/5 + 32,
        ("mmHg", "kPa"): 0.133322,
        ("kPa", "mmHg"): 7.50062
    }
    
    def __init__(self):
        """Initialize the schema mapper."""
        pass
    
    def map_to_canonical(
        self,
        source_data: List[Dict[str, Any]],
        mapping: SchemaMapping
    ) -> List[Dict[str, Any]]:
        """
        Map source data to canonical schema.
        
        Args:
            source_data: List of records from source system
            mapping: SchemaMapping defining field transformations
        
        Returns:
            List of records in canonical schema format
        
        Implements Requirements 5.1, 5.2
        """
        canonical_data = []
        
        for record in source_data:
            canonical_record = {}
            
            for field_mapping in mapping.field_mappings:
                # Extract value from source
                source_value = self._extract_value(record, field_mapping.source_path)
                
                # Apply transformation if specified
                if field_mapping.transform and source_value is not None:
                    transformed_value = self._apply_transformation(
                        source_value,
                        field_mapping.transform,
                        field_mapping.transform_params or {}
                    )
                else:
                    transformed_value = source_value
                
                # Set target field
                canonical_record[field_mapping.target_field] = transformed_value
            
            canonical_data.append(canonical_record)
        
        return canonical_data
    
    def _extract_value(self, record: Dict[str, Any], path: str) -> Any:
        """
        Extract value from nested dictionary using dot notation path.
        
        Example: "patient.name.given" extracts record["patient"]["name"]["given"]
        """
        parts = path.split(".")
        value = record
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                idx = int(part)
                value = value[idx] if idx < len(value) else None
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _apply_transformation(
        self,
        value: Any,
        transform_type: str,
        params: Dict[str, Any]
    ) -> Any:
        """
        Apply transformation function to a value.
        
        Implements Requirements 5.2-5.6
        """
        if transform_type == TransformationType.DATE_PARSE:
            return self._transform_date(value, params.get("format"))
        
        elif transform_type == TransformationType.CODE_LOOKUP:
            return self._transform_code(value, params.get("code_system"))
        
        elif transform_type == TransformationType.UNIT_CONVERSION:
            return self._transform_unit(
                value,
                params.get("from_unit"),
                params.get("to_unit")
            )
        
        elif transform_type == TransformationType.STRING_NORMALIZE:
            return self._transform_string(value)
        
        else:
            return value
    
    def _transform_date(self, value: Any, format_hint: Optional[str] = None) -> str:
        """
        Transform date to ISO 8601 format.
        
        Implements Requirement 5.3
        """
        if isinstance(value, datetime):
            return value.date().isoformat()
        
        if not isinstance(value, str):
            return str(value)
        
        # Try format hint first
        if format_hint:
            try:
                dt = datetime.strptime(value, format_hint)
                return dt.date().isoformat()
            except ValueError:
                pass
        
        # Try common formats
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
        
        # If all parsing fails, return original value
        return value
    
    def _transform_code(self, value: Any, code_system: Optional[str] = None) -> str:
        """
        Lookup code in specified code system.
        
        Implements Requirement 5.4
        """
        if not isinstance(value, str):
            return str(value)
        
        # If code system specified, validate/normalize
        if code_system and code_system in self.CODE_SYSTEMS:
            # In a real implementation, this would lookup the code
            # For now, just return the code as-is
            return value
        
        # Extract code from common formats like "G20 - Parkinson's disease"
        code_match = re.match(r'^([A-Z0-9.]+)', value)
        if code_match:
            return code_match.group(1)
        
        return value
    
    def _transform_unit(
        self,
        value: Any,
        from_unit: Optional[str],
        to_unit: Optional[str]
    ) -> float:
        """
        Convert value from one unit to another.
        
        Implements Requirement 5.5
        """
        if not from_unit or not to_unit:
            return float(value)
        
        # Get conversion factor
        conversion_key = (from_unit, to_unit)
        
        if conversion_key in self.UNIT_CONVERSIONS:
            converter = self.UNIT_CONVERSIONS[conversion_key]
            
            if callable(converter):
                return converter(float(value))
            else:
                return float(value) * converter
        
        # No conversion available, return original
        return float(value)
    
    def _transform_string(self, value: Any) -> str:
        """
        Normalize string values.
        
        Implements Requirement 5.6
        """
        if not isinstance(value, str):
            return str(value)
        
        # Normalize whitespace
        normalized = " ".join(value.split())
        
        # Trim
        normalized = normalized.strip()
        
        # Convert to title case for names
        # (This is a simple heuristic; real implementation might be more sophisticated)
        if len(normalized) > 0 and normalized[0].isupper():
            normalized = normalized.title()
        
        return normalized
    
    def infer_mapping(
        self,
        source_schema: str,
        target_schema: str,
        sample_data: Optional[List[Dict[str, Any]]] = None
    ) -> SchemaMapping:
        """
        Infer field mappings based on field names and types.
        
        Implements Requirement 5.7
        """
        field_mappings = []
        
        # Define common field name patterns for canonical schema
        field_patterns = {
            "subject_id": ["id", "patient_id", "subject_id", "mrn", "patient_identifier"],
            "date_of_birth": ["dob", "birth_date", "date_of_birth", "birthdate"],
            "sex": ["sex", "gender"],
            "diagnosis_codes": ["diagnosis", "diagnoses", "icd10", "conditions"],
            "procedure_code": ["procedure", "procedure_code", "cpt"],
            "procedure_name": ["procedure_name", "procedure_description"],
            "procedure_date": ["procedure_date", "date", "service_date"],
            "observation_type": ["observation_type", "test_type", "loinc"],
            "observation_value": ["value", "result", "observation_value"],
            "observation_unit": ["unit", "units", "uom"],
            "observation_date": ["observation_date", "test_date", "result_date"]
        }
        
        # If sample data provided, analyze field names
        if sample_data and len(sample_data) > 0:
            sample_record = sample_data[0]
            source_fields = list(sample_record.keys())
            
            # Match source fields to target fields
            for target_field, patterns in field_patterns.items():
                for source_field in source_fields:
                    source_lower = source_field.lower().replace("_", "").replace(" ", "")
                    
                    for pattern in patterns:
                        pattern_lower = pattern.lower().replace("_", "")
                        
                        if pattern_lower in source_lower or source_lower in pattern_lower:
                            # Determine if transformation needed
                            transform = None
                            transform_params = None
                            
                            # Check if field looks like a date
                            if "date" in source_field.lower() or "dob" in source_field.lower():
                                transform = TransformationType.DATE_PARSE
                                transform_params = {}
                            
                            # Check if field looks like a code
                            elif "code" in source_field.lower() or "icd" in source_field.lower():
                                transform = TransformationType.CODE_LOOKUP
                                transform_params = {}
                            
                            field_mappings.append(FieldMapping(
                                source_path=source_field,
                                target_field=target_field,
                                transform=transform,
                                transform_params=transform_params
                            ))
                            break
        
        return SchemaMapping(
            source_schema=source_schema,
            target_schema=target_schema,
            field_mappings=field_mappings
        )
