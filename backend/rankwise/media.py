"""Authorized page rendering and standalone-image ingestion services."""

from __future__ import annotations

import hashlib
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .catalog import Catalog, ImageRecord, JobRecord
from .errors import NotFoundError, ValidationError
from .jobs import JobRunner
from .ports import DocumentStore
from .services import IngestionService

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


@dataclass(frozen=True, slots=True)
class RenderedPage:
    data: bytes
    width: int
    height: int
    dpi: int
    bbox: tuple[float, float, float, float]


class MediaService:
    def __init__(self, document_store: DocumentStore, *, max_dpi: int = 300) -> None:
        self.document_store = document_store
        self.max_dpi = max_dpi

    def render_page(
        self,
        document_version_id: str,
        page_number: int,
        *,
        dpi: int = 144,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> RenderedPage:
        if page_number <= 0:
            raise ValidationError("page_number must be positive")
        if not 72 <= dpi <= self.max_dpi:
            raise ValidationError(f"dpi must be between 72 and {self.max_dpi}")
        import pymupdf

        source_path = self.document_store.source_path(document_version_id)
        with pymupdf.open(source_path) as document:
            if page_number > document.page_count:
                raise NotFoundError("Page was not found", code="page_not_found")
            page = document[page_number - 1]
            clip = page.rect
            if bbox is not None:
                if (
                    len(bbox) != 4
                    or not all(math.isfinite(value) for value in bbox)
                    or bbox[2] <= bbox[0]
                    or bbox[3] <= bbox[1]
                ):
                    raise ValidationError("bbox must be an ordered x0,y0,x1,y1 rectangle")
                clip = pymupdf.Rect(*bbox) & page.rect
                if clip.is_empty or clip.is_infinite:
                    raise ValidationError("bbox does not intersect the page")
            scale = dpi / 72
            estimated_pixels = clip.width * scale * clip.height * scale
            if estimated_pixels > 25_000_000:
                raise ValidationError("Rendered region exceeds the 25 megapixel limit")
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False)
            return RenderedPage(
                data=pixmap.tobytes("png"),
                width=pixmap.width,
                height=pixmap.height,
                dpi=dpi,
                bbox=(float(clip.x0), float(clip.y0), float(clip.x1), float(clip.y1)),
            )


class ImageService:
    def __init__(
        self,
        *,
        catalog: Catalog,
        jobs: JobRunner,
        ingestion: IngestionService,
        data_dir: Path,
    ) -> None:
        self.catalog = catalog
        self.jobs = jobs
        self.ingestion = ingestion
        self.images_dir = data_dir / "images"
        self.pending_dir = data_dir / "pending-images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(
        self,
        collection_id: str,
        tenant_id: str,
        source_path: Path,
        filename: str,
    ) -> JobRecord:
        self.catalog.get_collection(collection_id, tenant_id)
        extension = Path(filename).suffix.casefold()
        if extension not in IMAGE_MIME_TYPES:
            raise ValidationError(
                "Supported image types are PNG, JPEG, WebP, and TIFF",
                code="unsupported_file_type",
            )
        pending_path = self.pending_dir / f"{os.urandom(16).hex()}{extension}"
        shutil.copyfile(source_path, pending_path)

        def ingest() -> dict:
            raw_destination: Path | None = None
            try:
                digest = hashlib.sha256(pending_path.read_bytes()).hexdigest()
                image_id = (
                    "img_" + hashlib.sha256(f"{collection_id}:{digest}".encode()).hexdigest()[:24]
                )
                try:
                    existing = self.catalog.get_image(image_id, tenant_id)
                except NotFoundError:
                    existing = None
                if existing is not None:
                    return {"image": existing.public_dict(), "reused": True}

                import pymupdf

                try:
                    with pymupdf.open(pending_path) as image_document:
                        if image_document.page_count != 1:
                            raise ValidationError(
                                "The image could not be decoded", code="invalid_image"
                            )
                        pdf_bytes = image_document.convert_to_pdf()
                except ValidationError:
                    raise
                except Exception as exc:
                    raise ValidationError(
                        "The image could not be decoded", code="invalid_image"
                    ) from exc

                image_dir = self.images_dir / image_id
                image_dir.mkdir(parents=True, exist_ok=True)
                raw_destination = image_dir / f"original{extension}"
                temporary_raw = image_dir / f".tmp-{os.urandom(8).hex()}{extension}"
                shutil.copyfile(pending_path, temporary_raw)
                os.replace(temporary_raw, raw_destination)

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as converted:
                    converted.write(pdf_bytes)
                    converted_path = Path(converted.name)
                try:
                    document = self.ingestion.ingest_pdf(
                        converted_path,
                        filename,
                        activate=False,
                        source_type="image",
                    )
                finally:
                    converted_path.unlink(missing_ok=True)
                self.catalog.add_document(collection_id, tenant_id, document.document_version_id)
                record = self.catalog.save_image(
                    image_id=image_id,
                    collection_id=collection_id,
                    tenant_id=tenant_id,
                    filename=filename,
                    mime_type=IMAGE_MIME_TYPES[extension],
                    sha256=digest,
                    document_version_id=document.document_version_id,
                    storage_path=str(raw_destination),
                    warnings=document.warnings,
                )
                return {"image": record.public_dict(), "reused": False}
            except Exception:
                if raw_destination is not None:
                    raw_destination.unlink(missing_ok=True)
                raise
            finally:
                pending_path.unlink(missing_ok=True)

        try:
            return self.jobs.submit(
                tenant_id,
                "image_ingestion",
                {"collection_id": collection_id, "filename": filename},
                ingest,
            )
        except Exception:
            pending_path.unlink(missing_ok=True)
            raise

    def get(self, image_id: str, tenant_id: str) -> tuple[ImageRecord, Path]:
        record = self.catalog.get_image(image_id, tenant_id)
        path = Path(record.storage_path)
        if not path.is_file():
            raise NotFoundError("Image source was not found", code="image_source_not_found")
        return record, path
