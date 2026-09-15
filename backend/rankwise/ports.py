"""Replaceable model and storage interfaces."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from .domain import Chunk, DocumentRecord, Evidence, SearchHit


class Embedder(Protocol):
    @property
    def model_id(self) -> str: ...

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def encode_query(self, text: str) -> list[float]: ...


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class Generator(Protocol):
    @property
    def configured(self) -> bool: ...

    def generate(self, question: str, evidence: Sequence[Evidence]) -> str: ...

    def status(self) -> dict[str, Any]: ...


class IndexStore(Protocol):
    def build(self, document_version_id: str, vectors: Sequence[Sequence[float]]) -> None: ...

    def exists(self, document_version_id: str) -> bool: ...

    def search(
        self, document_version_id: str, vector: Sequence[float], k: int
    ) -> list[SearchHit]: ...


class DocumentStore(Protocol):
    def save(
        self,
        record: DocumentRecord,
        chunks: Sequence[Chunk],
        source_path: Path,
    ) -> None: ...

    def activate(self, document_version_id: str) -> None: ...

    def active_version_id(self) -> str | None: ...

    def get_document(self, document_version_id: str) -> DocumentRecord: ...

    def get_chunks(self, document_version_id: str) -> list[Chunk]: ...

    def resolve_evidence(self, document_version_id: str, evidence_id: str) -> Chunk: ...

    def source_path(self, document_version_id: str) -> Path: ...
