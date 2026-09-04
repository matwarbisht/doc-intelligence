import {
  ApiError,
  createDocumentApiClient,
  DEFAULT_API_BASE_URL,
} from '@doc-intelligence/api-client';
import { useMutation } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link } from 'react-router';

import { Button } from '../../components/Button/Button';
import { Card } from '../../components/Card/Card';
import { Input } from '../../components/Input/Input';
import styles from './QueryPage.module.scss';

const client = createDocumentApiClient(
  import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE_URL,
);

export function QueryPage() {
  const [question, setQuestion] = useState('');
  const queryMutation = useMutation({
    mutationFn: (value: string) => client.queryCorpus(value),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    if (normalized) queryMutation.mutate(normalized);
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
          <label htmlFor="corpus-question">Question</label>
          <div className={styles.controls}>
            <Input
              id="corpus-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What do these documents say about…?"
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
              Answer · {queryMutation.data.query_type}
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
