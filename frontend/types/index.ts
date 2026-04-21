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

// Clinical Query types

export interface Encounter {
  encounter_id: string;
  patient_id: string;
  encounter_date: string | null;
  encounter_type: string | null;
  primary_provider: string | null;
  primary_provider_type: string | null;
  facility: string | null;
  source_file: string | null;
  data_point_count: number;
  created_at: string;
}

export interface ClinicalQueryFilters {
  patient_id?: string;
  encounter_id?: string;
  date_from?: string;
  date_to?: string;
  provider_types?: string[];
  data_types?: string[];
  vital_names?: string[];
  lab_names?: string[];
  limit?: number;
  offset?: number;
}

export interface ClinicalQueryResponse {
  rows: Record<string, unknown>[];
  total_count: number;
  provenance_refs: Record<string, string>;
}

export interface AggregateRequest {
  patient_id?: string;
  encounter_id?: string;
  date_from?: string;
  date_to?: string;
  provider_types?: string[];
  metric_name: string;
  data_type: string;
  aggregations: string[];
  group_by: string;
}

export interface AggregatedMetric {
  group_key: string;
  group_label: string;
  metric_name: string;
  encounter_date: string | null;
  encounter_type: string | null;
  min: number | null;
  max: number | null;
  avg: number | null;
  first: number | null;
  last: number | null;
  count: number;
  provenance_ids: string[];
}

export interface AggregateResponse {
  groups: AggregatedMetric[];
}

export interface ProvenanceDetail {
  provenance_id: string;
  data_record_id: string;
  data_table: string;
  source_file: string;
  page_number: number | null;
  provider_name: string | null;
  provider_type: string | null;
  extraction_confidence: number;
  extraction_job_id: string;
  raw_snippet: string | null;
  created_at: string;
}

export interface EncounterSummary {
  encounter_id: string;
  patient_id: string;
  encounter_date: string | null;
  encounter_type: string | null;
  primary_provider: string | null;
  primary_provider_type: string | null;
  facility: string | null;
  vitals: Record<string, unknown>[];
  labs: Record<string, unknown>[];
  diagnoses: Record<string, unknown>[];
  procedures: Record<string, unknown>[];
  medications: Record<string, unknown>[];
  notes: Record<string, unknown>[];
  imaging: Record<string, unknown>[];
  provenance: ProvenanceDetail[];
}
