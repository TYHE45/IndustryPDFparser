from __future__ import annotations

from typing import Any

from src.models import DocumentData
from src.record_access import parameter_values, rule_values, section_values, standard_values
from src.utils import normalize_line


def get_profile_dict(document: DocumentData) -> dict[str, Any]:
    profile = getattr(document, "profile", None)
    return profile.to_dict() if profile is not None and hasattr(profile, "to_dict") else {}


def get_section_entries(document: DocumentData) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in document.sections:
        number, title, level, parent_number, body, part = section_values(item)
        heading = normalize_line(title if str(number).startswith("U") else f"{number} {title}".strip())
        entries.append(
            {
                "number": normalize_line(number),
                "title": normalize_line(title),
                "heading": heading,
                "level": int(level),
                "parent_number": normalize_line(parent_number),
                "body": str(body),
                "part": normalize_line(part),
            }
        )
    return entries


def get_parameter_entries(document: DocumentData) -> list[dict[str, Any]]:
    facts = getattr(document, "parameter_facts_v2", None) or []
    if facts:
        entries: list[dict[str, Any]] = []
        for item in facts:
            data = item.to_dict()
            anchor = data.get("subject_anchor") or {}
            entries.append(
                {
                    "id": data.get("param_id", ""),
                    "name": normalize_line(data.get("canonical_name") or data.get("raw_name", "")),
                    "raw_name": normalize_line(data.get("raw_name", "")),
                    "value_text": normalize_line(data.get("value_text") or data.get("value_raw", "")),
                    "value_min": normalize_line(data.get("value_min", "")),
                    "value_max": normalize_line(data.get("value_max", "")),
                    "comparator": normalize_line(data.get("comparator", "")),
                    "unit": normalize_line(data.get("unit_norm") or data.get("unit_raw", "")),
                    "condition": normalize_line(data.get("condition", "")),
                    "section_name": normalize_line(anchor.get("display_name", "")),
                    "anchor": anchor,
                    "source_table": normalize_line(data.get("source_table", "")),
                    "source_item": normalize_line(data.get("source_item", "")),
                    "source_refs": data.get("source_refs", []),
                }
            )
        return entries

    entries = []
    for item in document.numeric_parameters:
        name, value_text, unit, lower, upper, comparator, condition, section_name, source_table, source_item = parameter_values(item)
        entries.append(
            {
                "id": "",
                "name": normalize_line(name),
                "raw_name": normalize_line(name),
                "value_text": normalize_line(value_text),
                "value_min": normalize_line(lower),
                "value_max": normalize_line(upper),
                "comparator": normalize_line(comparator),
                "unit": normalize_line(unit),
                "condition": normalize_line(condition),
                "section_name": normalize_line(section_name),
                "anchor": {},
                "source_table": normalize_line(source_table),
                "source_item": normalize_line(source_item),
                "source_refs": [],
            }
        )
    return entries


def get_rule_entries(document: DocumentData) -> list[dict[str, Any]]:
    facts = getattr(document, "rule_facts_v2", None) or []
    if facts:
        entries: list[dict[str, Any]] = []
        for item in facts:
            data = item.to_dict()
            anchor = data.get("subject_anchor") or {}
            entries.append(
                {
                    "id": data.get("rule_id", ""),
                    "rule_type": normalize_line(data.get("rule_type", "")),
                    "content": normalize_line(data.get("text_norm") or data.get("text_raw", "")),
                    "section_name": normalize_line(anchor.get("display_name", "")),
                    "anchor": anchor,
                    "source_refs": data.get("source_refs", []),
                }
            )
        return entries

    entries = []
    for item in document.rules:
        rule_type, content, condition, section_name = rule_values(item)
        entries.append(
            {
                "id": "",
                "rule_type": normalize_line(rule_type),
                "content": normalize_line(content),
                "condition": normalize_line(condition),
                "section_name": normalize_line(section_name),
                "anchor": {},
                "source_refs": [],
            }
        )
    return entries


def get_standard_entries(document: DocumentData) -> list[dict[str, Any]]:
    facts = getattr(document, "standard_facts_v2", None) or []
    if facts:
        entries: list[dict[str, Any]] = []
        for item in facts:
            data = item.to_dict()
            anchor = data.get("subject_anchor") or {}
            entries.append(
                {
                    "code": normalize_line(data.get("code_norm") or data.get("code_raw", "")),
                    "title": normalize_line(data.get("title", "")),
                    "family": normalize_line(data.get("family", "")),
                    "section_name": normalize_line(anchor.get("display_name", "")),
                    "anchor": anchor,
                    "source_refs": data.get("source_refs", []),
                }
            )
        return entries

    entries = []
    for item in document.standards:
        code, title, standard_type, section_name = standard_values(item)
        entries.append(
            {
                "code": normalize_line(code),
                "title": normalize_line(title),
                "family": normalize_line(standard_type),
                "section_name": normalize_line(section_name),
                "anchor": {},
                "source_refs": [],
            }
        )
    return entries


def get_product_entries(document: DocumentData) -> list[dict[str, Any]]:
    products = getattr(document, "products_v2", None) or []
    entries: list[dict[str, Any]] = []
    for item in products:
        anchor = item.anchor.to_dict() if item.anchor else {}
        entries.append(
            {
                "id": item.product_id,
                "name": normalize_line(item.name),
                "model": normalize_line(item.model),
                "series": normalize_line(item.series),
                "anchor": anchor,
                "display_name": normalize_line(anchor.get("display_name", "") or item.model or item.name or item.series),
                "source_refs": [ref.to_dict() for ref in item.source_refs],
            }
        )
    return entries
