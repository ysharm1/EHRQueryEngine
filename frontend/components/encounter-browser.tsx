'use client';

import { useState } from 'react';
import { clinicalQueryService } from '@/lib/api-services';
import type { Encounter } from '@/types';

interface EncounterBrowserProps {
  onSelectEncounter: (encounterId: string) => void;
  selectedEncounterId?: string;
}

export default function EncounterBrowser({
  onSelectEncounter,
  selectedEncounterId,
}: EncounterBrowserProps) {
  const [patientId, setPatientId] = useState('');
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    if (!patientId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await clinicalQueryService.getEncounters(patientId.trim());
      setEncounters(data.encounters);
      setSearched(true);
    } catch {
      setError('Failed to load encounters');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Encounter Browser</h3>

      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          className="flex-1 px-3 py-2 border rounded text-sm"
          placeholder="Enter Patient ID"
        />
        <button
          onClick={search}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Loading…' : 'Search'}
        </button>
      </div>

      {error && <p className="text-red-600 text-sm mb-2">{error}</p>}

      {searched && encounters.length === 0 && !loading && (
        <p className="text-gray-400 text-sm">No encounters found for this patient.</p>
      )}

      {encounters.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Provider</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Data Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {encounters.map((enc) => (
                <tr
                  key={enc.encounter_id}
                  onClick={() => onSelectEncounter(enc.encounter_id)}
                  className={`cursor-pointer hover:bg-blue-50 transition-colors ${
                    selectedEncounterId === enc.encounter_id ? 'bg-blue-100' : ''
                  }`}
                >
                  <td className="px-4 py-2 whitespace-nowrap">
                    {enc.encounter_date
                      ? new Date(enc.encounter_date).toLocaleDateString()
                      : '—'}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">{enc.encounter_type || '—'}</td>
                  <td className="px-4 py-2 whitespace-nowrap">{enc.primary_provider || '—'}</td>
                  <td className="px-4 py-2 whitespace-nowrap">{enc.data_point_count ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
