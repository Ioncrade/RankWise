"""Selective OCR, layout-aware extraction, and deterministic page chunking."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .domain import Chunk
from .errors import ValidationError

PARSER_VERSION = "pymupdf-layout-ocr-v2"
EQUATION_PATTERN = re.compile(
    r"(?:[A-Za-zΑ-ωΔΣ][A-Za-z0-9_()]*\s*(?:=|≈|≤|≥)\s*\S+|\S+\s*(?:→|⇌|->)\s*\S+)"
)
OCR_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_+-]+$")


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    pages: tuple[str, ...]
    chunks: tuple[Chunk, ...]
    warnings: tuple[str, ...] = ()
    ocr_pages: tuple[int, ...] = ()
    content_counts: dict[str, int] | None = None


def _stable_id(prefix: str, value: str, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]}"


def split_text(text: str, *, target_size: int, overlap: int) -> Iterator[tuple[int, int, str]]:
    """Split text with a hard size bound while preferring natural boundaries."""
    if target_size <= 0 or overlap < 0 or overlap >= target_size:
        raise ValueError("invalid chunk size or overlap")

    start = 0
    text_length = len(text)
    boundary_floor = max(1, int(target_size * 0.6))
    while start < text_length:
        hard_end = min(start + target_size, text_length)
        end = hard_end
        if hard_end < text_length:
            window = text[start + boundary_floor : hard_end]
            choices = [
                window.rfind("\n\n"),
                window.rfind("\n"),
                window.rfind(". "),
                window.rfind("; "),
                window.rfind(" "),
            ]
            best = max(choices)
            if best >= 0:
                end = start + boundary_floor + best + 1

        leading = len(text[start:end]) - len(text[start:end].lstrip())
        trailing = len(text[start:end].rstrip())
        actual_start = start + leading
        actual_end = start + trailing
        if actual_end > actual_start:
            yield actual_start, actual_end, text[actual_start:actual_end]

        if end >= text_length:
            break
        start = max(end - overlap, start + 1)


def _text_blocks(page, *, textpage=None) -> list[tuple[str, tuple[float, float, float, float]]]:
    blocks = page.get_text("blocks", sort=True, textpage=textpage)
    return [
        (
            str(block[4]).strip(),
            (float(block[0]), float(block[1]), float(block[2]), float(block[3])),
        )
        for block in blocks
        if len(block) >= 7 and int(block[6]) == 0 and str(block[4]).strip()
    ]


def _table_markdown(rows: Sequence[Sequence[object]]) -> str:
    normalized = [
        [str(cell).strip().replace("\n", " ") if cell is not None else "" for cell in row]
        for row in rows
        if row
    ]
    if not normalized:
        return ""
    width = max(map(len, normalized))
    normalized = [row + [""] * (width - len(row)) for row in normalized]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)


class PdfParser:
    def __init__(
        self,
        *,
        chunk_size: int,
        chunk_overlap: int,
        ocr_enabled: bool = False,
        ocr_languages: str = "eng",
        ocr_dpi: int = 200,
        ocr_min_characters: int = 24,
    ) -> None:
        if not OCR_LANGUAGE_PATTERN.fullmatch(ocr_languages):
            raise ValueError("invalid OCR language configuration")
        if not 72 <= ocr_dpi <= 600:
            raise ValueError("OCR DPI must be between 72 and 600")
        if ocr_min_characters <= 0:
            raise ValueError("OCR minimum characters must be positive")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ocr_enabled = ocr_enabled
        self.ocr_languages = ocr_languages
        self.ocr_dpi = ocr_dpi
        self.ocr_min_characters = ocr_min_characters

    @property
    def version(self) -> str:
        return (
            f"{PARSER_VERSION}:size={self.chunk_size}:overlap={self.chunk_overlap}:"
            f"ocr={int(self.ocr_enabled)}:{self.ocr_languages}:{self.ocr_dpi}:"
            f"minchars={self.ocr_min_characters}"
        )

    def _needs_ocr(self, page, text: str) -> bool:
        characters = sum(character.isalnum() for character in text)
        replacement_ratio = text.count("�") / max(1, len(text))
        return (
            characters < self.ocr_min_characters
            or replacement_ratio > 0.1
            or (bool(page.get_images(full=True)) and characters < self.ocr_min_characters * 4)
        )

    def _ocr_textpage(self, page):
        return page.get_textpage_ocr(
            language=self.ocr_languages,
            dpi=self.ocr_dpi,
            full=True,
        )

    @staticmethod
    def _chunk(
        *,
        document_id: str,
        document_version_id: str,
        page_id: str,
        page_number: int,
        char_start: int,
        char_end: int,
        text: str,
        content_type: str,
        extraction_method: str,
        bbox: tuple[float, float, float, float] | None,
    ) -> Chunk:
        identity = (
            f"{document_version_id}:{page_number}:{content_type}:{extraction_method}:"
            f"{char_start}:{char_end}:{bbox}:{text}"
        )
        chunk_id = _stable_id("chunk", identity)
        return Chunk(
            chunk_id=chunk_id,
            evidence_id=_stable_id("ev", chunk_id),
            document_id=document_id,
            document_version_id=document_version_id,
            page_id=page_id,
            page_number=page_number,
            char_start=char_start,
            char_end=char_end,
            text=text,
            content_type=content_type,
            extraction_method=extraction_method,
            bbox=bbox,
        )

    def parse(
        self,
        pdf_path: Path,
        *,
        document_id: str,
        document_version_id: str,
    ) -> ParsedDocument:
        with pdf_path.open("rb") as source:
            header = source.read(1024)
        if b"%PDF-" not in header:
            raise ValidationError("The uploaded file is not a valid PDF", code="invalid_pdf")

        pages: list[str] = []
        chunks: list[Chunk] = []
        warnings: list[str] = []
        ocr_pages: list[int] = []
        seen_content: set[tuple[int, str, str]] = set()
        try:
            import pymupdf

            with pymupdf.open(pdf_path) as document:
                if document.needs_pass:
                    raise ValidationError(
                        "Password-protected PDFs are not supported",
                        code="encrypted_pdf",
                    )
                for page_number, page in enumerate(document, start=1):
                    native_text = page.get_text("text", sort=True)
                    extraction_method = "native"
                    textpage = None
                    if self.ocr_enabled and self._needs_ocr(page, native_text):
                        try:
                            textpage = self._ocr_textpage(page)
                            ocr_text = page.get_text("text", sort=True, textpage=textpage)
                            if ocr_text.strip():
                                native_text = ocr_text
                                extraction_method = "ocr"
                                ocr_pages.append(page_number)
                            else:
                                warnings.append(f"Page {page_number}: OCR returned no text")
                        except Exception as exc:
                            warnings.append(
                                f"Page {page_number}: OCR unavailable or failed "
                                f"({type(exc).__name__})"
                            )

                    blocks = _text_blocks(page, textpage=textpage)
                    if not blocks and native_text.strip():
                        blocks = [
                            (
                                native_text.strip(),
                                tuple(float(value) for value in page.rect),
                            )
                        ]
                    page_text = "\n".join(block_text for block_text, _ in blocks)
                    pages.append(page_text)
                    page_id = _stable_id("page", f"{document_version_id}:{page_number}")
                    page_offset = 0
                    for block_text, bbox in blocks:
                        block_start = page_text.find(block_text, page_offset)
                        block_start = page_offset if block_start < 0 else block_start
                        for start, end, chunk_text in split_text(
                            block_text,
                            target_size=self.chunk_size,
                            overlap=self.chunk_overlap,
                        ):
                            key = (page_number, "text", chunk_text)
                            if key not in seen_content:
                                chunks.append(
                                    self._chunk(
                                        document_id=document_id,
                                        document_version_id=document_version_id,
                                        page_id=page_id,
                                        page_number=page_number,
                                        char_start=block_start + start,
                                        char_end=block_start + end,
                                        text=chunk_text,
                                        content_type="text",
                                        extraction_method=extraction_method,
                                        bbox=bbox,
                                    )
                                )
                                seen_content.add(key)
                        for line in block_text.splitlines():
                            equation_match = EQUATION_PATTERN.search(line.strip())
                            equation = equation_match.group(0) if equation_match else ""
                            key = (page_number, "equation", equation)
                            if 3 <= len(equation) <= 300 and key not in seen_content:
                                chunks.append(
                                    self._chunk(
                                        document_id=document_id,
                                        document_version_id=document_version_id,
                                        page_id=page_id,
                                        page_number=page_number,
                                        char_start=block_start,
                                        char_end=block_start + len(block_text),
                                        text=equation,
                                        content_type="equation",
                                        extraction_method=extraction_method,
                                        bbox=bbox,
                                    )
                                )
                                seen_content.add(key)
                        page_offset = block_start + len(block_text)

                    try:
                        tables = page.find_tables()
                        for table in tables.tables:
                            table_text = _table_markdown(table.extract())
                            key = (page_number, "table", table_text)
                            if table_text and key not in seen_content:
                                chunks.append(
                                    self._chunk(
                                        document_id=document_id,
                                        document_version_id=document_version_id,
                                        page_id=page_id,
                                        page_number=page_number,
                                        char_start=0,
                                        char_end=len(table_text),
                                        text=table_text,
                                        content_type="table",
                                        extraction_method="native_table",
                                        bbox=tuple(float(value) for value in table.bbox),
                                    )
                                )
                                seen_content.add(key)
                    except Exception as exc:
                        warnings.append(
                            f"Page {page_number}: table extraction failed ({type(exc).__name__})"
                        )
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(f"Unable to parse PDF: {exc}", code="invalid_pdf") from exc

        if not chunks:
            detail = "; ".join(warnings) if warnings else "OCR is disabled or found no text"
            raise ValidationError(
                f"No extractable text was found. {detail}",
                code="no_extractable_text",
            )
        counts = Counter(chunk.content_type for chunk in chunks)
        return ParsedDocument(
            pages=tuple(pages),
            chunks=tuple(chunks),
            warnings=tuple(warnings),
            ocr_pages=tuple(ocr_pages),
            content_counts=dict(counts),
        )
