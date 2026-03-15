'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

interface ParsedIntent {
  cohort_criteria: Array<{
    filter_type: string;
    field: string;
    operator: string;
    value: string;
  }>;
  variables: Array<{
    name: string;
    source: string;
    field: string;
  }>;
  time_range?: {
    start: string;
    end: string;
  };
  confidence: number;
}

interface QueryResponse {
  dataset_id: string;
  status: string;
  row_count: number;
  column_count: number;
  download_urls: string[];
  metadata: {
    created_at: string;
    created_by: string;
    data_sources: string[];
  };
  parsed_intent?: ParsedIntent;
  error?: string;
}

export default function ChatInterface({ onDatasetCreated }: { onDatasetCreated: (datasetId: string) => void }) {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [needsClarification, setNeedsClarification] = useState(false);

  const submitQuery = useMutation({
    mutationFn: async (queryText: string) => {
      const res = await apiClient.post<QueryResponse>('/api/query', {
        query_text: queryText,
        data_source_ids: ['clinical_db'],
        output_format: 'CSV',
      });
      return res.data;
    },
    onSuccess: (data) => {
      setResponse(data);
      
      if (data.status === 'Failed' && data.error?.includes('clarify')) {
        setNeedsClarification(true);
      } else if (data.status === 'Completed') {
        setNeedsClarification(false);
        onDatasetCreated(data.dataset_id);
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      submitQuery.mutate(query);
    }
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-xl font-semibold text-gray-900">
          Natural Language Query
        </h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="query" className="block text-sm font-medium text-gray-700">
              Enter your research question
            </label>
            <textarea
              id="query"
              rows={4}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-blue-500"
              placeholder="Example: Find all Parkinson's patients with DBS surgery who had MRI within 6 months post-op"
            />
          </div>

          <button
            type="submit"
            disabled={submitQuery.isPending || !query.trim()}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400"
          >
            {submitQuery.isPending ? 'Processing...' : 'Submit Query'}
          </button>
        </form>
      </div>

      {/* Query Processing Status */}
      {submitQuery.isPending && (
        <div className="rounded-lg bg-blue-50 p-4">
          <div className="flex items-center space-x-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
            <p className="text-sm text-blue-800">Processing your query...</p>
          </div>
        </div>
      )}

      {/* Parsed Intent Display */}
      {response?.parsed_intent && (
        <div className="rounded-lg bg-white p-6 shadow">
          <h3 className="mb-3 text-lg font-semibold text-gray-900">
            Parsed Intent
          </h3>
          
          <div className="space-y-3">
            <div>
              <p className="text-sm font-medium text-gray-700">
                Confidence Score: 
                <span className={`ml-2 ${response.parsed_intent.confidence >= 0.7 ? 'text-green-600' : 'text-red-600'}`}>
                  {(response.parsed_intent.confidence * 100).toFixed(1)}%
                </span>
              </p>
            </div>

            {response.parsed_intent.cohort_criteria.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700">Cohort Criteria:</p>
                <ul className="mt-1 space-y-1">
                  {response.parsed_intent.cohort_criteria.map((criteria, idx) => (
                    <li key={idx} className="text-sm text-gray-600">
                      • {criteria.filter_type}: {criteria.field} {criteria.operator} {criteria.value}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {response.parsed_intent.variables.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700">Variables:</p>
                <ul className="mt-1 space-y-1">
                  {response.parsed_intent.variables.map((variable, idx) => (
                    <li key={idx} className="text-sm text-gray-600">
                      • {variable.name} (from {variable.source})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Clarification Request */}
      {needsClarification && response?.error && (
        <div className="rounded-lg bg-yellow-50 p-4">
          <h3 className="mb-2 text-sm font-semibold text-yellow-800">
            Clarification Needed
          </h3>
          <p className="text-sm text-yellow-700">{response.error}</p>
          <p className="mt-2 text-sm text-yellow-600">
            Please refine your query and try again.
          </p>
        </div>
      )}

      {/* Error Display */}
      {submitQuery.isError && (
        <div className="rounded-lg bg-red-50 p-4">
          <p className="text-sm text-red-800">
            {(submitQuery.error as any)?.response?.data?.detail || 'An error occurred while processing your query.'}
          </p>
        </div>
      )}

      {/* Success Message */}
      {response?.status === 'Completed' && (
        <div className="rounded-lg bg-green-50 p-4">
          <h3 className="mb-2 text-sm font-semibold text-green-800">
            Query Completed Successfully
          </h3>
          <p className="text-sm text-green-700">
            Dataset generated with {response.row_count} rows and {response.column_count} columns.
          </p>
        </div>
      )}
    </div>
  );
}
