from __future__ import annotations

from pathlib import Path

import pymupdf
from rankwise.parsing import PdfParser, split_text


def test_split_text_honors_hard_size_and_overlap() -> None:
    text = " ".join(f"word-{index}" for index in range(300))
    chunks = list(split_text(text, target_size=200, overlap=25))

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 200 for _, _, chunk in chunks)
    assert all(start < end for start, end, _ in chunks)


def test_pdf_parser_produces_stable_page_aware_ids(
    tmp_path: Path, science_pdf_bytes: bytes
) -> None:
    path = tmp_path / "science.pdf"
    path.write_bytes(science_pdf_bytes)
    parser = PdfParser(chunk_size=300, chunk_overlap=30)

    first = parser.parse(path, document_id="doc_test", document_version_id="dv_test")
    second = parser.parse(path, document_id="doc_test", document_version_id="dv_test")

    assert len(first.pages) == 2
    assert [chunk.chunk_id for chunk in first.chunks] == [chunk.chunk_id for chunk in second.chunks]
    assert {chunk.page_number for chunk in first.chunks} == {1, 2}
    assert all(chunk.evidence_id.startswith("ev_") for chunk in first.chunks)
    assert all(chunk.bbox is not None for chunk in first.chunks)


def test_parser_records_selective_ocr_provenance(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "short.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "F = m*a")
    document.save(path)
    document.close()
    parser = PdfParser(
        chunk_size=300,
        chunk_overlap=30,
        ocr_enabled=True,
        ocr_min_characters=100,
    )
    monkeypatch.setattr(parser, "_ocr_textpage", lambda page: page.get_textpage())

    parsed = parser.parse(path, document_id="doc_ocr", document_version_id="dv_ocr")

    assert parsed.ocr_pages == (1,)
    assert any(chunk.extraction_method == "ocr" for chunk in parsed.chunks)
    assert any(chunk.content_type == "equation" for chunk in parsed.chunks)


def test_parser_extracts_native_table_regions(tmp_path: Path) -> None:
    path = tmp_path / "table.pdf"
    document = pymupdf.open()
    page = document.new_page()
    for x in (72, 180, 288):
        page.draw_line((x, 72), (x, 144))
    for y in (72, 108, 144):
        page.draw_line((72, y), (288, y))
    page.insert_text((82, 95), "Quantity")
    page.insert_text((190, 95), "Unit")
    page.insert_text((82, 131), "Force")
    page.insert_text((190, 131), "newton")
    document.save(path)
    document.close()

    parsed = PdfParser(chunk_size=300, chunk_overlap=30).parse(
        path, document_id="doc_table", document_version_id="dv_table"
    )
    tables = [chunk for chunk in parsed.chunks if chunk.content_type == "table"]
    assert len(tables) == 1
    assert "Quantity" in tables[0].text
    assert "newton" in tables[0].text
    assert tables[0].bbox is not None
