import { type DocumentStatus } from '@doc-intelligence/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router';

import { api } from '../../api/client';
import { useCapabilities } from '../../api/useCapabilities';
import { Card } from '../../components/Card/Card';
import { Button } from '../../components/Button/Button';
import styles from './DocumentDetailPage.module.scss';

export function DocumentDetailPage() {
  const { documentId = '' } = useParams();
  const queryClient = useQueryClient();
  const capabilities = useCapabilities();
  const retryEnabled =
    capabilities.data?.processing !== false &&
    capabilities.data?.processing_retries !== false;
  const askEnabled = capabilities.data?.ask !== false;
  const [retryAttemptBaseline, setRetryAttemptBaseline] = useState<
    number | null
  >(null);
  const document = useQuery({
    queryKey: ['documents', documentId],
    queryFn: ({ signal }) => api.getDocument(documentId, { signal }),
    enabled: Boolean(documentId),
    refetchInterval: (query) =>
      query.state.data &&
      (isProcessing(query.state.data.status) || retryAttemptBaseline !== null)
        ? 2_000
        : false,
  });
  const retry = useMutation({
    mutationFn: () => api.processDocument(documentId),
    onMutate: () => {
      setRetryAttemptBaseline(totalAttempts(document.data?.processing ?? []));
    },
    onError: () => setRetryAttemptBaseline(null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['documents', documentId],
      });
    },
  });

  useEffect(() => {
    if (
      retryAttemptBaseline !== null &&
      document.data &&
      !isProcessing(document.data.status) &&
      totalAttempts(document.data.processing) > retryAttemptBaseline
    ) {
      setRetryAttemptBaseline(null);
    }
  }, [document.data, retryAttemptBaseline]);

  if (document.isPending)
    return <p className={styles.state}>Loading document…</p>;
  if (document.error)
    return <p className={styles.state}>{document.error.message}</p>;

  const detail = document.data;
  const sources = new Map(
    detail.sources.map((source) => [source.chunk_id, source]),
  );
  const entities = new Map(
    detail.entities.map((entity) => [entity.id, entity]),
  );

  return (
    <div className={styles.page}>
      <Link className={styles.back} to="/documents">
        ← Document library
      </Link>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Document intelligence</p>
          <h1>{detail.filename}</h1>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.status} data-status={detail.status}>
            {detail.status.replaceAll('_', ' ')}
          </span>
          {detail.status === 'ready' && askEnabled ? (
            <Link
              className={styles.askLink}
              to={`/ask?document=${encodeURIComponent(detail.id)}`}
            >
              Ask about this document
            </Link>
          ) : null}
          {isFailed(detail.status) ? (
            <Button
              variant="secondary"
              onClick={() => retry.mutate()}
              disabled={
                retry.isPending ||
                retryAttemptBaseline !== null ||
                !retryEnabled
              }
            >
              {!retryEnabled
                ? 'Retries unavailable'
                : retry.isPending || retryAttemptBaseline !== null
                  ? 'Retry queued…'
                  : 'Retry processing'}
            </Button>
          ) : null}
        </div>
      </header>
      {retry.error ? (
        <p className={styles.retryError} role="alert">
          {retry.error.message}
        </p>
      ) : null}

      <section className={styles.metrics} aria-label="Processing overview">
        <Card>
          <strong>{detail.chunk_count}</strong>
          <span>Chunks</span>
        </Card>
        <Card>
          <strong>{detail.embedding_count}</strong>
          <span>Embeddings</span>
        </Card>
        <Card>
          <strong>{detail.entities.length}</strong>
          <span>Entities</span>
        </Card>
        <Card>
          <strong>{detail.facts.length}</strong>
          <span>Facts</span>
        </Card>
      </section>

      <section className={styles.grid}>
        <Card className={styles.summary}>
          <p className={styles.eyebrow}>Summary</p>
          <h2>
            {detail.extraction?.document_type?.replaceAll('_', ' ') ??
              'Pending'}
          </h2>
          <p>
            {detail.extraction?.summary ??
              'Semantic extraction has not completed yet.'}
          </p>
          <div className={styles.tags}>
            {detail.extraction?.topics.map((topic) => (
              <span key={topic}>{topic}</span>
            ))}
          </div>
        </Card>

        <Card>
          <p className={styles.eyebrow}>Pipeline</p>
          <ol className={styles.pipeline}>
            {detail.processing.map((job) => (
              <li key={job.stage} data-status={job.status}>
                <span>{job.stage}</span>
                <small>{job.status}</small>
              </li>
            ))}
          </ol>
        </Card>
      </section>

      <DetailSection
        title="Entities"
        empty="No entities extracted yet."
        hasItems={detail.entities.length > 0}
      >
        <div className={styles.tags}>
          {detail.entities.map((entity) => (
            <span key={entity.id}>
              {entity.canonical_name} · {entity.entity_type}
            </span>
          ))}
        </div>
      </DetailSection>

      <DetailSection
        title="Facts"
        empty="No facts extracted yet."
        hasItems={detail.facts.length > 0}
      >
        <div className={styles.records}>
          {detail.facts.map((fact) => (
            <article key={fact.id}>
              <p>
                <strong>{fact.subject}</strong>{' '}
                {fact.predicate.replaceAll('_', ' ')}{' '}
                <strong>{fact.object_value}</strong>
              </p>
              <Source source={sources.get(fact.source_chunk_id)} />
            </article>
          ))}
        </div>
      </DetailSection>

      <DetailSection
        title="Relationships"
        empty="No relationships extracted yet."
        hasItems={detail.relationships.length > 0}
      >
        <div className={styles.records}>
          {detail.relationships.map((relationship) => (
            <article key={relationship.id}>
              <p>
                <strong>
                  {entities.get(relationship.subject_entity_id)
                    ?.canonical_name ?? 'Entity'}
                </strong>{' '}
                {relationship.predicate.replaceAll('_', ' ')}{' '}
                <strong>
                  {relationship.object_entity_id
                    ? entities.get(relationship.object_entity_id)
                        ?.canonical_name
                    : relationship.object_text}
                </strong>
              </p>
              <Source source={sources.get(relationship.source_chunk_id)} />
            </article>
          ))}
        </div>
      </DetailSection>
    </div>
  );
}

function DetailSection({
  title,
  empty,
  hasItems = true,
  children,
}: {
  title: string;
  empty: string;
  hasItems?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={styles.section}>
      <h2>{title}</h2>
      {hasItems ? children : <p className={styles.muted}>{empty}</p>}
    </section>
  );
}

function Source({
  source,
}: {
  source: { excerpt: string; page_start: number | null } | undefined;
}) {
  if (!source) return null;
  return (
    <blockquote>
      {source.excerpt}
      {source.page_start ? <cite>Page {source.page_start}</cite> : null}
    </blockquote>
  );
}

function isProcessing(status: DocumentStatus): boolean {
  return ['queued', 'parsing', 'extracting', 'embedding', 'indexing'].includes(
    status,
  );
}

function isFailed(status: DocumentStatus): boolean {
  return status.endsWith('_failed');
}

function totalAttempts(processing: { attempts: number }[]): number {
  return processing.reduce((total, job) => total + job.attempts, 0);
}
