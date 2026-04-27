from __future__ import annotations

import unittest

from src.source_guard import (
    canonicalize_standard_code,
    detect_metadata_mismatch_reason,
    extract_canonical_standard_codes,
    strip_markdown_metadata,
)
from tests.helpers import build_sample_document


class CanonicalizeStandardCodeTests(unittest.TestCase):
    def test_full_four_digit_year(self):
        self.assertEqual(canonicalize_standard_code("GB/T 1234-2020"), "GB/T 1234-2020")

    def test_two_digit_year_above_80(self):
        self.assertEqual(canonicalize_standard_code("GB/T 1234-96"), "GB/T 1234-1996")

    def test_two_digit_year_below_80(self):
        self.assertEqual(canonicalize_standard_code("GB/T 1234-23"), "GB/T 1234-2023")

    def test_sub_committee_code(self):
        self.assertEqual(canonicalize_standard_code("CB/T 3945-2002"), "CB/T 3945-2002")

    def test_base_code_without_sub(self):
        self.assertEqual(canonicalize_standard_code("ISO 9001-2015"), "ISO 9001-2015")

    def test_din_code(self):
        self.assertEqual(canonicalize_standard_code("DIN 2501-2020"), "DIN 2501-2020")

    def test_code_with_various_separators(self):
        self.assertEqual(canonicalize_standard_code("CB 589-95"), "CB 589-1995")
        self.assertEqual(canonicalize_standard_code("CB 589—95"), "CB 589-1995")
        self.assertEqual(canonicalize_standard_code("CB 589_95"), "CB 589-1995")

    def test_no_match_returns_empty(self):
        self.assertEqual(canonicalize_standard_code("普通文本没有标准号"), "")

    def test_edge_empty_string(self):
        self.assertEqual(canonicalize_standard_code(""), "")

    def test_edge_single_word(self):
        self.assertEqual(canonicalize_standard_code("Hello"), "")


class ExtractCanonicalStandardCodesTests(unittest.TestCase):
    def test_extract_single_code(self):
        codes = extract_canonical_standard_codes("参照 GB/T 1234-2020 执行")
        self.assertIn("GB/T 1234-2020", codes)

    def test_extract_multiple_codes(self):
        codes = extract_canonical_standard_codes("涉及 GB/T 1234-2020 和 CB 589-95")
        self.assertIn("GB/T 1234-2020", codes)
        self.assertIn("CB 589-1995", codes)

    def test_extract_from_noise(self):
        codes = extract_canonical_standard_codes("无标准号文本")
        self.assertEqual(codes, set())


class StripMarkdownMetadataTests(unittest.TestCase):
    def test_strip_file_info_section(self):
        markdown = """# 标题
## 文件基础信息
文件名称：test.pdf
标准编号：GB/T 1234-2020
## 正文内容
这是正文。"""
        result = strip_markdown_metadata(markdown)
        self.assertNotIn("文件基础信息", result)
        self.assertNotIn("文件名称：test.pdf", result)
        self.assertIn("正文内容", result)
        self.assertIn("这是正文。", result)

    def test_no_file_info_preserves_all(self):
        markdown = "# 标题\n正文内容。"
        self.assertEqual(strip_markdown_metadata(markdown), markdown)

    def test_empty_markdown(self):
        self.assertEqual(strip_markdown_metadata(""), "")


class DetectMetadataMismatchReasonTests(unittest.TestCase):
    def test_no_mismatch_when_codes_match(self):
        doc = build_sample_document()
        doc.文件元数据.文件名称 = "GB/T 1234-2020 标准.pdf"
        markdown = "# 1 范围\n引用 GB/T 1234-2020"
        reason = detect_metadata_mismatch_reason(doc, markdown)
        self.assertEqual(reason, "")

    def test_no_mismatch_when_no_code_in_filename(self):
        doc = build_sample_document()
        doc.文件元数据.文件名称 = "普通文档.pdf"
        reason = detect_metadata_mismatch_reason(doc, "# 正文")
        self.assertEqual(reason, "")

    def test_mismatch_detected(self):
        doc = build_sample_document()
        doc.文件元数据.文件名称 = "GB/T 1234-2020 标准.pdf"
        # Remove standard refs that would match the expected code
        doc.引用标准列表 = []
        markdown = "引用 DIN 2501-2020"
        reason = detect_metadata_mismatch_reason(doc, markdown)
        self.assertIn("文件名预期标准号", reason)
        self.assertIn("GB/T 1234-2020", reason)
        self.assertIn("DIN 2501-2020", reason)

    def test_empty_filename(self):
        doc = build_sample_document()
        doc.文件元数据.文件名称 = ""
        self.assertEqual(detect_metadata_mismatch_reason(doc, "# text"), "")


if __name__ == "__main__":
    unittest.main()
