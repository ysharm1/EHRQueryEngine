"""
Error Handler Service

Centralized error handling with recovery suggestions and retry logic.
Implements Requirements 16.2-16.7.
"""

from typing import Optional, Callable, Any
import logging
import time
from functools import wraps


logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling service."""

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    BACKOFF_FACTOR = 2.0

    @staticmethod
    def handle_timeout_error(
        query_plan: Optional[dict] = None,
        estimated_rows: Optional[int] = None
    ) -> dict:
        logger.error(f"Query timeout. Estimated rows: {estimated_rows}")
        suggestions = [
            "Add more specific filters to reduce the cohort size",
            "Reduce the number of variables requested",
            "Break the query into smaller, more focused queries",
        ]
        if estimated_rows and estimated_rows > 100000:
            suggestions.insert(0, f"Your query would return ~{estimated_rows:,} rows, which is very large")
        return {
            "error_type": "QueryTimeout",
            "message": "Query execution exceeded the 5-minute timeout limit",
            "details": {"estimated_rows": estimated_rows, "query_plan": query_plan},
            "recovery_suggestions": suggestions,
        }

    @staticmethod
    def handle_schema_mapping_error(unmapped_fields: list, source_schema: str, target_schema: str) -> dict:
        logger.error(f"Schema mapping failed. Unmapped fields: {unmapped_fields}")
        return {
            "error_type": "SchemaMappingError",
            "message": "Failed to map source schema to canonical schema",
            "details": {"unmapped_fields": unmapped_fields, "source_schema": source_schema, "target_schema": target_schema},
            "recovery_suggestions": [
                "Review the unmapped fields and provide manual mappings",
                "Check if field names in source data match expected format",
            ],
        }

    @staticmethod
    def handle_validation_error(validation_errors: list, record_count: int, failed_count: int) -> dict:
        logger.error(f"Data validation failed. {failed_count}/{record_count} records failed")
        return {
            "error_type": "DataValidationError",
            "message": f"{failed_count} out of {record_count} records failed validation",
            "details": {"validation_errors": validation_errors[:10], "total_errors": len(validation_errors)},
            "recovery_suggestions": ["Review the validation error report for specific issues"],
        }

    @staticmethod
    def log_error(error_type: str, component: str, error_message: str, details: Optional[dict] = None):
        from datetime import datetime
        logger.error({
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "component": component,
            "message": error_message,
            "details": details or {},
        })

    @classmethod
    def with_retry(cls, max_retries: Optional[int] = None, retry_delay: Optional[float] = None, backoff_factor: Optional[float] = None):
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
                        if not cls._is_retryable_error(e):
                            raise
                        logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...")
                        if attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= backoff_factor
                raise last_exception
            return wrapper
        return decorator

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        msg = str(error).lower()
        if "connection" in msg or "timeout" in msg:
            return True
        return type(error).__name__ in ["OperationalError", "TimeoutError", "ConnectionError", "RequestError"]

    @staticmethod
    def get_recovery_suggestion(error: Exception) -> str:
        msg = str(error).lower()
        if "connection" in msg:
            return "Database connection failed. Check database server status."
        if "validation" in msg:
            return "Data validation failed. Review validation errors."
        if "timeout" in msg:
            return "Operation timed out. Try reducing query scope."
        if "schema" in msg or "mapping" in msg:
            return "Schema mapping failed. Verify field mappings."
        return "An error occurred. Check logs for details."
