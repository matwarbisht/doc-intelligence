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

export interface ProcessingProgress {
  stage: 'queued' | 'parsing' | 'extracting' | 'embedding' | 'indexing';
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  progress: number;
  attempts: number;
  error: string | null;
}

export interface ExtractionSummary {
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  document_type: string | null;
  summary: string | null;
  topics: string[];
}

export interface ExtractedEntity {
  id: string;
  canonical_name: string;
  entity_type: string;
  normalized_value: string | null;
}

export interface ExtractedFact {
  id: string;
  source_chunk_id: string;
  subject: string;
  predicate: string;
  object_value: string;
  qualifiers: Record<string, unknown>;
  confidence: number | null;
}

export interface ExtractedRelationship {
  id: string;
  source_chunk_id: string;
  subject_entity_id: string;
  predicate: string;
  object_entity_id: string | null;
  object_text: string | null;
  confidence: number | null;
}

export interface SourceExcerpt {
  chunk_id: string;
  filename: string;
  page_start: number | null;
  page_end: number | null;
  excerpt: string;
}

export interface DocumentDetail extends DocumentRecord {
  processing: ProcessingProgress[];
  extraction: ExtractionSummary | null;
  entities: ExtractedEntity[];
  facts: ExtractedFact[];
  relationships: ExtractedRelationship[];
  sources: SourceExcerpt[];
  chunk_count: number;
  embedding_count: number;
}

export type QueryType = 'keyword' | 'semantic' | 'structured' | 'hybrid';

export interface QuerySource {
  citation_number: number;
  document_id: string;
  chunk_id: string;
  filename: string;
  section: string | null;
  page_start: number | null;
  page_end: number | null;
  excerpt: string;
  score: number;
  match_types: QueryType[];
}

export interface CorpusQueryResponse {
  id: string;
  query: string;
  query_type: QueryType;
  document_id: string | null;
  answer: string;
  sources: QuerySource[];
  created_at: string;
}

export interface CapabilitiesResponse {
  public_signup: boolean;
  uploads: boolean;
  processing: boolean;
  processing_retries: boolean;
  ask: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
    retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export interface DocumentApiClient {
  getCapabilities(options?: {
    signal?: AbortSignal;
  }): Promise<CapabilitiesResponse>;
  queryCorpus(
    query: string,
    options?: { documentId?: string; signal?: AbortSignal },
  ): Promise<CorpusQueryResponse>;
  listDocuments(options?: {
    signal?: AbortSignal;
  }): Promise<DocumentListResponse>;
  getDocument(
    id: string,
    options?: { signal?: AbortSignal },
  ): Promise<DocumentDetail>;
  uploadDocument(
    file: File,
    options?: { signal?: AbortSignal },
  ): Promise<DocumentUploadResponse>;
  processDocument(
    id: string,
    options?: { signal?: AbortSignal },
  ): Promise<DocumentProcessResponse>;
}

export interface AccessTokenRequest {
  forceRefresh?: boolean;
}

export type AccessTokenProvider = (
  options?: AccessTokenRequest,
) => string | null | Promise<string | null>;

export function createDocumentApiClient(
  baseUrl: string = DEFAULT_API_BASE_URL,
  getAccessToken?: AccessTokenProvider,
): DocumentApiClient {
  const apiUrl = baseUrl.replace(/\/$/, '');
  const authenticatedRequest = async <T>(url: string, init?: RequestInit) => {
    const accessToken = await getAccessToken?.();
    if (!accessToken) return request<T>(url, init);
    const headers = new Headers(init?.headers);
    headers.set('authorization', `Bearer ${accessToken}`);
    try {
      return await request<T>(url, { ...init, headers });
    } catch (error) {
      if (
        !(error instanceof ApiError) ||
        error.status !== 401 ||
        !getAccessToken
      ) {
        throw error;
      }
      const refreshedToken = await getAccessToken({ forceRefresh: true });
      if (!refreshedToken) throw error;
      headers.set('authorization', `Bearer ${refreshedToken}`);
      return request<T>(url, { ...init, headers });
    }
  };

  return {
    getCapabilities: ({ signal } = {}) =>
      request<CapabilitiesResponse>(`${apiUrl}/api/v1/capabilities`, {
        signal,
      }),

    queryCorpus: (query, { documentId, signal } = {}) =>
      authenticatedRequest<CorpusQueryResponse>(`${apiUrl}/api/v1/query`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          query,
          ...(documentId ? { document_id: documentId } : {}),
        }),
        signal,
      }),

    listDocuments: ({ signal } = {}) =>
      authenticatedRequest<DocumentListResponse>(`${apiUrl}/api/v1/documents`, {
        signal,
      }),

    getDocument: (id, { signal } = {}) =>
      authenticatedRequest<DocumentDetail>(
        `${apiUrl}/api/v1/documents/${encodeURIComponent(id)}`,
        { signal },
      ),

    uploadDocument: (file, { signal } = {}) => {
      const body = new FormData();
      body.append('file', file);
      return authenticatedRequest<DocumentUploadResponse>(
        `${apiUrl}/api/v1/documents`,
        {
          method: 'POST',
          body,
          signal,
        },
      );
    },

    processDocument: (id, { signal } = {}) =>
      authenticatedRequest<DocumentProcessResponse>(
        `${apiUrl}/api/v1/documents/${encodeURIComponent(id)}/process`,
        { method: 'POST', signal },
      ),
  };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const error = await errorDetails(response);
    throw new ApiError(
      error.message,
      response.status,
      error.code,
      error.retryAfterSeconds,
    );
  }
  return (await response.json()) as T;
}

async function errorDetails(response: Response): Promise<{
  message: string;
  code: string | null;
  retryAfterSeconds: number | null;
}> {
  const fallback = `Request failed with status ${response.status}.`;
  try {
    const payload = (await response.json()) as unknown;
    if (typeof payload === 'object' && payload !== null) {
      const message =
        'detail' in payload && typeof payload.detail === 'string'
          ? payload.detail
          : fallback;
      const code =
        'code' in payload && typeof payload.code === 'string'
          ? payload.code
          : null;
      const retryAfterSeconds =
        'retry_after_seconds' in payload &&
        typeof payload.retry_after_seconds === 'number'
          ? payload.retry_after_seconds
          : null;
      return { message, code, retryAfterSeconds };
    }
  } catch {
    return { message: fallback, code: null, retryAfterSeconds: null };
  }
  return { message: fallback, code: null, retryAfterSeconds: null };
}
