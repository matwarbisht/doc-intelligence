import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { QueryPage } from './QueryPage';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('renders a grounded answer and linked source evidence', async () => {
  const queryResponse = {
    id: 'query-1',
    query: 'How much did revenue grow?',
    query_type: 'hybrid',
    document_id: null,
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
  };
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation((_url: string, init?: RequestInit) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              init?.method === 'POST'
                ? queryResponse
                : { items: [], limit: 50, offset: 0 },
            ),
            { status: 200, headers: { 'content-type': 'application/json' } },
          ),
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

it('uses the document from the URL as a strict query scope', async () => {
  const fetchMock = vi
    .fn()
    .mockImplementation((_url: string, init?: RequestInit) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            init?.method === 'POST'
              ? {
                  id: 'query-2',
                  query: 'What changed?',
                  query_type: 'hybrid',
                  document_id: 'doc-1',
                  answer: 'The document describes a change [1].',
                  sources: [],
                  created_at: '2026-09-05T00:00:00Z',
                }
              : {
                  items: [
                    {
                      id: 'doc-1',
                      filename: 'report.pdf',
                      mime_type: 'application/pdf',
                      status: 'ready',
                      size_bytes: 42,
                      created_at: '2026-09-05T00:00:00Z',
                      updated_at: '2026-09-05T00:00:00Z',
                    },
                  ],
                  limit: 50,
                  offset: 0,
                },
          ),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      ),
    );
  vi.stubGlobal('fetch', fetchMock);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/ask?document=doc-1']}>
        <QueryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(
    await screen.findByText('Answers will use only report.pdf.'),
  ).toBeVisible();
  expect(screen.getByLabelText('Answer scope')).toHaveValue('doc-1');
  fireEvent.change(screen.getByLabelText('Question'), {
    target: { value: 'What changed?' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Ask documents' }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/query',
      expect.objectContaining({
        body: JSON.stringify({
          query: 'What changed?',
          document_id: 'doc-1',
        }),
      }),
    ),
  );

  fireEvent.click(screen.getByRole('button', { name: 'Clear scope' }));
  expect(screen.getByLabelText('Answer scope')).toHaveValue('');
  expect(
    screen.getByText('Answers may use evidence from every ready document.'),
  ).toBeVisible();
});

it('keeps document review available when asking is disabled', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            url.endsWith('/capabilities')
              ? {
                  public_signup: true,
                  uploads: true,
                  processing: true,
                  processing_retries: true,
                  ask: false,
                }
              : { items: [], limit: 50, offset: 0 },
          ),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
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

  expect(
    await screen.findByText(/question answering is temporarily unavailable/i),
  ).toBeVisible();
  expect(screen.getByLabelText('Question')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Ask documents' })).toBeDisabled();
});
