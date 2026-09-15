"""SQLite catalog for collections, jobs, and generated note versions."""

from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import NotFoundError, ValidationError


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


@dataclass(frozen=True, slots=True)
class CollectionRecord:
    collection_id: str
    tenant_id: str
    title: str
    subject: str
    education_level: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    tenant_id: str
    kind: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NoteVersion:
    note_id: str
    note_version_id: str
    collection_id: str
    title: str
    profile: str
    markdown: str
    content: dict[str, Any]
    citations: tuple[dict[str, Any], ...]
    document_version_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    change_reason: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["citations"] = list(self.citations)
        value["document_version_ids"] = list(self.document_version_ids)
        value["warnings"] = list(self.warnings)
        return value


@dataclass(frozen=True, slots=True)
class ImageRecord:
    image_id: str
    collection_id: str
    filename: str
    mime_type: str
    sha256: str
    document_version_id: str
    storage_path: str
    warnings: tuple[str, ...]
    created_at: str

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("storage_path")
        value["warnings"] = list(self.warnings)
        return value


class Catalog:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS collections (
                    collection_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    education_level TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collection_documents (
                    collection_id TEXT NOT NULL
                        REFERENCES collections(collection_id) ON DELETE CASCADE,
                    document_version_id TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (collection_id, document_version_id)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notes (
                    note_version_id TEXT PRIMARY KEY,
                    note_id TEXT NOT NULL,
                    collection_id TEXT NOT NULL
                        REFERENCES collections(collection_id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    document_versions_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    change_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS images (
                    image_id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL
                        REFERENCES collections(collection_id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    document_version_id TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_collections_tenant
                    ON collections(tenant_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_notes_current ON notes(note_id, created_at DESC);
                """
            )

    @staticmethod
    def _tenant_id(tenant_id: str) -> str:
        normalized = tenant_id.strip()
        if not normalized or len(normalized) > 100:
            raise ValidationError("A valid tenant ID is required", code="invalid_tenant")
        return normalized

    def create_collection(
        self, tenant_id: str, title: str, subject: str, education_level: str
    ) -> CollectionRecord:
        title = title.strip()
        if not title:
            raise ValidationError("Collection title is required")
        record = CollectionRecord(
            collection_id=_id("col"),
            tenant_id=self._tenant_id(tenant_id),
            title=title,
            subject=subject.strip() or "general_science",
            education_level=education_level.strip() or "undergraduate",
            created_at=_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collections
                (collection_id, tenant_id, title, subject, education_level, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                tuple(record.to_dict().values()),
            )
        return record

    def get_collection(self, collection_id: str, tenant_id: str) -> CollectionRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collections WHERE collection_id = ? AND tenant_id = ?",
                (collection_id, self._tenant_id(tenant_id)),
            ).fetchone()
        if row is None:
            raise NotFoundError("Collection was not found", code="collection_not_found")
        return CollectionRecord(**dict(row))

    def list_collections(self, tenant_id: str) -> list[CollectionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM collections WHERE tenant_id = ? ORDER BY created_at DESC
                """,
                (self._tenant_id(tenant_id),),
            ).fetchall()
        return [CollectionRecord(**dict(row)) for row in rows]

    def add_document(self, collection_id: str, tenant_id: str, document_version_id: str) -> None:
        self.get_collection(collection_id, tenant_id)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO collection_documents VALUES (?, ?, ?)",
                (collection_id, document_version_id, _now()),
            )

    def document_versions(self, collection_id: str, tenant_id: str) -> list[str]:
        self.get_collection(collection_id, tenant_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_version_id FROM collection_documents
                WHERE collection_id = ? ORDER BY added_at
                """,
                (collection_id,),
            ).fetchall()
        return [str(row["document_version_id"]) for row in rows]

    def has_document_access(self, document_version_id: str, tenant_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM collection_documents AS documents
                JOIN collections ON collections.collection_id = documents.collection_id
                WHERE documents.document_version_id = ? AND collections.tenant_id = ?
                LIMIT 1
                """,
                (document_version_id, self._tenant_id(tenant_id)),
            ).fetchone()
        return row is not None

    def save_image(
        self,
        *,
        image_id: str,
        collection_id: str,
        tenant_id: str,
        filename: str,
        mime_type: str,
        sha256: str,
        document_version_id: str,
        storage_path: str,
        warnings: tuple[str, ...],
    ) -> ImageRecord:
        self.get_collection(collection_id, tenant_id)
        record = ImageRecord(
            image_id=image_id,
            collection_id=collection_id,
            filename=filename,
            mime_type=mime_type,
            sha256=sha256,
            document_version_id=document_version_id,
            storage_path=storage_path,
            warnings=warnings,
            created_at=_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO images
                (image_id, collection_id, filename, mime_type, sha256,
                 document_version_id, storage_path, warnings_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.image_id,
                    record.collection_id,
                    record.filename,
                    record.mime_type,
                    record.sha256,
                    record.document_version_id,
                    record.storage_path,
                    json.dumps(record.warnings),
                    record.created_at,
                ),
            )
        return record

    def get_image(self, image_id: str, tenant_id: str) -> ImageRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT images.* FROM images
                JOIN collections ON collections.collection_id = images.collection_id
                WHERE images.image_id = ? AND collections.tenant_id = ?
                """,
                (image_id, self._tenant_id(tenant_id)),
            ).fetchone()
        if row is None:
            raise NotFoundError("Image was not found", code="image_not_found")
        return ImageRecord(
            image_id=row["image_id"],
            collection_id=row["collection_id"],
            filename=row["filename"],
            mime_type=row["mime_type"],
            sha256=row["sha256"],
            document_version_id=row["document_version_id"],
            storage_path=row["storage_path"],
            warnings=tuple(json.loads(row["warnings_json"])),
            created_at=row["created_at"],
        )

    def list_images(self, collection_id: str, tenant_id: str) -> list[ImageRecord]:
        self.get_collection(collection_id, tenant_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT image_id FROM images WHERE collection_id = ? ORDER BY created_at",
                (collection_id,),
            ).fetchall()
        return [self.get_image(row["image_id"], tenant_id) for row in rows]

    def create_job(self, tenant_id: str, kind: str, payload: dict[str, Any]) -> JobRecord:
        now = _now()
        record = JobRecord(
            job_id=_id("job"),
            tenant_id=self._tenant_id(tenant_id),
            kind=kind,
            status="queued",
            payload=payload,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.job_id,
                    record.tenant_id,
                    record.kind,
                    record.status,
                    json.dumps(record.payload),
                    None,
                    None,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def update_job(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET status = ?, result_json = ?, error_json = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    json.dumps(result) if result is not None else None,
                    json.dumps(error) if error is not None else None,
                    _now(),
                    job_id,
                ),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("Job was not found", code="job_not_found")

    def get_job(self, job_id: str, tenant_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ? AND tenant_id = ?",
                (job_id, self._tenant_id(tenant_id)),
            ).fetchone()
        if row is None:
            raise NotFoundError("Job was not found", code="job_not_found")
        return JobRecord(
            job_id=row["job_id"],
            tenant_id=row["tenant_id"],
            kind=row["kind"],
            status=row["status"],
            payload=json.loads(row["payload_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=json.loads(row["error_json"]) if row["error_json"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_note(
        self,
        *,
        collection_id: str,
        title: str,
        profile: str,
        markdown: str,
        citations: tuple[dict[str, Any], ...],
        content: dict[str, Any],
        document_version_ids: tuple[str, ...],
        warnings: tuple[str, ...],
        change_reason: str,
        tenant_id: str,
        note_id: str | None = None,
    ) -> NoteVersion:
        self.get_collection(collection_id, tenant_id)
        record = NoteVersion(
            note_id=note_id or _id("note"),
            note_version_id=_id("nv"),
            collection_id=collection_id,
            title=title,
            profile=profile,
            markdown=markdown,
            content=content,
            citations=citations,
            document_version_ids=document_version_ids,
            warnings=warnings,
            change_reason=change_reason,
            created_at=_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notes
                (note_version_id, note_id, collection_id, title, profile, markdown,
                 content_json, citations_json, document_versions_json, warnings_json,
                 change_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.note_version_id,
                    record.note_id,
                    record.collection_id,
                    record.title,
                    record.profile,
                    record.markdown,
                    json.dumps(record.content),
                    json.dumps(record.citations),
                    json.dumps(record.document_version_ids),
                    json.dumps(record.warnings),
                    record.change_reason,
                    record.created_at,
                ),
            )
        return record

    def get_note(self, note_id: str, tenant_id: str) -> NoteVersion:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM notes WHERE note_id = ? ORDER BY created_at DESC LIMIT 1",
                (note_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("Note was not found", code="note_not_found")
        self.get_collection(row["collection_id"], tenant_id)
        return self._note_from_row(row)

    def list_note_versions(self, note_id: str, tenant_id: str) -> list[NoteVersion]:
        current = self.get_note(note_id, tenant_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM notes WHERE note_id = ? ORDER BY created_at DESC",
                (current.note_id,),
            ).fetchall()
        return [self._note_from_row(row) for row in rows]

    @staticmethod
    def _note_from_row(row: sqlite3.Row) -> NoteVersion:
        return NoteVersion(
            note_id=row["note_id"],
            note_version_id=row["note_version_id"],
            collection_id=row["collection_id"],
            title=row["title"],
            profile=row["profile"],
            markdown=row["markdown"],
            content=json.loads(row["content_json"]),
            citations=tuple(json.loads(row["citations_json"])),
            document_version_ids=tuple(json.loads(row["document_versions_json"])),
            warnings=tuple(json.loads(row["warnings_json"])),
            change_reason=row["change_reason"],
            created_at=row["created_at"],
        )
