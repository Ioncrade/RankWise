"""Application services for ingestion, retrieval, and grounded answering."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from .domain import AnswerResult, Chunk, DocumentRecord, Evidence
from .errors import ConfigurationError, NotFoundError, ProviderError, ValidationError
from .parsing import PdfParser
from .ports import DocumentStore, Embedder, Generator, IndexStore, Reranker
from .retrieval import bm25_scores, reciprocal_rank_fusion


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IngestionService:
    def __init__(
        self,
        *,
        parser: PdfParser,
        embedder: Embedder,
        index_store: IndexStore,
        document_store: DocumentStore,
    ) -> None:
        self.parser = parser
        self.embedder = embedder
        self.index_store = index_store
        self.document_store = document_store

    def ingest_pdf(
        self,
        pdf_path: Path,
        filename: str,
        *,
        activate: bool = True,
        source_type: str = "pdf",
    ) -> DocumentRecord:
        digest = _file_sha256(pdf_path)
        document_id = f"doc_{digest[:16]}"
        version_input = f"{digest}|{self.parser.version}|{self.embedder.model_id}|{source_type}"
        version_digest = hashlib.sha256(version_input.encode("utf-8")).hexdigest()
        document_version_id = f"dv_{version_digest[:24]}"
        try:
            existing = self.document_store.get_document(document_version_id)
        except NotFoundError:
            existing = None
        if existing is not None and self.index_store.exists(document_version_id):
            if activate:
                self.document_store.activate(document_version_id)
            return existing
        parsed = self.parser.parse(
            pdf_path,
            document_id=document_id,
            document_version_id=document_version_id,
        )
        vectors = self.embedder.encode_documents([chunk.text for chunk in parsed.chunks])
        if len(vectors) != len(parsed.chunks):
            raise ValidationError("Embedding count does not match chunk count")

        record = DocumentRecord(
            document_id=document_id,
            document_version_id=document_version_id,
            filename=filename,
            sha256=digest,
            page_count=len(parsed.pages),
            chunk_count=len(parsed.chunks),
            created_at=datetime.now(UTC).isoformat(),
            parser_version=self.parser.version,
            embedding_model=self.embedder.model_id,
            ocr_pages=parsed.ocr_pages,
            warnings=parsed.warnings,
            content_counts=parsed.content_counts or {},
            source_type=source_type,
        )
        self.document_store.save(record, parsed.chunks, pdf_path)
        self.index_store.build(document_version_id, vectors)
        if activate:
            self.document_store.activate(document_version_id)
        return record


class QuestionService:
    _citation_pattern = re.compile(r"\[(E\d+)\]")

    def __init__(
        self,
        *,
        embedder: Embedder,
        reranker: Reranker,
        generator: Generator,
        generators: dict[str, Generator] | None = None,
        default_provider: str = "groq",
        index_store: IndexStore,
        document_store: DocumentStore,
        candidate_k: int,
        context_k: int,
    ) -> None:
        self.embedder = embedder
        self.reranker = reranker
        self.generator = generator
        self.generators = dict(generators or {"groq": generator})
        self.generators.setdefault("groq", generator)
        self.default_provider = default_provider
        self.index_store = index_store
        self.document_store = document_store
        self.candidate_k = candidate_k
        self.context_k = context_k

    def _version_id(self, requested: str | None) -> str:
        version_id = requested or self.document_store.active_version_id()
        if not version_id:
            raise NotFoundError("Upload a PDF before asking a question", code="no_document")
        return version_id

    def retrieve(self, query: str, document_version_id: str | None = None) -> tuple[Evidence, ...]:
        version_id = self._version_id(document_version_id)
        return self.retrieve_versions(query, [version_id])

    def retrieve_versions(
        self, query: str, document_version_ids: list[str] | tuple[str, ...]
    ) -> tuple[Evidence, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValidationError("Query must be a non-empty string", code="invalid_query")
        version_ids = tuple(dict.fromkeys(document_version_ids))
        if not version_ids:
            raise NotFoundError("The collection has no ready documents", code="empty_collection")

        chunks_by_key: dict[str, Chunk] = {}
        filenames: dict[str, str] = {}
        source_types: dict[str, str] = {}
        dense_scores: dict[str, float] = {}
        dense_ranking: list[str] = []
        best_dense_by_version: list[str] = []
        query_vector = self.embedder.encode_query(normalized_query)
        for version_id in version_ids:
            chunks = self.document_store.get_chunks(version_id)
            document = self.document_store.get_document(version_id)
            filenames[version_id] = document.filename
            source_types[version_id] = document.source_type
            for chunk in chunks:
                chunks_by_key[chunk.evidence_id] = chunk
            hits = self.index_store.search(version_id, query_vector, self.candidate_k)
            first_valid_key: str | None = None
            for hit in hits:
                if 0 <= hit.position < len(chunks):
                    key = chunks[hit.position].evidence_id
                    first_valid_key = first_valid_key or key
                    dense_scores[key] = hit.score
                    dense_ranking.append(key)
            if first_valid_key is not None:
                best_dense_by_version.append(first_valid_key)
        dense_ranking.sort(key=lambda key: dense_scores[key], reverse=True)

        all_chunks = list(chunks_by_key.values())
        sparse_values = bm25_scores(normalized_query, [chunk.text for chunk in all_chunks])
        sparse_ranking = [
            chunk.evidence_id
            for chunk, score in sorted(
                zip(all_chunks, sparse_values, strict=True),
                key=lambda item: item[1],
                reverse=True,
            )
            if score > 0
        ]
        fused = reciprocal_rank_fusion((dense_ranking, sparse_ranking))
        fused_ranking = sorted(fused, key=fused.__getitem__, reverse=True)
        candidate_keys = list(dict.fromkeys([*best_dense_by_version, *fused_ranking]))[
            : self.candidate_k
        ]
        candidate_chunks = [chunks_by_key[key] for key in candidate_keys]
        reranker_scores = self.reranker.score(
            normalized_query, [chunk.text for chunk in candidate_chunks]
        )
        if len(reranker_scores) != len(candidate_chunks):
            raise ValidationError("Reranker score count does not match candidate count")

        ranked_candidates = sorted(
            zip(candidate_chunks, reranker_scores, strict=True),
            key=lambda value: value[1],
            reverse=True,
        )
        ranked: list[tuple[Chunk, float]] = []
        seen_versions: set[str] = set()
        if ranked_candidates:
            ranked.append(ranked_candidates[0])
            seen_versions.add(ranked_candidates[0][0].document_version_id)
        for candidate in ranked_candidates[1:]:
            if len(ranked) >= self.context_k:
                break
            if candidate[0].document_version_id not in seen_versions:
                ranked.append(candidate)
                seen_versions.add(candidate[0].document_version_id)
        for candidate in ranked_candidates[1:]:
            if len(ranked) >= self.context_k:
                break
            if candidate not in ranked:
                ranked.append(candidate)
        return tuple(
            Evidence(
                label=f"E{index}",
                evidence_id=chunk.evidence_id,
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                page_id=chunk.page_id,
                page_number=chunk.page_number,
                text=chunk.text,
                retrieval_score=fused[chunk.evidence_id],
                reranker_score=float(reranker_score),
                content_type=chunk.content_type,
                extraction_method=chunk.extraction_method,
                bbox=chunk.bbox,
                document_filename=filenames[chunk.document_version_id],
                source_type=source_types[chunk.document_version_id],
            )
            for index, (chunk, reranker_score) in enumerate(ranked, start=1)
        )

    def ask(
        self,
        query: str,
        document_version_id: str | None = None,
        generation_provider: str | None = None,
    ) -> AnswerResult:
        evidence = self.retrieve(query, document_version_id)
        return self.answer_from_evidence(query, evidence, generation_provider)

    def ask_versions(
        self,
        query: str,
        document_version_ids: list[str] | tuple[str, ...],
        generation_provider: str | None = None,
    ) -> AnswerResult:
        return self.answer_from_evidence(
            query, self.retrieve_versions(query, document_version_ids), generation_provider
        )

    def answer_from_evidence(
        self,
        query: str,
        evidence: tuple[Evidence, ...],
        generation_provider: str | None = None,
    ) -> AnswerResult:
        requested_provider = (generation_provider or self.default_provider).strip().casefold()
        if requested_provider not in {"auto", "groq", "ollama"}:
            raise ValidationError(
                "generation_provider must be auto, groq, or ollama",
                code="invalid_generation_provider",
            )
        if not evidence:
            return AnswerResult(
                answer="I couldn't find relevant evidence in the document.",
                evidence=(),
                citations=(),
                warnings=("No evidence passed retrieval.",),
                generation={"requested_provider": requested_provider},
            )
        provider_order = (
            ["groq", "ollama"] if requested_provider == "auto" else [requested_provider]
        )
        fallback_reason: str | None = None
        answer: str | None = None
        provider_used: str | None = None
        provider_model: str | None = None
        last_error: Exception | None = None
        for provider_name in provider_order:
            provider = self.generators.get(provider_name)
            if provider is None or not getattr(provider, "configured", False):
                last_error = ConfigurationError(
                    f"The {provider_name} generation provider is not configured",
                    code=f"{provider_name}_not_configured",
                )
                if requested_provider == "auto":
                    fallback_reason = fallback_reason or f"{provider_name}_not_configured"
                    continue
                raise last_error
            try:
                answer = provider.generate(query.strip(), evidence)
                provider_used = provider_name
                provider_model = getattr(provider, "model", None)
                break
            except ProviderError as exc:
                last_error = exc
                if (
                    requested_provider == "auto"
                    and exc.retryable
                    and provider_name != provider_order[-1]
                ):
                    fallback_reason = exc.code
                    continue
                raise
        if answer is None or provider_used is None:
            if last_error is not None:
                raise last_error
            raise ConfigurationError("No generation provider is configured")
        requested_labels = set(self._citation_pattern.findall(answer))
        citations = tuple(item for item in evidence if item.label in requested_labels)
        warnings: tuple[str, ...] = ()
        if not citations:
            warnings = ("The generated answer did not contain a valid inline citation.",)
        generation = {
            "requested_provider": requested_provider,
            "provider_used": provider_used,
            "model": provider_model,
            "fallback": bool(fallback_reason),
        }
        if fallback_reason:
            generation["fallback_reason"] = fallback_reason
        return AnswerResult(
            answer=answer,
            evidence=evidence,
            citations=citations,
            warnings=warnings,
            generation=generation,
        )

    def provider_status(self) -> dict[str, dict[str, object]]:
        statuses: dict[str, dict[str, object]] = {}
        for name, provider in self.generators.items():
            status_method = getattr(provider, "status", None)
            status = status_method() if callable(status_method) else {}
            statuses[name] = {
                "configured": bool(getattr(provider, "configured", False)),
                "model": getattr(provider, "model", None),
                **status,
            }
        return statuses

    def resolve_evidence(self, document_version_id: str, evidence_id: str):
        return self.document_store.resolve_evidence(document_version_id, evidence_id)
