import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DeidentifyPage from './page';
import SidebarNav from '@/components/sidebar-nav';
import { deidentifyService } from '@/lib/api-services';
import type { DeidResponse } from '@/types';

// --- Module mocks --------------------------------------------------------

vi.mock('@/lib/api-services', () => ({
  deidentifyService: {
    deidentifyText: vi.fn(),
    deidentifyUpload: vi.fn(),
    submitReview: vi.fn(),
    finalize: vi.fn(),
    getCertificate: vi.fn(),
    ingest: vi.fn(),
  },
}));

vi.mock('@/lib/auth-context', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'tester', role: 'Admin' },
    isLoading: false,
    logout: vi.fn(),
  }),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/deidentify',
  useRouter: () => ({ push: vi.fn() }),
}));

const mockedService = vi.mocked(deidentifyService);

const needsReviewResponse: DeidResponse = {
  job_id: 'job-1',
  status: 'needs_review',
  deidentified_text: 'Patient [NAME] seen on [DATE-2023].',
  report: {
    method: 'HIPAA Safe Harbor',
    category_counts: { NAME: 1, DATE: 1 },
    total_redactions: 2,
    low_confidence: [
      {
        index: 0,
        category: 'NAME',
        start: 8,
        end: 12,
        token: '[NAME]',
        method: 'llm',
        confidence: 0.5,
      },
    ],
  },
};

const finalizedResponse: DeidResponse = {
  job_id: 'job-2',
  status: 'deidentified',
  deidentified_text: 'Contact [EMAIL] for details.',
  report: {
    method: 'HIPAA Safe Harbor',
    category_counts: { EMAIL: 1 },
    total_redactions: 1,
    low_confidence: [],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DeidentifyPage', () => {
  it('renders upload and paste controls (Req 10.2)', () => {
    render(<DeidentifyPage />);

    // Both input mode toggles are present.
    expect(screen.getByRole('button', { name: 'Paste text' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload PDF' })).toBeInTheDocument();

    // Paste mode is the default: the text area is shown.
    expect(screen.getByLabelText('Text to de-identify')).toBeInTheDocument();

    // Switching to upload mode reveals the file input.
    fireEvent.click(screen.getByRole('button', { name: 'Upload PDF' }));
    expect(screen.getByLabelText('PDF file to de-identify')).toBeInTheDocument();
  });

  it('shows the review panel with approve/reject/edit controls when flagged items are present (Req 10.4)', async () => {
    mockedService.deidentifyText.mockResolvedValue(needsReviewResponse);
    render(<DeidentifyPage />);

    fireEvent.change(screen.getByLabelText('Text to de-identify'), {
      target: { value: 'Patient John seen on 01/15/2023.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'De-identify' }));

    const panel = await screen.findByTestId('review-panel');
    expect(panel).toBeInTheDocument();
    expect(screen.getByTestId('flagged-item')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'approve' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'reject' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'edit' })).toBeInTheDocument();
  });

  it('shows the download certificate control when the job is finalized (Req 10.5)', async () => {
    mockedService.deidentifyText.mockResolvedValue(finalizedResponse);
    render(<DeidentifyPage />);

    fireEvent.change(screen.getByLabelText('Text to de-identify'), {
      target: { value: 'Contact a@b.com for details.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'De-identify' }));

    expect(
      await screen.findByRole('button', { name: 'Download certificate' })
    ).toBeInTheDocument();
    // No review panel when nothing is flagged.
    expect(screen.queryByTestId('review-panel')).not.toBeInTheDocument();
  });

  it('shows the ingest control for a finalized job and ingests into the warehouse (Req 5.1)', async () => {
    mockedService.deidentifyText.mockResolvedValue(finalizedResponse);
    mockedService.ingest.mockResolvedValue({
      job_id: 'job-2',
      source_id: 'default-clinic',
      table: 'clinical_notes',
      record_ids: ['deid-note:job-2'],
      ingested: true,
    });
    render(<DeidentifyPage />);

    fireEvent.change(screen.getByLabelText('Text to de-identify'), {
      target: { value: 'Contact a@b.com for details.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'De-identify' }));

    // The ingest control appears alongside the certificate download for a
    // finalized job.
    const ingestButton = await screen.findByRole('button', {
      name: 'Ingest into warehouse',
    });
    expect(ingestButton).toBeInTheDocument();

    fireEvent.click(ingestButton);

    await waitFor(() => {
      expect(mockedService.ingest).toHaveBeenCalledWith('job-2');
    });

    // The returned record ids and newly-ingested state are surfaced.
    expect(await screen.findByTestId('ingest-result')).toBeInTheDocument();
    expect(screen.getByTestId('ingest-record-id')).toHaveTextContent('deid-note:job-2');
  });

  it('does not show the ingest control for a job that still needs review (Req 5.1)', async () => {
    mockedService.deidentifyText.mockResolvedValue(needsReviewResponse);
    render(<DeidentifyPage />);

    fireEvent.change(screen.getByLabelText('Text to de-identify'), {
      target: { value: 'Patient John seen on 01/15/2023.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'De-identify' }));

    await screen.findByTestId('review-panel');
    expect(
      screen.queryByRole('button', { name: 'Ingest into warehouse' })
    ).not.toBeInTheDocument();
  });

  it('submits review decisions then finalizes and reveals the certificate download', async () => {
    mockedService.deidentifyText.mockResolvedValue(needsReviewResponse);
    mockedService.submitReview.mockResolvedValue({
      job_id: 'job-1',
      status: 'needs_review',
      flagged: 1,
      decided: 1,
      can_finalize: true,
    });
    mockedService.finalize.mockResolvedValue({
      job_id: 'job-1',
      status: 'deidentified',
      approved: 1,
      rejected: 0,
      edited: 0,
    });
    render(<DeidentifyPage />);

    fireEvent.change(screen.getByLabelText('Text to de-identify'), {
      target: { value: 'Patient John seen on 01/15/2023.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'De-identify' }));

    await screen.findByTestId('review-panel');
    // Approve the single flagged item, then finalize.
    fireEvent.click(screen.getByRole('button', { name: 'approve' }));
    fireEvent.click(screen.getByRole('button', { name: 'Submit review & finalize' }));

    await waitFor(() => {
      expect(mockedService.submitReview).toHaveBeenCalledWith('job-1', [
        { redaction_index: 0, action: 'approve' },
      ]);
      expect(mockedService.finalize).toHaveBeenCalledWith('job-1');
    });

    expect(
      await screen.findByRole('button', { name: 'Download certificate' })
    ).toBeInTheDocument();
  });
});

describe('SidebarNav', () => {
  it('includes the De-identify navigation entry (Req 10.1)', () => {
    render(<SidebarNav />);
    const link = screen.getByRole('link', { name: /De-identify/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/deidentify');
  });
});
