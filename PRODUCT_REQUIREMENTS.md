# RankWise Science Notes — Product Requirements Document

| Field | Value |
|---|---|
| Status | Proposed |
| Version | 0.1 |
| Date | 2026-09-12 |
| Product type | Multi-document, multimodal RAG study assistant |
| Primary domains | Mathematics, physics, chemistry, biology, and general science |
| Related engineering plan | [`BACKEND_RAG_CHECKPOINTS.md`](BACKEND_RAG_CHECKPOINTS.md) |

## 1. Product summary

RankWise Science Notes lets a student or educator create a collection of PDFs and images, then generate accurate, structured study notes grounded in those sources. It understands ordinary text, scanned pages, equations, tables, graphs, diagrams, and chemical notation. It can search across several documents, show page-level citations, flag conflicts or missing evidence, and call constrained calculation and science tools to verify—not invent—the technical content in its notes.

The product is not merely “chat with a PDF.” Its main output is a reusable study artifact containing explanations, definitions, formulas, derivations, worked examples, reactions, diagrams, misconceptions, flashcards, and practice questions, each traceable to source material.

## 2. Problem statement

Science students commonly study from a combination of textbooks, lecture slides, formula sheets, lab manuals, handwritten or scanned pages, and diagrams. Existing basic RAG systems tend to:

- accept only one document at a time;
- lose equations, page structure, tables, and images during text extraction;
- retrieve semantically similar passages without reliably matching symbols, compound names, identifiers, or numbers;
- produce prose summaries rather than useful subject-specific notes;
- perform arithmetic, algebra, unit conversions, and chemistry reasoning entirely inside the LLM;
- provide no citations or cite a page that does not support the claim;
- merge conflicting documents without telling the learner;
- have no measurable definition of note quality.

RankWise should solve these problems while remaining understandable, testable, and safe to operate as a backend service.

## 3. Product goals

### 3.1 User goals

- Upload several PDFs and standalone images into a named study collection.
- Generate notes for the entire collection, selected documents, page ranges, or a topic.
- Receive notes adapted to mathematics and science rather than a generic summary format.
- See exactly which document, page, figure, table, or equation supports each important statement.
- Trust calculations, symbolic manipulations, units, and balanced chemical equations because deterministic tools checked them.
- Ask follow-up questions and update only the affected section of existing notes.
- Export notes in a portable format without losing equations or citations.

### 3.2 Business/product goals

- Make the project demonstrably stronger in AI/ML quality and backend architecture.
- Produce repeatable evaluation results rather than relying on demo impressions.
- Support incremental indexing and multi-user isolation so the service can grow beyond a local prototype.
- Keep model/provider choices replaceable and control latency and cost per collection and note job.

### 3.3 Non-goals for the first release

- Real-time collaborative document editing.
- General-purpose web research or an unrestricted browsing agent.
- Guaranteed recognition of arbitrary handwritten equations or complex molecular drawings.
- Replacing a computer algebra system, chemistry database, instructor, or laboratory safety review.
- Automatically grading high-stakes examinations.
- Generating novel wet-lab synthesis protocols or unsafe experimental instructions.
- Training custom foundation models before a measured baseline exists.

## 4. Target users and jobs

| Persona | Primary job | Main success condition |
|---|---|---|
| University STEM student | Combine a textbook chapter, slides, and formula sheet into exam notes | Notes cover the examinable concepts, preserve notation, and cite all sources |
| Secondary-school science student | Turn class PDFs and scanned worksheets into understandable revision notes | Explanations match the selected level and difficult terms are defined |
| Educator or teaching assistant | Produce a source-grounded outline, formula sheet, and question bank | Output is editable, attributable, and does not introduce unsupported claims |
| Research learner | Compare an introductory text with papers or technical notes | Differences, assumptions, terminology, and conflicts remain visible |

Core jobs to be done:

1. “Create one set of notes from all the material for this topic.”
2. “Explain this derivation without dropping any assumptions or symbols.”
3. “Summarize these reactions and verify that the equations balance.”
4. “Explain this graph/diagram and connect it to the text around it.”
5. “Compare what these two sources say and show where they disagree.”
6. “Turn these notes into a formula sheet, flashcards, and practice questions.”

## 5. Release assumptions and limits

These are initial product limits, configurable by deployment and subject to load testing:

- Up to 20 PDFs per collection.
- Up to 50 MB and 500 pages per PDF.
- Up to 2,000 pages total per collection.
- Up to 100 standalone PNG, JPEG, or WebP images, 20 MB each.
- Printed English is the first fully evaluated language. Other languages may be accepted only after language-specific OCR, embedding, and evaluation support is declared.
- Notes generation is asynchronous. Question answering may be synchronous or streamed.
- The uploaded collection is the authoritative source. External scientific enrichment is off by default.

When a deployment cannot satisfy a configured limit, the API must reject it before expensive processing and return a machine-readable reason.

## 6. Product principles

1. **Evidence before prose.** The system retrieves and records evidence before drafting a note section.
2. **Source and computation are distinct.** A PDF citation supports what the source says; a tool result shows what the system calculated or verified.
3. **No silent uncertainty.** Low-quality OCR, unreadable formulas, source conflicts, and missing support remain visible.
4. **Structure is data.** Pages, headings, equations, figures, tables, captions, and document versions have stable identities.
5. **Tools are constrained.** The model selects from server-approved, typed tools with budgets; it never receives arbitrary shell or network access.
6. **Quality is measured by subject slice.** A higher average score cannot hide failures on scans, equations, tables, chemistry, or multi-document synthesis.

## 7. Core user journeys

### 7.1 Create and ingest a study collection

1. The user creates a collection with title, subject, education level, language, and optional exam/course context.
2. The user uploads multiple PDFs and/or standalone images in one interaction.
3. The API immediately returns document and ingestion-job IDs.
4. The interface reports each file as queued, extracting, OCRing, indexing, ready, partially ready, or failed.
5. The system displays page counts, detected chapters, OCR warnings, duplicated documents, and unsupported pages.
6. Ready documents become searchable without waiting for unrelated failed documents.

### 7.2 Generate notes

1. The user selects the whole collection, particular documents, page ranges, or a topic.
2. The user selects a note profile: comprehensive notes, concise revision notes, formula/reaction sheet, concept map, worked-example guide, or lab-reading summary.
3. The user chooses education level, desired detail, output language, and whether external enrichment is allowed.
4. RankWise creates a note job, plans sections, retrieves evidence, calls verification tools where necessary, validates citations, and renders the result.
5. The user sees progress by stage and can cancel the job.
6. The completed notes show citations and warnings inline. The user can regenerate or edit one section without recreating everything.

### 7.3 Ask questions across documents

1. The user asks within a collection and may limit scope to chosen sources.
2. RankWise retrieves across allowed text and visual evidence.
3. The answer cites each substantive claim and identifies which document is being used.
4. If sources disagree, the answer presents both positions instead of silently selecting one.
5. If evidence is insufficient, the system says so and offers to broaden document scope or—only with permission—use external enrichment.

## 8. Functional requirements

Priority meanings: P0 is required for the first useful release, P1 follows immediately, and P2 is an enhancement.

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Users can create, rename, list, and delete isolated document collections | P0 |
| FR-002 | A collection accepts multiple PDFs and standalone images with independent status | P0 |
| FR-003 | Ingestion runs asynchronously with progress, cancellation, retry, and idempotency | P0 |
| FR-004 | Native text extraction falls back to selective OCR and records extraction quality | P0 |
| FR-005 | The system preserves page, layout, equation, table, figure, and caption metadata | P0 |
| FR-006 | Users can search/ask over a collection or an explicit document/page subset | P0 |
| FR-007 | Users can generate subject-aware notes with page/region citations | P0 |
| FR-008 | A bounded tool-calling workflow verifies math, units, and chemistry content | P0 |
| FR-009 | Every generated artifact stores source, model, prompt, parser, index, and tool versions | P0 |
| FR-010 | Users can inspect the cited page/region behind a note claim | P0 |
| FR-011 | Users can regenerate one section and retain a version history | P1 |
| FR-012 | The product generates formula sheets, reaction sheets, flashcards, and practice questions | P1 |
| FR-013 | The system detects cross-document agreement, conflict, and terminology differences | P1 |
| FR-014 | Notes export to Markdown and print-ready PDF with equations and citations intact | P1 |
| FR-015 | Users can provide feedback at note-section and citation level | P1 |
| FR-016 | Users can share a read-only collection or note through explicit access control | P2 |

### 8.1 Multi-PDF collection requirements

- Each file receives stable `document_id` and `document_version_id` values. Replacing a PDF creates a version; it does not silently mutate historical notes.
- Scope is explicit on every query or note job: collection, selected documents, and optional page ranges.
- Duplicate upload detection uses a content checksum. The user can reuse, skip, or intentionally add a new copy.
- Retrieval applies tenant and collection access control before searching.
- Results include document title, version, page, region, section path, content type, and score.
- One large document must not dominate a collection summary. Section planning measures source coverage and can allocate evidence quotas per document.
- Cross-document notes deduplicate repeated explanations but retain independent citations.
- When sources conflict, notes contain a “Source differences” block with each claim and citation. The model must not average incompatible constants, definitions, signs, or conventions.
- Adding a document incrementally indexes only the new version. Existing notes become “source update available” rather than changing silently.
- Deleting a document removes its raw file, derived blocks, embeddings, index entries, cached results, and future access while preserving a compliant tombstone/audit record.

### 8.2 PDF and image understanding requirements

The product supports both images embedded in PDFs and separately uploaded images.

- Extract native text first, preserving blocks and coordinates.
- Detect page regions likely to be titles, paragraphs, lists, tables, equations, figures, captions, headers, or footers.
- Run OCR selectively on image-only or low-text regions and cache its result.
- Store the original page image and cropped evidence region so users can inspect it.
- Create searchable representations for captions, OCR text, table cells, detected equation text/LaTeX, and a bounded visual description.
- Associate a figure/table/equation with its caption and nearby explanatory text.
- Preserve confidence and provenance for every transformation: native extraction, OCR, equation recognition, table extraction, or vision description.
- Never convert a low-confidence image interpretation into an unqualified fact. Notes must show “image interpretation uncertain” and cite the visual region.
- A standalone image may be assigned a title, subject, and collection. Its citation format is `Image <name>, region <n>` rather than a fabricated page.
- Support rotation, common page orientations, and configurable OCR languages.
- The first release may show complex molecular structures or handwritten equations as cited images if reliable machine interpretation is unavailable.

### 8.3 Notes-generation requirements

Every note job has a declared scope and template. The default comprehensive science template contains:

1. Scope and source list.
2. Learning objectives inferred from headings and repeated emphasis.
3. Topic outline.
4. Core explanations.
5. Definitions and terminology.
6. Equations/formulas with symbol definitions, units, assumptions, and cited origin.
7. Reactions, mechanisms, or processes where applicable.
8. Important diagrams/tables with explanations.
9. Worked examples found in the sources, clearly separated from system-created practice examples.
10. Common misconceptions, exceptions, or boundary conditions supported by the sources.
11. Formula/reaction quick-reference sheet.
12. Flashcards and practice questions.
13. Source differences, extraction warnings, and unresolved items.

Required behavior:

- Notes are generated section by section from retrieved evidence, not from an entire raw-document dump.
- Each factual paragraph, formula, reaction, table interpretation, and source-derived example has one or more resolvable citations.
- Directly source-derived content and system-generated explanation are visually distinguishable.
- The output uses a typed internal schema before Markdown/PDF rendering.
- The user can request concise, standard, or detailed depth and a declared learner level.
- The system avoids repeated content across sections and maintains consistent symbols and terminology.
- A glossary entry links back to the sections and sources where the term is used.
- A notes version is immutable. Regeneration creates a new version with a recorded change reason.

Proposed internal notes shape:

```json
{
  "title": "Thermodynamics — Revision Notes",
  "scope": {"collection_id": "col_...", "document_version_ids": ["dv_..."]},
  "sections": [
    {
      "heading": "First law of thermodynamics",
      "explanation_markdown": "...",
      "concepts": ["internal energy", "heat", "work"],
      "equations": [
        {
          "latex": "\\Delta U = Q - W",
          "symbols": {"U": "internal energy", "Q": "heat added", "W": "work done by the system"},
          "assumptions": ["sign convention stated in source"],
          "verification_status": "verified",
          "citations": ["ev_123"]
        }
      ],
      "citations": ["ev_123", "ev_456"],
      "warnings": []
    }
  ],
  "unresolved_items": [],
  "provenance": {"pipeline_version": "...", "generated_at": "..."}
}
```

### 8.4 Subject-specific note profiles

#### Mathematics

- Preserve equations as structured LaTeX plus source text/image and never silently rename symbols.
- Extract definitions, theorems, lemmas, assumptions, domains, boundary conditions, and proof/derivation steps.
- Distinguish a derivation reproduced from the source from an explanatory derivation added by RankWise.
- Show variable definitions before using an equation.
- Use symbolic verification for algebraic rearrangement, simplification, differentiation, integration, equation solving, and substitution when supported.
- State when a symbolic tool cannot prove equivalence or when a domain assumption changes the result.
- Generate practice questions at selected difficulty without presenting generated questions as source content.

#### Physics

- Build a quantity table containing symbol, meaning, SI unit, and source convention.
- Verify dimensional consistency and unit conversion for worked calculations.
- Preserve vector/scalar distinction, coordinate system, direction, sign convention, and significant figures.
- Link graphs and free-body/circuit/optics diagrams to the surrounding explanation.
- Record assumptions such as idealization, negligible resistance, constant acceleration, or small-angle approximation.
- Separate physical law, model assumption, measured observation, and calculated result.

#### Chemistry

- Extract compound names, formulas, states of matter, charges, stoichiometric coefficients, conditions, catalysts, yields, and safety statements.
- Preserve subscripts, superscripts, equilibrium arrows, electron movement, and reaction conditions when extraction confidence permits.
- Verify atom and charge balance for recognized reactions. A verified balanced form may be shown as a calculated annotation; the original source equation remains available.
- Use unit-aware calculations for molarity, moles, mass, gas relationships, dilution, percentage yield, and stoichiometry.
- Represent recognized molecules using a canonical structure identifier where possible and retain the original image/notation.
- Distinguish facts found in the PDFs from optional database enrichment such as identifiers or computed descriptors.
- Never invent a catalyst, temperature, solvent, hazard, or procedural step absent from the source or an explicitly cited external reference.
- Put hazard and lab-safety content in a clearly labeled block and preserve the wording/context of the source.

#### Biology and general science

- Extract hierarchical structures, pathways, cycles, taxonomies, experimental variables, and causal relationships.
- Distinguish observation, hypothesis, mechanism, evidence, and conclusion.
- Explain diagrams as ordered processes and preserve labels and directionality.
- Keep statistical claims attached to their population, sample, units, and cited table/figure.

## 9. Tool-calling requirements

Tool calling is used to improve correctness and evidence coverage. It is not permission for autonomous, unbounded action.

### 9.1 Required tool catalog

| Tool | Purpose | Suggested implementation | Grounding rule |
|---|---|---|---|
| `search_evidence` | Hybrid retrieval over allowed collection scope | Dense + BM25 + fusion + reranker | Every result returns a stable evidence ID and ACL-filtered provenance |
| `fetch_evidence` | Fetch exact text/table/equation/figure region and neighbors | Metadata/document repository | May fetch only evidence already authorized for the job |
| `render_page_region` | Inspect a cited visual region at adequate resolution | PyMuPDF page rendering/object storage | Result is an image observation, not automatically a textual fact |
| `ocr_region` | Retry OCR on a selected page/region/language/DPI | PyMuPDF + Tesseract initially | Returns engine/version/confidence and never overwrites raw evidence |
| `extract_table` | Recover table structure and headers | Benchmarked PDF/table parser | Retains page coordinates and emits uncertainty for merged/ambiguous cells |
| `extract_equation` | Convert printed equation region into structured notation | Benchmarked equation OCR/parser | Returns source crop, raw recognition, normalized LaTeX, and confidence |
| `verify_symbolic_math` | Simplify, solve, differentiate, integrate, substitute, or compare expressions | SymPy in a constrained worker | Returns assumptions, exact result, verification status, and failure reason |
| `calculate_with_units` | Arithmetic, conversions, dimensions, significant figures | Pint plus decimal/numeric library | Inputs/outputs include units; dimensional errors are explicit |
| `plot_function` | Render a bounded 2D function/series to aid a sourced explanation | Sandboxed plotting service | No arbitrary code; domain, samples, labels, and formula are recorded |
| `balance_chemical_equation` | Check atom/charge balance and derive coefficients | Deterministic parser + linear algebra | Shows original and verified form; never invents reaction conditions |
| `analyze_molecule` | Validate SMILES/InChI and compute selected descriptors | RDKit | Returns canonical identifier, tool version, and calculation provenance |
| `lookup_chemical_entity` | Optional name/formula/identifier/property lookup | PubChem PUG REST or approved source | External, opt-in, cited, timestamped, cached, and visibly labeled |
| `validate_citations` | Check that cited evidence exists and supports generated claims | Deterministic resolver + entailment check | Blocks publication for missing IDs; flags weak semantic support |

Scientific constants should come from a versioned, reviewed local dataset or an explicitly cited approved authority. They must not be recalled from model memory when precision matters.

### 9.2 Orchestration flow

```text
Note request
  -> scope/ACL validation
  -> section plan
  -> search evidence for each section
  -> fetch exact page regions and neighboring context
  -> call equation/table/image extraction only where needed
  -> call math/unit/chemistry verification only for relevant claims
  -> draft typed note sections
  -> resolve and validate citations
  -> run coverage, conflict, duplication, and unsupported-claim checks
  -> render immutable note version
```

### 9.3 Tool execution policy

- The server, not the model, decides which tools are available for a job and enforces tenant/document scope.
- Tool arguments and results conform to versioned JSON Schemas and are validated before execution and before returning to the model.
- Maximum tool calls, repeated calls, total time, per-tool time, memory, output size, and external cost are bounded.
- Independent read-only calls may run in parallel; dependent math or evidence steps retain ordering.
- The orchestration loop has a maximum iteration count and stops on duplicate calls or no evidence gain.
- There is no arbitrary Python, shell, filesystem, URL-fetch, or general web tool in the notes workflow.
- External network tools use an allowlist, strict timeouts, caching, rate limits, and opt-in user consent.
- Uploaded text is untrusted data. Instructions inside a PDF or image cannot change tool permissions, system policy, document scope, or output schema.
- Tool failures are returned as typed observations. The model must not guess the missing result.
- Every call records tool/version, normalized inputs, output hash, duration, status, and related note section without logging sensitive raw content unnecessarily.
- A computed statement is labeled “Calculated” or “Verified.” It also cites the source formula/inputs when those originated in the uploaded collection.
- Model IDs remain configurable. Provider support for tools and structured output must be capability-checked at startup and in CI.

Current Groq documentation describes JSON-Schema tool definitions and local tool execution. It also documents combinations where tool use and strict structured output are not available together. The implementation should therefore support a two-phase design: perform tool calls, then make a separate schema-constrained synthesis call, followed by application validation.

## 10. Retrieval and evidence requirements

- Store multiple representations per block when appropriate: normalized text, equation text/LaTeX, table text, caption, image description, and sparse terms.
- Search must combine dense semantic retrieval with lexical retrieval for symbols, names, formulas, identifiers, and exact numbers.
- Query analysis classifies subject, task, likely modality, and whether a tool is needed; it must not narrow document scope without recording the decision.
- Retrieve a broad candidate pool and rerank to the evidence budget. The configured values are selected by benchmark, not hard-coded product claims.
- Evidence results have stable IDs and immutable content tied to `document_version_id`.
- Parent/neighbor expansion may add context around a matched equation or paragraph without changing which span caused the match.
- Retrieval across images can use caption/OCR/equation text first and a multimodal representation where evaluation shows value.
- Conflicting sources remain separate evidence items. Their document date/version and terminology must be available during synthesis.
- The system abstains when the evidence score/coverage falls below a calibrated threshold.

## 11. High-level system design

```text
Client
  |
API and authentication
  |--- Collection/Document service ---- Metadata DB
  |--- Object service ----------------- PDFs, images, page crops, exports
  |--- Ingestion jobs ----------------- Parser/OCR/Layout workers
  |                                      |
  |                                      +--- Sparse and vector indexes
  |
  +--- Notes/QA orchestrator
          |--- Evidence retrieval and citation resolver
          |--- Math/unit/chemistry tool workers
          |--- Configurable LLM provider
          +--- Notes/version repository
```

Required logical entities:

- `User`, `Tenant`, `Collection`, `CollectionMembership`
- `Document`, `DocumentVersion`, `StandaloneImage`, `Page`, `ContentBlock`
- `Chunk`, `EmbeddingVersion`, `IndexVersion`, `IngestionJob`
- `Evidence`, `RetrievalRun`, `ToolRun`, `GenerationRun`
- `Note`, `NoteVersion`, `NoteSection`, `Citation`, `UserFeedback`

Raw uploaded files are the source of truth. Parsed blocks and indexes are derived, versioned, and rebuildable.

## 12. Proposed API surface

The exact schema belongs in OpenAPI; this section defines required behavior.

| Method and path | Purpose | Key response behavior |
|---|---|---|
| `POST /v1/collections` | Create collection | Returns collection ID and limits |
| `GET /v1/collections` | List accessible collections | Paginated, tenant-scoped |
| `POST /v1/collections/{id}/documents` | Upload one or more PDFs | Returns document and job IDs; `202 Accepted` |
| `POST /v1/collections/{id}/images` | Upload standalone images | Returns image and job IDs; `202 Accepted` |
| `GET /v1/jobs/{job_id}` | Read progress/failure | Stage, percentage, warnings, retryability |
| `POST /v1/collections/{id}/queries` | Ask a grounded question | Answer, citations, warnings, retrieval run ID |
| `POST /v1/collections/{id}/notes` | Start notes generation | Validated scope/template/profile; returns job ID |
| `GET /v1/notes/{note_id}` | Fetch current note | Typed note plus render links and provenance |
| `POST /v1/notes/{note_id}/sections/{section_id}/regenerate` | Replace one section | Creates a new immutable note version |
| `GET /v1/evidence/{evidence_id}` | Resolve citation | Authorized text/region preview and source location |
| `POST /v1/notes/{note_id}/exports` | Create Markdown/PDF export | Asynchronous export job |
| `POST /v1/feedback` | Record note/citation feedback | Links feedback to immutable run/version IDs |
| `DELETE /v1/documents/{document_id}` | Delete source and derivatives | Idempotent, auditable lifecycle operation |

Every error response includes a stable code, human-readable message, request ID, retryability, and field-level details when relevant.

## 13. Non-functional requirements

### 13.1 Reliability and performance

- API job creation p95 under 1 second, excluding upload transfer time.
- Progress becomes visible within 5 seconds of queue acceptance.
- Grounded question-answer p95 under 12 seconds for a ready collection under the declared reference load; streaming should expose earlier time-to-first-token where supported.
- Initial planning target: a 100-page native-text notes job completes within 5 minutes p95 and an OCR-heavy job within 20 minutes p95 on the declared reference infrastructure. These targets must be revised using measured stage timings.
- Job retries are idempotent and cannot publish duplicate document or note versions.
- Partial document failures do not corrupt an existing searchable index.
- Availability target is 99.5% for the API after the MVP; background processing has a separately measured completion SLO.

### 13.2 Security and privacy

- All collection, evidence, index, cache, and object-storage access is tenant-scoped.
- Files are validated by signature and parser, not extension alone; size/page/time/memory limits protect parsers and workers.
- Potentially malicious PDFs are processed in isolated, least-privileged workers.
- Encryption is required in transit and at rest; secrets are managed outside code and images.
- Uploaded material and generated notes are not used for model training without explicit consent.
- Data retention and deletion behavior is configurable and testable, including vector/index removal.
- Provider data-handling terms are documented per deployment; sensitive collections can be restricted to approved local/private models.
- Prompt-injection and cross-tenant retrieval tests are release gates.

### 13.3 Accessibility and portability

- Equations have LaTeX/source-text representations and readable fallbacks.
- Figure explanations include alt text, while uncertain details are marked.
- Citations remain usable in exported Markdown and PDF.
- Generated notes use semantic headings and do not rely on color alone to express warnings or provenance.

### 13.4 Observability and cost

- Trace ingestion and generation by request, job, collection, document version, note version, and pipeline version.
- Record per-stage duration, queue time, OCR pages, chunks, retrieval scores, tool calls, tokens, retries, and estimated cost.
- Do not log full user documents, page images, prompts, or notes by default.
- Enforce per-user/tenant upload, storage, OCR, model-token, tool-call, and concurrency quotas.
- Alert on queue age, failure rate, p95 latency, provider errors, spend anomalies, and quality-canary regression.

## 14. Quality and evaluation requirements

### 14.1 Evaluation corpus

The held-out evaluation corpus must contain licensed or internally created material covering:

- multiple documents about the same topic;
- duplicated and conflicting sources;
- native and scanned PDFs;
- single- and two-column pages;
- equations, derivations, graphs, scientific diagrams, tables, and captions;
- chemistry formulas, reactions, states, charges, and molecule diagrams;
- standalone page/board/diagram images;
- answerable, unanswerable, exact-number, symbol-heavy, multi-hop, and cross-document questions.

Gold annotations include key concepts expected in notes, evidence page/regions, equations and semantic equivalents, table cells, image labels, answerability, conflicts, and expected tool use.

### 14.2 Initial launch gates

Targets below are proposed product gates and should be validated for feasibility against the corrected baseline:

| Quality dimension | Proposed gate |
|---|---|
| Supported-file ingestion | At least 99% successful on the controlled fixture suite; every partial failure is visible |
| Evidence retrieval | At least 90% Recall@10 overall with no critical subject/modality slice below the agreed floor |
| Citation resolvability | 100% of published citation IDs resolve to an authorized immutable source region |
| Citation correctness | At least 95% of sampled substantive citations support the associated claim |
| Unsupported claims | Fewer than 2% major unsupported factual claims in sampled final notes |
| Key-concept coverage | At least 90% recall against expert-annotated key concepts without exceeding the duplication limit |
| Unanswerable behavior | At most 5% false-answer rate on the held-out unanswerable set |
| Printed equation preservation | At least 95% semantic equivalence on the evaluated equation set |
| Verified chemical equations | 100% atom/charge balance for equations published with `verified` status |
| Unit calculations | 100% dimensional consistency for calculations published with `verified` status |
| Multi-document provenance | 100% of conflict blocks identify all represented source/version IDs |

No note may receive “verified” status merely because an LLM says it is correct. Verification status comes from a deterministic tool result or an explicit human review.

### 14.3 Experiment and regression policy

- Compare parser, OCR, chunking, embedding, sparse retrieval, fusion, reranker, multimodal, model, prompt, and tool-policy changes one controlled variable at a time where practical.
- Report metrics by subject and modality, plus latency and cost. Never promote a change based only on aggregate quality.
- Use deterministic metrics first and human review for final quality. LLM-as-judge metrics are secondary and periodically calibrated against humans.
- Save experiment configuration, code commit, dataset version, immutable model revisions, prompt/tool schemas, seed, and hardware.
- CI runs unit/integration tests and a small evaluation smoke set. A scheduled or release job runs the complete held-out suite.

## 15. MVP acceptance scenarios

1. **Multiple sources:** Given five ready PDFs in one collection, when a user generates topic notes scoped to all five, the result records all source versions, cites every represented document, and does not retrieve from another collection.
2. **Selective scope:** Given a collection with a textbook and answer key, when the user excludes the answer key, neither retrieval evidence nor generated content may come from it.
3. **Scanned page:** Given a supported scanned worksheet with no native text, ingestion applies OCR, marks the page as OCR-derived, makes its content retrievable, and resolves citations to the page image.
4. **Visual evidence:** Given a labeled scientific diagram, generated notes cite the figure region, preserve detected labels, and flag any low-confidence interpretation instead of asserting it as fact.
5. **Mathematics verification:** Given a sourced equation and valid domain assumptions, when the note contains an algebraic rearrangement, the symbolic tool result and assumptions are recorded; a failed verification cannot be published as verified.
6. **Physics units:** Given a worked calculation with incompatible units, the units tool returns a dimensional error and the final note either corrects the step with an explicit calculated annotation or flags the source conflict.
7. **Chemistry balance:** Given an unbalanced but parseable source reaction, the note preserves the original cited reaction and may add a separately labeled, atom/charge-verified balanced form. It must not add reaction conditions.
8. **Conflicting documents:** Given two sources using opposite sign conventions, notes identify both conventions with citations and do not merge the equations into one unsupported statement.
9. **Insufficient evidence:** Given a question absent from the selected sources, the answer abstains. External lookup occurs only after explicit permission and its result is labeled external.
10. **Tool failure:** Given an OCR, symbolic, chemistry, or provider timeout, the job remains retryable, publishes no false `verified` label, and reports which sections are incomplete.
11. **Incremental update:** Given an existing note and a newly added PDF, the original note version remains unchanged and the user can generate a new version showing the added source and affected sections.
12. **Deletion:** Given an authorized document deletion, its evidence IDs become inaccessible, derived index entries are removed, and historical notes clearly show that a cited source is no longer available rather than leaking its contents.

## 16. Product success metrics

Primary outcome metrics:

- Percentage of ready collections that produce a completed note.
- Percentage of generated notes exported, revisited, or used to generate study material.
- Section-level helpful rate and citation-correctness rate.
- Median number of user edits/regenerations required before export.
- Held-out key-concept coverage, faithfulness, and abstention performance.

Guardrail metrics:

- Unsupported major claim and invalid citation rates.
- Cross-tenant evidence incidents, with a target of zero.
- OCR/extraction partial-failure rate.
- p95 ingestion and query latency, queue age, provider/tool failures, and retry rate.
- Cost per ready page, question, and generated note.
- Tool calls per note and percentage of calls that contribute to the final artifact.

## 17. Rollout plan

### Phase 0 — repair and instrument the current backend

- Fix the broken query route and retired model configuration.
- Establish pinned dependencies, tests, service boundaries, and an evaluation baseline.
- Introduce stable document/page/chunk/evidence identities and citation resolution.

Exit: one native-text PDF can be ingested and queried reproducibly with correct citations.

### Phase 1 — multi-PDF grounded notes MVP

- Collections, multi-file async ingestion, versioned storage, hybrid retrieval, note jobs, note schema, citations, Markdown export, and section regeneration.
- Comprehensive and concise general-science templates.

Exit: users can generate cited notes from at least five PDFs; tenant isolation and held-out quality gates pass.

### Phase 2 — scans, images, mathematics, and physics

- Selective OCR, page-region viewer, equation/table extraction, symbolic math, units, plots, formula-sheet template, and math/physics evaluation slices.

Exit: OCR, equation, unit, and visual citation gates pass on the fixture suite.

### Phase 3 — chemistry and study artifacts

- Reaction extraction/balancing, molecule analysis, optional chemical entity lookup, reaction sheets, flashcards, and practice questions.

Exit: verified-reaction/unit gates pass, external facts are visibly distinguished, and unsafe-procedure tests pass.

### Phase 4 — scale and product refinement

- Load testing, quotas, cost controls, notes/search caching, controlled sharing, feedback-driven evaluation, canary releases, and index scaling based on measured need.

Exit: staging meets service SLOs and quality gates at the target concurrency with a tested rollback.

## 18. Risks and mitigations

| Risk | Mitigation |
|---|---|
| OCR corrupts formulas or chemical subscripts | Preserve page crop/raw text, store confidence, verify where possible, and visibly flag uncertainty |
| Long collections exceed context/cost limits | Hierarchical section planning, evidence budgets, per-document coverage, incremental cached summaries, and async jobs |
| One source dominates or conflicts disappear | Source coverage accounting and mandatory conflict blocks |
| LLM invents a derivation or reaction condition | Source/computation labels, typed outputs, deterministic verification, and unsupported-claim checks |
| Tool calls create latency or loop indefinitely | Subject-aware routing, parallel independent calls, strict call/time/cost budgets, caching, and max iterations |
| PDF prompt injection requests tools or data | Treat documents as untrusted evidence; server-side tool allowlist and ACL enforcement |
| External chemistry lookup contaminates source-grounded notes | Default off, explicit consent, separate enrichment sections, authoritative citations, timestamps, and cache provenance |
| Model/provider removal breaks production | Capability registry, configuration-based IDs, startup validation, evaluation-based migration, and provider abstraction |
| “Verified” label creates false confidence | Reserve it for deterministic checks with recorded inputs/assumptions; make verification scope explicit |

## 19. Open product decisions

These decisions need user research or benchmarks before final specification:

- Is the first target secondary school, undergraduate, or postgraduate material?
- Which languages and handwritten-content quality are required at launch?
- Should users be able to choose which document wins when sources conflict, or only see comparisons?
- Which note templates matter most: examination revision, lecture companion, formula sheet, lab preparation, or research comparison?
- Is cloud-provider processing acceptable for all users, or is a private/local pipeline required?
- What are the retention defaults and storage/compute budget per user?
- Is external scientific enrichment desirable, and which authorities are approved?
- Are chemistry structure recognition and mechanism diagrams required for MVP or acceptable as cited visual regions?
- Which exports are essential beyond Markdown and PDF, such as Anki, LaTeX, or LMS formats?

## 20. Reference implementations and constraints

- [Groq tool-use overview](https://console.groq.com/docs/tool-use/overview) — JSON-Schema tool definitions and application-managed local tool execution.
- [Groq structured outputs](https://console.groq.com/docs/structured-outputs) — schema-constrained responses and current compatibility constraints with tool use/streaming.
- [PyMuPDF OCR guidance](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html) — selective Tesseract-backed page/region OCR.
- [PyMuPDF image guidance](https://pymupdf.readthedocs.io/en/latest/recipes-images.html) — page rendering and image extraction options.
- [SymPy solving guidance](https://docs.sympy.org/latest/guides/solving/solve-equation-algebraically.html) — symbolic solving with explicit domains and assumptions.
- [Pint documentation](https://pint.readthedocs.io/en/stable/) — quantity, unit conversion, and dimensional analysis support.
- [RDKit documentation](https://www.rdkit.org/docs/GettingStartedInPython.html) — molecular representations and computed descriptors.
- [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest) — optional external chemical information lookup.
