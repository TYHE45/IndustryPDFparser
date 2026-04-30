from __future__ import annotations

import unittest
from unittest import mock
from pathlib import Path

from config import AppConfig
from src.context import PipelineContext
from src.models import (
    DocumentData,
    FileMetadata,
    SectionRecord,
    TableRecord,
    BlockRecord,
    PageRecord,
    NumericParameter,
    RuleRecord,
    InspectionRecord,
    StandardReference,
    DocumentProfile,
)
from src.fixer import (
    classify_fix_actions,
    apply_fixes,
    _map_problem_to_action,
    _infer_module_from_action,
    _clean_noisy_tags,
)


# ═══════════════════════════════════════════════════════════════════════════
# Module-level factory helpers
# ═══════════════════════════════════════════════════════════════════════════

def _meta(**overrides):
    defaults = dict(
        文件名称="test.pdf",
        文件类型="pdf",
        文档标题="测试",
        文档类型="standard",
        标准编号="G1",
        版本日期="2024",
        适用范围="test",
    )
    return FileMetadata(**(defaults | overrides))


def _section(**overrides):
    defaults = dict(
        章节编号="1",
        章节标题="概述",
        章节层级=1,
        章节清洗文本="正文。",
        所属部分="正文",
    )
    return SectionRecord(**(defaults | overrides))


def _page(**overrides):
    defaults = dict(
        页码索引=0,
        原始文本="正文内容\n段落文本。",
    )
    return PageRecord(**(defaults | overrides))


def _doc(**overrides):
    return DocumentData(文件元数据=_meta(), **(overrides))


# ═══════════════════════════════════════════════════════════════════════════
# 1. MapProblemToActionTests
# ═══════════════════════════════════════════════════════════════════════════

class MapProblemToActionTests(unittest.TestCase):
    """单元测试 _map_problem_to_action：问题标识到修正动作的映射。"""

    def test_rerun_parser_all_seven(self):
        positions = [
            "正文主链缺失",
            "结构未建立",
            "结构主线缺失",
            "表格未转化为参数",
            "表格未消费",
            "标准实体缺失",
            "OCR标题噪音明显",
        ]
        for pos in positions:
            with self.subTest(position=pos):
                self.assertEqual(_map_problem_to_action(pos), "重跑parser")

    def test_ocr_block_both(self):
        self.assertEqual(_map_problem_to_action("疑似扫描件"), "标记需OCR")
        self.assertEqual(_map_problem_to_action("OCR覆盖不足"), "标记需OCR")

    def test_rebuild_markdown_all_three(self):
        positions = [
            "markdown内容过少",
            "表格视图缺失",
            "自动表标题残留",
        ]
        for pos in positions:
            with self.subTest(position=pos):
                self.assertEqual(_map_problem_to_action(pos), "重建markdown")

    def test_rebuild_summary_all_three(self):
        positions = [
            "章节摘要为空",
            "参数摘要为空",
            "摘要疑似模板回退",
        ]
        for pos in positions:
            with self.subTest(position=pos):
                self.assertEqual(_map_problem_to_action(pos), "重建summary")

    def test_rebuild_tags_all_five(self):
        positions = [
            "标准引用标签为空",
            "参数标签为空",
            "产品型号标签为空",
            "关键标签缺失",
            "标签存在句子污染",
        ]
        for pos in positions:
            with self.subTest(position=pos):
                self.assertEqual(_map_problem_to_action(pos), "重建tags")

    def test_clean_tags_both(self):
        self.assertEqual(_map_problem_to_action("参数标签存在噪音"), "清洗标签噪音")
        self.assertEqual(_map_problem_to_action("OCR参数污染明显"), "清洗标签噪音")

    def test_unknown_position_returns_none(self):
        self.assertEqual(_map_problem_to_action("不存在的标识"), "无可用自动修正")

    def test_empty_string_returns_none(self):
        self.assertEqual(_map_problem_to_action(""), "无可用自动修正")

    def test_case_sensitive(self):
        # Lowercase or mixed-case should not match the exact Chinese identifiers
        self.assertEqual(_map_problem_to_action("scan_like"), "无可用自动修正")
        self.assertEqual(_map_problem_to_action("疑似扫描件 "), "无可用自动修正")


# ═══════════════════════════════════════════════════════════════════════════
# 2. InferModuleFromActionTests
# ═══════════════════════════════════════════════════════════════════════════

class InferModuleFromActionTests(unittest.TestCase):
    """单元测试 _infer_module_from_action：动作到根因模块的推断。"""

    def test_rerun_parser(self):
        self.assertEqual(_infer_module_from_action("重跑parser"), "parser")

    def test_ocr_block(self):
        self.assertEqual(_infer_module_from_action("标记需OCR"), "ocr")

    def test_rebuild_markdown(self):
        self.assertEqual(_infer_module_from_action("重建markdown"), "md_builder")

    def test_rebuild_summary(self):
        self.assertEqual(_infer_module_from_action("重建summary"), "summarizer")

    def test_rebuild_tags(self):
        self.assertEqual(_infer_module_from_action("重建tags"), "tagger")

    def test_clean_tags(self):
        self.assertEqual(_infer_module_from_action("清洗标签噪音"), "fixer")

    def test_unknown_action(self):
        self.assertEqual(_infer_module_from_action("不存在的动作"), "")


# ═══════════════════════════════════════════════════════════════════════════
# 3. CleanNoisyTagsTests
# ═══════════════════════════════════════════════════════════════════════════

class CleanNoisyTagsTests(unittest.TestCase):
    """单元测试 _clean_noisy_tags：参数标签噪音清洗。"""

    def test_empty_param_tags(self):
        tags = {"参数标签": []}
        result = _clean_noisy_tags(tags)
        self.assertEqual(result["参数标签"], [])

    def test_no_noise_all_kept(self):
        tags = {"参数标签": ["工作压力", "温度范围"]}
        result = _clean_noisy_tags(tags)
        self.assertEqual(result["参数标签"], ["工作压力", "温度范围"])

    def test_digit_noise_removed(self):
        tags = {"参数标签": ["1. 2. 3.", "有效标签"]}
        result = _clean_noisy_tags(tags)
        self.assertEqual(result["参数标签"], ["有效标签"])

    def test_letter_noise_removed(self):
        # "a b c" has 3 short letter sequences → noise
        # "x" has only 1 short letter → kept (regex {2,} requires 2+ sequences)
        tags = {"参数标签": ["a b c", "x", "有效标签"]}
        result = _clean_noisy_tags(tags)
        self.assertEqual(result["参数标签"], ["x", "有效标签"])

    def test_non_list_param_tags_unchanged(self):
        tags = {"参数标签": "not a list"}
        result = _clean_noisy_tags(tags)
        self.assertEqual(result["参数标签"], "not a list")

    def test_other_keys_preserved(self):
        tags = {"参数标签": ["标签A"], "主题标签": ["主题1"]}
        result = _clean_noisy_tags(tags)
        self.assertIn("参数标签", result)
        self.assertIn("主题标签", result)
        self.assertEqual(result["主题标签"], ["主题1"])


# ═══════════════════════════════════════════════════════════════════════════
# 4. ClassifyFixActionsTests
# ═══════════════════════════════════════════════════════════════════════════

def _problem(position="", action="", module="", level="B", blocking=False):
    return {
        "级别": level,
        "位置": position,
        "修正动作": action,
        "根因模块": module,
        "是否阻断": blocking,
    }


def _review(problems):
    return {"问题清单": problems}


class ClassifyFixActionsTests(unittest.TestCase):
    """单元测试 classify_fix_actions：评审结果到修正动作列表的分类。"""

    def test_empty_problem_list(self):
        result = classify_fix_actions(_review([]))
        self.assertEqual(result, [])

    def test_missing_问题清单_key(self):
        result = classify_fix_actions({})
        self.assertEqual(result, [])

    def test_single_problem_with_explicit_action(self):
        result = classify_fix_actions(_review([_problem(action="重跑parser", module="parser")]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["动作"], "重跑parser")
        self.assertEqual(result[0]["模块"], "parser")

    def test_action_mapped_from_position_when_empty(self):
        result = classify_fix_actions(_review([_problem(position="正文主链缺失")]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["动作"], "重跑parser")

    def test_skip_action_none_when_position_unknown(self):
        result = classify_fix_actions(_review([_problem(position="unknown")]))
        self.assertEqual(result, [])

    def test_dedup_by_action_module_tuple(self):
        problems = [
            _problem(action="重跑parser", module="parser"),
            _problem(action="重跑parser", module="parser"),
        ]
        result = classify_fix_actions(_review(problems))
        self.assertEqual(len(result), 1)

    def test_no_dedup_different_module(self):
        problems = [
            _problem(action="重跑parser", module="parser"),
            _problem(action="重跑parser", module="other"),
        ]
        result = classify_fix_actions(_review(problems))
        self.assertEqual(len(result), 2)

    def test_blocking_true_when_key_blocking_set(self):
        result = classify_fix_actions(_review([_problem(action="重建summary", blocking=True)]))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["是否阻断"])

    def test_blocking_true_when_action_is_ocr_block(self):
        result = classify_fix_actions(_review([_problem(action="标记需OCR")]))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["是否阻断"])

    def test_blocking_false_default(self):
        result = classify_fix_actions(_review([_problem(action="重建summary")]))
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["是否阻断"])

    def test_sort_by_level_S_A_B(self):
        problems = [
            _problem(action="清洗标签噪音", level="B"),
            _problem(action="标记需OCR", level="A"),
            _problem(action="重跑parser", level="S"),
        ]
        result = classify_fix_actions(_review(problems))
        levels = [item["级别"] for item in result]
        self.assertEqual(levels, ["S", "A", "B"])

    def test_sort_same_level_by_action_priority(self):
        problems = [
            _problem(action="清洗标签噪音", level="B"),
            _problem(action="重建tags", level="B"),
            _problem(action="重建markdown", level="B"),
        ]
        result = classify_fix_actions(_review(problems))
        actions = [item["动作"] for item in result]
        self.assertEqual(actions, ["重建markdown", "重建tags", "清洗标签噪音"])

    def test_sort_level_priority_beats_action_priority(self):
        problems = [
            _problem(action="清洗标签噪音", level="S"),
            _problem(action="标记需OCR", level="A"),
        ]
        result = classify_fix_actions(_review(problems))
        levels = [item["级别"] for item in result]
        self.assertEqual(levels, ["S", "A"])
        self.assertEqual(result[0]["动作"], "清洗标签噪音")

    def test_module_from_explicit_root_module(self):
        result = classify_fix_actions(_review([_problem(action="重跑parser", module="custom_module")]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["模块"], "custom_module")

    def test_module_inferred_when_no_root_module(self):
        result = classify_fix_actions(_review([_problem(action="重建markdown")]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["模块"], "md_builder")

    def test_default_level_B_when_missing_key(self):
        result = classify_fix_actions(_review([{"位置": "正文主链缺失"}]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["级别"], "B")

    def test_return_items_shape(self):
        result = classify_fix_actions(_review([_problem(action="标记需OCR", position="疑似扫描件")]))
        self.assertEqual(len(result), 1)
        item = result[0]
        keys = {"动作", "模块", "原因", "级别", "是否阻断"}
        self.assertEqual(set(item.keys()), keys)
        self.assertEqual(item["动作"], "标记需OCR")
        self.assertEqual(item["模块"], "ocr")
        self.assertEqual(item["原因"], "疑似扫描件")
        self.assertEqual(item["级别"], "B")
        self.assertTrue(item["是否阻断"])

    def test_rerun_parser_blocks_even_if_false_explicitly(self):
        # 重跑parser 本身不强制 blocking，只有 标记需OCR 才强制
        result = classify_fix_actions(_review([_problem(action="重跑parser", blocking=False)]))
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["是否阻断"])

    def test_multiple_unique_actions_no_duplicates(self):
        problems = [
            _problem(action="重跑parser", module="parser"),
            _problem(action="重建markdown", module="md_builder"),
            _problem(action="重建summary", module="summarizer"),
        ]
        result = classify_fix_actions(_review(problems))
        self.assertEqual(len(result), 3)

    def test_empty_action_with_known_position_fills_action(self):
        result = classify_fix_actions(_review([_problem(position="疑似扫描件", action="")]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["动作"], "标记需OCR")


# ═══════════════════════════════════════════════════════════════════════════
# 5. ApplyFixesNoOCRTests
# ═══════════════════════════════════════════════════════════════════════════

class ApplyFixesNoOCRTests(unittest.TestCase):
    """集成测试 apply_fixes：非 OCR 修正路径。"""

    def setUp(self):
        self.config = AppConfig(input_path=Path("/fake/input.pdf"), output_dir=Path("/fake/output"))
        self.context = PipelineContext()

    def _base_actions(self, action_names):
        return [{"动作": name, "模块": _infer_module_from_action(name), "原因": "", "级别": "B", "是否阻断": False} for name in action_names]

    def test_no_actions_returns_identity(self):
        doc = _doc()
        result = apply_fixes(doc, self.config, [], "md", {"s": "s"}, {"t": "t"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result
        self.assertIs(new_doc, doc)
        self.assertEqual(md, "md")
        self.assertEqual(summary, {"s": "s"})
        self.assertEqual(tags, {"t": "t"})
        self.assertIn("无可执行的自动修正。", fix_log)
        self.assertIsNone(stop_reason)

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    @mock.patch("src.fixer.refine_document_structure")
    @mock.patch("src.fixer.normalize_document")
    @mock.patch("src.fixer.PDFParser")
    def test_rerun_parser_rebuilds_all(
        self,
        mock_parser,
        mock_norm,
        mock_refine,
        mock_md,
        mock_sum,
        mock_tags,
    ):
        mock_instance = mock.MagicMock()
        mock_instance.parse.return_value = _doc()
        mock_parser.return_value = mock_instance
        mock_norm.return_value = _doc()
        mock_refine.return_value = (_doc(), False)
        mock_md.return_value = "# new md"
        mock_sum.return_value = {"new": "summary"}
        mock_tags.return_value = {"new": "tags"}

        actions = [{"动作": "重跑parser", "模块": "parser", "原因": "", "级别": "S", "是否阻断": False}]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, {"old": "tags"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        mock_instance.parse.assert_called_once()
        mock_norm.assert_called_once()
        mock_refine.assert_called_once()
        mock_md.assert_called_once()
        mock_sum.assert_called_once()
        mock_tags.assert_called_once()
        self.assertEqual(md, "# new md")
        self.assertEqual(summary, {"new": "summary"})
        self.assertEqual(tags, {"new": "tags"})
        self.assertIn("重跑了解析主链", fix_log[0])
        self.assertIsNone(stop_reason)

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    @mock.patch("src.fixer.refine_document_structure")
    @mock.patch("src.fixer.normalize_document")
    @mock.patch("src.fixer.PDFParser")
    def test_rerun_parser_with_clean_tags(
        self,
        mock_parser,
        mock_norm,
        mock_refine,
        mock_md,
        mock_sum,
        mock_tags,
    ):
        mock_instance = mock.MagicMock()
        mock_instance.parse.return_value = _doc()
        mock_parser.return_value = mock_instance
        mock_norm.return_value = _doc()
        mock_refine.return_value = (_doc(), False)
        mock_md.return_value = "# new md"
        mock_sum.return_value = {"new": "summary"}
        mock_tags.return_value = {"参数标签": ["1. 2. 3.", "有效标签"]}

        actions = [
            {"动作": "重跑parser", "模块": "parser", "原因": "", "级别": "S", "是否阻断": False},
            {"动作": "清洗标签噪音", "模块": "fixer", "原因": "", "级别": "B", "是否阻断": False},
        ]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, {"old": "tags"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        mock_tags.assert_called_once()
        # _clean_noisy_tags should have filtered the digit noise
        self.assertEqual(tags["参数标签"], ["有效标签"])
        self.assertIn("在重建 tags 后额外清洗了标签噪音。", fix_log)

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    @mock.patch("src.fixer.refine_document_structure")
    @mock.patch("src.fixer.normalize_document")
    @mock.patch("src.fixer.PDFParser")
    def test_rebuild_markdown_only(
        self,
        mock_parser,
        mock_norm,
        mock_refine,
        mock_md,
        mock_sum,
        mock_tags,
    ):
        mock_md.return_value = "# rebuilt md"

        actions = [{"动作": "重建markdown", "模块": "md_builder", "原因": "", "级别": "B", "是否阻断": False}]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, {"old": "tags"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        mock_md.assert_called_once()
        mock_sum.assert_not_called()
        mock_tags.assert_not_called()
        mock_parser.assert_not_called()
        self.assertEqual(md, "# rebuilt md")
        self.assertEqual(summary, {"old": "sum"})
        self.assertEqual(tags, {"old": "tags"})


# ═══════════════════════════════════════════════════════════════════════════
# 6. ApplyFixesRebuildAndCleanTests
# ═══════════════════════════════════════════════════════════════════════════

class ApplyFixesRebuildAndCleanTests(unittest.TestCase):
    """集成测试 apply_fixes：重建 summary / tags / 清洗标签。"""

    def setUp(self):
        self.config = AppConfig(input_path=Path("/fake/input.pdf"), output_dir=Path("/fake/output"))
        self.context = PipelineContext()

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    def test_rebuild_summary_only(self, mock_md, mock_sum, mock_tags):
        mock_sum.return_value = {"rebuilt": "summary"}
        actions = [{"动作": "重建summary", "模块": "summarizer", "原因": "", "级别": "B", "是否阻断": False}]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, {"old": "tags"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        mock_sum.assert_called_once()
        mock_md.assert_not_called()
        mock_tags.assert_not_called()
        self.assertEqual(md, "old_md")
        self.assertEqual(summary, {"rebuilt": "summary"})
        self.assertEqual(tags, {"old": "tags"})

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    def test_rebuild_tags_only(self, mock_md, mock_sum, mock_tags):
        mock_tags.return_value = {"参数标签": ["新标签"]}
        actions = [{"动作": "重建tags", "模块": "tagger", "原因": "", "级别": "B", "是否阻断": False}]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, {"old": "tags"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        mock_tags.assert_called_once()
        mock_md.assert_not_called()
        mock_sum.assert_not_called()
        self.assertEqual(tags, {"参数标签": ["新标签"]})

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    def test_clean_tags_only(self, mock_md, mock_sum, mock_tags):
        actions = [{"动作": "清洗标签噪音", "模块": "fixer", "原因": "", "级别": "B", "是否阻断": False}]
        doc = _doc()
        existing_tags = {"参数标签": ["1. 2. 3.", "有效标签"]}
        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, existing_tags, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        mock_tags.assert_not_called()  # REBUILD_TAGS not in actions
        mock_md.assert_not_called()
        mock_sum.assert_not_called()
        self.assertEqual(tags["参数标签"], ["有效标签"])
        self.assertIn("清洗了标签噪音。", fix_log)


# ═══════════════════════════════════════════════════════════════════════════
# 7. ApplyFixesOCRBlockTests
# ═══════════════════════════════════════════════════════════════════════════

class ApplyFixesOCRBlockTests(unittest.TestCase):
    """集成测试 apply_fixes：OCR 阻断修正路径。"""

    def setUp(self):
        self.config = AppConfig(input_path=Path("/fake/input.pdf"), output_dir=Path("/fake/output"))
        self.context = PipelineContext()

    def test_ocr_block_ocr_disabled(self):
        self.config.ocr_enabled = False
        actions = [{"动作": "标记需OCR", "模块": "ocr", "原因": "", "级别": "A", "是否阻断": True}]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "md", {}, {}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result
        self.assertIn("OCR 已在配置中禁用", stop_reason)

    @mock.patch("src.fixer._OCR_IMPORT_OK", False)
    def test_ocr_block_import_not_ok(self):
        actions = [{"动作": "标记需OCR", "模块": "ocr", "原因": "", "级别": "A", "是否阻断": True}]
        doc = _doc()
        result = apply_fixes(doc, self.config, actions, "md", {}, {}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result
        self.assertIn("PaddleOCR 不可用", stop_reason)

    @mock.patch("src.fixer._OCR_IMPORT_OK", True)
    @mock.patch("src.fixer.needs_ocr_by_text_layer")
    def test_ocr_block_no_pages_need_ocr_stop(self, mock_needs):
        mock_needs.return_value = (False, [], {})

        actions = [{"动作": "标记需OCR", "模块": "ocr", "原因": "", "级别": "A", "是否阻断": True}]
        doc = _doc(页面列表=[_page(页码索引=0, 原始文本="充分文本内容\n第二行。")])
        result = apply_fixes(doc, self.config, actions, "md", {}, {}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result
        self.assertEqual(stop_reason, "没有需要 OCR 的页")

    @mock.patch("src.fixer.build_tags")
    @mock.patch("src.fixer.build_summary")
    @mock.patch("src.fixer.build_markdown")
    @mock.patch("src.fixer.refine_document_structure")
    @mock.patch("src.fixer.normalize_document")
    @mock.patch("src.fixer.PDFParser")
    @mock.patch("src.fixer.run_table_structure_on_pages")
    @mock.patch("src.fixer.run_ocr_on_pages")
    @mock.patch("src.fixer.get_engine_version")
    @mock.patch("src.fixer.build_ocr_runtime_plan")
    @mock.patch("src.fixer.build_force_ocr_payload")
    @mock.patch("src.fixer.build_page_eval_map")
    @mock.patch("src.fixer.evaluate_ocr_batch")
    @mock.patch("src.fixer.needs_ocr_by_text_layer")
    @mock.patch("src.fixer._OCR_IMPORT_OK", True)
    def test_ocr_block_full_flow(
        self,
        mock_needs,
        mock_eval,
        mock_page_eval_map,
        mock_force_payload,
        mock_build_runtime,
        mock_engine_version,
        mock_run_ocr,
        mock_run_table,
        mock_parser,
        mock_norm,
        mock_refine,
        mock_md,
        mock_sum,
        mock_tags,
    ):
        # ── Phase 1: needs_ocr_by_text_layer returns True ──
        mock_needs.return_value = (True, ["low_chars"], {})

        # ── Phase 2: build OCR runtime plan ──
        runtime_plan = {
            "page_count": 1,
            "requested_dpi": 300,
            "effective_dpi": 300,
            "dpi_downgraded": False,
            "batch_size": 6,
            "timeout_seconds": 180.0,
        }
        mock_build_runtime.return_value = runtime_plan

        # ── Phase 3: run OCR on pages ──
        ocr_map = {0: "OCR识别文本"}
        ocr_runtime = {"elapsed": 1.2, "timed_out": False}
        mock_run_ocr.return_value = (ocr_map, ocr_runtime)

        # ── Phase 4: get engine version ──
        mock_engine_version.return_value = "v3"

        # ── Phase 5: evaluate OCR batch ──
        mock_batch_eval = mock.MagicMock()
        mock_batch_eval.识别成功页数 = 1
        mock_batch_eval.目标页数 = 1
        mock_batch_eval.OCR引擎 = "PaddleOCR v3"
        mock_batch_eval.to_dict.return_value = {"pages": 1}
        mock_eval.return_value = mock_batch_eval

        # ── Phase 6: build page eval map ──
        mock_page_eval_map.return_value = {0: {"OCR来源": "PaddleOCR v3"}}

        # ── Phase 7: build force OCR payload ──
        mock_force_payload.return_value = {0: "OCR识别文本"}

        # ── Phase 8: run table structure ──
        mock_run_table.return_value = ({}, {"命中页码列表": []})

        # ── Phase 9: PDFParser / normalize / refine / build ──
        mock_instance = mock.MagicMock()
        mock_instance.parse.return_value = _doc()
        mock_parser.return_value = mock_instance
        mock_norm.return_value = _doc()
        mock_refine.return_value = (_doc(), False)
        mock_md.return_value = "# final md"
        mock_sum.return_value = {"final": "summary"}
        mock_tags.return_value = {"final": "tags"}

        doc = _doc(页面列表=[_page(页码索引=0, 原始文本="short")])
        actions = [{"动作": "标记需OCR", "模块": "ocr", "原因": "", "级别": "A", "是否阻断": True}]

        result = apply_fixes(doc, self.config, actions, "old_md", {"old": "sum"}, {"old": "tags"}, self.context)
        new_doc, md, summary, tags, fix_log, stop_reason, fix_meta = result

        # Verify the full chain ran
        mock_needs.assert_called_once()
        mock_build_runtime.assert_called_once()
        mock_run_ocr.assert_called_once()
        mock_eval.assert_called_once()
        mock_page_eval_map.assert_called_once()
        mock_force_payload.assert_called_once()
        mock_run_table.assert_called_once()
        mock_instance.parse.assert_called_once()
        mock_norm.assert_called_once()
        mock_refine.assert_called_once()
        mock_md.assert_called_once()
        mock_sum.assert_called_once()
        mock_tags.assert_called_once()

        # Verify outputs
        self.assertIsNone(stop_reason)
        self.assertEqual(md, "# final md")
        self.assertEqual(summary, {"final": "summary"})
        self.assertEqual(tags, {"final": "tags"})
        # force_ocr_pages should be set on the context
        self.assertEqual(self.context.force_ocr_pages, {0: "OCR识别文本"})


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
