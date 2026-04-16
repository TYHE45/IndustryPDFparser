from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from src.models import DocumentData
from src.record_access import (
    block_dict,
    inspection_dict,
    metadata_dict,
    parameter_dict,
    rule_dict,
    section_dict,
    section_ref,
    standard_dict,
    table_dict,
    table_values,
)
from src.utils import normalize_line, safe_write_json


def export_all(
    output_dir: Path,
    document: DocumentData,
    markdown: str,
    summary: dict[str, Any],
    tags: dict[str, Any],
    process_log: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_write_json(output_dir / "文件基础信息.json", metadata_dict(document.metadata))

    profile = getattr(document, "profile", None)
    if profile is not None and hasattr(profile, "to_dict"):
        safe_write_json(output_dir / "文档画像.json", profile.to_dict())
    safe_write_json(output_dir / "document_profile.json", _build_document_profile_json(document))

    safe_write_json(output_dir / "章节结构.json", [section_dict(item) for item in document.sections])
    safe_write_json(output_dir / "内容块.json", [block_dict(item) for item in document.blocks])
    safe_write_json(output_dir / "表格.json", [table_dict(item) for item in document.tables])
    safe_write_json(output_dir / "数值型参数.json", [parameter_dict(item) for item in document.numeric_parameters])
    safe_write_json(output_dir / "规则类内容.json", [rule_dict(item) for item in document.rules])
    safe_write_json(output_dir / "检验与证书.json", [inspection_dict(item) for item in document.inspections])
    safe_write_json(output_dir / "引用标准.json", [standard_dict(item) for item in document.standards])
    safe_write_json(output_dir / "原文解析.json", _build_raw_parse_json(document))
    safe_write_json(output_dir / "facts.json", _build_facts_json(document))
    safe_write_json(output_dir / "tables.json", _build_tables_json(document))
    safe_write_json(output_dir / "trace_map.json", _build_trace_map_json(document))

    _export_v2_views(output_dir, document)

    (output_dir / "原文解析.md").write_text(markdown, encoding="utf-8")
    safe_write_json(output_dir / "summary.json", summary)
    safe_write_json(output_dir / "tags.json", tags)
    safe_write_json(output_dir / "process_log.json", process_log)


def _export_v2_views(output_dir: Path, document: DocumentData) -> None:
    pages_v2 = getattr(document, "pages_v2", None)
    nodes_v2 = getattr(document, "nodes_v2", None)
    products_v2 = getattr(document, "products_v2", None)
    parameter_facts_v2 = getattr(document, "parameter_facts_v2", None)
    rule_facts_v2 = getattr(document, "rule_facts_v2", None)
    standard_facts_v2 = getattr(document, "standard_facts_v2", None)
    parsed_view = getattr(document, "parsed_view", None)

    if pages_v2:
        safe_write_json(output_dir / "页面记录_v2.json", [item.to_dict() for item in pages_v2])
    if nodes_v2:
        safe_write_json(output_dir / "结构节点_v2.json", [item.to_dict() for item in nodes_v2])
    if products_v2:
        safe_write_json(output_dir / "产品实体_v2.json", [item.to_dict() for item in products_v2])
    if parameter_facts_v2:
        safe_write_json(output_dir / "参数事实_v2.json", [item.to_dict() for item in parameter_facts_v2])
    if rule_facts_v2:
        safe_write_json(output_dir / "规则事实_v2.json", [item.to_dict() for item in rule_facts_v2])
    if standard_facts_v2:
        safe_write_json(output_dir / "标准实体_v2.json", [item.to_dict() for item in standard_facts_v2])
    if parsed_view is not None and hasattr(parsed_view, "to_dict"):
        safe_write_json(output_dir / "解析视图_v2.json", parsed_view.to_dict())


def _build_document_profile_json(document: DocumentData) -> dict[str, Any]:
    profile = getattr(document, "profile", None)
    return {
        "metadata": metadata_dict(document.metadata),
        "profile": profile.to_dict() if profile is not None and hasattr(profile, "to_dict") else {},
    }


def _build_raw_parse_json(document: DocumentData) -> dict[str, Any]:
    profile = getattr(document, "profile", None)
    pages_v2 = getattr(document, "pages_v2", None) or []
    nodes_v2 = getattr(document, "nodes_v2", None) or []
    products_v2 = getattr(document, "products_v2", None) or []
    return {
        "metadata": metadata_dict(document.metadata),
        "profile": profile.to_dict() if profile is not None and hasattr(profile, "to_dict") else {},
        "pages": [item.to_dict() for item in pages_v2],
        "sections": [section_dict(item) for item in document.sections],
        "blocks": [block_dict(item) for item in document.blocks],
        "tables": [table_dict(item) for item in document.tables],
        "nodes": [item.to_dict() for item in nodes_v2],
        "products": [item.to_dict() for item in products_v2],
    }


def _build_facts_json(document: DocumentData) -> dict[str, Any]:
    products_v2 = getattr(document, "products_v2", None) or []
    parameter_facts_v2 = getattr(document, "parameter_facts_v2", None) or []
    rule_facts_v2 = getattr(document, "rule_facts_v2", None) or []
    standard_facts_v2 = getattr(document, "standard_facts_v2", None) or []
    return {
        "products": [item.to_dict() for item in products_v2],
        "parameters": [item.to_dict() for item in parameter_facts_v2] or [parameter_dict(item) for item in document.numeric_parameters],
        "rules": [item.to_dict() for item in rule_facts_v2] or [rule_dict(item) for item in document.rules],
        "standards": [item.to_dict() for item in standard_facts_v2] or [standard_dict(item) for item in document.standards],
        "inspections": [inspection_dict(item) for item in document.inspections],
    }


def _build_tables_json(document: DocumentData) -> dict[str, Any]:
    return {
        "count": len(document.tables),
        "tables": [table_dict(item) for item in document.tables],
    }


def _build_trace_map_json(document: DocumentData) -> dict[str, Any]:
    section_page_map = _build_section_page_map(document)
    return {
        "sections": [
            {
                "section_ref": section_ref(section),
                "source_pages": section_page_map.get(normalize_line(section_ref(section)), []),
            }
            for section in document.sections
        ],
        "tables": [_table_trace_entry(table, section_page_map) for table in document.tables],
        "parameters": _parameter_trace_entries(document),
        "rules": _rule_trace_entries(document),
        "standards": _standard_trace_entries(document),
    }


def _build_section_page_map(document: DocumentData) -> dict[str, list[int]]:
    mapping: dict[str, set[int]] = {}
    for block in document.blocks:
        section_name = normalize_line(getattr(block, "所属章节", ""))
        page = getattr(block, "来源页码", 0)
        if not section_name or not page:
            continue
        mapping.setdefault(section_name, set()).add(int(page))
    return {key: sorted(value) for key, value in mapping.items()}


def _table_trace_entry(table: Any, section_page_map: dict[str, list[int]]) -> dict[str, Any]:
    table_id, table_title, section_name, headers, rows = table_values(table)
    return {
        "table_id": table_id,
        "table_title": table_title,
        "section_ref": section_name,
        "source_pages": _guess_table_pages(table_id) or section_page_map.get(normalize_line(section_name), []),
        "header_count": len(headers),
        "row_count": len(rows),
    }


def _guess_table_pages(table_id: str) -> list[int]:
    match = re.search(r"第(\d+)页", str(table_id))
    return [int(match.group(1))] if match else []


def _parameter_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    parameter_facts_v2 = getattr(document, "parameter_facts_v2", None) or []
    if parameter_facts_v2:
        entries: list[dict[str, Any]] = []
        for item in parameter_facts_v2:
            data = item.to_dict()
            entries.append(
                {
                    "parameter_id": data.get("param_id", ""),
                    "parameter_name": data.get("canonical_name") or data.get("raw_name", ""),
                    "anchor": data.get("subject_anchor"),
                    "source_table": data.get("source_table", ""),
                    "source_item": data.get("source_item", ""),
                    "source_refs": data.get("source_refs", []),
                }
            )
        return entries
    return [
        {
            "parameter_name": entry.get("参数名称", ""),
            "section_ref": entry.get("所属章节", ""),
            "source_table": entry.get("来源表格", ""),
            "source_item": entry.get("来源子项", ""),
        }
        for entry in [parameter_dict(item) for item in document.numeric_parameters]
    ]


def _rule_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    rule_facts_v2 = getattr(document, "rule_facts_v2", None) or []
    if rule_facts_v2:
        entries: list[dict[str, Any]] = []
        for item in rule_facts_v2:
            data = item.to_dict()
            entries.append(
                {
                    "rule_id": data.get("rule_id", ""),
                    "rule_type": data.get("rule_type", ""),
                    "anchor": data.get("subject_anchor"),
                    "source_refs": data.get("source_refs", []),
                }
            )
        return entries
    return [
        {
            "rule_type": entry.get("规则类型", ""),
            "section_ref": entry.get("所属章节", ""),
        }
        for entry in [rule_dict(item) for item in document.rules]
    ]


def _standard_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    standard_facts_v2 = getattr(document, "standard_facts_v2", None) or []
    if standard_facts_v2:
        entries: list[dict[str, Any]] = []
        for item in standard_facts_v2:
            data = item.to_dict()
            entries.append(
                {
                    "code": data.get("code_norm") or data.get("code_raw", ""),
                    "family": data.get("family", ""),
                    "anchor": data.get("subject_anchor"),
                    "source_refs": data.get("source_refs", []),
                }
            )
        return entries
    return [
        {
            "code": entry.get("标准编号", ""),
            "section_ref": entry.get("所属章节", ""),
        }
        for entry in [standard_dict(item) for item in document.standards]
    ]
