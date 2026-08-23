'use client';

import Link from 'next/link';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';

const STEPS = [
  {
    step: '1',
    title: 'Add your data',
    href: '/dashboard',
    cta: 'Go to Data Sources',
    description:
      'Upload clinical PDFs or structured datasets (CSV/Excel). QueryAble extracts the data and organizes it by patient visit.',
  },
  {
    step: '2',
    title: 'De-identify it',
    href: '/deidentify',
    cta: 'Go to De-identify',
    description:
      'Remove the 18 HIPAA Safe Harbor identifiers automatically. Review flagged items, then download a compliance certificate — so the data is safe to use and share.',
  },
  {
    step: '3',
    title: 'Query & explore',
    href: '/query',
    cta: 'Go to Query',
    description:
      'Ask questions in plain English to build a dataset, or use advanced filters to explore records — with every value traceable back to its source document.',
  },
];

export default function OverviewPage() {
  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="mx-auto max-w-4xl">
            {/* Header */}
            <div className="mb-8">
              <h2 className="text-2xl font-semibold text-gray-900">Welcome to QueryAble</h2>
              <p className="mt-2 max-w-2xl text-sm text-gray-600">
                QueryAble turns raw clinical records into de-identified, research-ready data you can
                query in plain English. Here&rsquo;s how it works, in three steps.
              </p>
            </div>

            {/* Pipeline steps */}
            <div className="space-y-4">
              {STEPS.map((s) => (
                <div
                  key={s.step}
                  className="flex items-start gap-5 rounded-lg border border-gray-100 bg-white p-6 shadow-sm"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-base font-semibold text-white">
                    {s.step}
                  </div>
                  <div className="flex-1">
                    <h3 className="text-base font-semibold text-gray-900">{s.title}</h3>
                    <p className="mt-1 text-sm text-gray-600">{s.description}</p>
                    <Link
                      href={s.href}
                      className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700"
                    >
                      {s.cta}
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                      </svg>
                    </Link>
                  </div>
                </div>
              ))}
            </div>

            {/* Trust footer */}
            <div className="mt-8 rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <p className="text-sm text-gray-600">
                Every de-identification and query is logged with a tamper-evident audit trail, and
                the de-identification method used is <span className="font-medium">HIPAA Safe Harbor</span>.
              </p>
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
