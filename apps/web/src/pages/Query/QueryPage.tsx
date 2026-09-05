import {
  ApiError,
  createDocumentApiClient,
  DEFAULT_API_BASE_URL,
} from '@doc-intelligence/api-client';
import { useMutation, useQuery } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { Button } from '../../components/Button/Button';
import { Card } from '../../components/Card/Card';
import { Input } from '../../components/Input/Input';
import styles from './QueryPage.module.scss';

const client = createDocumentApiClient(
  import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE_URL,
);

export function QueryPage() {
  const [question, setQuestion] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedDocumentId = searchParams.get('document') ?? '';
  const documents = useQuery({
    queryKey: ['documents', 'query-scope'],
    queryFn: ({ signal }) => client.listDocuments({ signal }),
  });
  const queryMutation = useMutation({
    mutationFn: ({
      value,
      documentId,
    }: {
      value: string;
      documentId: string;
    }) =>
      client.queryCorpus(value, {
        documentId: documentId || undefined,
      }),
  });
  const readyDocuments =
    documents.data?.items.filter((document) => document.status === 'ready') ??
    [];
  const selectedDocument = readyDocuments.find(
    (document) => document.id === selectedDocumentId,
  );
  const scopeLabel = selectedDocumentId
    ? (selectedDocument?.filename ?? 'Selected document')
    : 'All documents';

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    if (normalized) {
      queryMutation.mutate({
        value: normalized,
        documentId: selectedDocumentId,
      });
    }
  }

  function changeScope(documentId: string) {
    const next = new URLSearchParams(searchParams);
    if (documentId) next.set('document', documentId);
    else next.delete('document');
    setSearchParams(next, { replace: true });
    queryMutation.reset();
  }

  const errorMessage = queryMutation.error
    ? queryMutation.error instanceof ApiError
      ? queryMutation.error.message
      : 'The document corpus could not be queried right now.'
    : null;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Corpus intelligence</p>
        <h1>Ask across your documents.</h1>
        <p>
          Answers combine keyword, semantic, and extracted-knowledge retrieval.
          Every source remains linked to its document evidence.
        </p>
      </header>

      <Card className={styles.queryCard}>
        <form onSubmit={submit}>
          <div className={styles.scopeField}>
            <label htmlFor="query-scope">Answer scope</label>
            <div className={styles.scopeControl}>
              <select
                id="query-scope"
                value={selectedDocumentId}
                onChange={(event) => changeScope(event.target.value)}
                disabled={documents.isPending || queryMutation.isPending}
              >
                <option value="">All documents</option>
                {selectedDocumentId && !selectedDocument ? (
                  <option value={selectedDocumentId}>
                    Selected document unavailable
                  </option>
                ) : null}
                {readyDocuments.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.filename}
                  </option>
                ))}
              </select>
              {selectedDocumentId ? (
                <Button variant="ghost" onClick={() => changeScope('')}>
                  Clear scope
                </Button>
              ) : null}
            </div>
            <p>
              {selectedDocumentId
                ? `Answers will use only ${scopeLabel}.`
                : 'Answers may use evidence from every ready document.'}
            </p>
          </div>
          <label htmlFor="corpus-question">Question</label>
          <div className={styles.controls}>
            <Input
              id="corpus-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={
                selectedDocumentId
                  ? `Ask about ${scopeLabel}…`
                  : 'What do these documents say about…?'
              }
              maxLength={2000}
              disabled={queryMutation.isPending}
            />
            <Button
              type="submit"
              disabled={!question.trim() || queryMutation.isPending}
            >
              {queryMutation.isPending ? 'Finding evidence…' : 'Ask documents'}
            </Button>
          </div>
        </form>
        {errorMessage ? (
          <p className={styles.error} role="alert">
            {errorMessage}
          </p>
        ) : null}
      </Card>

      {queryMutation.data ? (
        <section className={styles.result} aria-live="polite">
          <Card className={styles.answer}>
            <p className={styles.eyebrow}>
              Answer · {scopeLabel} · {queryMutation.data.query_type}
            </p>
            <p>{queryMutation.data.answer}</p>
          </Card>

          <div className={styles.sources}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.eyebrow}>Evidence</p>
                <h2>Sources</h2>
              </div>
              <span>{queryMutation.data.sources.length} cited</span>
            </div>
            {queryMutation.data.sources.length ? (
              queryMutation.data.sources.map((source) => (
                <article key={source.chunk_id} className={styles.source}>
                  <div className={styles.sourceMeta}>
                    <span>[{source.citation_number}]</span>
                    <Link to={`/documents/${source.document_id}`}>
                      {source.filename}
                    </Link>
                    <span>{pageLabel(source.page_start, source.page_end)}</span>
                  </div>
                  <blockquote>{source.excerpt}</blockquote>
                  <div className={styles.matches}>
                    {source.match_types.map((type) => (
                      <span key={type}>{type}</span>
                    ))}
                  </div>
                </article>
              ))
            ) : (
              <p className={styles.empty}>No supporting sources were found.</p>
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function pageLabel(start: number | null, end: number | null) {
  if (start === null) return 'Page unavailable';
  return end !== null && end !== start
    ? `Pages ${start}–${end}`
    : `Page ${start}`;
}
