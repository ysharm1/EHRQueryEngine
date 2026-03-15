"""
Error Handler Service

Centralized error handling with recovery suggestions and retry logic.
Implements Requirements 16.1-16.7.
"""

from typing import Optional, Callable, Any
import logging
import time
from functools import wraps
from app.services.fhir_connector import FHIRAuthenticationError


logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Centralized error handling service.
    
    Implements:
    - Requirement 16.1: Handle FHIR authentication errors
    - Requirement 16.2: Handle query timeout errors
    - Requirement 16.3: Handle schema mapping failures
    - Requirement 16.4: Handle data validation failures
    - Requirement 16.5: Log all errors
    - Requirement 16.6: Provide recovery suggestions
    - Requirement 16.7: Database retry logic
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    BACKOFF_FACTOR = 2.0  # exponential backoff
    
    @staticmethod
    def handle_fhir_auth_error(error: FHIRAuthenticationError) -> dict:
        """
        Handle FHIR authentication errors.
        
        Implements Requirement 16.1
        """
        logger.error(f"FHIR authentication failed: {error}")
        
        return {
            "error_type": "FHIRAuthenticationError",
            "message": "FHIR authentication failed. Please check your credentials.",
            "details": str(error),
            "recovery_suggestions": [
                "Verify FHIR endpoint URL is correct",
                "Check that authentication token is valid and not expired",
                "Ensure you have proper permissions to access the FHIR server",
                "Contact your system administrator if the issue persists"
            ]
        }
    
    @staticmethod
    def handle_timeout_error(
        query_plan: Optional[dict] = None,
        estimated_rows: Optional[int] = None
    ) -> dict:
        """
        Handle query timeout errors.
        
        Implements Requirement 16.2
        """
        logger.error(f"Query timeout. Estimated rows: {estimated_rows}")
        
        suggestions = [
            "Add more specific filters to reduce the cohort size",
            "Reduce the number of variables requested",
            "Break the query into smaller, more focused queries"
        ]
        
        if estimated_rows and estimated_rows > 100000:
            suggestions.insert(0, f"Your query would return ~{estimated_rows:,} rows, which is very large")
        
        return {
            "error_type": "QueryTimeout",
            "message": "Query execution exceeded the 5-minute timeout limit",
            "details": {
                "estimated_rows": estimated_rows,
                "query_plan": query_plan
            },
            "recovery_suggestions": suggestions
        }
    
    @staticmethod
    def handle_schema_mapping_error(
        unmapped_fields: list,
        source_schema: str,
        target_schema: str
    ) -> dict:
        """
        Handle schema mapping failures.
        
        Implements Requirement 16.3
        """
        logger.error(
            f"Schema mapping failed. Unmapped fields: {unmapped_fields}"
        )
        
        return {
            "error_type": "SchemaMappingError",
            "message": "Failed to map source schema to canonical schema",
            "details": {
                "unmapped_fields": unmapped_fields,
                "source_schema": source_schema,
                "target_schema": target_schema
            },
            "recovery_suggestions": [
                "Review the unmapped fields and provide manual mappings",
                "Check if field names in source data match expected format",
                "Verify that source schema definition is correct",
                "Contact support to create a custom schema mapping"
            ]
        }
    
    @staticmethod
    def handle_validation_error(
        validation_errors: list,
        record_count: int,
        failed_count: int
    ) -> dict:
        """
        Handle data validation failures.
        
        Implements Requirement 16.4
        """
        logger.error(
            f"Data validation failed. {failed_count}/{record_count} records failed"
        )
        
        return {
            "error_type": "DataValidationError",
            "message": f"{failed_count} out of {record_count} records failed validation",
            "details": {
                "validation_errors": validation_errors[:10],  # First 10 errors
                "total_errors": len(validation_errors),
                "failed_count": failed_count,
                "record_count": record_count
            },
            "recovery_suggestions": [
                "Review the validation error report for specific issues",
                "Fix data quality issues in the source system",
                "Adjust validation rules if they are too strict",
                "Contact data quality team for assistance"
            ]
        }
    
    @staticmethod
    def log_error(
        error_type: str,
        component: str,
        error_message: str,
        details: Optional[dict] = None
    ):
        """
        Log error with timestamp, component, and details.
        
        Implements Requirement 16.5
        """
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "component": component,
            "message": error_message,
            "details": details or {}
        }
        
        logger.error(f"Error logged: {log_entry}")
    
    @classmethod
    def with_retry(
        cls,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        backoff_factor: Optional[float] = None
    ):
        """
        Decorator for database operations with retry logic.
        
        Implements Requirement 16.7
        """
        max_retries = max_retries or cls.MAX_RETRIES
        retry_delay = retry_delay or cls.RETRY_DELAY
        backoff_factor = backoff_factor or cls.BACKOFF_FACTOR
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                delay = retry_delay
                
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    
                    except Exception as e:
                        last_exception = e
                        
                        # Check if error is retryable
                        if not cls._is_retryable_error(e):
                            raise
                        
                        # Log retry attempt
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        
                        # Wait before retry
                        if attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= backoff_factor
                
                # All retries exhausted
                logger.error(
                    f"All {max_retries} retry attempts failed for {func.__name__}"
                )
                raise last_exception
            
            return wrapper
        return decorator
    
    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Retryable errors include:
        - Database connection errors
        - Temporary network errors
        - Timeout errors (for certain operations)
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Database connection errors
        if "connection" in error_message or "timeout" in error_message:
            return True
        
        # Specific retryable error types
        retryable_types = [
            "OperationalError",  # SQLAlchemy database errors
            "TimeoutError",
            "ConnectionError",
            "RequestError"  # httpx network errors
        ]
        
        return error_type in retryable_types
    
    @staticmethod
    def get_recovery_suggestion(error: Exception) -> str:
        """
        Get recovery suggestion for an error.
        
        Implements Requirement 16.6
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # FHIR authentication errors
        if isinstance(error, FHIRAuthenticationError):
            return "Check FHIR credentials and endpoint configuration"
        
        # Database errors
        if "connection" in error_message:
            return "Database connection failed. Check database server status and network connectivity"
        
        # Validation errors
        if "validation" in error_message:
            return "Data validation failed. Review validation errors and fix data quality issues"
        
        # Timeout errors
        if "timeout" in error_message:
            return "Operation timed out. Try reducing query scope or increasing timeout limit"
        
        # Schema mapping errors
        if "schema" in error_message or "mapping" in error_message:
            return "Schema mapping failed. Verify field mappings and source data format"
        
        # Generic suggestion
        return "An error occurred. Check logs for details and contact support if issue persists"
