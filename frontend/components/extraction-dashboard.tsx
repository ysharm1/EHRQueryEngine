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
