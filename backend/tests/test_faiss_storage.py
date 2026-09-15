from __future__ import annotations

from pathlib import Path

import pytest
from rankwise.storage import FaissIndexStore

pytest.importorskip("faiss")


def test_faiss_index_is_versioned_and_handles_k_larger_than_index(tmp_path: Path) -> None:
    store = FaissIndexStore(tmp_path / "data")
    store.build("dv_test", [[1.0, 0.0], [0.0, 1.0]])

    assert store.exists("dv_test")
    assert not store.exists("dv_missing")
    hits = store.search("dv_test", [1.0, 0.0], k=10)

    assert [hit.position for hit in hits] == [0, 1]
    assert hits[0].score == pytest.approx(1.0)
