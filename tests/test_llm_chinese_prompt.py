from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import AppConfig
from src.summarizer import build_summary
from src.tagger import build_tags
from src.text_localization import localize_source_text
from tests.helpers import build_sample_document


class LlmChinesePromptTests(unittest.TestCase):
    def _config(self) -> AppConfig:
        return AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output/test"), use_llm=True)

    def _build_english_document(self):
        document = build_sample_document()
        document.文件元数据.文档标题 = "Flexible hose assemblies"
        document.章节列表[0].章节标题 = "Scope"
        document.章节列表[0].章节清洗文本 = "This document specifies hose assemblies for petroleum based fluids."
        document.数值参数列表[0].参数名称 = "Working pressure"
        document.数值参数列表[0].适用条件 = "Ambient temperature"
        document.规则列表[0].规则类型 = "Requirement"
        document.规则列表[0].规则内容 = "The hose assembly shall remain leak tight."
        return document

    def _build_german_document(self):
        document = build_sample_document()
        document.文件元数据.文档标题 = "Schlauchleitungen"
        document.章节列表[0].章节标题 = "Anwendungsbereich"
        document.章节列表[0].章节清洗文本 = "Die Schlauchleitung ist für verschiedene Medien vorgesehen."
        document.表格列表[0].表格标题 = "Maße in mm"
        document.数值参数列表[0].参数名称 = "Kleinster Biegeradius"
        document.规则列表[0].规则类型 = "Anforderung"
        document.规则列表[0].规则内容 = "Die Leitung muss elektrisch leitfähig sein."
        return document

    def test_summary_llm_prompt_requires_chinese_main_body_for_english_input(self) -> None:
        document = self._build_english_document()
        captured: dict[str, str] = {}

        def fake_request_structured_json(**kwargs):
            captured["system_prompt"] = kwargs["system_prompt"]
            return (
                {
                    "全文摘要": "该文档规定了软管总成的主要适用范围与核心要求。",
                    "章节摘要": [{"章节标题": "适用范围", "摘要": "本章节说明软管总成的适用介质与使用边界。"}],
                    "参数摘要": {"数值型参数": [], "规则型参数": []},
                    "要求摘要": [{"要求类型": "要求", "内容": "应保持密封。", "适用条件": "", "所属章节": "适用范围"}],
                    "引用标准摘要": [],
                },
                "mock-summary",
            )

        with patch("src.summarizer.llm_available", return_value=True), patch(
            "src.summarizer.request_structured_json",
            side_effect=fake_request_structured_json,
        ):
            summary = build_summary(document, self._config())

        self.assertIn("所有输出必须以简体中文为主干", captured["system_prompt"])
        self.assertIn("不要把大段外文原句直接当作摘要正文返回", captured["system_prompt"])
        self.assertIn("如果原料本身已经是中文", captured["system_prompt"])
        self.assertEqual(summary["_llm_backend"], "mock-summary")
        self.assertNotIn("原文：", summary["全文摘要"])
        self.assertEqual(summary["章节摘要"][0]["章节标题"], "适用范围")

    def test_tagger_llm_prompt_requires_chinese_tags_for_german_input(self) -> None:
        document = self._build_german_document()
        captured: dict[str, str] = {}

        def fake_request_structured_json(**kwargs):
            captured["system_prompt"] = kwargs["system_prompt"]
            return (
                {
                    "doc_type_tags": ["标准规范"],
                    "topic_tags": ["适用范围", "尺寸"],
                    "process_tags": [],
                    "parameter_tags": ["弯曲半径"],
                    "inspection_tags": [],
                    "standard_tags": ["SN"],
                    "product_series_tags": [],
                    "product_model_tags": [],
                    "application_tags": ["多种介质"],
                    "certification_tags": [],
                    "defect_tags": [],
                    "weld_type_tags": [],
                    "region_tags": [],
                },
                "mock-tags",
            )

        with patch("src.tagger.llm_available", return_value=True), patch(
            "src.tagger.request_structured_json",
            side_effect=fake_request_structured_json,
        ):
            tags = build_tags(document, self._config())

        self.assertIn("标签必须以简体中文为主", captured["system_prompt"])
        self.assertIn("只有在中文难以代替时才能写成", captured["system_prompt"])
        self.assertIn("不要让标签退化成", captured["system_prompt"])
        self.assertEqual(tags["_llm_backend"], "mock-tags")
        self.assertIn("适用范围", tags["文档主题标签"])
        self.assertNotIn("原文：", "".join(tags["文档主题标签"]))

    def test_mixed_input_preserves_chinese_main_stem_and_foreign_fallback_warns(self) -> None:
        self.assertEqual(localize_source_text("工作压力 working pressure", fallback_prefix="参数项"), "工作压力 working pressure")
        with self.assertLogs("src.text_localization", level="WARNING") as captured:
            localized = localize_source_text("Operating pressure", fallback_prefix="参数项")

        self.assertEqual(localized, "压力（原文：Operating pressure）")
        self.assertIn("安全网已触发", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
