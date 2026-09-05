# Example corpus

Every document in this directory is fictional and was written specifically for
development and demonstrations. It contains no customer data, credentials, or
personally identifiable information.

The corpus deliberately mixes prose, meeting notes, and invoice-like content so
that keyword, semantic, and structured retrieval can be exercised together.
`evaluation.json` records a few stable questions and the filenames expected to
support each answer. It is a smoke-test fixture, not a retrieval benchmark.

Run the deterministic database integration path with:

```bash
make db-test
```

With the full local application and provider credentials already running, test
a real provider-backed upload-to-answer flow with:

```bash
make live-e2e
```

The live command uploads a synthetic file to the local library and consumes
Unstructured and Gemini quota. Never place private documents in this directory.
