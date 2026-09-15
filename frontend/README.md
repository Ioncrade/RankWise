# RankWise web client

The frontend is a React 19 + TypeScript + Vite application built with local shadcn-style
components, Radix primitives, Tailwind CSS, and Lucide icons. It targets the versioned RankWise
backend API; the legacy `/upload_pdf` and `/ask` routes are intentionally not used.

## Run locally

Start the backend from the repository root:

```bash
uv run flask --app backend/app.py run
```

Then start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the client at `http://127.0.0.1:3000` and proxies `/v1` and `/health` to the backend
at `http://127.0.0.1:5000`. Set `VITE_API_BASE_URL` when the API is on a different origin. That
deployment must also configure the corresponding CORS policy.

## Production build

```bash
npm test
npm run typecheck
npm run format:check
npm run build
```

The Vite build is written to `backend/build`, which is the static directory served by the Flask
application. Source maps are emitted for debugging.

## Product flows

- Change the development workspace/tenant ID.
- Create and switch collections.
- Upload up to 20 PDFs or standalone images per request and poll ingestion jobs.
- Ask collection-scoped questions and preview authorized evidence regions.
- Generate comprehensive notes, concise notes, formula sheets, reaction sheets, flashcards, and
  practice questions.
- Export Markdown and regenerate one section into a new immutable version.
- Run symbolic math, unit conversion, plotting, reaction balancing, and molecule analysis.
- Perform explicit-consent PubChem lookup with clear external-enrichment labeling.
- Inspect backend capability/readiness state.
- Select Auto, Groq-only, or Local Ollama generation from the sidebar. Auto preserves the same
  retrieved evidence and falls back to Ollama after retryable Groq failures.

Generated note IDs are kept in browser local storage because the current backend exposes note
lookup/version endpoints but not a collection-level note-list endpoint. The note content itself
remains stored by the backend. `X-Tenant-ID` is a development isolation header, not authentication;
production must derive it from an authenticated gateway.
