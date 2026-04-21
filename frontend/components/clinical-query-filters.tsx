'use client';

import { useState, useEffect } from 'react';
import { clinicalQueryService } from '@/lib/api-services';
import type { ClinicalQueryFilters } from '@/types';

const DATA_TYPES = [
  { key: 'vitals', label: 'Vitals' },
  { key: 'labs', label: 'Labs' },
  { key: 'diagnoses', label: 'Diagnoses' },
  { key: 'procedures', label: 'Procedures' },
  { key: 'medications', label: 'Medications' },
  { key: 'notes', label: 'Notes' },
  { key: 'imaging', label: 'Imaging' },
];

interface ClinicalQueryFiltersProps {
  filters: ClinicalQueryFilters;
  onChange: (filters: ClinicalQueryFilters) => void;
  onSubmit: () => void;
}

export default function ClinicalQueryFiltersPanel({
  filters,
  onChange,
  onSubmit,
}: ClinicalQueryFiltersProps) {
  const [providerTypes, setProviderTypes] = useState<string[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);

  useEffect(() => {
    setLoadingProviders(true);
    clinicalQueryService
      .getProviderTypes()
      .then(setProviderTypes)
      .catch(() => setProviderTypes([]))
      .finally(() => setLoadingProviders(false));
  }, []);

  const toggleProviderType = (pt: string) => {
    const current = filters.provider_types || [];
    const next = current.includes(pt)
      ? current.filter((t) => t !== pt)
      : [...current, pt];
    onChange({ ...filters, provider_types: next.length ? next : undefined });
  };

  const toggleDataType = (dt: string) => {
    const current = filters.data_types || [];
    const next = current.includes(dt)
      ? current.filter((t) => t !== dt)
      : [...current, dt];
    onChange({ ...filters, data_types: next.length ? next : undefined });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') onSubmit();
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-5">
      <h3 className="text-lg font-semibold text-gray-900">Filters</h3>

      {/* Patient ID */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Patient ID</label>
        <input
          type="text"
          value={filters.patient_id || ''}
          onChange={(e) => onChange({ ...filters, patient_id: e.target.value || undefined })}
          onKeyDown={handleKeyDown}
          className="w-full px-3 py-2 border rounded text-sm"
          placeholder="e.g. patient-123"
        />
      </div>

      {/* Date Range */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Date From</label>
          <input
            type="date"
            value={filters.date_from || ''}
            onChange={(e) => onChange({ ...filters, date_from: e.target.value || undefined })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Date To</label>
          <input
            type="date"
            value={filters.date_to || ''}
            onChange={(e) => onChange({ ...filters, date_to: e.target.value || undefined })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
      </div>

      {/* Provider Types */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Provider Types</label>
        {loadingProviders ? (
          <p className="text-sm text-gray-400">Loading…</p>
        ) : providerTypes.length === 0 ? (
          <p className="text-sm text-gray-400">No provider types found</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {providerTypes.map((pt) => (
              <label key={pt} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={(filters.provider_types || []).includes(pt)}
                  onChange={() => toggleProviderType(pt)}
                  className="rounded border-gray-300"
                />
                {pt}
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Data Types */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Data Types</label>
        <div className="flex flex-wrap gap-2">
          {DATA_TYPES.map(({ key, label }) => {
            const active = (filters.data_types || []).includes(key);
            return (
              <button
                key={key}
                onClick={() => toggleDataType(key)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  active
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Submit */}
      <button
        onClick={onSubmit}
        className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium"
      >
        Search
      </button>
    </div>
  );
}
