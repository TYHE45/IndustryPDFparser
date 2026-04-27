from __future__ import annotations

import unittest
from pathlib import Path

from config import AppConfig
from src.cleaner import LineCleaner, detect_repeated_noise


def _make_config(**kwargs) -> AppConfig:
    return AppConfig(
        input_path=Path("test.pdf"),
        output_dir=Path("out"),
        **kwargs,
    )


class LineCleanerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _make_config()
        self.cleaner = LineCleaner(self.config)

    def test_clean_lines_removes_empty(self):
        result = self.cleaner.clean_lines(["  ", "hello", "", "world"])
        self.assertEqual(result, ["hello", "world"])

    def test_clean_lines_removes_header_footer_page_number(self):
        result = self.cleaner.clean_lines(["正文", "3/15", "继续"])
        self.assertEqual(result, ["正文", "继续"])

    def test_clean_lines_removes_chinese_page_number(self):
        result = self.cleaner.clean_lines(["正文", "第 3 页", "继续"])
        self.assertEqual(result, ["正文", "继续"])

    def test_clean_lines_removes_english_page_number(self):
        result = self.cleaner.clean_lines(["正文", "Page 3", "继续"])
        self.assertEqual(result, ["正文", "继续"])

    def test_clean_lines_removes_full_page_format(self):
        result = self.cleaner.clean_lines(["正文", "Page 3 of 15", "继续"])
        self.assertEqual(result, ["正文", "继续"])

    def test_clean_lines_removes_skip_line_contains(self):
        result = self.cleaner.clean_lines([
            "正文",
            "未经书面许可不得复制本文档",
            "继续",
        ])
        self.assertEqual(result, ["正文", "继续"])

    def test_clean_lines_removes_repeated_noise(self):
        result = self.cleaner.clean_lines(
            ["正文", "标准分享网", "继续"],
            repeated_noise={"标准分享网"},
        )
        self.assertEqual(result, ["正文", "继续"])

    def test_clean_lines_preserves_normal_content(self):
        result = self.cleaner.clean_lines(["1 范围", "本标准适用于压力容器。"])
        self.assertEqual(result, ["1 范围", "本标准适用于压力容器。"])

    def test_clean_lines_normalizes_whitespace(self):
        result = self.cleaner.clean_lines(["  正文  内容  "])
        self.assertEqual(result, ["正文 内容"])

    def test_empty_input(self):
        result = self.cleaner.clean_lines([])
        self.assertEqual(result, [])

    def test_date_pattern_removed(self):
        config = _make_config(header_footer_patterns=(r"\d{4}[-/]\d{2}",))
        cleaner = LineCleaner(config)
        result = cleaner.clean_lines(["正文", "2024-01", "继续"])
        self.assertEqual(result, ["正文", "继续"])

    def test_skip_line_contains_multi_fragment(self):
        config = _make_config(skip_line_contains=(
            "商业网站",
            "版权所有",
        ))
        cleaner = LineCleaner(config)
        result = cleaner.clean_lines(["正文", "商业网站 17jzw", "版权所有 2024", "继续"])
        self.assertEqual(result, ["正文", "继续"])


class DetectRepeatedNoiseTests(unittest.TestCase):
    def test_detects_repeated_lines(self):
        lines = [
            [".", "内容A", "页眉"],
            ["内容B", "页眉"],
            ["内容C", "页眉"],
        ]
        noise = detect_repeated_noise(lines, min_repeat=2)
        self.assertIn("页眉", noise)

    def test_no_repeated_noise(self):
        lines = [
            ["唯一行A", "内容B"],
            ["唯一行C", "内容D"],
        ]
        noise = detect_repeated_noise(lines, min_repeat=2)
        self.assertEqual(noise, set())

    def test_long_lines_capped(self):
        lines = [
            ["A" * 60] * 6,
        ]
        noise = detect_repeated_noise(lines, min_repeat=2)
        self.assertNotIn("A" * 60, noise)

    def test_sn200_lines_included_even_when_long(self):
        # Each page has the line once, 6 pages total to exceed min_repeat
        long_line = "SN 200 标准" * 10  # > 50 chars
        pages = [[long_line] for _ in range(6)]
        noise = detect_repeated_noise(pages, min_repeat=2)
        self.assertTrue(noise)

    def test_empty_input(self):
        self.assertEqual(detect_repeated_noise([], min_repeat=2), set())

    def test_single_page_no_repeat(self):
        lines = [["内容A", "内容B"]]
        noise = detect_repeated_noise(lines, min_repeat=2)
        self.assertEqual(noise, set())


class LineCleanerGermanTests(unittest.TestCase):
    def test_german_page_format(self):
        result = LineCleaner(_make_config()).clean_lines(["正文", "Seite 5", "weiter"])
        self.assertEqual(result, ["正文", "weiter"])

    def test_german_date_pattern(self):
        config = _make_config(header_footer_patterns=(r"^\d{4}[-/]\d{2}$",))
        result = LineCleaner(config).clean_lines(["正文", "2024/01"])
        self.assertEqual(result, ["正文"])


if __name__ == "__main__":
    unittest.main()
