export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export type DocumentStatus =
  | 'uploaded'
  | 'queued'
  | 'parsing'
  | 'extracting'
  | 'embedding'
  | 'indexing'
  | 'ready'
  | 'parsing_failed'
  | 'extraction_failed'
  | 'embedding_failed'
  | 'indexing_failed';

export interface DocumentRecord {
  id: string;
  filename: string;
  mime_type: string;
  status: DocumentStatus;
  size_bytes: number | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentRecord[];
  limit: number;
  offset: number;
}

export interface DocumentUploadResponse {
  document: DocumentRecord;
  duplicate: boolean;
}

export interface DocumentProcessResponse {
  document_id: string;
  accepted: boolean;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface DocumentApiClient {
  listDocuments(options?: {
    signal?: AbortSignal;
  }): Promise<DocumentListResponse>;
  getDocument(
    id: string,
    options?: { signal?: AbortSignal },
  ): Promise<DocumentRecord>;
  uploadDocument(
    file: File,
    options?: { signal?: AbortSignal },
  ): Promise<DocumentUploadResponse>;
  processDocument(
    id: string,
    options?: { signal?: AbortSignal },
  ): Promise<DocumentProcessResponse>;
}

export function createDocumentApiClient(
  baseUrl: string = DEFAULT_API_BASE_URL,
): DocumentApiClient {
  const apiUrl = baseUrl.replace(/\/$/, '');

  return {
    listDocuments: ({ signal } = {}) =>
      request<DocumentListResponse>(`${apiUrl}/api/v1/documents`, { signal }),

    getDocument: (id, { signal } = {}) =>
      request<DocumentRecord>(
        `${apiUrl}/api/v1/documents/${encodeURIComponent(id)}`,
        { signal },
      ),

    uploadDocument: (file, { signal } = {}) => {
      const body = new FormData();
      body.append('file', file);
      return request<DocumentUploadResponse>(`${apiUrl}/api/v1/documents`, {
        method: 'POST',
        body,
        signal,
      });
    },

    processDocument: (id, { signal } = {}) =>
      request<DocumentProcessResponse>(
        `${apiUrl}/api/v1/documents/${encodeURIComponent(id)}/process`,
        { method: 'POST', signal },
      ),
  };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  const fallback = `Request failed with status ${response.status}.`;
  try {
    const payload = (await response.json()) as unknown;
    if (
      typeof payload === 'object' &&
      payload !== null &&
      'detail' in payload &&
      typeof payload.detail === 'string'
    ) {
      return payload.detail;
    }
  } catch {
    return fallback;
  }
  return fallback;
}
