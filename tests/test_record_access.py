from __future__ import annotations

import unittest

from src.record_access import (
    block_dict,
    block_values,
    get_parameter_entries,
    get_product_entries,
    get_profile_dict,
    get_rule_entries,
    get_section_entries,
    get_standard_entries,
    inspection_dict,
    inspection_values,
    metadata_dict,
    metadata_doc_type,
    metadata_filename,
    metadata_title,
    metadata_values,
    parameter_dict,
    parameter_values,
    rule_dict,
    rule_values,
    section_dict,
    section_ref,
    section_values,
    standard_dict,
    standard_values,
    table_dict,
    table_values,
)
from src.models import (
    AnchorRef,
    BlockRecord,
    DocumentData,
    DocumentProfile,
    FileMetadata,
    InspectionRecord,
    NumericParameter,
    ProductRecord,
    RuleRecord,
    SectionRecord,
    SourceRef,
    StandardReference,
    TableRecord,
)


# ── helpers ────────────────────────────────────────────────────────────

def _anchor(name: str = "第3章 技术要求") -> AnchorRef:
    return AnchorRef(锚点类型="section", 锚点ID="sec-3", 显示名称=name)


def _source_ref(page: int = 1, block: str = "b1") -> SourceRef:
    return SourceRef(页码索引=page, 块ID=block, 摘录文本="摘录文本测试")


def _document() -> DocumentData:
    """最小 DocumentData，含各列表各 1 条记录。"""
    return DocumentData(
        文件元数据=FileMetadata(
            文件名称="test.pdf",
            文件类型="pdf",
            文档标题="测试文档",
            文档类型="standard",
            标准编号="GB/T 12345",
            版本日期="2024-01-01",
            适用范围="工业",
        ),
        章节列表=[
            SectionRecord(
                章节编号="1",
                章节标题="概述",
                章节层级=1,
                父章节编号="",
                章节清洗文本="本章概述内容。",
                所属部分="正文",
            ),
        ],
        数值参数列表=[
            NumericParameter(
                参数名称="抗拉强度",
                参数值清洗值="500",
                参数单位="MPa",
                参数范围下限="400",
                参数范围上限="600",
                比较符号=">=",
                适用条件="常温",
                所属章节="3",
                来源表格="表1",
                来源子项="1-1",
                参数ID="P001",
                主体锚点=_anchor("第3章 力学性能"),
                来源引用列表=[_source_ref(1, "b1")],
                置信度=0.95,
            ),
        ],
        规则列表=[
            RuleRecord(
                规则类型="判定规则",
                规则内容="抗拉强度 >= 400 MPa",
                适用条件="所有批次",
                所属章节="4",
                规则ID="R001",
                主体锚点=_anchor("第4章 检验规则"),
                来源引用列表=[_source_ref(2, "b2")],
            ),
        ],
        检验列表=[
            InspectionRecord(
                检验对象="焊缝",
                检验方法="超声波",
                检验要求="无缺陷",
                证书类型="EN 10204 3.1",
                所属章节="5",
            ),
        ],
        引用标准列表=[
            StandardReference(
                标准编号="GB/T 228.1",
                标准名称="金属材料 拉伸试验",
                标准类型="method",
                所属章节="2",
                标准族="GB/T 228",
                主体锚点=_anchor("第2章 规范性引用文件"),
                来源引用列表=[_source_ref(1, "b3")],
            ),
        ],
        产品列表=[
            ProductRecord(
                产品ID="PROD001",
                系列="X系列",
                型号="X-100",
                名称="法兰盘",
                别名列表=["法兰", "连接盘"],
                锚点=_anchor("附录A 产品规格"),
                来源引用列表=[_source_ref(5, "b10")],
            ),
        ],
        文档画像=DocumentProfile(
            文档类型="standard",
            置信度=0.9,
            语言="zh",
            布局模式="single_column",
            是否含大量表格=True,
            是否含产品卡片=False,
            是否需要OCR=False,
            页数=12,
            文本行数=500,
            每页平均字符数=300.0,
            表格数量=3,
            判断依据=["标题分析", "格式特征"],
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Layer 1 — 纯访问器（单条 dataclass 实例 → dict / str / tuple）
# ═══════════════════════════════════════════════════════════════════════


class MetadataAccessorTests(unittest.TestCase):
    """覆盖 metadata_dict / metadata_title / metadata_filename / metadata_doc_type / metadata_values。"""

    def setUp(self):
        self.meta = FileMetadata(
            文件名称="doc.pdf",
            文件类型="pdf",
            文档标题="技术条件",
            文档类型="standard",
            标准编号="GB/T 1",
            版本日期="2023-06-01",
            适用范围="建筑",
        )

    def test_metadata_dict_返回全部7个字段的字典(self):
        result = metadata_dict(self.meta)
        self.assertEqual(result["文件名称"], "doc.pdf")
        self.assertEqual(result["文件类型"], "pdf")
        self.assertEqual(result["文档标题"], "技术条件")
        self.assertEqual(result["文档类型"], "standard")
        self.assertEqual(result["标准编号"], "GB/T 1")
        self.assertEqual(result["版本日期"], "2023-06-01")
        self.assertEqual(result["适用范围"], "建筑")
        self.assertEqual(len(result), 7)

    def test_metadata_title_返回文档标题(self):
        self.assertEqual(metadata_title(self.meta), "技术条件")

    def test_metadata_filename_返回文件名称(self):
        self.assertEqual(metadata_filename(self.meta), "doc.pdf")

    def test_metadata_doc_type_返回文档类型(self):
        self.assertEqual(metadata_doc_type(self.meta), "standard")

    def test_metadata_values_返回7元组(self):
        result = metadata_values(self.meta)
        self.assertEqual(result, ("doc.pdf", "pdf", "技术条件", "standard", "GB/T 1", "2023-06-01", "建筑"))
        self.assertEqual(len(result), 7)


class SectionAccessorTests(unittest.TestCase):
    """覆盖 section_dict / section_ref / section_values。"""

    def setUp(self):
        self.sec = SectionRecord(
            章节编号="3.1",
            章节标题="材料要求",
            章节层级=2,
            父章节编号="3",
            章节清洗文本="材料应符合标准。",
            所属部分="技术要求",
        )

    def test_section_dict_返回全部6字段(self):
        result = section_dict(self.sec)
        self.assertEqual(result["章节编号"], "3.1")
        self.assertEqual(result["章节标题"], "材料要求")
        self.assertEqual(result["章节层级"], 2)
        self.assertEqual(result["父章节编号"], "3")
        self.assertEqual(result["章节清洗文本"], "材料应符合标准。")
        self.assertEqual(result["所属部分"], "技术要求")
        self.assertEqual(len(result), 6)

    def test_section_ref_编号标题拼接(self):
        self.assertEqual(section_ref(self.sec), "3.1 材料要求")

    def test_section_ref_标题为空不抛异常(self):
        sec = SectionRecord(章节编号="4", 章节标题="")
        self.assertEqual(section_ref(sec), "4")

    def test_section_values_返回6元组(self):
        result = section_values(self.sec)
        self.assertEqual(result, ("3.1", "材料要求", 2, "3", "材料应符合标准。", "技术要求"))


class TableAccessorTests(unittest.TestCase):
    """覆盖 table_dict / table_values。"""

    def setUp(self):
        self.tbl = TableRecord(
            表格编号="表2",
            表格标题="化学成分",
            所属章节="5",
            表头=["元素", "含量%"],
            表体=[["C", "0.2"], ["Mn", "1.5"]],
        )

    def test_table_dict_返回全部5字段(self):
        result = table_dict(self.tbl)
        self.assertEqual(result["表格编号"], "表2")
        self.assertEqual(result["表格标题"], "化学成分")
        self.assertEqual(result["所属章节"], "5")
        self.assertEqual(result["表头"], ["元素", "含量%"])
        self.assertEqual(result["表体"], [["C", "0.2"], ["Mn", "1.5"]])

    def test_table_values_返回5元组(self):
        result = table_values(self.tbl)
        self.assertEqual(result, ("表2", "化学成分", "5", ["元素", "含量%"], [["C", "0.2"], ["Mn", "1.5"]]))


class ParameterAccessorTests(unittest.TestCase):
    """覆盖 parameter_dict / parameter_values，含主体锚点为 None 和空来源引用列表的边界。"""

    def test_parameter_dict_完整含锚点和引用(self):
        param = NumericParameter(
            参数名称="屈服强度",
            参数值清洗值="235",
            参数单位="MPa",
            参数范围下限="200",
            参数范围上限="250",
            比较符号=">=",
            适用条件="室温",
            所属章节="6",
            来源表格="表3",
            来源子项="2-1",
            参数ID="P002",
            主体锚点=_anchor("第6章"),
            来源引用列表=[_source_ref(3, "b6")],
            置信度=0.88,
        )
        result = parameter_dict(param)
        self.assertEqual(result["参数名称"], "屈服强度")
        self.assertEqual(result["参数值清洗值"], "235")
        self.assertEqual(result["参数单位"], "MPa")
        self.assertEqual(result["参数范围下限"], "200")
        self.assertEqual(result["参数范围上限"], "250")
        self.assertEqual(result["比较符号"], ">=")
        self.assertEqual(result["适用条件"], "室温")
        self.assertEqual(result["所属章节"], "6")
        self.assertEqual(result["来源表格"], "表3")
        self.assertEqual(result["来源子项"], "2-1")
        self.assertEqual(result["参数ID"], "P002")
        self.assertIsNotNone(result["主体锚点"])
        self.assertEqual(result["主体锚点"]["显示名称"], "第6章")
        self.assertEqual(len(result["来源引用列表"]), 1)
        self.assertEqual(result["置信度"], 0.88)

    def test_parameter_dict_主体锚点为None_来源引用为空列表(self):
        param = NumericParameter(
            参数名称="硬度",
            参数值清洗值="180",
            参数单位="HB",
            参数范围下限="",
            参数范围上限="",
            比较符号="",
            适用条件="",
            所属章节="7",
            来源表格="",
            来源子项="",
            参数ID="P003",
            主体锚点=None,
            来源引用列表=[],
            置信度=0.5,
        )
        result = parameter_dict(param)
        self.assertIsNone(result["主体锚点"])
        self.assertEqual(result["来源引用列表"], [])

    def test_parameter_values_返回10元组(self):
        param = NumericParameter(
            参数名称="伸长率", 参数值清洗值="20", 参数单位="%",
            参数范围下限="18", 参数范围上限="22", 比较符号=">=",
            适用条件="常温", 所属章节="8", 来源表格="表4", 来源子项="3-1",
        )
        result = parameter_values(param)
        self.assertEqual(result, ("伸长率", "20", "%", "18", "22", ">=", "常温", "8", "表4", "3-1"))


class RuleAccessorTests(unittest.TestCase):
    """覆盖 rule_dict / rule_values，含 None 锚点和空引用列表边界。"""

    def test_rule_dict_完整含锚点和引用(self):
        rule = RuleRecord(
            规则类型="验收规则",
            规则内容="表面无裂纹",
            适用条件="目视检查",
            所属章节="9",
            规则ID="R010",
            主体锚点=_anchor("第9章"),
            来源引用列表=[_source_ref(4, "b7")],
        )
        result = rule_dict(rule)
        self.assertEqual(result["规则类型"], "验收规则")
        self.assertEqual(result["规则内容"], "表面无裂纹")
        self.assertEqual(result["适用条件"], "目视检查")
        self.assertEqual(result["所属章节"], "9")
        self.assertEqual(result["规则ID"], "R010")
        self.assertEqual(result["主体锚点"]["显示名称"], "第9章")
        self.assertEqual(len(result["来源引用列表"]), 1)

    def test_rule_dict_锚点为None_引用为空列表(self):
        rule = RuleRecord(
            规则类型="禁止项", 规则内容="禁止使用石棉",
            适用条件="", 所属章节="10", 规则ID="R020",
            主体锚点=None, 来源引用列表=[],
        )
        result = rule_dict(rule)
        self.assertIsNone(result["主体锚点"])
        self.assertEqual(result["来源引用列表"], [])

    def test_rule_values_返回4元组(self):
        rule = RuleRecord(规则类型="A", 规则内容="B", 适用条件="C", 所属章节="D")
        self.assertEqual(rule_values(rule), ("A", "B", "C", "D"))


class InspectionAccessorTests(unittest.TestCase):
    """覆盖 inspection_dict / inspection_values。"""

    def setUp(self):
        self.rec = InspectionRecord(
            检验对象="钢板", 检验方法="磁粉",
            检验要求="无表面缺陷", 证书类型="EN 10204 2.2", 所属章节="11",
        )

    def test_inspection_dict_返回全部5字段(self):
        result = inspection_dict(self.rec)
        self.assertEqual(result["检验对象"], "钢板")
        self.assertEqual(result["检验方法"], "磁粉")
        self.assertEqual(result["检验要求"], "无表面缺陷")
        self.assertEqual(result["证书类型"], "EN 10204 2.2")
        self.assertEqual(result["所属章节"], "11")

    def test_inspection_values_返回5元组(self):
        self.assertEqual(
            inspection_values(self.rec),
            ("钢板", "磁粉", "无表面缺陷", "EN 10204 2.2", "11"),
        )


class StandardAccessorTests(unittest.TestCase):
    """覆盖 standard_dict / standard_values，含 None 锚点边界。"""

    def test_standard_dict_完整含锚点和引用(self):
        std = StandardReference(
            标准编号="ISO 9001",
            标准名称="质量管理体系",
            标准类型="system",
            所属章节="2",
            标准族="ISO 9000",
            主体锚点=_anchor("第2章"),
            来源引用列表=[_source_ref(1, "b_ref")],
        )
        result = standard_dict(std)
        self.assertEqual(result["标准编号"], "ISO 9001")
        self.assertEqual(result["标准名称"], "质量管理体系")
        self.assertEqual(result["标准类型"], "system")
        self.assertEqual(result["所属章节"], "2")
        self.assertEqual(result["标准族"], "ISO 9000")
        self.assertEqual(result["主体锚点"]["显示名称"], "第2章")
        self.assertEqual(len(result["来源引用列表"]), 1)

    def test_standard_dict_锚点为None_引用为空列表(self):
        std = StandardReference(
            标准编号="ASTM A36", 标准名称="碳结构钢", 标准类型="material",
            所属章节="3", 主体锚点=None, 来源引用列表=[],
        )
        result = standard_dict(std)
        self.assertIsNone(result["主体锚点"])
        self.assertEqual(result["来源引用列表"], [])

    def test_standard_values_返回4元组(self):
        std = StandardReference(标准编号="X", 标准名称="Y", 标准类型="Z", 所属章节="W")
        self.assertEqual(standard_values(std), ("X", "Y", "Z", "W"))


class BlockAccessorTests(unittest.TestCase):
    """覆盖 block_dict / block_values。"""

    def setUp(self):
        self.blk = BlockRecord(
            块类型="paragraph", 标题="注意事项",
            内容="操作前请阅读说明书。", 所属部分="附录",
            所属章节="A.1", 来源页码=10,
        )

    def test_block_dict_返回全部6字段(self):
        result = block_dict(self.blk)
        self.assertEqual(result["块类型"], "paragraph")
        self.assertEqual(result["标题"], "注意事项")
        self.assertEqual(result["内容"], "操作前请阅读说明书。")
        self.assertEqual(result["所属部分"], "附录")
        self.assertEqual(result["所属章节"], "A.1")
        self.assertEqual(result["来源页码"], 10)

    def test_block_values_返回6元组(self):
        result = block_values(self.blk)
        self.assertEqual(result, ("paragraph", "注意事项", "操作前请阅读说明书。", "附录", "A.1", 10))


# ═══════════════════════════════════════════════════════════════════════
# Layer 2 — DocumentData 级函数
# ═══════════════════════════════════════════════════════════════════════


class DocumentDataAccessorTests(unittest.TestCase):
    """覆盖 get_profile_dict / get_section_entries / get_parameter_entries /
    get_rule_entries / get_standard_entries / get_product_entries。"""

    def setUp(self):
        self.doc = _document()

    # ── get_profile_dict ──────────────────────────────────────────────

    def test_get_profile_dict_画像存在时返回to_dict结果(self):
        result = get_profile_dict(self.doc)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["文档类型"], "standard")
        self.assertGreater(len(result), 5)  # DocumentProfile 有 16 个字段

    def test_get_profile_dict_画像为None时返回空字典(self):
        doc_no_profile = DocumentData(
            文件元数据=FileMetadata(文件名称="empty.pdf"),
            文档画像=None,
        )
        self.assertEqual(get_profile_dict(doc_no_profile), {})

    def test_get_profile_dict_画像无to_dict方法时返回空字典(self):
        class FakeProfileNoToDict:
            pass
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="bad.pdf"),
            文档画像=None,
        )
        # 使用 object.__setattr__ 注入一个无 to_dict 的对象（绕过 dataclass 类型检查）
        object.__setattr__(doc, "文档画像", FakeProfileNoToDict())
        self.assertEqual(get_profile_dict(doc), {})

    # ── get_section_entries ───────────────────────────────────────────

    def test_get_section_entries_普通章节返回规范化条目(self):
        entries = get_section_entries(self.doc)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["章节编号"], "1")
        self.assertEqual(e["章节标题"], "概述")
        self.assertEqual(e["章节标题全称"], "1 概述")
        self.assertEqual(e["章节层级"], 1)
        self.assertEqual(e["父章节编号"], "")
        self.assertEqual(e["章节正文"], "本章概述内容。")
        self.assertEqual(e["所属部分"], "正文")

    def test_get_section_entries_U编号章节标题全称不拼接编号(self):
        """章节编号以 U 开头时，章节标题全称 = 章节标题（不拼接编号）。"""
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="u.pdf"),
            章节列表=[SectionRecord(章节编号="U1", 章节标题="前言", 章节层级=0)],
        )
        entries = get_section_entries(doc)
        self.assertEqual(entries[0]["章节标题全称"], "前言")

    def test_get_section_entries_空列表返回空列表(self):
        doc = DocumentData(文件元数据=FileMetadata(文件名称="empty.pdf"))
        self.assertEqual(get_section_entries(doc), [])

    # ── get_parameter_entries ─────────────────────────────────────────

    def test_get_parameter_entries_含锚点参数返回完整条目(self):
        entries = get_parameter_entries(self.doc)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["ID"], "P001")
        self.assertEqual(e["参数名称"], "抗拉强度")
        self.assertEqual(e["参数值文本"], "500")
        self.assertEqual(e["单位"], "MPa")
        self.assertEqual(e["参数范围下限"], "400")
        self.assertEqual(e["参数范围上限"], "600")
        self.assertEqual(e["比较符号"], ">=")
        self.assertEqual(e["适用条件"], "常温")
        self.assertEqual(e["所属章节"], "第3章 力学性能")  # from anchor.显示名称
        self.assertEqual(e["来源表格"], "表1")
        self.assertEqual(e["来源子项"], "1-1")
        self.assertIsInstance(e["主体锚点"], dict)
        self.assertEqual(e["主体锚点"]["显示名称"], "第3章 力学性能")
        self.assertEqual(len(e["来源引用列表"]), 1)
        # 原始名称与参数名称一致
        self.assertEqual(e["原始名称"], "抗拉强度")

    def test_get_parameter_entries_锚点为None时回退为所属章节字段(self):
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="p.pdf"),
            数值参数列表=[
                NumericParameter(
                    参数名称="密度", 参数值清洗值="7.85",
                    参数单位="g/cm3", 所属章节="附录B",
                    参数ID="P999", 主体锚点=None, 来源引用列表=[],
                ),
            ],
        )
        entries = get_parameter_entries(doc)
        self.assertEqual(entries[0]["所属章节"], "附录B")  # fallback to item.所属章节
        self.assertEqual(entries[0]["主体锚点"], {})

    # ── get_rule_entries ──────────────────────────────────────────────

    def test_get_rule_entries_含锚点规则返回完整条目(self):
        entries = get_rule_entries(self.doc)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["ID"], "R001")
        self.assertEqual(e["规则类型"], "判定规则")
        self.assertEqual(e["内容"], "抗拉强度 >= 400 MPa")
        self.assertEqual(e["适用条件"], "所有批次")
        self.assertEqual(e["所属章节"], "第4章 检验规则")
        self.assertEqual(e["主体锚点"]["显示名称"], "第4章 检验规则")
        self.assertEqual(len(e["来源引用列表"]), 1)

    def test_get_rule_entries_锚点为None时回退为所属章节字段(self):
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="r.pdf"),
            规则列表=[
                RuleRecord(
                    规则类型="A", 规则内容="B", 适用条件="C",
                    所属章节="12", 规则ID="R000",
                    主体锚点=None, 来源引用列表=[],
                ),
            ],
        )
        entries = get_rule_entries(doc)
        self.assertEqual(entries[0]["所属章节"], "12")
        self.assertEqual(entries[0]["主体锚点"], {})

    # ── get_standard_entries ──────────────────────────────────────────

    def test_get_standard_entries_含锚点标准返回完整条目(self):
        entries = get_standard_entries(self.doc)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["标准编号"], "GB/T 228.1")
        self.assertEqual(e["标准名称"], "金属材料 拉伸试验")
        self.assertEqual(e["标准族"], "GB/T 228")  # item.标准族 不为空
        self.assertEqual(e["所属章节"], "第2章 规范性引用文件")
        self.assertEqual(e["主体锚点"]["显示名称"], "第2章 规范性引用文件")
        self.assertEqual(len(e["来源引用列表"]), 1)

    def test_get_standard_entries_标准族为空时回退为标准类型(self):
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="s.pdf"),
            引用标准列表=[
                StandardReference(
                    标准编号="YB/T 1", 标准名称="行业标准测试",
                    标准类型="industry", 所属章节="1",
                    标准族="",  # 空字符串
                    主体锚点=None, 来源引用列表=[],
                ),
            ],
        )
        entries = get_standard_entries(doc)
        self.assertEqual(entries[0]["标准族"], "industry")  # fallback to 标准类型

    # ── get_product_entries ───────────────────────────────────────────

    def test_get_product_entries_含锚点产品返回完整条目(self):
        entries = get_product_entries(self.doc)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["ID"], "PROD001")
        self.assertEqual(e["名称"], "法兰盘")
        self.assertEqual(e["型号"], "X-100")
        self.assertEqual(e["系列"], "X系列")
        self.assertEqual(e["主体锚点"]["显示名称"], "附录A 产品规格")
        self.assertEqual(e["显示名称"], "附录A 产品规格")  # anchor.显示名称
        self.assertEqual(len(e["来源引用列表"]), 1)

    def test_get_product_entries_锚点为None时显示名称为空字符串(self):
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="prod.pdf"),
            产品列表=[
                ProductRecord(
                    产品ID="P_NONE", 名称="", 型号="", 系列="",
                    锚点=None, 来源引用列表=[],
                ),
            ],
        )
        entries = get_product_entries(doc)
        self.assertEqual(entries[0]["显示名称"], "")  # 全空

    def test_get_product_entries_锚点为None时回退为型号名称系列(self):
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="prod2.pdf"),
            产品列表=[
                ProductRecord(
                    产品ID="P_FB", 名称="螺栓", 型号="M12", 系列="标准件",
                    锚点=None, 来源引用列表=[],
                ),
            ],
        )
        entries = get_product_entries(doc)
        # anchor is None → anchor.显示名称 is "" → fallback to 型号 "M12"
        self.assertEqual(entries[0]["显示名称"], "M12")

    def test_get_product_entries_锚点显示名称为空时回退为型号(self):
        doc = DocumentData(
            文件元数据=FileMetadata(文件名称="prod3.pdf"),
            产品列表=[
                ProductRecord(
                    产品ID="P_EMPTY", 名称="垫圈", 型号="WD-01", 系列="W系列",
                    锚点=AnchorRef(锚点类型="product", 锚点ID="a1", 显示名称=""),
                    来源引用列表=[],
                ),
            ],
        )
        entries = get_product_entries(doc)
        # anchor 存在但显示名称为 "" → fallback to 型号
        self.assertEqual(entries[0]["显示名称"], "WD-01")


if __name__ == "__main__":
    unittest.main()
