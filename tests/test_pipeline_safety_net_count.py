from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import AppConfig
from src import pipeline
from src.text_localization import localize_display_text, localize_tag_text
from tests.helpers import build_sample_document


class _FakeParser:
    def __init__(self, document) -> None:
        self._document = document

    def parse(self):
        return self._document


class PipelineSafetyNetCountTests(unittest.TestCase):
    def test_process_log_includes_safety_net_trigger_count(self) -> None:
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
            "总分": 100.0,
            "是否通过": True,
            "红线触发": False,
            "红线列表": [],
            "问题清单": [],
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
            result = pipeline.run_iterative_pipeline(
                AppConfig(
                    input_path=Path("sample.pdf"),
                    output_dir=Path("output"),
                )
            )

        self.assertIn("安全网触发次数", result["process_log"])
        self.assertEqual(result["process_log"]["安全网触发次数"], 2)


if __name__ == "__main__":
    unittest.main()
