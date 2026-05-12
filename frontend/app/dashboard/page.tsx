'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import ExtractionDashboard from '@/components/extraction-dashboard';
import ExtractionConfig from '@/components/extraction-config';
import { useAuth } from '@/lib/auth-context';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'upload' | 'config'>('upload');
  const { user, logout } = useAuth();

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        {/* Navigation */}
        <nav className="bg-white border-b border-gray-200">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 items-center justify-between">
              <div className="flex items-center space-x-8">
                <h1 className="text-xl font-semibold text-gray-900">EHR Query Engine</h1>
                <div className="hidden md:flex space-x-1">
                  <a
                    href="/dashboard"
                    className="px-3 py-2 rounded-md text-sm font-medium bg-gray-100 text-gray-900"
                  >
                    Dashboard
                  </a>
                  <a
                    href="/clinical-query"
                    className="px-3 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  >
                    Clinical Query
                  </a>
                  <a
                    href="/cohort-search"
                    className="px-3 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  >
                    Cohort Search
                  </a>
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{user?.username}</p>
                  <p className="text-xs text-gray-500">{user?.role}</p>
                </div>
                <button
                  onClick={logout}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
                >
                  Sign out
                </button>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {/* Tab Navigation */}
          <div className="border-b border-gray-200 mb-8">
            <nav className="flex space-x-8">
              <button
                onClick={() => setActiveTab('upload')}
                className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'upload'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Upload &amp; Extract
              </button>
              <button
                onClick={() => setActiveTab('config')}
                className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'config'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Settings
              </button>
            </nav>
          </div>

          {/* Tab Content */}
          {activeTab === 'upload' ? <ExtractionDashboard /> : <ExtractionConfig />}
        </main>
      </div>
    </ProtectedRoute>
  );
}
