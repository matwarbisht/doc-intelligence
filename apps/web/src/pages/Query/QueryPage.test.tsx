import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { QueryPage } from './QueryPage';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('renders a grounded answer and linked source evidence', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'query-1',
          query: 'How much did revenue grow?',
          query_type: 'hybrid',
          answer: 'Revenue grew by 24% [1].',
          created_at: '2026-09-05T00:00:00Z',
          sources: [
            {
              citation_number: 1,
              document_id: 'doc-1',
              chunk_id: 'chunk-1',
              filename: 'report.pdf',
              section: 'Performance',
              page_start: 7,
              page_end: 7,
              excerpt: 'Revenue grew by 24%.',
              score: 0.03,
              match_types: ['semantic', 'structured'],
            },
          ],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    ),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <QueryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  fireEvent.change(screen.getByLabelText('Question'), {
    target: { value: 'How much did revenue grow?' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Ask documents' }));

  expect(await screen.findByText('Revenue grew by 24% [1].')).toBeVisible();
  expect(screen.getByText('Revenue grew by 24%.')).toBeVisible();
  expect(screen.getByRole('link', { name: 'report.pdf' })).toHaveAttribute(
    'href',
    '/documents/doc-1',
  );
  expect(screen.getByText('semantic')).toBeVisible();
});
