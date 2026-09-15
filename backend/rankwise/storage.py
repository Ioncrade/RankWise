"""Safe local metadata and FAISS persistence."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .domain import Chunk, DocumentRecord, SearchHit
from .errors import NotFoundError, ValidationError


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".tmp-",
            delete=False,
        ) as temporary:
            json.dump(value, temporary, ensure_ascii=False, indent=2)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


class LocalDocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.documents_dir = root / "documents"
        self.state_path = root / "state.json"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def _version_dir(self, document_version_id: str) -> Path:
        if not document_version_id.startswith("dv_") or "/" in document_version_id:
            raise ValidationError("Invalid document version ID")
        return self.documents_dir / document_version_id

    def save(
        self,
        record: DocumentRecord,
        chunks: Sequence[Chunk],
        source_path: Path,
    ) -> None:
        version_dir = self._version_dir(record.document_version_id)
        version_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(version_dir / "document.json", record.to_dict())
        _atomic_json(version_dir / "chunks.json", [chunk.to_dict() for chunk in chunks])

        destination = version_dir / "source.pdf"
        temporary_path: Path | None = None
        try:
            with (
                source_path.open("rb") as source,
                tempfile.NamedTemporaryFile(
                    mode="wb", dir=version_dir, prefix=".tmp-", delete=False
                ) as temporary,
            ):
                shutil.copyfileobj(source, temporary)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()

    def activate(self, document_version_id: str) -> None:
        self.get_document(document_version_id)
        _atomic_json(self.state_path, {"active_document_version_id": document_version_id})

    def active_version_id(self) -> str | None:
        if not self.state_path.exists():
            return None
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            version_id = value.get("active_document_version_id")
            return version_id if isinstance(version_id, str) else None
        except (OSError, json.JSONDecodeError):
            return None

    def get_document(self, document_version_id: str) -> DocumentRecord:
        path = self._version_dir(document_version_id) / "document.json"
        if not path.exists():
            raise NotFoundError("Document version was not found", code="document_not_found")
        try:
            return DocumentRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise NotFoundError(
                "Document metadata is unavailable", code="document_metadata_unavailable"
            ) from exc

    def get_chunks(self, document_version_id: str) -> list[Chunk]:
        path = self._version_dir(document_version_id) / "chunks.json"
        if not path.exists():
            raise NotFoundError("Document chunks were not found", code="chunks_not_found")
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            return [Chunk.from_dict(value) for value in values]
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise NotFoundError(
                "Document chunks are unavailable", code="chunks_unavailable"
            ) from exc

    def resolve_evidence(self, document_version_id: str, evidence_id: str) -> Chunk:
        for chunk in self.get_chunks(document_version_id):
            if chunk.evidence_id == evidence_id:
                return chunk
        raise NotFoundError("Evidence was not found", code="evidence_not_found")

    def source_path(self, document_version_id: str) -> Path:
        path = self._version_dir(document_version_id) / "source.pdf"
        if not path.is_file():
            raise NotFoundError("Document source was not found", code="document_source_not_found")
        return path


class FaissIndexStore:
    def __init__(self, root: Path) -> None:
        self.index_dir = root / "indices"
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, document_version_id: str) -> Path:
        if not document_version_id.startswith("dv_") or "/" in document_version_id:
            raise ValidationError("Invalid document version ID")
        return self.index_dir / f"{document_version_id}.faiss"

    def build(self, document_version_id: str, vectors: Sequence[Sequence[float]]) -> None:
        if not vectors:
            raise ValidationError("Cannot build an index without vectors")
        import faiss
        import numpy as np

        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise ValidationError("Embedding matrix has an invalid shape")
        index = faiss.IndexFlatIP(int(matrix.shape[1]))
        index.add(matrix)

        path = self._path(document_version_id)
        temporary = tempfile.NamedTemporaryFile(
            dir=self.index_dir, prefix=".tmp-", suffix=".faiss", delete=False
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        try:
            faiss.write_index(index, str(temporary_path))
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def exists(self, document_version_id: str) -> bool:
        return self._path(document_version_id).is_file()

    def search(self, document_version_id: str, vector: Sequence[float], k: int) -> list[SearchHit]:
        import faiss
        import numpy as np

        path = self._path(document_version_id)
        if not path.exists():
            raise NotFoundError("Vector index was not found", code="index_not_found")
        index = faiss.read_index(str(path))
        query = np.asarray([vector], dtype="float32")
        if query.shape[1] != index.d:
            raise ValidationError("Query and index embedding dimensions do not match")
        scores, positions = index.search(query, min(k, index.ntotal))
        return [
            SearchHit(position=int(position), score=float(score))
            for score, position in zip(scores[0], positions[0], strict=True)
            if position >= 0
        ]
