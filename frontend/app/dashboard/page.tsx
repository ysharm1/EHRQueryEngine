'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import ChatInterface from '@/components/chat-interface';
import DatasetExplorer from '@/components/dataset-explorer';
import DatasetExport from '@/components/dataset-export';
import { DataUpload } from '@/components/data-upload';
import ExtractionDashboard from '@/components/extraction-dashboard';
import ExtractionConfig from '@/components/extraction-config';
import { useAuth } from '@/lib/auth-context';

export default function DashboardPage() {
  const [currentDatasetId, setCurrentDatasetId] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [activeTab, setActiveTab] = useState<'extraction' | 'config'>('extraction');
  const { user, logout } = useAuth();

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white shadow">
          <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Research Dataset Builder
                </h1>
                <p className="mt-1 text-sm text-gray-600">
                  Generate structured datasets from multimodal research data
                </p>
              </div>
              
              <div className="flex items-center space-x-4">
                <a
                  href="/clinical-query"
                  className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                  Clinical Query
                </a>
                <button
                  onClick={() => setShowUpload(!showUpload)}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  {showUpload ? 'Hide Upload' : 'Upload Data'}
                </button>
                
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{user?.username}</p>
                  <p className="text-xs text-gray-600">{user?.role}</p>
                </div>
                
                <button
                  onClick={logout}
                  className="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="space-y-8">
            {/* Extraction Dashboard Tabs */}
            <section>
              <div className="flex gap-4 mb-6">
                <button
                  onClick={() => setActiveTab('extraction')}
                  className={`px-4 py-2 rounded ${activeTab === 'extraction' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                >
                  Extraction Dashboard
                </button>
                <button
                  onClick={() => setActiveTab('config')}
                  className={`px-4 py-2 rounded ${activeTab === 'config' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                >
                  Configuration
                </button>
              </div>

              {activeTab === 'extraction' ? <ExtractionDashboard /> : <ExtractionConfig />}
            </section>

            {/* Data Upload Section */}
            {showUpload && (
              <section>
                <DataUpload onUploadComplete={() => {
                  setShowUpload(false);
                  // Optionally refresh available tables
                }} />
              </section>
            )}

            {/* Chat Interface */}
            <section>
              <ChatInterface onDatasetCreated={setCurrentDatasetId} />
            </section>

            {/* Dataset Explorer and Export */}
            {currentDatasetId && (
              <>
                <section>
                  <DatasetExplorer datasetId={currentDatasetId} />
                </section>

                <section>
                  <DatasetExport datasetId={currentDatasetId} />
                </section>
              </>
            )}

            {/* Help Section */}
            {!currentDatasetId && !showUpload && activeTab === 'extraction' && (
              <section className="rounded-lg bg-white p-6 shadow">
                <h2 className="mb-4 text-lg font-semibold text-gray-900">
                  Getting Started
                </h2>
                
                <div className="space-y-4">
                  <div>
                    <h3 className="font-medium text-gray-900">1. Upload Your Data (Optional)</h3>
                    <p className="mt-1 text-sm text-gray-600">
                      Click "Upload Data" to import your own CSV, Excel, JSON, or Parquet files.
                      The system will automatically detect the schema and make it queryable.
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="font-medium text-gray-900">2. Enter Your Query</h3>
                    <p className="mt-1 text-sm text-gray-600">
                      Describe your research question in natural language. For example:
                      "Find all Parkinson's patients with DBS surgery"
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="font-medium text-gray-900">3. Review Parsed Intent</h3>
                    <p className="mt-1 text-sm text-gray-600">
                      The system will parse your query and show the extracted cohort criteria
                      and variables. If the confidence is low, you'll be asked to clarify.
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="font-medium text-gray-900">4. Explore Your Dataset</h3>
                    <p className="mt-1 text-sm text-gray-600">
                      Once generated, you can preview the dataset, view metadata, and explore
                      the schema and query provenance.
                    </p>
                  </div>
                  
                  <div>
                    <h3 className="font-medium text-gray-900">5. Export Your Data</h3>
                    <p className="mt-1 text-sm text-gray-600">
                      Choose your preferred format (CSV, Parquet, or JSON) and download the
                      dataset along with schema and provenance files.
                    </p>
                  </div>
                </div>

                <div className="mt-6 rounded-lg bg-blue-50 p-4">
                  <h3 className="text-sm font-semibold text-blue-800">Example Queries</h3>
                  <ul className="mt-2 space-y-1 text-sm text-blue-700">
                    <li>• "Patients with diabetes and hypertension over age 50"</li>
                    <li>• "Subjects with MRI scans and cognitive test scores"</li>
                    <li>• "Cancer patients who received chemotherapy in 2023"</li>
                    <li>• "All observations for subjects in the treatment group"</li>
                  </ul>
                </div>
              </section>
            )}
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}