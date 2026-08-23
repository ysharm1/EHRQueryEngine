'use client';

import { useState, useEffect } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import ChatInterface from '@/components/chat-interface';
import DatasetExplorer from '@/components/dataset-explorer';
import DatasetExport from '@/components/dataset-export';
import ClinicalQueryFiltersPanel from '@/components/clinical-query-filters';
import EncounterBrowser from '@/components/encounter-browser';
import AggregationResults from '@/components/aggregation-results';
import ProvenanceDetailPanel from '@/components/provenance-detail';
import { apiGet } from '@/lib/api-client';
import { clinicalQueryService } from '@/lib/api-services';
import type {
  ClinicalQueryFilters,
  ClinicalQueryResponse,
  AggregatedMetric,
} from '@/types';

interface TableInfo {
  table_name?: string;
  name?: string;
  row_count: number;
  columns: string[];
}

type QueryMode = 'ask' | 'advanced';

export default function QueryPage() {
  const [mode, setMode] = useState<QueryMode>('ask');

  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="mx-auto max-w-5xl">
            {/* Page header */}
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Query</h2>
              <p className="mt-1 text-sm text-gray-500">
                Ask questions about your de-identified data in plain English, or use advanced
                filters to explore clinical records with full source traceability.
              </p>
            </div>

            {/* Mode tabs */}
            <div className="mb-6 inline-flex rounded-lg border border-gray-200 p-0.5">
              <button
                type="button"
                onClick={() => setMode('ask')}
                className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                  mode === 'ask' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                Ask (Natural Language)
              </button>
              <button
                type="button"
                onClick={() => setMode('advanced')}
                className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                  mode === 'advanced' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                Advanced (Filters)
              </button>
            </div>

            {mode === 'ask' ? <AskPanel /> : <AdvancedPanel />}
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}

/* ------------------------------------------------------------------ */
/* Ask — natural-language query → dataset (formerly Query Builder)     */
/* ------------------------------------------------------------------ */

function AskPanel() {
  const [currentDatasetId, setCurrentDatasetId] = useState<string | null>(null);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loadingTables, setLoadingTables] = useState(true);

  useEffect(() => {
    apiGet('/api/tables')
      .then((data) => setTables(data.tables || []))
      .catch(() => setTables([]))
      .finally(() => setLoadingTables(false));
  }, []);

  const loaded = tables.filter((t) => t.row_count > 0);

  return (
    <div>
      <p className="mb-4 text-sm text-gray-500">
        Describe the dataset you need in plain English and get analysis-ready results back.
      </p>

      {/* Available Tables */}
      <div className="mb-6 rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-medium text-gray-700">Available Datasets</h3>
        {loadingTables ? (
          <p className="text-xs text-gray-400">Loading…</p>
        ) : loaded.length === 0 ? (
          <p className="text-xs text-gray-400">
            No datasets loaded. Add data on the Data Sources page first.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {loaded
              .sort((a, b) => b.row_count - a.row_count)
              .map((t) => (
                <div
                  key={t.table_name || t.name}
                  className="flex items-center justify-between rounded-md border border-gray-150 bg-gray-50 px-3 py-2"
                >
                  <span className="truncate text-sm font-medium text-gray-800">
                    {t.table_name || t.name}
                  </span>
                  <span className="ml-2 shrink-0 text-xs text-gray-500">
                    {t.row_count?.toLocaleString()}
                  </span>
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
  );
}

/* ------------------------------------------------------------------ */
/* Advanced — filters + aggregation + provenance (formerly Patient    */
/* Analytics)                                                          */
/* ------------------------------------------------------------------ */

function AdvancedPanel() {
  const [filters, setFilters] = useState<ClinicalQueryFilters>({ limit: 100, offset: 0 });
  const [queryResult, setQueryResult] = useState<ClinicalQueryResponse | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  const [metricName, setMetricName] = useState('');
  const [dataType, setDataType] = useState<'vitals' | 'labs'>('vitals');
  const [aggGroups, setAggGroups] = useState<AggregatedMetric[]>([]);
  const [aggLoading, setAggLoading] = useState(false);

  const [selectedProvenanceId, setSelectedProvenanceId] = useState<string | null>(null);
  const [selectedEncounterId, setSelectedEncounterId] = useState<string | undefined>();

  const runQuery = async () => {
    setQueryLoading(true);
    setQueryError(null);
    try {
      setQueryResult(await clinicalQueryService.query(filters));
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
    if (provenanceIds.length > 0) setSelectedProvenanceId(provenanceIds[0]);
  };

  const handleRowProvenanceClick = (recordId: string) => {
    if (queryResult?.provenance_refs[recordId]) {
      setSelectedProvenanceId(queryResult.provenance_refs[recordId]);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
      {/* Left — filters */}
      <div className="space-y-6 lg:col-span-1">
        <ClinicalQueryFiltersPanel filters={filters} onChange={setFilters} onSubmit={runQuery} />
      </div>

      {/* Main */}
      <div className="space-y-6 lg:col-span-3">
        <EncounterBrowser
          onSelectEncounter={handleEncounterSelect}
          selectedEncounterId={selectedEncounterId}
        />

        {/* Aggregation controls */}
        <div className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-base font-semibold text-gray-900">Metric Aggregation</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Metric Name</label>
              <input
                type="text"
                value={metricName}
                onChange={(e) => setMetricName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runAggregation()}
                className="rounded border px-3 py-2 text-sm"
                placeholder="e.g. GCS, Hemoglobin"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Data Type</label>
              <select
                value={dataType}
                onChange={(e) => setDataType(e.target.value as 'vitals' | 'labs')}
                className="rounded border px-3 py-2 text-sm"
              >
                <option value="vitals">Vitals</option>
                <option value="labs">Labs</option>
              </select>
            </div>
            <button
              onClick={runAggregation}
              disabled={aggLoading || !metricName.trim()}
              className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {aggLoading ? 'Loading…' : 'Aggregate'}
            </button>
          </div>
        </div>

        <AggregationResults
          groups={aggGroups}
          loading={aggLoading}
          onProvenanceClick={handleProvenanceClick}
        />

        {queryLoading && (
          <div className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
            <p className="text-sm text-gray-400">Running query…</p>
          </div>
        )}
        {queryError && (
          <div className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
            <p className="text-sm text-red-600">{queryError}</p>
          </div>
        )}
        {queryResult && !queryLoading && (
          <div className="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
            <h3 className="mb-2 text-base font-semibold text-gray-900">
              Query Results ({queryResult.total_count} rows)
            </h3>
            {queryResult.rows.length === 0 ? (
              <p className="text-sm text-gray-400">No results match your filters.</p>
            ) : (
              <div className="max-h-96 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-gray-50">
                    <tr>
                      {Object.keys(queryResult.rows[0]).map((col) => (
                        <th key={col} className="px-3 py-2 text-left font-medium uppercase text-gray-500">
                          {col}
                        </th>
                      ))}
                      <th className="px-3 py-2 text-center font-medium uppercase text-gray-500">
                        Provenance
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {queryResult.rows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        {Object.values(row).map((val, ci) => (
                          <td key={ci} className="whitespace-nowrap px-3 py-1.5">
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

        <ProvenanceDetailPanel
          provenanceId={selectedProvenanceId}
          onClose={() => setSelectedProvenanceId(null)}
        />
      </div>
    </div>
  );
}
