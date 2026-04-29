from __future__ import annotations

import unittest
from collections import OrderedDict

from src.models import DocumentData, FileMetadata, SectionRecord, StandardReference, TableRecord
from src.md_builder import (
    _clean_body,
    _collect_standards,
    _should_render_table_heading,
    _should_suppress_section_heading,
    build_markdown,
)


# ═══════════════════════════════════════════════════════════════════════════
# Module-level factory helpers
# ═══════════════════════════════════════════════════════════════════════════

def _meta(**overrides) -> FileMetadata:
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


def _section(**overrides) -> SectionRecord:
    defaults = dict(
        章节编号="1",
        章节标题="概述",
        章节层级=1,
        父章节编号="",
        章节清洗文本="测试正文。",
        所属部分="正文",
    )
    return SectionRecord(**(defaults | overrides))


def _table(**overrides) -> TableRecord:
    defaults = dict(
        表格编号="表1",
        表格标题="主要参数",
        所属章节="1 概述",
        表头=["参数", "数值"],
        表体=[["A", "1"], ["B", "2"]],
    )
    return TableRecord(**(defaults | overrides))


def _standard(**overrides) -> StandardReference:
    defaults = dict(
        标准编号="GB/T 1",
        标准名称="测试标准",
        标准类型="method",
        所属章节="1",
    )
    return StandardReference(**(defaults | overrides))


def _minimal_doc() -> DocumentData:
    return DocumentData(文件元数据=_meta())


# ═══════════════════════════════════════════════════════════════════════════
# 1. CleanBodyTests
# ═══════════════════════════════════════════════════════════════════════════

class CleanBodyTests(unittest.TestCase):
    """单元测试 _clean_body：文本清洗与空白行过滤。"""

    def test_空字符串返回空字符串(self):
        self.assertEqual(_clean_body(""), "")

    def test_全为空白行返回空字符串(self):
        self.assertEqual(_clean_body("  \n\t\n   \n"), "")

    def test_混合内容仅保留有效行(self):
        result = _clean_body("第一行\n  \n第二行\n\t\n第三行\n")
        self.assertEqual(result, "第一行\n第二行\n第三行")

    def test_已清理文本原样返回(self):
        clean = "第一章\n第二章\n第三章"
        self.assertEqual(_clean_body(clean), clean)


# ═══════════════════════════════════════════════════════════════════════════
# 2. ShouldRenderTableHeadingTests
# ═══════════════════════════════════════════════════════════════════════════

class ShouldRenderTableHeadingTests(unittest.TestCase):
    """单元测试 _should_render_table_heading：6 条排除规则。"""

    def test_空标题返回False(self):
        self.assertFalse(_should_render_table_heading("", "", set()))

    def test_全空白标题返回False(self):
        self.assertFalse(_should_render_table_heading("   \t  ", "", set()))

    def test_合成标题第3页表5返回False(self):
        self.assertFalse(_should_render_table_heading("第3页表5", "", set()))

    def test_低信号中文引用标准返回False(self):
        self.assertFalse(_should_render_table_heading("引用标准", "", set()))

    def test_低信号英文ReferenceStandards返回False(self):
        self.assertFalse(_should_render_table_heading("Reference Standards", "", set()))

    def test_低信号德文ZitierteNormen返回False(self):
        self.assertFalse(_should_render_table_heading("Zitierte Normen", "", set()))

    def test_逗号碎片标题返回False(self):
        self.assertFalse(_should_render_table_heading("化学成分,", "", set()))

    def test_标题与所属章节标题相同大小写不敏感返回False(self):
        self.assertFalse(_should_render_table_heading("Scope", "scope", set()))

    def test_标题已在已渲染集合中大小写折叠返回False(self):
        # rendered_titles 存储 casefold 后的字符串
        self.assertFalse(_should_render_table_heading("Scope", "", {"scope"}))

    def test_正常标题返回True(self):
        self.assertTrue(_should_render_table_heading("主要参数", "", set()))


# ═══════════════════════════════════════════════════════════════════════════
# 3. ShouldSuppressSectionHeadingTests
# ═══════════════════════════════════════════════════════════════════════════

class ShouldSuppressSectionHeadingTests(unittest.TestCase):
    """单元测试 _should_suppress_section_heading：U 章节标题抑制逻辑。"""

    def test_非U编号返回False(self):
        table = _table(表格标题="前言")
        self.assertFalse(_should_suppress_section_heading("1", "概述", "正文", [table]))

    def test_U章节有正文返回False(self):
        table = _table(表格标题="前言")
        self.assertFalse(_should_suppress_section_heading("U", "前言", "有正文内容", [table]))

    def test_U章节无正文无表格返回False(self):
        self.assertFalse(_should_suppress_section_heading("U", "前言", "", []))

    def test_U章节无正文有表格但标题不匹配返回False(self):
        table = _table(表格标题="其他内容")
        self.assertFalse(_should_suppress_section_heading("U", "前言", "", [table]))

    def test_U章节无正文表格标题匹配返回True(self):
        table = _table(表格标题="前言")
        self.assertTrue(_should_suppress_section_heading("U", "前言", "", [table]))

    def test_U章节无正文表格标题大小写不敏感匹配返回True(self):
        table = _table(表格标题="Preamble")
        self.assertTrue(_should_suppress_section_heading("U", "PREAMBLE", "", [table]))

    def test_小写u前缀返回False(self):
        table = _table(表格标题="前言")
        self.assertFalse(_should_suppress_section_heading("u", "前言", "", [table]))


# ═══════════════════════════════════════════════════════════════════════════
# 4. CollectStandardsTests
# ═══════════════════════════════════════════════════════════════════════════

class CollectStandardsTests(unittest.TestCase):
    """单元测试 _collect_standards：引用标准去重与收集。"""

    def test_空列表返回空OrderedDict(self):
        doc = DocumentData(文件元数据=_meta(), 引用标准列表=[])
        result = _collect_standards(doc)
        self.assertIsInstance(result, OrderedDict)
        self.assertEqual(len(result), 0)

    def test_单个标准返回单条目(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[_standard(标准编号="GB/T 1", 标准名称="测试标准")],
        )
        result = _collect_standards(doc)
        self.assertEqual(len(result), 1)
        self.assertEqual(result["GB/T 1"], "测试标准")

    def test_重复编号仅保留首次出现(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="GB/T 1", 标准名称="第一份"),
                _standard(标准编号="GB/T 1", 标准名称="第二份"),
            ],
        )
        result = _collect_standards(doc)
        self.assertEqual(len(result), 1)
        self.assertEqual(result["GB/T 1"], "第一份")

    def test_大小写不同视为不同键(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="GB/T 1", 标准名称="大写版本"),
                _standard(标准编号="gb/t 1", 标准名称="小写版本"),
            ],
        )
        result = _collect_standards(doc)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["GB/T 1"], "大写版本")
        self.assertEqual(result["gb/t 1"], "小写版本")

    def test_三个不同编号全部保留插入顺序(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="C", 标准名称="第三个"),
                _standard(标准编号="A", 标准名称="第一个"),
                _standard(标准编号="B", 标准名称="第二个"),
            ],
        )
        result = _collect_standards(doc)
        self.assertEqual(len(result), 3)
        self.assertEqual(list(result.keys()), ["C", "A", "B"])

    def test_空字符串编号被跳过(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="", 标准名称="无编号"),
                _standard(标准编号="GB/T 1", 标准名称="有效标准"),
            ],
        )
        result = _collect_standards(doc)
        self.assertEqual(len(result), 1)
        self.assertNotIn("", result)
        self.assertIn("GB/T 1", result)

    def test_仅空白字符编号被跳过(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="   \t  ", 标准名称="空白编号"),
                _standard(标准编号="GB/T 1", 标准名称="有效标准"),
            ],
        )
        result = _collect_standards(doc)
        self.assertEqual(len(result), 1)
        self.assertIn("GB/T 1", result)


# ═══════════════════════════════════════════════════════════════════════════
# 5. BuildMarkdownTests
# ═══════════════════════════════════════════════════════════════════════════

class BuildMarkdownTests(unittest.TestCase):
    """单元测试 build_markdown：完整 Markdown 生成流程。"""

    def test_空文档仅包含元数据(self):
        doc = _minimal_doc()
        result = build_markdown(doc)
        self.assertIn("# 测试文档\n", result)
        self.assertIn("## 文件基础信息", result)
        self.assertIn("- 文件名称：test.pdf", result)
        self.assertIn("- 文档类型：standard", result)
        self.assertIn("- 标准编号：GB/T 1", result)
        self.assertIn("- 版本日期：2024-01-01", result)
        self.assertIn("- 适用范围：测试", result)
        self.assertNotIn("###", result)
        self.assertNotIn("引用标准", result)
        self.assertTrue(result.endswith("\n"))

    def test_单章节有正文无表格(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="概述", 章节层级=1,
                         章节清洗文本="第一章内容。\n第二段内容。", 所属部分="正文"),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("### 1 概述", result)
        self.assertIn("第一章内容。\n第二段内容。\n", result)

    def test_多层级section标题生成正确层级(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="一级", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
                _section(章节编号="1.1", 章节标题="二级", 章节层级=2, 章节清洗文本="", 所属部分="正文",
                         父章节编号="1"),
                _section(章节编号="1.1.1", 章节标题="三级", 章节层级=3, 章节清洗文本="", 所属部分="正文",
                         父章节编号="1.1"),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("### 1 一级", result)
        self.assertIn("#### 1.1 二级", result)
        self.assertIn("##### 1.1.1 三级", result)

    def test_层级上限为H6(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="深层章节", 章节层级=5, 章节清洗文本="", 所属部分="正文"),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("###### 1 深层章节", result)
        self.assertNotIn("#######", result)

    def test_多部分文档part切换(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="范围", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
                _section(章节编号="A.1", 章节标题="附录A", 章节层级=1, 章节清洗文本="", 所属部分="附录"),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("## 正文", result)
        self.assertIn("## 附录", result)

    def test_同part不重复生成part标题(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="范围", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
                _section(章节编号="2", 章节标题="术语", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
                _section(章节编号="A.1", 章节标题="附录A", 章节层级=1, 章节清洗文本="", 所属部分="附录"),
            ],
        )
        result = build_markdown(doc)
        self.assertEqual(result.count("## 正文\n"), 1)
        self.assertEqual(result.count("## 附录\n"), 1)

    def test_表格渲染含表头和表体(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="概述", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
            ],
            表格列表=[
                _table(表格编号="表1", 表格标题="主要参数", 所属章节="1 概述",
                       表头=["参数", "数值", "单位"],
                       表体=[["压力", "10", "bar"], ["温度", "120", "°C"]]),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("| 参数 | 数值 | 单位 |", result)
        self.assertIn("| --- | --- | --- |", result)
        self.assertIn("| 压力 | 10 | bar |", result)
        self.assertIn("| 温度 | 120 | °C |", result)

    def test_表格行少于表头时补齐空单元格(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="概述", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
            ],
            表格列表=[
                _table(表格编号="表1", 表格标题="测试表", 所属章节="1 概述",
                       表头=["A", "B", "C"],
                       表体=[["仅一列"]]),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("| 仅一列 |  |  |", result)

    def test_表格行多于表头时截断(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="概述", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
            ],
            表格列表=[
                _table(表格编号="表1", 表格标题="测试表", 所属章节="1 概述",
                       表头=["A"],
                       表体=[["超长", "被截", "不显示"]]),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("| 超长 |", result)
        self.assertNotIn("被截", result)

    def test_合成表格标题被抑制(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="1", 章节标题="概述", 章节层级=1, 章节清洗文本="", 所属部分="正文"),
            ],
            表格列表=[
                _table(表格编号="表1", 表格标题="第1页表1", 所属章节="1 概述",
                       表头=["K"], 表体=[["V"]]),
            ],
        )
        result = build_markdown(doc)
        self.assertNotIn("第1页表1", result)
        self.assertIn("| K |", result)
        self.assertIn("| V |", result)

    def test_引用标准附录含描述(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="GB/T 1", 标准名称="测试标准一"),
                _standard(标准编号="GB/T 2", 标准名称="测试标准二"),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("## 引用标准", result)
        self.assertIn("- GB/T 1：测试标准一", result)
        self.assertIn("- GB/T 2：测试标准二", result)

    def test_引用标准附录无描述仅显示编号(self):
        doc = DocumentData(
            文件元数据=_meta(),
            引用标准列表=[
                _standard(标准编号="GB/T 1", 标准名称="GB/T 1"),
                _standard(标准编号="GB/T 2", 标准名称=""),
            ],
        )
        result = build_markdown(doc)
        self.assertIn("## 引用标准", result)
        self.assertIn("- GB/T 1\n", result)
        self.assertIn("- GB/T 2\n", result)
        self.assertNotIn("- GB/T 1：", result)
        self.assertNotIn("- GB/T 2：", result)

    def test_文档标题为空时回退为文件名称(self):
        doc = DocumentData(
            文件元数据=_meta(文档标题="", 文件名称="fallback.pdf"),
        )
        result = build_markdown(doc)
        self.assertIn("# fallback.pdf\n", result)
        self.assertNotIn("# \n", result)

    def test_U章节heading被抑制但表格heading被渲染(self):
        doc = DocumentData(
            文件元数据=_meta(),
            章节列表=[
                _section(章节编号="U", 章节标题="前言", 章节层级=1,
                         章节清洗文本="", 所属部分="正文"),
            ],
            表格列表=[
                _table(表格编号="表0", 表格标题="前言", 所属章节="U 前言",
                       表头=["项", "值"], 表体=[["X", "Y"]]),
            ],
        )
        result = build_markdown(doc)
        lines = result.split("\n")
        # 章节标题被抑制：没有任何一行是 "### 前言"
        self.assertNotIn("### 前言", lines)
        # 但表格标题被渲染
        self.assertIn("#### 前言", lines)


if __name__ == "__main__":
    unittest.main()
