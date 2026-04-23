from __future__ import annotations

from typing import Any

from src.models import DocumentData
from src.record_access import section_ref
from src.utils import normalize_line


def get_profile_dict(document: DocumentData) -> dict[str, Any]:
    profile = getattr(document, "文档画像", None)
    return profile.to_dict() if profile is not None and hasattr(profile, "to_dict") else {}


def get_section_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for section in document.章节列表:
        heading = normalize_line(
            section.章节标题 if str(section.章节编号).startswith("U") else f"{section.章节编号} {section.章节标题}".strip()
        )
        entries.append(
            {
                "number": normalize_line(section.章节编号),
                "title": normalize_line(section.章节标题),
                "heading": heading,
                "level": int(section.章节层级),
                "parent_number": normalize_line(section.父章节编号),
                "body": str(section.章节清洗文本),
                "part": normalize_line(section.所属部分),
            }
        )
    return entries


def get_parameter_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.数值参数列表:
        anchor = item.主体锚点
        anchor_dict = anchor.to_dict() if anchor else {}
        entries.append(
            {
                "id": item.参数ID,
                "name": normalize_line(item.参数名称),
                "raw_name": normalize_line(item.参数名称),
                "value_text": normalize_line(item.参数值清洗值),
                "value_min": normalize_line(item.参数范围下限),
                "value_max": normalize_line(item.参数范围上限),
                "comparator": normalize_line(item.比较符号),
                "unit": normalize_line(item.参数单位),
                "condition": normalize_line(item.适用条件),
                "section_name": normalize_line(anchor.显示名称 if anchor else item.所属章节),
                "anchor": anchor_dict,
                "source_table": normalize_line(item.来源表格),
                "source_item": normalize_line(item.来源子项),
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def get_rule_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.规则列表:
        anchor = item.主体锚点
        anchor_dict = anchor.to_dict() if anchor else {}
        entries.append(
            {
                "id": item.规则ID,
                "rule_type": normalize_line(item.规则类型),
                "content": normalize_line(item.规则内容),
                "condition": normalize_line(item.适用条件),
                "section_name": normalize_line(anchor.显示名称 if anchor else item.所属章节),
                "anchor": anchor_dict,
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def get_standard_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.引用标准列表:
        anchor = item.主体锚点
        anchor_dict = anchor.to_dict() if anchor else {}
        entries.append(
            {
                "code": normalize_line(item.标准编号),
                "title": normalize_line(item.标准名称),
                "family": normalize_line(item.标准族 or item.标准类型),
                "section_name": normalize_line(anchor.显示名称 if anchor else item.所属章节),
                "anchor": anchor_dict,
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def get_product_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.产品列表:
        anchor = item.锚点
        anchor_dict = anchor.to_dict() if anchor else {}
        entries.append(
            {
                "id": item.产品ID,
                "name": normalize_line(item.名称),
                "model": normalize_line(item.型号),
                "series": normalize_line(item.系列),
                "anchor": anchor_dict,
                "display_name": normalize_line(
                    (anchor.显示名称 if anchor else "") or item.型号 or item.名称 or item.系列
                ),
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries
