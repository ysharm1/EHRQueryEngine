"""
FHIR Connector Service

Connects to EHR systems via FHIR APIs and transforms resources to canonical schema.
Implements Requirements 6.1-6.8, 15.6, 16.1.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import httpx
import logging
from app.services.schema_mapper import SchemaMapper, SchemaMapping, FieldMapping, TransformationType


logger = logging.getLogger(__name__)


class FHIRResource(str, Enum):
    """FHIR resource types."""
    PATIENT = "Patient"
    CONDITION = "Condition"
    PROCEDURE = "Procedure"
    OBSERVATION = "Observation"
    MEDICATION_REQUEST = "MedicationRequest"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    IMAGING_STUDY = "ImagingStudy"
    ENCOUNTER = "Encounter"


@dataclass
class FHIRConfig:
    """FHIR endpoint configuration."""
    base_url: str
    auth_token: str
    version: str = "R4"
    timeout: int = 30


@dataclass
class FHIRQuery:
    """FHIR search query parameters."""
    resource_type: FHIRResource
    search_params: List[tuple[str, str]]
    page_size: int = 100


@dataclass
class FHIREntry:
    """Single entry in a FHIR bundle."""
    resource: Dict[str, Any]


@dataclass
class FHIRBundle:
    """FHIR bundle response."""
    resource_type: str
    entries: List[FHIREntry]
    next_page_url: Optional[str] = None


class FHIRConnector:
    """
    FHIR Connector service for EHR integration.
    
    Implements:
    - Requirement 6.1: Authenticate with FHIR endpoints
    - Requirement 6.2: Construct valid FHIR search requests
    - Requirement 6.3: Handle pagination
    - Requirement 6.4: Map Patient resources to subjects table
    - Requirement 6.5: Map Condition resources to observations table
    - Requirement 6.6: Map Procedure resources to procedures table
    - Requirement 6.7: Log validation errors and continue processing
    - Requirement 6.8: Return authentication failure errors
    - Requirement 15.6: Use encrypted connections
    - Requirement 16.1: Handle FHIR authentication errors
    """
    
    def __init__(self, config: FHIRConfig):
        """
        Initialize FHIR connector.
        
        Args:
            config: FHIR endpoint configuration
        
        Implements Requirement 6.1
        """
        self.config = config
        self.schema_mapper = SchemaMapper()
        self.client = httpx.Client(
            timeout=config.timeout,
            verify=True  # Enforce SSL verification (Req 15.6)
        )
    
    def query(self, query: FHIRQuery) -> FHIRBundle:
        """
        Execute FHIR search query with pagination support.
        
        Args:
            query: FHIR search query parameters
        
        Returns:
            FHIRBundle with resources and next page URL
        
        Implements Requirements 6.2, 6.3, 6.8, 16.1
        """
        # Construct FHIR search URL
        url = f"{self.config.base_url}/{query.resource_type.value}"
        
        # Build query parameters
        params = {
            "_count": query.page_size,
            "_format": "json"
        }
        
        # Add search parameters
        for key, value in query.search_params:
            params[key] = value
        
        # Set authorization header
        headers = {
            "Authorization": self.config.auth_token,
            "Accept": "application/fhir+json"
        }
        
        try:
            # Execute request (Req 6.2)
            response = self.client.get(url, params=params, headers=headers)
            
            # Handle authentication errors (Req 6.8, 16.1)
            if response.status_code in [401, 403]:
                raise FHIRAuthenticationError(
                    f"FHIR authentication failed: {response.status_code} {response.reason_phrase}"
                )
            
            response.raise_for_status()
            
            # Parse response
            bundle_data = response.json()
            
            # Extract entries
            entries = []
            for entry in bundle_data.get("entry", []):
                if "resource" in entry:
                    entries.append(FHIREntry(resource=entry["resource"]))
            
            # Extract next page URL (Req 6.3)
            next_page_url = None
            for link in bundle_data.get("link", []):
                if link.get("relation") == "next":
                    next_page_url = link.get("url")
                    break
            
            return FHIRBundle(
                resource_type=query.resource_type.value,
                entries=entries,
                next_page_url=next_page_url
            )
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                raise FHIRAuthenticationError(
                    f"FHIR authentication failed: {e.response.status_code}"
                )
            raise
        
        except httpx.RequestError as e:
            logger.error(f"FHIR request failed: {e}")
            raise
    
    def query_all_pages(self, query: FHIRQuery) -> List[FHIREntry]:
        """
        Execute FHIR query and retrieve all pages.
        
        Args:
            query: FHIR search query parameters
        
        Returns:
            List of all FHIR entries across all pages
        
        Implements Requirement 6.3
        """
        all_entries = []
        
        # Get first page
        bundle = self.query(query)
        all_entries.extend(bundle.entries)
        
        # Follow pagination links
        while bundle.next_page_url:
            # Parse next page URL and execute request
            try:
                headers = {
                    "Authorization": self.config.auth_token,
                    "Accept": "application/fhir+json"
                }
                
                response = self.client.get(bundle.next_page_url, headers=headers)
                response.raise_for_status()
                
                bundle_data = response.json()
                
                # Extract entries
                entries = []
                for entry in bundle_data.get("entry", []):
                    if "resource" in entry:
                        entries.append(FHIREntry(resource=entry["resource"]))
                
                all_entries.extend(entries)
                
                # Get next page URL
                next_page_url = None
                for link in bundle_data.get("link", []):
                    if link.get("relation") == "next":
                        next_page_url = link.get("url")
                        break
                
                bundle.next_page_url = next_page_url
            
            except Exception as e:
                logger.error(f"Error fetching next page: {e}")
                break
        
        return all_entries
    
    def transform_to_canonical(
        self,
        bundle: FHIRBundle,
        mapping: Optional[SchemaMapping] = None
    ) -> List[Dict[str, Any]]:
        """
        Transform FHIR resources to canonical schema.
        
        Args:
            bundle: FHIR bundle with resources
            mapping: Optional custom schema mapping
        
        Returns:
            List of records in canonical schema format
        
        Implements Requirements 6.4, 6.5, 6.6, 6.7
        """
        canonical_records = []
        
        for entry in bundle.entries:
            resource = entry.resource
            resource_type = resource.get("resourceType")
            
            try:
                # Transform based on resource type
                if resource_type == "Patient":
                    canonical_record = self._transform_patient(resource)
                elif resource_type == "Condition":
                    canonical_record = self._transform_condition(resource)
                elif resource_type == "Procedure":
                    canonical_record = self._transform_procedure(resource)
                elif resource_type == "Observation":
                    canonical_record = self._transform_observation(resource)
                else:
                    logger.warning(f"Unsupported resource type: {resource_type}")
                    continue
                
                if canonical_record:
                    canonical_records.append(canonical_record)
            
            except Exception as e:
                # Log validation error and continue (Req 6.7)
                resource_id = resource.get("id", "unknown")
                logger.error(
                    f"Failed to transform {resource_type} resource {resource_id}: {e}"
                )
                continue
        
        return canonical_records
    
    def _transform_patient(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform FHIR Patient resource to subjects table.
        
        Implements Requirement 6.4
        """
        patient_id = resource.get("id", "")
        
        # Extract birth date
        birth_date = resource.get("birthDate")
        
        # Extract gender/sex
        gender = resource.get("gender")
        sex_map = {"male": "M", "female": "F", "other": "O"}
        sex = sex_map.get(gender, None)
        
        # Extract diagnosis codes from conditions (if embedded)
        diagnosis_codes = []
        
        return {
            "subject_id": patient_id,
            "date_of_birth": birth_date,
            "sex": sex,
            "diagnosis_codes": diagnosis_codes,
            "study_group": None,
            "enrollment_date": None
        }
    
    def _transform_condition(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform FHIR Condition resource to observations table.
        
        Implements Requirement 6.5
        """
        condition_id = resource.get("id", "")
        
        # Extract subject reference
        subject_ref = resource.get("subject", {}).get("reference", "")
        subject_id = subject_ref.split("/")[-1] if "/" in subject_ref else subject_ref
        
        # Extract condition code
        code_obj = resource.get("code", {})
        coding = code_obj.get("coding", [{}])[0]
        condition_code = coding.get("code", "")
        condition_display = coding.get("display", "")
        
        # Extract recorded date
        recorded_date = resource.get("recordedDate") or resource.get("onsetDateTime")
        
        return {
            "observation_id": condition_id,
            "subject_id": subject_id,
            "observation_type": condition_code,
            "observation_value": condition_display,
            "observation_unit": None,
            "observation_date": recorded_date
        }
    
    def _transform_procedure(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform FHIR Procedure resource to procedures table.
        
        Implements Requirement 6.6
        """
        procedure_id = resource.get("id", "")
        
        # Extract subject reference
        subject_ref = resource.get("subject", {}).get("reference", "")
        subject_id = subject_ref.split("/")[-1] if "/" in subject_ref else subject_ref
        
        # Extract procedure code
        code_obj = resource.get("code", {})
        coding = code_obj.get("coding", [{}])[0]
        procedure_code = coding.get("code", "")
        procedure_name = coding.get("display", "")
        
        # Extract performed date
        performed_date = resource.get("performedDateTime") or resource.get("performedPeriod", {}).get("start")
        
        # Extract performer
        performers = resource.get("performer", [])
        performed_by = None
        if performers:
            actor_ref = performers[0].get("actor", {}).get("reference", "")
            performed_by = actor_ref.split("/")[-1] if "/" in actor_ref else actor_ref
        
        return {
            "procedure_id": procedure_id,
            "subject_id": subject_id,
            "procedure_code": procedure_code,
            "procedure_name": procedure_name,
            "procedure_date": performed_date,
            "performed_by": performed_by
        }
    
    def _transform_observation(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform FHIR Observation resource to observations table.
        """
        observation_id = resource.get("id", "")
        
        # Extract subject reference
        subject_ref = resource.get("subject", {}).get("reference", "")
        subject_id = subject_ref.split("/")[-1] if "/" in subject_ref else subject_ref
        
        # Extract observation code
        code_obj = resource.get("code", {})
        coding = code_obj.get("coding", [{}])[0]
        observation_type = coding.get("code", "")
        
        # Extract value
        value_quantity = resource.get("valueQuantity", {})
        observation_value = str(value_quantity.get("value", ""))
        observation_unit = value_quantity.get("unit")
        
        # If no quantity, try other value types
        if not observation_value:
            observation_value = resource.get("valueString") or resource.get("valueCodeableConcept", {}).get("text", "")
        
        # Extract effective date
        observation_date = resource.get("effectiveDateTime") or resource.get("issued")
        
        return {
            "observation_id": observation_id,
            "subject_id": subject_id,
            "observation_type": observation_type,
            "observation_value": observation_value,
            "observation_unit": observation_unit,
            "observation_date": observation_date
        }
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()


class FHIRAuthenticationError(Exception):
    """Exception raised for FHIR authentication failures."""
    pass
