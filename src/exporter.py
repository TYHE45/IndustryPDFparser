from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from src.models import DocumentData
from src.record_access import (
    inspection_dict,
    metadata_dict,
    parameter_dict,
    rule_dict,
    section_dict,
    section_ref,
    standard_dict,
    table_dict,
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
    safe_write_json(output_dir / "文档画像.json", _build_document_profile_json(document))
    safe_write_json(output_dir / "章节结构.json", [section_dict(item) for item in document.sections])
    safe_write_json(output_dir / "表格.json", [table_dict(item) for item in document.tables])
    safe_write_json(output_dir / "数值型参数.json", [parameter_dict(item) for item in document.numeric_parameters])
    safe_write_json(output_dir / "规则类内容.json", [rule_dict(item) for item in document.rules])
    safe_write_json(output_dir / "检验与证书.json", [inspection_dict(item) for item in document.inspections])
    safe_write_json(output_dir / "引用标准.json", [standard_dict(item) for item in document.standards])
    safe_write_json(output_dir / "trace_map.json", _build_trace_map_json(document))

    (output_dir / "原文解析.md").write_text(markdown, encoding="utf-8")
    safe_write_json(output_dir / "summary.json", summary)
    safe_write_json(output_dir / "tags.json", tags)
    safe_write_json(output_dir / "process_log.json", process_log)


def _build_document_profile_json(document: DocumentData) -> dict[str, Any]:
    profile = getattr(document, "profile", None)
    return {
        "metadata": metadata_dict(document.metadata),
        "profile": profile.to_dict() if profile is not None and hasattr(profile, "to_dict") else {},
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
        section_name = normalize_line(block.所属章节)
        page = block.来源页码
        if not section_name or not page:
            continue
        mapping.setdefault(section_name, set()).add(int(page))
    return {key: sorted(value) for key, value in mapping.items()}


def _table_trace_entry(table: Any, section_page_map: dict[str, list[int]]) -> dict[str, Any]:
    return {
        "table_id": table.表格编号,
        "table_title": table.表格标题,
        "section_ref": table.所属章节,
        "source_pages": _guess_table_pages(table.表格编号) or section_page_map.get(normalize_line(table.所属章节), []),
        "header_count": len(table.表头),
        "row_count": len(table.表体),
    }


def _guess_table_pages(table_id: str) -> list[int]:
    match = re.search(r"第(\d+)页", str(table_id))
    return [int(match.group(1))] if match else []


def _parameter_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.numeric_parameters:
        entries.append(
            {
                "parameter_id": item.参数ID,
                "parameter_name": item.参数名称,
                "anchor": item.主体锚点.to_dict() if item.主体锚点 else None,
                "source_table": item.来源表格,
                "source_item": item.来源子项,
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def _rule_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.rules:
        entries.append(
            {
                "rule_id": item.规则ID,
                "rule_type": item.规则类型,
                "anchor": item.主体锚点.to_dict() if item.主体锚点 else None,
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def _standard_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.standards:
        entries.append(
            {
                "code": item.标准编号,
                "family": item.标准族,
                "anchor": item.主体锚点.to_dict() if item.主体锚点 else None,
                "source_refs": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries
