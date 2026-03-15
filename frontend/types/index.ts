// Authentication types
export interface User {
  id: string;
  username: string;
  role: 'Admin' | 'Researcher' | 'Data_Analyst' | 'Read_Only';
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

// Query types
export type ExportFormat = 'CSV' | 'Parquet' | 'JSON';

export interface CohortFilter {
  filter_type: 'Diagnosis' | 'Procedure' | 'Medication' | 'Demographics' | 'Observation';
  field: string;
  operator: 'Equals' | 'Contains' | 'GreaterThan' | 'LessThan' | 'Between';
  value: string;
}

export interface VariableRequest {
  name: string;
  source: string;
  field: string;
  aggregation?: string;
}

export interface ParsedIntent {
  cohort_criteria: CohortFilter[];
  variables: VariableRequest[];
  time_range?: {
    start: string;
    end: string;
  };
  confidence: number;
}

export interface QueryRequest {
  query_text: string;
  data_source_ids: string[];
  output_format: ExportFormat;
}

export interface QueryResponse {
  dataset_id: string;
  status: 'Pending' | 'Processing' | 'Completed' | 'Failed';
  row_count: number;
  column_count: number;
  download_urls: string[];
  metadata: DatasetMetadata;
  parsed_intent?: ParsedIntent;
  error?: string;
}

// Dataset types
export interface DatasetMetadata {
  created_at: string;
  created_by: string;
  row_count: number;
  column_count: number;
  data_sources: string[];
}

export interface ColumnDefinition {
  name: string;
  data_type: 'String' | 'Integer' | 'Float' | 'Date' | 'Boolean';
  nullable: boolean;
  description: string;
}

export interface DatasetSchema {
  columns: ColumnDefinition[];
  primary_key?: string;
}

export interface QueryProvenance {
  original_query: string;
  parsed_intent: ParsedIntent;
  sql_executed: string;
  execution_time: number;
}

export interface Dataset {
  dataset_id: string;
  rows: any[][];
  schema: DatasetSchema;
  metadata: DatasetMetadata;
  query_provenance: QueryProvenance;
}

// Export types
export interface ExportFile {
  name: string;
  url: string;
  size: number;
}

export interface ExportResponse {
  download_urls: string[];
  format: ExportFormat;
  files?: ExportFile[];
}
