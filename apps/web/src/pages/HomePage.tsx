import { DEFAULT_API_BASE_URL } from '@doc-intelligence/api-client';
import { Link } from 'react-router';

import { Card } from '../components/Card/Card';
import styles from './HomePage.module.scss';

const apiBaseUrl = import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE_URL;

export function HomePage() {
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>Stage 1 · MVP</p>
          <h1 className={styles.title}>Turn documents into intelligence.</h1>
        </div>
        <div>
          <p className={styles.summary}>
            Transform heterogeneous files into searchable structure, semantic
            facts, and answers grounded in source evidence.
          </p>
          <div className={styles.actions}>
            <Link className={styles.primaryLink} to="/style-guide">
              Explore the system
            </Link>
            <a className={styles.secondaryLink} href={`${apiBaseUrl}/docs`}>
              API documentation
            </a>
          </div>
        </div>
      </section>

      <section className={styles.details} aria-label="Product foundations">
        <Card className={styles.detailCard}>
          <span>01</span>
          <h2>Canonical structure</h2>
          <p>
            Preserve headings, paragraphs, tables, pages, and reading order.
          </p>
        </Card>
        <Card className={styles.detailCard}>
          <span>02</span>
          <h2>Semantic enrichment</h2>
          <p>
            Extract reusable entities and facts without discarding source
            context.
          </p>
        </Card>
        <Card className={styles.detailCard}>
          <span>03</span>
          <h2>Cited retrieval</h2>
          <p>
            Combine structured and semantic search with auditable provenance.
          </p>
        </Card>
      </section>
    </div>
  );
}
