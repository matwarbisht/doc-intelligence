import {
  createDocumentApiClient,
  DEFAULT_API_BASE_URL,
  type DocumentRecord,
} from '@doc-intelligence/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useState, type FormEvent } from 'react';

import { Button } from '../../components/Button/Button';
import { Card } from '../../components/Card/Card';
import { Input } from '../../components/Input/Input';
import styles from './DocumentsPage.module.scss';

const api = createDocumentApiClient(
  import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE_URL,
);
const documentsQueryKey = ['documents'] as const;

export function DocumentsPage() {
  const inputId = useId();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const documents = useQuery({
    queryKey: documentsQueryKey,
    queryFn: ({ signal }) => api.listDocuments({ signal }),
  });
  const upload = useMutation({
    mutationFn: (selectedFile: File) => api.uploadDocument(selectedFile),
    onSuccess: async (result) => {
      setNotice(
        result.duplicate
          ? `${result.document.filename} was already in the library.`
          : `${result.document.filename} was uploaded and queued.`,
      );
      setFile(null);
      setInputKey((key) => key + 1);
      await queryClient.invalidateQueries({ queryKey: documentsQueryKey });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    if (file) upload.mutate(file);
  }

  const uploadError =
    upload.error instanceof Error ? upload.error.message : null;
  const listError =
    documents.error instanceof Error ? documents.error.message : null;

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Document library</p>
          <h1>Upload and track documents.</h1>
        </div>
        <p>
          Originals stay private. Each upload is versioned, queued, and prepared
          for the processing pipeline.
        </p>
      </header>

      <Card className={styles.uploadCard}>
        <form onSubmit={handleSubmit}>
          <div>
            <label htmlFor={inputId}>Choose a document</label>
            <p>PDF, DOCX, Markdown, or plain text. Maximum 50 MB.</p>
          </div>
          <div className={styles.uploadControls}>
            <Input
              id={inputId}
              key={inputKey}
              type="file"
              accept=".pdf,.docx,.md,.markdown,.txt"
              onChange={(event) => {
                setNotice(null);
                setFile(event.target.files?.[0] ?? null);
              }}
            />
            <Button type="submit" disabled={!file || upload.isPending}>
              {upload.isPending ? 'Uploading…' : 'Upload document'}
            </Button>
          </div>
          {file ? (
            <p className={styles.selection}>Selected: {file.name}</p>
          ) : null}
          {notice ? (
            <p className={styles.notice} role="status">
              {notice}
            </p>
          ) : null}
          {uploadError ? (
            <p className={styles.error} role="alert">
              {uploadError}
            </p>
          ) : null}
        </form>
      </Card>

      <section className={styles.library} aria-labelledby="library-heading">
        <div className={styles.libraryHeader}>
          <div>
            <p className={styles.eyebrow}>Corpus</p>
            <h2 id="library-heading">Documents</h2>
          </div>
          {documents.data ? (
            <span>{documents.data.items.length} shown</span>
          ) : null}
        </div>

        {documents.isPending ? (
          <p className={styles.empty}>Loading documents…</p>
        ) : null}
        {listError ? (
          <p className={styles.error} role="alert">
            {listError}
          </p>
        ) : null}
        {documents.data?.items.length === 0 ? (
          <p className={styles.empty}>
            No documents yet. Upload the first one above.
          </p>
        ) : null}
        {documents.data?.items.length ? (
          <div className={styles.documentList}>
            {documents.data.items.map((document) => (
              <DocumentRow document={document} key={document.id} />
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function DocumentRow({ document }: { document: DocumentRecord }) {
  return (
    <article className={styles.documentRow}>
      <div className={styles.documentIdentity}>
        <div className={styles.fileMark} aria-hidden="true">
          {fileType(document)}
        </div>
        <div>
          <h3>{document.filename}</h3>
          <p>
            {formatFileSize(document.size_bytes)} · Added{' '}
            {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
              new Date(document.created_at),
            )}
          </p>
        </div>
      </div>
      <span className={styles.status} data-status={document.status}>
        {document.status.replaceAll('_', ' ')}
      </span>
    </article>
  );
}

function fileType(document: DocumentRecord): string {
  if (document.mime_type === 'application/pdf') return 'PDF';
  if (document.mime_type.includes('wordprocessingml')) return 'DOC';
  if (document.mime_type === 'text/markdown') return 'MD';
  return 'TXT';
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null) return 'Unknown size';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
