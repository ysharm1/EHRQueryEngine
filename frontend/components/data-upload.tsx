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

interface UploadedFile {
  id: string;
  fileName: string;
  tableName: string;
  rowsImported: number;
  columns: string[];
}

export function DataUpload({ onUploadComplete }: { onUploadComplete?: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.xls', '.json', '.parquet'];

  const addFiles = (newFiles: File[]) => {
    const valid = newFiles.filter((f) =>
      ACCEPTED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (valid.length === 0) return;
    setFiles((prev) => [...prev, ...valid]);
    setError(null);
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const removeUploaded = (id: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleUploadAll = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);

    for (const file of files) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        const tableName = file.name
          .replace(/\.[^/.]+$/, '')
          .toLowerCase()
          .replace(/[^a-z0-9]/g, '_');
        formData.append('table_name', tableName);

        const response = await apiClient.post('/api/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        setUploadedFiles((prev) => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
            fileName: file.name,
            tableName: response.data.table_name,
            rowsImported: response.data.rows_imported,
            columns: response.data.columns,
          },
        ]);
      } catch (err: any) {
        setError(`Failed to upload ${file.name}: ${err.response?.data?.detail || err.message}`);
      }
    }

    setFiles([]);
    setUploading(false);
    if (onUploadComplete) onUploadComplete();
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(e.target.files || []));
    e.target.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Drop Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`relative rounded-xl border-2 border-dashed p-10 text-center transition-all ${
          dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:border-gray-300'
        }`}
      >
        <div className="space-y-4">
          <div className="mx-auto w-12 h-12 rounded-full bg-green-50 flex items-center justify-center">
            <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <p className="text-base font-medium text-gray-700">Drop data files here</p>
            <p className="text-sm text-gray-500 mt-1">CSV, Excel, JSON, or Parquet — select multiple</p>
          </div>
          <input
            type="file"
            accept=".csv,.xlsx,.xls,.json,.parquet"
            multiple
            onChange={onFileSelect}
            className="hidden"
            id="data-upload-input"
          />
          <label
            htmlFor="data-upload-input"
            className="inline-flex items-center px-5 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium cursor-pointer hover:bg-green-700 transition-colors shadow-sm"
          >
            Select Files
          </label>
        </div>
      </div>

      {/* Pending Files */}
      {files.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">{files.length} file{files.length > 1 ? 's' : ''} ready to upload</p>
            <button
              onClick={handleUploadAll}
              disabled={uploading}
              className="px-4 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? 'Uploading…' : 'Upload All'}
            </button>
          </div>
          <div className="divide-y divide-gray-50">
            {files.map((file, idx) => (
              <div key={idx} className="px-5 py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-800">{file.name}</span>
                  <span className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</span>
                </div>
                <button
                  onClick={() => removeFile(idx)}
                  className="text-xs text-red-500 hover:text-red-700"
                  aria-label={`Remove ${file.name}`}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Uploaded Files */}
      {uploadedFiles.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <p className="text-sm font-medium text-gray-700">Uploaded Data</p>
          </div>
          <div className="divide-y divide-gray-50">
            {uploadedFiles.map((uf) => (
              <div key={uf.id} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-800">{uf.fileName}</p>
                  <p className="text-xs text-gray-500">
                    Table: <span className="font-mono">{uf.tableName}</span> · {uf.rowsImported.toLocaleString()} rows · {uf.columns.length} columns
                  </p>
                </div>
                <button
                  onClick={() => removeUploaded(uf.id)}
                  className="text-xs text-gray-400 hover:text-red-600"
                  aria-label={`Remove ${uf.fileName}`}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
