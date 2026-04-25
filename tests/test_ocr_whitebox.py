from __future__ import annotations

import builtins
import unittest
from pathlib import Path
from unittest.mock import patch

from src import ocr


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


class OCRWhiteBoxTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_table_engine_cache = ocr._TABLE_ENGINE_CACHE
        self._orig_table_engine_available = ocr._TABLE_ENGINE_AVAILABLE

    def tearDown(self) -> None:
        ocr._TABLE_ENGINE_CACHE = self._orig_table_engine_cache
        ocr._TABLE_ENGINE_AVAILABLE = self._orig_table_engine_available

    def test_get_table_structure_engine_returns_none_when_import_fails(self) -> None:
        original_import = builtins.__import__

        def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "paddleocr":
                raise ImportError("boom")
            return original_import(name, globals, locals, fromlist, level)

        ocr._TABLE_ENGINE_CACHE = None
        ocr._TABLE_ENGINE_AVAILABLE = None
        with patch("builtins.__import__", side_effect=_fake_import):
            engine = ocr.get_table_structure_engine()

        self.assertIsNone(engine)
        self.assertFalse(ocr._TABLE_ENGINE_AVAILABLE)

    def test_run_ocr_on_pages_returns_empty_when_engine_unavailable(self) -> None:
        with patch("src.ocr.get_ocr_engine", return_value=None):
            results, runtime = ocr.run_ocr_on_pages(
                pdf_path=Path("sample.pdf"),
                page_indices=[0, 1],
                lang="ch",
                dpi=220,
                batch_size=1,
                timeout_seconds=1.0,
            )

        self.assertEqual(results, {})
        self.assertEqual(runtime["executed_pages"], 0)
        self.assertEqual(runtime["successful_pages"], 0)
        self.assertFalse(runtime["timed_out"])

    def test_run_table_structure_on_pages_stops_after_soft_timeout_and_keeps_partial_results(self) -> None:
        with patch("src.ocr.get_table_structure_engine", return_value=_FakeTableEngine()), patch(
            "src.ocr.get_ocr_engine",
            return_value=_FakeTextEngine(),
        ), patch(
            "src.ocr.fitz.open",
            return_value=_FakeDoc(page_count=2),
        ), patch(
            "src.ocr.time.perf_counter",
            side_effect=[0.0, 0.0, 2.0],
        ):
            results, runtime = ocr.run_table_structure_on_pages(
                pdf_path=Path("sample.pdf"),
                page_indices=[0, 1],
                lang="ch",
                dpi=220,
                batch_size=1,
                timeout_seconds=1.0,
            )

        self.assertEqual(results, {0: [[["参数", "数值"], ["压力", "10"]]]})
        self.assertTrue(runtime["timed_out"])
        self.assertEqual(runtime["executed_pages"], 1)
        self.assertEqual(runtime["detected_table_pages"], 1)
        self.assertEqual(runtime["extracted_table_count"], 1)
        self.assertEqual(runtime["batch_count"], 1)

    def test_run_table_structure_on_pages_returns_empty_when_text_engine_missing(self) -> None:
        with patch("src.ocr.get_table_structure_engine", return_value=_FakeTableEngine()), patch(
            "src.ocr.get_ocr_engine",
            return_value=None,
        ):
            results, runtime = ocr.run_table_structure_on_pages(
                pdf_path=Path("sample.pdf"),
                page_indices=[0],
                lang="ch",
                dpi=220,
                batch_size=1,
            )

        self.assertEqual(results, {})
        self.assertEqual(runtime["executed_pages"], 0)
        self.assertEqual(runtime["detected_table_pages"], 0)
        self.assertEqual(runtime["extracted_table_count"], 0)

    def test_build_table_matrix_gracefully_handles_alignment_miss(self) -> None:
        cell_boxes = [
            [[0, 0], [90, 0], [90, 40], [0, 40]],
            [[100, 0], [190, 0], [190, 40], [100, 40]],
            [[0, 50], [90, 50], [90, 90], [0, 90]],
            [[100, 50], [190, 50], [190, 90], [100, 90]],
        ]
        ocr_lines = [
            {"text": "outside-1", "rect": (400.0, 400.0, 460.0, 420.0), "cx": 430.0, "cy": 410.0},
            {"text": "outside-2", "rect": (500.0, 500.0, 560.0, 520.0), "cx": 530.0, "cy": 510.0},
        ]

        matrix = ocr._build_table_matrix_from_cells(cell_boxes, ocr_lines)

        self.assertEqual(matrix, [["", ""], ["", ""]])

    def test_build_table_matrix_keeps_nearby_line_with_small_alignment_drift(self) -> None:
        cell_boxes = [
            [[0, 0], [90, 0], [90, 40], [0, 40]],
            [[100, 0], [190, 0], [190, 40], [100, 40]],
            [[0, 50], [90, 50], [90, 90], [0, 90]],
            [[100, 50], [190, 50], [190, 90], [100, 90]],
        ]
        ocr_lines = [
            {"text": "near-edge", "rect": (91.0, 10.0, 97.0, 24.0), "cx": 94.0, "cy": 17.0},
        ]

        matrix = ocr._build_table_matrix_from_cells(cell_boxes, ocr_lines)

        self.assertEqual(matrix, [["near-edge", ""], ["", ""]])

    def test_build_table_matrix_returns_empty_for_empty_cell_boxes(self) -> None:
        ocr_lines = [
            {"text": "x", "rect": (0, 0, 10, 10), "cx": 5, "cy": 5},
        ]

        matrix = ocr._build_table_matrix_from_cells([], ocr_lines)

        self.assertEqual(matrix, [])

    def test_build_table_matrix_with_empty_ocr_lines_returns_empty_string_matrix(self) -> None:
        cell_boxes = [
            [[0, 0], [90, 0], [90, 40], [0, 40]],
            [[100, 0], [190, 0], [190, 40], [100, 40]],
            [[0, 50], [90, 50], [90, 90], [0, 90]],
            [[100, 50], [190, 50], [190, 90], [100, 90]],
        ]

        matrix = ocr._build_table_matrix_from_cells(cell_boxes, [])

        self.assertEqual(matrix, [["", ""], ["", ""]])

    def test_build_table_matrix_preserves_degenerate_shapes(self) -> None:
        cell_boxes = [
            [[0, 0], [90, 0], [90, 40], [0, 40]],
            [[100, 0], [190, 0], [190, 40], [100, 40]],
            [[200, 0], [290, 0], [290, 40], [200, 40]],
        ]
        ocr_lines = [
            {"text": "内容", "rect": (110.0, 10.0, 170.0, 24.0), "cx": 140.0, "cy": 17.0},
        ]

        matrix = ocr._build_table_matrix_from_cells(cell_boxes, ocr_lines)

        self.assertEqual(matrix, [["", "内容", ""]])


if __name__ == "__main__":
    unittest.main()
