from __future__ import annotations

import unittest

from src import reviewer
from src.models import PageRecord, SectionRecord, StructureNode
from tests.helpers import build_sample_document


class ReviewerOcrQualityTests(unittest.TestCase):
    def _ocr_page(self, text: str) -> PageRecord:
        return PageRecord(
            页码索引=1,
            原始文本=text,
            是否执行OCR=True,
            OCR来源="paddleocr",
            OCR评估等级="pass",
            OCR是否注入解析=True,
            OCR有效字符数=len(text),
        )

    def test_review_ocr_quality_flags_missing_standard_entity_from_ocr_text(self) -> None:
        document = build_sample_document()
        document.引用标准列表 = []
        document.页面列表 = [self._ocr_page("DIN EN 853\nScope of application\nOperating pressure 10 bar")]

        result = reviewer._review_ocr_quality(document, "# 1 Scope\n正文内容")

        issues = {item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]}
        self.assertIn(reviewer.STANDARD_ENTITY_MISSING, issues)

    def test_review_ocr_quality_flags_missing_core_table_when_ocr_result_is_table_driven(self) -> None:
        document = build_sample_document()
        document.表格列表 = []
        document.数值参数列表 = []
        document.页面列表 = [
            self._ocr_page("Table 1\nDimensions in mm\nOperating pressure bar dynamic static\nDN 20"),
        ]

        result = reviewer._review_ocr_quality(document, "# 1 Scope\nDN 20\n压力范围")

        issues = {item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]}
        self.assertIn(reviewer.TABLE_CORE_MISSING, issues)

    def test_review_ocr_quality_flags_weak_backbone_after_ocr_recovery(self) -> None:
        document = build_sample_document()
        document.章节列表 = [SectionRecord(章节编号="U1", 章节标题="概述", 章节层级=1, 章节清洗文本="", 所属部分="正文")]
        document.结构节点列表 = [StructureNode(节点ID="node-u1", 节点类型="section", 节点标题="概述", 节点层级=1)]
        document.数值参数列表 = []
        document.引用标准列表 = []
        document.规则列表 = []
        document.表格列表 = []
        document.页面列表 = [self._ocr_page("Recovered OCR paragraph with limited body text only.")]

        result = reviewer._review_ocr_quality(document, "# U1 概述")

        issues = {item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]}
        self.assertIn(reviewer.STRUCTURED_BACKBONE_MISSING, issues)


if __name__ == "__main__":
    unittest.main()
