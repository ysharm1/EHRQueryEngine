'use client';

import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ExtractionConfig from '@/components/extraction-config';

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="max-w-4xl mx-auto">
            {/* Page header */}
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900">Settings</h2>
              <p className="text-sm text-gray-500 mt-1">Configure extraction parameters and system preferences.</p>
            </div>

            <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-6">
              <ExtractionConfig />
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
