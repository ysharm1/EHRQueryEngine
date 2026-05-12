'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';

interface ExtractionJob {
  job_id: string;
  file_name: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  patient_id: string | null;
  records_extracted: number;
  confidence: number;
  error_message: string | null;
}

interface ExtractionStats {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  pending_jobs: number;
  jobs_today: number;
  success_rate: number;
  avg_confidence: number;
  avg_records_per_job: number;
}

interface UploadItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  message: string;
}

export default function ExtractionDashboard() {
  const [jobs, setJobs] = useState<ExtractionJob[]>([]);
  const [stats, setStats] = useState<ExtractionStats | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [reindexResult, setReindexResult] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await apiGet('/api/extraction/jobs?limit=50');
      setJobs(data.jobs || []);
    } catch {
      // silently fail on poll
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const data = await apiGet('/api/extraction/stats');
      setStats(data);
    } catch {
      // silently fail on poll
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    fetchStats();
    const interval = setInterval(() => {
      fetchJobs();
      fetchStats();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchJobs, fetchStats]);

  // Process upload queue sequentially
  useEffect(() => {
    if (isProcessing) return;
    const pendingIdx = uploadQueue.findIndex((item) => item.status === 'pending');
    if (pendingIdx === -1) return;

    setIsProcessing(true);

    const processNext = async () => {
      setUploadQueue((prev) =>
        prev.map((item, i) =>
          i === pendingIdx ? { ...item, status: 'uploading' as const, message: 'Extracting…' } : item
        )
      );

      try {
        const formData = new FormData();
        formData.append('file', uploadQueue[pendingIdx].file);
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/extraction/upload`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
            body: formData,
          }
        );
        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
          throw new Error(typeof err.detail === 'string' ? err.detail : 'Upload failed');
        }
        const data = await response.json();
        const msg =
          data.status === 'completed'
            ? `${data.records_extracted} records extracted (${Math.round((data.confidence || 0) * 100)}% confidence)`
            : data.status === 'failed'
            ? `Failed: ${data.error_message || 'Unknown error'}`
            : `Status: ${data.status}`;

        setUploadQueue((prev) =>
          prev.map((item, i) =>
            i === pendingIdx
              ? { ...item, status: (data.status === 'failed' ? 'failed' : 'completed') as 'completed' | 'failed', message: msg }
              : item
          )
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Upload failed';
        setUploadQueue((prev) =>
          prev.map((item, i) =>
            i === pendingIdx ? { ...item, status: 'failed' as const, message } : item
          )
        );
      } finally {
        setIsProcessing(false);
        fetchJobs();
        fetchStats();
      }
    };

    processNext();
  }, [uploadQueue, isProcessing, fetchJobs, fetchStats]);

  const handleFiles = (files: File[]) => {
    const pdfFiles = files.filter((f) => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) return;
    const newItems: UploadItem[] = pdfFiles.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      status: 'pending' as const,
      message: 'Waiting…',
    }));
    setUploadQueue((prev) => [...prev, ...newItems]);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(Array.from(e.dataTransfer.files));
  };

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(Array.from(e.target.files || []));
    e.target.value = '';
  };

  const clearQueue = () => {
    setUploadQueue((prev) => prev.filter((i) => i.status === 'pending' || i.status === 'uploading'));
  };

  const handleReindex = async () => {
    setReindexing(true);
    setReindexResult(null);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/cohort/reindex`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
            'Content-Type': 'application/json',
          },
        }
      );
      if (!response.ok) throw new Error('Reindex failed');
      const data = await response.json();
      setReindexResult(`Indexed ${data.notes_processed} notes → ${data.embeddings_created} embeddings`);
    } catch {
      setReindexResult('Reindex failed — check API key');
    } finally {
      setReindexing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-50 text-green-700 ring-green-600/20';
      case 'failed': return 'bg-red-50 text-red-700 ring-red-600/20';
      case 'processing': return 'bg-yellow-50 text-yellow-700 ring-yellow-600/20';
      default: return 'bg-gray-50 text-gray-700 ring-gray-600/20';
    }
  };

  return (
    <div className="space-y-8">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500">Total Extractions</p>
          <p className="text-3xl font-semibold text-gray-900 mt-1">{stats?.total_jobs || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500">Completed</p>
          <p className="text-3xl font-semibold text-green-600 mt-1">{stats?.completed_jobs || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500">Success Rate</p>
          <p className="text-3xl font-semibold text-gray-900 mt-1">{stats?.success_rate ? `${stats.success_rate.toFixed(0)}%` : '—'}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <p className="text-sm text-gray-500">Avg Confidence</p>
          <p className="text-3xl font-semibold text-gray-900 mt-1">{stats?.avg_confidence ? `${stats.avg_confidence.toFixed(0)}%` : '—'}</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleReindex}
          disabled={reindexing}
          className="inline-flex items-center px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 shadow-sm"
        >
          {reindexing ? 'Indexing…' : 'Reindex for Cohort Search'}
        </button>
        {reindexResult && (
          <span className={`text-sm ${reindexResult.includes('failed') ? 'text-red-600' : 'text-green-600'}`}>
            {reindexResult}
          </span>
        )}
      </div>

      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`relative rounded-xl border-2 border-dashed p-10 text-center transition-all ${
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-200 bg-white hover:border-gray-300'
        }`}
      >
        <div className="space-y-4">
          <div className="mx-auto w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center">
            <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16v-8m0 0l-3 3m3-3l3 3M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1" />
            </svg>
          </div>
          <div>
            <p className="text-base font-medium text-gray-700">
              {isProcessing ? 'Processing…' : 'Drop clinical PDFs here'}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Upload one or multiple PDF files for AI extraction
            </p>
          </div>
          <input
            type="file"
            accept=".pdf"
            multiple
            onChange={onFileSelect}
            className="hidden"
            id="pdf-upload-input"
          />
          <label
            htmlFor="pdf-upload-input"
            className="inline-flex items-center px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium cursor-pointer hover:bg-blue-700 transition-colors shadow-sm"
          >
            Select PDFs
          </label>
        </div>
      </div>

      {/* Upload Queue */}
      {uploadQueue.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <p className="text-sm font-medium text-gray-700">
              Upload Progress — {uploadQueue.filter((i) => i.status === 'completed').length}/{uploadQueue.length} complete
            </p>
            {uploadQueue.every((i) => i.status === 'completed' || i.status === 'failed') && (
              <button onClick={clearQueue} className="text-xs text-blue-600 hover:text-blue-800 font-medium">
                Clear
              </button>
            )}
          </div>
          <div className="divide-y divide-gray-50 max-h-64 overflow-y-auto">
            {uploadQueue.map((item) => (
              <div key={item.id} className="px-5 py-3 flex items-center gap-3">
                <span className="flex-shrink-0 text-base">
                  {item.status === 'pending' && '⏳'}
                  {item.status === 'uploading' && <span className="animate-pulse">⚙️</span>}
                  {item.status === 'completed' && '✅'}
                  {item.status === 'failed' && '❌'}
                </span>
                <span className="flex-1 text-sm text-gray-800 truncate">{item.file.name}</span>
                <span className={`text-xs ${item.status === 'failed' ? 'text-red-600' : item.status === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
                  {item.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Extraction Jobs Table */}
      {jobs.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-base font-semibold text-gray-900">Recent Extractions</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50/50">
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">File</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Records</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Confidence</th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {jobs.map((job) => (
                  <tr key={job.job_id} className="hover:bg-gray-50/50">
                    <td className="px-5 py-3.5 text-sm font-medium text-gray-900">{job.file_name}</td>
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${getStatusBadge(job.status)}`}>
                        {job.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-gray-600">{job.records_extracted || '—'}</td>
                    <td className="px-5 py-3.5 text-sm text-gray-600">
                      {job.confidence ? `${Math.round(job.confidence * 100)}%` : '—'}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-gray-500">
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {jobs.length === 0 && uploadQueue.length === 0 && (
        <div className="text-center py-12">
          <p className="text-sm text-gray-500">No extractions yet. Upload a clinical PDF to get started.</p>
        </div>
      )}
    </div>
  );
}
