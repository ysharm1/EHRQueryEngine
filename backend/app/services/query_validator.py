"""
Query Validator Service

Validates query plans for safety, ensuring read-only operations and resource limits.
Implements Requirements 3.1-3.7, 18.4.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import re
from app.services.query_planner import QueryPlan, QueryStep, QueryOperationType


@dataclass
class ValidationResult:
    """Result of query validation."""
    is_safe: bool
    reason: str = ""
    
    @classmethod
    def safe(cls) -> "ValidationResult":
        """Create a safe validation result."""
        return cls(is_safe=True, reason="")
    
    @classmethod
    def unsafe(cls, reason: str) -> "ValidationResult":
        """Create an unsafe validation result."""
        return cls(is_safe=False, reason=reason)


class QueryValidator:
    """
    Query Validator service that ensures query safety.
    
    Implements:
    - Requirement 3.1: Verify all operations are read-only
    - Requirement 3.2: Reject data modification operations
    - Requirement 3.3: Detect and reject recursive queries
    - Requirement 3.4: Reject queries exceeding 1M row limit
    - Requirement 3.5: Verify all referenced tables exist
    - Requirement 3.6: Return validation result with isSafe flag
    - Requirement 3.7: Return descriptive error messages
    - Requirement 18.4: Enforce row count limits
    """
    
    # Maximum allowed rows in result set
    MAX_ROWS = 1_000_000
    
    # Valid table names in the canonical schema
    VALID_TABLES = {
        "subjects",
        "procedures",
        "observations",
        "imaging_features",
        "imaging",  # alias used in variable requests
    }
    
    # SQL keywords that indicate data modification
    MODIFICATION_KEYWORDS = {
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
        "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE"
    }
    
    def __init__(self):
        """Initialize the query validator."""
        pass
    
    def validate(self, plan: QueryPlan) -> ValidationResult:
        """
        Validate a query plan for safety.
        
        Args:
            plan: QueryPlan to validate
        
        Returns:
            ValidationResult with is_safe flag and reason
        
        Implements Requirements 3.1-3.7, 18.4
        """
        # Check 1: Verify all operations are read-only (Req 3.1, 3.2)
        for step in plan.steps:
            if not self._is_read_only_operation(step):
                return ValidationResult.unsafe(
                    f"Data modification operation detected in step {step.step_id}"
                )
        
        # Check 2: Detect recursive queries (Req 3.3)
        if self._has_recursion(plan):
            return ValidationResult.unsafe("Recursive queries not allowed")
        
        # Check 3: Verify estimated row count within limits (Req 3.4, 18.4)
        if plan.estimated_rows > self.MAX_ROWS:
            return ValidationResult.unsafe(
                f"Result set too large ({plan.estimated_rows:,} rows, max {self.MAX_ROWS:,})"
            )
        
        # Check 4: Verify all referenced tables exist (Req 3.5)
        invalid_tables = self._check_table_existence(plan)
        if invalid_tables:
            return ValidationResult.unsafe(
                f"Table(s) not found: {', '.join(invalid_tables)}"
            )
        
        # Check 5: Validate SQL draft for modification keywords
        if self._contains_modification_keywords(plan.sql_draft):
            return ValidationResult.unsafe(
                "SQL contains data modification keywords"
            )
        
        # All checks passed (Req 3.6)
        return ValidationResult.safe()
    
    def _is_read_only_operation(self, step: QueryStep) -> bool:
        """
        Check if a query step contains only read-only operations.
        
        Implements Requirements 3.1, 3.2
        """
        # All supported operation types are read-only
        allowed_operations = {
            QueryOperationType.FILTER,
            QueryOperationType.JOIN,
            QueryOperationType.AGGREGATE,
            QueryOperationType.TRANSFORM
        }
        
        return step.operation.operation_type in allowed_operations
    
    def _has_recursion(self, plan: QueryPlan) -> bool:
        """
        Detect recursive queries by checking for circular dependencies.
        
        Implements Requirement 3.3
        """
        # Build dependency graph
        dependencies: Dict[str, List[str]] = {}
        
        for step in plan.steps:
            output = step.output_table
            inputs = step.input_tables
            dependencies[output] = inputs
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(table: str) -> bool:
            """DFS to detect cycles."""
            if table in rec_stack:
                return True
            if table in visited:
                return False
            
            visited.add(table)
            rec_stack.add(table)
            
            # Check dependencies
            for dep in dependencies.get(table, []):
                if dep in dependencies and has_cycle(dep):
                    return True
            
            rec_stack.remove(table)
            return False
        
        # Check all tables for cycles
        for table in dependencies:
            if table not in visited:
                if has_cycle(table):
                    return True
        
        return False
    
    def _check_table_existence(self, plan: QueryPlan) -> List[str]:
        """
        Verify all referenced tables exist in the database.
        
        Returns list of invalid table names.
        Implements Requirement 3.5
        """
        invalid_tables = []
        
        # Extract all table names from steps
        referenced_tables = set()
        for step in plan.steps:
            referenced_tables.update(step.input_tables)
        
        # Also check data sources
        referenced_tables.update(plan.data_sources)
        
        # Filter out intermediate tables (cohort_step_*, variable_step_*)
        base_tables = {
            table for table in referenced_tables
            if not table.startswith("cohort_step_") and not table.startswith("variable_step_")
        }
        
        # Check against valid tables
        for table in base_tables:
            if table not in self.VALID_TABLES:
                invalid_tables.append(table)
        
        return invalid_tables
    
    def _contains_modification_keywords(self, sql: str) -> bool:
        """
        Check if SQL contains data modification keywords.
        
        Implements Requirement 3.2
        """
        # Convert to uppercase for case-insensitive matching
        sql_upper = sql.upper()
        
        # Check for modification keywords
        for keyword in self.MODIFICATION_KEYWORDS:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                return True
        
        return False
    
    def validate_query_safety(self, plan: QueryPlan) -> ValidationResult:
        """
        Alias for validate() method for compatibility.
        
        Implements Requirements 3.1-3.7
        """
        return self.validate(plan)
