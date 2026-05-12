'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import { cohortSearchService } from '@/lib/api-services';
import type { CohortSearchResult } from '@/types';

export default function CohortSearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CohortSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const response = await cohortSearchService.search(query.trim());
      setResults(response.results);
    } catch {
      setError('Search failed. Please try again.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const formatScore = (score: number): string => {
    return `${Math.round(score * 100)}% match`;
  };

  const exportCSV = () => {
    if (results.length === 0) return;
    const headers = ['patient_id', 'relevant_sentence', 'note_date', 'similarity_score'];
    const rows = results.map((r) => [
      r.patient_id,
      `"${(r.relevant_sentence || '').replace(/"/g, '""')}"`,
      r.note_date || '',
      r.similarity_score.toFixed(4),
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cohort_search_${query.replace(/\s+/g, '_').slice(0, 30)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="max-w-4xl mx-auto">
            {/* Page header */}
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900">Cohort Search</h2>
              <p className="text-sm text-gray-500 mt-1">Search across clinical notes using natural language to identify patient cohorts.</p>
            </div>

            {/* Search Form */}
            <form onSubmit={handleSearch} className="mb-8">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g., GI bleeding while on anticoagulation"
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Searching…' : 'Search'}
                </button>
              </div>
            </form>

            {/* Error State */}
            {error && (
              <div className="mb-6 rounded-lg bg-red-50 p-4">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
                  <p className="mt-3 text-sm text-gray-600">Searching clinical notes…</p>
                </div>
              </div>
            )}

            {/* Results */}
            {!loading && hasSearched && results.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-600">
                    {results.length} matching {results.length === 1 ? 'result' : 'results'}
                  </p>
                  <button
                    onClick={exportCSV}
                    className="inline-flex items-center px-3 py-1.5 rounded-md border border-gray-200 bg-white text-xs font-medium text-gray-700 hover:bg-gray-50 shadow-sm"
                  >
                    Export CSV
                  </button>
                </div>
                {results.map((result, idx) => (
                  <div
                    key={`${result.note_id}-${idx}`}
                    className="rounded-lg bg-white border border-gray-100 p-5 shadow-sm"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                            {result.patient_id}
                          </span>
                          {result.note_date && (
                            <span className="text-xs text-gray-500">
                              {new Date(result.note_date).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-800 leading-relaxed">
                          {result.relevant_sentence}
                        </p>
                      </div>
                      <span className="ml-4 inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 whitespace-nowrap">
                        {formatScore(result.similarity_score)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Empty State */}
            {!loading && hasSearched && results.length === 0 && !error && (
              <div className="text-center py-12">
                <p className="text-sm text-gray-500">
                  No matching patients found. Try a different search query.
                </p>
              </div>
            )}

            {/* Initial State */}
            {!hasSearched && !loading && (
              <div className="text-center py-12">
                <p className="text-sm text-gray-500">
                  Enter a clinical query above to search across patient notes.
                </p>
                <div className="mt-4 space-y-1">
                  <p className="text-xs text-gray-400">Example searches:</p>
                  <p className="text-xs text-gray-400">&quot;GI bleeding while on anticoagulation&quot;</p>
                  <p className="text-xs text-gray-400">&quot;diabetes with renal complications&quot;</p>
                  <p className="text-xs text-gray-400">&quot;chest pain with elevated troponin&quot;</p>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
