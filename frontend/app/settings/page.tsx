'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ExtractionConfig from '@/components/extraction-config';

export default function SettingsPage() {
  const [resetting, setResetting] = useState(false);
  const [resetResult, setResetResult] = useState<string | null>(null);

  const handleReset = async () => {
    if (!confirm('This will permanently delete ALL uploaded data, extracted records, embeddings, and PDFs. This cannot be undone. Continue?')) return;
    if (!confirm('Are you absolutely sure? All data will be lost.')) return;

    setResetting(true);
    setResetResult(null);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/admin/reset`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
            'Content-Type': 'application/json',
          },
        }
      );
      if (!response.ok) throw new Error('Reset failed');
      const data = await response.json();
      setResetResult(`Reset complete. ${data.tables_dropped} tables dropped, ${data.files_deleted} files deleted.`);
    } catch {
      setResetResult('Reset failed. Check server logs.');
    } finally {
      setResetting(false);
    }
  };

  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="max-w-4xl mx-auto space-y-8">
            {/* Page header */}
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Settings</h2>
              <p className="text-sm text-gray-500 mt-1">Configure extraction parameters and system preferences.</p>
            </div>

            <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-6">
              <ExtractionConfig />
            </div>

            {/* Danger Zone */}
            <div className="bg-white rounded-lg border border-red-200 shadow-sm p-6">
              <h3 className="text-base font-semibold text-red-900 mb-2">Danger Zone</h3>
              <p className="text-sm text-gray-600 mb-4">
                Reset all data to start fresh. This deletes all uploaded files, extracted clinical data, embeddings, and query results. Cannot be undone.
              </p>
              <button
                onClick={handleReset}
                disabled={resetting}
                className="px-4 py-2 rounded-md bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {resetting ? 'Resetting…' : 'Reset All Data'}
              </button>
              {resetResult && (
                <p className={`mt-3 text-sm ${resetResult.includes('failed') ? 'text-red-600' : 'text-green-600'}`}>
                  {resetResult}
                </p>
              )}
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
