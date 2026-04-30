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

    def test_build_ocr_process_summary_no_ocr_rounds(self):
        result = _build_ocr_process_summary([])
        self.assertFalse(result["是否触发OCR"])
        self.assertEqual(result["OCR调用次数"], 0)
        self.assertEqual(result["OCR完成页数"], 0)
        self.assertEqual(result["OCR目标页数累计"], 0)
        self.assertEqual(result["OCR识别成功页数累计"], 0)
        self.assertEqual(result["OCR总耗时秒"], 0.0)
        self.assertEqual(result["OCR失败原因列表"], [])
        self.assertEqual(result["OCR引擎"], "")
        self.assertEqual(result["OCR语言"], "")

    def test_build_ocr_process_summary_partial_completion(self):
        review_rounds = [{
            "轮次": 1.0,
            "OCR执行结果": {"timed_out": True},
            "OCR评估摘要": {
                "目标页数": "5",
                "识别成功页数": "2",
                "评估通过页数": "2",
                "边缘页数": "0",
                "拒绝页数": "3",
                "注入页码列表": [0, 1],
                "是否触发OCR": True,
                "OCR分辨率DPI": 200,
                "OCR引擎": "paddleocr",
                "OCR语言": "zh",
                "OCR总耗时秒": 120.0,
            },
        }]
        result = _build_ocr_process_summary(review_rounds)
        self.assertEqual(result["OCR目标页数累计"], 5)
        self.assertEqual(result["OCR识别成功页数累计"], 2)
        self.assertEqual(result["OCR完成页数"], 2)
        self.assertTrue(result["OCR部分完成"])
        self.assertAlmostEqual(result["OCR完成比例"], 0.4)

    def test_build_ocr_process_summary_multiple_rounds_aggregate(self):
        review_rounds = [
            {
                "轮次": 1.0,
                "OCR执行结果": {},
                "OCR评估摘要": {
                    "目标页数": "3", "识别成功页数": "3", "评估通过页数": "3",
                    "边缘页数": "0", "拒绝页数": "0", "注入页码列表": [0, 1, 2],
                    "是否触发OCR": True, "OCR分辨率DPI": 200,
                    "OCR引擎": "paddleocr", "OCR语言": "zh", "OCR总耗时秒": 60.0,
                },
            },
            {
                "轮次": 2.0,
                "OCR执行结果": {},
                "OCR评估摘要": {
                    "目标页数": "2", "识别成功页数": "1", "评估通过页数": "1",
                    "边缘页数": "1", "拒绝页数": "0", "注入页码列表": [0],
                    "是否触发OCR": True, "OCR分辨率DPI": 200,
                    "OCR引擎": "paddleocr", "OCR语言": "zh", "OCR总耗时秒": 40.0,
                },
            },
        ]
        result = _build_ocr_process_summary(review_rounds)
        self.assertEqual(result["OCR调用次数"], 2)
        self.assertEqual(result["OCR目标页数累计"], 5)
        self.assertEqual(result["OCR识别成功页数累计"], 4)
        self.assertEqual(result["OCR评估通过页数累计"], 4)
        self.assertEqual(result["OCR边缘页数累计"], 1)
        self.assertEqual(result["OCR实际注入页数累计"], 4)
        self.assertAlmostEqual(result["OCR总耗时秒"], 100.0)

    def test_build_ocr_process_summary_with_failure_reasons(self):
        review_rounds = [{
            "轮次": 1.0,
            "OCR执行结果": {"timed_out": True},
            "OCR评估摘要": {
                "目标页数": "3", "识别成功页数": "1", "评估通过页数": "1",
                "边缘页数": "0", "拒绝页数": "2", "注入页码列表": [0],
                "是否触发OCR": True, "OCR分辨率DPI": 200,
                "OCR引擎": "paddleocr", "OCR语言": "zh", "OCR总耗时秒": 180.0,
                "失败原因": "软超时提前停止",
            },
        }]
        result = _build_ocr_process_summary(review_rounds)
        self.assertIn("软超时提前停止", result["OCR失败原因列表"])
        self.assertEqual(len(result["OCR失败原因列表"]), 1)

    def test_build_ocr_process_summary_all_remaining_fields(self):
        review_rounds = [{
            "轮次": 1.0,
            "OCR执行结果": {"total_pages": 3, "engine_version": "2.7.1"},
            "OCR评估摘要": {
                "目标页数": "3", "识别成功页数": "3", "评估通过页数": "2",
                "边缘页数": "1", "拒绝页数": "0", "注入页码列表": [0, 1],
                "是否触发OCR": True, "OCR分辨率DPI": 300,
                "OCR引擎": "paddleocr", "OCR语言": "zh", "OCR总耗时秒": 90.0,
            },
        }]
        result = _build_ocr_process_summary(review_rounds)
        self.assertTrue(result["是否触发OCR"])
        self.assertEqual(result["OCR调用次数"], 1)
        self.assertEqual(result["OCR分辨率DPI"], 300)
        self.assertEqual(result["OCR目标页数累计"], 3)
        self.assertEqual(result["OCR识别成功页数累计"], 3)
        self.assertEqual(result["OCR评估通过页数累计"], 2)
        self.assertEqual(result["OCR边缘页数累计"], 1)
        self.assertEqual(result["OCR拒绝页数累计"], 0)
        self.assertEqual(result["OCR实际注入页数累计"], 2)
        self.assertEqual(result["OCR完成页数"], 3)
        self.assertFalse(result["OCR部分完成"])
        self.assertAlmostEqual(result["OCR完成比例"], 1.0)
        self.assertEqual(result["OCR总耗时秒"], 90.0)
        self.assertEqual(result["OCR引擎"], "paddleocr")
        self.assertEqual(result["OCR语言"], "zh")


if __name__ == "__main__":
    unittest.main()
