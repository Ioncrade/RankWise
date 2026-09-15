#!/usr/bin/env python3
"""Evaluate a running RankWise /retrieve endpoint against gold page labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import request

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from rankwise.evaluation import RetrievalCase, retrieval_metrics  # noqa: E402


def _retrieve(base_url: str, query: str, document_version_id: str) -> tuple[int, ...]:
    body = json.dumps({"query": query, "document_version_id": document_version_id}).encode("utf-8")
    api_request = request.Request(
        f"{base_url.rstrip('/')}/retrieve",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(api_request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    return tuple(int(item["page_number"]) for item in payload["evidence"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("document_version_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    cases: list[RetrievalCase] = []
    for line in args.dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        ranked_pages = _retrieve(args.base_url, item["query"], args.document_version_id)
        cases.append(
            RetrievalCase(
                ranked_pages=ranked_pages,
                relevant_pages=frozenset(int(page) for page in item["relevant_pages"]),
            )
        )
    print(json.dumps(retrieval_metrics(cases, k=args.k), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
