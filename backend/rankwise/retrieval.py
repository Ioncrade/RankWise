"""Dependency-free lexical ranking and rank fusion helpers."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

TOKEN_PATTERN = re.compile(r"[\w.+\-/]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())


def bm25_scores(query: str, documents: Sequence[str]) -> list[float]:
    """Return BM25 scores in corpus order using conventional baseline parameters."""
    if not documents:
        return []
    query_terms = set(tokenize(query))
    tokenized = [tokenize(document) for document in documents]
    average_length = sum(map(len, tokenized)) / len(tokenized) or 1.0
    document_frequency = Counter(
        term for document in tokenized for term in set(document) if term in query_terms
    )
    scores: list[float] = []
    k1 = 1.5
    b = 0.75
    for document in tokenized:
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1
                + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * len(document) / average_length)
            score += inverse_frequency * frequency * (k1 + 1) / denominator
        scores.append(score)
    return scores


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, rank_constant: int = 60
) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            fused[key] = fused.get(key, 0.0) + 1.0 / (rank_constant + rank)
    return fused
