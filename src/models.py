from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DocType = Literal["standard", "product_catalog", "manual", "report", "unknown"]
NodeType = Literal["section", "product", "model", "appendix", "revision"]
AnchorType = Literal["document", "section", "product", "model"]


@dataclass
class FileMetadata:
    文件名称: str = ""
    文件类型: str = ""
    文档标题: str = ""
    文档类型: str = ""
    标准编号: str = ""
    版本日期: str = ""
    适用范围: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class DocumentProfile:
    doc_type: DocType = "unknown"
    confidence: float = 0.0
    language: str = "unknown"
    layout_mode: str = "single_column"
    has_many_tables: bool = False
    has_product_cards: bool = False
    needs_ocr: bool = False
    page_count: int = 0
    text_line_count: int = 0
    avg_chars_per_page: float = 0.0
    table_count: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class SectionRecord:
    章节编号: str = ""
    章节标题: str = ""
    章节层级: int = 0
    父章节编号: str = ""
    章节清洗文本: str = ""
    所属部分: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class TableRecord:
    表格编号: str = ""
    表格标题: str = ""
    所属章节: str = ""
    表头: list[str] = field(default_factory=list)
    表体: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class SourceRef:
    页码索引: int = 0
    块ID: str = ""
    表格ID: str = ""
    行索引: int = -1
    列索引: int = -1
    节点ID: str = ""
    摘录文本: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class AnchorRef:
    锚点类型: AnchorType = "document"
    锚点ID: str = ""
    显示名称: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class NumericParameter:
    参数名称: str = ""
    参数值清洗值: str = ""
    参数单位: str = ""
    参数范围下限: str = ""
    参数范围上限: str = ""
    比较符号: str = ""
    适用条件: str = ""
    所属章节: str = ""
    来源表格: str = ""
    来源子项: str = ""
    参数ID: str = ""
    主体锚点: AnchorRef | None = None
    来源引用列表: list[SourceRef] = field(default_factory=list)
    置信度: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["主体锚点"] = self.主体锚点.to_dict() if self.主体锚点 else None
        data["来源引用列表"] = [ref.to_dict() for ref in self.来源引用列表]
        return data


@dataclass
class RuleRecord:
    规则类型: str = ""
    规则内容: str = ""
    适用条件: str = ""
    所属章节: str = ""
    规则ID: str = ""
    主体锚点: AnchorRef | None = None
    来源引用列表: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["主体锚点"] = self.主体锚点.to_dict() if self.主体锚点 else None
        data["来源引用列表"] = [ref.to_dict() for ref in self.来源引用列表]
        return data


@dataclass
class InspectionRecord:
    检验对象: str = ""
    检验方法: str = ""
    检验要求: str = ""
    证书类型: str = ""
    所属章节: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class StandardReference:
    标准编号: str = ""
    标准名称: str = ""
    标准类型: str = ""
    所属章节: str = ""
    标准族: str = ""
    主体锚点: AnchorRef | None = None
    来源引用列表: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["主体锚点"] = self.主体锚点.to_dict() if self.主体锚点 else None
        data["来源引用列表"] = [ref.to_dict() for ref in self.来源引用列表]
        return data


@dataclass
class BlockRecord:
    块类型: str = ""
    标题: str = ""
    内容: str = ""
    所属部分: str = ""
    所属章节: str = ""
    来源页码: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class PageRecord:
    页码索引: int = 0
    原始文本: str = ""
    页面宽度: float = 0.0
    页面高度: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class StructureNode:
    节点ID: str = ""
    节点类型: NodeType = "section"
    节点标题: str = ""
    节点层级: int = 0
    父节点ID: str = ""
    起始页码: int = 0
    结束页码: int = 0
    关联块ID列表: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProductRecord:
    产品ID: str = ""
    系列: str = ""
    型号: str = ""
    名称: str = ""
    别名列表: list[str] = field(default_factory=list)
    锚点: AnchorRef | None = None
    来源引用列表: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["锚点"] = self.锚点.to_dict() if self.锚点 else None
        data["来源引用列表"] = [ref.to_dict() for ref in self.来源引用列表]
        return data


@dataclass
class DocumentData:
    metadata: FileMetadata
    raw_pages: list[dict[str, Any]] = field(default_factory=list)
    sections: list[SectionRecord] = field(default_factory=list)
    tables: list[TableRecord] = field(default_factory=list)
    numeric_parameters: list[NumericParameter] = field(default_factory=list)
    rules: list[RuleRecord] = field(default_factory=list)
    inspections: list[InspectionRecord] = field(default_factory=list)
    standards: list[StandardReference] = field(default_factory=list)
    blocks: list[BlockRecord] = field(default_factory=list)
    profile: DocumentProfile | None = None
    页面列表: list[PageRecord] = field(default_factory=list)
    结构节点列表: list[StructureNode] = field(default_factory=list)
    产品列表: list[ProductRecord] = field(default_factory=list)
