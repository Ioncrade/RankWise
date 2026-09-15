"""Small deterministic adapters used by backend tests."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from rankwise.domain import Evidence, SearchHit
from rankwise.errors import NotFoundError, ProviderError

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))


class HashingEmbedder:
    dimension = 128
    model_id = "test-hashing-v1"

    def _encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:2], "big") % self.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def encode_query(self, text: str) -> list[float]:
        return self._encode(text)


class MemoryIndexStore:
    def __init__(self) -> None:
        self.vectors: dict[str, list[list[float]]] = {}

    def build(self, document_version_id: str, vectors: Sequence[Sequence[float]]) -> None:
        self.vectors[document_version_id] = [list(vector) for vector in vectors]

    def exists(self, document_version_id: str) -> bool:
        return document_version_id in self.vectors

    def search(self, document_version_id: str, vector: Sequence[float], k: int) -> list[SearchHit]:
        if document_version_id not in self.vectors:
            raise NotFoundError("Test index not found")
        scored = [
            SearchHit(
                position=position,
                score=sum(left * right for left, right in zip(item, vector, strict=True)),
            )
            for position, item in enumerate(self.vectors[document_version_id])
        ]
        return sorted(scored, key=lambda item: item.score, reverse=True)[:k]


class LexicalReranker:
    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        query_tokens = _tokens(query)
        return [float(len(query_tokens & _tokens(text))) for text in texts]


class CitingGenerator:
    configured = True

    def generate(self, question: str, evidence: Sequence[Evidence]) -> str:
        del question
        if not evidence:
            return "The evidence is insufficient."
        return f"The document states: {evidence[0].text} [{evidence[0].label}]"


class NoCitationGenerator:
    configured = True

    def generate(self, question: str, evidence: Sequence[Evidence]) -> str:
        del question, evidence
        return "An answer without evidence labels."


class RateLimitedGenerator:
    configured = True
    model = "groq-test"

    def generate(self, question: str, evidence: Sequence[Evidence]) -> str:
        del question, evidence
        raise ProviderError(
            "rate limited",
            provider="groq",
            code="groq_rate_limited",
            retryable=True,
        )

    def status(self):
        return {"configured": True, "model": self.model, "reachable": None}


class LocalCitingGenerator:
    configured = True
    model = "ollama-test"

    def generate(self, question: str, evidence: Sequence[Evidence]) -> str:
        del question
        return f"Local answer: {evidence[0].text} [{evidence[0].label}]"

    def status(self):
        return {"configured": True, "model": self.model, "reachable": True}
