#!/usr/bin/env python3
"""Run an end-to-end RAGAS benchmark against a running RankWise collection."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def load_cases(path: Path) -> list[dict[str, object]]:
    cases = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not cases:
        raise ValueError("benchmark dataset is empty")
    required = {"case_id", "question", "ground_truth", "reference_contexts"}
    for case in cases:
        missing = required - case.keys()
        if missing:
            raise ValueError(f"{case.get('case_id', '<unknown>')} missing: {sorted(missing)}")
    return cases


def query_collection(
    base_url: str, collection_id: str, tenant_id: str, question: str, provider: str
) -> dict[str, object]:
    body = json.dumps({"query": question, "generation_provider": provider}).encode()
    api_request = request.Request(
        f"{base_url.rstrip('/')}/v1/collections/{collection_id}/queries",
        data=body,
        headers={"Content-Type": "application/json", "X-Tenant-ID": tenant_id},
        method="POST",
    )
    with request.urlopen(api_request, timeout=180) as response:  # noqa: S310
        return json.load(response)


def build_rows(
    cases: list[dict[str, object]], responses: list[dict[str, object]]
) -> list[dict[str, object]]:
    rows = []
    for case, payload in zip(cases, responses, strict=True):
        evidence = payload.get("retrieved_evidence", [])
        rows.append(
            {
                "case_id": case["case_id"],
                "user_input": case["question"],
                "response": payload.get("answer", ""),
                "retrieved_contexts": [item.get("text", "") for item in evidence],
                "reference": case["ground_truth"],
                "reference_contexts": case["reference_contexts"],
                "generation": payload.get("generation", {}),
                "retrieved_evidence": evidence,
            }
        )
    return rows


def run_ragas(rows: list[dict[str, object]]) -> dict[str, float]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.embeddings import HuggingFaceEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics import (
            answer_correctness,
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from ragas.run_config import RunConfig
    except ImportError as exc:
        raise RuntimeError(
            "Install the evaluation extra first: uv sync --extra evaluation"
        ) from exc
    api_key = os.getenv("RAGAS_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set RAGAS_API_KEY (or OPENAI_API_KEY). For Ollama, use RAGAS_API_KEY=ollama."
        )
    client_kwargs: dict[str, str] = {"api_key": api_key}
    if base_url := os.getenv("RAGAS_BASE_URL"):
        client_kwargs["base_url"] = base_url
    from openai import OpenAI

    evaluator_client = OpenAI(**client_kwargs)
    evaluator_llm = llm_factory(os.getenv("RAGAS_MODEL", "gpt-4o-mini"), client=evaluator_client)
    evaluator_embeddings = HuggingFaceEmbeddings(
        model=os.getenv("RAGAS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    )
    dataset_rows = [
        {
            key: row[key]
            for key in (
                "user_input",
                "response",
                "retrieved_contexts",
                "reference",
                "reference_contexts",
            )
        }
        for row in rows
    ]
    result = evaluate(
        Dataset.from_list(dataset_rows),
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
            answer_correctness,
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=RunConfig(max_workers=1, timeout=600, max_retries=2),
        raise_exceptions=False,
    )
    return {key: float(value) for key, value in result.items() if isinstance(value, (int, float))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("collection_id")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--provider", choices=("auto", "groq", "ollama"), default="auto")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, help="evaluate only the first N cases")
    parser.add_argument(
        "--dry-run", action="store_true", help="validate and print the manifest without model calls"
    )
    args = parser.parse_args()
    cases = load_cases(args.dataset)
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        cases = cases[: args.limit]
    if args.dry_run:
        print(
            json.dumps(
                {
                    "case_count": len(cases),
                    "domains": sorted({case["domain"] for case in cases}),
                    "metric_set": [
                        "context_precision",
                        "context_recall",
                        "faithfulness",
                        "answer_relevancy",
                        "answer_correctness",
                    ],
                },
                indent=2,
            )
        )
        return
    try:
        responses = [
            query_collection(
                args.base_url, args.collection_id, args.tenant_id, case["question"], args.provider
            )
            for case in cases
        ]
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise SystemExit(
            f"RankWise returned HTTP {exc.code} for the collection query. "
            f"Check collection readiness, tenant ID, and collection ID. Response: {details}"
        ) from exc
    except OSError as exc:
        raise SystemExit(
            f"Could not reach RankWise at {args.base_url}. "
            f"Start Flask and verify the collection ID: {exc}"
        ) from exc
    rows = build_rows(cases, responses)
    report = {
        "kind": "rankwise_ragas_benchmark",
        "recorded_at": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "collection_id": args.collection_id,
        "tenant_id": args.tenant_id,
        "requested_provider": args.provider,
        "case_count": len(rows),
        "metrics": run_ragas(rows),
        "cases": rows,
    }
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
