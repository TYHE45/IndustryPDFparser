from __future__ import annotations

import unittest
from pathlib import Path

from config import AppConfig
from src.context import PipelineContext
from src.models import DocumentProfile, SectionRecord
from src.parser import PDFParser  # alias for UniversalPDFParser


# ---------------------------------------------------------------------------
# 1. HeadingClassificationTests
# ---------------------------------------------------------------------------

class HeadingClassificationTests(unittest.TestCase):
    """标题分类相关静态/纯函数测试 (~30 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _looks_like_part_heading ──────────────────────────────────────

    def test_part_heading_english(self) -> None:
        self.assertTrue(self.parser._looks_like_part_heading("Part 1"))

    def test_part_heading_english_general_overview(self) -> None:
        self.assertTrue(self.parser._looks_like_part_heading("Part 1: General"))

    def test_part_heading_german(self) -> None:
        self.assertTrue(self.parser._looks_like_part_heading("Teil 2"))

    def test_part_heading_chinese(self) -> None:
        self.assertTrue(self.parser._looks_like_part_heading("第 1 部分"))

    def test_part_heading_chinese_with_extra_spaces(self) -> None:
        self.assertTrue(self.parser._looks_like_part_heading("第  3  部分"))

    def test_part_heading_non_part_line(self) -> None:
        self.assertFalse(self.parser._looks_like_part_heading("Introduction"))

    def test_part_heading_normal_numbered_heading(self) -> None:
        self.assertFalse(self.parser._looks_like_part_heading("1 Scope"))

    # ── _looks_like_heading_fragment ──────────────────────────────────

    def test_heading_fragment_short_allcaps_token(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("DIN"))

    def test_heading_fragment_value_like(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("100"))

    def test_heading_fragment_negative_value(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("-5"))

    def test_heading_fragment_leading_conjunction(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("and material"))

    def test_heading_fragment_lowercase_start(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("must be tested"))

    def test_heading_fragment_punctuation_ending(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading_fragment("The standard applies.")
        )

    def test_heading_fragment_unbalanced_parens(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("Material (see note"))

    def test_heading_fragment_sentence_verb_multiword(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading_fragment("the value is calculated from")
        )

    def test_heading_fragment_section_number_only(self) -> None:
        self.assertTrue(self.parser._looks_like_heading_fragment("3.2"))

    def test_heading_fragment_normal_heading_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_heading_fragment("Scope"))

    def test_heading_fragment_material_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_heading_fragment("Material"))

    # ── _looks_like_ocr_noise_heading ─────────────────────────────────

    def test_ocr_noise_high_digit_count_with_spec(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading("PN 16 DN 100 20 mm 5")
        )

    def test_ocr_noise_digits_with_data_cue(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading("12345 为 67890 公称尺寸")
        )

    def test_ocr_noise_long_text_with_data_cue_and_digits(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading("这是长达18个字符以上的文本内容，包括一些数据 12 mm 规格")
        )

    def test_ocr_noise_compact_with_multiple_specs(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading("PN16 DN100 20mm")
        )

    def test_ocr_noise_leading_numeric_cjk_glue(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading("100公称通径")
        )

    def test_ocr_noise_leading_numeric_cjk_glue_compare(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading("≤5壁厚")
        )

    def test_ocr_noise_sentence_cues_with_data(self) -> None:
        self.assertTrue(
            self.parser._looks_like_ocr_noise_heading(
                "必须按照规格尺寸12mm进行检验"
            )
        )

    def test_ocr_noise_clean_heading_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_ocr_noise_heading("Scope"))

    def test_ocr_noise_short_text_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_ocr_noise_heading("12 mm"))

    def test_ocr_noise_low_digit_text_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_ocr_noise_heading("Material requirements")
        )

    # ── _looks_like_ocr_fragment_heading ──────────────────────────────

    def test_ocr_fragment_unit_only(self) -> None:
        self.assertTrue(self.parser._looks_like_ocr_fragment_heading("mm"))

    def test_ocr_fragment_unit_with_parens(self) -> None:
        self.assertTrue(self.parser._looks_like_ocr_fragment_heading("(mm)"))

    def test_ocr_fragment_letter_marker(self) -> None:
        self.assertTrue(self.parser._looks_like_ocr_fragment_heading("a)"))

    def test_ocr_fragment_punctuation_ending_cjk(self) -> None:
        self.assertTrue(self.parser._looks_like_ocr_fragment_heading("尺寸。"))

    def test_ocr_fragment_short_compact_non_cjk(self) -> None:
        self.assertTrue(self.parser._looks_like_ocr_fragment_heading("ab"))

    def test_ocr_fragment_no_letters_or_cjk(self) -> None:
        self.assertTrue(self.parser._looks_like_ocr_fragment_heading("12.5"))

    def test_ocr_fragment_normal_heading_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_ocr_fragment_heading("Scope"))

    def test_ocr_fragment_short_cjk_heading_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_ocr_fragment_heading("范围"))

    # ── _looks_like_number_noise_heading ──────────────────────────────

    def test_number_noise_deep_numbering(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("1.2.3", "Detail")
        )

    def test_number_noise_x_dot_zero_pairs(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("15.0", "Value")
        )

    def test_number_noise_four_plus_digit_plain(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("1234", "Item")
        )

    def test_number_noise_footnote_marker(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("1)", "Note")
        )

    def test_number_noise_model_code_in_title(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("74", "M27X1.5 thread")
        )

    def test_number_noise_shape_d_deep(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("1.2.3", "shape d")
        )

    def test_number_noise_zero_number(self) -> None:
        self.assertTrue(
            self.parser._looks_like_number_noise_heading("0", "Introduction")
        )

    def test_number_noise_normal_number_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_number_noise_heading("1", "Scope")
        )

    def test_number_noise_two_level_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_number_noise_heading("1.1", "General")
        )

    # ── _looks_like_heading (full method) ─────────────────────────────

    @staticmethod
    def _make_profile(lang: str = "en") -> DocumentProfile:
        return DocumentProfile(语言=lang)

    def _heading_kwargs(
        self,
        prev_line: str = "",
        next_line: str = "",
        lang: str = "en",
        page_ocr_used: bool = False,
        page_ocr_fragmented: bool = False,
    ) -> dict:
        return {
            "prev_line": prev_line,
            "next_line": next_line,
            "profile": self._make_profile(lang),
            "page_table_cells": set(),
            "page_ocr_used": page_ocr_used,
            "page_ocr_fragmented": page_ocr_fragmented,
        }

    def test_heading_numbered(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "1 Scope", **self._heading_kwargs()
            )
        )

    def test_heading_numbered_multilevel(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "1.1 General requirements", **self._heading_kwargs()
            )
        )

    def test_heading_generic_short(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "Requirements", **self._heading_kwargs()
            )
        )

    def test_heading_generic_short_scope(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "Application scope", **self._heading_kwargs()
            )
        )

    def test_heading_colon_ending(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "Material:", **self._heading_kwargs()
            )
        )

    def test_heading_colon_chinese_ending(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "材料：", **self._heading_kwargs(lang="unknown")
            )
        )

    def test_heading_short_next_long(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "Scope",
                **self._heading_kwargs(
                    next_line="This standard defines the requirements for pressure vessels"
                )
            )
        )

    def test_heading_en_uppercase(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "DIMENSIONS AND TOLERANCES", **self._heading_kwargs(lang="en")
            )
        )

    def test_heading_de_uppercase(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "ANWENDUNGSBEREICH", **self._heading_kwargs(lang="de")
            )
        )

    def test_heading_noise_exclusion_standard_line(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "DIN 1234", **self._heading_kwargs()
            )
        )

    def test_heading_noise_exclusion_ics(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "ICS 91.100", **self._heading_kwargs()
            )
        )

    def test_heading_noise_exclusion_caption(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "Table 1 Dimensions", **self._heading_kwargs()
            )
        )

    def test_heading_banned_exact_mm(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "mm", **self._heading_kwargs()
            )
        )

    def test_heading_banned_exact_bar(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "bar", **self._heading_kwargs()
            )
        )

    def test_heading_ocr_fragment_excluded(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "a)", **self._heading_kwargs(page_ocr_used=True)
            )
        )

    def test_heading_form_shape_pattern(self) -> None:
        self.assertTrue(
            self.parser._looks_like_heading(
                "Form A", **self._heading_kwargs()
            )
        )

    def test_heading_too_long(self) -> None:
        self.assertFalse(
            self.parser._looks_like_heading(
                "A" * 101, **self._heading_kwargs()
            )
        )


# ---------------------------------------------------------------------------
# 2. TableDetectionTests
# ---------------------------------------------------------------------------

class TableDetectionTests(unittest.TestCase):
    """表格检测相关方法测试 (~16 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _looks_like_table_fragment ────────────────────────────────────

    def test_table_fragment_exact_cell_match(self) -> None:
        cells = {"DN 100", "PN 16", "12.5 mm"}
        for cell in cells:
            with self.subTest(cell=cell):
                self.assertTrue(
                    self.parser._looks_like_table_fragment(cell, cells)
                )

    def test_table_fragment_noise_marker(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("bearbeitet:", set())
        )

    def test_table_fragment_dotted_leading(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("type-", set())
        )

    def test_table_fragment_conjunction_leading(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("and requirements", set())
        )

    def test_table_fragment_short_token(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("DN", set())
        )

    def test_table_fragment_value_fragment(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("42.5", set())
        )

    def test_table_fragment_digit_density_three_digits_short_text(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("1 2 3", set())
        )

    def test_table_fragment_footnote_marker(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("3)", set())
        )

    def test_table_fragment_table_header_fragment(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("pressure", set())
        )

    def test_table_fragment_header_value(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("weight", set())
        )

    def test_table_fragment_dn_with_multiple_tokens(self) -> None:
        self.assertTrue(
            self.parser._looks_like_table_fragment("DN 100 PN 16", set())
        )

    def test_table_fragment_normal_text_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_table_fragment(
                "This standard specifies requirements", set()
            )
        )

    def test_table_fragment_empty_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_table_fragment("   ", set())
        )

    # ── _looks_like_caption ───────────────────────────────────────────

    def test_caption_table_chinese(self) -> None:
        self.assertTrue(self.parser._looks_like_caption("表 1 尺寸"))

    def test_caption_figure_english(self) -> None:
        self.assertTrue(self.parser._looks_like_caption("Figure 1 Overview"))

    def test_caption_figure_abbreviated(self) -> None:
        self.assertTrue(self.parser._looks_like_caption("Fig. 2 Layout"))

    def test_caption_ordinary_text(self) -> None:
        self.assertFalse(self.parser._looks_like_caption("General requirements"))

    def test_caption_normal_text_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_caption("Dimensions"))

    # ── _looks_like_toc_line ──────────────────────────────────────────

    def test_toc_line_dot_leader(self) -> None:
        self.assertTrue(
            self.parser._looks_like_toc_line("Introduction ........... 3")
        )

    def test_toc_line_ellipsis_leader(self) -> None:
        self.assertTrue(
            self.parser._looks_like_toc_line("Scope …………… 5")
        )

    def test_toc_line_contents_keyword(self) -> None:
        self.assertTrue(self.parser._looks_like_toc_line("Contents"))

    def test_toc_line_inhalt_keyword(self) -> None:
        self.assertTrue(self.parser._looks_like_toc_line("Inhalt"))

    def test_toc_line_chinese_keyword(self) -> None:
        self.assertTrue(self.parser._looks_like_toc_line("目录"))

    def test_toc_line_normal_line_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_toc_line("1 Scope")
        )

    def test_toc_line_empty_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_toc_line(""))


# ---------------------------------------------------------------------------
# 3. StandardAndContextTests
# ---------------------------------------------------------------------------

class StandardAndContextTests(unittest.TestCase):
    """标准识别和上下文相关方法测试 (~10 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _looks_like_standard_line ─────────────────────────────────────

    def test_standard_line_din(self) -> None:
        self.assertTrue(self.parser._looks_like_standard_line("DIN 1234"))

    def test_standard_line_en(self) -> None:
        self.assertTrue(self.parser._looks_like_standard_line("EN 4567"))

    def test_standard_line_iso(self) -> None:
        self.assertTrue(self.parser._looks_like_standard_line("ISO 9001"))

    def test_standard_line_gb(self) -> None:
        self.assertTrue(self.parser._looks_like_standard_line("GB/T 1"))

    def test_standard_line_numbered_heading_containing_standard_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_standard_line("1 DIN 1234 Scope")
        )

    def test_standard_line_normal_text_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_standard_line("Scope"))

    # ── _looks_like_metadata_line ─────────────────────────────────────

    def test_metadata_line_ics(self) -> None:
        self.assertTrue(self.parser._looks_like_metadata_line("ICS 91.100"))

    def test_metadata_line_date(self) -> None:
        self.assertTrue(
            self.parser._looks_like_metadata_line("2024-01-15")
        )

    def test_metadata_line_classification(self) -> None:
        self.assertTrue(
            self.parser._looks_like_metadata_line("分类号 U 23")
        )

    def test_metadata_line_implementation_date(self) -> None:
        self.assertTrue(
            self.parser._looks_like_metadata_line("实施 2024-01-01")
        )

    def test_metadata_line_normal_text_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_metadata_line("Scope"))

    def test_metadata_line_empty_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_metadata_line(""))

    # ── _looks_like_front_matter_context ──────────────────────────────

    def test_front_matter_qianyan(self) -> None:
        self.assertTrue(
            self.parser._looks_like_front_matter_context("前言")
        )

    def test_front_matter_isbn(self) -> None:
        self.assertTrue(
            self.parser._looks_like_front_matter_context("ISBN 978-7-5026")
        )

    def test_front_matter_copyright(self) -> None:
        self.assertTrue(
            self.parser._looks_like_front_matter_context("版权 2024")
        )

    def test_front_matter_multi_part(self) -> None:
        self.assertTrue(
            self.parser._looks_like_front_matter_context("前言", "文件基础信息")
        )

    def test_front_matter_pricing(self) -> None:
        self.assertTrue(
            self.parser._looks_like_front_matter_context("定价 120 元")
        )

    def test_front_matter_normal_text_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_front_matter_context("1 Scope")
        )

    def test_front_matter_empty_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_front_matter_context(""))


# ---------------------------------------------------------------------------
# 4. ValueUnitDetectionTests
# ---------------------------------------------------------------------------

class ValueUnitDetectionTests(unittest.TestCase):
    """数值和单位检测方法测试 (~12 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _looks_like_unit_token ────────────────────────────────────────

    def test_unit_token_mm(self) -> None:
        self.assertTrue(self.parser._looks_like_unit_token("mm"))

    def test_unit_token_bar(self) -> None:
        self.assertTrue(self.parser._looks_like_unit_token("bar"))

    def test_unit_token_kn_per_m2(self) -> None:
        self.assertTrue(self.parser._looks_like_unit_token("kN/m2"))

    def test_unit_token_celsius(self) -> None:
        self.assertTrue(self.parser._looks_like_unit_token("°C"))

    def test_unit_token_percent(self) -> None:
        self.assertTrue(self.parser._looks_like_unit_token("%"))

    def test_unit_token_normal_word_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_unit_token("scope"))

    def test_unit_token_empty_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_unit_token(""))

    # ── _looks_like_value ─────────────────────────────────────────────

    def test_value_range(self) -> None:
        self.assertTrue(self.parser._looks_like_value("10-20 mm"))

    def test_value_range_with_to(self) -> None:
        self.assertTrue(self.parser._looks_like_value("5 to 10 mm"))

    def test_value_compare(self) -> None:
        self.assertTrue(self.parser._looks_like_value("≤ 5"))

    def test_value_dimension(self) -> None:
        self.assertTrue(self.parser._looks_like_value("400x300"))

    def test_value_pure_numeric(self) -> None:
        self.assertTrue(self.parser._looks_like_value("42.5"))

    def test_value_negative(self) -> None:
        self.assertTrue(self.parser._looks_like_value("-10"))

    def test_value_with_unit_only(self) -> None:
        self.assertTrue(self.parser._looks_like_value("100 mm"))

    def test_value_normal_sentence_passes(self) -> None:
        self.assertFalse(
            self.parser._looks_like_value("This is a sentence.")
        )

    def test_value_empty_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_value(""))

    def test_value_date_passes(self) -> None:
        self.assertFalse(self.parser._looks_like_value("2024-01-15"))

    # ── _contains_banned_substring ────────────────────────────────────

    def test_banned_substring_date(self) -> None:
        self.assertTrue(
            self.parser._contains_banned_substring("Published 2024-01-15")
        )

    def test_banned_substring_standard_code(self) -> None:
        self.assertTrue(
            self.parser._contains_banned_substring("DIN 1234 requirements")
        )

    def test_banned_substring_clean_text_passes(self) -> None:
        self.assertFalse(self.parser._contains_banned_substring("Pressure 10 bar"))

    def test_banned_substring_empty_passes(self) -> None:
        self.assertFalse(self.parser._contains_banned_substring(""))


# ---------------------------------------------------------------------------
# 5. OcrPageFragmentTests
# ---------------------------------------------------------------------------

class OcrPageFragmentTests(unittest.TestCase):
    """OCR 页面碎片化判断测试 (~5 tests)"""

    def setUp(self) -> None:
        self.context = PipelineContext(
            ocr_page_evaluations={
                0: {
                    "是否注入解析": True,
                    "单字符碎片率": 0.25,
                    "重复行率": 0.05,
                    "标点噪音率": 0.15,
                    "评估等级": "警告",
                    "判定原因": ["碎片化特征命中"],
                },
                1: {"是否注入解析": False},
                2: {
                    "是否注入解析": True,
                    "单字符碎片率": 0.10,
                    "重复行率": 0.10,
                    "标点噪音率": 0.10,
                    "评估等级": "通过",
                    "判定原因": [],
                },
                3: {
                    "是否注入解析": True,
                    "单字符碎片率": 0.05,
                    "重复行率": 0.05,
                    "标点噪音率": 0.05,
                    "评估等级": "边缘",
                    "判定原因": [],
                },
            }
        )
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output")),
            context=self.context,
        )

    def test_fragmented_no_evaluation(self) -> None:
        self.assertFalse(self.parser._is_fragmented_ocr_page(99))

    def test_fragmented_not_injected(self) -> None:
        self.assertFalse(self.parser._is_fragmented_ocr_page(1))

    def test_fragmented_high_fragment_rate(self) -> None:
        self.assertTrue(self.parser._is_fragmented_ocr_page(0))

    def test_fragmented_edge_grade(self) -> None:
        self.assertTrue(self.parser._is_fragmented_ocr_page(3))

    def test_fragmented_fragment_reason(self) -> None:
        self.assertTrue(self.parser._is_fragmented_ocr_page(0))

    def test_fragmented_clean_page_passes(self) -> None:
        self.assertFalse(self.parser._is_fragmented_ocr_page(2))


# ---------------------------------------------------------------------------
# 6. StringTransformTests
# ---------------------------------------------------------------------------

class StringTransformTests(unittest.TestCase):
    """字符串转换和规范化方法测试 (~17 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _strip_heading_noise_prefix ───────────────────────────────────

    def test_strip_date_prefix(self) -> None:
        self.assertEqual(
            self.parser._strip_heading_noise_prefix("12.06.24 Shape A"),
            "Shape A",
        )

    def test_strip_numeric_prefix(self) -> None:
        self.assertEqual(
            self.parser._strip_heading_noise_prefix("1234 Admissible length deviation"),
            "Admissible length deviation",
        )

    def test_strip_normal_pass_through(self) -> None:
        self.assertEqual(
            self.parser._strip_heading_noise_prefix("1 Scope"),
            "1 Scope",
        )

    def test_strip_empty_pass_through(self) -> None:
        self.assertEqual(
            self.parser._strip_heading_noise_prefix(""),
            "",
        )

    # ── _classify_standard_family ─────────────────────────────────────

    def test_classify_din_en_iso(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("DIN EN ISO 1234"), "DIN EN ISO"
        )

    def test_classify_din_iso(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("DIN ISO 5678"), "DIN ISO"
        )

    def test_classify_din_en(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("DIN EN 9012"), "DIN EN"
        )

    def test_classify_din(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("DIN 1234"), "DIN"
        )

    def test_classify_en(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("EN 4567"), "EN"
        )

    def test_classify_gb(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("GB/T 1"), "GB"
        )

    def test_classify_chinese_industry(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("JB/T 1234"), "JB"
        )

    def test_classify_unknown_prefix(self) -> None:
        self.assertEqual(
            self.parser._classify_standard_family("XYZ 9999"), "其他"
        )

    # ── _normalize_unit ───────────────────────────────────────────────

    def test_normalize_unit_micron_mu(self) -> None:
        self.assertEqual(self.parser._normalize_unit("μm"), "μm")

    def test_normalize_unit_micron_micro_sign(self) -> None:
        self.assertEqual(self.parser._normalize_unit("µm"), "μm")

    def test_normalize_unit_micron_um(self) -> None:
        self.assertEqual(self.parser._normalize_unit("um"), "μm")

    def test_normalize_unit_kn_per_m2(self) -> None:
        self.assertEqual(self.parser._normalize_unit("kN/m2"), "kN/m2")

    def test_normalize_unit_n_per_mm2(self) -> None:
        self.assertEqual(self.parser._normalize_unit("N/mm2"), "N/mm2")

    def test_normalize_unit_unknown_pass_through(self) -> None:
        self.assertEqual(self.parser._normalize_unit("m/s"), "m/s")

    # ── _infer_unit_from_context ──────────────────────────────────────

    def test_infer_unit_mm(self) -> None:
        self.assertEqual(self.parser._infer_unit_from_context("10 mm"), "mm")

    def test_infer_unit_bar(self) -> None:
        self.assertEqual(self.parser._infer_unit_from_context("5 bar"), "bar")

    def test_infer_unit_k_per_m2(self) -> None:
        self.assertEqual(self.parser._infer_unit_from_context("100 kN/m2"), "kN/m2")

    def test_infer_unit_no_unit(self) -> None:
        self.assertEqual(self.parser._infer_unit_from_context("just text"), "")

    def test_infer_unit_empty(self) -> None:
        self.assertEqual(self.parser._infer_unit_from_context(""), "")


# ---------------------------------------------------------------------------
# 7. ParameterNameTests
# ---------------------------------------------------------------------------

class ParameterNameTests(unittest.TestCase):
    """参数名称规范化方法测试 (~13 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _canonicalize_parameter_name ──────────────────────────────────

    def test_canonicalize_weight(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("weight"), "重量"
        )

    def test_canonicalize_gewicht(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("Gewicht"), "重量"
        )

    def test_canonicalize_length(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("length"), "长度"
        )

    def test_canonicalize_laenge(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("Länge"), "长度"
        )

    def test_canonicalize_width(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("width"), "宽度"
        )

    def test_canonicalize_height(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("height"), "高度"
        )

    def test_canonicalize_diameter_returns_text(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("diameter"), "diameter"
        )

    def test_canonicalize_pressure(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("pressure"), "压力"
        )

    def test_canonicalize_temperature(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("temperature"), "温度"
        )

    def test_canonicalize_thickness(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("thickness"), "厚度"
        )

    def test_canonicalize_no_match_returns_original(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("CustomParam"), "CustomParam"
        )

    def test_canonicalize_long_text_truncated(self) -> None:
        long_name = "A" * 41
        self.assertEqual(
            self.parser._canonicalize_parameter_name(long_name), ""
        )

    def test_canonicalize_context_assisted(self) -> None:
        self.assertEqual(
            self.parser._canonicalize_parameter_name("wt", "weight table"),
            "重量",
        )

    # ── _guess_name_from_previous_line ────────────────────────────────

    def test_guess_name_clean_short_line(self) -> None:
        self.assertEqual(
            self.parser._guess_name_from_previous_line("Wall thickness"), "Wall thickness"
        )

    def test_guess_name_empty(self) -> None:
        self.assertEqual(self.parser._guess_name_from_previous_line(""), "")

    def test_guess_name_value_like(self) -> None:
        self.assertEqual(self.parser._guess_name_from_previous_line("10 mm"), "")

    def test_guess_name_too_long(self) -> None:
        long_line = "A" * 41
        self.assertEqual(
            self.parser._guess_name_from_previous_line(long_line), ""
        )

    # ── _pick_row_label ───────────────────────────────────────────────

    def test_pick_row_label_first_non_excluded(self) -> None:
        self.assertEqual(
            self.parser._pick_row_label(
                ["Total weight", "100", "kg"], model_columns=[], unit_col=2
            ),
            "Total weight",
        )

    def test_pick_row_label_skips_model_column(self) -> None:
        self.assertEqual(
            self.parser._pick_row_label(
                ["M27X1.5", "Total weight", "100"],
                model_columns=[(0, "M27X1.5")],
                unit_col=None,
            ),
            "Total weight",
        )

    def test_pick_row_label_all_excluded(self) -> None:
        self.assertEqual(
            self.parser._pick_row_label(
                ["100", "200"], model_columns=[], unit_col=None
            ),
            "",
        )

    def test_pick_row_label_empty_row(self) -> None:
        self.assertEqual(
            self.parser._pick_row_label([], model_columns=[], unit_col=None), ""
        )


# ---------------------------------------------------------------------------
# 8. TableStructureTests
# ---------------------------------------------------------------------------

class TableStructureTests(unittest.TestCase):
    """表格结构解析方法测试 (~10 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _split_table_header_body ──────────────────────────────────────

    def test_split_two_plus_rows(self) -> None:
        header, body = self.parser._split_table_header_body(
            [["Name", "Value", "Unit"], ["A", "10", "mm"], ["B", "20", "mm"]]
        )
        self.assertEqual(header, ["Name", "Value", "Unit"])
        self.assertEqual(body, [["A", "10", "mm"], ["B", "20", "mm"]])

    def test_split_one_row(self) -> None:
        header, body = self.parser._split_table_header_body(
            [["Name", "Value", "Unit"]]
        )
        self.assertEqual(header, ["Name", "Value", "Unit"])
        self.assertEqual(body, [])

    def test_split_empty(self) -> None:
        header, body = self.parser._split_table_header_body([])
        self.assertEqual(header, [])
        self.assertEqual(body, [])

    # ── _find_unit_column ─────────────────────────────────────────────

    def test_find_unit_column_mm(self) -> None:
        self.assertEqual(
            self.parser._find_unit_column(["Name", "Value", "mm"]), 2
        )

    def test_find_unit_column_bar(self) -> None:
        self.assertEqual(
            self.parser._find_unit_column(["Name", "bar", "Value"]), 1
        )

    def test_find_unit_column_not_found(self) -> None:
        self.assertIsNone(
            self.parser._find_unit_column(["Name", "Value", "Description"])
        )

    def test_find_unit_column_empty(self) -> None:
        self.assertIsNone(self.parser._find_unit_column([]))

    # ── _find_model_columns ───────────────────────────────────────────

    def test_find_model_columns_in_header(self) -> None:
        result = self.parser._find_model_columns(
            ["Name", "M27X1.5", "M39X2"], []
        )
        self.assertEqual(len(result), 2)
        self.assertIn((1, "M27X1"), result)
        self.assertIn((2, "M39X2"), result)

    def test_find_model_columns_in_body(self) -> None:
        result = self.parser._find_model_columns(
            ["Name", "Col1", "Col2"],
            [["Weight", "M27X1.5", "M39X2"]],
        )
        self.assertEqual(len(result), 2)

    def test_find_model_columns_none(self) -> None:
        result = self.parser._find_model_columns(
            ["Name", "Value", "Unit"], [["A", "10", "mm"]]
        )
        self.assertEqual(result, [])

    def test_find_model_columns_all_empty(self) -> None:
        result = self.parser._find_model_columns([], [])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# 9. LineProcessingTests
# ---------------------------------------------------------------------------

class LineProcessingTests(unittest.TestCase):
    """文本行处理方法测试 (~16 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _dedupe_lines ─────────────────────────────────────────────────

    def test_dedupe_removes_duplicates(self) -> None:
        result = self.parser._dedupe_lines(["a", "b", "a", "c", "b"])
        self.assertEqual(result, ["a", "b", "c"])

    def test_dedupe_preserves_order(self) -> None:
        result = self.parser._dedupe_lines(["c", "b", "a"])
        self.assertEqual(result, ["c", "b", "a"])

    def test_dedupe_empty_list(self) -> None:
        result = self.parser._dedupe_lines([])
        self.assertEqual(result, [])

    def test_dedupe_all_duplicates(self) -> None:
        result = self.parser._dedupe_lines(["x", "x", "x"])
        self.assertEqual(result, ["x"])

    def test_dedupe_whitespace_only_skipped(self) -> None:
        result = self.parser._dedupe_lines(["a", "   ", "b"])
        self.assertEqual(result, ["a", "b"])

    # ── _append_line ──────────────────────────────────────────────────

    def test_append_first_line(self) -> None:
        result = self.parser._append_line("", "First line")
        self.assertEqual(result, "First line")

    def test_append_second_line(self) -> None:
        result = self.parser._append_line("First line", "Second line")
        self.assertEqual(result, "First line\nSecond line")

    def test_append_skips_duplicate_last_line(self) -> None:
        result = self.parser._append_line("Line one", "Line one")
        self.assertEqual(result, "Line one")

    def test_append_skips_empty_line(self) -> None:
        result = self.parser._append_line("Existing", "   ")
        self.assertEqual(result, "Existing")

    def test_append_multiple_lines_build(self) -> None:
        current = "Line 1"
        current = self.parser._append_line(current, "Line 2")
        current = self.parser._append_line(current, "Line 3")
        self.assertEqual(current, "Line 1\nLine 2\nLine 3")

    # ── _pick_document_title ──────────────────────────────────────────

    def test_pick_title_first_valid_line(self) -> None:
        result = self.parser._pick_document_title(
            ["Standard Specification for Pressure Vessels", "1 Scope"]
        )
        self.assertEqual(result, "Standard Specification for Pressure Vessels")

    def test_pick_title_rejects_standard_code(self) -> None:
        result = self.parser._pick_document_title(
            ["DIN 1234", "Pressure Vessel Standard"]
        )
        self.assertEqual(result, "Pressure Vessel Standard")

    def test_pick_title_rejects_numbered_heading(self) -> None:
        result = self.parser._pick_document_title(
            ["1 Scope", "This standard applies to"]
        )
        self.assertEqual(result, "This standard applies to")

    def test_pick_title_rejects_noise_heading(self) -> None:
        result = self.parser._pick_document_title(
            ["Page 1", "Pressure Vessel Specification"]
        )
        self.assertEqual(result, "Pressure Vessel Specification")

    def test_pick_title_rejects_very_short(self) -> None:
        result = self.parser._pick_document_title(["ab", "Title Here"])
        self.assertEqual(result, "Title Here")

    def test_pick_title_fallback_to_stem(self) -> None:
        self.parser.config.input_path = Path("sample.pdf")
        result = self.parser._pick_document_title(["DIN 1234", "1 Scope"])
        self.assertEqual(result, "sample")

    # ── _pick_version_date ────────────────────────────────────────────

    def test_pick_version_iso_date(self) -> None:
        result = self.parser._pick_version_date(
            ["Some text", "2024-01 Standard"]
        )
        self.assertEqual(result, "2024-01")

    def test_pick_version_slash_date(self) -> None:
        result = self.parser._pick_version_date(
            ["Some text", "Published 2024/01"]
        )
        self.assertEqual(result, "2024/01")

    def test_pick_version_english_month(self) -> None:
        result = self.parser._pick_version_date(
            ["Some text", "January 2024 Edition"]
        )
        self.assertEqual(result, "January 2024")

    def test_pick_version_german_month(self) -> None:
        result = self.parser._pick_version_date(
            ["Some text", "Januar 2024 Ausgabe"]
        )
        self.assertEqual(result, "Januar 2024")

    def test_pick_version_not_found(self) -> None:
        result = self.parser._pick_version_date(["Some text", "No date here"])
        self.assertEqual(result, "")

    def test_pick_version_empty_list(self) -> None:
        result = self.parser._pick_version_date([])
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# 10. SectionRefTests
# ---------------------------------------------------------------------------

class SectionRefTests(unittest.TestCase):
    """章节引用和文档档案方法测试 (~6 tests)"""

    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output"))
        )

    # ── _section_ref ──────────────────────────────────────────────────

    def test_section_ref_number_and_title(self) -> None:
        section = SectionRecord(章节编号="1", 章节标题="Scope")
        self.assertEqual(self.parser._section_ref(section), "1 Scope")

    def test_section_ref_synthetic_number(self) -> None:
        section = SectionRecord(章节编号="U1", 章节标题="概述")
        self.assertEqual(self.parser._section_ref(section), "U1 概述")

    def test_section_ref_number_only(self) -> None:
        section = SectionRecord(章节编号="1.1", 章节标题="")
        self.assertEqual(self.parser._section_ref(section), "1.1")

    # ── _profile_label ────────────────────────────────────────────────

    def test_profile_label_standard(self) -> None:
        profile = DocumentProfile(文档类型="standard")
        self.assertEqual(
            self.parser._profile_label(profile), "标准/规范文档"
        )

    def test_profile_label_product_catalog(self) -> None:
        profile = DocumentProfile(文档类型="product_catalog")
        self.assertEqual(
            self.parser._profile_label(profile), "产品样本/规格资料"
        )

    def test_profile_label_unknown(self) -> None:
        profile = DocumentProfile(文档类型="unknown")
        self.assertEqual(self.parser._profile_label(profile), "技术资料")

    def test_profile_label_missing_type(self) -> None:
        profile = DocumentProfile(文档类型="not_a_type")
        self.assertEqual(self.parser._profile_label(profile), "技术资料")


if __name__ == "__main__":
    unittest.main()
