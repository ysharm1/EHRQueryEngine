'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ChatInterface from '@/components/chat-interface';
import DatasetExplorer from '@/components/dataset-explorer';
import DatasetExport from '@/components/dataset-export';

export default function QueryBuilderPage() {
  const [currentDatasetId, setCurrentDatasetId] = useState<string | null>(null);

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
