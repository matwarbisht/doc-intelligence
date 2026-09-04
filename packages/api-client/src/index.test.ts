import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, createDocumentApiClient } from './index';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('document API client', () => {
  it('lists documents from the versioned API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], limit: 50, offset: 0 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const response =
      await createDocumentApiClient('http://api.test/').listDocuments();

    expect(response.items).toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/api/v1/documents', {
      signal: undefined,
    });
  });

  it('sends uploads as multipart form data', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ document: { id: 'document-id' }, duplicate: false }),
        {
          status: 201,
          headers: { 'content-type': 'application/json' },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' });

    await createDocumentApiClient().uploadDocument(file);

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('file')).toBe(file);
  });

  it('exposes API error details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Unsupported document type.' }), {
          status: 415,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    );

    const promise = createDocumentApiClient().listDocuments();

    await expect(promise).rejects.toEqual(
      new ApiError('Unsupported document type.', 415),
    );
  });

  it('requests parsing for a document', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ document_id: 'doc-1', accepted: true }), {
        status: 202,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const client = createDocumentApiClient('http://api.test');

    await client.processDocument('doc-1');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/documents/doc-1/process',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
