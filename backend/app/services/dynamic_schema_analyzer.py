"""
Dynamic Schema Analyzer

Automatically discovers and analyzes database schema to enable flexible querying
regardless of column names or table structure. No data is lost.

This service:
1. Discovers all tables and columns in DuckDB
2. Fuzzy matches column names to semantic types
3. Generates dynamic SQL queries based on available schema
4. Preserves all columns even if not recognized
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import re
from difflib import SequenceMatcher


@dataclass
class ColumnInfo:
    """Information about a database column."""
    table_name: str
    column_name: str
    data_type: str
    semantic_type: str  # id, date, diagnosis, procedure, demographic, observation, unknown
    confidence: float  # 0.0 to 1.0
    aliases: List[str]  # Alternative names this column might be called


@dataclass
class TableInfo:
    """Information about a database table."""
    table_name: str
    columns: List[ColumnInfo]
    row_count: int
    primary_key: Optional[str]


class DynamicSchemaAnalyzer:
    """
    Analyzes database schema dynamically to enable flexible querying.
    
    Key features:
    - Discovers all tables and columns automatically
    - Fuzzy matches column names (handles typos, variations)
    - Maps natural language terms to database columns
    - Never loses data - all columns are preserved
    """
    
    # Semantic type patterns with fuzzy matching
    SEMANTIC_PATTERNS = {
        "id": [
            "id", "identifier", "subject", "patient", "mrn", "record", "key", "code"
        ],
        "date": [
            "date", "dob", "birth", "time", "timestamp", "when", "day", "year",
            "admission", "discharge", "visit", "enrollment", "start", "end"
        ],
        "diagnosis": [
            "diagnosis", "diagnoses", "condition", "disease", "icd", "snomed",
            "disorder", "illness", "pathology"
        ],
        "procedure": [
            "procedure", "surgery", "operation", "treatment", "intervention",
            "cpt", "service", "therapy"
        ],
        "demographic": [
            "age", "sex", "gender", "race", "ethnicity", "height", "weight",
            "bmi", "address", "zip", "state", "country"
        ],
        "observation": [
            "observation", "lab", "test", "result", "value", "measurement",
            "vital", "score", "level", "count", "loinc"
        ],
        "medication": [
            "medication", "drug", "prescription", "dose", "dosage", "rxnorm"
        ]
    }
    
    def __init__(self, db_connection):
        """
        Initialize the analyzer with a database connection.
        
        Args:
            db_connection: DuckDB connection object
        """
        self.conn = db_connection
        self.schema_cache: Dict[str, TableInfo] = {}
        self._refresh_schema()
    
    def _refresh_schema(self):
        """Discover all tables and columns in the database."""
        self.schema_cache.clear()
        
        # Get all tables
        tables = self.conn.execute("SHOW TABLES").fetchall()
        
        for (table_name,) in tables:
            # Get column information
            columns_raw = self.conn.execute(f"DESCRIBE {table_name}").fetchall()
            
            # Get row count
            row_count = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            
            columns = []
            for col_name, col_type, *_ in columns_raw:
                semantic_type, confidence, aliases = self._infer_semantic_type(col_name, col_type)
                
                columns.append(ColumnInfo(
                    table_name=table_name,
                    column_name=col_name,
                    data_type=col_type,
                    semantic_type=semantic_type,
                    confidence=confidence,
                    aliases=aliases
                ))
            
            # Try to identify primary key (usually an ID column)
            primary_key = self._identify_primary_key(columns)
            
            self.schema_cache[table_name] = TableInfo(
                table_name=table_name,
                columns=columns,
                row_count=row_count,
                primary_key=primary_key
            )
    
    def _infer_semantic_type(
        self, 
        column_name: str, 
        data_type: str
    ) -> Tuple[str, float, List[str]]:
        """
        Infer the semantic type of a column using fuzzy matching.
        
        Returns:
            (semantic_type, confidence, aliases)
        """
        col_lower = column_name.lower()
        col_tokens = re.split(r'[\W_]+', col_lower)
        
        best_type = "unknown"
        best_score = 0.0
        best_aliases = []
        
        for semantic_type, patterns in self.SEMANTIC_PATTERNS.items():
            for pattern in patterns:
                # Check exact match in tokens
                if pattern in col_tokens:
                    score = 1.0
                # Check if pattern is substring
                elif pattern in col_lower:
                    score = 0.9
                # Fuzzy match
                else:
                    score = max(
                        SequenceMatcher(None, pattern, token).ratio()
                        for token in col_tokens
                    )
                
                if score > best_score:
                    best_score = score
                    best_type = semantic_type
                    best_aliases = [p for p in patterns if p != pattern]
        
        # Boost confidence for certain data types
        if "date" in data_type.lower() or "timestamp" in data_type.lower():
            if best_type != "date":
                best_type = "date"
                best_score = max(best_score, 0.8)
        
        return best_type, best_score, best_aliases[:5]  # Top 5 aliases
    
    def _identify_primary_key(self, columns: List[ColumnInfo]) -> Optional[str]:
        """Identify the most likely primary key column."""
        id_columns = [
            col for col in columns 
            if col.semantic_type == "id" and col.confidence > 0.7
        ]
        
        if not id_columns:
            return None
        
        # Prefer columns with "subject" or "patient" in name
        for col in id_columns:
            if "subject" in col.column_name.lower() or "patient" in col.column_name.lower():
                return col.column_name
        
        # Otherwise return first ID column
        return id_columns[0].column_name
    
    def find_columns_by_semantic_type(
        self, 
        semantic_type: str, 
        min_confidence: float = 0.5
    ) -> List[ColumnInfo]:
        """
        Find all columns matching a semantic type across all tables.
        
        Args:
            semantic_type: The semantic type to search for
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of matching columns
        """
        matches = []
        for table_info in self.schema_cache.values():
            for col in table_info.columns:
                if col.semantic_type == semantic_type and col.confidence >= min_confidence:
                    matches.append(col)
        return matches
    
    def find_column_by_name(
        self, 
        search_term: str, 
        table_name: Optional[str] = None,
        fuzzy: bool = True
    ) -> Optional[ColumnInfo]:
        """
        Find a column by name with optional fuzzy matching.
        
        Args:
            search_term: Column name to search for
            table_name: Optional table to restrict search
            fuzzy: Whether to use fuzzy matching
        
        Returns:
            Best matching column or None
        """
        search_lower = search_term.lower()
        best_match = None
        best_score = 0.0
        
        tables_to_search = (
            [self.schema_cache[table_name]] if table_name and table_name in self.schema_cache
            else self.schema_cache.values()
        )
        
        for table_info in tables_to_search:
            for col in table_info.columns:
                col_lower = col.column_name.lower()
                
                # Exact match
                if col_lower == search_lower:
                    return col
                
                if fuzzy:
                    # Check aliases
                    if search_lower in [alias.lower() for alias in col.aliases]:
                        score = 0.95
                    # Fuzzy match on column name
                    else:
                        score = SequenceMatcher(None, search_lower, col_lower).ratio()
                    
                    if score > best_score and score > 0.6:  # Threshold for fuzzy match
                        best_score = score
                        best_match = col
        
        return best_match
    
    def get_all_tables(self) -> List[TableInfo]:
        """Get information about all tables."""
        return list(self.schema_cache.values())
    
    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get information about a specific table."""
        return self.schema_cache.get(table_name)
    
    def generate_select_query(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        where_clauses: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Generate a SELECT query dynamically based on available schema.
        
        Args:
            table_name: Table to query
            columns: Columns to select (None = all columns)
            where_clauses: WHERE conditions
            limit: Row limit
        
        Returns:
            SQL query string
        """
        table_info = self.get_table_info(table_name)
        if not table_info:
            raise ValueError(f"Table {table_name} not found")
        
        # Select columns
        if columns:
            # Validate columns exist
            valid_cols = []
            for col_name in columns:
                col_info = self.find_column_by_name(col_name, table_name)
                if col_info:
                    valid_cols.append(col_info.column_name)
            select_clause = ", ".join(valid_cols) if valid_cols else "*"
        else:
            select_clause = "*"
        
        # Build query
        query = f"SELECT {select_clause} FROM {table_name}"
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        if limit:
            query += f" LIMIT {limit}"
        
        return query
    
    def map_natural_language_to_columns(
        self, 
        terms: List[str]
    ) -> Dict[str, ColumnInfo]:
        """
        Map natural language terms to database columns.
        
        Args:
            terms: List of natural language terms (e.g., ["age", "diagnosis", "gender"])
        
        Returns:
            Dictionary mapping term to best matching column
        """
        mappings = {}
        
        for term in terms:
            # Try exact semantic type match first
            term_lower = term.lower()
            if term_lower in self.SEMANTIC_PATTERNS:
                matches = self.find_columns_by_semantic_type(term_lower)
                if matches:
                    mappings[term] = matches[0]  # Take best match
                    continue
            
            # Try fuzzy column name match
            col = self.find_column_by_name(term, fuzzy=True)
            if col:
                mappings[term] = col
        
        return mappings
    
    def get_schema_summary(self) -> Dict[str, any]:
        """Get a summary of the entire database schema."""
        return {
            "total_tables": len(self.schema_cache),
            "tables": [
                {
                    "name": table.table_name,
                    "row_count": table.row_count,
                    "column_count": len(table.columns),
                    "primary_key": table.primary_key,
                    "columns": [
                        {
                            "name": col.column_name,
                            "type": col.data_type,
                            "semantic_type": col.semantic_type,
                            "confidence": round(col.confidence, 2)
                        }
                        for col in table.columns
                    ]
                }
                for table in self.schema_cache.values()
            ]
        }
