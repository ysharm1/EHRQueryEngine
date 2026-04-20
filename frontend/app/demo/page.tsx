'use client';

import { useState } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const EXAMPLE_QUERIES = [
  "Find all Parkinson's patients with DBS surgery",
  "Show subjects with diabetes and hypertension",
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

interface ParsedCriteria {
  filter_type: string;
  field: string;
  operator: string;
  value: string;
}

export default function DemoPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [parsedCriteria, setParsedCriteria] = useState<ParsedCriteria[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'idle' | 'parsing' | 'querying' | 'done'>('idle');

  const runQuery = async (queryText: string) => {
    if (!queryText.trim()) return;
    setQuery(queryText);
    setLoading(true);
    setError(null);
    setResult(null);
    setParsedCriteria([]);
    setStep('parsing');

    try {
      // Small delay to show "parsing" step visually
      await new Promise(r => setTimeout(r, 600));
      setStep('querying');

      const res = await axios.post(`${API_URL}/api/demo/query`, {
        query_text: queryText,
        data_source_ids: ['subjects', 'procedures', 'observations'],
        output_format: 'CSV',
      });

      setResult(res.data);
      setStep('done');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Something went wrong. Is the backend running?');
      setStep('idle');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runQuery(query);
  };

  const downloadFile = (url: string) => {
    // url is already a full path like /api/demo/download/...
    window.open(`${API_URL}${url}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-white">
      {/* Header */}
      <header className="border-b border-slate-700 px-6 py-4">
        <div className="mx-auto max-w-4xl flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">EHR Query Engine</h1>
            <p className="text-sm text-slate-400">Natural language → research dataset</p>
          </div>
          <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/30">
            Live Demo
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10 space-y-8">

        {/* Hero */}
        <div className="text-center space-y-3">
          <h2 className="text-3xl font-bold">Ask your data anything</h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Type a research question in plain English. The engine parses your intent,
            queries the database, and returns a downloadable dataset — no SQL required.
          </p>
        </div>

        {/* Query Input */}
        <div className="rounded-xl bg-slate-800 border border-slate-700 p-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <textarea
              rows={3}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. Find all Parkinson's patients who had DBS surgery"
              className="w-full rounded-lg bg-slate-900 border border-slate-600 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed px-4 py-3 font-semibold transition-colors"
            >
              {loading ? 'Processing...' : 'Run Query →'}
            </button>
          </form>

          {/* Example queries */}
          <div>
            <p className="text-xs text-slate-500 mb-2">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUERIES.map(q => (
                <button
                  key={q}
                  onClick={() => runQuery(q)}
                  disabled={loading}
                  className="rounded-full bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-1 text-xs text-slate-300 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Pipeline Steps */}
        {step !== 'idle' && (
          <div className="rounded-xl bg-slate-800 border border-slate-700 p-6">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Pipeline</h3>
            <div className="flex items-center gap-3">
              {[
                { key: 'parsing', label: '1. Parse Intent' },
                { key: 'querying', label: '2. Query Database' },
                { key: 'done', label: '3. Build Dataset' },
              ].map((s, i) => {
                const steps = ['parsing', 'querying', 'done'];
                const currentIdx = steps.indexOf(step);
                const thisIdx = steps.indexOf(s.key);
                const isDone = currentIdx > thisIdx || step === 'done';
                const isActive = step === s.key;

                return (
                  <div key={s.key} className="flex items-center gap-3">
                    <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                      isDone ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                      isActive ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse' :
                      'bg-slate-700 text-slate-500'
                    }`}>
                      {isDone ? '✓' : isActive ? '⟳' : '○'} {s.label}
                    </div>
                    {i < 2 && <span className="text-slate-600">→</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Results */}
        {result && step === 'done' && (
          <div className="space-y-4">
            {result.status === 'Completed' ? (
              <>
                {/* Stats */}
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: 'Subjects Found', value: result.row_count },
                    { label: 'Variables', value: result.column_count },
                    { label: 'Status', value: 'Ready' },
                  ].map(stat => (
                    <div key={stat.label} className="rounded-xl bg-slate-800 border border-slate-700 p-4 text-center">
                      <div className="text-2xl font-bold text-white">{stat.value}</div>
                      <div className="text-xs text-slate-400 mt-1">{stat.label}</div>
                    </div>
                  ))}
                </div>

                {/* Metadata */}
                {result.metadata && (
                  <div className="rounded-xl bg-slate-800 border border-slate-700 p-4 space-y-2">
                    <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Query Details</h3>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="text-slate-400">Data sources</div>
                      <div className="text-white">{result.metadata.data_sources?.join(', ') || '—'}</div>
                      <div className="text-slate-400">Execution time</div>
                      <div className="text-white">{result.metadata.execution_time?.toFixed(3)}s</div>
                      <div className="text-slate-400">Confidence</div>
                      <div className="text-white">{result.metadata.confidence_score ? `${(result.metadata.confidence_score * 100).toFixed(0)}%` : '—'}</div>
                    </div>
                  </div>
                )}

                {/* Downloads */}
                {result.download_urls?.length > 0 && (
                  <div className="rounded-xl bg-slate-800 border border-slate-700 p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Download Dataset</h3>
                    <div className="flex flex-wrap gap-3">
                      {result.download_urls.map((url, i) => {
                        const filename = url.split('/').pop() || `file-${i}`;
                        const ext = filename.split('.').pop()?.toUpperCase();
                        return (
                          <button
                            key={url}
                            onClick={() => downloadFile(url)}
                            className="flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-500 px-4 py-2 text-sm font-medium transition-colors"
                          >
                            ↓ {ext} — {filename}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="rounded-xl bg-yellow-500/10 border border-yellow-500/30 p-4 text-yellow-400 text-sm">
                {result.error_message || 'No results found for this query. Try a different question.'}
              </div>
            )}
          </div>
        )}

        {/* How it works */}
        {step === 'idle' && (
          <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-6">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">How it works</h3>
            <div className="grid grid-cols-3 gap-6 text-sm">
              {[
                { icon: '💬', title: 'Natural Language', desc: 'Type your research question in plain English — no SQL or coding needed.' },
                { icon: '🧠', title: 'Intent Parsing', desc: 'The engine extracts cohort criteria, variables, and filters from your query.' },
                { icon: '📦', title: 'Instant Export', desc: 'Get a structured dataset as CSV, JSON, or Parquet with full provenance.' },
              ].map(item => (
                <div key={item.title} className="space-y-2">
                  <div className="text-2xl">{item.icon}</div>
                  <div className="font-medium text-white">{item.title}</div>
                  <div className="text-slate-400">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
