'use client';

import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '@/lib/api-client';

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

export default function ExtractionDashboard() {
  const [jobs, setJobs] = useState<ExtractionJob[]>([]);
  const [stats, setStats] = useState<ExtractionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const fetchJobs = async () => {
    try {
      const data = await apiGet('/extraction/jobs?limit=50');
      setJobs(data.jobs || []);
    } catch (err) {
      setError('Failed to load jobs');
    }
  };

  const fetchStats = async () => {
    try {
      const data = await apiGet('/extraction/stats');
      setStats(data);
    } catch (err) {
      setError('Failed to load stats');
    }
  };

  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadResult('Only PDF files are accepted');
      return;
    }
    setUploading(true);
    setUploadResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
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
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await response.json();
      setUploadResult(
        data.status === 'completed'
          ? `Extracted ${data.records_extracted} records (${(data.confidence * 100).toFixed(0)}% confidence)`
          : data.status === 'failed'
          ? `Extraction failed: ${data.error_message}`
          : `Processing: ${data.status}`
      );
      fetchJobs();
      fetchStats();
    } catch (err: any) {
      setUploadResult(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = '';
  };

  useEffect(() => {
    fetchJobs();
    fetchStats();
    const interval = setInterval(() => {
      fetchJobs();
      fetchStats();
    }, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'processing': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (error) {
    return <div className="text-red-600 p-4">{error}</div>;
  }

  return (
    <div className="space-y-6">
      {/* PDF Upload */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
        }`}
      >
        <div className="space-y-3">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <div>
            <p className="text-lg font-medium text-gray-700">
              {uploading ? 'Processing PDF…' : 'Drop a clinical PDF here'}
            </p>
            <p className="text-sm text-gray-500 mt-1">or click to select a file (max 50MB)</p>
          </div>
          <input
            type="file"
            accept=".pdf"
            onChange={onFileSelect}
            disabled={uploading}
            className="hidden"
            id="pdf-upload"
          />
          <label
            htmlFor="pdf-upload"
            className={`inline-block px-6 py-2 rounded-md text-sm font-medium cursor-pointer ${
              uploading
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {uploading ? 'Extracting…' : 'Select PDF'}
          </label>
        </div>
        {uploadResult && (
          <p className={`mt-3 text-sm ${uploadResult.includes('failed') || uploadResult.includes('Only') ? 'text-red-600' : 'text-green-600'}`}>
            {uploadResult}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-500">Total Jobs</div>
          <div className="text-2xl font-bold">{stats?.total_jobs || 0}</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-500">Completed</div>
          <div className="text-2xl font-bold text-green-600">{stats?.completed_jobs || 0}</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-500">Failed</div>
          <div className="text-2xl font-bold text-red-600">{stats?.failed_jobs || 0}</div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-500">Success Rate</div>
          <div className="text-2xl font-bold">{stats?.success_rate ? `${stats.success_rate.toFixed(1)}%` : '0%'}</div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">Extraction Jobs</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">File</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Records</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{job.file_name}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{job.records_extracted}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.confidence ? `${(job.confidence * 100).toFixed(0)}%` : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
