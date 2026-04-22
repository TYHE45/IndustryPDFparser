from __future__ import annotations

import re

from src.models import DocumentData
from src.record_access import metadata_title
from src.utils import normalize_line

STANDARD_CODE_TOKEN_RE = re.compile(
    r"\b(?P<base>[A-Z]{2,4})"
    r"(?:[/_\-\s]?(?P<sub>[A-Z]))?"
    r"[\s_]*(?P<number>\d+(?:\.\d+)*)"
    r"\s*[-—–_.一]\s*(?P<year>\d{2,4}(?:-\d{2})?)\b",
    re.IGNORECASE,
)


def canonicalize_standard_code(text: str) -> str:
    match = STANDARD_CODE_TOKEN_RE.search(normalize_line(text))
    if not match:
        return ""
    base = match.group("base").upper()
    sub = (match.group("sub") or "").upper()
    number = match.group("number")
    year = re.sub(r"[-—–_.一]+", "-", match.group("year"))
    if re.fullmatch(r"\d{2}", year):
        year = f"19{year}" if int(year) >= 80 else f"20{year}"
    family = f"{base}/{sub}" if sub else base
    return f"{family} {number}-{year}"


def extract_canonical_standard_codes(text: str) -> set[str]:
    codes: set[str] = set()
    normalized = normalize_line(text)
    for match in STANDARD_CODE_TOKEN_RE.finditer(normalized):
        code = canonicalize_standard_code(match.group(0))
        if code:
            codes.add(code)
    return codes


def strip_markdown_metadata(markdown: str) -> str:
    lines = markdown.splitlines()
    cleaned: list[str] = []
    in_file_info = False
    for line in lines:
        normalized = normalize_line(line.lstrip("#").strip())
        if normalized == "文件基础信息":
            in_file_info = True
            continue
        if in_file_info and line.lstrip().startswith("#"):
            in_file_info = False
        if in_file_info:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def detect_metadata_mismatch_reason(document: DocumentData, markdown: str) -> str:
    file_name = normalize_line(getattr(document.metadata, "文件名称", "") or "")
    if not file_name:
        return ""

    expected_codes = extract_canonical_standard_codes(file_name)
    if not expected_codes:
        return ""

    body_markdown = strip_markdown_metadata(markdown)
    metadata_title_text = normalize_line(metadata_title(document.metadata))
    section_text = "\n".join(
        normalize_line(part)
        for section in document.sections[:3]
        for part in (
            getattr(section, "章节标题", ""),
            getattr(section, "章节清洗文本", "")[:240],
        )
        if normalize_line(part)
    )
    body_codes = extract_canonical_standard_codes("\n".join([body_markdown[:4000], section_text]))
    title_codes = extract_canonical_standard_codes(metadata_title_text)
    standard_codes = {
        code
        for item in document.standards
        if (code := canonicalize_standard_code(getattr(item, "标准编号", "") or ""))
    }

    evidence_codes = body_codes | title_codes | standard_codes
    if evidence_codes & expected_codes:
        return ""

    conflicts = sorted(code for code in evidence_codes if code not in expected_codes)
    if not conflicts:
        return ""

    expected = sorted(expected_codes)[0]
    conflict = conflicts[0]
    return f"文件名预期标准号为 {expected}，但正文/标题/引用标准更明显地指向 {conflict}，疑似源文件串档或文本层错配。"


__all__ = [
    "canonicalize_standard_code",
    "detect_metadata_mismatch_reason",
    "extract_canonical_standard_codes",
    "strip_markdown_metadata",
]
