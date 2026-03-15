'use client';

import { useState } from 'react';
import { apiClient } from '@/lib/api-client';

interface UploadResponse {
  status: string;
  message: string;
  table_name: string;
  rows_imported: number;
  columns: string[];
  detected_schema: any;
  sample_data: any[];
}

export function DataUpload({ onUploadComplete }: { onUploadComplete?: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [tableName, setTableName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      // Auto-generate table name from filename
      const name = selectedFile.name
        .replace(/\.[^/.]+$/, '') // Remove extension
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '_'); // Replace non-alphanumeric with underscore
      setTableName(name);
      setResult(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (tableName) {
        formData.append('table_name', tableName);
      }

      const response = await apiClient.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
      if (onUploadComplete) {
        onUploadComplete();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">Upload Data</h2>
      
      <div className="space-y-4">
        {/* File Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select File
          </label>
          <input
            type="file"
            accept=".csv,.xlsx,.xls,.json,.parquet"
            onChange={handleFileChange}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-md file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100"
          />
          <p className="mt-1 text-xs text-gray-500">
            Supported formats: CSV, Excel (.xlsx, .xls), JSON, Parquet
          </p>
        </div>

        {/* Table Name Input */}
        {file && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Table Name (optional)
            </label>
            <input
              type="text"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="Auto-generated from filename"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Data will be imported into this table
            </p>
          </div>
        )}

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? 'Uploading...' : 'Upload and Import'}
        </button>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <p className="font-semibold">Upload Failed</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Success Message */}
        {result && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
            <p className="font-semibold">✓ {result.message}</p>
            <div className="mt-2 text-sm space-y-1">
              <p>Table: <span className="font-mono">{result.table_name}</span></p>
              <p>Rows imported: {result.rows_imported.toLocaleString()}</p>
              <p>Columns: {result.columns.length}</p>
            </div>

            {/* Sample Data Preview */}
            {result.sample_data && result.sample_data.length > 0 && (
              <div className="mt-4">
                <p className="font-semibold mb-2">Sample Data (first 5 rows):</p>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-xs border border-gray-300">
                    <thead className="bg-gray-100">
                      <tr>
                        {result.columns.map((col) => (
                          <th key={col} className="px-2 py-1 border border-gray-300 text-left">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.sample_data.map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          {result.columns.map((col) => (
                            <td key={col} className="px-2 py-1 border border-gray-300">
                              {String(row[col] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <p className="mt-4 text-sm">
              You can now query this data using the chat interface!
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
