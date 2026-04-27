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


class OCRTableStructureCoreTests(unittest.TestCase):
    """Phase 5 P1: OCR table text quality — unit tests for pure functions and integration."""

    # --- Integration tests (original) ---

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

    # --- Pure function unit tests ---

    def test_normalize_rect_4_tuple(self) -> None:
        self.assertEqual(ocr._normalize_rect([0, 10, 100, 90]), (0, 10, 100, 90))

    def test_normalize_rect_swapped_coords(self) -> None:
        self.assertEqual(ocr._normalize_rect([100, 90, 0, 10]), (0, 10, 100, 90))

    def test_normalize_rect_4_corner_format(self) -> None:
        result = ocr._normalize_rect([[10, 20], [90, 20], [90, 80], [10, 80]])
        self.assertEqual(result, (10, 20, 90, 80))

    def test_normalize_rect_none(self) -> None:
        self.assertIsNone(ocr._normalize_rect(None))

    def test_rect_overlap_area_full(self) -> None:
        area = ocr._rect_overlap_area((0, 0, 100, 100), (10, 10, 90, 90))
        self.assertEqual(area, 6400.0)

    def test_rect_overlap_area_partial(self) -> None:
        area = ocr._rect_overlap_area((0, 0, 50, 50), (25, 25, 75, 75))
        self.assertEqual(area, 625.0)

    def test_rect_overlap_area_none(self) -> None:
        area = ocr._rect_overlap_area((0, 0, 10, 10), (20, 20, 30, 30))
        self.assertEqual(area, 0.0)

    def test_merge_cell_texts_basic(self) -> None:
        result = ocr._merge_cell_texts([(10.0, 5.0, "a"), (10.0, 20.0, "b")])
        self.assertEqual(result, "a b")

    def test_merge_cell_texts_dedup(self) -> None:
        result = ocr._merge_cell_texts([(10.0, 5.0, "dup"), (20.0, 5.0, "dup")])
        self.assertEqual(result, "dup")

    def test_merge_cell_texts_multi_line(self) -> None:
        """Vertically separated text items should produce newline-separated output."""
        result = ocr._merge_cell_texts([(10.0, 5.0, "first"), (100.0, 5.0, "second")])
        self.assertEqual(result, "first\nsecond")

    def test_merge_cell_texts_empty(self) -> None:
        self.assertEqual(ocr._merge_cell_texts([]), "")

    def test_is_meaningful_table_matrix_false_when_few_cells(self) -> None:
        self.assertFalse(ocr._is_meaningful_table_matrix([["a"]]))

    def test_is_meaningful_table_matrix_true(self) -> None:
        self.assertTrue(ocr._is_meaningful_table_matrix([["a", "b"], ["c", "d"]]))

    def test_match_ocr_line_to_cell_inside(self) -> None:
        cells = [{"rect": (0, 0, 100, 50), "cx": 50.0, "cy": 25.0, "texts": []}]
        result = ocr._match_ocr_line_to_cell((10, 10, 90, 40), cells)
        self.assertIsNotNone(result)
        self.assertEqual(result["rect"], (0, 0, 100, 50))

    def test_match_ocr_line_to_cell_nearby(self) -> None:
        cells = [{"rect": (0, 0, 100, 50), "cx": 50.0, "cy": 25.0, "texts": []}]
        result = ocr._match_ocr_line_to_cell((5, -5, 95, 5), cells)
        self.assertIsNotNone(result)
        self.assertEqual(result["rect"], (0, 0, 100, 50))

    def test_match_ocr_line_to_cell_too_far(self) -> None:
        cells = [{"rect": (0, 0, 100, 50), "cx": 50.0, "cy": 25.0, "texts": []}]
        result = ocr._match_ocr_line_to_cell((200, 200, 300, 250), cells)
        self.assertIsNone(result)

    def test_match_ocr_line_to_cell_empty_cells(self) -> None:
        result = ocr._match_ocr_line_to_cell((0, 0, 10, 10), [])
        self.assertIsNone(result)

    # --- OCR confidence extraction ---

    def test_extract_page_ocr_confidence_v2(self) -> None:
        """Phase 5 P1: OCR置信度 v2 format [bbox, (text, conf)]."""
        result = ocr._extract_page_ocr_confidence(
            [[[0, 0], ("OK", 0.98)], [[1, 1], ("NG", 0.75)]]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "OK")
        self.assertAlmostEqual(result[0]["confidence"], 0.98)

    def test_extract_page_ocr_confidence_v3(self) -> None:
        """Phase 5 P1: OCR置信度 v3 format [OCRResult]."""
        result = ocr._extract_page_ocr_confidence(
            [{"rec_texts": ["hello", "world"], "rec_scores": [0.99, 0.88]}]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "hello")
        self.assertAlmostEqual(result[0]["confidence"], 0.99)

    def test_extract_page_ocr_confidence_v3_no_scores(self) -> None:
        """Phase 5 P1: OCR置信度 v3 without scores defaults to 0.0."""
        result = ocr._extract_page_ocr_confidence(
            [{"rec_texts": ["fallback"]}]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "fallback")
        self.assertEqual(result[0]["confidence"], 0.0)

    def test_extract_page_ocr_confidence_empty(self) -> None:
        self.assertEqual(ocr._extract_page_ocr_confidence(None), [])
        self.assertEqual(ocr._extract_page_ocr_confidence([]), [])


if __name__ == "__main__":
    unittest.main()
