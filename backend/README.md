# RankWise backend

The Phase 3 backend provides tenant-scoped PDF/image collections, selective OCR with provenance, layout/table/equation extraction, page-region rendering, BM25+dense retrieval, grounded questions, comprehensive/concise/formula/reaction notes, flashcard and practice-question artifacts, resolvable visual citations, deterministic symbolic math, units and reaction balancing, RDKit molecule analysis, opt-in PubChem enrichment, bounded plotting, Markdown export, and immutable section regeneration. Earlier API routes remain available for compatibility.

The legacy `backend/backend/faiss_index.bin` and `metadata.pkl` files are not loaded by the new backend. New runtime data uses safe JSON metadata under `backend/data/`, which is ignored by Git. The old artifacts remain only to avoid deleting repository data without an explicit migration decision.

## Setup

The supported Python range is 3.11–3.13; `.python-version` selects Python 3.12.

```bash
uv sync --extra ml --extra science --extra chemistry
cp backend/.env.example backend/.env
```

Selective OCR uses PyMuPDF's Tesseract integration. Install Tesseract and every configured language pack on the host—for example, `tesseract-ocr` and `tesseract-ocr-eng` on Debian/Ubuntu. `/health/ready` reports whether OCR and each science-tool dependency are available.

Set `GROQ_API_KEY` and an active `GROQ_MODEL` in `backend/.env` to enable generated answers and notes. Ingestion and evidence retrieval do not need a Groq key. Model IDs are intentionally not given a code default because hosted models are retired over time.

For local generation, install Ollama, pull a model such as `gemma3`, and set
`RANKWISE_GENERATION_PROVIDER=auto`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, and
`OLLAMA_MODEL=gemma3`. The `auto` route prefers Groq and falls back to Ollama for retryable Groq
failures. The frontend can also request `groq` or `ollama` explicitly. Retrieval runs once and the
same evidence labels are passed to either provider; the browser never calls Ollama directly.

Run from the repository root:

```bash
uv run flask --app backend/app.py run
```

Or from `backend/`:

```bash
uv run --project .. flask --app app.py run
```

For a production deployment, use the WSGI entry point `backend.app:app` with an appropriate production server. The built-in Flask server is for development only.

## Phase 1 API flow

All `/v1` routes require a trusted `X-Tenant-ID` header. This is an isolation boundary, not authentication: a production deployment must derive or validate the tenant through an identity-aware gateway rather than accepting an arbitrary client header. The complete contract is in [`openapi.yaml`](openapi.yaml).

```bash
curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"title":"Physics revision","subject":"physics","education_level":"undergraduate"}' \
  http://127.0.0.1:5000/v1/collections

curl -H 'X-Tenant-ID: local-demo' \
  -F 'files=@mechanics.pdf' -F 'files=@thermodynamics.pdf' \
  http://127.0.0.1:5000/v1/collections/col_REPLACE_ME/documents

curl -H 'X-Tenant-ID: local-demo' \
  http://127.0.0.1:5000/v1/jobs/job_REPLACE_ME

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"query":"How are force, mass, and acceleration related?"}' \
  http://127.0.0.1:5000/v1/collections/col_REPLACE_ME/queries

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"title":"Exam notes","profile":"comprehensive"}' \
  http://127.0.0.1:5000/v1/collections/col_REPLACE_ME/notes

curl -H 'X-Tenant-ID: local-demo' \
  -o notes.md http://127.0.0.1:5000/v1/notes/note_REPLACE_ME/export.md
```

Each `/v1` citation is checked against retrieved evidence and resolves only inside the same tenant scope. Notes use the internal `rankwise.note.v1` schema and store the exact document-version scope so later uploads never silently change an existing note.

## Phase 2 images, visual evidence, and tools

```bash
curl -H 'X-Tenant-ID: local-demo' -F 'images=@free-body-diagram.png' \
  http://127.0.0.1:5000/v1/collections/col_REPLACE_ME/images

curl -H 'X-Tenant-ID: local-demo' \
  'http://127.0.0.1:5000/v1/documents/dv_REPLACE_ME/pages/1/render?dpi=180&x0=50&y0=80&x1=500&y1=600' \
  -o evidence.png

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"operation":"compare","expression":"(x+1)^2","other_expression":"x^2+2*x+1","variables":["x"]}' \
  http://127.0.0.1:5000/v1/tools/math

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"value":1000,"from_unit":"meter","to_unit":"kilometer"}' \
  http://127.0.0.1:5000/v1/tools/units/convert

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"expression":"sin(x)","variable":"x","start":-6.28,"end":6.28,"samples":500}' \
  http://127.0.0.1:5000/v1/tools/plot -o plot.png
```

Use `profile: "formula_sheet"` when creating notes to attach bounded symbolic parser observations to extracted equation evidence. A `parsed_not_proven` status means the notation was normalized successfully; it deliberately does not claim that a sourced physical law is mathematically true.

## Phase 3 chemistry and study artifacts

```bash
curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"equation":"CH4 + O2 -> CO2 + H2O"}' \
  http://127.0.0.1:5000/v1/tools/chemistry/balance

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"notation":"CCO","format":"smiles"}' \
  http://127.0.0.1:5000/v1/tools/chemistry/molecule

curl -H 'X-Tenant-ID: local-demo' -H 'Content-Type: application/json' \
  -d '{"title":"Organic chemistry review","type":"reaction_sheet"}' \
  http://127.0.0.1:5000/v1/collections/col_REPLACE_ME/artifacts
```

Artifact types are `reaction_sheet`, `flashcards`, and `practice_questions`. Reaction sheets
retain the extracted source reaction and put a deterministic result beneath a separate
`Verified calculation` label. A failed or ambiguous balance is recorded as `not_verified`.
The chemistry prompt explicitly prohibits adding absent catalysts, solvents, temperatures,
yields, hazards, or procedures.

External chemical lookup is never called during ingestion or note generation. A client must
call `POST /v1/tools/chemistry/lookup` with `"consent": true`. Responses are marked
`external_enrichment`, include the PubChem URL and UTC retrieval time, and use a tenant-keyed
seven-day cache. This is optional enrichment, not source-PDF evidence.

## Legacy Phase 0 flow

```bash
curl -F file=@document.pdf http://127.0.0.1:5000/upload_pdf
curl -H 'Content-Type: application/json' \
  -d '{"query":"What is the main result?"}' \
  http://127.0.0.1:5000/ask
```

Legacy routes can access only the one active document uploaded through the legacy flow. Collection documents are not published to that global compatibility slot.

## Health endpoints

- `GET /health/live` checks that the web process is alive.
- `GET /health/ready` checks that answer generation has the required provider configuration. It returns `503` when `GROQ_API_KEY` or `GROQ_MODEL` is absent.
- `GET /health` is the compatibility liveness route.
- `GET /v1/providers` reports configured provider/model readiness without returning secrets.

## Tests and evaluation

```bash
uv run pytest
uv run ruff check backend
```

Tests use deterministic local adapters, so they do not download transformer models, call Groq, or contact PubChem. The suite covers five-PDF ingestion, selective-OCR decisions, table/equation regions, searchable standalone images, visual rendering, formula/reaction tool observations, symbolic math, units, reaction balance, molecule identity, external-enrichment provenance, study artifacts, unsafe-procedure rejection, plots, tenant isolation, and real FAISS persistence. See `backend/evaluation/README.md` for the evaluation fixtures.

## Current boundary

Job records survive process restarts in SQLite, but the current worker is an in-process bounded thread pool; queued/running work does not resume after a crash. Replace it with a production queue before horizontal scaling. PDFs and derived JSON/FAISS artifacts use local disk, so shared object storage is also required for multiple replicas.

OCR is selectively triggered for low-text, suspicious-glyph, or image-heavy pages. Complex handwritten equations, molecular diagrams, reaction mechanisms, table spans, and semantic figure descriptions remain deliberately unclaimed: their extraction needs a representative benchmark before adopting a specialized model. The formula parser supports conventional element formulas, nested parentheses/brackets, hydrates, states, and caret charges; it is not a chemistry language or mechanism parser. Symbolic and chemistry operations are grammar- and size-bounded, but production deployments should additionally isolate them in a resource-limited worker process.

The Phase 3 safety policy is a narrow, deterministic defense for clearly hazardous procedural
requests. It is tested, but it is not a comprehensive chemical-safety classifier or a substitute
for provider safeguards, abuse monitoring, policy evaluation, and expert review before public
deployment.
