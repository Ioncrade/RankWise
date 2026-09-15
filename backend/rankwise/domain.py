"""Serializable domain records for documents, chunks, and evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    document_id: str
    document_version_id: str
    filename: str
    sha256: str
    page_count: int
    chunk_count: int
    created_at: str
    parser_version: str
    embedding_model: str
    ocr_pages: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()
    content_counts: dict[str, int] = field(default_factory=dict)
    source_type: str = "pdf"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DocumentRecord:
        normalized = dict(value)
        normalized["ocr_pages"] = tuple(normalized.get("ocr_pages", ()))
        normalized["warnings"] = tuple(normalized.get("warnings", ()))
        return cls(**normalized)


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    evidence_id: str
    document_id: str
    document_version_id: str
    page_id: str
    page_number: int
    char_start: int
    char_end: int
    text: str
    content_type: str = "text"
    extraction_method: str = "native"
    bbox: tuple[float, float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Chunk:
        normalized = dict(value)
        if normalized.get("bbox") is not None:
            normalized["bbox"] = tuple(normalized["bbox"])
        return cls(**normalized)


@dataclass(frozen=True, slots=True)
class Evidence:
    label: str
    evidence_id: str
    document_id: str
    document_version_id: str
    page_id: str
    page_number: int
    text: str
    retrieval_score: float
    reranker_score: float
    content_type: str = "text"
    extraction_method: str = "native"
    bbox: tuple[float, float, float, float] | None = None
    document_filename: str | None = None
    source_type: str = "pdf"

    def public_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "evidence_id": self.evidence_id,
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "page_id": self.page_id,
            "page_number": self.page_number,
            "text": self.text,
            "retrieval_score": self.retrieval_score,
            "reranker_score": self.reranker_score,
            "content_type": self.content_type,
            "extraction_method": self.extraction_method,
            "bbox": self.bbox,
            "document_filename": self.document_filename,
            "source_type": self.source_type,
            "citation_display": (
                f"Image {self.document_filename or self.document_id}, region 1"
                if self.source_type == "image"
                else f"{self.document_filename or self.document_id}, page {self.page_number}"
            ),
            "url": (
                f"/v1/evidence/{self.evidence_id}?document_version_id={self.document_version_id}"
            ),
            "render_url": (
                f"/v1/evidence/{self.evidence_id}/render"
                f"?document_version_id={self.document_version_id}"
            ),
        }


@dataclass(frozen=True, slots=True)
class SearchHit:
    position: int
    score: float


@dataclass(frozen=True, slots=True)
class AnswerResult:
    answer: str
    evidence: tuple[Evidence, ...]
    citations: tuple[Evidence, ...]
    warnings: tuple[str, ...]
    generation: dict[str, Any] = field(default_factory=dict)
