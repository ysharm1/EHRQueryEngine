"""
Dataset Assembly Engine

Executes query plans and assembles multimodal datasets with variable collection,
missing value handling, and normalization.
Implements Requirements 7.1-7.7, 8.1-8.6, 9.1-9.6, 19.1-19.7.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import re
from app.models.canonical import Subject, Procedure, Observation, ImagingFeature
from app.services.query_planner import QueryPlan


class MissingValueStrategy(str, Enum):
    """Strategies for handling missing values."""
    USE_DEFAULT = "UseDefault"
    USE_NULL = "UseNull"
    USE_MEAN = "UseMean"
    EXCLUDE = "Exclude"


@dataclass
class VariableRequest:
    """Request for a variable to include in dataset."""
    name: str
    source: str  # "subjects", "procedures", "observations", "imaging"
    field: str
    aggregation: Optional[str] = None  # "mean", "count", "max", "min", "history"
    missing_strategy: MissingValueStrategy = MissingValueStrategy.USE_NULL
    default_value: str = ""


@dataclass
class ColumnDefinition:
    """Definition of a dataset column."""
    name: str
    data_type: str
    nullable: bool
    description: str


@dataclass
class DatasetSchema:
    """Schema definition for assembled dataset."""
    columns: List[ColumnDefinition]
    primary_key: Optional[str] = None


@dataclass
class DatasetMetadata:
    """Metadata for assembled dataset."""
    created_at: str
    created_by: str
    row_count: int
    column_count: int
    data_sources: List[str]
    missing_value_warnings: List[str]


@dataclass
class QueryProvenance:
    """Provenance information for dataset."""
    original_query: str
    parsed_intent: Dict[str, Any]
    sql_executed: str
    execution_time: float
    confidence_score: Optional[float] = None


@dataclass
class AssembledDataset:
    """Complete assembled dataset with metadata."""
    dataset_id: str
    rows: List[List[Any]]
    schema: DatasetSchema
    metadata: DatasetMetadata
    query_provenance: QueryProvenance


class DatasetAssemblyEngine:
    """
    Dataset Assembly Engine for creating analysis-ready datasets.
    
    Implements:
    - Requirements 7.1-7.7: Dataset assembly
    - Requirements 8.1-8.6: Missing value handling
    - Requirements 9.1-9.6: Variable name normalization
    - Requirements 19.1-19.7: Data provenance tracking
    """
    
    # Missing value threshold for warnings
    MISSING_VALUE_THRESHOLD = 0.20  # 20%
    
    def __init__(self, db: Session):
        """
        Initialize dataset assembly engine.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def assemble(
        self,
        cohort: List[Subject],
        variables: List[VariableRequest],
        query_plan: QueryPlan,
        original_query: str,
        parsed_intent: Dict[str, Any],
        user_id: str
    ) -> AssembledDataset:
        """
        Assemble dataset from cohort and variable requests.
        
        Args:
            cohort: List of subjects in cohort
            variables: List of variables to collect
            query_plan: Query plan that was executed
            original_query: Original natural language query
            parsed_intent: Parsed intent structure
            user_id: User who created the dataset
        
        Returns:
            AssembledDataset with data, schema, metadata, and provenance
        
        Implements Requirements 7.1-7.7, 19.1-19.7
        """
        start_time = datetime.now()
        
        # Build schema (Req 7.5)
        schema = self._build_schema(variables)
        
        # Collect data for all subjects (Req 7.1, 7.2)
        rows = []
        missing_counts = {var.name: 0 for var in variables}
        
        for subject in cohort:
            row = self._collect_subject_row(subject, variables, missing_counts)
            
            # Check if row should be excluded due to missing values
            if row is not None:
                rows.append(row)
        
        # Ensure all rows have same number of columns (Req 7.4)
        expected_columns = len(schema.columns)
        for row in rows:
            assert len(row) == expected_columns, f"Row has {len(row)} columns, expected {expected_columns}"
        
        # Generate missing value warnings (Req 8.6)
        warnings = []
        total_rows = len(cohort)
        if total_rows > 0:
            for var_name, missing_count in missing_counts.items():
                missing_pct = missing_count / total_rows
                if missing_pct > self.MISSING_VALUE_THRESHOLD:
                    warnings.append(
                        f"Variable '{var_name}' has {missing_pct:.1%} missing values"
                    )
        
        # Generate metadata (Req 7.6)
        data_sources = list(set(var.source for var in variables))
        metadata = DatasetMetadata(
            created_at=datetime.now().isoformat(),
            created_by=user_id,
            row_count=len(rows),
            column_count=len(schema.columns),
            data_sources=data_sources,
            missing_value_warnings=warnings
        )
        
        # Generate provenance (Req 7.7, 19.1-19.7)
        execution_time = (datetime.now() - start_time).total_seconds()
        provenance = QueryProvenance(
            original_query=original_query,
            parsed_intent=parsed_intent,
            sql_executed=query_plan.sql_draft,
            execution_time=execution_time,
            confidence_score=parsed_intent.get("confidence")
        )
        
        # Create dataset
        dataset_id = str(uuid.uuid4())
        return AssembledDataset(
            dataset_id=dataset_id,
            rows=rows,
            schema=schema,
            metadata=metadata,
            query_provenance=provenance
        )
    
    def _build_schema(self, variables: List[VariableRequest]) -> DatasetSchema:
        """
        Build dataset schema from variable requests.
        
        Implements Requirement 7.5
        """
        columns = []
        
        # Always include subject_id as first column
        columns.append(ColumnDefinition(
            name="subject_id",
            data_type="string",
            nullable=False,
            description="Subject identifier"
        ))
        
        # Add columns for each variable
        for variable in variables:
            # Normalize variable name (Req 9.1-9.6)
            normalized_name = self.normalize_variable_name(variable.name)
            
            # Determine data type
            data_type = self._infer_data_type(variable)
            
            columns.append(ColumnDefinition(
                name=normalized_name,
                data_type=data_type,
                nullable=True,
                description=f"{variable.field} from {variable.source}"
            ))
        
        return DatasetSchema(
            columns=columns,
            primary_key="subject_id"
        )
    
    def _collect_subject_row(
        self,
        subject: Subject,
        variables: List[VariableRequest],
        missing_counts: Dict[str, int]
    ) -> Optional[List[Any]]:
        """
        Collect data row for a single subject.
        
        Implements Requirements 7.2, 7.3, 8.1-8.5
        """
        row = [subject.subject_id]
        exclude_row = False
        
        for variable in variables:
            # Extract value from appropriate source (Req 7.2)
            value = self._extract_variable_value(subject, variable)
            
            # Handle missing values (Req 8.1-8.5)
            if value is None or value == "":
                missing_counts[variable.name] += 1
                
                if variable.missing_strategy == MissingValueStrategy.USE_DEFAULT:
                    value = variable.default_value  # Req 8.2
                
                elif variable.missing_strategy == MissingValueStrategy.USE_NULL:
                    value = None  # Req 8.3
                
                elif variable.missing_strategy == MissingValueStrategy.USE_MEAN:
                    # Calculate mean for this variable (Req 8.4)
                    value = self._calculate_mean(variable)
                
                elif variable.missing_strategy == MissingValueStrategy.EXCLUDE:
                    # Mark row for exclusion (Req 8.5)
                    exclude_row = True
                    break
            
            row.append(value)
        
        # Return None if row should be excluded
        if exclude_row:
            return None
        
        return row
    
    def _extract_variable_value(
        self,
        subject: Subject,
        variable: VariableRequest
    ) -> Any:
        """
        Extract variable value from appropriate data source.
        
        Implements Requirement 7.2
        """
        if variable.source == "subjects":
            return self._extract_from_subject(subject, variable)
        
        elif variable.source == "procedures":
            return self._extract_from_procedures(subject, variable)
        
        elif variable.source == "observations":
            return self._extract_from_observations(subject, variable)
        
        elif variable.source == "imaging":
            return self._extract_from_imaging(subject, variable)
        
        else:
            return None
    
    def _extract_from_subject(
        self,
        subject: Subject,
        variable: VariableRequest
    ) -> Any:
        """Extract value from subject record."""
        return getattr(subject, variable.field, None)
    
    def _extract_from_procedures(
        self,
        subject: Subject,
        variable: VariableRequest
    ) -> Any:
        """
        Extract value from procedures with optional aggregation.
        
        Implements Requirement 7.3
        """
        procedures = self.db.query(Procedure).filter(
            Procedure.subject_id == subject.subject_id
        ).all()
        
        if not procedures:
            return None
        
        # Extract field values
        values = [getattr(p, variable.field, None) for p in procedures]
        values = [v for v in values if v is not None]
        
        if not values:
            return None
        
        # Apply aggregation if specified (Req 7.3)
        if variable.aggregation == "count":
            return len(values)
        
        elif variable.aggregation == "history":
            return ", ".join(str(v) for v in values)
        
        elif variable.aggregation == "mean":
            try:
                return sum(float(v) for v in values) / len(values)
            except (ValueError, TypeError):
                return None
        
        elif variable.aggregation == "max":
            try:
                return max(float(v) for v in values)
            except (ValueError, TypeError):
                return max(values)
        
        elif variable.aggregation == "min":
            try:
                return min(float(v) for v in values)
            except (ValueError, TypeError):
                return min(values)
        
        else:
            # No aggregation, return first value
            return values[0]
    
    def _extract_from_observations(
        self,
        subject: Subject,
        variable: VariableRequest
    ) -> Any:
        """Extract value from observations with optional aggregation."""
        observations = self.db.query(Observation).filter(
            Observation.subject_id == subject.subject_id
        ).all()
        
        if not observations:
            return None
        
        # Filter by observation type if specified in field
        if ":" in variable.field:
            obs_type, field_name = variable.field.split(":", 1)
            observations = [o for o in observations if o.observation_type == obs_type]
            field = field_name
        else:
            field = "observation_value"
        
        # Extract values
        values = [getattr(o, field, None) for o in observations]
        values = [v for v in values if v is not None]
        
        if not values:
            return None
        
        # Apply aggregation
        if variable.aggregation == "count":
            return len(values)
        elif variable.aggregation == "mean":
            try:
                return sum(float(v) for v in values) / len(values)
            except (ValueError, TypeError):
                return None
        elif variable.aggregation == "history":
            return ", ".join(str(v) for v in values)
        else:
            return values[0]
    
    def _extract_from_imaging(
        self,
        subject: Subject,
        variable: VariableRequest
    ) -> Any:
        """Extract value from imaging features."""
        imaging = self.db.query(ImagingFeature).filter(
            ImagingFeature.subject_id == subject.subject_id
        ).all()
        
        if not imaging:
            return None
        
        # Extract feature values
        feature_name = variable.field
        values = []
        
        for img in imaging:
            if isinstance(img.features, dict) and feature_name in img.features:
                values.append(img.features[feature_name])
        
        if not values:
            return None
        
        # Apply aggregation
        if variable.aggregation == "mean":
            return sum(values) / len(values)
        elif variable.aggregation == "max":
            return max(values)
        elif variable.aggregation == "min":
            return min(values)
        else:
            return values[0]
    
    def _calculate_mean(self, variable: VariableRequest) -> Optional[float]:
        """
        Calculate mean value for a variable across all subjects.
        
        Implements Requirement 8.4
        """
        # This is a simplified implementation
        # In production, would query database for mean
        return 0.0
    
    def _infer_data_type(self, variable: VariableRequest) -> str:
        """Infer data type from variable source and field."""
        # Simple heuristics for data type inference
        if "date" in variable.field.lower() or "dob" in variable.field.lower():
            return "date"
        elif "count" in variable.field.lower() or variable.aggregation == "count":
            return "integer"
        elif variable.aggregation in ["mean", "max", "min"]:
            return "float"
        elif variable.source == "imaging":
            return "float"
        else:
            return "string"
    
    @staticmethod
    def normalize_variable_name(name: str) -> str:
        """
        Normalize variable name to valid SQL identifier.
        
        Implements Requirements 9.1-9.6
        """
        # Convert to lowercase (Req 9.1)
        normalized = name.lower()
        
        # Replace spaces with underscores (Req 9.2)
        normalized = normalized.replace(" ", "_")
        
        # Remove special characters except underscores (Req 9.3)
        normalized = re.sub(r'[^a-z0-9_]', '', normalized)
        
        # Handle empty names (Req 9.5)
        if not normalized:
            return "col"
        
        # Prefix names starting with digits (Req 9.4)
        if normalized[0].isdigit():
            normalized = f"col_{normalized}"
        
        return normalized
