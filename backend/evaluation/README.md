# Retrieval evaluation harnesses

This small evaluator proves that RankWise can record deterministic page-level retrieval metrics. The included three-question dataset is a smoke fixture, not a product-quality benchmark.

`phase0_smoke_baseline.json` records the deterministic adapter result used while building Phase 0. Its perfect score is expected for this tiny fixture and must not be reported as product quality. The meaningful next baseline uses the configured transformer models and the reviewed held-out corpus described in the checkpoints document.

From the repository root:

```bash
uv sync --extra ml
uv run python backend/evaluation/create_sample_pdf.py /tmp/rankwise-science.pdf
uv run flask --app backend/app.py run
```

Upload the generated PDF in another terminal and copy the returned `document_version_id`:

```bash
curl -F file=@/tmp/rankwise-science.pdf http://127.0.0.1:5000/upload_pdf
uv run python backend/evaluation/evaluate_retrieval.py \
  backend/evaluation/sample_questions.jsonl dv_REPLACE_ME -k 5
```

The evaluator calls `/retrieve`, compares ranked page numbers with the gold pages, and prints hit rate, recall, and mean reciprocal rank. A real baseline must replace this smoke fixture with the held-out, reviewed dataset specified in `BACKEND_RAG_CHECKPOINTS.md`.

## Phase 1 collection evaluator

`evaluate_collection.py` calls the tenant-scoped collection query endpoint and ranks stable `filename#page` locations, so page 1 in two different PDFs is never treated as the same result. It reports hit rate, recall, MRR, and nDCG.

```bash
uv run python backend/evaluation/evaluate_collection.py \
  backend/evaluation/phase1_collection_questions.jsonl col_REPLACE_ME \
  --tenant-id local-demo -k 5
```

`phase1_fixture_gate.json` records the deterministic five-PDF integration result exercised by the test suite. Its perfect score is a wiring regression gate, not a production-quality claim. The reviewed 75–150 question RankWise corpus and external BEIR sanity check remain roadmap work.

## Phase 2 math, physics, and visual fixtures

`phase2_math_physics_cases.jsonl` defines deterministic symbolic-equivalence, calculus, unit-conversion, and bounded-plot slices. The regular test suite exercises those cases along with native equation/table extraction, page and evidence-region rendering, formula-sheet tool observations, and standalone-image storage/search.

`phase2_fixture_gate.json` records which integration gates pass and explicitly records that live Tesseract OCR could not run in this development host because system package installation requires an interactive sudo password. OCR routing and provenance are tested with an injected deterministic text page; this must not be reported as OCR accuracy. A release-quality evaluation still needs scanned math/physics pages with labeled OCR text, equation regions, table cells, and visual citation coordinates.

## Phase 3 chemistry and study-artifact fixtures

`phase3_chemistry_cases.jsonl` defines deterministic reaction balancing, grouped-formula,
molecule-identity, external-consent, and unsafe-procedure slices. The test suite also exercises
reaction-sheet generation with the original source reaction kept beside a separately labeled
verified calculation, plus flashcard and practice-question artifact creation.

`phase3_fixture_gate.json` records the local regression results. PubChem behavior is tested with
an injected response so tests never perform an external lookup or imply live-data correctness.
This remains a wiring gate, not a chemistry extraction or educational-quality benchmark. A
release gate still needs a reviewed chemistry corpus with reaction spans, states, charges,
conditions, balance labels, structure identifiers, and unsupported-condition annotations.

## End-to-end RAGAS benchmark

`ragas_cases.jsonl` is an eight-question smoke set spanning physics, mathematics, chemistry, and
biology. The evaluator gets answers and retrieved contexts exclusively from the running RankWise
API, then computes RAGAS scores:
`context_precision`, `context_recall`, `faithfulness`, `answer_relevancy`, and `answer_correctness`.

Validate the manifest without model calls:

```bash
uv sync --extra ml --extra evaluation
uv run python backend/evaluation/evaluate_ragas.py \
  backend/evaluation/ragas_cases.jsonl col_REPLACE_ME \
  --tenant-id local-demo --dry-run
```

Run against a live collection and save the complete per-case report:

```bash
uv run python backend/evaluation/evaluate_ragas.py \
  backend/evaluation/ragas_cases.jsonl col_REPLACE_ME \
  --tenant-id local-demo --provider auto \
  --output backend/evaluation/ragas_results.json
```

Use `--provider groq` or `--provider ollama` for a direct model comparison. The eight-case set is
a smoke benchmark; use a reviewed 75–150 question held-out set and fixed evaluator model before
setting release thresholds.

For a fully local RAGAS judge, Ollama exposes an OpenAI-compatible endpoint. Set the evaluator
variables separately from RankWise's generation settings:

```bash
export RAGAS_API_KEY=ollama
export RAGAS_BASE_URL=http://127.0.0.1:11434/v1
export RAGAS_MODEL=<small-installed-judge-model>
export RAGAS_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Use a smaller judge model (for example a 3B–8B model) for practical local runtimes; a 27B model
can take several minutes per structured metric call. The evaluator runs sequentially with bounded
retries to avoid overloading Ollama.
