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

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class RuleRecord:
    规则类型: str = ""
    规则内容: str = ""
    适用条件: str = ""
    所属章节: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


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

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


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
    page_index: int
    raw_text: str = ""
    width: float = 0.0
    height: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class StructureNode:
    node_id: str
    node_type: NodeType
    title: str
    level: int = 0
    parent_id: str = ""
    page_start: int = 0
    page_end: int = 0
    block_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class SourceRef:
    page_index: int
    block_id: str = ""
    table_id: str = ""
    row_index: int = -1
    col_index: int = -1
    node_id: str = ""
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class AnchorRef:
    anchor_type: AnchorType
    anchor_id: str
    display_name: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProductRecord:
    product_id: str
    series: str = ""
    model: str = ""
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    anchor: AnchorRef | None = None
    source_refs: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["anchor"] = self.anchor.to_dict() if self.anchor else None
        data["source_refs"] = [ref.to_dict() for ref in self.source_refs]
        return data


@dataclass
class ParameterFact:
    param_id: str
    subject_anchor: AnchorRef | None = None
    raw_name: str = ""
    canonical_name: str = ""
    value_raw: str = ""
    value_text: str = ""
    value_min: str = ""
    value_max: str = ""
    comparator: str = ""
    unit_raw: str = ""
    unit_norm: str = ""
    condition: str = ""
    source_table: str = ""
    source_item: str = ""
    source_refs: list[SourceRef] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["subject_anchor"] = self.subject_anchor.to_dict() if self.subject_anchor else None
        data["source_refs"] = [ref.to_dict() for ref in self.source_refs]
        return data


@dataclass
class RuleFact:
    rule_id: str
    rule_type: str = ""
    text_raw: str = ""
    text_norm: str = ""
    subject_anchor: AnchorRef | None = None
    source_refs: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["subject_anchor"] = self.subject_anchor.to_dict() if self.subject_anchor else None
        data["source_refs"] = [ref.to_dict() for ref in self.source_refs]
        return data


@dataclass
class StandardFact:
    code_raw: str = ""
    code_norm: str = ""
    family: str = ""
    title: str = ""
    subject_anchor: AnchorRef | None = None
    source_refs: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["subject_anchor"] = self.subject_anchor.to_dict() if self.subject_anchor else None
        data["source_refs"] = [ref.to_dict() for ref in self.source_refs]
        return data


@dataclass
class ParsedDocument:
    metadata: FileMetadata
    profile: DocumentProfile
    pages: list[PageRecord] = field(default_factory=list)
    blocks: list[BlockRecord] = field(default_factory=list)
    nodes: list[StructureNode] = field(default_factory=list)
    products: list[ProductRecord] = field(default_factory=list)
    parameters: list[ParameterFact] = field(default_factory=list)
    rules: list[RuleFact] = field(default_factory=list)
    standards: list[StandardFact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "profile": self.profile.to_dict(),
            "pages": [page.to_dict() for page in self.pages],
            "blocks": [block.to_dict() for block in self.blocks],
            "nodes": [node.to_dict() for node in self.nodes],
            "products": [product.to_dict() for product in self.products],
            "parameters": [param.to_dict() for param in self.parameters],
            "rules": [rule.to_dict() for rule in self.rules],
            "standards": [standard.to_dict() for standard in self.standards],
        }


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
    pages_v2: list[PageRecord] = field(default_factory=list)
    nodes_v2: list[StructureNode] = field(default_factory=list)
    products_v2: list[ProductRecord] = field(default_factory=list)
    parameter_facts_v2: list[ParameterFact] = field(default_factory=list)
    rule_facts_v2: list[RuleFact] = field(default_factory=list)
    standard_facts_v2: list[StandardFact] = field(default_factory=list)
    parsed_view: ParsedDocument | None = None
