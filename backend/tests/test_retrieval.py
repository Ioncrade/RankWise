from rankwise.retrieval import bm25_scores, reciprocal_rank_fusion, tokenize


def test_bm25_prefers_exact_rare_terms() -> None:
    documents = [
        "force mass acceleration",
        "photosynthesis chlorophyll photon",
        "chemical bonds electrons",
    ]
    scores = bm25_scores("chlorophyll photosynthesis", documents)
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]
    assert bm25_scores("anything", []) == []
    assert tokenize("F=m/a + H2O") == ["f", "m/a", "+", "h2o"]


def test_reciprocal_rank_fusion_rewards_shared_results() -> None:
    fused = reciprocal_rank_fusion((("dense", "shared"), ("sparse", "shared")))
    assert fused["shared"] > fused["dense"]
    assert fused["shared"] > fused["sparse"]
