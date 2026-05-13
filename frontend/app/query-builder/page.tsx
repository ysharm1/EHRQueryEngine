'use client';

import { useState, useEffect } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ChatInterface from '@/components/chat-interface';
import DatasetExplorer from '@/components/dataset-explorer';
import DatasetExport from '@/components/dataset-export';
import { apiGet } from '@/lib/api-client';

interface TableInfo {
  table_name?: string;
  name?: string;
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
              <h3 className="text-sm font-medium text-gray-700 mb-3">Available Datasets</h3>
              {loadingTables ? (
                <p className="text-xs text-gray-400">Loading…</p>
              ) : tables.filter((t) => t.row_count > 0).length === 0 ? (
                <p className="text-xs text-gray-400">No datasets loaded. Upload data on the Data Sources page first.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {tables
                    .filter((t) => t.row_count > 0)
                    .sort((a, b) => b.row_count - a.row_count)
                    .map((t) => (
                      <div
                        key={t.table_name || t.name}
                        className="flex items-center justify-between rounded-md bg-gray-50 border border-gray-150 px-3 py-2"
                      >
                        <span className="text-sm font-medium text-gray-800 truncate">{t.table_name || t.name}</span>
                        <span className="text-xs text-gray-500 ml-2 shrink-0">{t.row_count?.toLocaleString()}</span>
                      </div>
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
