'use client';

import { useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import ClinicalQueryFiltersPanel from '@/components/clinical-query-filters';
import EncounterBrowser from '@/components/encounter-browser';
import AggregationResults from '@/components/aggregation-results';
import ProvenanceDetailPanel from '@/components/provenance-detail';
import { clinicalQueryService } from '@/lib/api-services';
import { useAuth } from '@/lib/auth-context';
import type {
  ClinicalQueryFilters,
  ClinicalQueryResponse,
  AggregatedMetric,
} from '@/types';

export default function ClinicalQueryPage() {
  const { user, logout } = useAuth();

  // Filters
  const [filters, setFilters] = useState<ClinicalQueryFilters>({ limit: 100, offset: 0 });

  // Query results
  const [queryResult, setQueryResult] = useState<ClinicalQueryResponse | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Aggregation
  const [metricName, setMetricName] = useState('');
  const [dataType, setDataType] = useState<'vitals' | 'labs'>('vitals');
  const [aggGroups, setAggGroups] = useState<AggregatedMetric[]>([]);
  const [aggLoading, setAggLoading] = useState(false);

  // Provenance
  const [selectedProvenanceId, setSelectedProvenanceId] = useState<string | null>(null);

  // Encounter selection
  const [selectedEncounterId, setSelectedEncounterId] = useState<string | undefined>();

  const runQuery = async () => {
    setQueryLoading(true);
    setQueryError(null);
    try {
      const result = await clinicalQueryService.query(filters);
      setQueryResult(result);
    } catch {
      setQueryError('Query failed. Check your filters and try again.');
    } finally {
      setQueryLoading(false);
    }
  };

  const runAggregation = async () => {
    if (!metricName.trim()) return;
    setAggLoading(true);
    try {
      const result = await clinicalQueryService.aggregate({
        patient_id: filters.patient_id,
        encounter_id: selectedEncounterId,
        date_from: filters.date_from,
        date_to: filters.date_to,
        provider_types: filters.provider_types,
        metric_name: metricName.trim(),
        data_type: dataType,
        aggregations: ['min', 'max', 'avg', 'count'],
        group_by: 'encounter',
      });
      setAggGroups(result.groups || []);
    } catch {
      setAggGroups([]);
    } finally {
      setAggLoading(false);
    }
  };

  const handleEncounterSelect = (encounterId: string) => {
    setSelectedEncounterId(encounterId);
    setFilters((prev) => ({ ...prev, encounter_id: encounterId }));
  };

  const handleProvenanceClick = (provenanceIds: string[]) => {
    if (provenanceIds.length > 0) {
      setSelectedProvenanceId(provenanceIds[0]);
    }
  };

  const handleRowProvenanceClick = (recordId: string) => {
    if (queryResult?.provenance_refs[recordId]) {
      setSelectedProvenanceId(queryResult.provenance_refs[recordId]);
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white shadow">
          <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Clinical Query</h1>
                <p className="mt-1 text-sm text-gray-600">
                  Browse encounters, filter clinical data, and trace provenance
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <a
                  href="/dashboard"
                  className="rounded-md bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300"
                >
                  Dashboard
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
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Left sidebar — filters */}
            <div className="lg:col-span-1 space-y-6">
              <ClinicalQueryFiltersPanel
                filters={filters}
                onChange={setFilters}
                onSubmit={runQuery}
              />
            </div>

            {/* Main area */}
            <div className="lg:col-span-3 space-y-6">
              {/* Encounter Browser */}
              <EncounterBrowser
                onSelectEncounter={handleEncounterSelect}
                selectedEncounterId={selectedEncounterId}
              />

              {/* Aggregation Controls */}
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Metric Aggregation</h3>
                <div className="flex flex-wrap gap-3 items-end">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Metric Name</label>
                    <input
                      type="text"
                      value={metricName}
                      onChange={(e) => setMetricName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && runAggregation()}
                      className="px-3 py-2 border rounded text-sm"
                      placeholder="e.g. GCS, Hemoglobin"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Data Type</label>
                    <select
                      value={dataType}
                      onChange={(e) => setDataType(e.target.value as 'vitals' | 'labs')}
                      className="px-3 py-2 border rounded text-sm"
                    >
                      <option value="vitals">Vitals</option>
                      <option value="labs">Labs</option>
                    </select>
                  </div>
                  <button
                    onClick={runAggregation}
                    disabled={aggLoading || !metricName.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                  >
                    {aggLoading ? 'Loading…' : 'Aggregate'}
                  </button>
                </div>
              </div>

              {/* Aggregation Results */}
              <AggregationResults
                groups={aggGroups}
                loading={aggLoading}
                onProvenanceClick={handleProvenanceClick}
              />

              {/* Query Results */}
              {queryLoading && (
                <div className="bg-white rounded-lg shadow p-6">
                  <p className="text-gray-400 text-sm">Running query…</p>
                </div>
              )}
              {queryError && (
                <div className="bg-white rounded-lg shadow p-6">
                  <p className="text-red-600 text-sm">{queryError}</p>
                </div>
              )}
              {queryResult && !queryLoading && (
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Query Results ({queryResult.total_count} rows)
                  </h3>
                  {queryResult.rows.length === 0 ? (
                    <p className="text-gray-400 text-sm">No results match your filters.</p>
                  ) : (
                    <div className="overflow-x-auto max-h-96">
                      <table className="w-full text-xs">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            {Object.keys(queryResult.rows[0]).map((col) => (
                              <th
                                key={col}
                                className="px-3 py-2 text-left font-medium text-gray-500 uppercase"
                              >
                                {col}
                              </th>
                            ))}
                            <th className="px-3 py-2 text-center font-medium text-gray-500 uppercase">
                              Provenance
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {queryResult.rows.map((row, idx) => (
                            <tr key={idx} className="hover:bg-gray-50">
                              {Object.values(row).map((val, ci) => (
                                <td key={ci} className="px-3 py-1.5 whitespace-nowrap">
                                  {val != null ? String(val) : '—'}
                                </td>
                              ))}
                              <td className="px-3 py-1.5 text-center">
                                {row.id && queryResult.provenance_refs[String(row.id)] ? (
                                  <button
                                    onClick={() => handleRowProvenanceClick(String(row.id))}
                                    className="text-blue-600 hover:underline"
                                  >
                                    View
                                  </button>
                                ) : (
                                  <span className="text-gray-300">—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Provenance Detail */}
              <ProvenanceDetailPanel
                provenanceId={selectedProvenanceId}
                onClose={() => setSelectedProvenanceId(null)}
              />
            </div>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
