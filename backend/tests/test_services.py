from __future__ import annotations

from pathlib import Path

from rankwise.parsing import PdfParser
from rankwise.services import IngestionService, QuestionService
from rankwise.storage import LocalDocumentStore

from .fakes import (
    HashingEmbedder,
    LexicalReranker,
    LocalCitingGenerator,
    MemoryIndexStore,
    NoCitationGenerator,
    RateLimitedGenerator,
)


def test_answer_without_valid_labels_is_flagged(tmp_path: Path, science_pdf_bytes: bytes) -> None:
    pdf_path = tmp_path / "science.pdf"
    pdf_path.write_bytes(science_pdf_bytes)
    document_store = LocalDocumentStore(tmp_path / "data")
    index_store = MemoryIndexStore()
    embedder = HashingEmbedder()
    ingestion = IngestionService(
        parser=PdfParser(chunk_size=300, chunk_overlap=30),
        embedder=embedder,
        index_store=index_store,
        document_store=document_store,
    )
    record = ingestion.ingest_pdf(pdf_path, "science.pdf")
    questions = QuestionService(
        embedder=embedder,
        reranker=LexicalReranker(),
        generator=NoCitationGenerator(),
        index_store=index_store,
        document_store=document_store,
        candidate_k=5,
        context_k=2,
    )

    result = questions.ask("What is Newton's second law?", record.document_version_id)
    assert result.citations == ()
    assert result.warnings == ("The generated answer did not contain a valid inline citation.",)


def test_auto_provider_falls_back_without_retrieving_again(
    tmp_path: Path, science_pdf_bytes: bytes
) -> None:
    pdf_path = tmp_path / "science.pdf"
    pdf_path.write_bytes(science_pdf_bytes)
    document_store = LocalDocumentStore(tmp_path / "data")
    index_store = MemoryIndexStore()
    embedder = HashingEmbedder()
    record = IngestionService(
        parser=PdfParser(chunk_size=300, chunk_overlap=30),
        embedder=embedder,
        index_store=index_store,
        document_store=document_store,
    ).ingest_pdf(pdf_path, "science.pdf")
    questions = QuestionService(
        embedder=embedder,
        reranker=LexicalReranker(),
        generator=RateLimitedGenerator(),
        generators={"groq": RateLimitedGenerator(), "ollama": LocalCitingGenerator()},
        default_provider="auto",
        index_store=index_store,
        document_store=document_store,
        candidate_k=5,
        context_k=2,
    )

    result = questions.ask("What is Newton's second law?", record.document_version_id)

    assert result.generation == {
        "requested_provider": "auto",
        "provider_used": "ollama",
        "model": "ollama-test",
        "fallback": True,
        "fallback_reason": "groq_rate_limited",
    }
    assert result.citations
