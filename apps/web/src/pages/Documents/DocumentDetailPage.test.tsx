import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';

import { DocumentDetailPage } from './DocumentDetailPage';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('renders semantic intelligence with cited source text', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'doc-1',
          filename: 'report.txt',
          mime_type: 'text/plain',
          status: 'ready',
          size_bytes: 42,
          created_at: '2026-09-04T00:00:00Z',
          updated_at: '2026-09-04T00:00:00Z',
          processing: [
            {
              stage: 'extracting',
              status: 'succeeded',
              progress: 1,
              attempts: 1,
              error: null,
            },
          ],
          extraction: {
            status: 'succeeded',
            document_type: 'financial_report',
            summary: 'Revenue grew during the quarter.',
            topics: ['revenue'],
          },
          entities: [
            {
              id: 'entity-1',
              canonical_name: 'Acme',
              entity_type: 'organization',
              normalized_value: null,
            },
          ],
          facts: [
            {
              id: 'fact-1',
              source_chunk_id: 'chunk-1',
              subject: 'Acme',
              predicate: 'revenue_growth',
              object_value: '24%',
              qualifiers: {},
              confidence: 0.9,
            },
          ],
          relationships: [],
          sources: [
            {
              chunk_id: 'chunk-1',
              filename: 'report.txt',
              page_start: 2,
              page_end: 2,
              excerpt: 'Revenue grew by 24%.',
            },
          ],
          chunk_count: 1,
          embedding_count: 1,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    ),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/documents/doc-1']}>
        <Routes>
          <Route
            path="/documents/:documentId"
            element={<DocumentDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(
    await screen.findByRole('heading', { name: 'report.txt' }),
  ).toBeVisible();
  expect(screen.getByText('Revenue grew during the quarter.')).toBeVisible();
  expect(screen.getByText('Revenue grew by 24%.')).toBeVisible();
  expect(screen.getByText('Page 2')).toBeVisible();
});
