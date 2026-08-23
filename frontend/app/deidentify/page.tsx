'use client';

import { useMemo, useRef, useState } from 'react';
import ProtectedRoute from '@/components/protected-route';
import SidebarNav from '@/components/sidebar-nav';
import { deidentifyService } from '@/lib/api-services';
import type {
  DeidResponse,
  DeidRedaction,
  DeidReviewDecision,
} from '@/types';

type InputMode = 'paste' | 'upload';
type ReviewAction = 'approve' | 'reject' | 'edit';

interface DecisionState {
  action: ReviewAction;
  replacement: string;
}

// Matches typed redaction tokens like [NAME], [SSN], [DATE-2023], [HEALTH_PLAN].
// The split pattern is global (to keep captured delimiters); the test pattern is
// non-global so `.test()` stays stateless when classifying each part.
const TOKEN_SPLIT_PATTERN = /(\[[A-Z_]+(?:-\d{4})?\])/g;
const TOKEN_TEST_PATTERN = /^\[[A-Z_]+(?:-\d{4})?\]$/;

/** Render text with redaction tokens visually highlighted. */
function HighlightedText({ text }: { text: string }) {
  const parts = text.split(TOKEN_SPLIT_PATTERN);
  return (
    <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-800">
      {parts.map((part, idx) =>
        TOKEN_TEST_PATTERN.test(part) ? (
          <mark
            key={idx}
            data-testid="redaction-token"
            className="rounded bg-yellow-100 px-1 font-mono text-xs font-semibold text-yellow-900"
          >
            {part}
          </mark>
        ) : (
          <span key={idx}>{part}</span>
        )
      )}
    </p>
  );
}

export default function DeidentifyPage() {
  const [mode, setMode] = useState<InputMode>('paste');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DeidResponse | null>(null);
  // The text that was submitted (available for paste mode) so the review panel
  // and "before" view can show the original spans. Empty for PDF uploads.
  const [originalText, setOriginalText] = useState('');

  const [decisions, setDecisions] = useState<Record<number, DecisionState>>({});
  const [finalizing, setFinalizing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const [downloading, setDownloading] = useState(false);
  const [certError, setCertError] = useState<string | null>(null);

  const flagged: DeidRedaction[] = useMemo(
    () => result?.report.low_confidence ?? [],
    [result]
  );
  const status = result?.status ?? null;
  const isFinalized = status === 'deidentified';

  const allDecided = useMemo(
    () => flagged.every((r) => decisions[r.index] !== undefined),
    [flagged, decisions]
  );

  const resetOutputs = () => {
    setResult(null);
    setDecisions({});
    setReviewError(null);
    setCertError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    if (mode === 'paste' && !text.trim()) return;
    if (mode === 'upload' && !file) return;

    setLoading(true);
    setError(null);
    resetOutputs();
    try {
      const response =
        mode === 'paste'
          ? await deidentifyService.deidentifyText(text)
          : await deidentifyService.deidentifyUpload(file as File);
      setResult(response);
      setOriginalText(mode === 'paste' ? text : '');
    } catch {
      setError('De-identification failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const setDecision = (index: number, action: ReviewAction) => {
    setDecisions((prev) => ({
      ...prev,
      [index]: { action, replacement: prev[index]?.replacement ?? '' },
    }));
  };

  const setReplacement = (index: number, replacement: string) => {
    setDecisions((prev) => ({
      ...prev,
      [index]: { action: prev[index]?.action ?? 'edit', replacement },
    }));
  };

  const handleFinalize = async () => {
    if (!result || finalizing) return;
    setFinalizing(true);
    setReviewError(null);
    try {
      const payload: DeidReviewDecision[] = flagged.map((r) => {
        const d = decisions[r.index];
        return {
          redaction_index: r.index,
          action: d.action,
          ...(d.action === 'edit' ? { replacement: d.replacement } : {}),
        };
      });
      if (payload.length > 0) {
        await deidentifyService.submitReview(result.job_id, payload);
      }
      const finalized = await deidentifyService.finalize(result.job_id);
      setResult({ ...result, status: finalized.status });
    } catch {
      setReviewError('Could not finalize the job. Please review the decisions and try again.');
    } finally {
      setFinalizing(false);
    }
  };

  const handleDownloadCertificate = async () => {
    if (!result || downloading) return;
    setDownloading(true);
    setCertError(null);
    try {
      const certificate = await deidentifyService.getCertificate(result.job_id);
      const blob = new Blob([JSON.stringify(certificate, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `deidentification_certificate_${result.job_id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setCertError('Could not download the certificate. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  const categoryEntries = result
    ? Object.entries(result.report.category_counts).filter(([, count]) => count > 0)
    : [];

  return (
    <ProtectedRoute>
      <div className="flex h-screen">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
          <div className="mx-auto max-w-4xl">
            {/* Page header */}
            <div className="mb-8">
              <h2 className="text-xl font-semibold text-gray-900">De-identify</h2>
              <p className="mt-1 text-sm text-gray-500">
                Remove HIPAA Safe Harbor identifiers from clinical text or PDFs. Review flagged
                items, then download a de-identification certificate.
              </p>
            </div>

            {/* Input controls */}
            <form onSubmit={handleSubmit} className="mb-8 rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <div className="mb-4 inline-flex rounded-lg border border-gray-200 p-0.5">
                <button
                  type="button"
                  onClick={() => setMode('paste')}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    mode === 'paste' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  Paste text
                </button>
                <button
                  type="button"
                  onClick={() => setMode('upload')}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    mode === 'upload' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  Upload PDF
                </button>
              </div>

              {mode === 'paste' ? (
                <textarea
                  aria-label="Text to de-identify"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={8}
                  placeholder="Paste clinical text here…"
                  className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              ) : (
                <div className="flex items-center gap-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf,.pdf"
                    aria-label="PDF file to de-identify"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="block w-full text-sm text-gray-600 file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
                  />
                </div>
              )}

              <div className="mt-4 flex justify-end">
                <button
                  type="submit"
                  disabled={loading || (mode === 'paste' ? !text.trim() : !file)}
                  className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {loading ? 'De-identifying…' : 'De-identify'}
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
                  <p className="mt-3 text-sm text-gray-600">De-identifying document…</p>
                </div>
              </div>
            )}

            {/* Results */}
            {!loading && result && (
              <div className="space-y-6">
                {/* Report summary */}
                <div className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">
                        {result.report.total_redactions} redaction
                        {result.report.total_redactions === 1 ? '' : 's'} applied
                      </h3>
                      <p className="mt-0.5 text-xs text-gray-500">Method: {result.report.method}</p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        isFinalized ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {isFinalized ? 'De-identified' : 'Needs review'}
                    </span>
                  </div>
                  {categoryEntries.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {categoryEntries.map(([category, count]) => (
                        <span
                          key={category}
                          className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700"
                        >
                          {category}: {count}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Before / After view */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
                    <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Before
                    </h4>
                    {originalText ? (
                      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-800">
                        {originalText}
                      </p>
                    ) : (
                      <p className="text-sm italic text-gray-400">
                        Original text is not shown for uploaded PDFs to avoid retaining PHI.
                      </p>
                    )}
                  </div>
                  <div className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
                    <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      After
                    </h4>
                    <HighlightedText text={result.deidentified_text} />
                  </div>
                </div>

                {/* Review panel (Req 10.4) */}
                {!isFinalized && flagged.length > 0 && (
                  <div
                    data-testid="review-panel"
                    className="rounded-lg border border-amber-200 bg-amber-50 p-5 shadow-sm"
                  >
                    <h3 className="text-sm font-semibold text-gray-900">
                      Review {flagged.length} low-confidence redaction
                      {flagged.length === 1 ? '' : 's'}
                    </h3>
                    <p className="mt-0.5 text-xs text-gray-600">
                      Approve to keep the redaction, reject to restore the original text, or edit to
                      supply a replacement.
                    </p>

                    <div className="mt-4 space-y-3">
                      {flagged.map((r) => {
                        const decision = decisions[r.index];
                        const snippet = originalText
                          ? originalText.slice(r.start, r.end)
                          : null;
                        return (
                          <div
                            key={r.index}
                            data-testid="flagged-item"
                            className="rounded-lg border border-gray-200 bg-white p-4"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                                {r.category}
                              </span>
                              <span className="text-xs text-gray-500">
                                {Math.round(r.confidence * 100)}% confidence
                              </span>
                              {snippet && (
                                <span className="font-mono text-xs text-gray-800">
                                  &ldquo;{snippet}&rdquo;
                                </span>
                              )}
                            </div>

                            <div className="mt-3 flex flex-wrap items-center gap-2">
                              {(['approve', 'reject', 'edit'] as ReviewAction[]).map((action) => (
                                <button
                                  key={action}
                                  type="button"
                                  onClick={() => setDecision(r.index, action)}
                                  className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                                    decision?.action === action
                                      ? action === 'approve'
                                        ? 'bg-green-600 text-white'
                                        : action === 'reject'
                                          ? 'bg-red-600 text-white'
                                          : 'bg-blue-600 text-white'
                                      : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                                  }`}
                                >
                                  {action}
                                </button>
                              ))}
                            </div>

                            {decision?.action === 'edit' && (
                              <input
                                type="text"
                                aria-label={`Replacement for redaction ${r.index}`}
                                value={decision.replacement}
                                onChange={(e) => setReplacement(r.index, e.target.value)}
                                placeholder="Replacement text"
                                className="mt-2 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {reviewError && <p className="mt-3 text-sm text-red-700">{reviewError}</p>}

                    <div className="mt-4 flex items-center justify-end gap-3">
                      {!allDecided && (
                        <p className="text-xs text-gray-500">Decide on every item to finalize.</p>
                      )}
                      <button
                        type="button"
                        onClick={handleFinalize}
                        disabled={!allDecided || finalizing}
                        className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {finalizing ? 'Finalizing…' : 'Submit review & finalize'}
                      </button>
                    </div>
                  </div>
                )}

                {/* Certificate download (Req 10.5) */}
                {isFinalized && (
                  <div className="rounded-lg border border-green-200 bg-green-50 p-5 shadow-sm">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <h3 className="text-sm font-semibold text-gray-900">Job finalized</h3>
                        <p className="mt-0.5 text-xs text-gray-600">
                          Download the de-identification certificate for your compliance records.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={handleDownloadCertificate}
                        disabled={downloading}
                        className="shrink-0 rounded-lg bg-green-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {downloading ? 'Preparing…' : 'Download certificate'}
                      </button>
                    </div>
                    {certError && <p className="mt-3 text-sm text-red-700">{certError}</p>}
                  </div>
                )}
              </div>
            )}

            {/* Initial State */}
            {!loading && !result && !error && (
              <div className="py-12 text-center">
                <p className="text-sm text-gray-500">
                  Paste clinical text or upload a PDF above to begin de-identification.
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
