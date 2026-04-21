'use client';

import { useState, useEffect } from 'react';
import { clinicalQueryService } from '@/lib/api-services';
import type { ProvenanceDetail } from '@/types';

interface ProvenanceDetailPanelProps {
  provenanceId: string | null;
  onClose: () => void;
}

export default function ProvenanceDetailPanel({
  provenanceId,
  onClose,
}: ProvenanceDetailPanelProps) {
  const [detail, setDetail] = useState<ProvenanceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!provenanceId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    clinicalQueryService
      .getProvenance(provenanceId)
      .then(setDetail)
      .catch(() => setError('Failed to load provenance'))
      .finally(() => setLoading(false));
  }, [provenanceId]);

  if (!provenanceId) return null;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Provenance Detail</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-sm"
          aria-label="Close provenance panel"
        >
          ✕
        </button>
      </div>

      {loading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {detail && (
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="font-medium text-gray-500">Source File</dt>
            <dd className="text-gray-900 break-all">{detail.source_file}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Page Number</dt>
            <dd className="text-gray-900">
              {detail.page_number != null ? detail.page_number : 'Page unknown'}
            </dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Provider Name</dt>
            <dd className="text-gray-900">{detail.provider_name || '—'}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Provider Type</dt>
            <dd className="text-gray-900">{detail.provider_type || '—'}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Extraction Confidence</dt>
            <dd className="text-gray-900">
              {detail.extraction_confidence != null
                ? `${(detail.extraction_confidence * 100).toFixed(0)}%`
                : '—'}
            </dd>
          </div>
          {detail.raw_snippet && (
            <div>
              <dt className="font-medium text-gray-500">Raw Snippet</dt>
              <dd className="mt-1 bg-gray-50 rounded p-3 text-gray-800 text-xs font-mono whitespace-pre-wrap">
                {detail.raw_snippet}
              </dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
