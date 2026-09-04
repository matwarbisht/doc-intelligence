import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import { MemoryRouter } from 'react-router';

import { DocumentsPage } from './DocumentsPage';

const document = {
  id: 'b9a29354-3ff7-4c55-9054-efae0dff3559',
  filename: 'notes.txt',
  mime_type: 'text/plain',
  status: 'queued',
  size_bytes: 5,
  created_at: '2026-09-03T12:00:00Z',
  updated_at: '2026-09-03T12:00:00Z',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it('lists documents from the API', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ items: [document], limit: 50, offset: 0 }),
        {
          status: 200,
          headers: { 'content-type': 'application/json' },
        },
      ),
    ),
  );

  renderPage();

  expect(
    await screen.findByRole('heading', { name: 'notes.txt' }),
  ).toBeVisible();
  expect(screen.getByText('queued')).toBeVisible();
});

it('shows browser-level errors when the document list cannot be loaded', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
  );

  renderPage();

  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch');
});

it('uploads a selected document and shows feedback', async () => {
  const fetchMock = vi
    .fn()
    .mockImplementation((_url: string, init?: RequestInit) => {
      const payload =
        init?.method === 'POST'
          ? { document, duplicate: false }
          : { items: [], limit: 50, offset: 0 };
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: init?.method === 'POST' ? 201 : 200,
          headers: { 'content-type': 'application/json' },
        }),
      );
    });
  vi.stubGlobal('fetch', fetchMock);
  renderPage();
  const file = new File(['hello'], 'notes.txt', { type: 'text/plain' });

  fireEvent.change(screen.getByLabelText('Choose a document'), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Upload document' }));

  expect(await screen.findByRole('status')).toHaveTextContent(
    'notes.txt was uploaded and queued.',
  );
  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:8000/api/v1/documents',
    expect.objectContaining({ method: 'POST' }),
  );
});
