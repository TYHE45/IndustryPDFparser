from __future__ import annotations

import re
from typing import Any

from src.models import DocumentProfile
from src.utils import normalize_line

NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+){0,4}\s+\S+")
PART_RE = re.compile(r"^(?:第\s*\d+\s*部分|Part\s+\d+|Teil\s+\d+)", re.IGNORECASE)
STANDARD_RE = re.compile(r"\b(?:DIN|EN|ISO|SN|SEW|DVS|AD|TRbF|GB|CB)(?:\s+[A-Z]+)?\s*[0-9][0-9A-Za-z./\-—–]*\b")
MODEL_RE = re.compile(r"\b[A-Z]{1,5}(?:[-/][A-Z0-9]{2,}|\d{2,}[A-Z0-9/-]*)\b")
PRODUCT_HINT_RE = re.compile(r"(型号|系列|规格|参数|订货|选型|model|series|specification|ordering|type)", re.IGNORECASE)
MANUAL_HINT_RE = re.compile(r"(安装|操作|维护|步骤|警告|注意|installation|operation|maintenance|warning|caution)", re.IGNORECASE)
REPORT_HINT_RE = re.compile(r"(报告|证书|检验记录|测试结果|certificate|report|inspection|test report)", re.IGNORECASE)
ENGLISH_HINT_RE = re.compile(r"\b(the|and|for|with|application|dimensions|standard|requirements|inspection)\b", re.IGNORECASE)
GERMAN_HINT_RE = re.compile(r"\b(und|für|mit|maße|teil|anwendungsbereich|werkstoff|zitierte|prüfung)\b", re.IGNORECASE)


VALID_CHAR_RE = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9，。、；：！？\u201c\u201d\u2018\u2019（）【】《》,.;:!?\(\)\[\]\s]"
)


def _compute_quality_ratio(full_text: str, char_count: int) -> float:
    if char_count <= 0:
        return 1.0
    valid = sum(1 for ch in full_text if VALID_CHAR_RE.match(ch))
    return valid / max(1, char_count)


_WATERMARK_URL_RE = re.compile(r"(?:https?://|www\.)[\w\-.]+\.(?:com|cn|net|org|html?|asp|php)", re.IGNORECASE)
_WATERMARK_KEYWORDS_RE = re.compile(r"免费下载|建站|分享网|标准分享|bzfxw|17jzw|淘宝|文库|道客巴巴")
_ADVERTISEMENT_LINE_RE = re.compile(r"(?:17jzw|bzfxw|分享网|免费下载|建站平台|商业网站|标准下载|文库|道客巴巴|淘宝|www\.)", re.IGNORECASE)
_FRONT_MATTER_LINE_RE = re.compile(r"(?:备案号|邮政编码|邮编|电话|传真|网址|网站|印数|定价|出版|发行|版权|ISBN|地址|前言|发布|实施)", re.IGNORECASE)
_STANDARD_ENTITY_RE = re.compile(r"(?:GB|CB|ISO|GB/T|CB/T)\s*\d+-\d+")
_NUMERIC_PARAM_RE = re.compile(r"\d+\s*(?:mm|kg|MPa|℃)")
_SECTION_NUM_RE = re.compile(r"(?m)^\s*\d+\.\d+")
_SECTION_SIGNAL_LINE_RE = re.compile(
    r"^(?:\d+(?:\.\d+){0,4}\s+\S+|第\s*\d+\s*(?:章|节|部分)?|范围\b|要求\b|代号\b|术语\b|定义\b|标记\b|包装\b|运输\b|贮存\b|试验\b|检验\b)",
    re.IGNORECASE,
)
_TABLE_SIGNAL_RE = re.compile(r"(?:^|[\s(（])(?:表|图|Table|Figure|Fig\.?|Tabelle)\s*\d+", re.IGNORECASE)
_CONTENT_LINE_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def inspect_text_layer(lines: list[str]) -> dict[str, float | int | str]:
    normalized_lines = [normalize_line(line) for line in lines if normalize_line(line)]
    full_text = "\n".join(normalized_lines)
    char_count = sum(len(line) for line in normalized_lines)
    content_line_count = sum(1 for line in normalized_lines if _CONTENT_LINE_RE.search(line))
    quality_ratio = _compute_quality_ratio(full_text, char_count)
    advertisement_line_count = sum(1 for line in normalized_lines if _ADVERTISEMENT_LINE_RE.search(line))
    metadata_line_count = sum(1 for line in normalized_lines if _FRONT_MATTER_LINE_RE.search(line))
    structural_signal_count = (
        sum(1 for line in normalized_lines if _SECTION_SIGNAL_LINE_RE.search(line))
        + len(_STANDARD_ENTITY_RE.findall(full_text))
        + len(_NUMERIC_PARAM_RE.findall(full_text))
        + len(_TABLE_SIGNAL_RE.findall(full_text))
    )
    watermark_hit, watermark_reason = _looks_like_watermark_only(
        full_text,
        content_line_count=content_line_count,
        advertisement_line_count=advertisement_line_count,
        metadata_line_count=metadata_line_count,
        structural_signal_count=structural_signal_count,
    )
    return {
        "char_count": char_count,
        "quality_ratio": quality_ratio,
        "content_line_count": content_line_count,
        "advertisement_line_count": advertisement_line_count,
        "metadata_line_count": metadata_line_count,
        "advertisement_line_ratio": round(advertisement_line_count / max(1, content_line_count), 3),
        "metadata_line_ratio": round(metadata_line_count / max(1, content_line_count), 3),
        "structural_signal_count": structural_signal_count,
        "watermark_hit": int(watermark_hit),
        "watermark_reason": watermark_reason,
    }


def needs_ocr_by_text_layer(
    lines: list[str],
    *,
    page_count: int = 1,
    min_chars: int | None = None,
) -> tuple[bool, list[str], dict[str, float | int | str]]:
    metrics = inspect_text_layer(lines)
    char_floor = max(int(min_chars or 0), 60, page_count * 50)
    char_count = int(metrics["char_count"])
    quality_ratio = float(metrics["quality_ratio"])
    structural_signal_count = int(metrics["structural_signal_count"])
    advertisement_line_ratio = float(metrics["advertisement_line_ratio"])
    metadata_line_ratio = float(metrics["metadata_line_ratio"])
    watermark_hit = bool(metrics["watermark_hit"])

    reasons: list[str] = []
    if char_count < char_floor:
        reasons.append("low_text_chars")
    if char_count > 0 and quality_ratio < 0.5:
        reasons.append("low_quality_text_layer")
    if watermark_hit:
        reasons.append("watermark_only")
    if advertisement_line_ratio >= 0.25 and structural_signal_count == 0:
        reasons.append("advertisement_without_structure")
    if (
        structural_signal_count <= 1
        and metadata_line_ratio >= 0.6
        and char_count < max(char_floor * 4, page_count * 160)
    ):
        reasons.append("metadata_heavy_low_structure")
    return bool(reasons), list(dict.fromkeys(reasons)), metrics


def _looks_like_watermark_only(
    full_text: str,
    *,
    content_line_count: int = 0,
    advertisement_line_count: int = 0,
    metadata_line_count: int = 0,
    structural_signal_count: int = 0,
) -> tuple[bool, str]:
    if not full_text:
        return False, ""
    if _WATERMARK_URL_RE.search(full_text) and len(full_text) < 300:
        return True, "watermark_url_short_body"
    if _WATERMARK_KEYWORDS_RE.search(full_text):
        return True, "watermark_keyword"
    has_entity = bool(
        _STANDARD_ENTITY_RE.search(full_text)
        or _NUMERIC_PARAM_RE.search(full_text)
        or _SECTION_NUM_RE.search(full_text)
    )
    if advertisement_line_count > 0 and structural_signal_count == 0:
        return True, "advertisement_without_structure"
    if content_line_count and metadata_line_count >= max(2, content_line_count - 1) and structural_signal_count == 0:
        return True, "metadata_only"
    if not has_entity and len(full_text) < 220 and content_line_count <= 4:
        return True, "no_structural_entities"
    return False, ""


def profile_document(
    source_name: str,
    pages: list[dict[str, Any]],
    page_tables: dict[int, list[list[list[str]]]],
) -> DocumentProfile:
    sampled_lines = _collect_lines(pages)
    full_text = "\n".join(sampled_lines)
    table_count = sum(len(tables) for tables in page_tables.values())
    text_metrics = inspect_text_layer(sampled_lines)
    char_count = int(text_metrics["char_count"])
    avg_chars_per_page = round(char_count / max(1, len(pages)), 1)

    section_count = sum(1 for line in sampled_lines if NUMBERED_HEADING_RE.match(line))
    part_count = sum(1 for line in sampled_lines if PART_RE.match(line))
    standard_count = len(STANDARD_RE.findall(full_text))
    product_hint_count = sum(1 for line in sampled_lines if PRODUCT_HINT_RE.search(line))
    manual_hint_count = sum(1 for line in sampled_lines if MANUAL_HINT_RE.search(line))
    report_hint_count = sum(1 for line in sampled_lines if REPORT_HINT_RE.search(line))
    model_hits = {match for match in MODEL_RE.findall(full_text) if len(match) >= 4}

    needs_ocr, ocr_reason_codes, _ = needs_ocr_by_text_layer(sampled_lines, page_count=len(pages))
    quality_ratio = float(text_metrics["quality_ratio"])
    needs_ocr_override = "low_quality_text_layer" in ocr_reason_codes
    watermark_hit = "watermark_only" in ocr_reason_codes
    watermark_reason = str(text_metrics["watermark_reason"])

    profile = DocumentProfile(
        language=_detect_language(full_text),
        has_many_tables=table_count >= 4,
        has_product_cards=(
            product_hint_count >= 4
            or len(model_hits) >= 8
            or (product_hint_count >= 2 and table_count >= 2 and len(model_hits) >= 1)
        ),
        needs_ocr=needs_ocr,
        page_count=len(pages),
        text_line_count=len(sampled_lines),
        avg_chars_per_page=avg_chars_per_page,
        table_count=table_count,
    )
    profile.layout_mode = _infer_layout_mode(sampled_lines, table_count, profile.needs_ocr)

    if "low_text_chars" in ocr_reason_codes:
        profile.reasons.append("low_text_layer")
    if needs_ocr_override:
        profile.reasons.append("low_quality_text_layer")
        profile.reasons.append(f"text_quality_ratio={quality_ratio:.2f}")
    if watermark_hit:
        profile.reasons.append("watermark_only")
        profile.reasons.append(f"watermark_signal={watermark_reason}")
    if "advertisement_without_structure" in ocr_reason_codes:
        profile.reasons.append(f"advertisement_line_ratio={float(text_metrics['advertisement_line_ratio']):.2f}")
    if "metadata_heavy_low_structure" in ocr_reason_codes:
        profile.reasons.append("low_structural_signal")
        profile.reasons.append(f"metadata_line_ratio={float(text_metrics['metadata_line_ratio']):.2f}")

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
