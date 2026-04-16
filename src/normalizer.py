from __future__ import annotations

import copy
import re

from src.models import (
    AnchorRef,
    DocumentData,
    ParameterFact,
    ParsedDocument,
    ProductRecord,
    RuleFact,
    SectionRecord,
    SourceRef,
    StandardFact,
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
    if doc.profile is not None:
        doc.metadata.文档类型 = {
            "standard": "标准/规范文档",
            "product_catalog": "产品样本/规格资料",
            "manual": "技术手册",
            "report": "报告文档",
            "unknown": "技术资料",
        }.get(doc.profile.doc_type, doc.metadata.文档类型 or "技术资料")

    doc.sections = _normalize_sections(doc.sections)
    doc.numeric_parameters = _normalize_parameters(doc.numeric_parameters)
    doc.rules = _normalize_rules(doc.rules)
    doc.standards = _normalize_standards(doc.standards)
    doc.products_v2 = _normalize_products(doc.products_v2)
    doc.nodes_v2 = doc.nodes_v2 or _build_nodes_from_sections(doc.sections, doc.products_v2)
    doc.parameter_facts_v2 = _normalize_parameter_facts(doc.parameter_facts_v2, doc.numeric_parameters, doc.products_v2)
    doc.rule_facts_v2 = _normalize_rule_facts(doc.rule_facts_v2, doc.rules)
    doc.standard_facts_v2 = _normalize_standard_facts(doc.standard_facts_v2, doc.standards)
    if doc.pages_v2 and doc.profile is not None:
        doc.parsed_view = ParsedDocument(
            metadata=doc.metadata,
            profile=doc.profile,
            pages=doc.pages_v2,
            blocks=doc.blocks,
            nodes=doc.nodes_v2,
            products=doc.products_v2,
            parameters=doc.parameter_facts_v2,
            rules=doc.rule_facts_v2,
            standards=doc.standard_facts_v2,
        )
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
        product.name = normalize_line(product.name)
        product.model = normalize_line(product.model)
        if product.anchor:
            product.anchor.display_name = normalize_line(product.anchor.display_name)
        display = product.anchor.display_name if product.anchor else (product.model or product.name)
        if display and display not in seen:
            seen.add(display)
            out.append(product)
    return out


def _build_nodes_from_sections(sections: list[SectionRecord], products: list[ProductRecord]) -> list[StructureNode]:
    nodes = [
        StructureNode(
            node_id=f"section:{section.章节编号}",
            node_type="section",
            title=f"{section.章节编号} {section.章节标题}".strip(),
            level=section.章节层级,
            parent_id=f"section:{section.父章节编号}" if section.父章节编号 else "",
        )
        for section in sections
    ]
    nodes.extend(
        StructureNode(
            node_id=f"product:{product.product_id}",
            node_type="product",
            title=product.anchor.display_name if product.anchor else (product.model or product.name),
            level=1,
        )
        for product in products
    )
    return nodes


def _normalize_parameter_facts(facts: list[ParameterFact], legacy_parameters: list, products: list[ProductRecord]) -> list[ParameterFact]:
    if not facts:
        facts = []
        for idx, item in enumerate(legacy_parameters, 1):
            facts.append(
                ParameterFact(
                    param_id=f"param-{idx}",
                    subject_anchor=_resolve_anchor(item.适用条件, item.所属章节, products),
                    raw_name=item.参数名称,
                    canonical_name=item.参数名称,
                    value_raw=item.参数值清洗值,
                    value_text=item.参数值清洗值,
                    value_min=item.参数范围下限,
                    value_max=item.参数范围上限,
                    comparator=item.比较符号,
                    unit_raw=item.参数单位,
                    unit_norm=item.参数单位,
                    condition=item.适用条件,
                    source_table=item.来源表格,
                    source_item=item.来源子项,
                    source_refs=[SourceRef(page_index=0, excerpt=item.来源子项 or item.参数名称)],
                    confidence=0.75,
                )
            )
    for fact in facts:
        fact.raw_name = normalize_line(fact.raw_name)
        fact.canonical_name = _canonicalize_parameter_name(fact.canonical_name or fact.raw_name)
        fact.unit_raw = _normalize_unit(fact.unit_raw)
        fact.unit_norm = _normalize_unit(fact.unit_norm or fact.unit_raw)
        fact.condition = normalize_line(fact.condition)
        fact.source_table = normalize_line(fact.source_table)
        fact.source_item = normalize_line(fact.source_item)
    return facts


def _normalize_rule_facts(facts: list[RuleFact], rules: list) -> list[RuleFact]:
    if not facts:
        facts = [
            RuleFact(
                rule_id=f"rule-{idx}",
                rule_type=rule.规则类型,
                text_raw=rule.规则内容,
                text_norm=rule.规则内容,
                subject_anchor=AnchorRef(anchor_type="section", anchor_id=rule.所属章节 or "文档", display_name=rule.所属章节 or "文档"),
                source_refs=[SourceRef(page_index=0, excerpt=rule.规则内容[:160])],
            )
            for idx, rule in enumerate(rules, 1)
        ]
    return facts


def _normalize_standard_facts(facts: list[StandardFact], standards: list) -> list[StandardFact]:
    if not facts:
        facts = [
            StandardFact(
                code_raw=item.标准编号,
                code_norm=item.标准编号,
                family=item.标准类型,
                title=item.标准名称,
                subject_anchor=AnchorRef(anchor_type="section", anchor_id=item.所属章节 or "文档", display_name=item.所属章节 or "文档"),
                source_refs=[SourceRef(page_index=0, excerpt=item.标准名称[:160] or item.标准编号)],
            )
            for item in standards
        ]
    return facts


def _resolve_anchor(condition: str, section_ref: str, products: list[ProductRecord]) -> AnchorRef:
    normalized_condition = normalize_line(condition)
    for product in products:
        display = product.anchor.display_name if product.anchor else (product.model or product.name)
        if display and display in normalized_condition:
            return AnchorRef(anchor_type="product", anchor_id=product.product_id, display_name=display)
    display = normalize_line(section_ref) or "文档"
    return AnchorRef(anchor_type="section", anchor_id=display, display_name=display)


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
