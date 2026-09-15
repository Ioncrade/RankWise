#!/usr/bin/env python3
"""Create the small native-text science PDF used by the evaluation example."""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

PAGES = (
    (
        "States of matter\n\n"
        "At standard pressure, pure water freezes at 0 degrees Celsius and boils at "
        "100 degrees Celsius. A phase change changes physical state but not molecular identity."
    ),
    (
        "Newton's second law\n\n"
        "Net force equals mass times acceleration: F = m a. In SI units, force is measured "
        "in newtons, mass in kilograms, and acceleration in metres per second squared."
    ),
    (
        "Chemical equations\n\n"
        "A balanced equation conserves the number of atoms of each element. The combustion "
        "of methane can be written CH4 + 2 O2 -> CO2 + 2 H2O."
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open()
    for text in PAGES:
        page = document.new_page()
        page.insert_textbox((72, 72, 540, 760), text, fontsize=12)
    document.save(args.output)
    document.close()


if __name__ == "__main__":
    main()
