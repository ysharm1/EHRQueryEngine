"""
Export Engine Service

Generates dataset files in multiple formats (CSV, Parquet, JSON) with schema
and provenance information.
Implements Requirements 10.1-10.7, 11.1-11.6.
"""

from typing import List, Dict, Any
import csv
import json
import os
from pathlib import Path
from datetime import datetime
from app.services.dataset_assembly import AssembledDataset
from app.models.metadata import ExportFormat


class ExportEngine:
    """
    Export Engine for generating dataset files.
    
    Implements:
    - Requirements 10.1-10.4: Export in CSV, Parquet, JSON formats
    - Requirement 10.5: Generate schema definition file
    - Requirement 10.6: Generate query provenance file
    - Requirement 10.7: Return download URLs
    - Requirements 11.1-11.6: Generate reproducible queries
    """
    
    def __init__(self, export_dir: str = "exports"):
        """
        Initialize export engine.
        
        Args:
            export_dir: Directory for exported files
        """
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_files(
        self,
        dataset: AssembledDataset,
        export_format: ExportFormat
    ) -> List[str]:
        """
        Generate export files for dataset.
        
        Args:
            dataset: Assembled dataset to export
            export_format: Desired export format
        
        Returns:
            List of file paths for generated files
        
        Implements Requirements 10.1-10.7
        """
        file_paths = []
        
        # Create dataset directory
        dataset_dir = self.export_dir / dataset.dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate data file in requested format
        if export_format == ExportFormat.CSV:
            data_file = self._export_csv(dataset, dataset_dir)
            file_paths.append(data_file)
        
        elif export_format == ExportFormat.PARQUET:
            data_file = self._export_parquet(dataset, dataset_dir)
            file_paths.append(data_file)
        
        elif export_format == ExportFormat.JSON:
            data_file = self._export_json(dataset, dataset_dir)
            file_paths.append(data_file)
        
        # Generate schema file (Req 10.5)
        schema_file = self._export_schema(dataset, dataset_dir)
        file_paths.append(schema_file)
        
        # Generate provenance file (Req 10.6)
        provenance_file = self._export_provenance(dataset, dataset_dir)
        file_paths.append(provenance_file)
        
        # Generate reproducible query file (Req 11.1-11.6)
        query_file = self._export_reproducible_query(dataset, dataset_dir)
        file_paths.append(query_file)
        
        return file_paths
    
    def _export_csv(
        self,
        dataset: AssembledDataset,
        output_dir: Path
    ) -> str:
        """
        Export dataset as CSV file.
        
        Implements Requirement 10.2
        """
        file_path = output_dir / "data.csv"
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            header = [col.name for col in dataset.schema.columns]
            writer.writerow(header)
            
            # Write data rows
            for row in dataset.rows:
                writer.writerow(row)
        
        return str(file_path)
    
    def _export_parquet(
        self,
        dataset: AssembledDataset,
        output_dir: Path
    ) -> str:
        """
        Export dataset as Parquet file.
        
        Implements Requirement 10.3
        """
        file_path = output_dir / "data.parquet"
        
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            
            # Build schema
            fields = []
            for col in dataset.schema.columns:
                if col.data_type == "string":
                    pa_type = pa.string()
                elif col.data_type == "integer":
                    pa_type = pa.int64()
                elif col.data_type == "float":
                    pa_type = pa.float64()
                elif col.data_type == "date":
                    pa_type = pa.date32()
                else:
                    pa_type = pa.string()
                
                fields.append(pa.field(col.name, pa_type, nullable=col.nullable))
            
            schema = pa.schema(fields)
            
            # Convert rows to columnar format
            columns = {col.name: [] for col in dataset.schema.columns}
            for row in dataset.rows:
                for i, col in enumerate(dataset.schema.columns):
                    columns[col.name].append(row[i])
            
            # Create table
            arrays = [pa.array(columns[col.name]) for col in dataset.schema.columns]
            table = pa.Table.from_arrays(arrays, schema=schema)
            
            # Write parquet file
            pq.write_table(table, file_path)
        
        except ImportError:
            # Fallback to CSV if pyarrow not available
            return self._export_csv(dataset, output_dir)
        
        return str(file_path)
    
    def _export_json(
        self,
        dataset: AssembledDataset,
        output_dir: Path
    ) -> str:
        """
        Export dataset as JSON file.
        
        Implements Requirement 10.4
        """
        file_path = output_dir / "data.json"
        
        # Convert rows to list of objects
        column_names = [col.name for col in dataset.schema.columns]
        records = []
        
        for row in dataset.rows:
            record = {}
            for i, col_name in enumerate(column_names):
                record[col_name] = row[i]
            records.append(record)
        
        # Write JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, default=str)
        
        return str(file_path)
    
    def _export_schema(
        self,
        dataset: AssembledDataset,
        output_dir: Path
    ) -> str:
        """
        Export schema definition as JSON file.
        
        Implements Requirement 10.5
        """
        file_path = output_dir / "schema.json"
        
        schema_dict = {
            "columns": [
                {
                    "name": col.name,
                    "data_type": col.data_type,
                    "nullable": col.nullable,
                    "description": col.description
                }
                for col in dataset.schema.columns
            ],
            "primary_key": dataset.schema.primary_key,
            "row_count": dataset.metadata.row_count,
            "column_count": dataset.metadata.column_count
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schema_dict, f, indent=2)
        
        return str(file_path)
    
    def _export_provenance(
        self,
        dataset: AssembledDataset,
        output_dir: Path
    ) -> str:
        """
        Export query provenance as JSON file.
        
        Implements Requirement 10.6
        """
        file_path = output_dir / "provenance.json"
        
        provenance_dict = {
            "dataset_id": dataset.dataset_id,
            "original_query": dataset.query_provenance.original_query,
            "parsed_intent": dataset.query_provenance.parsed_intent,
            "sql_executed": dataset.query_provenance.sql_executed,
            "execution_time": dataset.query_provenance.execution_time,
            "confidence_score": dataset.query_provenance.confidence_score,
            "created_at": dataset.metadata.created_at,
            "created_by": dataset.metadata.created_by,
            "data_sources": dataset.metadata.data_sources
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(provenance_dict, f, indent=2, default=str)
        
        return str(file_path)
    
    def _export_reproducible_query(
        self,
        dataset: AssembledDataset,
        output_dir: Path
    ) -> str:
        """
        Generate reproducible SQL query file.
        
        Implements Requirements 11.1-11.6
        """
        file_path = output_dir / "query.sql"
        
        # Build SQL with comments (Req 11.2)
        sql_parts = []
        
        # Header with metadata (Req 11.2)
        sql_parts.append("-- Research Dataset Builder - Reproducible Query")
        sql_parts.append(f"-- Generated: {dataset.metadata.created_at}")
        sql_parts.append(f"-- Created by: {dataset.metadata.created_by}")
        sql_parts.append(f"-- Dataset ID: {dataset.dataset_id}")
        sql_parts.append(f"-- Original Query: {dataset.query_provenance.original_query}")
        sql_parts.append("")
        
        # Cohort definition (Req 11.3)
        sql_parts.append("-- Cohort Definition")
        cohort_criteria = dataset.query_provenance.parsed_intent.get("cohort_criteria", [])
        if cohort_criteria:
            cohort_sql = self._generate_cohort_sql(cohort_criteria)
            sql_parts.append(cohort_sql)
        sql_parts.append("")
        
        # Variable collection (Req 11.4)
        sql_parts.append("-- Variable Collection")
        variables = dataset.query_provenance.parsed_intent.get("variables", [])
        if variables:
            variable_sql = self._generate_variable_sql(variables)
            sql_parts.append(variable_sql)
        sql_parts.append("")
        
        # Full query (Req 11.5)
        sql_parts.append("-- Complete Query")
        sql_parts.append(dataset.query_provenance.sql_executed)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(sql_parts))
        
        return str(file_path)
    
    def _generate_cohort_sql(self, criteria: List[Dict[str, Any]]) -> str:
        """
        Generate SQL for cohort definition.
        
        Implements Requirement 11.3
        """
        conditions = []
        
        for criterion in criteria:
            filter_type = criterion.get("filter_type")
            value = criterion.get("value", "")
            
            if filter_type == "Diagnosis":
                conditions.append(f"'{value}' = ANY(diagnosis_codes)")
            
            elif filter_type == "Procedure":
                conditions.append(
                    f"subject_id IN (SELECT subject_id FROM procedures WHERE procedure_code = '{value}')"
                )
            
            elif filter_type == "Demographics":
                field = criterion.get("field", "")
                operator = criterion.get("operator", "Equals")
                sql_op = self._operator_to_sql(operator)
                conditions.append(f"{field} {sql_op} '{value}'")
            
            elif filter_type == "Observation":
                field = criterion.get("field", "")
                conditions.append(
                    f"subject_id IN (SELECT subject_id FROM observations WHERE observation_type = '{field}')"
                )
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return f"SELECT subject_id FROM subjects WHERE {where_clause};"
    
    def _generate_variable_sql(self, variables: List[Dict[str, Any]]) -> str:
        """
        Generate SQL for variable collection.
        
        Implements Requirement 11.4
        """
        select_fields = ["s.subject_id"]
        
        for variable in variables:
            field = variable.get("field", "")
            source = variable.get("source", "subjects")
            aggregation = variable.get("aggregation")
            
            if aggregation:
                select_fields.append(f"{aggregation}({source[0]}.{field}) AS {field}")
            else:
                select_fields.append(f"{source[0]}.{field}")
        
        return f"SELECT {', '.join(select_fields)} FROM subjects s;"
    
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
    
    def get_download_urls(
        self,
        file_paths: List[str],
        dataset_id: str = "",
    ) -> List[str]:
        """
        Generate download URLs for exported files.

        Implements Requirement 10.7
        """
        urls = []
        for file_path in file_paths:
            file_name = Path(file_path).name
            urls.append(f"/api/dataset/{dataset_id}/download?file_name={file_name}")
        return urls
