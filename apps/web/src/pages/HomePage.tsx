import { DEFAULT_API_BASE_URL } from '@doc-intelligence/api-client';

const apiBaseUrl = import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE_URL;

export function HomePage() {
  return (
    <section className="hero">
      <p className="eyebrow">Stage 1 · MVP</p>
      <h1>Turn documents into intelligence.</h1>
      <p className="lede">
        The application foundation is ready. Document ingestion, enrichment, and
        retrieval are next.
      </p>
      <p className="status">API: {apiBaseUrl}</p>
    </section>
  );
}
