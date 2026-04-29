from __future__ import annotations

import unittest

from src import reviewer
from tests.helpers import build_sample_document


class ReviewerHitConditionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = build_sample_document()

    def test_summary_structure_flags_count_only_summary_when_chapters_are_low_signal(self) -> None:
        summary = {
            "\u5168\u6587\u6458\u8981": (
                "\u300aKupplungen ohne R\u00fcckschlagventil\u300b\u5f53\u524d\u8bc6\u522b\u4e3a"
                "\u6807\u51c6/\u89c4\u8303\u6587\u6863\u3002\u5df2\u5efa\u7acb 19 \u4e2a\u6b63\u6587"
                "\u7ae0\u8282\u6458\u8981\u3002\u5df2\u62bd\u53d6 63 \u6761\u6570\u503c\u578b\u53c2\u6570\u3002"
                "\u5df2\u8bc6\u522b 13 \u6761\u5f15\u7528\u6807\u51c6\u3002"
            ),
            "\u7ae0\u8282\u6458\u8981": [
                {
                    "\u7ae0\u8282\u6807\u9898": "\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm A\uff09",
                    "\u6458\u8981": "\u5f53\u524d\u4ec5\u7a33\u5b9a\u8bc6\u522b\u5230\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm A\uff09\uff0c\u6b63\u6587\u4ecd\u7136\u8f83\u5c11\u3002",
                },
                {
                    "\u7ae0\u8282\u6807\u9898": "\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm B\uff09",
                    "\u6458\u8981": "\u5f53\u524d\u4ec5\u7a33\u5b9a\u8bc6\u522b\u5230\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm B\uff09\uff0c\u6b63\u6587\u4ecd\u7136\u8f83\u5c11\u3002",
                },
                {
                    "\u7ae0\u8282\u6807\u9898": "Form",
                    "\u6458\u8981": "\u672c\u7ae0\u8282\u4e3b\u8981\u56f4\u7ed5 Form \u5c55\u5f00\uff0c\u5df2\u8bc6\u522b\u5230\u539f\u6587\u6b63\u6587\uff0c\u5f53\u524d\u7ec6\u8282\u4ecd\u4ee5\u539f\u6587\u4e3a\u51c6\u3002",
                },
            ],
        }

        result = reviewer._review_summary_structure(self.document, summary)
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.CHAPTER_SUMMARY_EMPTY, issue_names)
        self.assertIn(reviewer.SUMMARY_TEMPLATE_FALLBACK, issue_names)

    def test_summary_structure_uses_process_log_when_llm_reason_missing(self) -> None:
        """Phase 4.5 P0-2: 当上游异常路径产出无 _llm_reason 的回退 summary 时，
        reviewer 应从 process_log["摘要LLM原因"] 兜底，把模板回退降级为非阻断。"""
        # 模板感强、无 _llm_backend、无 _llm_reason 的 summary——这是 build_summary
        # 异常 fallback 在修复前的产出形态。
        summary = {
            "全文摘要": "当前识别为标准/规范文档。已建立 5 个章节。",
            "章节摘要": [],
        }
        process_log = {"摘要LLM原因": "构建摘要时出错：boom"}

        result = reviewer._review_summary_structure(self.document, summary, process_log=process_log)
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.SUMMARY_FALLBACK_EXPLAINED, issue_names)
        self.assertNotIn(reviewer.SUMMARY_TEMPLATE_FALLBACK, issue_names)

    def test_summary_structure_blocks_when_neither_summary_nor_process_log_has_reason(self) -> None:
        """对照组：summary 与 process_log 都无原因时，仍应触发阻断的 SUMMARY_TEMPLATE_FALLBACK。"""
        summary = {
            "全文摘要": "当前识别为标准/规范文档。已建立 5 个章节。",
            "章节摘要": [],
        }

        result = reviewer._review_summary_structure(self.document, summary, process_log={})
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.SUMMARY_TEMPLATE_FALLBACK, issue_names)
        self.assertNotIn(reviewer.SUMMARY_FALLBACK_EXPLAINED, issue_names)

    def test_summary_structure_summary_reason_takes_precedence_over_process_log(self) -> None:
        """summary 自带 _llm_reason 时优先使用，process_log 是兜底而非覆盖。"""
        summary = {
            "全文摘要": "当前识别为标准/规范文档。已建立 5 个章节。",
            "章节摘要": [],
            "_llm_reason": "配置关闭LLM摘要生成",
        }
        process_log = {"摘要LLM原因": "should-be-ignored"}

        result = reviewer._review_summary_structure(self.document, summary, process_log=process_log)
        explained = [
            item for item in result[reviewer.KEY_ISSUES]
            if item[reviewer.KEY_CONTENT] == reviewer.SUMMARY_FALLBACK_EXPLAINED
        ]
        self.assertEqual(len(explained), 1)
        self.assertIn("配置关闭LLM摘要生成", explained[0][reviewer.KEY_REASON])

    def test_review_outputs_threads_process_log_to_summary_structure(self) -> None:
        """端到端：review_outputs 通过新 kwarg 把 process_log 传到 _review_summary_structure。"""
        summary = {
            "全文摘要": "当前识别为标准/规范文档。已建立 5 个章节。",
            "章节摘要": [],
        }
        process_log = {"摘要LLM原因": "LLM不可用：缺少可用的 OpenAI SDK 或 OPENAI_API_KEY"}

        review_with = reviewer.review_outputs(self.document, "", summary, {}, process_log=process_log)
        review_without = reviewer.review_outputs(self.document, "", summary, {})

        problems_with = [p[reviewer.KEY_PROBLEM_ID] for p in review_with[reviewer.PROBLEMS_KEY]]
        problems_without = [p[reviewer.KEY_PROBLEM_ID] for p in review_without[reviewer.PROBLEMS_KEY]]

        # 带 process_log → 走 SUMMARY_FALLBACK_EXPLAINED（非阻断）
        self.assertIn("summary_fallback_explained", problems_with)
        self.assertNotIn("summary_template_fallback", problems_with)
        # 不带 process_log → 仍是 SUMMARY_TEMPLATE_FALLBACK（阻断）
        self.assertIn("summary_template_fallback", problems_without)

    def test_summary_structure_blocks_when_reason_not_in_whitelist(self) -> None:
        """Phase 4.5 P0-2 反例：非白名单原因（如未知错误字符串）必须保持阻断，
        防止真实缺陷被借'有原因'之名漏过。"""
        summary = {
            "全文摘要": "当前识别为标准/规范文档。已建立 5 个章节。",
            "章节摘要": [],
            "_llm_reason": "未知错误：something exploded",
        }

        result = reviewer._review_summary_structure(self.document, summary)
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.SUMMARY_TEMPLATE_FALLBACK, issue_names)
        self.assertNotIn(reviewer.SUMMARY_FALLBACK_EXPLAINED, issue_names)

    def test_is_benign_llm_reason_whitelist(self) -> None:
        """白名单覆盖 summarizer.py 全部 fallback 路径 + pipeline 来源隔离/异常路径。"""
        for reason in (
            "配置关闭LLM摘要生成",
            "LLM不可用：缺少可用的 OpenAI SDK 或 OPENAI_API_KEY",
            "结构化原料不足，跳过LLM摘要生成",
            "LLM摘要生成失败，已回退到规则摘要",
            "文件名与正文标准号不一致，已隔离常规摘要流程",
            "构建摘要时出错：boom",
            "构建标签时出错：boom",
        ):
            self.assertTrue(
                reviewer._is_benign_llm_reason(reason),
                f"reason should be whitelisted: {reason!r}",
            )
        self.assertFalse(reviewer._is_benign_llm_reason(""))
        self.assertFalse(reviewer._is_benign_llm_reason("未知原因"))

    def test_review_tags_flags_foreign_phrase_parameter_tags(self) -> None:
        tags = {
            "\u53c2\u6570\u6807\u7b7e": [
                "\u91cd\u91cf",
                "verwendet f\u00fcr DN",
            ],
        }

        result = reviewer._review_tags(self.document, tags)
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.NOISY_PARAMETER_TAGS, issue_names)


if __name__ == "__main__":
    unittest.main()
