"""
Query Orchestrator Service

Coordinates the entire query-to-dataset pipeline from natural language parsing
through dataset assembly and export.
Implements Requirements 1.1-1.4, 2.1-2.3, 3.1, 7.1, 10.1, 18.1-18.5.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import uuid as _uuid
from app.services.nl_parser import NLParserService
from app.services.query_planner import QueryPlanner, QueryPlan
from app.services.query_validator import QueryValidator
from app.services.schema_mapper import SchemaMapper
from app.services.cohort import CohortIdentifier
from app.services.dataset_assembly import DatasetAssemblyEngine, VariableRequest, MissingValueStrategy
from app.services.export_engine import ExportEngine
from app.models.metadata import ExportFormat, DatasetMetadata as DatasetMetadataModel, QueryProvenance as QueryProvenanceModel


logger = logging.getLogger(__name__)


class QueryStatus(str, Enum):
    """Status of query execution."""
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    TIMEOUT = "Timeout"


@dataclass
class QueryRequest:
    """Request to process a query."""
    user_id: str
    query_text: str
    data_source_ids: List[str]
    output_format: ExportFormat


@dataclass
class QueryResponse:
    """Response from query processing."""
    dataset_id: str
    status: QueryStatus
    row_count: int
    column_count: int
    download_urls: List[str]
    metadata: Dict[str, Any]
    error_message: Optional[str] = None


class QueryOrchestrator:
    """
    Query Orchestrator coordinates the query-to-dataset pipeline.
    
    Implements:
    - Requirements 1.1-1.4: Natural language query processing
    - Requirements 2.1-2.3: Query plan generation
    - Requirement 3.1: Query validation
    - Requirement 7.1: Dataset assembly
    - Requirement 10.1: Dataset export
    - Requirements 18.1-18.5: Timeout and resource limits
    """
    
    # Query execution timeout in seconds
    QUERY_TIMEOUT = 300  # 5 minutes
    
    # Confidence threshold for NL parsing
    CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(
        self,
        db: Session,
        nl_parser: NLParserService,
        export_dir: str = "exports"
    ):
        """
        Initialize query orchestrator.
        
        Args:
            db: Database session
            nl_parser: Natural language parser service
            export_dir: Directory for exported files
        """
        self.db = db
        self.nl_parser = nl_parser
        self.query_planner = QueryPlanner()
        self.query_validator = QueryValidator()
        self.schema_mapper = SchemaMapper()
        self.cohort_identifier = CohortIdentifier(db)
        self.dataset_assembly = DatasetAssemblyEngine(db)
        self.export_engine = ExportEngine(export_dir)
    
    def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Process a natural language query to generate a dataset.
        
        Args:
            request: Query request with user ID, query text, and options
        
        Returns:
            QueryResponse with dataset information or error
        
        Implements Requirements 1.1-1.4, 2.1-2.3, 3.1, 7.1, 10.1, 18.1-18.5
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Parse natural language query (Req 1.1, 1.2)
            logger.info(f"Parsing query: {request.query_text}")
            parsed_intent_obj = self.nl_parser.parse(request.query_text)
            
            # Convert to dict for compatibility with existing code
            parsed_intent = parsed_intent_obj.to_dict()
            
            # Step 2: Validate confidence threshold (Req 1.3, 1.4)
            confidence = parsed_intent.get("confidence", 0.0)
            if confidence < self.CONFIDENCE_THRESHOLD:
                return QueryResponse(
                    dataset_id="",
                    status=QueryStatus.FAILED,
                    row_count=0,
                    column_count=0,
                    download_urls=[],
                    metadata={},
                    error_message="Query ambiguous, please clarify. Try being more specific about the cohort criteria and variables you need."
                )
            
            # Check for required fields (Req 1.5)
            cohort_criteria = parsed_intent.get("cohort_criteria", [])
            variables = parsed_intent.get("variables", [])
            
            if not cohort_criteria and not variables:
                return QueryResponse(
                    dataset_id="",
                    status=QueryStatus.FAILED,
                    row_count=0,
                    column_count=0,
                    download_urls=[],
                    metadata={},
                    error_message="Query must include at least one cohort filter or variable request"
                )
            
            # Step 3: Load schema mappings for data sources
            schema_mappings = self._load_schema_mappings(request.data_source_ids)
            
            # Step 4: Create query plan (Req 2.1, 2.2, 2.3)
            logger.info("Creating query plan")
            query_plan = self.query_planner.create_plan(parsed_intent, schema_mappings)
            
            # Step 5: Validate query safety (Req 3.1)
            logger.info("Validating query safety")
            validation_result = self.query_validator.validate(query_plan)
            
            if not validation_result.is_safe:
                return QueryResponse(
                    dataset_id="",
                    status=QueryStatus.FAILED,
                    row_count=0,
                    column_count=0,
                    download_urls=[],
                    metadata={},
                    error_message=f"Query validation failed: {validation_result.reason}"
                )
            
            # Step 6: Check timeout (Req 18.1)
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > self.QUERY_TIMEOUT:
                return self._handle_timeout(query_plan)
            
            # Step 7: Identify cohort
            logger.info("Identifying cohort")
            cohort = self.cohort_identifier.identify_cohort(cohort_criteria)
            
            if not cohort:
                return QueryResponse(
                    dataset_id="",
                    status=QueryStatus.FAILED,
                    row_count=0,
                    column_count=0,
                    download_urls=[],
                    metadata={},
                    error_message="No subjects match the specified cohort criteria"
                )
            
            # Step 8: Convert variables to VariableRequest objects
            variable_requests = self._convert_variables(variables)
            
            # Step 9: Assemble dataset (Req 7.1)
            logger.info(f"Assembling dataset for {len(cohort)} subjects")
            dataset = self.dataset_assembly.assemble(
                cohort=cohort,
                variables=variable_requests,
                query_plan=query_plan,
                original_query=request.query_text,
                parsed_intent=parsed_intent,
                user_id=request.user_id
            )
            
            # Step 10: Check timeout again
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > self.QUERY_TIMEOUT:
                return self._handle_timeout(query_plan)
            
            # Step 11: Generate export files (Req 10.1)
            logger.info(f"Exporting dataset in {request.output_format} format")
            file_paths = self.export_engine.generate_files(dataset, request.output_format)
            download_urls = self.export_engine.get_download_urls(file_paths, dataset_id=dataset.dataset_id)

            # Step 12: Persist metadata + provenance so GET /dataset/{id} works
            execution_time_secs = (datetime.now() - start_time).total_seconds()
            db_meta = DatasetMetadataModel(
                dataset_id=dataset.dataset_id,
                created_by=request.user_id,
                row_count=dataset.metadata.row_count,
                column_count=dataset.metadata.column_count,
                data_sources=dataset.metadata.data_sources,
                export_format=request.output_format,
                file_paths=file_paths,
            )
            db_prov = QueryProvenanceModel(
                provenance_id=str(_uuid.uuid4()),
                dataset_id=dataset.dataset_id,
                original_query=request.query_text,
                parsed_intent=parsed_intent,
                sql_executed=dataset.query_provenance.sql_executed,
                execution_time=int(execution_time_secs * 1000),
                confidence_score=int(confidence * 100) if confidence else None,
            )
            self.db.add(db_meta)
            self.db.add(db_prov)
            self.db.commit()
            logger.info(f"Persisted DatasetMetadata {dataset.dataset_id}")

            # Step 13: Return success response
            return QueryResponse(
                dataset_id=dataset.dataset_id,
                status=QueryStatus.COMPLETED,
                row_count=dataset.metadata.row_count,
                column_count=dataset.metadata.column_count,
                download_urls=download_urls,
                metadata={
                    "created_at": dataset.metadata.created_at,
                    "data_sources": dataset.metadata.data_sources,
                    "execution_time": (datetime.now() - start_time).total_seconds(),
                    "confidence_score": confidence,
                    "missing_value_warnings": dataset.metadata.missing_value_warnings
                }
            )
        
        except Exception as e:
            logger.error(f"Query processing failed: {e}", exc_info=True)
            return QueryResponse(
                dataset_id="",
                status=QueryStatus.FAILED,
                row_count=0,
                column_count=0,
                download_urls=[],
                metadata={},
                error_message=f"Query processing failed: {str(e)}"
            )
    
    def _load_schema_mappings(
        self,
        data_source_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Load schema mappings for requested data sources.
        
        Args:
            data_source_ids: List of data source identifiers
        
        Returns:
            Dictionary of schema mappings
        """
        # In a full implementation, this would load from database
        # For now, return empty dict
        return {}
    
    def _convert_variables(
        self,
        variables: List[Dict[str, Any]]
    ) -> List[VariableRequest]:
        """
        Convert variable dictionaries to VariableRequest objects.
        
        Args:
            variables: List of variable specifications
        
        Returns:
            List of VariableRequest objects
        """
        variable_requests = []
        
        for var in variables:
            # Determine missing value strategy
            strategy_str = var.get("missing_strategy", "UseNull")
            try:
                strategy = MissingValueStrategy(strategy_str)
            except ValueError:
                strategy = MissingValueStrategy.USE_NULL
            
            variable_requests.append(VariableRequest(
                name=var.get("name", var.get("field", "unknown")),
                source=var.get("source", "subjects"),
                field=var.get("field", ""),
                aggregation=var.get("aggregation"),
                missing_strategy=strategy,
                default_value=var.get("default_value", "")
            ))
        
        return variable_requests
    
    def _handle_timeout(self, query_plan: QueryPlan) -> QueryResponse:
        """
        Handle query timeout.
        
        Implements Requirements 18.1, 18.2, 18.3, 18.5
        """
        # Log query plan and estimated rows (Req 18.3)
        logger.warning(
            f"Query timeout exceeded. Estimated rows: {query_plan.estimated_rows}, "
            f"Data sources: {query_plan.data_sources}"
        )
        
        # Suggest optimization (Req 18.5)
        suggestions = []
        if query_plan.estimated_rows > 100000:
            suggestions.append("Consider adding more specific filters to reduce the cohort size")
        if len(query_plan.data_sources) > 3:
            suggestions.append("Try reducing the number of data sources or variables")
        
        suggestion_text = " ".join(suggestions) if suggestions else "Try simplifying your query"
        
        return QueryResponse(
            dataset_id="",
            status=QueryStatus.TIMEOUT,
            row_count=0,
            column_count=0,
            download_urls=[],
            metadata={
                "estimated_rows": query_plan.estimated_rows,
                "data_sources": query_plan.data_sources
            },
            error_message=f"Query timeout exceeded (5 minutes). {suggestion_text}"
        )
