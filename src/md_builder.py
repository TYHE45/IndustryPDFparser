from __future__ import annotations

from collections import OrderedDict
import re

from src.models import DocumentData
from src.record_access import metadata_dict, section_ref, section_values, standard_values, table_values
from src.utils import normalize_line

SYNTHETIC_TABLE_TITLE_RE = re.compile(r"^第\d+页表\d+$")
LOW_SIGNAL_TABLE_TITLE_RE = re.compile(
    r"^(?:zitierte normen|引用标准|references|reference standards|weitere normen|further standards)$",
    re.IGNORECASE,
)
COMMA_FRAGMENT_TABLE_TITLE_RE = re.compile(r".+,\s*$")


def build_markdown(document: DocumentData) -> str:
    meta = metadata_dict(document.metadata)
    lines: list[str] = [
        f"# {meta['文档标题'] or meta['文件名称']}",
        "",
        "## 文件基础信息",
        f"- 文件名称：{meta['文件名称']}",
        f"- 文档类型：{meta['文档类型']}",
        f"- 标准编号：{meta['标准编号']}",
        f"- 版本日期：{meta['版本日期']}",
        f"- 适用范围：{meta['适用范围']}",
        "",
    ]

    tables_by_section: dict[str, list] = {}
    for table in document.tables:
        _, _, table_section, _, _ = table_values(table)
        tables_by_section.setdefault(normalize_line(table_section), []).append(table)

    current_part = ""
    for section in document.sections:
        number, title, level, _, body, part = section_values(section)
        normalized_title = normalize_line(title)
        part = normalize_line(part)
        if part and part != current_part:
            current_part = part
            lines.extend([f"## {current_part}", ""])

        heading_level = min(max(int(level), 1) + 2, 6)
        cleaned_body = _clean_body(body)
        section_tables = tables_by_section.get(normalize_line(section_ref(section)), [])
        suppress_section_heading = _should_suppress_section_heading(str(number), normalized_title, cleaned_body, section_tables)
        if not suppress_section_heading:
            heading = normalized_title if str(number).startswith("U") else f"{number} {normalized_title}".strip()
            lines.extend([f"{'#' * heading_level} {normalize_line(heading)}", ""])

        if cleaned_body:
            lines.extend([cleaned_body, ""])

        rendered_table_titles: set[str] = set()
        title_for_comparison = "" if suppress_section_heading else normalized_title
        for table in section_tables:
            _, table_title, _, headers, rows = table_values(table)
            table_heading = normalize_line(table_title)
            if _should_render_table_heading(table_heading, title_for_comparison, rendered_table_titles):
                rendered_table_titles.add(table_heading.casefold())
                lines.extend([f"{'#' * min(heading_level + 1, 6)} {table_heading}", ""])
            if headers:
                lines.append("| " + " | ".join(headers) + " |")
                lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for row in rows:
                    padded = row + [""] * max(0, len(headers) - len(row))
                    lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
                lines.append("")

    standards = _collect_standards(document)
    if standards:
        lines.extend(["## 引用标准", ""])
        for code, desc in standards.items():
            lines.append(f"- {code}" if not desc or desc == code else f"- {code}：{desc}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _clean_body(text: str) -> str:
    rows: list[str] = []
    for raw in str(text).splitlines():
        line = normalize_line(raw)
        if line:
            rows.append(line)
    return "\n".join(rows)


def _should_render_table_heading(title: str, section_title: str, rendered_titles: set[str]) -> bool:
    normalized = normalize_line(title)
    if not normalized:
        return False
    if SYNTHETIC_TABLE_TITLE_RE.fullmatch(normalized):
        return False
    if LOW_SIGNAL_TABLE_TITLE_RE.fullmatch(normalized):
        return False
    if COMMA_FRAGMENT_TABLE_TITLE_RE.fullmatch(normalized):
        return False
    if normalized.casefold() == normalize_line(section_title).casefold():
        return False
    if normalized.casefold() in rendered_titles:
        return False
    return True


def _should_suppress_section_heading(number: str, title: str, body: str, section_tables: list) -> bool:
    normalized_title = normalize_line(title)
    if not str(number).startswith("U"):
        return False
    if body:
        return False
    if not section_tables:
        return False
    table_titles = [normalize_line(table_values(item)[1]) for item in section_tables]
    return any(item and item.casefold() == normalized_title.casefold() for item in table_titles)


def _collect_standards(document: DocumentData) -> OrderedDict[str, str]:
    result: OrderedDict[str, str] = OrderedDict()
    for item in document.standards:
        code, title, _, _ = standard_values(item)
        code = normalize_line(code)
        title = normalize_line(title)
        if code and code not in result:
            result[code] = title
    return result
