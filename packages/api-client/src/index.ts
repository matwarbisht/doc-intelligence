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
  answer: string;
  sources: QuerySource[];
  created_at: string;
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
  queryCorpus(
    query: string,
    options?: { signal?: AbortSignal },
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

export function createDocumentApiClient(
  baseUrl: string = DEFAULT_API_BASE_URL,
): DocumentApiClient {
  const apiUrl = baseUrl.replace(/\/$/, '');

  return {
    queryCorpus: (query, { signal } = {}) =>
      request<CorpusQueryResponse>(`${apiUrl}/api/v1/query`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ query }),
        signal,
      }),

    listDocuments: ({ signal } = {}) =>
      request<DocumentListResponse>(`${apiUrl}/api/v1/documents`, { signal }),

    getDocument: (id, { signal } = {}) =>
      request<DocumentDetail>(
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
