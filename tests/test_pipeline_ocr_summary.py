from __future__ import annotations

import unittest

from src.pipeline import _build_ocr_process_summary


class PipelineOcrSummaryTests(unittest.TestCase):
    def test_build_ocr_process_summary_uses_ocr_display_dpi_field(self) -> None:
        review_rounds = [
            {
                "OCR评估摘要": {
                    "OCR引擎": "paddleocr-3.4.1",
                    "OCR语言": "ch",
                    "OCR分辨率DPI": 220,
                    "目标页数": 3,
                    "识别成功页数": 2,
                    "评估通过页数": 1,
                    "边缘页数": 1,
                    "拒绝页数": 1,
                    "注入页码列表": [0, 2],
                    "OCR总耗时秒": 12.5,
                    "失败原因": "",
                }
            }
        ]

        summary = _build_ocr_process_summary(review_rounds)

        self.assertTrue(summary["是否触发OCR"])
        self.assertEqual(summary["OCR分辨率DPI"], 220)
        self.assertEqual(summary["OCR目标页数累计"], 3)
        self.assertEqual(summary["OCR实际注入页数累计"], 2)


if __name__ == "__main__":
    unittest.main()
