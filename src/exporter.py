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
    safe_write_json(output_dir / "章节结构.json", [section_dict(item) for item in document.章节列表])
    safe_write_json(output_dir / "表格.json", [table_dict(item) for item in document.表格列表])
    safe_write_json(output_dir / "数值型参数.json", [parameter_dict(item) for item in document.数值参数列表])
    safe_write_json(output_dir / "规则类内容.json", [rule_dict(item) for item in document.规则列表])
    safe_write_json(output_dir / "检验与证书.json", [inspection_dict(item) for item in document.检验列表])
    safe_write_json(output_dir / "引用标准.json", [standard_dict(item) for item in document.引用标准列表])
    safe_write_json(output_dir / "trace_map.json", _build_trace_map_json(document))

    (output_dir / "原文解析.md").write_text(markdown, encoding="utf-8")
    safe_write_json(output_dir / "summary.json", {k: v for k, v in (summary or {}).items() if not k.startswith("_")})
    safe_write_json(output_dir / "tags.json", {k: v for k, v in (tags or {}).items() if not k.startswith("_")})
    safe_write_json(output_dir / "process_log.json", process_log)


def _build_document_profile_json(document: DocumentData) -> dict[str, Any]:
    profile = getattr(document, "文档画像", None)
    return {
        "元数据": metadata_dict(document.文件元数据),
        "文档画像": profile.to_dict() if profile is not None and hasattr(profile, "to_dict") else {},
    }


def _build_trace_map_json(document: DocumentData) -> dict[str, Any]:
    section_page_map = _build_section_page_map(document)
    return {
        "章节": [
            {
                "章节引用": section_ref(section),
                "来源页码": section_page_map.get(normalize_line(section_ref(section)), []),
            }
            for section in document.章节列表
        ],
        "表格": [_table_trace_entry(table, section_page_map) for table in document.表格列表],
        "参数": _parameter_trace_entries(document),
        "规则": _rule_trace_entries(document),
        "引用标准": _standard_trace_entries(document),
    }


def _build_section_page_map(document: DocumentData) -> dict[str, list[int]]:
    mapping: dict[str, set[int]] = {}
    for block in document.内容块列表:
        section_name = normalize_line(block.所属章节)
        page = block.来源页码
        if not section_name or not page:
            continue
        mapping.setdefault(section_name, set()).add(int(page))
    return {key: sorted(value) for key, value in mapping.items()}


def _table_trace_entry(table: Any, section_page_map: dict[str, list[int]]) -> dict[str, Any]:
    return {
        "表格编号": table.表格编号,
        "表格标题": table.表格标题,
        "所属章节": table.所属章节,
        "来源页码": _guess_table_pages(table.表格编号) or section_page_map.get(normalize_line(table.所属章节), []),
        "表头列数": len(table.表头),
        "数据行数": len(table.表体),
    }


def _guess_table_pages(table_id: str) -> list[int]:
    match = re.search(r"第(\d+)页", str(table_id))
    return [int(match.group(1))] if match else []


def _parameter_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.数值参数列表:
        entries.append(
            {
                "参数ID": item.参数ID,
                "参数名称": item.参数名称,
                "主体锚点": item.主体锚点.to_dict() if item.主体锚点 else None,
                "来源表格": item.来源表格,
                "来源子项": item.来源子项,
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def _rule_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.规则列表:
        entries.append(
            {
                "规则ID": item.规则ID,
                "规则类型": item.规则类型,
                "主体锚点": item.主体锚点.to_dict() if item.主体锚点 else None,
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries


def _standard_trace_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.引用标准列表:
        entries.append(
            {
                "标准编号": item.标准编号,
                "标准族": item.标准族,
                "主体锚点": item.主体锚点.to_dict() if item.主体锚点 else None,
                "来源引用列表": [ref.to_dict() for ref in item.来源引用列表],
            }
        )
    return entries
