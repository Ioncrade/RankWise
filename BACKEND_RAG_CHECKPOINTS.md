# RankWise Backend and RAG Improvement Checkpoints

> Scope: backend, retrieval, ML evaluation, and production engineering only. The React source and generated frontend build were not reviewed.
>
> Repository snapshot reviewed: commit `7ca68508199373ff89ae30c3bcaec9b93c4f14fa` (`main`, 2025-04-01).

### Implementation status — 2026-09-13

Phase 0 through the scoped Phase 3 MVP are implemented in the working tree. Phase 3 adds deterministic atom/charge reaction balancing, original-versus-verified reaction annotations, RDKit molecule identifiers/descriptors, opt-in tenant-cached PubChem enrichment, reaction-sheet/flashcard/practice-question artifacts, chemistry safety rules, capability reporting, and chemistry fixture slices. Phase 1's deterministic five-document gate remains at Hit/Recall/MRR/nDCG@1 = 1.0.

The fixture scores prove wiring and regression behavior, not production AI quality. Live Tesseract could not be installed on this host because sudo requires an interactive password, so OCR decisions/provenance and image search use an injected deterministic OCR text page in tests. A deployment still needs Tesseract plus configured language packs and a labeled live-OCR evaluation. Other remaining production gates include a reviewed held-out corpus, live transformer/Groq evaluation, real authentication, a crash-resumable queue, resource-isolated symbolic execution, and concurrency/load tests.

The current suite passes 34 tests at 84.17% statement coverage. Deterministic fixture results must not be presented as production chemistry quality.

### Phase 3 MVP status

- [x] Parse and deterministically balance conventional element formulas, nested groups, hydrates, physical states, and caret charge notation with bounded input and coefficients.
- [x] Preserve the original reaction and render any successful atom/charge balance as a separate `Verified calculation`; failures remain `not_verified`.
- [x] Validate SMILES/InChI and calculate canonical identifiers, formulas, charge, and basic descriptors with RDKit.
- [x] Keep PubChem lookup opt-in and externally labeled with source URL, retrieval timestamp, response-size/timeout limits, and a tenant-keyed cache.
- [x] Generate reaction-sheet, flashcard, and practice-question artifacts through the existing scoped, cited, immutable note pipeline.
- [x] Reject hazardous procedural regeneration prompts and instruct chemistry generation not to invent conditions, catalysts, solvents, yields, hazards, or procedures.
- [x] Add deterministic chemistry, external-provenance, study-artifact, and unsafe-procedure regression fixtures.
- [ ] Evaluate reaction extraction, charges, conditions, chemical names, and unsupported additions on a manually reviewed chemistry corpus.
- [ ] Replace the narrow hazardous-procedure keyword gate with a policy-backed, adversarially evaluated safety layer before public deployment.
- [ ] Add reaction-mechanism and molecule-diagram understanding only if benchmark results justify a specialized multimodal model.

### Phase 2 MVP status

- [x] Select low-text, suspicious-glyph, or image-heavy pages for OCR rather than OCRing every page.
- [x] Persist OCR page numbers, warnings, language/DPI/parser configuration, extraction method, content type, and bounding boxes.
- [x] Extract native tables into Markdown and equation-like spans into separately retrievable evidence.
- [x] Upload standalone PNG/JPEG/WebP/TIFF images, preserve originals, OCR/index their PDF representation, and return image-specific citation labels.
- [x] Render authorized full pages and evidence bounding boxes with DPI, geometry, and megapixel limits.
- [x] Provide constrained symbolic simplify/compare/differentiate/integrate/solve, dimensional unit conversion, and bounded plotting endpoints.
- [x] Feed deterministic equation-parser observations into immutable formula-sheet notes without calling a sourced physical law “proven.”
- [x] Add math, physics, equation, table, visual-citation, and injected-OCR regression fixtures.
- [ ] Run and record live OCR CER/WER plus equation/table/visual-coordinate accuracy on a reviewed scanned fixture set.

## Executive assessment

RankWise is a useful RAG proof of concept, but it is not yet a reliable multi-user RAG service. It demonstrates the main components—PDF text extraction, chunking, dense embeddings, vector search, cross-encoder scoring, query expansion, and LLM generation—but has no quality baseline, citations, document isolation, durable application data model, or production safeguards.

The best improvement strategy is:

1. Restore a runnable and reproducible baseline.
2. Build an evaluation set and record baseline quality/latency.
3. Improve parsing, chunking, retrieval, and grounding one variable at a time.
4. Separate the pipeline into services and make ingestion asynchronous and multi-tenant.
5. Add security, observability, load testing, and deployment controls.

Changing the embedding model first would produce a different system, but not evidence that it is a better one.

## What exists today

```text
POST /upload_pdf
  -> save one temporary PDF
  -> PyMuPDF plain-text extraction
  -> CharacterTextSplitter(separator="\n\n", size=200, overlap=10)
  -> all-MiniLM-L6-v2 embeddings + L2 normalization
  -> overwrite one FAISS IndexFlatIP file and one pickle metadata file

POST /ask
  -> embed query
  -> retrieve 5 dense candidates
  -> rerank those same 5 with ms-marco-MiniLM-L-6-v2
  -> ask an LLM for one follow-up query
  -> repeat retrieval
  -> concatenate both contexts
  -> ask a Groq-hosted LLM for a long answer
```

Useful foundations already present:

- The embedding model is loaded once at process startup.
- Embeddings are normalized and searched with inner product, which implements cosine-style ranking.
- A cross-encoder is used as a second-stage relevance scorer.
- A second retrieval pass can sometimes improve recall.
- Upload and question routes perform some basic input checks.
- Temporary upload files are normally deleted.

## Why it is still a basic RAG implementation

| Area | Current implementation | Why it is limited |
|---|---|---|
| Ingestion | One PDF at a time, synchronous | Large PDFs block a web worker; there is no job state, retry, progress, deduplication, or incremental indexing. |
| Extraction | `page.get_text("text")` only | Scans return no text; reading order, columns, headers, footers, tables, figures, and formulas are not handled. |
| Chunking | Character splitter over a page-less concatenated string | Page/source metadata is lost. It is not token-aware or structure-aware. Long paragraphs are not actually constrained to 200 characters. |
| Embeddings | One hard-coded, small general English model | There is no domain/language requirement, model comparison, batching policy, version record, or re-embedding strategy. |
| Vector storage | One exact, flat FAISS index on local disk | Each upload overwrites the previous document. It cannot isolate users/documents, filter metadata, scale horizontally, or support lifecycle operations. |
| Retrieval | Dense top-5 only | The README calls this “hybrid,” but there is no lexical/BM25 retrieval or fusion. Exact names, IDs, acronyms, and rare terms can be missed. |
| Reranking | Retrieve 5, rerank 5, keep 5 | The reranker cannot improve candidate recall and barely changes context selection. A larger first-stage pool should be reranked to a smaller final set. |
| Multi-hop | One LLM-created follow-up query | This is query expansion, not a controlled multi-hop evidence process. It has no decomposition, stopping rule, evidence tracking, or fallback. |
| Context building | Concatenate two result strings | Duplicate chunks are likely; there is no token budget, diversity selection, neighbor expansion, ordering, or source label. |
| Generation | Free-form “long elaborated answer” | There are no citations, claim/evidence mapping, structured output, context delimiters, calibrated abstention, or answer length control. |
| Conversation | Global list of prior answers | History is returned but is not used for question rewriting. It leaks across users/processes and grows without a bound. |
| Evaluation | None | Retrieval, answer quality, hallucination, abstention, OCR, latency, throughput, and cost cannot be compared. |
| Backend | One module and global state | API, domain logic, storage, configuration, and model clients are tightly coupled and hard to test. |

Artifact inspection reinforces the chunking problem. The committed metadata contains 561 text strings. Although `chunk_size=200`, their character lengths have a median of 1,963, p95 of 2,853, and maximum of 4,910. `CharacterTextSplitter` does not split an individual separator-delimited unit that is already over the target in the way this code assumes.

## Checkpoint 0 — restore a trustworthy baseline (P0)

- [x] Fix `/ask`: it calls undefined `search_rerank_and_answer()` instead of the defined `multi_hop_search_rerank_and_answer()`.
  - Done when: an API test uploads a fixture and `/ask` returns a generated or explicitly stubbed answer without `NameError`.
- [x] Replace the hard-coded `gemma2-9b-it` model ID. Groq lists it as shut down on 2025-10-08; make the generation and query-rewrite model IDs environment/config values.
  - Done when: startup or readiness validates the configured model and a provider-model change requires no code edit.
- [x] Pin direct dependencies and use the correct distribution name `python-dotenv` for `from dotenv import load_dotenv`.
  - Prefer `pyproject.toml` plus a lock file; record the supported Python version.
  - Done when: a clean environment produces the same dependency graph and passes a smoke test.
- [x] Fix paths so data and static files resolve from the application directory, not the caller's current working directory.
  - Done when: the server works when launched from both the repository root and `backend/`.
- [x] Do not require a Groq key merely to import ingestion code or run unit tests. Validate provider settings at the boundary that needs them, or expose degraded readiness clearly.
- [x] Return typed failures with correct status codes. The retrieval function currently converts every exception into a string, which can look like a successful answer.
- [x] Remove `debug=True` from the production entry point and run behind a production WSGI/ASGI server.
- [x] Add `.gitignore`, `.env.example`, backend run commands, and a migration note for index/model changes.
- [ ] Decide whether the committed FAISS and pickle files are fixtures or user-derived data. Remove user data from Git; keep small, explicitly licensed fixtures under `tests/fixtures` if needed.

## Checkpoint 1 — establish evaluation before optimization (P0/P1)

### Build a gold dataset

- [ ] Start with 75–150 manually reviewed questions over representative PDFs. Store JSONL rows with:
  - `question_id`, `document_ids`, `question`, `answerable`, `reference_answer`
  - gold `page_numbers` or stable evidence IDs
  - `question_type`, `difficulty`, `language`, and notes
- [ ] Include explicit slices: ordinary prose, exact identifiers/numbers, tables, two-column layouts, scanned/OCR pages, multi-document questions, genuine multi-hop questions, and unanswerable/adversarial questions.
- [ ] Separate development and held-out test sets. Do not tune prompts, chunk sizes, or thresholds on the test set.
- [ ] Review synthetic questions against source evidence. Synthetic generation can increase coverage, but it must not be its own judge.

### Measure the right layers

| Layer | Minimum metrics |
|---|---|
| Extraction | page success rate; OCR character/word error rate on a labeled sample; table cell/row preservation where tables matter |
| Retrieval | Recall@5/10/20, MRR@10, nDCG@10, precision/context precision, and results broken down by question slice |
| Reranking | Recall of first-stage pool; nDCG/MRR before vs. after reranking; latency added |
| Answer | exact match/F1 where appropriate, semantic correctness, citation precision/recall, faithfulness/groundedness, answer relevance |
| Abstention | precision, recall, and false-answer rate on unanswerable questions |
| Operations | ingestion time/page, p50/p95/p99 query latency, time to first token, requests/sec, error/retry rate, memory, tokens and cost/query |

- [x] Use deterministic retrieval metrics as the primary signal. LLM-as-judge metrics such as Ragas faithfulness/context precision are useful secondary signals, not unquestioned ground truth.
- [ ] Add a human review rubric for correctness, completeness, citation support, and harmful confidence; sample regressions on every release.
- [ ] Save every experiment with code commit, dataset version, parser/chunker config, embedding/reranker/generator IDs and revisions, prompt version, seed, hardware, quality metrics, latency, and cost.
- [ ] Add CI regression gates. Initial targets should be set from the corrected baseline, then ratcheted upward—for example, no statistically meaningful quality regression and no >10% p95 latency regression without an approved tradeoff.

### Experiment ladder

Run the following ablations on the same held-out set so the value of each component is visible:

1. Corrected current system: dense-only MiniLM, no query expansion.
2. Structure-aware/token-aware chunks; all other components fixed.
3. Candidate embedding models; all other components fixed.
4. Sparse BM25 and dense retrieval separately.
5. Hybrid BM25 + dense with Reciprocal Rank Fusion (RRF).
6. Hybrid retrieval of 30–100 candidates, then rerank to the best 5–10.
7. Add deduplication, diversity, neighbor/parent expansion, and token budgeting.
8. Add query expansion only for question classes where it wins.
9. Compare generator models and grounded prompt formats last.

Use a public IR suite such as BEIR for general retriever sanity checks, but use the RankWise document set as the release gate: public benchmark performance does not substitute for the actual PDF/domain distribution.

## Checkpoint 2 — document ingestion and OCR (P1)

- [ ] Preserve page-level metadata from the beginning: `document_id`, `version`, `page`, `block`, bounding box, section path, content type, parser version, and checksum.
- [x] Detect pages that need OCR instead of OCRing everything. Current signals are little extracted text, embedded images with little text, and suspicious replacement-glyph output.
- [ ] Add OCR fallback with PyMuPDF's Tesseract integration, or benchmark another parser/OCR engine if tables/layout dominate.
  - OCR is much slower than native extraction, so cache the OCR result and record language, DPI, engine, version, confidence, and duration.
  - Add language-pack configuration rather than assuming English.
- [ ] Preserve reading order for multi-column pages and remove repeated headers/footers without deleting real content.
- [ ] Treat tables, lists, captions, and section headings as structures. Keep a text representation for retrieval plus enough coordinates/metadata to cite the original page.
- [ ] Define a policy for figures and diagrams: caption-only retrieval first; vision extraction only when the product requirements and benchmark justify its cost.
- [ ] Normalize Unicode, whitespace, hyphenation, and page breaks while retaining raw extracted text for debugging.
- [ ] Replace character-only splitting with a benchmarked strategy:
  - token-aware recursive splitting as a baseline;
  - heading/paragraph-aware boundaries;
  - configurable target and overlap;
  - optional small child chunks for retrieval with larger parent sections for generation.
- [ ] Add ingestion quality checks: empty-document rejection, chunk-size distribution, duplicate ratio, OCR usage, page coverage, and suspicious extraction warnings.
- [x] Make ingestion idempotent with a content checksum. Re-uploading the same document/config should reuse artifacts; changing parser/chunker/embedder versions should create a traceable new index version.

## Checkpoint 3 — embeddings, retrieval, and reranking (P1)

- [ ] Define requirements first: English vs. multilingual, domain, CPU/GPU budget, corpus scale, acceptable latency, maximum sequence length, and model license.
- [ ] Benchmark embedding candidates rather than labeling one “best.” Keep `all-MiniLM-L6-v2` as the cheap baseline and compare at least:
  - a stronger English retrieval model (for example E5 or BGE small/base class);
  - a multilingual model such as BGE-M3 only if multilingual PDFs are in scope;
  - an API embedding model only if privacy, cost, and network latency are acceptable.
- [ ] Use the model's documented query/document prefixes and normalization rules. Persist model name, immutable revision, dimension, distance metric, and preprocessing config with every index.
- [ ] Batch embeddings and expose batch size/device as configuration. Measure memory and throughput; do not download models implicitly in every production replica.
- [x] Implement actual hybrid search: BM25/sparse results plus dense results, fused initially with RRF. This particularly helps names, codes, numbers, and rare terms.
- [x] Retrieve a larger first-stage pool (currently configurable, default 30), rerank it, and keep only the best configured context set. A true token budget remains future work.
- [ ] Benchmark the current cross-encoder against alternatives on the gold set. Calibrate score thresholds; do not assume raw scores from different rerankers are comparable probabilities.
- [x] Handle fewer-than-`top_k` chunks. FAISS can return `-1` slots, and the current list indexing would incorrectly select the final chunk.
- [ ] Deduplicate identical/overlapping chunks and use MMR or another diversity rule when results repeat the same passage.
- [ ] Consider neighboring or parent-section expansion after a relevant child is found, while tracking which exact span caused the match.
- [ ] Add metadata filters for tenant, document, collection, ACL, version, language, and content type before or during retrieval—not after context has leaked.
- [ ] Keep `IndexFlatIP` while the corpus is small and exact search meets the latency SLO. Benchmark HNSW/IVF or a vector database only when corpus size, filtering, durability, or distributed serving requires it.
- [x] Create a stable retriever interface so FAISS can be replaced without rewriting HTTP or generation code.

## Checkpoint 4 — grounded generation and real multi-hop behavior (P1)

- [x] Give every returned chunk a stable evidence ID and page number. Return citations in the API and render answers with page-level references.
- [ ] Use explicit context delimiters and instruct the model that document text is untrusted evidence, not executable instructions. Test indirect prompt injection in uploaded documents.
- [ ] Require a structured output such as `answer`, `citations`, `confidence_reason`, and `insufficient_evidence`; validate it server-side.
- [ ] Replace “generate a long elaborated answer” with a concise, evidence-first prompt. More tokens are not evidence of better quality.
- [ ] Set an evidence threshold and abstain when retrieval support is weak. Validate every citation against the supplied span and reject citations to absent evidence IDs.
- [ ] Deduplicate and order context, enforce an input token budget, reserve output tokens, and log which chunks were actually sent.
- [ ] Make generation temperature and maximum output tokens explicit and version the prompt.
- [ ] Make query expansion conditional. Simple factual questions should not automatically pay for a second LLM call and retrieval pass.
- [ ] If multi-hop is a real goal, implement and evaluate a bounded loop:
  1. Decompose the question into answerable subquestions.
  2. Retrieve cited evidence for each subquestion.
  3. Detect unresolved information and either retrieve again or stop.
  4. Synthesize only from collected evidence.
  5. Enforce maximum hops, latency/token budgets, and duplicate-query detection.
- [ ] Add conversational retrieval only if required: store history per authenticated session, rewrite follow-ups into standalone queries, and summarize/truncate history. Do not pass a global history list between users.
- [ ] Add streaming after correctness so users see a lower perceived latency, while preserving a final validated/cited response.

## Checkpoint 5 — backend architecture and data model (P1/P2)

- [x] Split `app.py` into testable boundaries: API routes, configuration, ingestion, parsing, chunking, embeddings, retrieval, reranking, generation, repositories, and provider clients.
- [x] Use an application factory and dependency injection so unit tests can supply fake embedder, retriever, reranker, storage, and LLM clients.
- [ ] Introduce durable entities:

```text
Tenant/User -> Collection -> Document -> DocumentVersion -> Page/Block -> Chunk
                                                |
                                                +-> IngestionJob
Query -> RetrievalRun -> RetrievedEvidence -> GenerationRun -> Answer/Citations
```

- [x] Generate opaque collection/job/note IDs, require collection/document scope on `/v1` queries, and enforce trusted tenant scope in the catalog before retrieval. Authentication and richer ACL membership remain required for production.
- [x] Store collection/job/note metadata in SQLite and raw PDFs/chunk JSON on local durable storage. Treat the vector index as derived, rebuildable data. Shared object storage remains a scale milestone.
- [x] Replace pickle for new metadata with non-executable JSON and SQLite. Legacy pickle is retained but never loaded pending an explicit deletion/migration decision.
- [x] Make document metadata, raw-PDF, and FAISS publication atomic at the individual artifact level. A multi-artifact transaction/recovery marker remains future hardening.
- [x] Move parsing/embedding into a bounded background executor. Return `202 Accepted` plus job IDs and expose queued/running/succeeded/failed states. Replace the in-process executor with a crash-resumable queue before production.
- [ ] Add per-stage timeouts, bounded retries with jitter for transient 429/5xx errors, and no retries for invalid input. Reuse the provider client rather than constructing it inside every query.
- [ ] Add request schemas and limits: MIME/magic-byte validation, maximum upload bytes/pages, maximum query length, supported encryption policy, and normalized error envelopes.
- [ ] Add authentication, tenant-aware authorization, request rate limits, quotas, retention/deletion APIs, and audit events before supporting multiple users.
- [ ] Bound all in-memory caches/history and never use process globals as durable application state.
- [x] Provide separate liveness and readiness endpoints. Readiness reports generation, OCR, symbolic math, units, plotting, and page-rendering capabilities without making expensive third-party calls.
- [x] Publish an OpenAPI 3.1 contract and use `/v1` API versioning for collections, jobs, notes, and authorized citations.

## Checkpoint 6 — reliability, security, and operations (P2)

- [ ] Add unit tests for extraction decisions, chunk boundaries/metadata, normalization, fusion, reranking, token budgeting, citation validation, and abstention.
- [ ] Add integration tests with tiny native-text, scanned, multi-column, table, malformed, encrypted, and fewer-than-five-chunks PDFs.
- [x] Add end-to-end tests with fake deterministic models; keep a small opt-in live-provider smoke test outside normal CI.
- [ ] Add concurrency tests for simultaneous upload/query and tenant isolation tests that prove cross-document data cannot leak.
- [ ] Fuzz malformed PDFs and enforce CPU, memory, file-size, page-count, and processing-time limits. Consider sandboxing document parsing in a separate worker/container.
- [ ] Add structured logs with request/job/document/run IDs, stage timings, model/config versions, retrieved evidence IDs/scores, token counts, retries, and normalized failures. Do not log raw documents, prompts, or answers by default.
- [ ] Export metrics and traces for parse, OCR, embed, retrieve, rerank, provider, and total latency. Alert on error rate, queue age, p95 latency, quality canary regressions, and spend.
- [ ] Define SLOs and load-test realistic mixtures of upload, OCR, and query traffic. Measure cold starts and model memory per worker.
- [ ] Add Docker/Compose for local reproducibility, a non-root production image, health checks, resource limits, and a real process manager.
- [ ] Scan and pin dependencies, keep secrets outside images/Git, rotate provider keys, and use separate development/staging/production credentials and quotas.
- [ ] Add CI for formatting, linting, type checking, tests, dependency review, container build, and evaluation smoke tests.
- [ ] Define backups and restore drills for metadata/object storage. Document how vector indexes are rebuilt and rolled back.

## Checkpoint 7 — advanced AI/ML work after the baseline (P3)

Only pursue these when the evaluation slices show a specific gap:

- [ ] Train or fine-tune an embedding model with domain query-positive pairs and hard negatives; compare against the untuned baseline on a held-out set.
- [ ] Fine-tune the reranker with cross-encoder hard negatives if ranking, rather than candidate recall, is the bottleneck.
- [ ] Add learned sparse retrieval or late interaction (for example, ColBERT-style retrieval) if BM25+dense cannot meet quality within latency/storage constraints.
- [ ] Add semantic answer caching keyed by tenant, ACL, document/index version, prompt/model version, and normalized query.
- [ ] Add active-learning queues from low-confidence, thumbs-down, and citation-failure examples; require privacy review before retaining user content.
- [ ] Add a small online A/B or canary framework only after offline gates, with guardrails for cost, latency, and unsupported-answer rate.
- [ ] Explore multimodal page understanding only for benchmark slices where OCR/text representations demonstrably fail.

## Recommended implementation order

| Milestone | Deliverable | Exit evidence |
|---|---|---|
| M0: runnable baseline | Fix route/model/config/path/dependencies; minimal tests | Clean install, upload/query smoke test, current metrics recorded |
| M1: evaluation harness | Versioned gold dataset and experiment runner | Reproducible retrieval, answer, abstention, latency, and cost report |
| M2: evidence-preserving ingestion | Page/block metadata, OCR fallback, structure-aware chunks | Native/OCR/layout slices improve without unacceptable latency regression |
| M3: retrieval v2 | BM25+dense RRF, larger candidate pool, tuned reranker, dedup/token budget | Significant held-out Recall/nDCG gain and documented latency tradeoff |
| M4: trustworthy answers | Structured answers, verified citations, calibrated abstention | Citation/faithfulness and unanswerable-question gates pass |
| M5: service architecture | IDs, tenants/ACLs, durable storage, jobs, atomic index versions | Concurrent isolation/E2E tests and restart/rebuild test pass |
| M6: production readiness | Observability, limits, security, container/CI, load tests, SLOs | Staging load/chaos run meets agreed SLO and rollback works |

## High-value portfolio outcomes

To make this stand out as both an AI/ML and backend engineering project, publish artifacts that prove engineering decisions:

- An evaluation report with ablations showing how chunking, embeddings, hybrid retrieval, reranking, OCR, and query expansion affect each question slice.
- A failure analysis with examples of retrieval misses, extraction errors, unsupported answers, and the fixes they motivated.
- An architecture decision record explaining local FAISS vs. a vector database and the measured scale threshold for migration.
- A versioned OpenAPI spec, ingestion job state machine, and tenant/ACL model.
- A load-test and cost report with stage-level p95 latency, throughput, memory, token use, and quality/latency/cost tradeoffs.
- A reproducible demo corpus that includes scanned pages, tables, multi-column text, exact identifiers, multi-hop questions, and questions that must be refused.

## Definition of “better”

The upgraded project should not be declared complete because it has more libraries or a larger model. It is better when it can demonstrate all of the following on a held-out, representative dataset:

- Higher retrieval recall and ranking quality.
- More correct answers with evidence that resolves to the right document and page.
- A lower unsupported-answer rate and reliable abstention when evidence is absent.
- Measured OCR/layout coverage instead of silent document loss.
- Stable p95 latency, bounded cost, and known capacity under concurrent load.
- Isolation between users/documents and safe deletion/re-indexing.
- Reproducible builds, automated tests, observable failures, and a tested rollback path.

## Primary references

- [Groq model deprecations](https://console.groq.com/docs/deprecations) — records the shutdown of `gemma2-9b-it` and its suggested replacement at that time. Active model IDs should still be fetched/validated rather than copied permanently.
- [Groq production-ready checklist](https://console.groq.com/docs/production-readiness/production-ready-checklist) — provider guidance for timeouts, retries, monitoring, load testing, and cost controls.
- [PyMuPDF OCR guidance](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html) — selective page OCR through Tesseract and its performance implications.
- [Sentence Transformers retrieve-and-rerank guidance](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) — two-stage candidate retrieval followed by cross-encoder reranking.
- [BEIR](https://github.com/beir-cellar/beir) — heterogeneous information-retrieval benchmark and standard ranking metrics.
- [Ragas metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/) — optional secondary RAG metrics such as context precision/recall and faithfulness.
- [python-dotenv](https://pypi.org/project/python-dotenv/) — the distribution that provides `from dotenv import load_dotenv`.
