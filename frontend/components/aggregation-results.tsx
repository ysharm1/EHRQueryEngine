'use client';

import type { AggregatedMetric } from '@/types';

interface AggregationResultsProps {
  groups: AggregatedMetric[];
  loading: boolean;
  onProvenanceClick?: (provenanceIds: string[]) => void;
}

export default function AggregationResults({
  groups,
  loading,
  onProvenanceClick,
}: AggregationResultsProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Aggregation Results</h3>
        <p className="text-gray-400 text-sm">Loading…</p>
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Aggregation Results</h3>
        <p className="text-gray-400 text-sm">No aggregation data to display. Run a query with a metric name to see results.</p>
      </div>
    );
  }

  const fmt = (v: number | null) => (v != null ? v.toFixed(2) : '—');

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Aggregation Results</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Encounter</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Metric</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Min</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Max</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Avg</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Count</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Provenance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {groups.map((g, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                <td className="px-4 py-2 whitespace-nowrap">{g.group_label || g.group_key}</td>
                <td className="px-4 py-2 whitespace-nowrap">{g.metric_name}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(g.min)}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(g.max)}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap">{fmt(g.avg)}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap">{g.count}</td>
                <td className="px-4 py-2 text-center whitespace-nowrap">
                  {g.provenance_ids && g.provenance_ids.length > 0 && onProvenanceClick ? (
                    <button
                      onClick={() => onProvenanceClick(g.provenance_ids)}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      View ({g.provenance_ids.length})
                    </button>
                  ) : (
                    <span className="text-gray-300 text-xs">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
