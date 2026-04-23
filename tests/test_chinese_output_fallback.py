from __future__ import annotations

import unittest
from pathlib import Path

from config import AppConfig
from src.summarizer import build_summary
from src.tagger import build_tags
from src.text_localization import localize_source_text
from tests.helpers import build_sample_document


class ChineseFallbackOutputTests(unittest.TestCase):
    def _build_foreign_document(self):
        document = build_sample_document()
        document.文件元数据.文档标题 = "Niederdruck – Schlauchleitungen"
        document.章节列表[0].章节标题 = "Anwendungsbereich"
        document.章节列表[0].章节清洗文本 = "Die Schlauchleitung ist für verschiedene Medien vorgesehen."
        document.表格列表[0].表格标题 = "Maße in mm"
        document.数值参数列表[0].参数名称 = "Kleinster Biegeradius (bezogen auf Schlauchachse)"
        document.数值参数列表[0].适用条件 = "Nenngröße=N 20"
        document.数值参数列表[0].来源表格 = "Maße in mm"
        document.数值参数列表[0].来源子项 = "Betriebsdruck"
        document.数值参数列表[0].主体锚点.显示名称 = "1 Anwendungsbereich"
        document.规则列表[0].规则类型 = "Anforderung"
        document.规则列表[0].规则内容 = "Die Leitung muss elektrisch leitfähig sein."
        document.规则列表[0].主体锚点.显示名称 = "1 Anwendungsbereich"
        document.引用标准列表[0].标准名称 = "Gummischläuche und Schlauchleitungen"
        document.引用标准列表[0].主体锚点.显示名称 = "5 Zitierte Normen"
        return document

    def test_summary_fallback_wraps_foreign_content_in_chinese(self) -> None:
        document = self._build_foreign_document()
        config = AppConfig(input_path=Path("sample.pdf"), output_dir=Path("output/test"), use_llm=False)

        summary = build_summary(document, config)

        chapter = summary["章节摘要"][0]
        param = summary["参数摘要"]["数值型参数"][0]
        standard = summary["引用标准摘要"][0]

        self.assertIn("适用范围", chapter["章节标题"])
        self.assertIn("本章节主要围绕", chapter["摘要"])
        self.assertIn("弯曲半径", param["参数名称"])
        self.assertIn("公称尺寸条件", param["适用条件"])
        self.assertIn("标准标题", standard["标准概述"])

    def test_tags_fallback_localizes_foreign_topic_titles(self) -> None:
        document = self._build_foreign_document()

        tags = build_tags(document)

        self.assertIn("尺寸", tags["文档主题标签"])
        self.assertNotIn("Anwendungsbereich", tags["文档主题标签"])
        self.assertNotIn("Maße in mm", tags["文档主题标签"])

    def test_short_technical_tokens_are_preserved(self) -> None:
        self.assertEqual(localize_source_text("DN", fallback_prefix="参数项"), "DN")
        self.assertEqual(localize_source_text("d1", fallback_prefix="参数项"), "d1")


if __name__ == "__main__":
    unittest.main()
