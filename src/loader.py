from __future__ import annotations

from pathlib import Path

import fitz
import pdfplumber


def open_pdf(input_path: Path) -> tuple[fitz.Document, pdfplumber.PDF]:
    return fitz.open(input_path), pdfplumber.open(str(input_path))
