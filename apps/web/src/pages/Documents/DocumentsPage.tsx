import { type DocumentRecord } from '@doc-intelligence/api-client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react';
import { Link } from 'react-router';

import { api } from '../../api/client';
import { Button } from '../../components/Button/Button';
import { Card } from '../../components/Card/Card';
import styles from './DocumentsPage.module.scss';

const documentsQueryKey = ['documents'] as const;
const uploadConcurrency = 3;

type UploadState =
  'pending' | 'uploading' | 'uploaded' | 'duplicate' | 'failed';

interface UploadQueueItem {
  id: string;
  file: File;
  state: UploadState;
  error?: string;
}

export function DocumentsPage() {
  const inputId = useId();
  const nextItemId = useRef(0);
  const queryClient = useQueryClient();
  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const documents = useQuery({
    queryKey: documentsQueryKey,
    queryFn: ({ signal }) => api.listDocuments({ signal }),
    refetchInterval: (query) =>
      query.state.data?.items.some((document) => isProcessing(document.status))
        ? 2_000
        : false,
  });
  function addFiles(files: FileList | File[]) {
    const selected = Array.from(files);
    if (!selected.length) return;
    setQueue((current) => {
      const known = new Set(current.map((item) => fileFingerprint(item.file)));
      const additions: UploadQueueItem[] = [];
      for (const file of selected) {
        const fingerprint = fileFingerprint(file);
        if (known.has(fingerprint)) continue;
        known.add(fingerprint);
        additions.push({
          id: `upload-${nextItemId.current++}`,
          file,
          state: 'pending',
        });
      }
      return [...current, ...additions];
    });
  }

  function handleSelection(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) addFiles(event.target.files);
    event.target.value = '';
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (!isUploading) addFiles(event.dataTransfer.files);
  }

  async function uploadItems(items: UploadQueueItem[]) {
    if (!items.length || isUploading) return;
    setIsUploading(true);
    let nextIndex = 0;

    async function worker() {
      while (nextIndex < items.length) {
        const item = items[nextIndex++];
        if (!item) return;
        updateQueueItem(item.id, { state: 'uploading', error: undefined });
        try {
          const result = await api.uploadDocument(item.file);
          updateQueueItem(item.id, {
            state: result.duplicate ? 'duplicate' : 'uploaded',
          });
        } catch (error) {
          updateQueueItem(item.id, {
            state: 'failed',
            error: error instanceof Error ? error.message : 'Upload failed.',
          });
        }
      }
    }

    try {
      await Promise.all(
        Array.from(
          { length: Math.min(uploadConcurrency, items.length) },
          worker,
        ),
      );
      await queryClient.invalidateQueries({ queryKey: documentsQueryKey });
    } finally {
      setIsUploading(false);
    }
  }

  function updateQueueItem(id: string, update: Partial<UploadQueueItem>) {
    setQueue((current) =>
      current.map((item) => (item.id === id ? { ...item, ...update } : item)),
    );
  }

  const pending = queue.filter((item) => item.state === 'pending');
  const failed = queue.filter((item) => item.state === 'failed');
  const completedCount = queue.filter((item) =>
    ['uploaded', 'duplicate'].includes(item.state),
  ).length;
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
        <div
          className={styles.dropzone}
          data-dragging={isDragging || undefined}
          onDragEnter={() => !isUploading && setIsDragging(true)}
          onDragLeave={() => setIsDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <input
            className={styles.fileInput}
            id={inputId}
            type="file"
            accept=".pdf,.docx,.md,.markdown,.txt"
            multiple
            onChange={handleSelection}
            disabled={isUploading}
          />
          <div className={styles.dropMark} aria-hidden="true">
            ↑
          </div>
          <div>
            <h2>Drop documents here</h2>
            <p>PDF, DOCX, Markdown, or plain text. Maximum 50 MB each.</p>
          </div>
          <label className={styles.filePicker} htmlFor={inputId}>
            Choose files
          </label>
        </div>

        {queue.length ? (
          <section className={styles.uploadQueue} aria-live="polite">
            <div className={styles.queueHeader}>
              <div>
                <p className={styles.eyebrow}>Upload queue</p>
                <h2>{queue.length} documents selected</h2>
              </div>
              <div className={styles.queueActions}>
                {completedCount ? (
                  <Button
                    variant="ghost"
                    onClick={() =>
                      setQueue((current) =>
                        current.filter(
                          (item) =>
                            item.state !== 'uploaded' &&
                            item.state !== 'duplicate',
                        ),
                      )
                    }
                    disabled={isUploading}
                  >
                    Clear completed
                  </Button>
                ) : null}
                {failed.length ? (
                  <Button
                    variant="secondary"
                    onClick={() => void uploadItems(failed)}
                    disabled={isUploading}
                  >
                    Retry failed
                  </Button>
                ) : null}
                {pending.length ? (
                  <Button
                    onClick={() => void uploadItems(pending)}
                    disabled={isUploading}
                  >
                    {isUploading
                      ? 'Uploading…'
                      : `Upload ${pending.length} ${pending.length === 1 ? 'document' : 'documents'}`}
                  </Button>
                ) : null}
              </div>
            </div>
            <div className={styles.queueList}>
              {queue.map((item) => (
                <article className={styles.queueItem} key={item.id}>
                  <div>
                    <strong>{item.file.name}</strong>
                    <span>{formatFileSize(item.file.size)}</span>
                  </div>
                  <div
                    className={styles.queueStatus}
                    data-state={item.state}
                    role={item.state === 'failed' ? 'alert' : undefined}
                  >
                    <span>{uploadStateLabel(item)}</span>
                    {(item.state === 'pending' || item.state === 'failed') &&
                    !isUploading ? (
                      <Button
                        variant="ghost"
                        onClick={() =>
                          setQueue((current) =>
                            current.filter((entry) => entry.id !== item.id),
                          )
                        }
                      >
                        Remove
                      </Button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}
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

function fileFingerprint(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function uploadStateLabel(item: UploadQueueItem): string {
  if (item.state === 'pending') return 'Ready to upload';
  if (item.state === 'uploading') return 'Uploading…';
  if (item.state === 'uploaded') return 'Uploaded and queued';
  if (item.state === 'duplicate') return 'Already in library';
  return item.error ?? 'Upload failed';
}

function DocumentRow({ document }: { document: DocumentRecord }) {
  return (
    <article className={styles.documentRow}>
      <div className={styles.documentIdentity}>
        <div className={styles.fileMark} aria-hidden="true">
          {fileType(document)}
        </div>
        <div>
          <h3>
            <Link to={`/documents/${document.id}`}>{document.filename}</Link>
          </h3>
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

function isProcessing(status: DocumentRecord['status']): boolean {
  return ['queued', 'parsing', 'extracting', 'embedding', 'indexing'].includes(
    status,
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
