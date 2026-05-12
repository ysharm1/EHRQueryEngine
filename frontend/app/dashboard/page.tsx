'use client';

import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ExtractionDashboard from '@/components/extraction-dashboard';
import { DataUpload } from '@/components/data-upload';

export default function DashboardPage() {
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
