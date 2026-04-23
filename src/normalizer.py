from __future__ import annotations

import copy
import re

from src.models import (
    AnchorRef,
    DocumentData,
    NumericParameter,
    ProductRecord,
    RuleRecord,
    SectionRecord,
    SourceRef,
    StandardReference,
    StructureNode,
)
from src.utils import normalize_line

UNIT_MAP = {
    "um": "μm",
    "μm": "μm",
    "µm": "μm",
    "°c": "℃",
    "℃": "℃",
    "n/mm2": "N/mm2",
    "n/mm²": "N/mm2",
    "kn/m2": "kN/m2",
}

PARAMETER_NAME_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(weight|gewicht)\b", re.IGNORECASE), "重量"),
    (re.compile(r"\b(length|länge|laenge)\b", re.IGNORECASE), "长度"),
    (re.compile(r"\b(width|breite)\b", re.IGNORECASE), "宽度"),
    (re.compile(r"\b(height|höhe|hoehe)\b", re.IGNORECASE), "高度"),
    (re.compile(r"\b(pressure|druck)\b", re.IGNORECASE), "压力"),
    (re.compile(r"\b(temperature|temperatur)\b", re.IGNORECASE), "温度"),
    (re.compile(r"\b(tolerance|abweichung)\b", re.IGNORECASE), "公差"),
    (re.compile(r"\b(roughness|ra|rz)\b", re.IGNORECASE), "粗糙度"),
    (re.compile(r"\b(radius|halbmesser)\b", re.IGNORECASE), "半径"),
    (re.compile(r"\b(thickness|wanddicke|wall thickness)\b", re.IGNORECASE), "厚度"),
]


def normalize_document(document: DocumentData) -> DocumentData:
    doc = copy.deepcopy(document)
    if doc.文档画像 is not None:
        doc.文件元数据.文档类型 = {
            "standard": "标准/规范文档",
            "product_catalog": "产品样本/规格资料",
            "manual": "技术手册",
            "report": "报告文档",
            "unknown": "技术资料",
        }.get(doc.文档画像.文档类型, doc.文件元数据.文档类型 or "技术资料")

    doc.章节列表 = _normalize_sections(doc.章节列表)
    doc.数值参数列表 = _normalize_parameters(doc.数值参数列表)
    doc.规则列表 = _normalize_rules(doc.规则列表)
    doc.引用标准列表 = _normalize_standards(doc.引用标准列表)
    doc.产品列表 = _normalize_products(doc.产品列表)
    doc.结构节点列表 = doc.结构节点列表 or _build_nodes_from_sections(doc.章节列表, doc.产品列表)
    _normalize_parameter_enrichment(doc.数值参数列表, doc.产品列表)
    _normalize_rule_enrichment(doc.规则列表)
    _normalize_standard_enrichment(doc.引用标准列表)
    return doc


def _normalize_sections(sections: list[SectionRecord]) -> list[SectionRecord]:
    cleaned: list[SectionRecord] = []
    seen: set[tuple[str, str]] = set()
    for section in sections:
        section.章节标题 = normalize_line(section.章节标题).strip(":：")
        section.所属部分 = normalize_line(section.所属部分)
        lines = [normalize_line(line) for line in section.章节清洗文本.splitlines() if normalize_line(line)]
        section.章节清洗文本 = "\n".join(_dedupe(lines))
        key = (section.章节编号, section.章节标题)
        if key not in seen and (section.章节标题 or section.章节清洗文本):
            seen.add(key)
            cleaned.append(section)
    return cleaned


def _normalize_parameters(parameters: list) -> list:
    out = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in parameters:
        item.参数名称 = _canonicalize_parameter_name(item.参数名称)
        item.参数单位 = _normalize_unit(item.参数单位)
        item.适用条件 = normalize_line(item.适用条件)
        item.所属章节 = normalize_line(item.所属章节)
        item.来源表格 = normalize_line(item.来源表格)
        item.来源子项 = normalize_line(item.来源子项)
        key = (item.参数名称, item.参数值清洗值, item.适用条件, item.所属章节)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _normalize_rules(rules: list) -> list:
    out = []
    seen: set[tuple[str, str, str]] = set()
    for rule in rules:
        rule.规则类型 = normalize_line(rule.规则类型)
        rule.规则内容 = normalize_line(rule.规则内容)
        rule.所属章节 = normalize_line(rule.所属章节)
        key = (rule.规则类型, rule.规则内容, rule.所属章节)
        if key not in seen:
            seen.add(key)
            out.append(rule)
    return out


def _normalize_standards(standards: list) -> list:
    out = []
    seen: set[tuple[str, str]] = set()
    for item in standards:
        item.标准编号 = normalize_line(item.标准编号)
        item.标准名称 = normalize_line(item.标准名称)
        item.所属章节 = normalize_line(item.所属章节)
        key = (item.标准编号, item.所属章节)
        if item.标准编号 and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _normalize_products(products: list[ProductRecord]) -> list[ProductRecord]:
    out: list[ProductRecord] = []
    seen: set[str] = set()
    for product in products:
        product.名称 = normalize_line(product.名称)
        product.型号 = normalize_line(product.型号)
        if product.锚点:
            product.锚点.显示名称 = normalize_line(product.锚点.显示名称)
        display = product.锚点.显示名称 if product.锚点 else (product.型号 or product.名称)
        if display and display not in seen:
            seen.add(display)
            out.append(product)
    return out


def _build_nodes_from_sections(sections: list[SectionRecord], products: list[ProductRecord]) -> list[StructureNode]:
    nodes = [
        StructureNode(
            节点ID=f"section:{section.章节编号}",
            节点类型="section",
            节点标题=f"{section.章节编号} {section.章节标题}".strip(),
            节点层级=section.章节层级,
            父节点ID=f"section:{section.父章节编号}" if section.父章节编号 else "",
        )
        for section in sections
    ]
    nodes.extend(
        StructureNode(
            节点ID=f"product:{product.产品ID}",
            节点类型="product",
            节点标题=product.锚点.显示名称 if product.锚点 else (product.型号 or product.名称),
            节点层级=1,
        )
        for product in products
    )
    return nodes


def _normalize_parameter_enrichment(params: list[NumericParameter], products: list[ProductRecord]) -> None:
    for idx, item in enumerate(params, 1):
        if not item.参数ID:
            item.参数ID = f"param-{idx}"
        if not item.主体锚点:
            item.主体锚点 = _resolve_anchor(item.适用条件, item.所属章节, products)
        if not item.来源引用列表:
            item.来源引用列表 = [SourceRef(页码索引=0, 摘录文本=item.来源子项 or item.参数名称)]
        if item.置信度 == 0.0:
            item.置信度 = 0.75
        # Normalize enrichment fields
        if item.主体锚点:
            item.主体锚点.显示名称 = normalize_line(item.主体锚点.显示名称)


def _normalize_rule_enrichment(rules: list[RuleRecord]) -> None:
    for idx, rule in enumerate(rules, 1):
        if not rule.规则ID:
            rule.规则ID = f"rule-{idx}"
        if not rule.主体锚点:
            display = normalize_line(rule.所属章节) or "文档"
            rule.主体锚点 = AnchorRef(锚点类型="section", 锚点ID=display, 显示名称=display)
        if not rule.来源引用列表:
            rule.来源引用列表 = [SourceRef(页码索引=0, 摘录文本=rule.规则内容[:160])]


def _normalize_standard_enrichment(standards: list[StandardReference]) -> None:
    for item in standards:
        if not item.标准族:
            item.标准族 = item.标准类型
        if not item.主体锚点:
            display = normalize_line(item.所属章节) or "文档"
            item.主体锚点 = AnchorRef(锚点类型="section", 锚点ID=display, 显示名称=display)
        if not item.来源引用列表:
            item.来源引用列表 = [SourceRef(页码索引=0, 摘录文本=item.标准名称[:160] or item.标准编号)]


def _resolve_anchor(condition: str, section_ref: str, products: list[ProductRecord]) -> AnchorRef:
    normalized_condition = normalize_line(condition)
    for product in products:
        display = product.锚点.显示名称 if product.锚点 else (product.型号 or product.名称)
        if display and display in normalized_condition:
            return AnchorRef(锚点类型="product", 锚点ID=product.产品ID, 显示名称=display)
    display = normalize_line(section_ref) or "文档"
    return AnchorRef(锚点类型="section", 锚点ID=display, 显示名称=display)


def _canonicalize_parameter_name(name: str) -> str:
    normalized = normalize_line(name)
    lowered = normalized.lower()
    for pattern, replacement in PARAMETER_NAME_PATTERNS:
        if pattern.search(lowered):
            return replacement
    return normalized


def _normalize_unit(unit: str) -> str:
    normalized = normalize_line(unit).replace("µ", "μ")
    return UNIT_MAP.get(normalized.lower(), normalized)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
