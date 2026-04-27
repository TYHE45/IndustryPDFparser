from __future__ import annotations

import unittest
from copy import deepcopy

from src.models import (
    AnchorRef,
    DocumentData,
    DocumentProfile,
    FileMetadata,
    NumericParameter,
    ProductRecord,
    RuleRecord,
    SectionRecord,
    SourceRef,
    StandardReference,
    StructureNode,
)
from tests.helpers import build_sample_document


class NormalizeDocumentTests(unittest.TestCase):
    def test_doc_type_set_from_profile(self):
        doc = build_sample_document()
        doc.文档画像.文档类型 = "manual"
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(result.文件元数据.文档类型, "技术手册")

    def test_sections_deduplicated(self):
        doc = build_sample_document()
        duplicate = SectionRecord(章节编号="1", 章节标题="范围", 章节清洗文本="文本")
        doc.章节列表 = [duplicate, duplicate]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(len(result.章节列表), 1)

    def test_empty_sections_removed(self):
        doc = build_sample_document()
        empty = SectionRecord(章节编号="", 章节标题="", 章节清洗文本="")
        doc.章节列表.append(empty)
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertNotIn(empty, result.章节列表)

    def test_parameters_deduplicated(self):
        doc = build_sample_document()
        from src.normalizer import normalize_document

        param1 = NumericParameter(参数名称="重量", 参数值清洗值="10", 适用条件="", 所属章节="1 范围")
        param2 = NumericParameter(参数名称="重量", 参数值清洗值="10", 适用条件="", 所属章节="1 范围")
        doc.数值参数列表 = [param1, param2]
        result = normalize_document(doc)
        self.assertEqual(len(result.数值参数列表), 1)

    def test_units_normalized(self):
        doc = build_sample_document()
        doc.数值参数列表 = [NumericParameter(参数名称="压力", 参数单位="n/mm2")]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(result.数值参数列表[0].参数单位, "N/mm2")

    def test_um_to_micron(self):
        doc = build_sample_document()
        doc.数值参数列表 = [NumericParameter(参数名称="厚度", 参数单位="um")]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(result.数值参数列表[0].参数单位, "μm")

    def test_products_deduplicated(self):
        doc = build_sample_document()
        anchor = AnchorRef(锚点类型="product", 锚点ID="p1", 显示名称="产品A")
        doc.产品列表 = [
            ProductRecord(产品ID="1", 名称="产品A", 锚点=deepcopy(anchor)),
            ProductRecord(产品ID="2", 名称="产品A", 锚点=deepcopy(anchor)),
        ]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(len(result.产品列表), 1)

    def test_standards_deduplicated(self):
        doc = build_sample_document()
        doc.引用标准列表 = [
            StandardReference(标准编号="GB/T 1234-2020", 所属章节="1 范围"),
            StandardReference(标准编号="GB/T 1234-2020", 所属章节="1 范围"),
        ]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(len(result.引用标准列表), 1)

    def test_rules_deduplicated(self):
        doc = build_sample_document()
        doc.规则列表 = [
            RuleRecord(规则类型="约束", 规则内容="内容", 所属章节="1 范围"),
            RuleRecord(规则类型="约束", 规则内容="内容", 所属章节="1 范围"),
        ]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(len(result.规则列表), 1)

    def test_parameter_enrichment_sets_id(self):
        doc = build_sample_document()
        doc.数值参数列表 = [NumericParameter(参数名称="压力", 参数值清洗值="10", 参数ID="")]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertTrue(result.数值参数列表[0].参数ID.startswith("param-"))

    def test_parameter_enrichment_sets_confidence(self):
        doc = build_sample_document()
        doc.数值参数列表 = [NumericParameter(参数名称="压力", 参数值清洗值="10", 置信度=0.0)]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(result.数值参数列表[0].置信度, 0.75)

    def test_parameter_name_canonicalization(self):
        doc = build_sample_document()
        doc.数值参数列表 = [NumericParameter(参数名称="Weight", 参数值清洗值="5")]
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertEqual(result.数值参数列表[0].参数名称, "重量")

    def test_build_nodes_from_sections(self):
        doc = build_sample_document()
        doc.结构节点列表 = []
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        self.assertTrue(len(result.结构节点列表) > 0)

    def test_profile_not_set(self):
        doc = build_sample_document()
        doc.文档画像 = None
        from src.normalizer import normalize_document

        result = normalize_document(doc)
        # Should not crash, doc type unchanged
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
