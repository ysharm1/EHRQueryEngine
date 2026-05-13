'use client';

import { useState, useEffect } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ChatInterface from '@/components/chat-interface';
import DatasetExplorer from '@/components/dataset-explorer';
import DatasetExport from '@/components/dataset-export';
import { apiGet } from '@/lib/api-client';

interface TableInfo {
  table_name: string;
  row_count: number;
  columns: string[];
}

export default function QueryBuilderPage() {
  const [currentDatasetId, setCurrentDatasetId] = useState<string | null>(null);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loadingTables, setLoadingTables] = useState(true);

  useEffect(() => {
    apiGet('/api/tables')
      .then((data) => setTables(data.tables || []))
      .catch(() => setTables([]))
      .finally(() => setLoadingTables(false));
  }, []);

  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="max-w-5xl mx-auto">
            {/* Page header */}
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900">Query Builder</h2>
              <p className="text-sm text-gray-500 mt-1">Use natural language to query your structured datasets. Describe what you need and get SQL-powered results.</p>
            </div>

            {/* Available Tables */}
            <div className="mb-6 bg-white rounded-lg border border-gray-100 shadow-sm p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Available Tables</h3>
              {loadingTables ? (
                <p className="text-xs text-gray-400">Loading…</p>
              ) : tables.length === 0 ? (
                <p className="text-xs text-gray-400">No tables found. Upload data on the Data Sources page first.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {tables.map((t) => (
                    <span
                      key={t.table_name}
                      className="inline-flex items-center gap-1.5 rounded-md bg-gray-50 border border-gray-200 px-2.5 py-1 text-xs"
                      title={`Columns: ${t.columns?.join(', ') || 'unknown'}`}
                    >
                      <span className="font-medium text-gray-800">{t.table_name}</span>
                      <span className="text-gray-400">({t.row_count?.toLocaleString()} rows)</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-8">
              <ChatInterface onDatasetCreated={setCurrentDatasetId} />
              {currentDatasetId && (
                <>
                  <DatasetExplorer datasetId={currentDatasetId} />
                  <DatasetExport datasetId={currentDatasetId} />
                </>
              )}
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
