from __future__ import annotations

import sys
from pathlib import Path

import fitz
import pdfplumber


def open_pdf(input_path: Path) -> tuple[fitz.Document | None, pdfplumber.PDF | None]:
    try:
        doc = fitz.open(input_path)
    except Exception as exc:
        print(f"fitz 无法打开 PDF: {exc}", file=sys.stderr)
        return None, None

    try:
        plumber = pdfplumber.open(str(input_path))
    except Exception as exc:
        doc.close()
        print(f"pdfplumber 无法打开 PDF: {exc}", file=sys.stderr)
        return None, None

    return doc, plumber
