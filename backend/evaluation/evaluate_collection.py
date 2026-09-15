#!/usr/bin/env python3
"""Evaluate a running Phase 1 collection endpoint against document/page labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import request

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from rankwise.evaluation import (  # noqa: E402
    CollectionRetrievalCase,
    collection_retrieval_metrics,
)


def _retrieve(base_url: str, collection_id: str, tenant_id: str, query: str) -> tuple[str, ...]:
    api_request = request.Request(
        f"{base_url.rstrip('/')}/v1/collections/{collection_id}/queries",
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json", "X-Tenant-ID": tenant_id},
        method="POST",
    )
    with request.urlopen(api_request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    return tuple(
        f"{item['document_filename']}#{item['page_number']}"
        for item in payload["retrieved_evidence"]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("collection_id")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    cases = []
    for line in args.dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cases.append(
            CollectionRetrievalCase(
                ranked_locations=_retrieve(
                    args.base_url, args.collection_id, args.tenant_id, item["query"]
                ),
                relevant_locations=frozenset(item["relevant_locations"]),
            )
        )
    print(json.dumps(collection_retrieval_metrics(cases, k=args.k), indent=2))


if __name__ == "__main__":
    main()
