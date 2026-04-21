import apiClient from './api-client';
import type {
  LoginRequest,
  LoginResponse,
  QueryRequest,
  QueryResponse,
  Dataset,
  ExportResponse,
  User,
  ClinicalQueryFilters,
  ClinicalQueryResponse,
  AggregateRequest,
  AggregateResponse,
  Encounter,
  EncounterSummary,
  ProvenanceDetail,
} from '@/types';

// Authentication services
export const authService = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/auth/login', credentials);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/api/auth/logout');
  },

  refreshToken: async (refreshToken: string): Promise<{ access_token: string }> => {
    const response = await apiClient.post('/api/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/api/auth/me');
    return response.data;
  },
};

// Query services
export const queryService = {
  submitQuery: async (request: QueryRequest): Promise<QueryResponse> => {
    const response = await apiClient.post<QueryResponse>('/api/query', request);
    return response.data;
  },

  getQueryStatus: async (datasetId: string): Promise<QueryResponse> => {
    const response = await apiClient.get<QueryResponse>(`/api/query/${datasetId}/status`);
    return response.data;
  },
};

// Dataset services
export const datasetService = {
  getDataset: async (datasetId: string): Promise<Dataset> => {
    const response = await apiClient.get<Dataset>(`/api/dataset/${datasetId}`);
    return response.data;
  },

  downloadDataset: async (datasetId: string, format: string): Promise<ExportResponse> => {
    const response = await apiClient.get<ExportResponse>(
      `/api/dataset/${datasetId}/download`,
      {
        params: { format },
      }
    );
    return response.data;
  },

  listDatasets: async (): Promise<Dataset[]> => {
    const response = await apiClient.get<Dataset[]>('/api/datasets');
    return response.data;
  },
};

// FHIR services (for future use)
export const fhirService = {
  triggerIngestion: async (config: any): Promise<{ job_id: string }> => {
    const response = await apiClient.post('/api/fhir/ingest', config);
    return response.data;
  },

  getIngestionStatus: async (jobId: string): Promise<any> => {
    const response = await apiClient.get(`/api/fhir/ingest/${jobId}/status`);
    return response.data;
  },
};

// Extraction services
export const extractionService = {
  getStatus: async (): Promise<any> => {
    const response = await apiClient.get('/api/extraction/status');
    return response.data;
  },

  listJobs: async (limit: number = 50, status?: string): Promise<any> => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (status) params.append('status', status);
    const response = await apiClient.get(`/api/extraction/jobs?${params}`);
    return response.data;
  },

  getJob: async (jobId: string): Promise<any> => {
    const response = await apiClient.get(`/api/extraction/jobs/${jobId}`);
    return response.data;
  },

  processPdf: async (filePath: string): Promise<any> => {
    const response = await apiClient.post('/api/extraction/process', { file_path: filePath });
    return response.data;
  },

  retryJob: async (jobId: string): Promise<any> => {
    const response = await apiClient.post(`/api/extraction/retry/${jobId}`);
    return response.data;
  },

  getStats: async (): Promise<any> => {
    const response = await apiClient.get('/api/extraction/stats');
    return response.data;
  },

  getConfig: async (): Promise<any> => {
    const response = await apiClient.get('/api/extraction/config');
    return response.data;
  },

  updateConfig: async (config: any): Promise<any> => {
    const response = await apiClient.put('/api/extraction/config', config);
    return response.data;
  },
};

// Clinical Query services
export const clinicalQueryService = {
  query: async (filters: ClinicalQueryFilters): Promise<ClinicalQueryResponse> => {
    const response = await apiClient.post<ClinicalQueryResponse>('/api/clinical/query', filters);
    return response.data;
  },

  aggregate: async (request: AggregateRequest): Promise<AggregateResponse> => {
    const response = await apiClient.post<AggregateResponse>('/api/clinical/aggregate', request);
    return response.data;
  },

  getEncounters: async (patientId: string, dateFrom?: string, dateTo?: string): Promise<{ encounters: Encounter[]; total: number }> => {
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    const query = params.toString() ? `?${params}` : '';
    const response = await apiClient.get<{ encounters: Encounter[]; total: number }>(`/api/clinical/encounters/${patientId}${query}`);
    return response.data;
  },

  getEncounterSummary: async (encounterId: string): Promise<EncounterSummary> => {
    const response = await apiClient.get<EncounterSummary>(`/api/clinical/encounters/${encounterId}/summary`);
    return response.data;
  },

  getProvenance: async (provenanceId: string): Promise<ProvenanceDetail> => {
    const response = await apiClient.get<ProvenanceDetail>(`/api/clinical/provenance/${provenanceId}`);
    return response.data;
  },

  getProviderTypes: async (): Promise<string[]> => {
    const response = await apiClient.get<{ provider_types: string[] }>('/api/clinical/providers');
    return response.data.provider_types;
  },
};
