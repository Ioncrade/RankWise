from __future__ import annotations

from rankwise.domain import Evidence
from rankwise.providers import OllamaGenerator


def _evidence() -> Evidence:
    return Evidence(
        label="E1",
        evidence_id="ev_1",
        document_id="doc_1",
        document_version_id="dv_1",
        page_id="page_1",
        page_number=2,
        text="Net force equals mass times acceleration.",
        retrieval_score=1.0,
        reranker_score=1.0,
    )


def test_ollama_generation_receives_canonical_evidence(monkeypatch) -> None:
    provider = OllamaGenerator(
        base_url="http://127.0.0.1:11434",
        model="local-test",
    )
    calls = []

    def fake_request(path, payload=None, timeout_seconds=None):
        calls.append((path, payload, timeout_seconds))
        return {"message": {"content": "Force follows the evidence [E1]."}}

    monkeypatch.setattr(provider, "_request", fake_request)

    answer = provider.generate("What is force?", (_evidence(),))

    assert answer == "Force follows the evidence [E1]."
    assert calls[0][0] == "/chat"
    assert calls[0][1]["model"] == "local-test"
    assert calls[0][1]["stream"] is False
    assert "[E1]" in calls[0][1]["messages"][1]["content"]
    assert "Net force equals mass" in calls[0][1]["messages"][1]["content"]
