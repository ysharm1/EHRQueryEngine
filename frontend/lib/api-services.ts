import apiClient from './api-client';
import type {
  LoginRequest,
  LoginResponse,
  QueryRequest,
  QueryResponse,
  Dataset,
  ExportResponse,
  User,
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
