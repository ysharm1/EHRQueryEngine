'use client';

import { useState, useRef } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const EXAMPLE_QUERIES = [
  "Find all Parkinson's patients with DBS surgery",
  "Subjects with diabetes and hypertension",
  "Patients with MRI imaging data",
  "All subjects in the treatment group",
  "Find subjects with observations",
];

interface QueryResult {
  dataset_id: string;
  status: string;
  row_count: number;
  column_count: number;
  download_urls: string[];
  metadata: any;
  error_message?: string;
}

interface PublicDataset {
  id: string;
  name: string;
  description: string;
  subjects: string;
  url: string;
  access: string;
  tags: string[];
  format: string;
  organization: string;
}

interface UploadResult {
  table_name: string;
  rows_imported: number;
  columns: string[];
  sample_data: any[];
}

type Step = 'idle' | 'parsing' | 'querying' | 'done';

const PIPELINE_STEPS = [
  { key: 'parsing', label: 'Parse Intent' },
  { key: 'querying', label: 'Query Database' },
  { key: 'done', label: 'Build Dataset' },
];

export default function DemoPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [publicDatasets, setPublicDatasets] = useState<PublicDataset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<Step>('idle');

  // Upload state
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const runQuery = async (queryText: string) => {
    if (!queryText.trim()) return;
    setQuery(queryText);
    setLoading(true);
    setError(null);
    setResult(null);
    setPublicDatasets([]);
    setStep('parsing');

    try {
      await new Promise(r => setTimeout(r, 500));
      setStep('querying');

      const [queryRes, publicRes] = await Promise.allSettled([
        axios.post(`${API_URL}/api/demo/query`, {
          query_text: queryText,
          data_source_ids: ['subjects', 'procedures', 'observations'],
          output_format: 'CSV',
        }),
        axios.get(`${API_URL}/api/demo/public-datasets`, { params: { q: queryText } }),
      ]);

      if (queryRes.status === 'fulfilled') {
        setResult(queryRes.value.data);
      } else {
        const err = (queryRes as any).reason;
        setError(err.response?.data?.detail || 'Query failed. Please try again.');
      }

      if (publicRes.status === 'fulfilled') {
        setPublicDatasets((publicRes as any).value.data.results || []);
      }

      setStep('done');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Something went wrong.');
      setStep('idle');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runQuery(query);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setUploadResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${API_URL}/api/demo/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadResult(res.data);
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const downloadFile = (url: string) => {
    window.open(`${API_URL}${url}`, '_blank');
  };

  const stepIndex = PIPELINE_STEPS.findIndex(s => s.key === step);

  return (
    <div className="min-h-screen bg-[#0f1117] text-white font-sans">

      {/* Header */}
      <header className="border-b border-white/10 px-6 py-4">
        <div className="mx-auto max-w-5xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-sm font-bold">E</div>
            <div>
              <span className="font-semibold text-white">EHR Query Engine</span>
              <span className="ml-2 text-xs text-white/40">by Research Dataset Builder</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setShowUpload(v => !v); setUploadResult(null); setUploadError(null); }}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                showUpload
                  ? 'border-blue-500/50 bg-blue-500/15 text-blue-400'
                  : 'border-white/10 bg-white/5 text-white/50 hover:text-white/80'
              }`}
            >
              {showUpload ? '✕ Close Upload' : '↑ Upload Data'}
            </button>
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </span>
            <a
              href="https://github.com/ysharm1/EHRQueryEngine"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-white/40 hover:text-white/70 transition-colors"
            >
              GitHub →
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-12 space-y-8">

        {/* Upload Panel */}
        {showUpload && (
          <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-sm text-white">Upload Your Dataset</h2>
                <p className="text-xs text-white/40 mt-0.5">CSV, Excel (.xlsx), or JSON — the system auto-detects the schema</p>
              </div>
            </div>

            {/* Drop zone */}
            <label className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 cursor-pointer transition-colors ${
              uploading ? 'border-blue-500/30 bg-blue-500/5' : 'border-white/10 hover:border-blue-500/40 hover:bg-blue-500/5'
            }`}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls,.json"
                onChange={handleFileUpload}
                className="hidden"
                disabled={uploading}
              />
              {uploading ? (
                <div className="flex items-center gap-2 text-blue-400 text-sm">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  Importing...
                </div>
              ) : (
                <>
                  <div className="text-3xl">📂</div>
                  <div className="text-sm text-white/60">Click to select a file, or drag and drop</div>
                  <div className="text-xs text-white/30">CSV · Excel · JSON</div>
                </>
              )}
            </label>

            {/* Upload error */}
            {uploadError && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-red-400 text-xs">
                {uploadError}
              </div>
            )}

            {/* Upload success */}
            {uploadResult && (
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-3">
                <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
                  <span>✓</span>
                  <span>Imported as table <code className="font-mono bg-white/10 px-1.5 py-0.5 rounded text-xs">{uploadResult.table_name}</code></span>
                </div>
                <div className="flex gap-4 text-xs text-white/50">
                  <span>👥 {uploadResult.rows_imported.toLocaleString()} rows</span>
                  <span>📊 {uploadResult.columns.length} columns</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {uploadResult.columns.slice(0, 8).map(col => (
                    <span key={col} className="rounded bg-white/5 border border-white/10 px-2 py-0.5 text-xs text-white/50 font-mono">
                      {col}
                    </span>
                  ))}
                  {uploadResult.columns.length > 8 && (
                    <span className="text-xs text-white/30">+{uploadResult.columns.length - 8} more</span>
                  )}
                </div>
                <p className="text-xs text-white/40">
                  Your data is loaded. Now type a query below to search it.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Hero */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-xs text-blue-400">
            Natural Language → Research Dataset
          </div>
          <h1 className="text-4xl font-bold tracking-tight">
            Ask your clinical data anything
          </h1>
          <p className="text-white/50 max-w-lg mx-auto text-base">
            Upload your own dataset or query the built-in sample data.
            The engine parses your intent and surfaces both local results and public datasets.
          </p>
        </div>

        {/* Query Box */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <textarea
              rows={3}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runQuery(query); } }}
              placeholder="e.g. Find all Parkinson's patients who had DBS surgery"
              className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none text-sm"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:bg-white/10 disabled:text-white/30 disabled:cursor-not-allowed px-4 py-3 font-semibold text-sm transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  Processing...
                </span>
              ) : 'Run Query →'}
            </button>
          </form>

          {/* Examples */}
          <div>
            <p className="text-xs text-white/30 mb-2">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUERIES.map(q => (
                <button
                  key={q}
                  onClick={() => runQuery(q)}
                  disabled={loading}
                  className="rounded-full border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-40 px-3 py-1 text-xs text-white/60 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Pipeline */}
        {step !== 'idle' && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs text-white/40 uppercase tracking-widest mb-4">Pipeline</p>
            <div className="flex items-center gap-2 flex-wrap">
              {PIPELINE_STEPS.map((s, i) => {
                const isDone = step === 'done' || stepIndex > i;
                const isActive = PIPELINE_STEPS[stepIndex]?.key === s.key && step !== 'done';
                return (
                  <div key={s.key} className="flex items-center gap-2">
                    <div className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium border transition-all ${
                      isDone ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : isActive ? 'bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse'
                        : 'bg-white/5 text-white/30 border-white/10'
                    }`}>
                      {isDone ? '✓' : isActive ? '◌' : '○'} {s.label}
                    </div>
                    {i < PIPELINE_STEPS.length - 1 && <span className="text-white/20 text-xs">→</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Results */}
        {step === 'done' && (
          <div className="space-y-6">

            {/* Local Results */}
            {result && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/40 uppercase tracking-widest">Local Database</span>
                  <div className="flex-1 h-px bg-white/10" />
                </div>

                {result.status === 'Completed' ? (
                  <>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { label: 'Subjects Found', value: result.row_count, color: 'text-blue-400' },
                        { label: 'Variables', value: result.column_count, color: 'text-purple-400' },
                        { label: 'Execution', value: result.metadata?.execution_time ? `${result.metadata.execution_time.toFixed(2)}s` : '—', color: 'text-emerald-400' },
                      ].map(stat => (
                        <div key={stat.label} className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
                          <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                          <div className="text-xs text-white/40 mt-1">{stat.label}</div>
                        </div>
                      ))}
                    </div>

                    {result.metadata?.confidence_score && (
                      <div className="rounded-xl border border-white/10 bg-white/5 p-4 flex items-center justify-between text-sm">
                        <span className="text-white/50">Query confidence</span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-1.5 rounded-full bg-white/10 overflow-hidden">
                            <div className="h-full rounded-full bg-emerald-400" style={{ width: `${(result.metadata.confidence_score * 100).toFixed(0)}%` }} />
                          </div>
                          <span className="text-emerald-400 font-medium">{(result.metadata.confidence_score * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    )}

                    {result.download_urls?.length > 0 && (
                      <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
                        <p className="text-xs text-white/40 uppercase tracking-widest">Download Dataset</p>
                        <div className="flex flex-wrap gap-2">
                          {result.download_urls.map((url, i) => {
                            const raw = url.split('?')[0];
                            const filename = raw.split('/').pop() || `file-${i}`;
                            const ext = filename.split('.').pop()?.toUpperCase() || 'FILE';
                            const icons: Record<string, string> = { CSV: '📊', JSON: '📋', SQL: '🔍', PARQUET: '📦' };
                            return (
                              <button key={url} onClick={() => downloadFile(url)}
                                className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 px-4 py-2 text-sm font-medium transition-colors">
                                <span>{icons[ext] || '📄'}</span>
                                <span>{ext}</span>
                                <span className="text-white/40 text-xs">{filename}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-4 text-yellow-400 text-sm">
                    {result.error_message || 'No matching subjects found. Try uploading your own data or a different query.'}
                  </div>
                )}
              </div>
            )}

            {/* Public Datasets */}
            {publicDatasets.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/40 uppercase tracking-widest">Public Datasets</span>
                  <div className="flex-1 h-px bg-white/10" />
                  <span className="text-xs text-white/30">{publicDatasets.length} found</span>
                </div>

                <div className="space-y-3">
                  {publicDatasets.map(ds => (
                    <div key={ds.id} className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2 hover:border-white/20 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-sm text-white">{ds.name}</span>
                            <span className="text-xs text-white/40 border border-white/10 rounded px-1.5 py-0.5">{ds.organization}</span>
                          </div>
                          <p className="text-xs text-white/50 leading-relaxed">{ds.description}</p>
                        </div>
                        <a href={ds.url} target="_blank" rel="noopener noreferrer"
                          className="shrink-0 rounded-lg border border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20 px-3 py-1.5 text-xs text-blue-400 font-medium transition-colors">
                          Access →
                        </a>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-white/40 flex-wrap">
                        <span>👥 {ds.subjects} subjects</span>
                        <span>📁 {ds.format}</span>
                        <span>🔑 {ds.access}</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {ds.tags.slice(0, 5).map(tag => (
                          <span key={tag} className="rounded-full bg-white/5 border border-white/10 px-2 py-0.5 text-xs text-white/40">{tag}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-white/25 text-center">
                  Public datasets require separate access approval. Links go directly to source.
                </p>
              </div>
            )}
          </div>
        )}

        {/* How it works */}
        {step === 'idle' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { icon: '↑', title: 'Upload Your Data', desc: 'Bring your own CSV, Excel, or JSON file. The system auto-detects the schema — no formatting needed.' },
              { icon: '💬', title: 'Query in Plain English', desc: 'Type your research question. GPT-4 parses your intent and queries the database automatically.' },
              { icon: '🌐', title: 'Local + Public Results', desc: 'Get your local dataset plus relevant public datasets (PPMI, MIMIC, TCGA, etc.) with direct access links.' },
            ].map(item => (
              <div key={item.title} className="rounded-2xl border border-white/10 bg-white/5 p-5 space-y-2">
                <div className="text-2xl">{item.icon}</div>
                <div className="font-semibold text-sm">{item.title}</div>
                <div className="text-xs text-white/50 leading-relaxed">{item.desc}</div>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="border-t border-white/10 px-6 py-4 mt-12">
        <div className="mx-auto max-w-5xl flex items-center justify-between text-xs text-white/25">
          <span>EHR Query Engine — Research Dataset Builder</span>
          <span>Demo uses synthetic patient data</span>
        </div>
      </footer>
    </div>
  );
}
