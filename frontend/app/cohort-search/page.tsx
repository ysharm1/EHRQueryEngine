'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import { cohortSearchService } from '@/lib/api-services';
import { useAuth } from '@/lib/auth-context';
import type { CohortSearchResult } from '@/types';

export default function CohortSearchPage() {
  const { user, logout } = useAuth();
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

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white shadow">
          <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Cohort Search</h1>
                <p className="mt-1 text-sm text-gray-600">
                  Find patients by searching clinical notes with natural language
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <a
                  href="/dashboard"
                  className="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
                >
                  Dashboard
                </a>
                <a
                  href="/clinical-query"
                  className="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
                >
                  Clinical Query
                </a>
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
              <p className="text-sm text-gray-600">
                {results.length} matching {results.length === 1 ? 'result' : 'results'}
              </p>
              {results.map((result, idx) => (
                <div
                  key={`${result.note_id}-${idx}`}
                  className="rounded-lg bg-white p-5 shadow"
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
        </main>
      </div>
    </ProtectedRoute>
  );
}
