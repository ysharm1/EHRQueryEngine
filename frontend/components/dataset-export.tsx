'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

type ExportFormat = 'CSV' | 'Parquet' | 'JSON';

interface ExportResponse {
  download_urls: string[];
  format: ExportFormat;
  files: Array<{
    name: string;
    url: string;
    size: number;
  }>;
}

export default function DatasetExport({ datasetId }: { datasetId: string }) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('CSV');
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);

  const exportMutation = useMutation({
    mutationFn: async (_format: ExportFormat) => {
      // /files returns JSON with {files, download_urls, format}
      const response = await apiClient.get<ExportResponse>(
        `/api/dataset/${datasetId}/files`
      );
      return response.data;
    },
    onSuccess: (data) => {
      setExportResult(data);
    },
  });

  const handleExport = () => {
    exportMutation.mutate(selectedFormat);
  };

  const handleDownload = (url: string, filename: string) => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const fullUrl = url.startsWith('http') ? url : `${API_URL}${url}`;
    const link = document.createElement('a');
    link.href = fullUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">
        Export Dataset
      </h2>

      {/* Format Selection */}
      <div className="mb-6">
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Select Export Format
        </label>
        
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {(['CSV', 'Parquet', 'JSON'] as ExportFormat[]).map((format) => (
            <button
              key={format}
              onClick={() => setSelectedFormat(format)}
              className={`rounded-lg border-2 p-4 text-left transition-colors ${
                selectedFormat === format
                  ? 'border-blue-600 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">{format}</p>
                  <p className="mt-1 text-xs text-gray-600">
                    {format === 'CSV' && 'Comma-separated values, compatible with Excel'}
                    {format === 'Parquet' && 'Columnar format, optimized for analytics'}
                    {format === 'JSON' && 'JavaScript Object Notation, web-friendly'}
                  </p>
                </div>
                {selectedFormat === format && (
                  <div className="h-5 w-5 rounded-full bg-blue-600 flex items-center justify-center">
                    <svg className="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Export Button */}
      <button
        onClick={handleExport}
        disabled={exportMutation.isPending}
        className="w-full rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400"
      >
        {exportMutation.isPending ? (
          <span className="flex items-center justify-center">
            <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
            Generating Export...
          </span>
        ) : (
          `Export as ${selectedFormat}`
        )}
      </button>

      {/* Export Progress */}
      {exportMutation.isPending && (
        <div className="mt-4 rounded-lg bg-blue-50 p-4">
          <div className="flex items-center space-x-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-800">
                Generating {selectedFormat} export...
              </p>
              <p className="text-xs text-blue-600">
                This may take a few moments for large datasets
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {exportMutation.isError && (
        <div className="mt-4 rounded-lg bg-red-50 p-4">
          <p className="text-sm text-red-800">
            Export failed: {(exportMutation.error as any)?.response?.data?.detail || 'Unknown error'}
          </p>
        </div>
      )}

      {/* Download Links */}
      {exportResult && (
        <div className="mt-6 space-y-4">
          <div className="rounded-lg bg-green-50 p-4">
            <h3 className="mb-2 text-sm font-semibold text-green-800">
              Export Complete
            </h3>
            <p className="text-sm text-green-700">
              Your dataset has been exported successfully. Download the files below:
            </p>
          </div>

          <div className="space-y-2">
            {exportResult.files?.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-lg border border-gray-200 p-4"
              >
                <div className="flex items-center space-x-3">
                  <svg
                    className="h-8 w-8 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{file.name}</p>
                    <p className="text-xs text-gray-600">
                      {(file.size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                </div>
                
                <button
                  onClick={() => handleDownload(file.url, file.name)}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                >
                  Download
                </button>
              </div>
            ))}

            {/* Fallback for simple download_urls array */}
            {!exportResult.files && exportResult.download_urls?.map((url, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-lg border border-gray-200 p-4"
              >
                <div className="flex items-center space-x-3">
                  <svg
                    className="h-8 w-8 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {url.split('/').pop() || `File ${idx + 1}`}
                    </p>
                  </div>
                </div>
                
                <a
                  href={url}
                  download
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                >
                  Download
                </a>
              </div>
            ))}
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <p className="text-xs text-gray-600">
              <strong>Note:</strong> Export files include the dataset in your selected format,
              a schema definition (JSON), and query provenance information for reproducibility.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
