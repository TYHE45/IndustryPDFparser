"""定向修正模块 —— 根据评审结果分级修正，不整体重新解析。"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from config import AppConfig
from src.llm_refiner import refine_document_structure
from src.md_builder import build_markdown
from src.models import DocumentData
from src.normalizer import normalize_document
from src.ocr_eval import build_force_ocr_payload, build_page_eval_map, evaluate_ocr_batch
from src.parser import PDFParser
from src.profiler import needs_ocr_by_text_layer
from src.summarizer import build_summary
from src.tagger import build_tags

# 问题级别常量（与 reviewer.py 一致）
KEY_LEVEL = "级别"
KEY_POSITION = "位置"
KEY_ACTION = "修正动作"
KEY_ROOT_MODULE = "根因模块"
KEY_BLOCKING = "是否阻断"

# reviewer.py 中的问题标识
DOC_CHAIN_MISSING = "正文主链缺失"
MARKDOWN_TOO_SHORT = "markdown内容过少"
TABLE_VIEW_MISSING = "表格视图缺失"
AUTO_TABLE_TITLE_LEFT = "自动表标题残留"
CHAPTER_SUMMARY_EMPTY = "章节摘要为空"
TABLE_NOT_TO_PARAM = "表格未转化为参数"
PARAM_SUMMARY_EMPTY = "参数摘要为空"
SCAN_LIKE = "疑似扫描件"
STANDARD_TAG_EMPTY = "标准引用标签为空"
PARAM_TAG_EMPTY = "参数标签为空"
PRODUCT_MODEL_TAG_EMPTY = "产品型号标签为空"
NOISY_PARAMETER_TAGS = "参数标签存在噪音"
SENTENCE_TAG_POLLUTION = "标签存在句子污染"
STRUCTURE_MISSING = "结构未建立"
TABLE_NOT_CONSUMED = "表格未消费"
STANDARD_ENTITY_MISSING = "标准实体缺失"
STRUCTURED_BACKBONE_MISSING = "结构主线缺失"
MISSING_CRITICAL_TAGS = "关键标签缺失"
OCR_COVERAGE_WEAK = "OCR覆盖不足"
OCR_HEADING_NOISE = "OCR标题噪音明显"
OCR_PARAMETER_POLLUTION = "OCR参数污染明显"
SUMMARY_TEMPLATE_FALLBACK = "摘要疑似模板回退"

# 修正动作标识
ACTION_RERUN_PARSER = "重跑parser"
ACTION_REBUILD_MARKDOWN = "重建markdown"
ACTION_REBUILD_SUMMARY = "重建summary"
ACTION_REBUILD_TAGS = "重建tags"
ACTION_CLEAN_TAGS = "清洗标签噪音"
ACTION_OCR_BLOCK = "标记需OCR"
ACTION_NONE = "无可用自动修正"


def classify_fix_actions(review: dict[str, Any]) -> list[dict[str, Any]]:
    """根据评审结果中的问题清单，分类出需要执行的修正动作列表。"""

    problems = review.get("问题清单", [])
    if not problems:
        return []

    actions: list[dict[str, Any]] = []
    seen_actions: set[tuple[str, str]] = set()
    level_priority = {"S": 0, "A": 1, "B": 2}
    action_priority = {
        ACTION_OCR_BLOCK: 0,
        ACTION_RERUN_PARSER: 1,
        ACTION_REBUILD_MARKDOWN: 2,
        ACTION_REBUILD_SUMMARY: 3,
        ACTION_REBUILD_TAGS: 4,
        ACTION_CLEAN_TAGS: 5,
    }

    for problem in problems:
        level = str(problem.get(KEY_LEVEL, "B"))
        position = str(problem.get(KEY_POSITION, ""))
        action = str(problem.get(KEY_ACTION) or _map_problem_to_action(position))
        if action == ACTION_NONE:
            continue

        module = str(problem.get(KEY_ROOT_MODULE) or _infer_module_from_action(action))
        blocking = bool(problem.get(KEY_BLOCKING, False) or action == ACTION_OCR_BLOCK)
        action_key = (action, module)
        if action_key in seen_actions:
            continue

        seen_actions.add(action_key)
        actions.append(
            {
                "动作": action,
                "模块": module,
                "原因": position,
                "级别": level,
                "是否阻断": blocking,
            }
        )

    actions.sort(
        key=lambda item: (
            level_priority.get(str(item["级别"]), 9),
            action_priority.get(str(item["动作"]), 99),
        )
    )
    return actions


def apply_fixes(
    document: DocumentData,
    config: AppConfig,
    actions: list[dict[str, Any]],
    current_markdown: str,
    current_summary: dict[str, Any],
    current_tags: dict[str, Any],
) -> tuple[DocumentData, str, dict[str, Any], dict[str, Any], list[str | dict[str, Any]], str | None, dict[str, Any]]:
    """执行修正动作，返回 (document, markdown, summary, tags, 执行日志, 停止原因, 修正元数据)。"""

    new_document = document
    markdown = current_markdown
    summary = current_summary
    tags = current_tags
    fix_log: list[str | dict[str, Any]] = []
    fix_meta: dict[str, Any] = {}

    action_names = {str(item["动作"]) for item in actions}
    active_config = config

    if ACTION_OCR_BLOCK in action_names:
        if not getattr(config, "ocr_enabled", True):
            fix_log.append("检测到疑似扫描件但配置禁用 OCR（ocr_enabled=False），停止自动修正。")
            return new_document, markdown, summary, tags, fix_log, "OCR 已在配置中禁用", fix_meta

        from src.ocr import run_ocr_on_pages
        from src.ocr import get_engine_version

        # 选出需要 OCR 的页：除了低文本量外，也覆盖广告/水印页和结构信号极弱的伪文本层页面。
        threshold = int(getattr(config, "min_chars_per_page_before_ocr_warning", 60) or 60)
        target_pages: list[int] = []
        native_page_texts: dict[int, str] = {}
        target_page_reasons: dict[int, list[str]] = {}
        for page in document.页面列表:
            if getattr(page, "OCR是否注入解析", False):
                continue
            text = (page.原始文本 or "").strip()
            native_page_texts[page.页码索引] = text
            page_lines = [line for line in text.splitlines() if line.strip()]
            page_needs_ocr, page_reason_codes, _ = needs_ocr_by_text_layer(
                page_lines,
                page_count=1,
                min_chars=threshold,
            )
            if page_needs_ocr:
                target_pages.append(page.页码索引)
                target_page_reasons[page.页码索引] = page_reason_codes
        if not target_pages:
            if not document.页面列表:
                # 兜底：页面列表为空（profile 异常），按 PDF 实际页数跑全量 OCR
                try:
                    import fitz

                    with fitz.open(config.input_path) as doc:
                        target_pages = list(range(len(doc)))
                except Exception as exc:
                    fix_log.append(f"无法枚举 PDF 页用于 OCR：{exc}")
                    return new_document, markdown, summary, tags, fix_log, "OCR 失败：无法打开 PDF", fix_meta
            else:
                fix_log.append("没有需要 OCR 的页（页面列表非空，且所有页文本量或已注入均满足阈值）。")
                return new_document, markdown, summary, tags, fix_log, "没有需要 OCR 的页", fix_meta

        if target_page_reasons:
            fix_log.append(
                {
                    "类型": "OCR选页",
                    "页级原因": {
                        str(page_index + 1): reasons
                        for page_index, reasons in list(target_page_reasons.items())[:12]
                    },
                }
            )
        fix_log.append(f"对 {len(target_pages)} 页执行 OCR（PaddleOCR，lang={config.ocr_lang}）。")
        started_at = time.perf_counter()
        ocr_map = run_ocr_on_pages(
            config.input_path,
            target_pages,
            lang=config.ocr_lang,
            dpi=config.ocr_dpi,
        )
        batch_eval = evaluate_ocr_batch(
            native_page_texts=native_page_texts,
            target_pages=target_pages,
            ocr_map=ocr_map,
            engine=get_engine_version(),
            lang=config.ocr_lang,
            dpi=config.ocr_dpi,
            elapsed_seconds=time.perf_counter() - started_at,
        )
        page_eval_map = build_page_eval_map(batch_eval)
        for page_meta in page_eval_map.values():
            page_meta["OCR来源"] = batch_eval.OCR引擎
        accepted_ocr_pages = build_force_ocr_payload(ocr_map, batch_eval)
        fix_meta["OCR评估"] = batch_eval.to_dict()
        fix_log.append({"类型": "OCR页级评估", **batch_eval.to_dict()})

        if not ocr_map:
            fix_log.append("OCR 未识别到任何文本（可能是 PaddleOCR 未安装或识别失败）。")
            return new_document, markdown, summary, tags, fix_log, "OCR 未产出可用文本", fix_meta

        fix_log.append(
            f"OCR 识别成功页数：{batch_eval.识别成功页数} / {batch_eval.目标页数}。"
        )
        fix_log.append(
            f"OCR 建议注入页数：{len(accepted_ocr_pages)} / {batch_eval.目标页数}。"
        )
        if not accepted_ocr_pages:
            fix_log.append("OCR 已执行，但页级评估未发现可安全注入 parser 的结果。")
            return new_document, markdown, summary, tags, fix_log, "OCR 未产出可注入文本", fix_meta

        existing_force_ocr_pages = dict(getattr(config, "force_ocr_pages", {}) or {})
        existing_force_ocr_pages.update(accepted_ocr_pages)
        existing_page_evals = dict(getattr(config, "ocr_page_evaluations", {}) or {})
        existing_page_evals.update(page_eval_map)
        active_config = replace(
            config,
            force_ocr_pages=existing_force_ocr_pages,
            ocr_page_evaluations=existing_page_evals,
        )
        fix_meta["_active_config"] = active_config

    if ACTION_RERUN_PARSER in action_names or ACTION_OCR_BLOCK in action_names:
        parser = PDFParser(active_config)
        rebuilt_document = normalize_document(parser.parse())
        rebuilt_document, _ = refine_document_structure(rebuilt_document, active_config)
        new_document = rebuilt_document
        if ACTION_OCR_BLOCK in action_names:
            fix_log.append("基于 OCR 结果重跑了解析主链（parser -> normalizer -> llm_refiner）。")
        else:
            fix_log.append("重跑了解析主链（parser -> normalizer -> llm_refiner）。")

        markdown = build_markdown(new_document)
        summary = build_summary(new_document, active_config)
        tags = build_tags(new_document, active_config)
        fix_log.append("基于新的结构状态重建了 markdown、summary、tags。")

        if ACTION_CLEAN_TAGS in action_names:
            tags = _clean_noisy_tags(tags)
            fix_log.append("在重建 tags 后额外清洗了标签噪音。")

        fix_meta["_active_config"] = active_config
        return new_document, markdown, summary, tags, fix_log, None, fix_meta

    if ACTION_REBUILD_MARKDOWN in action_names:
        markdown = build_markdown(new_document)
        fix_log.append("重建了 markdown（md_builder）。")

    if ACTION_REBUILD_SUMMARY in action_names:
        summary = build_summary(new_document, config)
        fix_log.append("重建了 summary（summarizer）。")

    if ACTION_REBUILD_TAGS in action_names:
        tags = build_tags(new_document, config)
        fix_log.append("重建了 tags（tagger）。")

    if ACTION_CLEAN_TAGS in action_names and ACTION_REBUILD_TAGS not in action_names:
        tags = _clean_noisy_tags(tags)
        fix_log.append("清洗了标签噪音。")

    if not fix_log:
        fix_log.append("无可执行的自动修正。")

    fix_meta["_active_config"] = active_config
    return new_document, markdown, summary, tags, fix_log, None, fix_meta


def _map_problem_to_action(position: str) -> str:
    """兼容旧问题清单：将问题标识映射到修正动作。"""

    if position in {
        DOC_CHAIN_MISSING,
        STRUCTURE_MISSING,
        STRUCTURED_BACKBONE_MISSING,
        TABLE_NOT_TO_PARAM,
        TABLE_NOT_CONSUMED,
        STANDARD_ENTITY_MISSING,
    }:
        return ACTION_RERUN_PARSER

    if position == SCAN_LIKE:
        return ACTION_OCR_BLOCK

    if position == OCR_COVERAGE_WEAK:
        return ACTION_OCR_BLOCK

    if position in {MARKDOWN_TOO_SHORT, TABLE_VIEW_MISSING, AUTO_TABLE_TITLE_LEFT}:
        return ACTION_REBUILD_MARKDOWN

    if position == OCR_HEADING_NOISE:
        return ACTION_RERUN_PARSER

    if position in {CHAPTER_SUMMARY_EMPTY, PARAM_SUMMARY_EMPTY, SUMMARY_TEMPLATE_FALLBACK}:
        return ACTION_REBUILD_SUMMARY

    if position in {STANDARD_TAG_EMPTY, PARAM_TAG_EMPTY, PRODUCT_MODEL_TAG_EMPTY, MISSING_CRITICAL_TAGS, SENTENCE_TAG_POLLUTION}:
        return ACTION_REBUILD_TAGS

    if position in {NOISY_PARAMETER_TAGS, OCR_PARAMETER_POLLUTION}:
        return ACTION_CLEAN_TAGS

    return ACTION_NONE


def _infer_module_from_action(action: str) -> str:
    return {
        ACTION_RERUN_PARSER: "parser",
        ACTION_OCR_BLOCK: "ocr",
        ACTION_REBUILD_MARKDOWN: "md_builder",
        ACTION_REBUILD_SUMMARY: "summarizer",
        ACTION_REBUILD_TAGS: "tagger",
        ACTION_CLEAN_TAGS: "fixer",
    }.get(action, "")


def _clean_noisy_tags(tags: dict[str, Any]) -> dict[str, Any]:
    """局部清洗：移除参数标签中的噪音项。"""

    import re

    noise_pattern = re.compile(r"(?:\d+[.)/]?\s*){2,}|(?:\b[a-z]{1,3}\b\s*){2,}", re.IGNORECASE)
    param_tags = tags.get("参数标签", [])
    if not isinstance(param_tags, list):
        return tags

    cleaned = [tag for tag in param_tags if not noise_pattern.search(str(tag))]
    updated = dict(tags)
    updated["参数标签"] = cleaned
    return updated
