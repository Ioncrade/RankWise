from __future__ import annotations

import io
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def science_pdf_bytes() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Water changes state at standard pressure. Pure water freezes at 0 degrees Celsius.\n"
        "A phase change does not change the identity of the water molecules.",
    )
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Newton's second law states that net force equals mass times acceleration: F = m a.\n"
        "Force is measured in newtons when mass is in kilograms and acceleration is in "
        "metres per second squared.",
    )
    value = document.tobytes()
    document.close()
    return value


@pytest.fixture
def science_pdf_upload(science_pdf_bytes: bytes):
    return io.BytesIO(science_pdf_bytes), "science.pdf"
