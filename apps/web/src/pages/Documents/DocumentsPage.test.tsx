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

it('queues and uploads multiple dropped documents independently', async () => {
  const fetchMock = vi
    .fn()
    .mockImplementation((_url: string, init?: RequestInit) => {
      const uploadedFile = (init?.body as FormData | undefined)?.get(
        'file',
      ) as File | null;
      const payload =
        init?.method === 'POST'
          ? {
              document: {
                ...document,
                filename: uploadedFile?.name ?? document.filename,
              },
              duplicate: false,
            }
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
  const first = new File(['hello'], 'notes.txt', { type: 'text/plain' });
  const second = new File(['report'], 'report.md', { type: 'text/markdown' });
  const dropzone = screen.getByRole('heading', { name: 'Drop documents here' })
    .parentElement?.parentElement;

  expect(screen.getByLabelText('Choose files')).toHaveAttribute('multiple');
  fireEvent.drop(dropzone as HTMLElement, {
    dataTransfer: { files: [first, second] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Upload 2 documents' }));

  expect(await screen.findAllByText('Uploaded and queued')).toHaveLength(2);
  expect(
    fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST'),
  ).toHaveLength(2);
});

it('keeps failed files retryable without repeating successful uploads', async () => {
  let shouldFail = true;
  const fetchMock = vi
    .fn()
    .mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method !== 'POST') {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], limit: 50, offset: 0 }), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          }),
        );
      }
      if (shouldFail) {
        shouldFail = false;
        return Promise.resolve(
          new Response(
            JSON.stringify({ detail: 'Unsupported document type.' }),
            {
              status: 415,
              headers: { 'content-type': 'application/json' },
            },
          ),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ document, duplicate: false }), {
          status: 201,
          headers: { 'content-type': 'application/json' },
        }),
      );
    });
  vi.stubGlobal('fetch', fetchMock);
  renderPage();
  const file = new File(['bad'], 'notes.txt', { type: 'text/plain' });

  fireEvent.change(screen.getByLabelText('Choose files'), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Upload 1 document' }));

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Unsupported document type.',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Retry failed' }));

  expect(await screen.findByText('Uploaded and queued')).toBeVisible();
  expect(
    fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST'),
  ).toHaveLength(2);
});
