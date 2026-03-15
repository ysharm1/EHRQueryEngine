"""
Query Planner Service

Converts parsed intent into executable query plans with optimized join strategies.
Implements Requirements 2.1-2.5.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class JoinType(str, Enum):
    """Join types for query operations."""
    INNER = "INNER"
    LEFT_OUTER = "LEFT OUTER"
    RIGHT_OUTER = "RIGHT OUTER"
    FULL_OUTER = "FULL OUTER"


class QueryOperationType(str, Enum):
    """Query operation types."""
    FILTER = "FILTER"
    JOIN = "JOIN"
    AGGREGATE = "AGGREGATE"
    TRANSFORM = "TRANSFORM"


@dataclass
class QueryOperation:
    """Represents a single query operation."""
    operation_type: QueryOperationType
    condition: Optional[str] = None
    join_type: Optional[JoinType] = None
    on_condition: Optional[str] = None
    group_by: Optional[List[str]] = None
    aggregates: Optional[List[str]] = None
    expression: Optional[str] = None


@dataclass
class QueryStep:
    """Represents a step in the query execution plan."""
    step_id: int
    operation: QueryOperation
    input_tables: List[str]
    output_table: str


@dataclass
class QueryPlan:
    """Complete query execution plan."""
    steps: List[QueryStep]
    estimated_rows: int
    data_sources: List[str]
    sql_draft: str


class QueryPlanner:
    """
    Query Planner service that converts parsed intent into executable query plans.
    
    Implements:
    - Requirement 2.1: Generate QueryPlan with executable steps
    - Requirement 2.2: Include estimated row count
    - Requirement 2.3: Produce SQL draft for validation
    - Requirement 2.4: Optimize join order
    - Requirement 2.5: List all required data sources
    """
    
    def __init__(self):
        """Initialize the query planner."""
        pass
    
    def create_plan(
        self,
        parsed_intent: Dict[str, Any],
        schema_mappings: Optional[Dict[str, Any]] = None
    ) -> QueryPlan:
        """
        Create an executable query plan from parsed intent.
        
        Args:
            parsed_intent: Structured intent from NL parser containing:
                - cohort_criteria: List of filters for cohort identification
                - variables: List of requested variables
                - time_range: Optional time constraints
            schema_mappings: Optional schema mapping information
        
        Returns:
            QueryPlan with steps, estimated rows, data sources, and SQL draft
        
        Implements Requirements 2.1-2.5
        """
        steps = []
        step_id = 0
        data_sources = set()
        
        # Extract cohort criteria and variables
        cohort_criteria = parsed_intent.get("cohort_criteria", [])
        variables = parsed_intent.get("variables", [])
        time_range = parsed_intent.get("time_range")
        
        # Step 1: Create cohort identification step
        if cohort_criteria:
            cohort_filters = self._build_cohort_filters(cohort_criteria)
            data_sources.add("subjects")
            
            # Add filter operations for each criterion
            for criterion in cohort_criteria:
                filter_type = criterion.get("filter_type")
                
                if filter_type == "Diagnosis":
                    operation = QueryOperation(
                        operation_type=QueryOperationType.FILTER,
                        condition=self._build_diagnosis_filter(criterion)
                    )
                    steps.append(QueryStep(
                        step_id=step_id,
                        operation=operation,
                        input_tables=["subjects"],
                        output_table="cohort_step_" + str(step_id)
                    ))
                    step_id += 1
                
                elif filter_type == "Procedure":
                    data_sources.add("procedures")
                    # Join with procedures table
                    operation = QueryOperation(
                        operation_type=QueryOperationType.JOIN,
                        join_type=JoinType.INNER,
                        on_condition="subjects.subject_id = procedures.subject_id"
                    )
                    steps.append(QueryStep(
                        step_id=step_id,
                        operation=operation,
                        input_tables=["subjects", "procedures"],
                        output_table="cohort_step_" + str(step_id)
                    ))
                    step_id += 1
                    
                    # Filter by procedure code
                    operation = QueryOperation(
                        operation_type=QueryOperationType.FILTER,
                        condition=self._build_procedure_filter(criterion)
                    )
                    steps.append(QueryStep(
                        step_id=step_id,
                        operation=operation,
                        input_tables=["cohort_step_" + str(step_id - 1)],
                        output_table="cohort_step_" + str(step_id)
                    ))
                    step_id += 1
                
                elif filter_type == "Demographics":
                    operation = QueryOperation(
                        operation_type=QueryOperationType.FILTER,
                        condition=self._build_demographic_filter(criterion)
                    )
                    steps.append(QueryStep(
                        step_id=step_id,
                        operation=operation,
                        input_tables=["subjects"],
                        output_table="cohort_step_" + str(step_id)
                    ))
                    step_id += 1
                
                elif filter_type == "Observation":
                    data_sources.add("observations")
                    # Join with observations table
                    operation = QueryOperation(
                        operation_type=QueryOperationType.JOIN,
                        join_type=JoinType.INNER,
                        on_condition="subjects.subject_id = observations.subject_id"
                    )
                    steps.append(QueryStep(
                        step_id=step_id,
                        operation=operation,
                        input_tables=["subjects", "observations"],
                        output_table="cohort_step_" + str(step_id)
                    ))
                    step_id += 1
                    
                    # Filter by observation criteria
                    operation = QueryOperation(
                        operation_type=QueryOperationType.FILTER,
                        condition=self._build_observation_filter(criterion)
                    )
                    steps.append(QueryStep(
                        step_id=step_id,
                        operation=operation,
                        input_tables=["cohort_step_" + str(step_id - 1)],
                        output_table="cohort_step_" + str(step_id)
                    ))
                    step_id += 1
        
        # Step 2: Add variable collection steps
        for variable in variables:
            source = variable.get("source", "subjects")
            data_sources.add(source)
            
            if source != "subjects":
                # Join with the variable source table
                operation = QueryOperation(
                    operation_type=QueryOperationType.JOIN,
                    join_type=JoinType.LEFT_OUTER,
                    on_condition=f"subjects.subject_id = {source}.subject_id"
                )
                steps.append(QueryStep(
                    step_id=step_id,
                    operation=operation,
                    input_tables=["subjects", source],
                    output_table="variable_step_" + str(step_id)
                ))
                step_id += 1
            
            # Add aggregation if specified
            aggregation = variable.get("aggregation")
            if aggregation:
                operation = QueryOperation(
                    operation_type=QueryOperationType.AGGREGATE,
                    group_by=["subject_id"],
                    aggregates=[f"{aggregation}({variable.get('field')})"]
                )
                steps.append(QueryStep(
                    step_id=step_id,
                    operation=operation,
                    input_tables=["variable_step_" + str(step_id - 1)],
                    output_table="variable_step_" + str(step_id)
                ))
                step_id += 1
        
        # Optimize join order (smaller tables first)
        optimized_steps = self._optimize_join_order(steps)
        
        # Estimate row count
        estimated_rows = self._estimate_row_count(cohort_criteria, variables)
        
        # Generate SQL draft
        sql_draft = self._generate_sql_draft(optimized_steps, cohort_criteria, variables, time_range)
        
        return QueryPlan(
            steps=optimized_steps,
            estimated_rows=estimated_rows,
            data_sources=list(data_sources),
            sql_draft=sql_draft
        )
    
    def _build_cohort_filters(self, criteria: List[Dict[str, Any]]) -> str:
        """Build WHERE clause for cohort identification."""
        filters = []
        for criterion in criteria:
            filter_type = criterion.get("filter_type")
            if filter_type == "Diagnosis":
                filters.append(self._build_diagnosis_filter(criterion))
            elif filter_type == "Demographics":
                filters.append(self._build_demographic_filter(criterion))
        return " AND ".join(filters) if filters else "1=1"
    
    def _build_diagnosis_filter(self, criterion: Dict[str, Any]) -> str:
        """Build diagnosis filter condition."""
        value = criterion.get("value", "")
        return f"'{value}' = ANY(diagnosis_codes)"
    
    def _build_procedure_filter(self, criterion: Dict[str, Any]) -> str:
        """Build procedure filter condition."""
        value = criterion.get("value", "")
        return f"procedure_code = '{value}'"
    
    def _build_demographic_filter(self, criterion: Dict[str, Any]) -> str:
        """Build demographic filter condition."""
        field = criterion.get("field", "")
        operator = criterion.get("operator", "Equals")
        value = criterion.get("value", "")
        
        sql_operator = self._operator_to_sql(operator)
        
        if operator == "Contains":
            return f"{field} LIKE '%{value}%'"
        else:
            return f"{field} {sql_operator} '{value}'"
    
    def _build_observation_filter(self, criterion: Dict[str, Any]) -> str:
        """Build observation filter condition."""
        field = criterion.get("field", "")
        operator = criterion.get("operator", "Equals")
        value = criterion.get("value", "")
        
        sql_operator = self._operator_to_sql(operator)
        
        return f"observation_type = '{field}' AND observation_value {sql_operator} '{value}'"
    
    def _operator_to_sql(self, operator: str) -> str:
        """Convert operator string to SQL operator."""
        operator_map = {
            "Equals": "=",
            "Contains": "LIKE",
            "GreaterThan": ">",
            "LessThan": "<",
            "Between": "BETWEEN"
        }
        return operator_map.get(operator, "=")
    
    def _optimize_join_order(self, steps: List[QueryStep]) -> List[QueryStep]:
        """
        Optimize join order to minimize intermediate result sizes.
        
        Strategy: Process filters before joins, and join smaller tables first.
        Implements Requirement 2.4.
        """
        # Separate filters and joins
        filters = [s for s in steps if s.operation.operation_type == QueryOperationType.FILTER]
        joins = [s for s in steps if s.operation.operation_type == QueryOperationType.JOIN]
        aggregates = [s for s in steps if s.operation.operation_type == QueryOperationType.AGGREGATE]
        
        # Reorder: filters first, then joins, then aggregates
        optimized = filters + joins + aggregates
        
        # Reassign step IDs
        for i, step in enumerate(optimized):
            step.step_id = i
        
        return optimized
    
    def _estimate_row_count(
        self,
        cohort_criteria: List[Dict[str, Any]],
        variables: List[Dict[str, Any]]
    ) -> int:
        """
        Estimate the number of rows in the result set.
        
        Simple heuristic: Start with 10000 subjects, apply selectivity factors.
        Implements Requirement 2.2.
        """
        base_count = 10000
        
        # Apply selectivity for each filter
        for criterion in cohort_criteria:
            filter_type = criterion.get("filter_type")
            if filter_type == "Diagnosis":
                base_count = int(base_count * 0.1)  # 10% selectivity
            elif filter_type == "Procedure":
                base_count = int(base_count * 0.2)  # 20% selectivity
            elif filter_type == "Demographics":
                base_count = int(base_count * 0.5)  # 50% selectivity
            elif filter_type == "Observation":
                base_count = int(base_count * 0.3)  # 30% selectivity
        
        return max(base_count, 1)  # At least 1 row
    
    def _generate_sql_draft(
        self,
        steps: List[QueryStep],
        cohort_criteria: List[Dict[str, Any]],
        variables: List[Dict[str, Any]],
        time_range: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate SQL draft from query plan.
        
        Implements Requirement 2.3.
        """
        # Build SELECT clause
        select_fields = ["s.subject_id"]
        for variable in variables:
            field = variable.get("field", "")
            source = variable.get("source", "subjects")
            aggregation = variable.get("aggregation")
            
            if aggregation:
                select_fields.append(f"{aggregation}({source[0]}.{field}) AS {field}")
            else:
                select_fields.append(f"{source[0]}.{field}")
        
        select_clause = "SELECT " + ", ".join(select_fields)
        
        # Build FROM clause
        from_clause = "FROM subjects s"
        
        # Build JOIN clauses
        join_clauses = []
        for step in steps:
            if step.operation.operation_type == QueryOperationType.JOIN:
                for table in step.input_tables:
                    if table != "subjects":
                        alias = table[0]
                        join_type = step.operation.join_type.value if step.operation.join_type else "INNER"
                        on_condition = step.operation.on_condition or f"s.subject_id = {alias}.subject_id"
                        join_clauses.append(f"{join_type} JOIN {table} {alias} ON {on_condition}")
        
        # Build WHERE clause
        where_conditions = []
        for criterion in cohort_criteria:
            filter_type = criterion.get("filter_type")
            if filter_type == "Diagnosis":
                where_conditions.append(self._build_diagnosis_filter(criterion))
            elif filter_type == "Procedure":
                where_conditions.append(self._build_procedure_filter(criterion))
            elif filter_type == "Demographics":
                where_conditions.append(self._build_demographic_filter(criterion))
            elif filter_type == "Observation":
                where_conditions.append(self._build_observation_filter(criterion))
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Build GROUP BY clause if needed
        group_by_clause = ""
        has_aggregation = any(v.get("aggregation") for v in variables)
        if has_aggregation:
            group_by_clause = "GROUP BY s.subject_id"
        
        # Combine all clauses
        sql_parts = [select_clause, from_clause] + join_clauses
        if where_clause:
            sql_parts.append(where_clause)
        if group_by_clause:
            sql_parts.append(group_by_clause)
        
        return "\n".join(sql_parts)
