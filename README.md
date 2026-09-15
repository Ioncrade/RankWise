# RankWise

RankWise is a source-grounded study workspace for PDFs and images. It ingests course material,
retrieves evidence with resolvable page or image-region citations, answers questions, and creates
structured study artifacts for mathematics, science, and chemistry.

The repository currently contains the backend through Phase 3 and a rebuilt React TypeScript
frontend. Product scope and planned improvements are documented in
[PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) and
[BACKEND_RAG_CHECKPOINTS.md](BACKEND_RAG_CHECKPOINTS.md). The local-model fallback design is in
[LOCAL_LLM_FALLBACK_PLAN.md](LOCAL_LLM_FALLBACK_PLAN.md).

## Current capabilities

- Tenant-scoped collections with batches of up to 20 PDFs or images per request.
- Native PDF extraction with selective Tesseract OCR and extraction provenance.
- BM25 and dense retrieval, reciprocal-rank fusion, cross-encoder reranking, and validated
  evidence citations.
- Grounded questions and comprehensive, concise, formula, and reaction notes.
- Flashcards, practice questions, Markdown export, and immutable section regeneration.
- Authorized page and evidence-region rendering.
- Bounded symbolic mathematics, unit conversion, plotting, chemical-equation balancing, and
  molecule analysis.
- Explicit-consent PubChem enrichment, kept separate from uploaded-source evidence.
- Groq generation with configurable Ollama local-model fallback and provider status reporting.
- A minimalist React 19, TypeScript, Vite, Tailwind, Radix, and shadcn-style web client.

## Architecture

```text
Browser
  └─ React + TypeScript client
       └─ Flask /v1 API
            ├─ SQLite collection, job, image, and note catalog
            ├─ PDF/image parser + selective OCR
            ├─ sentence-transformer embeddings + per-document FAISS indexes
            ├─ BM25 + dense retrieval + RRF + cross-encoder reranking
            ├─ Groq grounded generation + citation validation
            ├─ SymPy, Pint, matplotlib, and RDKit tools
            └─ local versioned documents, images, and cache
```

The frontend build is emitted into `backend/build` and served by Flask, so production can use one
origin for the browser and API. During development, Vite proxies `/v1` and `/health` to Flask.

The complete HTTP contract is in [backend/openapi.yaml](backend/openapi.yaml).

## Repository layout

```text
RankWise/
├── backend/
│   ├── app.py                 # WSGI entry point
│   ├── rankwise/              # API, RAG pipeline, storage, jobs, and tools
│   ├── tests/                 # deterministic backend test suite
│   ├── evaluation/            # retrieval and domain fixture gates
│   ├── build/                 # generated production frontend
│   ├── openapi.yaml           # versioned API contract
│   └── .env.example
├── frontend/
│   ├── src/api/               # typed API client and contracts
│   ├── src/components/        # product views and UI primitives
│   ├── vite.config.ts
│   └── package.json
├── pyproject.toml             # Python dependencies and tool configuration
├── uv.lock                    # locked Python dependency graph
├── PRODUCT_REQUIREMENTS.md
└── BACKEND_RAG_CHECKPOINTS.md
```

## Prerequisites

- Python 3.11–3.13. The repository's `.python-version` selects Python 3.12.
- [`uv`](https://docs.astral.sh/uv/) for Python environments and locked dependencies.
- Node.js `^20.19.0` or `>=22.12.0`, as required by the installed Vite version.
- npm, using the committed `frontend/package-lock.json`.
- Tesseract plus the requested language packs if OCR is required.
- A Groq API key and active Groq model ID for generated answers and artifacts.

Tesseract is optional for native-text PDFs and deterministic tools. On Debian or Ubuntu, English
OCR can be installed with:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

## Local setup

### 1. Clone the repository

```bash
git clone https://github.com/Ioncrade/RankWise.git
cd RankWise
```

### 2. Install backend dependencies

Install the full ML, science, and chemistry feature set from the lockfile:

```bash
uv sync --extra ml --extra science --extra chemistry
```

The first real backend startup may download the configured embedding and reranker models. Tests
use local deterministic adapters and do not download those models.

### 3. Configure the backend

```bash
cp backend/.env.example backend/.env
```

For generated answers and notes, edit `backend/.env` and provide both values:

```dotenv
GROQ_API_KEY=replace-with-a-secret
GROQ_MODEL=replace-with-an-active-model-id
```

To enable local generation, install [Ollama](https://ollama.com), start its local service, pull a
model, and configure it in `backend/.env`:

```bash
ollama pull gemma3
```

```dotenv
RANKWISE_GENERATION_PROVIDER=auto
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3
```

`auto` prefers Groq and falls back to Ollama for retryable Groq failures such as rate limits and
temporary provider errors. The frontend sidebar also supports manual `Groq` and `Local Ollama`
modes. Both providers receive the same backend-retrieved evidence context and validated citation
labels.

Do not commit `backend/.env`. Without these values, ingestion, retrieval, evidence rendering, and
deterministic tools still work, while `/health/ready` returns `503` and generation controls remain
disabled.

### 4. Install frontend dependencies

```bash
cd frontend
npm ci
cd ..
```

### 5. Start development servers

Start Flask from the repository root:

```bash
uv run flask --app backend/app.py run --host 127.0.0.1 --port 5000
```

In another terminal, start Vite:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:3000`. Vite proxies API and health requests to
`http://127.0.0.1:5000`.

### Production-like local run

Build the client first, then let Flask serve both the SPA and API:

```bash
cd frontend
npm run build
cd ..
uv run flask --app backend/app.py run --host 127.0.0.1 --port 5000
```

Open `http://127.0.0.1:5000`. The Flask development server is suitable for this local check, not
for an internet-facing deployment.

## Configuration

Backend settings are read from the process environment after loading `backend/.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | unset | Secret used for grounded answer and artifact generation. |
| `GROQ_MODEL` | unset | Active Groq model ID; deliberately has no hard-coded default. |
| `RANKWISE_GENERATION_PROVIDER` | `auto` | `auto`, `groq`, or `ollama` server default. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Server-side Ollama origin. |
| `OLLAMA_MODEL` | unset | Installed Ollama model used for local generation. |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Ollama generation timeout; readiness checks cap at two seconds. |
| `OLLAMA_API_KEY` | unset | Optional credential for a remote authenticated Ollama service. |
| `RANKWISE_DATA_DIR` | `backend/data` | SQLite, source files, chunks, indexes, images, and caches. Relative values are resolved from `backend/`. |
| `RANKWISE_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Dense embedding model. Changing it requires rebuilding existing indexes. |
| `RANKWISE_RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Candidate reranker. |
| `RANKWISE_CANDIDATE_K` | `30` | Retrieval candidates before reranking. |
| `RANKWISE_CONTEXT_K` | `5` | Evidence chunks supplied to generation; must not exceed candidate K. |
| `RANKWISE_CHUNK_SIZE` | `1200` | Target extracted-text chunk size. |
| `RANKWISE_CHUNK_OVERLAP` | `150` | Chunk overlap; must be smaller than chunk size. |
| `RANKWISE_MAX_UPLOAD_BYTES` | `52428800` | Maximum HTTP request size in bytes. |
| `RANKWISE_OCR_ENABLED` | `true` | Enables selective OCR routing. |
| `RANKWISE_OCR_LANGUAGES` | `eng` | Tesseract language codes, joined with `+` for multiple languages. |
| `RANKWISE_OCR_DPI` | `200` | OCR render resolution. |
| `RANKWISE_OCR_MIN_CHARACTERS` | `24` | Low-text threshold used by OCR routing. |
| `RANKWISE_RENDER_MAX_DPI` | `300` | Maximum evidence/page render resolution. |
| `HOST` | `127.0.0.1` | Host used only by `python backend/app.py`. |
| `PORT` | `5000` | Port used only by `python backend/app.py`. |
| `FLASK_DEBUG` | `false` | Debug flag used only by `python backend/app.py`; never enable in production. |
| `VITE_API_BASE_URL` | empty | Optional frontend API origin. Leave empty for the Vite proxy or same-origin production. |

## Database schema

The application creates a SQLite database at `RANKWISE_DATA_DIR/catalog.sqlite3` on startup and
enables write-ahead logging. There is currently no migration framework; schema changes must be
introduced carefully before production data exists.

All identifiers and timestamps are stored as `TEXT`. Timestamps are UTC ISO-8601 strings. Columns
ending in `_json` contain serialized JSON.

### `collections`

| Column | Constraints | Meaning |
| --- | --- | --- |
| `collection_id` | primary key | Generated `col_...` identifier. |
| `tenant_id` | not null, indexed with `created_at` | Development tenant/workspace boundary. |
| `title` | not null | Collection display name. |
| `subject` | not null | Subject classification. |
| `education_level` | not null | Intended learning level. |
| `created_at` | not null | Creation timestamp. |

### `collection_documents`

| Column | Constraints | Meaning |
| --- | --- | --- |
| `collection_id` | foreign key to `collections`, cascade delete | Owning collection. |
| `document_version_id` | composite primary key | Immutable `dv_...` version stored on disk. |
| `added_at` | not null | Time the version joined the collection. |

The primary key is `(collection_id, document_version_id)`. Document metadata is not duplicated in
SQLite; it lives in the versioned document directory described below.

### `jobs`

| Column | Constraints | Meaning |
| --- | --- | --- |
| `job_id` | primary key | Generated `job_...` identifier. |
| `tenant_id` | not null | Tenant that may read the job. |
| `kind` | not null | Ingestion, generation, or regeneration operation. |
| `status` | not null | `queued`, `running`, `succeeded`, or `failed`. |
| `payload_json` | not null | Submitted job parameters. |
| `result_json` | nullable | Successful result metadata. |
| `error_json` | nullable | Stable error code, message, and optional details. |
| `created_at` | not null | Creation timestamp. |
| `updated_at` | not null | Last state-transition timestamp. |

### `notes`

Each row is an immutable note version. Multiple rows share a logical `note_id`.

| Column | Constraints | Meaning |
| --- | --- | --- |
| `note_version_id` | primary key | Generated immutable `nv_...` version. |
| `note_id` | indexed with `created_at` | Stable logical note identifier. |
| `collection_id` | foreign key to `collections`, cascade delete | Owning collection. |
| `title` | not null | Artifact title. |
| `profile` | not null | Note/artifact type. |
| `markdown` | not null | Rendered and exportable note body. |
| `content_json` | not null | Structured `rankwise.note.v1` content. |
| `citations_json` | not null | Evidence records used by this version. |
| `document_versions_json` | not null | Exact immutable source scope. |
| `warnings_json` | not null | Extraction or generation warnings. |
| `change_reason` | not null | Initial generation or section-regeneration reason. |
| `created_at` | not null | Version timestamp. |

### `images`

| Column | Constraints | Meaning |
| --- | --- | --- |
| `image_id` | primary key | Content-derived `img_...` identifier. |
| `collection_id` | foreign key to `collections`, cascade delete | Owning collection. |
| `filename` | not null | Sanitized original filename. |
| `mime_type` | not null | Validated media type. |
| `sha256` | not null | Content digest. |
| `document_version_id` | not null | PDF-converted version used by retrieval. |
| `storage_path` | not null | Server-side original-image path. Never returned publicly. |
| `warnings_json` | not null | Ingestion warnings. |
| `created_at` | not null | Creation timestamp. |

The schema also creates `idx_collections_tenant` and `idx_notes_current`. Tenant checks are direct
for collections and jobs and inherited through the owning collection for notes, images, documents,
and evidence.

## Filesystem data layout

SQLite is only the catalog. The default local runtime layout is:

```text
backend/data/
├── catalog.sqlite3
├── catalog.sqlite3-wal       # present while WAL has pending pages
├── state.json                # active document for legacy endpoints
├── documents/
│   └── dv_<id>/
│       ├── document.json     # extraction metadata and provenance
│       ├── chunks.json       # text/equation/table chunks and evidence IDs
│       └── source.pdf        # immutable source or image-converted PDF
├── indices/
│   └── dv_<id>.faiss
├── images/
│   └── img_<id>/original.<extension>
├── external-cache/           # tenant-keyed PubChem response cache
├── pending/                  # temporary PDF ingestion files
└── pending-images/           # temporary image ingestion files
```

Back up the database and all of this directory as one consistency unit while the application is
quiesced, or use storage snapshots and SQLite-aware backup tooling. Copying only SQLite loses
documents and indexes; copying only files loses tenant ownership, note versions, and job state.

## API and frontend workflow

All `/v1` routes except health checks require `X-Tenant-ID`. The browser lets a developer choose
this value and sends it through the typed API client. This header provides development isolation,
not authentication.

A typical request sequence is:

1. Create a collection with `POST /v1/collections`.
2. Upload PDFs or images to that collection.
3. Poll the returned `/v1/jobs/{job_id}` resources until they succeed or fail.
4. Ask grounded questions or request an artifact.
5. Open returned evidence links or export a note version.

The backend does not yet expose a collection-level note-list endpoint. The frontend therefore
stores only recently generated note IDs in browser local storage; note content remains on the
backend.

Health endpoints:

- `GET /health/live` — process liveness.
- `GET /health/ready` — generation-provider readiness plus individual feature capabilities.
- `GET /health` — compatibility liveness route.
- `GET /v1/providers` — configured Groq/Ollama status and local-model availability; never returns secrets.

## Tests and quality gates

Run the complete verification suite from the repository root:

```bash
uv run pytest
uv run ruff check backend

cd frontend
npm test
npm run typecheck
npm run format:check
npm run build
npm audit --audit-level=moderate
```

The current backend suite has 31 tests and 85.62% statement coverage. Backend tests use local
deterministic adapters and do not call Groq or PubChem. Evaluation fixtures and commands are in
[backend/evaluation/README.md](backend/evaluation/README.md).

## Cloud deployment

### Current code: single-instance pilot

The current implementation can run safely as a controlled pilot on a container or virtual machine
when all of the following are true:

- Run exactly one application replica against one persistent volume.
- Mount that volume at a stable path such as `/var/lib/rankwise` and set
  `RANKWISE_DATA_DIR=/var/lib/rankwise`.
- Build the frontend during image/CI creation with `npm ci && npm run build`; include
  `backend/build` in the runtime artifact.
- Install Python dependencies with
  `uv sync --frozen --no-dev --extra ml --extra science --extra chemistry`.
- Install Tesseract and required language packs in the runtime image if OCR is enabled.
- Supply `GROQ_API_KEY` through the platform's secret manager and the remaining settings through
  deployment environment variables.
- Put the service behind TLS and an authenticated reverse proxy that removes any client-provided
  `X-Tenant-ID` and injects the tenant derived from the authenticated identity.
- Give the container enough memory for the embedding model, reranker, FAISS, OCR, and optional
  chemistry dependencies. Measure representative documents before fixing production limits.
- Persist or pre-populate model caches to avoid downloading models on every restart.
- Back up the complete data volume and test restoration regularly.

Add and lock a production WSGI server before deploying—for example, `uv add gunicorn`. Because jobs
currently execute inside the web process, keep one worker process for the pilot and use threads for
concurrent HTTP requests. A representative start command is:

```bash
gunicorn --workers 1 --threads 4 --timeout 180 \
  --bind "0.0.0.0:${PORT:-8080}" backend.app:app
```

Configure the platform health checks as:

- Liveness: `/health/live`
- Readiness: `/health/ready` only when generated answers are mandatory. It intentionally returns
  `503` when either Groq setting is absent.

Do not use an ephemeral serverless filesystem for the current design. SQLite, source documents,
FAISS files, and in-process background jobs require stable local state.

### Production target: horizontally scalable deployment

Before running multiple API replicas, split the current local responsibilities:

```text
CDN / load balancer
  └─ identity-aware API gateway
       ├─ stateless Flask API replicas
       ├─ durable ingestion/generation queue ── worker pool
       ├─ PostgreSQL catalog
       ├─ object storage for PDFs, images, exports, and rendered evidence
       ├─ managed vector index or versioned shared index service
       └─ shared cache, metrics, logs, and traces
```

Recommended migration order:

1. Replace the user-controlled tenant header with authenticated identity and authorization.
2. Introduce a real migration tool and move the catalog tables to PostgreSQL. Use native JSON/JSONB
   where appropriate, preserve immutable document/note IDs, and retain foreign keys.
3. Move PDFs, original images, chunks, and derived artifacts to private object storage. Store
   opaque object keys in the catalog and return short-lived authorized downloads rather than
   public bucket URLs.
4. Replace `BackgroundJobRunner` with a durable queue. Workers should claim idempotent jobs,
   persist progress, retry transient failures, and recover queued/running work after crashes.
5. Replace per-replica FAISS files with a vector service, pgvector, or a versioned shared-index
   design. Store the embedding model/version with every index and rebuild on model changes.
6. Move enrichment caching, rate limits, and short-lived coordination to a shared cache.
7. Add structured logs, request/job IDs, traces, latency/error metrics, queue-depth alerts, storage
   monitoring, and audit events for document/evidence access.
8. Add malware scanning, file-signature validation, egress restrictions, secret rotation, database
   encryption, object-store encryption, retention/deletion workflows, and tested disaster recovery.
9. Deploy API and worker revisions compatibly: migrate the database first, roll workers, then roll
   API instances. Keep old document and note versions readable during the deployment.

For a same-origin deployment, serve the generated frontend through Flask or a reverse proxy and
leave `VITE_API_BASE_URL` empty. If the frontend is hosted on a separate CDN origin, set that value
at build time and configure a strict backend CORS allowlist; CORS is not currently configured by
the application.

## Current production boundaries

- `X-Tenant-ID` is not authentication.
- SQLite and the local filesystem make the current service single-replica.
- Job state is durable, but queued or running work does not resume after a process crash.
- Ollama fallback is server-mediated; the browser never connects directly to the local model.
- Provider switching reconstructs context from backend evidence. It does not migrate hidden model
  memory or chain-of-thought state.
- Tesseract quality still needs CER/WER benchmarking on representative scans and equations.
- The formula parser is not a chemical mechanism parser, and visual molecule/reaction-mechanism
  understanding remains out of scope.
- Chemistry safety checks are a narrow deterministic baseline, not a comprehensive public-release
  safety system.
- Fixture tests demonstrate integration behavior, not production retrieval, OCR, or educational
  quality.

See [backend/README.md](backend/README.md) for endpoint examples and detailed phase behavior, and
[frontend/README.md](frontend/README.md) for client-specific development notes.
