from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import AppConfig
from src import ocr
from src.context import PipelineContext
from src.parser import PDFParser


class _FakePixmap:
    height = 1
    width = 1
    n = 3
    samples = bytes([0, 0, 0])


class _FakePage:
    def get_pixmap(self, matrix=None, alpha=False):
        return _FakePixmap()


class _FakeDoc:
    def __init__(self, page_count: int) -> None:
        self._pages = [_FakePage() for _ in range(page_count)]

    def __len__(self) -> int:
        return len(self._pages)

    def load_page(self, page_index: int):
        return self._pages[page_index]

    def close(self) -> None:
        return None


class _FakeTableEngine:
    def predict(self, image_array):
        return [
            {
                "bbox": [
                    [[0, 0], [90, 0], [90, 40], [0, 40]],
                    [[100, 0], [190, 0], [190, 40], [100, 40]],
                    [[0, 50], [90, 50], [90, 90], [0, 90]],
                    [[100, 50], [190, 50], [190, 90], [100, 90]],
                ]
            }
        ]


class _FakeTextEngine:
    def ocr(self, image_array):
        return [
            {
                "rec_texts": ["参数", "数值", "压力", "10"],
                "rec_polys": [
                    [[10, 10], [80, 10], [80, 30], [10, 30]],
                    [[110, 10], [180, 10], [180, 30], [110, 30]],
                    [[10, 60], [80, 60], [80, 80], [10, 80]],
                    [[110, 60], [180, 60], [180, 80], [110, 80]],
                ],
            }
        ]


class _FakePlumberPage:
    def __init__(self, tables):
        self._tables = tables

    def extract_tables(self):
        return self._tables


class _FakePlumberDoc:
    def __init__(self, pages):
        self.pages = pages


class OCRTableStructureTests(unittest.TestCase):
    def test_run_table_structure_on_pages_builds_table_matrix(self) -> None:
        with patch("src.ocr.get_table_structure_engine", return_value=_FakeTableEngine()), patch(
            "src.ocr.get_ocr_engine",
            return_value=_FakeTextEngine(),
        ), patch(
            "src.ocr.fitz.open",
            return_value=_FakeDoc(page_count=1),
        ):
            results, runtime = ocr.run_table_structure_on_pages(
                pdf_path=Path("sample.pdf"),
                page_indices=[0],
                lang="ch",
                dpi=220,
                batch_size=1,
            )

        self.assertEqual(results, {0: [[["参数", "数值"], ["压力", "10"]]]})
        self.assertEqual(runtime["executed_pages"], 1)
        self.assertEqual(runtime["detected_table_pages"], 1)
        self.assertEqual(runtime["extracted_table_count"], 1)
        self.assertFalse(runtime["timed_out"])

    def test_parser_extract_page_tables_merges_force_ocr_tables(self) -> None:
        config = AppConfig(
            input_path=Path("sample.pdf"),
            output_dir=Path("output"),
        )
        context = PipelineContext(
            force_ocr_tables={0: [[["OCR参数", "OCR数值"], ["温度", "120"]]]},
        )
        parser = PDFParser(config, context)
        plumber_doc = _FakePlumberDoc(
            pages=[
                _FakePlumberPage(
                    tables=[
                        [["PDF参数", "PDF数值"], ["压力", "10"]],
                    ]
                )
            ]
        )

        page_tables = parser._extract_page_tables(plumber_doc)

        self.assertEqual(len(page_tables[0]), 2)
        self.assertEqual(page_tables[0][0], [["PDF参数", "PDF数值"], ["压力", "10"]])
        self.assertEqual(page_tables[0][1], [["OCR参数", "OCR数值"], ["温度", "120"]])


if __name__ == "__main__":
    unittest.main()
