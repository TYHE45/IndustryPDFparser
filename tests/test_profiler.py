from __future__ import annotations

import unittest

from src.profiler import (
    inspect_text_layer,
    needs_ocr_by_text_layer,
    profile_document,
)


class InspectTextLayerTests(unittest.TestCase):
    def test_empty_lines(self):
        metrics = inspect_text_layer([])
        self.assertEqual(metrics["char_count"], 0)
        self.assertEqual(metrics["content_line_count"], 0)

    def test_normal_text(self):
        lines = ["这是第一行正文内容", "这是第二行正文内容", "GB/T 1234-2020"]
        metrics = inspect_text_layer(lines)
        self.assertGreater(metrics["char_count"], 0)
        self.assertGreater(metrics["quality_ratio"], 0.5)
        self.assertGreater(metrics["structural_signal_count"], 0)

    def test_advertisement_detection(self):
        lines = [
            "免费下载标准上标准分享网",
            "www.bzfxw.com 免费下载",
            "道客巴巴文档分享",
        ]
        metrics = inspect_text_layer(lines)
        self.assertGreater(metrics["advertisement_line_count"], 0)

    def test_metadata_heavy(self):
        lines = [
            "备案号：12345-2020",
            "邮政编码：100000",
            "电话：010-12345678",
            "地址：北京市",
            "出版：中国标准出版社",
            "定价：20.00元",
            "ISBN：978-7-1234-5678-9",
        ]
        metrics = inspect_text_layer(lines)
        self.assertGreater(metrics["metadata_line_count"], 0)
        self.assertEqual(metrics["structural_signal_count"], 0)


class NeedsOcrByTextLayerTests(unittest.TestCase):
    def test_high_quality_text_no_ocr(self):
        lines = [
            "1 范围",
            "本标准规定了产品的技术要求。",
            "2 规范性引用文件",
            "GB/T 1234-2020 引用标准",
            "3 术语和定义",
            "下列术语适用于本标准。",
        ]
        needs_ocr, reasons, _ = needs_ocr_by_text_layer(lines, page_count=1)
        self.assertFalse(needs_ocr)
        self.assertEqual(reasons, [])

    def test_low_text_chars_triggers_ocr(self):
        lines = ["短"]
        needs_ocr, reasons, _ = needs_ocr_by_text_layer(lines, page_count=1, min_chars=60)
        self.assertTrue(needs_ocr)
        self.assertIn("low_text_chars", reasons)

    def test_watermark_only_triggers_ocr(self):
        lines = ["www.bzfxw.com 免费下载", "标准分享网"]
        needs_ocr, reasons, _ = needs_ocr_by_text_layer(lines, page_count=1)
        self.assertTrue(needs_ocr)

    def test_advertisement_without_structure(self):
        lines = ["免费下载" for _ in range(10)]
        needs_ocr, reasons, _ = needs_ocr_by_text_layer(lines, page_count=1)
        self.assertTrue(needs_ocr)

    def test_empty_lines(self):
        needs_ocr, reasons, _ = needs_ocr_by_text_layer([], page_count=1)
        self.assertTrue(needs_ocr)
        self.assertIn("low_text_chars", reasons)


class ProfileDocumentTests(unittest.TestCase):
    def test_standard_doc_classification(self):
        pages = [
            {"lines": [
                "1 范围",
                "本标准适用于压力容器。",
                "2 规范性引用文件",
                "下列文件中的条款通过本标准的引用而成为本标准的条款。",
                "GB/T 1234-2020 基础标准",
                "GB/T 5678-2020 试验方法",
                "DIN 2501-2020 法兰标准",
                "ISO 9001-2015 质量体系",
                "3 术语和定义",
                "3.1 公称压力",
                "3.2 工作温度",
                "Part 1 通用要求",
            ]}
        ]
        profile = profile_document("test.pdf", pages, {})
        self.assertEqual(profile.文档类型, "standard")
        self.assertGreater(profile.置信度, 0.5)

    def test_product_catalog_classification(self):
        pages = [
            {"lines": [
                "产品型号 XYZ-100",
                "型号 ABC-200",
                "型号 DEF-300",
                "系列 A 规格说明",
                "系列 B 规格说明",
                "订货号 001",
                "选型参数",
                "型号 GHI-400",
                "型号 JKL-500",
                "型号 MNO-600",
            ]}
        ]
        page_tables = {0: [[["参数", "值"], ["压力", "10"]]]}
        profile = profile_document("catalog.pdf", pages, page_tables)
        self.assertEqual(profile.文档类型, "product_catalog")

    def test_manual_classification(self):
        pages = [
            {"lines": [
                "安装步骤",
                "操作说明",
                "维护保养",
                "警告：高压危险",
                "注意事项",
                "caution: hot surface",
            ]}
        ]
        profile = profile_document("manual.pdf", pages, {})
        self.assertEqual(profile.文档类型, "manual")

    def test_report_classification(self):
        pages = [
            {"lines": [
                "检验报告",
                "测试结果",
                "certificate of analysis",
                "inspection record",
            ]}
        ]
        profile = profile_document("report.pdf", pages, {})
        self.assertEqual(profile.文档类型, "report")

    def test_unknown_classification(self):
        pages = [{"lines": ["一些普通文本", "没有明显特征"]}]
        profile = profile_document("unknown.pdf", pages, {})
        self.assertEqual(profile.文档类型, "unknown")

    def test_empty_pages(self):
        profile = profile_document("empty.pdf", [], {})
        self.assertEqual(profile.文档类型, "unknown")

    def test_scan_like_triggers_ocr_flag(self):
        pages = [{"lines": ["www.watermark.com"]}]
        profile = profile_document("scan.pdf", pages, {})
        self.assertTrue(profile.是否需要OCR)

    def test_confidence_capped_at_98(self):
        pages = [
            {"lines": [
                f"1 范围 第{i}部分 GB/T {i}-2020" for i in range(1, 50)
            ]}
        ]
        profile = profile_document("highconf.pdf", pages, {})
        self.assertLessEqual(profile.置信度, 0.98)


class InspectTextLayerEdgeCaseTests(unittest.TestCase):
    def test_german_detection(self):
        lines = ["Maße und Toleranzen", "Werkstoff: Stahl", "Prüfung nach DIN"]
        metrics = inspect_text_layer(lines)
        self.assertGreater(metrics["char_count"], 0)

    def test_english_detection(self):
        lines = ["The application dimensions", "for standard requirements", "and inspection"]
        metrics = inspect_text_layer(lines)
        self.assertGreater(metrics["char_count"], 0)


if __name__ == "__main__":
    unittest.main()
