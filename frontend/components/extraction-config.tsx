'use client';

import { useState, useEffect } from 'react';
import { apiGet, apiPut } from '@/lib/api-client';

interface ExtractionConfig {
  watched_folders: string[];
  llm_provider: string;
  ocr_enabled: boolean;
  auto_process: boolean;
  extraction_hints: {
    facility?: string;
    ehr_system?: string;
  };
  sync: {
    mode: 'local_only' | 'hybrid';
    cloud_endpoint?: string;
  };
  retention_days: number;
}

export default function ExtractionConfig() {
  const [config, setConfig] = useState<ExtractionConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const data = await apiGet('/extraction/config');
      setConfig(data);
    } catch (err) {
      setError('Failed to load config');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await apiPut('/extraction/config', config);
      setError(null);
    } catch (err) {
      setError('Failed to save config');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-4">Loading...</div>;
  if (!config) return null;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Watched Folders</h3>
        <div className="space-y-2">
          {config.watched_folders.map((folder, idx) => (
            <div key={idx} className="flex gap-2">
              <input
                type="text"
                value={folder}
                onChange={(e) => {
                  const newFolders = [...config.watched_folders];
                  newFolders[idx] = e.target.value;
                  setConfig({ ...config, watched_folders: newFolders });
                }}
                className="flex-1 px-3 py-2 border rounded"
                placeholder="/path/to/pdf/folder"
              />
            </div>
          ))}
          <button
            onClick={() => setConfig({ ...config, watched_folders: [...config.watched_folders, ''] })}
            className="px-4 py-2 bg-blue-500 text-white rounded"
          >
            + Add Folder
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">LLM Provider</h3>
        <div className="flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              checked={config.llm_provider === 'openai'}
              onChange={() => setConfig({ ...config, llm_provider: 'openai' })}
            />
            OpenAI
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              checked={config.llm_provider === 'anthropic'}
              onChange={() => setConfig({ ...config, llm_provider: 'anthropic' })}
            />
            Anthropic
          </label>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Extraction Hints</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Facility Name</label>
            <input
              type="text"
              value={config.extraction_hints.facility || ''}
              onChange={(e) => setConfig({
                ...config,
                extraction_hints: { ...config.extraction_hints, facility: e.target.value }
              })}
              className="w-full px-3 py-2 border rounded"
              placeholder="e.g., General Hospital"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">EHR System</label>
            <select
              value={config.extraction_hints.ehr_system || ''}
              onChange={(e) => setConfig({
                ...config,
                extraction_hints: { ...config.extraction_hints, ehr_system: e.target.value }
              })}
              className="w-full px-3 py-2 border rounded"
            >
              <option value="">Unknown</option>
              <option value="cerner">Cerner</option>
              <option value="epic">Epic</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Sync Mode</h3>
        <div className="flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              checked={config.sync.mode === 'local_only'}
              onChange={() => setConfig({ ...config, sync: { mode: 'local_only' } })}
            />
            Local Only
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              checked={config.sync.mode === 'hybrid'}
              onChange={() => setConfig({ ...config, sync: { mode: 'hybrid', cloud_endpoint: '' } })}
            />
            Hybrid (Local + Cloud)
          </label>
        </div>
        {config.sync.mode === 'hybrid' && (
          <div className="mt-4">
            <label className="block text-sm text-gray-600 mb-1">Cloud Endpoint</label>
            <input
              type="text"
              value={config.sync.cloud_endpoint || ''}
              onChange={(e) => setConfig({
                ...config,
                sync: { ...config.sync, cloud_endpoint: e.target.value }
              })}
              className="w-full px-3 py-2 border rounded"
              placeholder="https://your-cloud-endpoint.com"
            />
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Data Retention</h3>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Retention Days</label>
          <input
            type="number"
            value={config.retention_days}
            onChange={(e) => setConfig({ ...config, retention_days: parseInt(e.target.value) || 90 })}
            className="w-full px-3 py-2 border rounded"
            min="1"
            max="3650"
          />
        </div>
      </div>

      <div className="flex gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
        {error && <span className="text-red-600 self-center">{error}</span>}
      </div>
    </div>
  );
}
