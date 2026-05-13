'use client';

import { useState, useEffect } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ExtractionDashboard from '@/components/extraction-dashboard';
import { DataUpload } from '@/components/data-upload';
import { apiGet } from '@/lib/api-client';

interface TableInfo {
  table_name: string;
  row_count: number;
  columns: string[];
}

export default function DashboardPage() {
  const [tables, setTables] = useState<TableInfo[]>([]);

  const refreshTables = () => {
    apiGet('/api/tables')
      .then((data) => setTables(data.tables || []))
      .catch(() => setTables([]));
  };

  useEffect(() => { refreshTables(); }, []);

  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="max-w-5xl mx-auto space-y-10">
            {/* Page header */}
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Data Sources</h2>
              <p className="text-sm text-gray-500 mt-1">Upload and manage your clinical documents and structured datasets.</p>
            </div>

            {/* Available Data summary */}
            {tables.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Loaded Datasets</h3>
                <div className="flex flex-wrap gap-2">
                  {tables.map((t) => (
                    <span
                      key={t.table_name}
                      className="inline-flex items-center gap-1.5 rounded-md bg-green-50 border border-green-200 px-2.5 py-1 text-xs"
                    >
                      <span className="font-medium text-green-800">{t.table_name}</span>
                      <span className="text-green-600">({t.row_count?.toLocaleString()} rows)</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Clinical PDFs section */}
            <section>
              <h3 className="text-base font-medium text-gray-800 mb-4">Clinical PDFs</h3>
              <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-6">
                <ExtractionDashboard />
              </div>
            </section>

            {/* Structured Data section */}
            <section>
              <h3 className="text-base font-medium text-gray-800 mb-4">Structured Data</h3>
              <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-6">
                <DataUpload />
              </div>
            </section>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
