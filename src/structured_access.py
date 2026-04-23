from __future__ import annotations

from typing import Any

from src.models import DocumentData
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
                "章节编号": normalize_line(section.章节编号),
                "章节标题": normalize_line(section.章节标题),
                "章节标题全称": heading,
                "章节层级": int(section.章节层级),
                "父章节编号": normalize_line(section.父章节编号),
                "章节正文": str(section.章节清洗文本),
                "所属部分": normalize_line(section.所属部分),
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
                "ID": item.参数ID,
                "参数名称": normalize_line(item.参数名称),
                "原始名称": normalize_line(item.参数名称),
                "参数值文本": normalize_line(item.参数值清洗值),
                "参数范围下限": normalize_line(item.参数范围下限),
                "参数范围上限": normalize_line(item.参数范围上限),
                "比较符号": normalize_line(item.比较符号),
                "单位": normalize_line(item.参数单位),
                "适用条件": normalize_line(item.适用条件),
                "所属章节": normalize_line(anchor.显示名称 if anchor else item.所属章节),
                "主体锚点": anchor_dict,
                "来源表格": normalize_line(item.来源表格),
                "来源子项": normalize_line(item.来源子项),
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
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
                "ID": item.规则ID,
                "规则类型": normalize_line(item.规则类型),
                "内容": normalize_line(item.规则内容),
                "适用条件": normalize_line(item.适用条件),
                "所属章节": normalize_line(anchor.显示名称 if anchor else item.所属章节),
                "主体锚点": anchor_dict,
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
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
                "标准编号": normalize_line(item.标准编号),
                "标准名称": normalize_line(item.标准名称),
                "标准族": normalize_line(item.标准族 or item.标准类型),
                "所属章节": normalize_line(anchor.显示名称 if anchor else item.所属章节),
                "主体锚点": anchor_dict,
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
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
                "ID": item.产品ID,
                "名称": normalize_line(item.名称),
                "型号": normalize_line(item.型号),
                "系列": normalize_line(item.系列),
                "主体锚点": anchor_dict,
                "显示名称": normalize_line(
                    (anchor.显示名称 if anchor else "") or item.型号 or item.名称 or item.系列
                ),
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries
