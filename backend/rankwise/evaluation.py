"""Deterministic retrieval metrics used by the baseline evaluator."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    ranked_pages: tuple[int, ...]
    relevant_pages: frozenset[int]


@dataclass(frozen=True, slots=True)
class CollectionRetrievalCase:
    """A cross-document case keyed as a stable filename/page location."""

    ranked_locations: tuple[str, ...]
    relevant_locations: frozenset[str]


def retrieval_metrics(cases: Iterable[RetrievalCase], *, k: int) -> dict[str, float]:
    locations = (
        CollectionRetrievalCase(
            ranked_locations=tuple(str(page) for page in case.ranked_pages),
            relevant_locations=frozenset(str(page) for page in case.relevant_pages),
        )
        for case in cases
    )
    return collection_retrieval_metrics(locations, k=k)


def collection_retrieval_metrics(
    cases: Iterable[CollectionRetrievalCase], *, k: int
) -> dict[str, float]:
    values = list(cases)
    if not values:
        raise ValueError("at least one evaluation case is required")
    if k <= 0:
        raise ValueError("k must be positive")

    hits = 0
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    for case in values:
        if not case.relevant_locations:
            raise ValueError("every evaluation case needs a relevant page")
        ranked = case.ranked_locations[:k]
        relevant_retrieved = set(ranked) & case.relevant_locations
        hits += int(bool(relevant_retrieved))
        recalls.append(len(relevant_retrieved) / len(case.relevant_locations))
        reciprocal_ranks.append(
            next(
                (
                    1.0 / rank
                    for rank, page in enumerate(ranked, start=1)
                    if page in case.relevant_locations
                ),
                0.0,
            )
        )

    count = len(values)
    ndcg_values = []
    for case in values:
        gains = [
            1.0 / math.log2(rank + 1)
            for rank, location in enumerate(case.ranked_locations[:k], start=1)
            if location in case.relevant_locations
        ]
        ideal_count = min(k, len(case.relevant_locations))
        ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
        ndcg_values.append(sum(gains) / ideal)
    return {
        f"hit_rate@{k}": hits / count,
        f"recall@{k}": sum(recalls) / count,
        f"mrr@{k}": sum(reciprocal_ranks) / count,
        f"ndcg@{k}": sum(ndcg_values) / count,
        "case_count": float(count),
    }
