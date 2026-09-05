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

  it('loads document intelligence details', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'doc-1',
          processing: [],
          extraction: null,
          entities: [],
          facts: [],
          relationships: [],
          sources: [],
          chunk_count: 2,
          embedding_count: 2,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const response =
      await createDocumentApiClient('http://api.test').getDocument('doc-1');

    expect(response.chunk_count).toBe(2);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/documents/doc-1',
      { signal: undefined },
    );
  });

  it('queries the corpus with JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'query-1',
          query: 'What changed?',
          query_type: 'hybrid',
          document_id: null,
          answer: 'Revenue increased [1].',
          sources: [],
          created_at: '2026-09-05T00:00:00Z',
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result =
      await createDocumentApiClient('http://api.test').queryCorpus(
        'What changed?',
      );

    expect(result.query_type).toBe('hybrid');
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/query',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ query: 'What changed?' }),
      }),
    );
  });

  it('sends an optional document scope with a corpus query', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'query-2',
          query: 'What changed?',
          query_type: 'hybrid',
          document_id: 'doc-1',
          answer: 'Revenue increased [1].',
          sources: [],
          created_at: '2026-09-05T00:00:00Z',
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await createDocumentApiClient('http://api.test').queryCorpus(
      'What changed?',
      { documentId: 'doc-1' },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/query',
      expect.objectContaining({
        body: JSON.stringify({
          query: 'What changed?',
          document_id: 'doc-1',
        }),
      }),
    );
  });
});
