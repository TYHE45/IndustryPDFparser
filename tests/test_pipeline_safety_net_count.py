from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import AppConfig
from src import pipeline
from src.contracts import KEY_PASSED, KEY_PROBLEMS, KEY_REDLINE_TRIGGERED, KEY_TOTAL_SCORE
from src.text_localization import localize_display_text, localize_tag_text
from tests.helpers import build_sample_document


class _FakeParser:
    def __init__(self, document) -> None:
        self._document = document

    def parse(self):
        return self._document


def _run_pipeline_with_two_safety_net_hits() -> dict[str, object]:
    """驱动一轮 pipeline，同时触发 display 与 tag 两类 safety-net warning。

    所有 safety-net-trigger-count 相关的测试共享同一份夹具，减少重复 patch。
    """

    document = build_sample_document()

    def _build_summary(*args, **kwargs):
        return {
            "全文摘要": localize_display_text("1 Scope", fallback_prefix="适用范围"),
        }

    def _build_tags(*args, **kwargs):
        return {
            "文档主题标签": [localize_tag_text("Material and design")],
        }

    review = {
        KEY_TOTAL_SCORE: 100.0,
        KEY_PASSED: True,
        KEY_REDLINE_TRIGGERED: False,
        "红线列表": [],
        KEY_PROBLEMS: [],
        "问题统计": {},
        "分项评分": {},
    }

    with patch("src.pipeline.PDFParser", return_value=_FakeParser(document)), patch(
        "src.pipeline.normalize_document",
        side_effect=lambda item: item,
    ), patch(
        "src.pipeline.refine_document_structure",
        return_value=(document, []),
    ), patch(
        "src.pipeline.build_markdown",
        return_value="# 1 范围\n测试正文",
    ), patch(
        "src.pipeline.build_summary",
        side_effect=_build_summary,
    ), patch(
        "src.pipeline.build_tags",
        side_effect=_build_tags,
    ), patch(
        "src.pipeline.detect_metadata_mismatch_reason",
        return_value="",
    ), patch(
        "src.pipeline.review_outputs",
        return_value=review,
    ):
        return pipeline.run_iterative_pipeline(
            AppConfig(
                input_path=Path("sample.pdf"),
                output_dir=Path("output"),
            )
        )


class PipelineSafetyNetCountTests(unittest.TestCase):
    def test_process_log_includes_safety_net_trigger_count(self) -> None:
        result = _run_pipeline_with_two_safety_net_hits()
        self.assertIn("安全网触发次数", result["process_log"])
        self.assertEqual(result["process_log"]["安全网触发次数"], 2)

    def test_process_log_includes_safety_net_trigger_detail(self) -> None:
        result = _run_pipeline_with_two_safety_net_hits()
        self.assertIn("安全网触发明细", result["process_log"])
        detail = result["process_log"]["安全网触发明细"]
        self.assertIsInstance(detail, dict)
        self.assertEqual(set(detail.keys()), {"显示", "来源", "条件", "标签"})
        self.assertGreaterEqual(detail["显示"], 1)
        self.assertGreaterEqual(detail["标签"], 1)
        self.assertEqual(
            sum(detail.values()),
            result["process_log"]["安全网触发次数"],
        )


if __name__ == "__main__":
    unittest.main()
