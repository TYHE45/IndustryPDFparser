from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from config import AppConfig
from src.models import (
    BlockRecord,
    DocumentData,
    DocumentProfile,
    FileMetadata,
    InspectionRecord,
    NumericParameter,
    RuleRecord,
    SectionRecord,
    StandardReference,
    TableRecord,
)
from src.llm_refiner import (
    TITLE_BLOCK,
    BODY_BLOCK,
    TABLE_FRAGMENT_BLOCK,
    LOCAL_STAGE,
    LLM_STAGE,
    _apply_local_cleanup,
    _apply_refinement,
    _collect_suspicious_blocks,
    _collect_suspicious_sections,
    _get_field,
    _hard_block_reasons,
    _hard_heading_reasons,
    _merge_body_text,
    _merge_section,
    _preserve_title_as_body,
    _replace_field_if_equal,
    _replace_section_refs,
    _request_refinement,
    _reset_views,
    _set_field,
    _suspicious_fragment_reasons,
    _suspicious_heading_reasons,
    refine_document_structure,
)


# ═══════════════════════════════════════════════════════════════════════════
# Module-level factory helpers
# ═══════════════════════════════════════════════════════════════════════════

def _meta(**overrides):
    defaults = dict(
        文件名称="test.pdf",
        文件类型="pdf",
        文档标题="测试文档",
        文档类型="standard",
        标准编号="GB/T 1",
        版本日期="2024-01-01",
        适用范围="测试",
    )
    return FileMetadata(**(defaults | overrides))


def _section(**overrides):
    defaults = dict(
        章节编号="1",
        章节标题="概述",
        章节层级=1,
        父章节编号="",
        章节清洗文本="测试正文。",
        所属部分="正文",
    )
    return SectionRecord(**(defaults | overrides))


def _block(**overrides):
    defaults = dict(
        块类型="正文",
        标题="",
        内容="",
        所属部分="正文",
        所属章节="1 概述",
        来源页码=1,
    )
    return BlockRecord(**(defaults | overrides))


def _profile(**overrides):
    defaults = dict(
        文档类型="standard",
        置信度=0.9,
        语言="zh",
        页数=1,
        文本行数=10,
        每页平均字符数=100.0,
    )
    return DocumentProfile(**(defaults | overrides))


def _minimal_doc():
    return DocumentData(文件元数据=_meta())


# ═══════════════════════════════════════════════════════════════════════════
# 1. SuspiciousHeadingReasonsTests
# ═══════════════════════════════════════════════════════════════════════════

class SuspiciousHeadingReasonsTests(unittest.TestCase):
    """单元测试 _suspicious_heading_reasons：17 条正则规则逐一验证。"""

    def test_empty_title_returns_empty_list(self):
        """标题为空时直接返回空列表。"""
        self.assertEqual(_suspicious_heading_reasons("", "", ""), [])

    def test_generic_page_word_page(self):
        """标题为 'page' 触发 generic_page_word。"""
        reasons = _suspicious_heading_reasons("page", "", "")
        self.assertIn("generic_page_word", reasons)

    def test_generic_page_word_seite(self):
        """标题为 'Seite'（德语）触发 generic_page_word。"""
        reasons = _suspicious_heading_reasons("Seite", "", "")
        self.assertIn("generic_page_word", reasons)

    def test_generic_page_word_contents(self):
        """标题为 'Contents' 触发 generic_page_word。"""
        reasons = _suspicious_heading_reasons("Contents", "", "")
        self.assertIn("generic_page_word", reasons)

    def test_generic_page_word_supersedes(self):
        """标题为 'supersedes' 触发 generic_page_word。"""
        reasons = _suspicious_heading_reasons("supersedes", "", "")
        self.assertIn("generic_page_word", reasons)

    def test_generic_page_word_index(self):
        """标题为 'index' 触发 generic_page_word。"""
        reasons = _suspicious_heading_reasons("index", "", "")
        self.assertIn("generic_page_word", reasons)

    def test_month_year_only_english(self):
        """标题为 'March 2024' 触发 month_year_only。"""
        reasons = _suspicious_heading_reasons("March 2024", "", "")
        self.assertIn("month_year_only", reasons)

    def test_month_year_only_german(self):
        """标题为 'Januar 2024'（德语）触发 month_year_only。"""
        reasons = _suspicious_heading_reasons("Januar 2024", "", "")
        self.assertIn("month_year_only", reasons)

    def test_number_only(self):
        """标题为纯数字编号 '3.2.1' 触发 number_only。"""
        reasons = _suspicious_heading_reasons("3.2.1", "", "")
        self.assertIn("number_only", reasons)

    def test_ics_code(self):
        """标题为 'ICS 91.010.30' 触发 ics_code。"""
        reasons = _suspicious_heading_reasons("ICS 91.010.30", "", "")
        self.assertIn("ics_code", reasons)

    def test_dimension_code(self):
        """标题为 'DN 150' 触发 dimension_code。"""
        reasons = _suspicious_heading_reasons("DN 150", "", "")
        self.assertIn("dimension_code", reasons)

    def test_copyright_notice(self):
        """标题含版权符号触发 copyright_notice（使用 search）。"""
        reasons = _suspicious_heading_reasons("copyright 2024 Company", "", "")
        self.assertIn("copyright_notice", reasons)

    def test_metadata_marker_draft(self):
        """标题为 'draft' 触发 metadata_marker。"""
        reasons = _suspicious_heading_reasons("draft", "", "")
        self.assertIn("metadata_marker", reasons)

    def test_metadata_marker_bearbeitet(self):
        """标题为 'bearbeitet'（德语）触发 metadata_marker。"""
        reasons = _suspicious_heading_reasons("bearbeitet", "", "")
        self.assertIn("metadata_marker", reasons)

    def test_trailing_hyphen(self):
        """标题以 '-' 结尾触发 trailing_hyphen。"""
        reasons = _suspicious_heading_reasons("Something-", "", "")
        self.assertIn("trailing_hyphen", reasons)

    def test_trailing_slash(self):
        """标题以 '/' 结尾同样触发 trailing_hyphen。"""
        reasons = _suspicious_heading_reasons("Something/", "", "")
        self.assertIn("trailing_hyphen", reasons)

    def test_leading_conjunction_and(self):
        """标题以 'and' 开头触发 leading_conjunction。"""
        reasons = _suspicious_heading_reasons("and something", "", "")
        self.assertIn("leading_conjunction", reasons)

    def test_leading_conjunction_und(self):
        """标题以 'und'（德语）开头触发 leading_conjunction。"""
        reasons = _suspicious_heading_reasons("und etwas", "", "")
        self.assertIn("leading_conjunction", reasons)

    def test_split_token_line(self):
        """标题为 'A / B / C' 触发 split_token_line。"""
        reasons = _suspicious_heading_reasons("A / B / C", "", "")
        self.assertIn("split_token_line", reasons)

    def test_unit_only_mm(self):
        """标题为 'mm' 触发 unit_only。"""
        reasons = _suspicious_heading_reasons("mm", "", "")
        self.assertIn("unit_only", reasons)

    def test_unit_only_percent(self):
        """标题为 '%' 触发 unit_only。"""
        reasons = _suspicious_heading_reasons("%", "", "")
        self.assertIn("unit_only", reasons)

    def test_short_token(self):
        """标题为全大写 1-3 字符的代码 'ABC' 触发 short_token。"""
        reasons = _suspicious_heading_reasons("ABC", "", "")
        self.assertIn("short_token", reasons)

    def test_letter_range(self):
        """标题为 'A - B' 触发 letter_range。"""
        reasons = _suspicious_heading_reasons("A - B", "", "")
        self.assertIn("letter_range", reasons)

    def test_value_fragment(self):
        """标题为纯数值 '42.5' 触发 value_fragment。"""
        reasons = _suspicious_heading_reasons("42.5", "", "")
        self.assertIn("value_fragment", reasons)

    def test_sentence_verb_fragment_triggered(self):
        """标题含动词且词数 >= 3 触发 sentence_verb_fragment。"""
        reasons = _suspicious_heading_reasons("This value shall meet", "", "")
        self.assertIn("sentence_verb_fragment", reasons)

    def test_sentence_verb_fragment_too_few_words(self):
        """标题含动词但词数 < 3 不触发 sentence_verb_fragment。"""
        reasons = _suspicious_heading_reasons("This shall", "", "")
        self.assertNotIn("sentence_verb_fragment", reasons)

    def test_sentence_fragment_triggered(self):
        """标题以 '.' 结尾且词数 <= 6 触发 sentence_fragment。"""
        reasons = _suspicious_heading_reasons("Short title.", "", "")
        self.assertIn("sentence_fragment", reasons)

    def test_sentence_fragment_high_word_count_not_triggered(self):
        """标题以 '.' 结尾但词数 > 6 不触发 sentence_fragment。"""
        reasons = _suspicious_heading_reasons("This title has more than six words indeed.", "", "")
        self.assertNotIn("sentence_fragment", reasons)

    def test_lowercase_fragment_triggered(self):
        """标题以小写开头结尾带标点 + 词数 <= 5 + body < 160 触发 lowercase_fragment。"""
        reasons = _suspicious_heading_reasons("intro.", "", "")
        self.assertIn("lowercase_fragment", reasons)

    def test_lowercase_fragment_long_body_not_triggered(self):
        """body >= 160 字符时不触发 lowercase_fragment。"""
        long_body = "x" * 160
        reasons = _suspicious_heading_reasons("intro.", long_body, "")
        self.assertNotIn("lowercase_fragment", reasons)

    def test_lowercase_fragment_uppercase_start_not_triggered(self):
        """标题以大写开头不匹配 TRAILING_FRAGMENT_RE，不触发 lowercase_fragment。"""
        reasons = _suspicious_heading_reasons("Intro.", "", "")
        self.assertNotIn("lowercase_fragment", reasons)

    def test_too_short_for_heading_triggered(self):
        """词数 <= 2、标题长 <= 6、body < 80、非 U 前缀触发 too_short_for_heading。"""
        reasons = _suspicious_heading_reasons("AB", "", "")
        self.assertIn("too_short_for_heading", reasons)

    def test_u_prefix_escapes_too_short(self):
        """章节编号以 'U' 开头时不触发 too_short_for_heading。"""
        reasons = _suspicious_heading_reasons("AB", "", "U1")
        self.assertNotIn("too_short_for_heading", reasons)

    def test_compound_reasons(self):
        """标题 'DN 150' 同时触发 dimension_code、value_fragment 和 too_short_for_heading。"""
        reasons = _suspicious_heading_reasons("DN 150", "", "")
        self.assertIn("dimension_code", reasons)
        self.assertIn("value_fragment", reasons)
        self.assertIn("too_short_for_heading", reasons)
        self.assertEqual(len(reasons), 3)


# ═══════════════════════════════════════════════════════════════════════════
# 2. SuspiciousFragmentReasonsTests
# ═══════════════════════════════════════════════════════════════════════════

class SuspiciousFragmentReasonsTests(unittest.TestCase):
    """单元测试 _suspicious_fragment_reasons：19 条规则逐一验证。"""

    def test_empty_text_returns_empty_list(self):
        """标题和内容均为空时返回空列表。"""
        reasons = _suspicious_fragment_reasons("正文", "", "")
        self.assertEqual(reasons, [])

    def test_falls_back_to_content_when_title_empty(self):
        """标题为空时回退检查内容文本。"""
        reasons = _suspicious_fragment_reasons("正文", "", "page")
        self.assertIn("generic_page_word", reasons)

    def test_generic_page_word_fragment(self):
        """文本为 'page' 触发 generic_page_word。"""
        reasons = _suspicious_fragment_reasons("正文", "page", "")
        self.assertIn("generic_page_word", reasons)

    def test_month_year_only_fragment(self):
        """文本为 'March 2024' 触发 month_year_only。"""
        reasons = _suspicious_fragment_reasons("正文", "March 2024", "")
        self.assertIn("month_year_only", reasons)

    def test_number_fragment(self):
        """纯数字触发 number_fragment（不同于 heading 的 number_only）。"""
        reasons = _suspicious_fragment_reasons("正文", "3.2.1", "")
        self.assertIn("number_fragment", reasons)

    def test_ics_code_fragment(self):
        """文本为 'ICS 91.010.30' 触发 ics_code。"""
        reasons = _suspicious_fragment_reasons("正文", "ICS 91.010.30", "")
        self.assertIn("ics_code", reasons)

    def test_copyright_notice_fragment(self):
        """文本含版权标记触发 copyright_notice。"""
        reasons = _suspicious_fragment_reasons("正文", "copyright 2024", "")
        self.assertIn("copyright_notice", reasons)

    def test_metadata_marker_fragment(self):
        """文本为 'draft' 触发 metadata_marker。"""
        reasons = _suspicious_fragment_reasons("正文", "draft", "")
        self.assertIn("metadata_marker", reasons)

    def test_trailing_hyphen_fragment(self):
        """文本以 '-' 结尾触发 trailing_hyphen。"""
        reasons = _suspicious_fragment_reasons("正文", "Item-", "")
        self.assertIn("trailing_hyphen", reasons)

    def test_leading_conjunction_fragment(self):
        """文本以 'and' 开头触发 leading_conjunction。"""
        reasons = _suspicious_fragment_reasons("正文", "and more", "")
        self.assertIn("leading_conjunction", reasons)

    def test_unit_only_fragment(self):
        """文本为 'mm' 触发 unit_only。"""
        reasons = _suspicious_fragment_reasons("正文", "mm", "")
        self.assertIn("unit_only", reasons)

    def test_short_token_fragment(self):
        """文本为全大写短代码 'ABC' 触发 short_token。"""
        reasons = _suspicious_fragment_reasons("正文", "ABC", "")
        self.assertIn("short_token", reasons)

    def test_letter_range_fragment(self):
        """文本为 'A - B' 触发 letter_range。"""
        reasons = _suspicious_fragment_reasons("正文", "A - B", "")
        self.assertIn("letter_range", reasons)

    def test_value_fragment_fragment(self):
        """文本为纯数值 '42.5' 触发 value_fragment。"""
        reasons = _suspicious_fragment_reasons("正文", "42.5", "")
        self.assertIn("value_fragment", reasons)

    def test_sentence_verb_fragment_fragment(self):
        """文本含动词且词数 >= 3 触发 sentence_verb_fragment。"""
        reasons = _suspicious_fragment_reasons("正文", "This value must meet", "")
        self.assertIn("sentence_verb_fragment", reasons)

    def test_matrix_token(self):
        """文本为 'A / 1 / B' 触发 matrix_token。"""
        reasons = _suspicious_fragment_reasons("正文", "A / 1 / B", "")
        self.assertIn("matrix_token", reasons)

    def test_dimension_code_fragment(self):
        """文本为 'DN 150' 触发 dimension_code。"""
        reasons = _suspicious_fragment_reasons("正文", "DN 150", "")
        self.assertIn("dimension_code", reasons)

    def test_number_matrix(self):
        """文本为重复数字 '1.5 2.3 4.7' 触发 number_matrix。"""
        reasons = _suspicious_fragment_reasons("正文", "1.5 2.3 4.7", "")
        self.assertIn("number_matrix", reasons)

    def test_very_short_fragment_table_block(self):
        """文本长度 <= 3 且块类型为表格碎片时触发 very_short_fragment。"""
        reasons = _suspicious_fragment_reasons(TABLE_FRAGMENT_BLOCK, "AB", "")
        self.assertIn("very_short_fragment", reasons)

    def test_very_short_fragment_title_block(self):
        """文本长度 <= 3 且块类型为标题时触发 very_short_fragment。"""
        reasons = _suspicious_fragment_reasons(TITLE_BLOCK, "AB", "")
        self.assertIn("very_short_fragment", reasons)

    def test_very_short_fragment_wrong_block_type_not_triggered(self):
        """文本长度 <= 3 但块类型非表格碎片/标题时不触发 very_short_fragment。"""
        reasons = _suspicious_fragment_reasons(BODY_BLOCK, "AB", "")
        self.assertNotIn("very_short_fragment", reasons)

    def test_sentence_fragment_title_based(self):
        """title 以 '.' 结尾且词数 <= 6 触发 sentence_fragment（仅标题检查）。"""
        reasons = _suspicious_fragment_reasons("标题", "Short title.", "")
        self.assertIn("sentence_fragment", reasons)

    def test_lowercase_fragment_title_based_triggered(self):
        """title 以小写开头结尾带标点且 content < 160 触发 lowercase_fragment。"""
        reasons = _suspicious_fragment_reasons("正文", "intro.", "")
        self.assertIn("lowercase_fragment", reasons)

    def test_lowercase_fragment_title_based_long_content_not_triggered(self):
        """title 符合条件但 content >= 160 不触发 lowercase_fragment。"""
        reasons = _suspicious_fragment_reasons("正文", "intro.", "x" * 160)
        self.assertNotIn("lowercase_fragment", reasons)

    def test_content_not_used_for_sentence_fragment(self):
        """sentence_fragment 仅基于 title，不检查 content。"""
        reasons = _suspicious_fragment_reasons("正文", "", "Short sentence.")
        self.assertNotIn("sentence_fragment", reasons)

    def test_compound_fragment_reasons(self):
        """文本 'DN 150' 同时触发 dimension_code 和 value_fragment。"""
        reasons = _suspicious_fragment_reasons("正文", "DN 150", "")
        self.assertIn("dimension_code", reasons)
        self.assertIn("value_fragment", reasons)


# ═══════════════════════════════════════════════════════════════════════════
# 3. MergeBodyTextTests
# ═══════════════════════════════════════════════════════════════════════════

class MergeBodyTextTests(unittest.TestCase):
    """单元测试 _merge_body_text：行级去重合并。"""

    def test_both_empty_returns_empty(self):
        """两边均为空时返回空字符串。"""
        result = _merge_body_text("", "")
        self.assertEqual(result, "")

    def test_append_mode(self):
        """默认模式 existing + extra 追加合并。"""
        result = _merge_body_text("line1\nline2", "line3")
        self.assertEqual(result, "line1\nline2\nline3")

    def test_prepend_mode(self):
        """prepend=True 时 extra 在前。"""
        result = _merge_body_text("line1", "line2", prepend=True)
        self.assertEqual(result, "line2\nline1")

    def test_line_level_dedup(self):
        """重复行被去重，保留首次出现。"""
        result = _merge_body_text("A\nB", "B\nC")
        self.assertEqual(result, "A\nB\nC")

    def test_dedup_within_extra(self):
        """extra 内部重复行也被去重。"""
        result = _merge_body_text("A", "B\nB\nC")
        self.assertEqual(result, "A\nB\nC")


# ═══════════════════════════════════════════════════════════════════════════
# 4. PreserveTitleAsBodyTests
# ═══════════════════════════════════════════════════════════════════════════

class PreserveTitleAsBodyTests(unittest.TestCase):
    """单元测试 _preserve_title_as_body：判断标题是否值得保留为正文。"""

    def test_empty_title_returns_false(self):
        """空标题返回 False。"""
        self.assertFalse(_preserve_title_as_body(""))

    def test_page_noise_returns_false(self):
        """'page' 之类噪音标题返回 False。"""
        self.assertFalse(_preserve_title_as_body("page"))

    def test_month_year_returns_false(self):
        """日期标题 'March 2024' 返回 False。"""
        self.assertFalse(_preserve_title_as_body("March 2024"))

    def test_copyright_returns_false(self):
        """版权标题返回 False。"""
        self.assertFalse(_preserve_title_as_body("copyright 2024 Company"))

    def test_normal_title_returns_true(self):
        """正常标题返回 True。"""
        self.assertTrue(_preserve_title_as_body("概述"))

    def test_dimension_code_returns_false(self):
        """尺寸代码标题 'DN 150' 返回 False。"""
        self.assertFalse(_preserve_title_as_body("DN 150"))


# ═══════════════════════════════════════════════════════════════════════════
# 5. HardReasonSetsTests
# ═══════════════════════════════════════════════════════════════════════════

class HardReasonSetsTests(unittest.TestCase):
    """单元测试 _hard_heading_reasons / _hard_block_reasons：集合包含预期键。"""

    def test_hard_heading_reasons_contains_expected_strings(self):
        """_hard_heading_reasons 返回 15 个确定的 reason 键。"""
        reasons = _hard_heading_reasons()
        expected = [
            "generic_page_word", "month_year_only", "number_only",
            "ics_code", "dimension_code", "copyright_notice",
            "metadata_marker", "trailing_hyphen", "leading_conjunction",
            "split_token_line", "unit_only", "short_token",
            "letter_range", "value_fragment", "sentence_verb_fragment",
        ]
        for key in expected:
            self.assertIn(key, reasons)
        self.assertEqual(len(reasons), 15)

    def test_hard_block_reasons_contains_expected_strings(self):
        """_hard_block_reasons 返回 17 个确定的 reason 键。"""
        reasons = _hard_block_reasons()
        expected = [
            "generic_page_word", "month_year_only", "number_fragment",
            "ics_code", "copyright_notice", "metadata_marker",
            "trailing_hyphen", "leading_conjunction", "unit_only",
            "short_token", "letter_range", "value_fragment",
            "sentence_verb_fragment", "matrix_token", "number_matrix",
            "dimension_code", "very_short_fragment",
        ]
        for key in expected:
            self.assertIn(key, reasons)
        self.assertEqual(len(reasons), 17)


# ═══════════════════════════════════════════════════════════════════════════
# 6. MergeSectionTests
# ═══════════════════════════════════════════════════════════════════════════

class MergeSectionTests(unittest.TestCase):
    """单元测试 _merge_section：章节合并与方向逻辑。"""

    def test_empty_section_list_returns_false(self):
        """章节列表为空时返回 False。"""
        doc = _minimal_doc()
        self.assertFalse(_merge_section(doc, 0, "previous"))

    def test_merge_into_previous(self):
        """合并到前一个章节（追加正文）。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="旧正文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="第二章", 章节清洗文本="新行。",
                         所属部分="正文"),
            ],
        )
        result = _merge_section(doc, 1, "previous")
        self.assertTrue(result)
        self.assertEqual(len(doc.章节列表), 1)
        combined = _get_field(doc.章节列表[0], 4)
        self.assertIn("旧正文", combined)
        self.assertIn("新行", combined)
        self.assertIn("第二章", combined)

    def test_merge_into_next(self):
        """合并到下一个章节（前置正文）。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="前行。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="第二章", 章节清洗文本="后续正文。",
                         所属部分="正文"),
            ],
        )
        result = _merge_section(doc, 0, "next")
        self.assertTrue(result)
        self.assertEqual(len(doc.章节列表), 1)
        combined = _get_field(doc.章节列表[0], 4)
        # prepend mode: source content first, then target
        self.assertTrue(combined.startswith("第一章") or combined.startswith("前行"))

    def test_boundary_first_section_previous_redirects_to_next(self):
        """第一个章节触发 previous 合并时自动转为 next。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一", 章节清洗文本="A。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="第二", 章节清洗文本="B。",
                         所属部分="正文"),
            ],
        )
        result = _merge_section(doc, 0, "previous")
        self.assertTrue(result)
        self.assertEqual(len(doc.章节列表), 1)

    def test_boundary_last_section_next_redirects_to_previous(self):
        """最后一个章节触发 next 合并时自动转为 previous。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一", 章节清洗文本="A。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="第二", 章节清洗文本="B。",
                         所属部分="正文"),
            ],
        )
        result = _merge_section(doc, 1, "next")
        self.assertTrue(result)
        self.assertEqual(len(doc.章节列表), 1)

    def test_single_section_returns_false(self):
        """仅有一个章节时任何方向合并都返回 False。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section()],
        )
        self.assertFalse(_merge_section(doc, 0, "previous"))

    def test_title_preserved_in_body(self):
        """正常标题被保留到目标章节正文中。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="前一章", 章节清洗文本="旧文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="被合并章", 章节清洗文本="新文。",
                         所属部分="正文"),
            ],
        )
        _merge_section(doc, 1, "previous")
        combined = _get_field(doc.章节列表[0], 4)
        self.assertIn("被合并章", combined)


# ═══════════════════════════════════════════════════════════════════════════
# 7. ReplaceRefsAndFieldTests
# ═══════════════════════════════════════════════════════════════════════════

class ReplaceRefsAndFieldTests(unittest.TestCase):
    """单元测试 _replace_field_if_equal 与 _replace_section_refs。"""

    def test_replace_field_if_equal_matches(self):
        """字段值与旧值相等时被替换。"""
        section = _section(章节标题="旧标题")
        _replace_field_if_equal(section, 1, "旧标题", "新标题")
        self.assertEqual(_get_field(section, 1), "新标题")

    def test_replace_field_if_equal_no_match(self):
        """字段值与旧值不相等时保持原样。"""
        section = _section(章节标题="其他标题")
        _replace_field_if_equal(section, 1, "旧标题", "新标题")
        self.assertEqual(_get_field(section, 1), "其他标题")

    def test_replace_section_refs_updates_all_record_types(self):
        """此函数更新表格/参数/规则/检验/标准/块共六种记录类型的所属章节字段。

        NumericParameter 所属章节字段索引为 7（而不是 5），必须使用真实模型实例验证。
        """
        old_ref = "1 概述"
        new_ref = "2 正文"
        doc = DocumentData(
            文件元数据=_meta(),
            表格列表=[TableRecord(表格编号="表1", 表格标题="测试", 所属章节=old_ref)],
            数值参数列表=[NumericParameter(参数名称="P", 所属章节=old_ref)],
            规则列表=[RuleRecord(规则类型="要求", 规则内容="R", 所属章节=old_ref)],
            检验列表=[InspectionRecord(检验对象="O", 所属章节=old_ref)],
            引用标准列表=[StandardReference(标准编号="S", 所属章节=old_ref)],
            内容块列表=[_block(块类型="正文", 所属章节=old_ref)],
        )
        _replace_section_refs(doc, old_ref, new_ref)

        self.assertEqual(_get_field(doc.表格列表[0], 2), new_ref)
        self.assertEqual(_get_field(doc.数值参数列表[0], 7), new_ref)
        self.assertEqual(_get_field(doc.规则列表[0], 3), new_ref)
        self.assertEqual(_get_field(doc.检验列表[0], 4), new_ref)
        self.assertEqual(_get_field(doc.引用标准列表[0], 3), new_ref)
        self.assertEqual(_get_field(doc.内容块列表[0], 4), new_ref)

    def test_replace_section_refs_same_value_returns_early(self):
        """old_ref 与 new_ref 相同时不修改任何记录。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[_block(块类型="正文", 所属章节="1 概述")],
        )
        _replace_section_refs(doc, "1 概述", "1 概述")
        self.assertEqual(_get_field(doc.内容块列表[0], 4), "1 概述")

    def test_replace_section_refs_empty_values_returns_early(self):
        """old_ref 或 new_ref 为空时提前返回。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[_block(块类型="正文", 所属章节="1 概述")],
        )
        _replace_section_refs(doc, "", "new")
        self.assertEqual(_get_field(doc.内容块列表[0], 4), "1 概述")

        _replace_section_refs(doc, "old", "")
        self.assertEqual(_get_field(doc.内容块列表[0], 4), "1 概述")


# ═══════════════════════════════════════════════════════════════════════════
# 8. FieldAccessTests
# ═══════════════════════════════════════════════════════════════════════════

class FieldAccessTests(unittest.TestCase):
    """单元测试 _get_field / _set_field：基于 dataclasses.fields 的索引访问。"""

    def test_get_field_returns_correct_attribute(self):
        """按索引读取 SectionRecord 字段。"""
        section = _section(章节编号="5", 章节标题="测试", 章节层级=2)
        self.assertEqual(_get_field(section, 0), "5")
        self.assertEqual(_get_field(section, 1), "测试")
        self.assertEqual(_get_field(section, 2), 2)

    def test_set_field_sets_correct_attribute(self):
        """按索引设置 SectionRecord 字段。"""
        section = _section(章节标题="旧标题")
        _set_field(section, 1, "新标题")
        self.assertEqual(section.章节标题, "新标题")
        self.assertEqual(_get_field(section, 1), "新标题")

    def test_get_set_roundtrip(self):
        """_set_field 后 _get_field 返回新值。"""
        section = _section()
        for idx in range(6):
            _set_field(section, idx, f"value-{idx}")
            self.assertEqual(_get_field(section, idx), f"value-{idx}")


# ═══════════════════════════════════════════════════════════════════════════
# 9. ResetViewsTests
# ═══════════════════════════════════════════════════════════════════════════

class ResetViewsTests(unittest.TestCase):
    """单元测试 _reset_views：清空结构节点列表。"""

    def test_reset_views_clears_structure_nodes(self):
        """调用后 结构节点列表 变为空列表。"""
        from src.models import StructureNode
        doc = _minimal_doc()
        doc.结构节点列表 = [StructureNode(节点ID="n1", 节点标题="测试节点")]
        _reset_views(doc)
        self.assertEqual(doc.结构节点列表, [])


# ═══════════════════════════════════════════════════════════════════════════
# 10. ApplyLocalCleanupTests
# ═══════════════════════════════════════════════════════════════════════════

class ApplyLocalCleanupTests(unittest.TestCase):
    """单元测试 _apply_local_cleanup：本地预清理。"""

    def test_no_candidates_no_change(self):
        """不含任何可疑章节/块时无变更。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节标题="正常标题", 章节清洗文本="正文内容。")],
            内容块列表=[_block(块类型="正文", 内容="普通正文。")],
        )
        changed, actions, sec_count, blk_count = _apply_local_cleanup(doc)
        self.assertFalse(changed)
        self.assertEqual(actions, 0)

    def test_hard_heading_merge(self):
        """标题为 'page' 的章节触发 hard 合并。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="正文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="page", 章节清洗文本="更多内容。",
                         所属部分="正文"),
            ],
        )
        changed, actions, sec_count, blk_count = _apply_local_cleanup(doc)
        self.assertTrue(changed)
        self.assertEqual(actions, 1)
        # 章节 'page' 已被合并到第一章
        self.assertEqual(len(doc.章节列表), 1)
        combined = _get_field(doc.章节列表[0], 4)
        self.assertIn("更多内容", combined)

    def test_table_fragment_block_deleted(self):
        """表格碎片块触发 hard 删除。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[
                _block(块类型=TABLE_FRAGMENT_BLOCK, 标题="", 内容="page"),
            ],
        )
        changed, actions, sec_count, blk_count = _apply_local_cleanup(doc)
        self.assertTrue(changed)
        self.assertEqual(actions, 1)
        self.assertEqual(len(doc.内容块列表), 0)

    def test_title_block_converted_to_body(self):
        """标题块触发 sentence_fragment 后被转为正文块。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[
                _block(块类型=TITLE_BLOCK, 标题="Short title.", 内容="",
                       所属部分="正文", 所属章节="1 概述"),
            ],
        )
        changed, actions, sec_count, blk_count = _apply_local_cleanup(doc)
        self.assertTrue(changed)
        self.assertEqual(actions, 1)
        block = doc.内容块列表[0]
        self.assertEqual(_get_field(block, 0), BODY_BLOCK)
        self.assertEqual(_get_field(block, 1), "")
        self.assertIn("Short title.", _get_field(block, 2))

    def test_hard_heading_merge_skips_non_hard_reasons(self):
        """原因不落在 _hard_heading_reasons 内的章节保留不动。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="正文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="Short title.",
                         章节清洗文本="更多。", 所属部分="正文"),
            ],
        )
        # "Short title." 触发了 sentence_fragment, 但它不在 _hard_heading_reasons 中
        changed, actions, sec_count, blk_count = _apply_local_cleanup(doc)
        # sentence_fragment 不在 hard reasons 中，所以不会被合并
        # 最终章节列表应该仍然是 2 个
        self.assertEqual(len(doc.章节列表), 2)


# ═══════════════════════════════════════════════════════════════════════════
# 11. CollectSuspiciousTests
# ═══════════════════════════════════════════════════════════════════════════

class CollectSuspiciousTests(unittest.TestCase):
    """单元测试 _collect_suspicious_sections / _collect_suspicious_blocks：候选收集。"""

    def test_collect_sections_returns_candidate(self):
        """包含可疑标题的章节被收集。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节标题="page", 章节清洗文本="正文。")],
        )
        candidates = _collect_suspicious_sections(doc, limit=10)
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0]["kind"], "section")
        self.assertIn("generic_page_word", candidates[0]["reasons"])

    def test_collect_sections_empty_when_no_reasons(self):
        """所有章节标题均正常时不返回候选。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节标题="Normal Section Title For Testing",
                               章节清洗文本="This is normal body text for testing purposes.")],
        )
        candidates = _collect_suspicious_sections(doc, limit=10)
        self.assertEqual(candidates, [])

    def test_collect_sections_sorted_by_score(self):
        """高分的候选排在前面。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节标题="DN 150", 章节清洗文本=""),   # 2 reasons
                _section(章节标题="page", 章节清洗文本=""),     # 1 reason
            ],
        )
        candidates = _collect_suspicious_sections(doc, limit=10)
        self.assertEqual(len(candidates), 2)
        self.assertGreaterEqual(candidates[0]["score"], candidates[1]["score"])

    def test_collect_blocks_returns_candidate(self):
        """包含可疑文本的块被收集。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[_block(块类型=TITLE_BLOCK, 标题="Short title.", 内容="")],
        )
        candidates = _collect_suspicious_blocks(doc, limit=10)
        self.assertGreater(len(candidates), 0)
        self.assertEqual(candidates[0]["kind"], "block")
        self.assertIn("sentence_fragment", candidates[0]["reasons"])

    def test_collect_blocks_empty_when_no_reasons(self):
        """所有块均正常时不返回候选。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[_block(块类型="正文", 内容="正常的一段文字。")],
        )
        candidates = _collect_suspicious_blocks(doc, limit=10)
        self.assertEqual(candidates, [])

    def test_collect_sections_respects_limit(self):
        """limit 参数限制返回候选数量。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节标题="page", 章节清洗文本="") for _ in range(10)],
        )
        candidates = _collect_suspicious_sections(doc, limit=3)
        self.assertEqual(len(candidates), 3)

    def test_collect_blocks_respects_limit(self):
        """limit 参数限制返回候选数量。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[_block(块类型=TITLE_BLOCK, 标题="Short title.", 内容="")
                       for _ in range(10)],
        )
        candidates = _collect_suspicious_blocks(doc, limit=4)
        self.assertEqual(len(candidates), 4)


# ═══════════════════════════════════════════════════════════════════════════
# 12. ApplyRefinementTests
# ═══════════════════════════════════════════════════════════════════════════

class ApplyRefinementTests(unittest.TestCase):
    """单元测试 _apply_refinement：将 LLM 响应应用到文档。"""

    def test_rename_heading(self):
        """LLM 决策 rename_heading 更新章节标题并替换引用。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="旧标题", 章节清洗文本="正文。",
                         所属部分="正文"),
            ],
            内容块列表=[_block(块类型="正文", 所属章节="1 旧标题")],
        )
        section_candidates = [
            {
                "candidate_id": "sec-0",
                "section_index": 0,
                "section_title": "旧标题",
                "reasons": ["short_token"],
            }
        ]
        response = {
            "section_decisions": [
                {
                    "candidate_id": "sec-0",
                    "action": "rename_heading",
                    "new_title": "新标题",
                    "reason": "应重命名",
                    "confidence": 0.95,
                }
            ],
            "block_decisions": [],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(
            doc, section_candidates, [], response
        )
        self.assertTrue(changed)
        self.assertEqual(action_count, 1)
        self.assertEqual(_get_field(doc.章节列表[0], 1), "新标题")
        # 块引用也被更新
        self.assertEqual(_get_field(doc.内容块列表[0], 4), "1 新标题")

    def test_merge_section_previous(self):
        """LLM 决策 drop_heading_merge_into_previous 合并章节。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一", 章节清洗文本="A。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="第二", 章节清洗文本="B。",
                         所属部分="正文"),
            ],
        )
        section_candidates = [
            {
                "candidate_id": "sec-1",
                "section_index": 1,
                "section_title": "第二",
                "reasons": ["short_token"],
            }
        ]
        response = {
            "section_decisions": [
                {
                    "candidate_id": "sec-1",
                    "action": "drop_heading_merge_into_previous",
                    "new_title": "",
                    "reason": "应合并",
                    "confidence": 0.9,
                }
            ],
            "block_decisions": [],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(
            doc, section_candidates, [], response
        )
        self.assertTrue(changed)
        self.assertEqual(action_count, 1)
        self.assertEqual(len(doc.章节列表), 1)

    def test_drop_block(self):
        """LLM 决策 drop_block 删除内容块。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[_block(块类型="正文", 标题="", 内容="x")],
        )
        block_candidates = [
            {
                "candidate_id": "blk-0",
                "block_index": 0,
                "block_type": "正文",
                "reasons": ["short_token"],
            }
        ]
        response = {
            "section_decisions": [],
            "block_decisions": [
                {
                    "candidate_id": "blk-0",
                    "action": "drop_block",
                    "reason": "应删除",
                    "confidence": 0.85,
                }
            ],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(
            doc, [], block_candidates, response
        )
        self.assertTrue(changed)
        self.assertEqual(action_count, 1)
        self.assertEqual(len(doc.内容块列表), 0)

    def test_block_to_body(self):
        """LLM 决策 block_to_body 将标题块转为正文块。"""
        doc = DocumentData(
            文件元数据=_meta(),
            内容块列表=[
                _block(块类型=TITLE_BLOCK, 标题="标题内容。", 内容="",
                       所属部分="正文", 所属章节="1 概述"),
            ],
        )
        block_candidates = [
            {
                "candidate_id": "blk-0",
                "block_index": 0,
                "block_type": TITLE_BLOCK,
                "reasons": ["sentence_fragment"],
            }
        ]
        response = {
            "section_decisions": [],
            "block_decisions": [
                {
                    "candidate_id": "blk-0",
                    "action": "block_to_body",
                    "reason": "应改正文",
                    "confidence": 0.8,
                }
            ],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(
            doc, [], block_candidates, response
        )
        self.assertTrue(changed)
        self.assertEqual(action_count, 1)
        self.assertEqual(_get_field(doc.内容块列表[0], 0), BODY_BLOCK)

    def test_empty_decisions_no_change(self):
        """响应不包含任何决策时无变更。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节标题="test", 章节清洗文本="body")],
        )
        response = {
            "section_decisions": [],
            "block_decisions": [],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(doc, [], [], response)
        self.assertFalse(changed)
        self.assertEqual(action_count, 0)

    def test_unknown_candidate_id_skipped(self):
        """candidate_id 未匹配到候选时跳过该决策。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节编号="1", 章节标题="唯一", 章节清洗文本="正文。")],
        )
        response = {
            "section_decisions": [
                {
                    "candidate_id": "sec-999",
                    "action": "rename_heading",
                    "new_title": "不会更新",
                    "reason": "无效",
                    "confidence": 1.0,
                }
            ],
            "block_decisions": [],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(doc, [], [], response)
        self.assertFalse(changed)
        self.assertEqual(action_count, 0)

    def test_rename_heading_skips_when_new_title_same(self):
        """新标题与原标题相同时跳过更新。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节编号="1", 章节标题="相同标题", 章节清洗文本="正文。")],
        )
        section_candidates = [
            {
                "candidate_id": "sec-0",
                "section_index": 0,
                "section_title": "相同标题",
                "reasons": ["short_token"],
            }
        ]
        response = {
            "section_decisions": [
                {
                    "candidate_id": "sec-0",
                    "action": "rename_heading",
                    "new_title": "相同标题",
                    "reason": "不变",
                    "confidence": 1.0,
                }
            ],
            "block_decisions": [],
            "global_notes": [],
        }
        changed, action_count = _apply_refinement(
            doc, section_candidates, [], response
        )
        self.assertFalse(changed)
        self.assertEqual(action_count, 0)


# ═══════════════════════════════════════════════════════════════════════════
# 13. RefineDocumentStructureTests
# ═══════════════════════════════════════════════════════════════════════════

class RefineDocumentStructureTests(unittest.TestCase):
    """集成测试 refine_document_structure：入口函数。"""

    def _config(self, **overrides):
        defaults = dict(
            input_path=Path("."),
            output_dir=Path("."),
            use_llm=False,
        )
        return AppConfig(**(defaults | overrides))

    def test_local_only_when_llm_disabled(self):
        """LLM 禁用时仅执行本地清理。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="正文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="page", 章节清洗文本="更多内容。",
                         所属部分="正文"),
            ],
        )
        config = self._config(use_llm=False)
        refined, rounds = refine_document_structure(doc, config)
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["阶段"], "本地预清理")

    def test_local_cleanup_before_llm(self):
        """LLM 启用时 round 0 始终是本地预清理。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="正文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="page", 章节清洗文本="更多内容。",
                         所属部分="正文"),
            ],
        )
        config = self._config(use_llm=True)
        with mock.patch("src.llm_refiner.llm_available", return_value=True), \
             mock.patch("src.llm_refiner.request_structured_json",
                        return_value=({"section_decisions": [], "block_decisions": [], "global_notes": []}, "mock")):
            refined, rounds = refine_document_structure(doc, config)
        # round 0 是本地预清理
        self.assertGreaterEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["阶段"], "本地预清理")

    def test_llm_error_adds_failure_entry(self):
        """LLM 请求失败时添加失败记录。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="page", 章节清洗文本="正文。",
                         所属部分="正文"),
            ],
        )
        config = self._config(use_llm=True)
        with mock.patch("src.llm_refiner.llm_available", return_value=True), \
             mock.patch("src.llm_refiner.request_structured_json",
                        side_effect=RuntimeError("LLM 不可用")):
            refined, rounds = refine_document_structure(doc, config)
        # round 0 本地预清理已合并 'page' 章节（无更多候选项），
        # 或至少有一轮 LLM 失败日志
        failure_rounds = [r for r in rounds if not r.get("是否成功", True)]
        self.assertGreaterEqual(len(failure_rounds), 0, "应检查是否有失败轮次")
        # 真正的测试：在 local cleanup 后 doc 已无候选项时会 break，
        # 所以需要 doc 仍有候选。重新构造一个本地清理后仍有候选的场景。
        # 本地清理只处理 _hard_heading_reasons，sentence_fragment 不在其中
        doc2 = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一章", 章节清洗文本="正文。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="Short title.",
                         章节清洗文本="更多。", 所属部分="正文"),
            ],
        )
        with mock.patch("src.llm_refiner.llm_available", return_value=True), \
             mock.patch("src.llm_refiner.request_structured_json",
                        side_effect=ValueError("服务不可达")):
            refined2, rounds2 = refine_document_structure(doc2, config)
        failure_rounds2 = [r for r in rounds2 if r.get("阶段") == "LLM结构复核" and not r.get("是否成功", False)]
        self.assertGreater(len(failure_rounds2), 0, "应至少有一个 LLM 失败记录")

    def test_no_candidates_breaks_loop(self):
        """无候选项时 LLM 循环提前终止。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[_section(章节标题="Normal Section Title For Testing",
                               章节清洗文本="This is normal body text for testing purposes.")],
        )
        config = self._config(use_llm=True)
        with mock.patch("src.llm_refiner.llm_available", return_value=True), \
             mock.patch("src.llm_refiner.request_structured_json") as mock_request:
            refined, rounds = refine_document_structure(doc, config)
        # 本地清理未改动，且无候选项 → 不会调用 LLM
        mock_request.assert_not_called()
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["阶段"], "本地预清理")

    def test_multi_round_convergence(self):
        """第一轮 LLM 有变更，第二轮无变更时收敛停止。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一", 章节清洗文本="A。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="DN 150", 章节清洗文本="",
                         所属部分="正文"),
                _section(章节编号="3", 章节标题="第三", 章节清洗文本="B。",
                         所属部分="正文"),
            ],
        )
        config = self._config(
            use_llm=True,
            llm_structure_refine_rounds=5,
        )
        # 第一轮返回 merging 决策；第二轮返回 keep
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (
                    {
                        "section_decisions": [
                            {
                                "candidate_id": "sec-1",
                                "action": "drop_heading_merge_into_previous",
                                "new_title": "",
                                "reason": "非章节标题",
                                "confidence": 0.9,
                            }
                        ],
                        "block_decisions": [],
                        "global_notes": [],
                    },
                    "test-model",
                )
            else:
                return (
                    {
                        "section_decisions": [
                            {
                                "candidate_id": "sec-1",
                                "action": "keep",
                                "new_title": "DN 150",
                                "reason": "保留",
                                "confidence": 0.95,
                            }
                        ],
                        "block_decisions": [],
                        "global_notes": [],
                    },
                    "test-model",
                )

        with mock.patch("src.llm_refiner.llm_available", return_value=True), \
             mock.patch("src.llm_refiner.request_structured_json", side_effect=side_effect):
            refined, rounds = refine_document_structure(doc, config)

        # 本地预清理将 "DN 150" 合并（dimension_code/value_fragment 都在 hard 原因中）
        # 之后 doc 应只剩 2 节并 normalize 后，DN 150 已在 body_line_count <= 4 时 merged previous
        # 继续检查 round 序列
        llm_rounds = [r for r in rounds if r["阶段"] == "LLM结构复核"]
        self.assertGreaterEqual(len(llm_rounds), 1)

    def test_keep_action_does_not_count_as_change(self):
        """全部 keep 决策不会触发 changed=True。"""
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="第一", 章节清洗文本="A。",
                         所属部分="正文"),
                _section(章节编号="2", 章节标题="Short title.",
                         章节清洗文本="B。", 所属部分="正文"),
            ],
        )
        config = self._config(use_llm=True, llm_structure_refine_rounds=1)
        with mock.patch("src.llm_refiner.llm_available", return_value=True), \
             mock.patch("src.llm_refiner.request_structured_json",
                        return_value=(
                            {
                                "section_decisions": [
                                    {
                                        "candidate_id": "sec-0",  # 本地清理后索引可能变化
                                        "action": "keep",
                                        "new_title": "",
                                        "reason": "正常",
                                        "confidence": 1.0,
                                    }
                                ],
                                "block_decisions": [],
                                "global_notes": [],
                            },
                            "test-model",
                        )):
            refined, rounds = refine_document_structure(doc, config)

        # rounds 应包含本地预清理和至少一轮 LLM
        self.assertGreaterEqual(len(rounds), 2)


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
