from __future__ import annotations

import re
from collections import Counter

from src.models import OCRBatchEvaluation, OCRPageEvaluation

SECTION_SIGNAL_RE = re.compile(
    r"(?:^\d+(?:\.\d+){0,4}\s+\S+|^第\s*\d+\s*(?:章|节|部分)?|^(?:范围|要求|标记示例|引用文件|结构和规格尺寸)\b)"
)
STANDARD_SIGNAL_RE = re.compile(r"\b(?:DIN|EN|ISO|SN|SEW|DVS|AD|TRbF|GB|CB)\s*[0-9][0-9A-Za-z./\-—–]*\b")
TABLE_SIGNAL_RE = re.compile(r"(?:表|图|Table|Figure|Fig\.?|Tabelle)\s*\d+", re.IGNORECASE)
CONTENT_CHAR_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
PUNCT_CHAR_RE = re.compile(r"[^\w\s\u4e00-\u9fff]")
ISOLATED_PUNCT_CHARS = "。，；：！？"
CJK_OR_ASCII_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def _isolated_punct_ratio(text: str) -> float:
    if not text:
        return 0.0
    total = 0
    isolated = 0
    for idx, ch in enumerate(text):
        if ch in ISOLATED_PUNCT_CHARS:
            total += 1
            left = text[max(0, idx - 2):idx]
            right = text[idx + 1:idx + 3]
            if not CJK_OR_ASCII_RE.search(left) and not CJK_OR_ASCII_RE.search(right):
                isolated += 1
    return isolated / max(1, total)


def _short_line_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    short = sum(1 for line in lines if len(line.strip()) < 6)
    return short / len(lines)


def _isolated_char_line_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    hits = sum(
        1 for line in lines
        if len(re.findall(r"[\u4e00-\u9fffA-Za-z]", line.strip())) == 1
    )
    return hits / len(lines)


def evaluate_ocr_batch(
    native_page_texts: dict[int, str],
    target_pages: list[int],
    ocr_map: dict[int, str],
    engine: str,
    lang: str,
    dpi: int,
    elapsed_seconds: float,
) -> OCRBatchEvaluation:
    page_results: list[OCRPageEvaluation] = []
    accepted_pages: list[int] = []
    rejected_pages: list[int] = []
    passed = 0
    marginal = 0

    for page_index in target_pages:
        page_eval = evaluate_single_ocr_page(
            page_index=page_index,
            native_text=native_page_texts.get(page_index, ""),
            ocr_text=ocr_map.get(page_index, ""),
        )
        page_results.append(page_eval)
        if page_eval.是否注入解析:
            accepted_pages.append(page_index)
            if page_eval.评估等级 == "通过":
                passed += 1
            else:
                marginal += 1
        else:
            rejected_pages.append(page_index)

    hit_count = sum(1 for page_index in target_pages if normalize_ocr_text(ocr_map.get(page_index, "")))
    batch = OCRBatchEvaluation(
        是否执行OCR=bool(target_pages),
        OCR引擎=engine,
        OCR语言=lang,
        OCR_DPI=dpi,
        目标页数=len(target_pages),
        识别成功页数=hit_count,
        评估通过页数=passed,
        边缘页数=marginal,
        拒绝页数=len(rejected_pages),
        注入页码列表=accepted_pages,
        拒绝页码列表=rejected_pages,
        OCR总耗时秒=round(elapsed_seconds, 3),
        页级详情=page_results,
        评估结论=_batch_conclusion(target_pages, accepted_pages, rejected_pages),
        失败原因="" if accepted_pages else "OCR 未产出可注入 parser 的页",
    )
    return batch


def evaluate_single_ocr_page(page_index: int, native_text: str, ocr_text: str) -> OCRPageEvaluation:
    normalized_text = normalize_ocr_text(ocr_text)
    lines = [line for line in normalized_text.splitlines() if line.strip()]
    raw_length = len((native_text or "").strip())
    text_length = len(normalized_text)
    content_chars = len(CONTENT_CHAR_RE.findall(normalized_text))
    punctuation_chars = len(PUNCT_CHAR_RE.findall(normalized_text))
    punctuation_ratio = round(punctuation_chars / max(1, len(normalized_text.replace("\n", ""))), 3)
    single_char_ratio = round(sum(1 for line in lines if len(line.strip()) <= 1) / max(1, len(lines)), 3)
    duplicate_ratio = round(_duplicate_ratio(lines), 3)
    section_signals = sum(1 for line in lines if SECTION_SIGNAL_RE.search(line))
    standard_signals = len(STANDARD_SIGNAL_RE.findall(normalized_text))
    table_signals = len(TABLE_SIGNAL_RE.findall(normalized_text))
    isolated_punct_ratio = round(_isolated_punct_ratio(normalized_text), 3)
    short_line_ratio = round(_short_line_ratio(lines), 3)
    isolated_char_ratio = round(_isolated_char_line_ratio(lines), 3)
    fragmentation_hit = (
        isolated_punct_ratio > 0.15
        or short_line_ratio > 0.5
        or isolated_char_ratio > 0.3
    )

    reasons: list[str] = []
    grade = "拒绝"
    inject = False

    if text_length == 0 or content_chars < 12 or not lines:
        reasons.append("文本为空或有效字符过少")
    else:
        if punctuation_ratio > 0.45:
            reasons.append("标点噪音率偏高")
        if single_char_ratio > 0.45:
            reasons.append("单字符碎片率偏高")
        if duplicate_ratio > 0.35:
            reasons.append("重复行比例偏高")

        strong_signal = section_signals > 0 or standard_signals > 0 or table_signals > 0
        quality_ok = punctuation_ratio <= 0.4 and single_char_ratio <= 0.4 and duplicate_ratio <= 0.35
        if content_chars >= 80 and len(lines) >= 4 and quality_ok:
            grade = "通过"
            inject = True
            reasons.append("文本量充足且噪音可控")
        elif content_chars >= 36 and strong_signal and single_char_ratio <= 0.6:
            grade = "边缘"
            inject = True
            reasons.append("文本量一般但含结构信号")
        elif content_chars >= 28 and quality_ok and len(lines) >= 3:
            grade = "边缘"
            inject = True
            reasons.append("文本可读但质量一般")
        else:
            reasons.append("文本质量不足以注入 parser")

    if fragmentation_hit:
        frag_reasons = []
        if isolated_punct_ratio > 0.15:
            frag_reasons.append(f"孤立标点率={isolated_punct_ratio}")
        if short_line_ratio > 0.5:
            frag_reasons.append(f"短行占比={short_line_ratio}")
        if isolated_char_ratio > 0.3:
            frag_reasons.append(f"孤立单字行率={isolated_char_ratio}")
        reasons.append("碎片化特征命中：" + "；".join(frag_reasons))
        if grade == "通过":
            grade = "边缘"
            reasons.append("碎片化触发评级降档：通过→边缘")
        elif grade == "边缘":
            grade = "拒绝"
            inject = False
            reasons.append("碎片化触发评级降档：边缘→拒绝")

    return OCRPageEvaluation(
        页码索引=page_index,
        原生文本字符数=raw_length,
        OCR文本字符数=text_length,
        OCR文本行数=len(lines),
        有效字符数=content_chars,
        章节信号数=section_signals,
        标准号信号数=standard_signals,
        表格图表信号数=table_signals,
        标点噪音率=punctuation_ratio,
        单字符碎片率=single_char_ratio,
        重复行率=duplicate_ratio,
        评估等级=grade,
        是否注入解析=inject,
        判定原因=_dedupe_keep_order(reasons),
    )


def build_force_ocr_payload(ocr_map: dict[int, str], batch_eval: OCRBatchEvaluation) -> dict[int, str]:
    accepted = set(batch_eval.注入页码列表)
    return {
        page_index: normalize_ocr_text(text)
        for page_index, text in ocr_map.items()
        if page_index in accepted and normalize_ocr_text(text)
    }


def build_page_eval_map(batch_eval: OCRBatchEvaluation) -> dict[int, dict[str, object]]:
    page_map: dict[int, dict[str, object]] = {}
    for item in batch_eval.页级详情:
        page_map[item.页码索引] = item.to_dict()
    return page_map


def normalize_ocr_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line and line.strip()]
    return "\n".join(lines)


def _duplicate_ratio(lines: list[str]) -> float:
    if not lines:
        return 0.0
    counts = Counter(lines)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return duplicates / max(1, len(lines))


def _batch_conclusion(target_pages: list[int], accepted_pages: list[int], rejected_pages: list[int]) -> str:
    if not target_pages or not accepted_pages:
        return "失败"
    if len(accepted_pages) == len(target_pages):
        return "成功"
    if rejected_pages:
        return "部分成功"
    return "成功"


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


__all__ = [
    "build_force_ocr_payload",
    "build_page_eval_map",
    "evaluate_ocr_batch",
    "evaluate_single_ocr_page",
]
