'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

interface DatasetMetadata {
  created_at: string;
  created_by: string;
  row_count: number;
  column_count: number;
  data_sources: string[];
}

interface DatasetSchema {
  columns: Array<{
    name: string;
    data_type: string;
    nullable: boolean;
    description: string;
  }>;
}

interface QueryProvenance {
  original_query: string;
  parsed_intent: any;
  sql_executed: string;
  execution_time: number;
}

interface Dataset {
  dataset_id: string;
  rows: any[][];
  schema: DatasetSchema;
  metadata: DatasetMetadata;
  query_provenance: QueryProvenance;
}

export default function DatasetExplorer({ datasetId }: { datasetId: string }) {
  const [currentPage, setCurrentPage] = useState(1);
  const [showProvenance, setShowProvenance] = useState(false);
  const rowsPerPage = 20;

  const { data: dataset, isLoading, error } = useQuery({
    queryKey: ['dataset', datasetId],
    queryFn: async () => {
      const response = await apiClient.get<Dataset>(`/api/dataset/${datasetId}`);
      return response.data;
    },
    enabled: !!datasetId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4">
        <p className="text-sm text-red-800">
          Failed to load dataset: {(error as any)?.response?.data?.detail || 'Unknown error'}
        </p>
      </div>
    );
  }

  if (!dataset) {
    return null;
  }

  const totalPages = Math.ceil(dataset.rows.length / rowsPerPage);
  const startIdx = (currentPage - 1) * rowsPerPage;
  const endIdx = startIdx + rowsPerPage;
  const currentRows = dataset.rows.slice(startIdx, endIdx);

  return (
    <div className="space-y-6">
      {/* Dataset Metadata */}
      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-xl font-semibold text-gray-900">
          Dataset Overview
        </h2>
        
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <p className="text-sm text-gray-600">Row Count</p>
            <p className="text-2xl font-semibold text-gray-900">
              {dataset.metadata.row_count.toLocaleString()}
            </p>
          </div>
          
          <div>
            <p className="text-sm text-gray-600">Column Count</p>
            <p className="text-2xl font-semibold text-gray-900">
              {dataset.metadata.column_count}
            </p>
          </div>
          
          <div>
            <p className="text-sm text-gray-600">Created</p>
            <p className="text-sm font-medium text-gray-900">
              {new Date(dataset.metadata.created_at).toLocaleString()}
            </p>
          </div>
          
          <div>
            <p className="text-sm text-gray-600">Created By</p>
            <p className="text-sm font-medium text-gray-900">
              {dataset.metadata.created_by}
            </p>
          </div>
        </div>

        <div className="mt-4">
          <p className="text-sm text-gray-600">Data Sources</p>
          <div className="mt-1 flex flex-wrap gap-2">
            {dataset.metadata.data_sources.map((source, idx) => (
              <span
                key={idx}
                className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800"
              >
                {source}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Schema Information */}
      <div className="rounded-lg bg-white p-6 shadow">
        <h3 className="mb-4 text-lg font-semibold text-gray-900">
          Schema Information
        </h3>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Column Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Data Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Nullable
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Description
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {dataset.schema.columns.map((column, idx) => (
                <tr key={idx}>
                  <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                    {column.name}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-600">
                    {column.data_type}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-600">
                    {column.nullable ? 'Yes' : 'No'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {column.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Dataset Preview */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">
            Dataset Preview
          </h3>
          <p className="text-sm text-gray-600">
            Showing {startIdx + 1}-{Math.min(endIdx, dataset.rows.length)} of {dataset.rows.length} rows
          </p>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {dataset.schema.columns.map((column, idx) => (
                  <th
                    key={idx}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                  >
                    {column.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {currentRows.map((row, rowIdx) => (
                <tr key={rowIdx}>
                  {row.map((cell, cellIdx) => (
                    <td
                      key={cellIdx}
                      className="whitespace-nowrap px-4 py-3 text-sm text-gray-900"
                    >
                      {cell === null ? (
                        <span className="text-gray-400">NULL</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:text-gray-400"
            >
              Previous
            </button>
            
            <span className="text-sm text-gray-700">
              Page {currentPage} of {totalPages}
            </span>
            
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:text-gray-400"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Query Provenance */}
      <div className="rounded-lg bg-white p-6 shadow">
        <button
          onClick={() => setShowProvenance(!showProvenance)}
          className="flex w-full items-center justify-between text-lg font-semibold text-gray-900"
        >
          <span>Query Provenance</span>
          <span className="text-gray-400">
            {showProvenance ? '▼' : '▶'}
          </span>
        </button>
        
        {showProvenance && (
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-sm font-medium text-gray-700">Original Query</p>
              <p className="mt-1 rounded bg-gray-50 p-3 text-sm text-gray-900">
                {dataset.query_provenance.original_query}
              </p>
            </div>
            
            <div>
              <p className="text-sm font-medium text-gray-700">Executed SQL</p>
              <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-3 text-xs text-gray-900">
                {dataset.query_provenance.sql_executed}
              </pre>
            </div>
            
            <div>
              <p className="text-sm font-medium text-gray-700">Execution Time</p>
              <p className="mt-1 text-sm text-gray-900">
                {dataset.query_provenance.execution_time.toFixed(2)} seconds
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
