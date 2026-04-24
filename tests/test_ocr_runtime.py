from __future__ import annotations

import unittest
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


class _FakeEngine:
    def __init__(self) -> None:
        self.calls = 0

    def ocr(self, image_array):
        self.calls += 1
        return [[[0, 0], ("recognized text", 0.99)]]


class OcrRuntimeTests(unittest.TestCase):
    def test_build_ocr_runtime_plan_reduces_dpi_for_large_batches(self) -> None:
        plan = ocr.build_ocr_runtime_plan(
            page_count=12,
            requested_dpi=300,
            batch_size=5,
            timeout_seconds=180.0,
            large_doc_page_threshold=8,
            reduced_dpi=220,
        )

        self.assertEqual(plan["requested_dpi"], 300)
        self.assertEqual(plan["effective_dpi"], 220)
        self.assertTrue(plan["dpi_downgraded"])
        self.assertEqual(plan["batch_size"], 5)
        self.assertEqual(plan["timeout_seconds"], 180.0)

    def test_run_ocr_on_pages_stops_after_soft_timeout_and_keeps_partial_results(self) -> None:
        fake_engine = _FakeEngine()
        fake_doc = _FakeDoc(page_count=2)

        with patch("src.ocr.get_ocr_engine", return_value=fake_engine), patch(
            "src.ocr.fitz.open",
            return_value=fake_doc,
        ), patch(
            "src.ocr.time.perf_counter",
            side_effect=[0.0, 0.0, 2.0],
        ):
            results, runtime = ocr.run_ocr_on_pages(
                pdf_path=ocr.Path("sample.pdf"),
                page_indices=[0, 1],
                lang="ch",
                dpi=220,
                batch_size=1,
                timeout_seconds=1.0,
            )

        self.assertEqual(results, {0: "recognized text"})
        self.assertEqual(fake_engine.calls, 1)
        self.assertTrue(runtime["timed_out"])
        self.assertEqual(runtime["executed_pages"], 1)
        self.assertEqual(runtime["successful_pages"], 1)
        self.assertEqual(runtime["batch_count"], 1)


if __name__ == "__main__":
    unittest.main()
