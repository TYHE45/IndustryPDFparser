from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

from src import reviewer
from tests.helpers import build_sample_document


def _empty_review(*, include_pseudo_titles: bool = True) -> dict[str, list[dict[str, str]]]:
    payload: dict[str, list[dict[str, str]]] = {
        reviewer.KEY_ISSUES: [],
    }
    if include_pseudo_titles:
        payload[reviewer.PSEUDO_HEADINGS] = []
    return payload


def _issue(content: str, reason: str) -> dict[str, str]:
    return {
        reviewer.KEY_CONTENT: content,
        reviewer.KEY_REASON: reason,
    }


class ReviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = build_sample_document()
        self.markdown = "# 1 范围\n用于测试评分契约。"

    def _patch_reviews(
        self,
        *,
        markdown: dict | None = None,
        summary_structure: dict | None = None,
        summary_facts: dict | None = None,
        summary_stub: dict | None = None,
        tags: dict | None = None,
        sources: dict | None = None,
        ocr: dict | None = None,
    ) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch("src.reviewer._review_markdown", return_value=markdown or _empty_review()))
        stack.enter_context(patch("src.reviewer._review_summary_structure", return_value=summary_structure or _empty_review(include_pseudo_titles=False)))
        stack.enter_context(patch("src.reviewer._review_summary_facts", return_value=summary_facts or _empty_review(include_pseudo_titles=False)))
        stack.enter_context(patch("src.reviewer._review_summary_llm_stub", return_value=summary_stub or _empty_review(include_pseudo_titles=False)))
        stack.enter_context(patch("src.reviewer._review_tags", return_value=tags or _empty_review(include_pseudo_titles=False)))
        stack.enter_context(patch("src.reviewer._review_sources", return_value=sources or _empty_review(include_pseudo_titles=False)))
        stack.enter_context(patch("src.reviewer._review_ocr_quality", return_value=ocr or _empty_review(include_pseudo_titles=False)))
        return stack

    def test_review_outputs_returns_unified_contract_when_passed(self) -> None:
        with self._patch_reviews():
            result = reviewer.review_outputs(self.document, self.markdown, {}, {})

        expected_keys = {
            "轮次",
            "总分",
            "是否通过",
            "基础质量分",
            "事实正确性分",
            "一致性与可追溯性分",
            "红线触发",
            "红线列表",
            "问题清单",
            "问题统计",
            "分项评分",
            "文档类型",
        }
        self.assertTrue(expected_keys.issubset(result.keys()))
        self.assertEqual(result["总分"], 100.0)
        self.assertTrue(result["是否通过"])
        self.assertFalse(result["红线触发"])
        self.assertEqual(result["红线列表"], [])

    def test_review_outputs_caps_total_score_when_redline_triggered(self) -> None:
        markdown_review = _empty_review()
        markdown_review[reviewer.KEY_ISSUES] = [
            _issue(reviewer.DOC_CHAIN_MISSING, "正文主链未建立。"),
        ]
        with self._patch_reviews(markdown=markdown_review):
            result = reviewer.review_outputs(self.document, self.markdown, {}, {})

        self.assertFalse(result["是否通过"])
        self.assertTrue(result["红线触发"])
        self.assertEqual(result["总分"], reviewer.REDLINE_CAP)
        self.assertEqual(result["红线列表"][0]["红线名称"], reviewer.DOC_CHAIN_MISSING)

    def test_review_outputs_enforces_85_point_threshold_without_redline(self) -> None:
        markdown_review = _empty_review()
        markdown_review[reviewer.KEY_ISSUES] = [
            _issue(reviewer.MARKDOWN_TOO_SHORT, "markdown 正文过短。"),
        ]
        summary_fact_review = _empty_review(include_pseudo_titles=False)
        summary_fact_review[reviewer.KEY_ISSUES] = [
            _issue(reviewer.PARAM_SUMMARY_EMPTY, "参数摘要为空。"),
        ]

        with self._patch_reviews(markdown=markdown_review, summary_facts=summary_fact_review):
            result = reviewer.review_outputs(self.document, self.markdown, {}, {})

        self.assertFalse(result["红线触发"])
        self.assertEqual(result["总分"], 84.0)
        self.assertFalse(result["是否通过"])


if __name__ == "__main__":
    unittest.main()
