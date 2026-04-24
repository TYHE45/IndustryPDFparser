from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from config import AppConfig
from src.fixer import apply_fixes, classify_fix_actions
from src.llm_refiner import refine_document_structure
from src.md_builder import build_markdown
from src.normalizer import normalize_document
from src.parser import PDFParser
from src.reviewer import review_outputs
from src.source_guard import detect_metadata_mismatch_reason
from src.summarizer import build_summary
from src.tagger import build_tags
from src.text_localization import get_safety_net_trigger_count, reset_safety_net_trigger_count

ROUND_NO = "轮次"
STAGE = "阶段"
FINAL_STAGE = "最终生成与验收"
SECTION_COUNT = "章节数量"
TABLE_COUNT = "表格数量"
NUMERIC_PARAM_COUNT = "数值型参数数量"
RULE_COUNT = "规则数量"
LLM_REFINE_STAGE = "LLM结构复核"
REVIEW_STAGE = "评审"

MAX_REVIEW_ROUNDS = 3


def run_iterative_pipeline(config: AppConfig) -> dict[str, object]:
    reset_safety_net_trigger_count()
    parser = PDFParser(config)
    document = normalize_document(parser.parse())
    document, refinement_rounds = refine_document_structure(document, config)

    output_config = config
    llm_round_count = sum(1 for item in refinement_rounds if item.get(STAGE) == LLM_REFINE_STAGE)
    llm_refine_failed = any(
        item.get(STAGE) == LLM_REFINE_STAGE and item.get("是否成功") is False
        for item in refinement_rounds
    )
    if llm_refine_failed:
        output_config = replace(config, use_llm=False)

    markdown = build_markdown(document)
    source_quarantine_reason = detect_metadata_mismatch_reason(document, markdown)
    if source_quarantine_reason:
        output_config = replace(output_config, use_llm=False)
    summary = build_summary(document, output_config)
    tags = build_tags(document, output_config)
    summary, tags, source_quarantine_reason = _apply_source_quarantine(
        document,
        markdown,
        summary,
        tags,
        source_quarantine_reason,
    )

    review_rounds: list[dict[str, Any]] = []
    review: dict[str, Any] | None = None

    for round_no in range(1, MAX_REVIEW_ROUNDS + 1):
        before_snapshot = _build_state_snapshot(document, markdown, summary, tags)
        before_fingerprint = _fingerprint_state(before_snapshot)

        review = review_outputs(document, markdown, summary, tags)
        review["轮次"] = float(round_no)
        problems = review.get("问题清单", [])
        actions = classify_fix_actions(review)

        round_record: dict[str, Any] = {
            ROUND_NO: float(round_no),
            STAGE: REVIEW_STAGE,
            "总分": review.get("总分", 0.0),
            "是否通过": review.get("是否通过", False),
            "红线触发": review.get("红线触发", False),
            "红线列表": review.get("红线列表", []),
            "问题数量": len(problems),
            "问题统计": review.get("问题统计", {}),
            "分项评分": review.get("分项评分", {}),
            "问题列表": problems,
            "修正动作": actions,
            "修正前状态摘要": before_snapshot,
            "修正前状态指纹": before_fingerprint,
        }

        if review.get("是否通过", False):
            round_record["修正后状态摘要"] = before_snapshot
            round_record["修正后状态指纹"] = before_fingerprint
            round_record["状态是否变化"] = False
            round_record["结论"] = "通过，进入导出"
            round_record["停止原因"] = "评审通过"
            review_rounds.append(round_record)
            break

        if round_no == MAX_REVIEW_ROUNDS:
            round_record["修正后状态摘要"] = before_snapshot
            round_record["修正后状态指纹"] = before_fingerprint
            round_record["状态是否变化"] = False
            round_record["结论"] = "已达最大轮次，强制导出"
            round_record["停止原因"] = "达到最大评审轮次"
            round_record["未通过原因"] = collect_failure_reasons(review)
            review_rounds.append(round_record)
            break

        if not actions:
            round_record["修正日志"] = ["无可用自动修正动作。"]
            round_record["修正后状态摘要"] = before_snapshot
            round_record["修正后状态指纹"] = before_fingerprint
            round_record["状态是否变化"] = False
            round_record["结论"] = "无可用自动修正，提前停止"
            round_record["停止原因"] = "无可用自动修正动作"
            round_record["未通过原因"] = collect_failure_reasons(review)
            review_rounds.append(round_record)
            break

        (
            document,
            markdown,
            summary,
            tags,
            fix_log,
            stop_reason,
            fix_meta,
        ) = apply_fixes(document, output_config, actions, markdown, summary, tags)

        summary, tags, source_quarantine_reason = _apply_source_quarantine(
            document,
            markdown,
            summary,
            tags,
        )

        after_snapshot = _build_state_snapshot(document, markdown, summary, tags)
        after_fingerprint = _fingerprint_state(after_snapshot)
        state_changed = before_fingerprint != after_fingerprint

        round_record["修正日志"] = fix_log
        next_config = fix_meta.get("_active_config") if isinstance(fix_meta, dict) else None
        if isinstance(next_config, AppConfig):
            output_config = next_config
        if isinstance(fix_meta, dict) and fix_meta.get("OCR评估"):
            ocr_meta = dict(fix_meta["OCR评估"])
            round_record["OCR评估摘要"] = {
                "是否执行OCR": bool(ocr_meta.get("是否执行OCR", False)),
                "OCR引擎": str(ocr_meta.get("OCR引擎", "")),
                "OCR语言": str(ocr_meta.get("OCR语言", "")),
                "OCR分辨率DPI": int(ocr_meta.get("OCR_DPI", 0) or 0),
                "目标页数": int(ocr_meta.get("目标页数", 0) or 0),
                "识别成功页数": int(ocr_meta.get("识别成功页数", 0) or 0),
                "评估通过页数": int(ocr_meta.get("评估通过页数", 0) or 0),
                "边缘页数": int(ocr_meta.get("边缘页数", 0) or 0),
                "拒绝页数": int(ocr_meta.get("拒绝页数", 0) or 0),
                "注入页码列表": list(ocr_meta.get("注入页码列表", [])),
                "拒绝页码列表": list(ocr_meta.get("拒绝页码列表", [])),
                "OCR总耗时秒": float(ocr_meta.get("OCR总耗时秒", 0.0) or 0.0),
                "评估结论": str(ocr_meta.get("评估结论", "")),
                "失败原因": str(ocr_meta.get("失败原因", "")),
            }
        if isinstance(fix_meta, dict) and fix_meta.get("OCR执行计划"):
            round_record["OCR执行计划"] = dict(fix_meta["OCR执行计划"])
        if isinstance(fix_meta, dict) and fix_meta.get("OCR执行结果"):
            round_record["OCR执行结果"] = dict(fix_meta["OCR执行结果"])
        if isinstance(fix_meta, dict) and fix_meta.get("OCR表格识别结果"):
            round_record["OCR表格识别结果"] = dict(fix_meta["OCR表格识别结果"])
        if isinstance(fix_meta, dict) and fix_meta.get("OCR评估"):
            # §2.5 为每页详情补一个 "判定原因列表" 别名字段，避免下游把 "判定原因"（实际是 list）
            # 误当作单个字符串；保留原字段以兼容既有消费方。
            page_details_raw = list(ocr_meta.get("页级详情", []))
            normalized_page_details: list[dict[str, Any]] = []
            for entry in page_details_raw:
                if isinstance(entry, dict):
                    normalized_entry = dict(entry)
                    reasons = normalized_entry.get("判定原因", [])
                    if isinstance(reasons, (list, tuple)):
                        normalized_entry["判定原因列表"] = list(reasons)
                    else:
                        normalized_entry["判定原因列表"] = [str(reasons)] if reasons else []
                    normalized_page_details.append(normalized_entry)
                else:
                    normalized_page_details.append(entry)
            round_record["OCR页级详情"] = normalized_page_details
        if source_quarantine_reason:
            round_record["来源隔离原因"] = source_quarantine_reason
        round_record["修正后状态摘要"] = after_snapshot
        round_record["修正后状态指纹"] = after_fingerprint
        round_record["状态是否变化"] = state_changed

        if stop_reason:
            round_record["结论"] = stop_reason
            round_record["停止原因"] = stop_reason
            round_record["未通过原因"] = collect_failure_reasons(review)
            review_rounds.append(round_record)
            break

        if not state_changed:
            round_record["结论"] = "修正后状态无变化，提前停止"
            round_record["停止原因"] = "状态指纹未变化"
            round_record["未通过原因"] = collect_failure_reasons(review)
            review_rounds.append(round_record)
            break

        round_record["结论"] = f"执行了 {len(fix_log)} 项修正，进入下一轮评审"
        round_record["停止原因"] = ""
        review_rounds.append(round_record)

    all_rounds: list[dict[str, Any]] = list(refinement_rounds)
    all_rounds.extend(review_rounds)
    all_rounds.append(
        {
            ROUND_NO: float(len(all_rounds) + 1),
            STAGE: FINAL_STAGE,
            SECTION_COUNT: float(len(document.章节列表)),
            TABLE_COUNT: float(len(document.表格列表)),
            NUMERIC_PARAM_COUNT: float(len(document.数值参数列表)),
            RULE_COUNT: float(len(document.规则列表)),
        }
    )

    profile = getattr(document, "文档画像", None)
    ocr_process_summary = _build_ocr_process_summary(review_rounds)
    process_log = {
        "输入文件": str(config.input_path),
        "输出目录": str(config.output_dir),
        "是否调用LLM": output_config.use_llm,
        "LLM结构修正轮次": float(llm_round_count),
        "评审轮次": float(len(review_rounds)),
        "最终是否通过": review.get("是否通过", False) if review else False,
        "最终总分": review.get("总分", 0.0) if review else 0.0,
        "摘要LLM后端": summary.get("_llm_backend", ""),
        "摘要LLM原因": summary.get("_llm_reason", ""),
        "摘要LLM错误": summary.get("_llm_error", ""),
        "标签LLM后端": tags.get("_llm_backend", ""),
        "标签LLM原因": tags.get("_llm_reason", ""),
        "标签LLM错误": tags.get("_llm_error", ""),
        "安全网触发次数": get_safety_net_trigger_count(),
        "文档类型": getattr(profile, "文档类型", "unknown"),
        "画像置信度": getattr(profile, "置信度", 0.0),
        "来源是否隔离": bool(source_quarantine_reason),
        "来源隔离原因": source_quarantine_reason or "",
        SECTION_COUNT: len(document.章节列表),
        TABLE_COUNT: len(document.表格列表),
        NUMERIC_PARAM_COUNT: len(document.数值参数列表),
        RULE_COUNT: len(document.规则列表),
        "检验记录数量": len(document.检验列表),
        "引用标准数量": len(document.引用标准列表),
        "迭代轮次": float(len(all_rounds)),
        **ocr_process_summary,
    }

    return {
        "document": document,
        "markdown": markdown,
        "summary": summary,
        "tags": tags,
        "review": review,
        "rounds": all_rounds,
        "review_rounds": review_rounds,
        "process_log": process_log,
    }


def _apply_source_quarantine(
    document: Any,
    markdown: str,
    summary: dict[str, Any],
    tags: dict[str, Any],
    reason: str = "",
) -> tuple[dict[str, Any], dict[str, Any], str]:
    mismatch_reason = reason or detect_metadata_mismatch_reason(document, markdown)
    if not mismatch_reason:
        return summary, tags, ""
    return (
        _build_source_quarantine_summary(document, mismatch_reason),
        _build_source_quarantine_tags(document, mismatch_reason),
        mismatch_reason,
    )


def _build_source_quarantine_summary(document: Any, reason: str) -> dict[str, Any]:
    title = (
        str(getattr(document.文件元数据, "文档标题", "") or "").strip()
        or str(getattr(document.文件元数据, "文件名称", "") or "").strip()
        or "当前文档"
    )
    profile = getattr(document, "文档画像", None)
    return {
        "全文摘要": f"《{title}》已触发来源隔离：{reason}",
        "章节摘要": [],
        "参数摘要": {"数值型参数": [], "规则型参数": []},
        "要求摘要": [],
        "引用标准摘要": [],
        "文档画像": profile.to_dict() if profile else {},
        "_llm_reason": "文件名与正文标准号不一致，已隔离常规摘要流程",
        "_source_quarantined": True,
        "_source_guard_reason": reason,
    }


def _build_source_quarantine_tags(document: Any, reason: str) -> dict[str, Any]:
    profile = getattr(document, "文档画像", None)
    doc_type_label = str(getattr(document.文件元数据, "文档类型", "") or "").strip()
    if not doc_type_label and profile:
        doc_type_label = str(getattr(profile, "文档类型", "") or "").strip()
    doc_type_tags = [item for item in [doc_type_label, "来源隔离"] if item]
    if profile and getattr(profile, "是否需要OCR", False) and "疑似扫描件" not in doc_type_tags:
        doc_type_tags.append("疑似扫描件")
    return {
        "文档类型标签": doc_type_tags,
        "文档主题标签": [],
        "工艺流程标签": [],
        "参数标签": [],
        "检验标签": [],
        "标准引用标签": [],
        "产品系列标签": [],
        "产品型号标签": [],
        "应用标签": [],
        "认证标签": [],
        "缺陷标签": [],
        "焊缝类型标签": [],
        "区域标签": [],
        "_llm_reason": "文件名与正文标准号不一致，已隔离常规标签流程",
        "_source_quarantined": True,
        "_source_guard_reason": reason,
    }


def _build_state_snapshot(
    document: Any,
    markdown: str,
    summary: dict[str, Any],
    tags: dict[str, Any],
) -> dict[str, Any]:
    ocr_attempted_pages = [page for page in getattr(document, "页面列表", []) if getattr(page, "是否执行OCR", False)]
    ocr_injected_pages = [page for page in ocr_attempted_pages if getattr(page, "OCR是否注入解析", False)]
    return {
        "章节数量": len(document.章节列表),
        "表格数量": len(document.表格列表),
        "数值型参数数量": len(document.数值参数列表),
        "规则数量": len(document.规则列表),
        "检验记录数量": len(document.检验列表),
        "引用标准数量": len(document.引用标准列表),
        "章节示例": [f"{item.章节编号} {item.章节标题}".strip() for item in document.章节列表[:5]],
        "参数示例": [item.参数名称 for item in document.数值参数列表[:5]],
        "标准示例": [item.标准编号 for item in document.引用标准列表[:5]],
        "原文解析长度": len(markdown),
        "全文摘要长度": len(str(summary.get("全文摘要", ""))),
        "OCR尝试页数": len(ocr_attempted_pages),
        "OCR注入页数": len(ocr_injected_pages),
        "OCR注入页索引": [int(page.页码索引) for page in ocr_injected_pages[:20]],
        "OCR有效字符数": sum(int(getattr(page, "OCR有效字符数", 0) or 0) for page in ocr_injected_pages),
        "标签数量统计": {
            key: len(value)
            for key, value in tags.items()
            if not str(key).startswith("_") and isinstance(value, list)
        },
    }


def _fingerprint_state(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def collect_failure_reasons(review: dict[str, Any]) -> list[str]:
    redlines = [
        item.get("红线名称", "")
        for item in review.get("红线列表", [])
        if item.get("红线名称")
    ]
    if redlines:
        return redlines

    severe_positions = [
        item.get("位置", item.get("内容", ""))
        for item in review.get("问题清单", [])
        if item.get("级别") == "S"
    ]
    return severe_positions or ["总分未达通过线"]


def _build_ocr_process_summary(review_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    ocr_rounds = [item for item in review_rounds if item.get("OCR评估摘要")]
    if not ocr_rounds:
        return {
            "是否触发OCR": False,
            "OCR调用次数": 0,
            "OCR引擎": "",
            "OCR语言": "",
            "OCR分辨率DPI": 0,
            "OCR目标页数累计": 0,
            "OCR识别成功页数累计": 0,
            "OCR评估通过页数累计": 0,
            "OCR边缘页数累计": 0,
            "OCR拒绝页数累计": 0,
            "OCR实际注入页数累计": 0,
            "OCR总耗时秒": 0.0,
            "OCR失败原因列表": [],
        }

    latest = ocr_rounds[-1]["OCR评估摘要"]
    failure_reasons = [
        str(item["OCR评估摘要"].get("失败原因", ""))
        for item in ocr_rounds
        if str(item["OCR评估摘要"].get("失败原因", "")).strip()
    ]
    return {
        "是否触发OCR": True,
        "OCR调用次数": len(ocr_rounds),
        "OCR引擎": str(latest.get("OCR引擎", "")),
        "OCR语言": str(latest.get("OCR语言", "")),
        "OCR分辨率DPI": int(latest.get("OCR分辨率DPI", 0) or 0),
        "OCR目标页数累计": sum(int(item["OCR评估摘要"].get("目标页数", 0) or 0) for item in ocr_rounds),
        "OCR识别成功页数累计": sum(int(item["OCR评估摘要"].get("识别成功页数", 0) or 0) for item in ocr_rounds),
        "OCR评估通过页数累计": sum(int(item["OCR评估摘要"].get("评估通过页数", 0) or 0) for item in ocr_rounds),
        "OCR边缘页数累计": sum(int(item["OCR评估摘要"].get("边缘页数", 0) or 0) for item in ocr_rounds),
        "OCR拒绝页数累计": sum(int(item["OCR评估摘要"].get("拒绝页数", 0) or 0) for item in ocr_rounds),
        "OCR实际注入页数累计": sum(len(item["OCR评估摘要"].get("注入页码列表", [])) for item in ocr_rounds),
        "OCR总耗时秒": round(sum(float(item["OCR评估摘要"].get("OCR总耗时秒", 0.0) or 0.0) for item in ocr_rounds), 3),
        "OCR失败原因列表": failure_reasons,
    }
