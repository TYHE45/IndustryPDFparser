from __future__ import annotations

import re
from typing import Any

from src.models import DocumentProfile
from src.utils import normalize_line

NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+){0,4}\s+\S+")
PART_RE = re.compile(r"^(?:第\s*\d+\s*部分|Part\s+\d+|Teil\s+\d+)", re.IGNORECASE)
STANDARD_RE = re.compile(r"\b(?:DIN|EN|ISO|SN|SEW|DVS|AD)(?:\s+[A-Z]+)?\s*[0-9][0-9A-Za-z./\-]*\b")
MODEL_RE = re.compile(r"\b[A-Z]{1,5}(?:[-/][A-Z0-9]{2,}|\d{2,}[A-Z0-9/-]*)\b")
PRODUCT_HINT_RE = re.compile(r"(型号|系列|规格|参数|订货|选型|model|series|specification|ordering|type)", re.IGNORECASE)
MANUAL_HINT_RE = re.compile(r"(安装|操作|维护|步骤|警告|注意|installation|operation|maintenance|warning|caution)", re.IGNORECASE)
REPORT_HINT_RE = re.compile(r"(报告|证书|检验记录|测试结果|certificate|report|inspection|test report)", re.IGNORECASE)
ENGLISH_HINT_RE = re.compile(r"\b(the|and|for|with|application|dimensions|standard|requirements|inspection)\b", re.IGNORECASE)
GERMAN_HINT_RE = re.compile(r"\b(und|für|mit|maße|teil|anwendungsbereich|werkstoff|zitierte|prüfung)\b", re.IGNORECASE)


def profile_document(
    source_name: str,
    pages: list[dict[str, Any]],
    page_tables: dict[int, list[list[list[str]]]],
) -> DocumentProfile:
    sampled_lines = _collect_lines(pages)
    full_text = "\n".join(sampled_lines)
    table_count = sum(len(tables) for tables in page_tables.values())
    char_count = sum(len(line) for line in sampled_lines)
    avg_chars_per_page = round(char_count / max(1, len(pages)), 1)

    section_count = sum(1 for line in sampled_lines if NUMBERED_HEADING_RE.match(line))
    part_count = sum(1 for line in sampled_lines if PART_RE.match(line))
    standard_count = len(STANDARD_RE.findall(full_text))
    product_hint_count = sum(1 for line in sampled_lines if PRODUCT_HINT_RE.search(line))
    manual_hint_count = sum(1 for line in sampled_lines if MANUAL_HINT_RE.search(line))
    report_hint_count = sum(1 for line in sampled_lines if REPORT_HINT_RE.search(line))
    model_hits = {match for match in MODEL_RE.findall(full_text) if len(match) >= 4}

    profile = DocumentProfile(
        language=_detect_language(full_text),
        has_many_tables=table_count >= 4,
        has_product_cards=(
            product_hint_count >= 4
            or len(model_hits) >= 8
            or (product_hint_count >= 2 and table_count >= 2 and len(model_hits) >= 1)
        ),
        needs_ocr=char_count < max(60, len(pages) * 50),
        page_count=len(pages),
        text_line_count=len(sampled_lines),
        avg_chars_per_page=avg_chars_per_page,
        table_count=table_count,
    )
    profile.layout_mode = _infer_layout_mode(sampled_lines, table_count, profile.needs_ocr)

    if profile.needs_ocr:
        profile.reasons.append("low_text_layer")

    if standard_count >= 4 or part_count >= 1 or section_count >= 3:
        profile.doc_type = "standard"
        profile.confidence = _cap_confidence(0.58 + standard_count * 0.015 + part_count * 0.08 + min(0.12, section_count * 0.01))
        profile.reasons.extend(
            [
                f"standard_refs={standard_count}",
                f"part_like_headings={part_count}",
                f"numbered_sections={section_count}",
            ]
        )
        return profile

    if (
        (product_hint_count >= 2 and table_count >= 2 and len(model_hits) >= 1)
        or (product_hint_count >= 4 and table_count >= 1)
        or (len(model_hits) >= 8 and table_count >= 1)
    ):
        profile.doc_type = "product_catalog"
        profile.confidence = _cap_confidence(0.55 + product_hint_count * 0.03 + min(0.18, len(model_hits) * 0.01))
        profile.reasons.extend(
            [
                f"product_hints={product_hint_count}",
                f"model_like_tokens={len(model_hits)}",
                f"tables={table_count}",
            ]
        )
        return profile

    if manual_hint_count >= 4:
        profile.doc_type = "manual"
        profile.confidence = _cap_confidence(0.52 + manual_hint_count * 0.04)
        profile.reasons.extend([f"manual_hints={manual_hint_count}", f"tables={table_count}"])
        return profile

    if report_hint_count >= 3:
        profile.doc_type = "report"
        profile.confidence = _cap_confidence(0.52 + report_hint_count * 0.05)
        profile.reasons.extend([f"report_hints={report_hint_count}", f"tables={table_count}"])
        return profile

    profile.doc_type = "unknown"
    profile.confidence = _cap_confidence(0.28 + standard_count * 0.01 + product_hint_count * 0.02)
    profile.reasons.extend(
        [
            f"source={source_name}",
            f"tables={table_count}",
            f"standard_refs={standard_count}",
            f"product_hints={product_hint_count}",
        ]
    )
    return profile


def _collect_lines(pages: list[dict[str, Any]], max_pages: int = 30) -> list[str]:
    lines: list[str] = []
    for page in pages[:max_pages]:
        for line in page.get("lines", []):
            normalized = normalize_line(line)
            if normalized:
                lines.append(normalized)
    return lines


def _detect_language(text: str) -> str:
    if not text:
        return "unknown"
    zh_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    en_hits = len(ENGLISH_HINT_RE.findall(text))
    de_hits = len(GERMAN_HINT_RE.findall(text))
    if zh_count >= 30:
        return "zh"
    if de_hits >= en_hits and de_hits >= 3:
        return "de"
    if en_hits >= 3:
        return "en"
    if re.search(r"[äöüßÄÖÜ]", text):
        return "de"
    return "unknown"


def _infer_layout_mode(lines: list[str], table_count: int, needs_ocr: bool) -> str:
    if needs_ocr:
        return "scan_like"
    if not lines:
        return "single_column"
    short_ratio = sum(1 for line in lines if len(line) <= 18) / max(1, len(lines))
    if table_count >= 4 and short_ratio >= 0.35:
        return "dense_table"
    if table_count >= 2:
        return "table_driven"
    if short_ratio >= 0.55:
        return "fragmented"
    return "single_column"


def _cap_confidence(value: float) -> float:
    return round(max(0.0, min(0.98, value)), 2)
