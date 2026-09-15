from __future__ import annotations

import pytest
from rankwise.evaluation import (
    CollectionRetrievalCase,
    RetrievalCase,
    collection_retrieval_metrics,
    retrieval_metrics,
)


def test_retrieval_metrics() -> None:
    result = retrieval_metrics(
        [
            RetrievalCase(ranked_pages=(2, 1), relevant_pages=frozenset({2})),
            RetrievalCase(ranked_pages=(3, 4, 1), relevant_pages=frozenset({1})),
        ],
        k=2,
    )

    assert result["hit_rate@2"] == 0.5
    assert result["recall@2"] == 0.5
    assert result["mrr@2"] == 0.5
    assert result["ndcg@2"] == 0.5


def test_retrieval_metrics_rejects_empty_cases() -> None:
    with pytest.raises(ValueError, match="at least one"):
        retrieval_metrics([], k=5)


def test_collection_metrics_do_not_confuse_same_page_across_documents() -> None:
    result = collection_retrieval_metrics(
        [
            CollectionRetrievalCase(
                ranked_locations=("wrong.pdf#1", "right.pdf#1"),
                relevant_locations=frozenset({"right.pdf#1"}),
            )
        ],
        k=2,
    )
    assert result["hit_rate@2"] == 1.0
    assert result["mrr@2"] == 0.5
    assert 0.6 < result["ndcg@2"] < 0.7
