from __future__ import annotations

import re
from collections import Counter
from typing import Any

from src.models import DocumentData
from src.profiler import needs_ocr_by_text_layer
from src.record_access import metadata_title
from src.source_guard import detect_metadata_mismatch_reason
from src.structured_access import get_parameter_entries, get_product_entries, get_standard_entries
from src.utils import normalize_line

FRONT_MATTER_PARAM_RE = re.compile(
    r"(?:备案号|邮政编码|邮编|电话|传真|网址|网站|印数|定价|出版|发行|"
    r"版权|ISBN|地址|前言|free download)",
    re.IGNORECASE,
)
FRONT_MATTER_VALUE_RE = re.compile(
    r"(?:\b\d{6}\b|(?:\(?0\d{2,4}\)?[-\s]?)?\d{5,8}(?:[-\s]\d{1,4})?|"
    r"定价\s*\d+(?:\.\d+)?\s*元|印数\s*\d+\s*[-~]\s*\d+|ISBN\s*[:：]?\s*[\d-]+)",
    re.IGNORECASE,
)
TABLE_DRIVEN_TITLE_RE = re.compile(r"(?:连接尺寸|密封面|垫片|填料|选用)", re.IGNORECASE)
TABLE_DRIVEN_BODY_RE = re.compile(r"(?:表\s*\d+|对照表|\bPN\s*\d+|\bDN\s*\d+|公称压力|温度|介质|连接尺寸|密封面)", re.IGNORECASE)
STANDARD_CODE_TOKEN_RE = re.compile(
    r"\b(?P<base>[A-Z]{2,4})"
    r"(?:[/_\-\s]?(?P<sub>[A-Z]))?"
    r"[\s_]*(?P<number>\d+(?:\.\d+)*)"
    r"\s*[-—–_.一]\s*(?P<year>\d{2,4}(?:-\d{2})?)\b",
    re.IGNORECASE,
)

STANDARD_CODE_RE = re.compile(r"\b(?:DIN|EN|ISO|SN|SEW|DVS|AD|TRbF|GB|CB)(?:\s+[A-Z]+)?\s*[0-9][0-9A-Za-z./\-—–]*\b")
SYNTHETIC_TABLE_TITLE_RE = re.compile(r"^#+\s+\u7b2c\d+\u9875\u8868\d+$")
SHORT_HEADING_RE = re.compile(r"^#+\s+[A-Z]{1,3}$")
SENTENCE_HEADING_RE = re.compile(r"^#+\s+.*[.;]$")
SUSPICIOUS_PARAM_TAG_RE = re.compile(r"(?:\d+[.)/]?\s*){2,}|(?:\b[a-z]{1,3}\b\s*){2,}", re.IGNORECASE)
SUSPICIOUS_OCR_HEADING_RE = re.compile(r"^(?:#+\s+)?(?:\d+(?:\.\d+)*\s*)?[A-Z]?\d+(?:\s*[A-Z0-9./×\-]{2,})+$")
DATE_LIKE_RE = re.compile(r"\b\d{4}[-—–/]\d{1,2}(?:[-—–/]\d{1,2})?\b")
METADATA_PARAM_RE = re.compile(r"(?:分类号|发布|实施|代替|计划项目代号|标准编号|版本日期)", re.IGNORECASE)
TEMPLATE_SUMMARY_RE = re.compile(r"(?:当前识别为|文本层极弱|建议先进行 OCR 后再做稳定抽取)")
LONG_SENTENCE_TAG_RE = re.compile(r"[，、；。,:：]")

BASE_SCORE_KEY = "\u57fa\u7840\u8d28\u91cf\u5206"
FACTUAL_SCORE_KEY = "\u4e8b\u5b9e\u6b63\u786e\u6027\u5206"
CONSISTENCY_SCORE_KEY = "\u4e00\u81f4\u6027\u4e0e\u53ef\u8ffd\u6eaf\u6027\u5206"
TOTAL_SCORE_KEY = "\u6700\u7ec8\u603b\u8bc4"
REDLINE_TRIGGERED_KEY = "\u7ea2\u7ebf\u662f\u5426\u89e6\u53d1"
REDLINE_LIST_KEY = "\u7ea2\u7ebf\u5217\u8868"
FINAL_PASS_KEY = "\u6700\u7ec8\u901a\u8fc7"
PROBLEM_STATS_KEY = "\u95ee\u9898\u7edf\u8ba1"
SUBSCORES_KEY = "\u5206\u9879\u8bc4\u5206"
PROBLEMS_KEY = "\u95ee\u9898\u6e05\u5355"
MARKDOWN_REVIEW_KEY = "markdown\u68c0\u67e5"
SUMMARY_STRUCTURE_REVIEW_KEY = "summary\u7ed3\u6784\u68c0\u67e5"
SUMMARY_FACT_REVIEW_KEY = "summary\u4e8b\u5b9e\u68c0\u67e5"
TAG_REVIEW_KEY = "tags\u68c0\u67e5"
OCR_REVIEW_KEY = "OCR\u4e13\u9879\u68c0\u67e5"
CONSISTENCY_REVIEW_KEY = "\u4e00\u81f4\u6027\u68c0\u67e5"
SOURCE_REVIEW_KEY = "\u6765\u6e90\u951a\u70b9\u68c0\u67e5"
TYPE_REVIEW_KEY = "\u7c7b\u578b\u4e13\u9879\u68c0\u67e5"
DOC_TYPE_KEY = "\u6587\u6863\u7c7b\u578b"
TOTAL_KEY = "\u603b\u5206"
PASS_KEY = "\u662f\u5426\u901a\u8fc7"
MUST_FIX_KEY = "\u5fc5\u987b\u4fee\u590d\u7684\u95ee\u9898"
KEY_ISSUES = "\u5173\u952e\u95ee\u9898"
PSEUDO_HEADINGS = "\u4f2a\u6807\u9898"
TABLE_FRAGMENTS = "\u8868\u683c\u6b8b\u5f71"
TOC_RESIDUE = "\u76ee\u5f55\u6b8b\u7559"
AUTO_TABLE_TITLES = "\u81ea\u52a8\u8868\u6807\u9898"
ILLEGAL_SECTION_NAMES = "\u975e\u6cd5\u7ae0\u8282\u540d"
INTERNAL_CODES = "\u5185\u90e8\u6280\u672f\u7f16\u53f7"
EMPTY_CHAPTER_SUMMARIES = "\u7a7a\u7ae0\u8282\u6458\u8981"
TABLE_RULE_ERRORS = "\u8868\u683c\u89c4\u5219\u538b\u7f29\u9519\u8bef"
PARAM_MULTI_VALUE_ERRORS = "\u53c2\u6570\u591a\u503c\u5408\u5e76"
MISSING_MAIN_COVERAGE = "\u4e3b\u8981\u90e8\u5206\u8986\u76d6\u7f3a\u5931"
LOW_PARAMETER_COVERAGE = "\u53c2\u6570\u8986\u76d6\u504f\u4f4e"
NOISY_TAGS = "\u566a\u97f3\u6807\u7b7e"
MISCLASSIFIED_TAGS = "\u6807\u7b7e\u5206\u7c7b\u9519\u4f4d"
MISSING_CRITICAL_TAGS = "\u5173\u952e\u6807\u7b7e\u7f3a\u5931"
ABNORMAL_PARAM_SOURCES = "\u53c2\u6570\u6765\u6e90\u5f02\u5e38"
ABNORMAL_RULE_SOURCES = "\u89c4\u5219\u6765\u6e90\u5f02\u5e38"


KEY_CONTENT = "\u5185\u5bb9"
KEY_REASON = "\u539f\u56e0"
KEY_LEVEL = "\u7ea7\u522b"
KEY_TARGET = "\u5bf9\u8c61"
KEY_TYPE = "\u95ee\u9898\u7c7b\u578b"
KEY_POSITION = "\u4f4d\u7f6e"
KEY_FIX = "\u4fee\u590d\u5efa\u8bae"
KEY_REDLINE_NAME = "\u7ea2\u7ebf\u540d\u79f0"
KEY_CAP = "\u5206\u6570\u4e0a\u9650"
KEY_PROBLEM_ID = "\u95ee\u9898ID"
KEY_ROOT_MODULE = "\u6839\u56e0\u6a21\u5757"
KEY_ACTION = "\u4fee\u6b63\u52a8\u4f5c"
KEY_BLOCKING = "\u662f\u5426\u963b\u65ad"
KEY_AFFECTED_OUTPUTS = "\u5f71\u54cd\u8f93\u51fa"


DOC_CHAIN_MISSING = "\u6b63\u6587\u4e3b\u94fe\u7f3a\u5931"
MARKDOWN_TOO_SHORT = "markdown\u5185\u5bb9\u8fc7\u5c11"
TABLE_VIEW_MISSING = "\u8868\u683c\u89c6\u56fe\u7f3a\u5931"
AUTO_TABLE_TITLE_LEFT = "\u81ea\u52a8\u8868\u6807\u9898\u6b8b\u7559"
CHAPTER_SUMMARY_EMPTY = "\u7ae0\u8282\u6458\u8981\u4e3a\u7a7a"
TABLE_NOT_TO_PARAM = "\u8868\u683c\u672a\u8f6c\u5316\u4e3a\u53c2\u6570"
PARAM_SUMMARY_EMPTY = "\u53c2\u6570\u6458\u8981\u4e3a\u7a7a"
SCAN_LIKE = "\u7591\u4f3c\u626b\u63cf\u4ef6"
STANDARD_TAG_EMPTY = "\u6807\u51c6\u5f15\u7528\u6807\u7b7e\u4e3a\u7a7a"
PARAM_TAG_EMPTY = "\u53c2\u6570\u6807\u7b7e\u4e3a\u7a7a"
PRODUCT_MODEL_TAG_EMPTY = "\u4ea7\u54c1\u578b\u53f7\u6807\u7b7e\u4e3a\u7a7a"
NOISY_PARAMETER_TAGS = "\u53c2\u6570\u6807\u7b7e\u5b58\u5728\u566a\u97f3"
SENTENCE_TAG_POLLUTION = "标签存在句子污染"
STRUCTURE_MISSING = "\u7ed3\u6784\u672a\u5efa\u7acb"
TABLE_NOT_CONSUMED = "\u8868\u683c\u672a\u6d88\u8d39"
STANDARD_ENTITY_MISSING = "\u6807\u51c6\u5b9e\u4f53\u7f3a\u5931"
STRUCTURED_BACKBONE_MISSING = "\u7ed3\u6784\u4e3b\u7ebf\u7f3a\u5931"
OCR_COVERAGE_WEAK = "OCR覆盖不足"
OCR_HEADING_NOISE = "OCR标题噪音明显"
OCR_HEADING_NOISE_MINOR = "OCR标题噪音轻度"
OCR_PARAMETER_POLLUTION = "OCR参数污染明显"
SUMMARY_TEMPLATE_FALLBACK = "摘要疑似模板回退"
LLM_STUB_SUMMARY = "LLM\u81ea\u8ff0\u65e0\u5185\u5bb9"
METADATA_MISMATCH = "\u6587\u4ef6\u540d\u4e0e\u6b63\u6587\u4e0d\u4e00\u81f4"
DOC_SKELETON_MISSING = "\u6587\u6863\u9aa8\u67b6\u672a\u5efa\u7acb"
TABLE_CORE_MISSING = "核心表格缺失"


# 三维度扣分表（First Principles §10）：issue 常量 → (维度, 扣分幅度)。
# 任何维度扣分下限 0，红线另行处理。
DIM_BASE = "\u57fa\u7840\u8d28\u91cf"
DIM_FACTUAL = "\u4e8b\u5b9e\u6b63\u786e\u6027"
DIM_CONSISTENCY = "\u4e00\u81f4\u6027\u4e0e\u53ef\u8ffd\u6eaf\u6027"

ISSUE_DEDUCTIONS: dict[str, tuple[str, float]] = {
    # 基础质量（满分 35）
    DOC_CHAIN_MISSING: (DIM_BASE, 10.0),
    MARKDOWN_TOO_SHORT: (DIM_BASE, 8.0),
    TABLE_VIEW_MISSING: (DIM_BASE, 5.0),
    AUTO_TABLE_TITLE_LEFT: (DIM_BASE, 4.0),
    # 事实正确性（满分 40）
    LLM_STUB_SUMMARY: (DIM_FACTUAL, 10.0),
    PARAM_SUMMARY_EMPTY: (DIM_FACTUAL, 8.0),
    METADATA_MISMATCH: (DIM_FACTUAL, 10.0),
    TABLE_CORE_MISSING: (DIM_FACTUAL, 8.0),
    NOISY_PARAMETER_TAGS: (DIM_FACTUAL, 5.0),
    SENTENCE_TAG_POLLUTION: (DIM_FACTUAL, 5.0),
    STANDARD_TAG_EMPTY: (DIM_FACTUAL, 4.0),
    PARAM_TAG_EMPTY: (DIM_FACTUAL, 4.0),
    PRODUCT_MODEL_TAG_EMPTY: (DIM_FACTUAL, 4.0),
    CHAPTER_SUMMARY_EMPTY: (DIM_FACTUAL, 6.0),
    SUMMARY_TEMPLATE_FALLBACK: (DIM_FACTUAL, 6.0),
    # 一致性与可追溯性（满分 25）
    STRUCTURE_MISSING: (DIM_CONSISTENCY, 5.0),
    TABLE_NOT_CONSUMED: (DIM_CONSISTENCY, 8.0),
    STANDARD_ENTITY_MISSING: (DIM_CONSISTENCY, 4.0),
    STRUCTURED_BACKBONE_MISSING: (DIM_CONSISTENCY, 5.0),
    SCAN_LIKE: (DIM_CONSISTENCY, 6.0),
    OCR_COVERAGE_WEAK: (DIM_CONSISTENCY, 5.0),
    OCR_HEADING_NOISE: (DIM_CONSISTENCY, 6.0),
    OCR_HEADING_NOISE_MINOR: (DIM_CONSISTENCY, 3.0),
    OCR_PARAMETER_POLLUTION: (DIM_CONSISTENCY, 6.0),
}

DIMENSION_FULL_SCORE: dict[str, float] = {
    DIM_BASE: 35.0,
    DIM_FACTUAL: 40.0,
    DIM_CONSISTENCY: 25.0,
}

# 红线分数上限（整数 74，避免 75.0 边界歧义）
REDLINE_CAP = 74.0

# 新版返回字段键名（对齐 .agent/skills/fp-review-output/SKILL.md 的 JSON 模板）
NEW_TOTAL_KEY = "\u603b\u5206"
NEW_PASS_KEY = "\u662f\u5426\u901a\u8fc7"
NEW_REDLINE_TRIGGERED_KEY = "\u7ea2\u7ebf\u89e6\u53d1"
NEW_REDLINE_LIST_KEY = "\u7ea2\u7ebf\u5217\u8868"
NEW_PROBLEM_LIST_KEY = "\u95ee\u9898\u6e05\u5355"
NEW_PROBLEM_STATS_KEY = "\u95ee\u9898\u7edf\u8ba1"
NEW_SUBSCORES_KEY = "\u5206\u9879\u8bc4\u5206"
NEW_DOC_TYPE_KEY = "\u6587\u6863\u7c7b\u578b"
REDLINE_NAME_FIELD = "\u7ea2\u7ebf\u540d\u79f0"
REDLINE_CAP_FIELD = "\u5206\u6570\u4e0a\u9650"
REDLINE_REASON_FIELD = "\u89e6\u53d1\u539f\u56e0"


def review_outputs(document: DocumentData, markdown: str, summary: dict[str, Any], tags: dict[str, Any]) -> dict[str, Any]:
    """按 FP §10 的 35/40/25 + 红线模型评分。

    评分流程：
    1. 各 `_review_*` 子检查产出 issues（结构不变）。
    2. 将 issues 映射到三个维度，逐项扣分；每维度最低 0。
    3. 检测红线（FP §10 的三条）：任一触发 → 总分 = min(总分, 74)。
    4. 通过条件：总分 ≥ 85 且 红线列表为空。
    """

    markdown_review = _review_markdown(document, markdown)
    summary_structure_review = _review_summary_structure(document, summary)
    summary_fact_review = _review_summary_facts(document, summary)
    summary_llm_stub_review = _review_summary_llm_stub(summary)
    summary_review = _merge_review_issues(summary_structure_review, summary_fact_review, summary_llm_stub_review)
    tag_review = _review_tags(document, tags)
    source_review = _review_sources(document, markdown)
    ocr_review = _review_ocr_quality(document, markdown)
    skeleton_review = _review_skeleton(document, markdown)
    metadata_review = _review_metadata_consistency(document, markdown)
    table_review = _review_table_criticality(document, markdown)
    source_review = _merge_review_issues_preserve(source_review, skeleton_review, metadata_review, table_review)

    problems = _build_problem_list(markdown_review, summary_review, tag_review, source_review, ocr_review)
    redlines = _detect_redlines(markdown_review, source_review)

    # 按维度收集扣分项
    base_deductions = _collect_deductions(DIM_BASE, markdown_review, summary_review, tag_review, source_review, ocr_review)
    factual_deductions = _collect_deductions(DIM_FACTUAL, markdown_review, summary_review, tag_review, source_review, ocr_review)
    consistency_deductions = _collect_deductions(DIM_CONSISTENCY, markdown_review, summary_review, tag_review, source_review, ocr_review)

    # 伪标题阈值是计算条件，不走 issue 常量；直接在 base 维度追加
    pseudo_titles = markdown_review.get(PSEUDO_HEADINGS, [])
    if len(pseudo_titles) > 5:
        base_deductions.append({
            "\u95ee\u9898": "\u4f2a\u6807\u9898\u8fc7\u591a",
            "\u6263\u5206": 3.0,
            "\u6458\u8981": f"\u4f2a\u6807\u9898 {len(pseudo_titles)} \u6761\uff08>5\uff09\u8868\u660e\u7ed3\u6784\u6e05\u6d01\u5ea6\u4e0d\u591f\u3002",
        })

    base_quality = max(0.0, DIMENSION_FULL_SCORE[DIM_BASE] - sum(item["\u6263\u5206"] for item in base_deductions))
    factual_quality = max(0.0, DIMENSION_FULL_SCORE[DIM_FACTUAL] - sum(item["\u6263\u5206"] for item in factual_deductions))
    consistency_quality = max(0.0, DIMENSION_FULL_SCORE[DIM_CONSISTENCY] - sum(item["\u6263\u5206"] for item in consistency_deductions))

    total = round(base_quality + factual_quality + consistency_quality, 2)
    if redlines:
        total = min(total, REDLINE_CAP)
    base_quality = round(base_quality, 2)
    factual_quality = round(factual_quality, 2)
    consistency_quality = round(consistency_quality, 2)

    severity_counter = Counter(item[KEY_LEVEL] for item in problems)
    is_pass = total >= 85.0 and not redlines

    return {
        "\u8f6e\u6b21": 1.0,
        NEW_TOTAL_KEY: total,
        NEW_PASS_KEY: is_pass,
        BASE_SCORE_KEY: base_quality,
        FACTUAL_SCORE_KEY: factual_quality,
        CONSISTENCY_SCORE_KEY: consistency_quality,
        NEW_REDLINE_TRIGGERED_KEY: bool(redlines),
        NEW_REDLINE_LIST_KEY: redlines,
        NEW_PROBLEM_LIST_KEY: problems,
        NEW_PROBLEM_STATS_KEY: {
            "\u0053\u7ea7\u95ee\u9898\u6570": float(severity_counter.get("S", 0)),
            "\u0041\u7ea7\u95ee\u9898\u6570": float(severity_counter.get("A", 0)),
            "\u0042\u7ea7\u95ee\u9898\u6570": float(severity_counter.get("B", 0)),
        },
        NEW_SUBSCORES_KEY: {
            "\u57fa\u7840\u8d28\u91cf\u5404\u6263\u5206\u70b9": base_deductions,
            "\u4e8b\u5b9e\u6b63\u786e\u6027\u5404\u6263\u5206\u70b9": factual_deductions,
            "\u4e00\u81f4\u6027\u5404\u6263\u5206\u70b9": consistency_deductions,
        },
        NEW_DOC_TYPE_KEY: document.文档画像.文档类型 if document.文档画像 else "unknown",
    }


def _collect_deductions(
    dimension: str,
    *reviews: dict[str, Any],
) -> list[dict[str, Any]]:
    """把 issues 按维度收集成扣分项明细，保留 issue 的原始常量和原因。"""

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for review in reviews:
        if not isinstance(review, dict):
            continue
        for item in review.get(KEY_ISSUES, []):
            content = item.get(KEY_CONTENT, "")
            mapping = ISSUE_DEDUCTIONS.get(content)
            if not mapping or mapping[0] != dimension:
                continue
            reason = item.get(KEY_REASON, "")
            key = (content, reason)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "\u95ee\u9898": content,
                "\u6263\u5206": mapping[1],
                "\u6458\u8981": reason,
            })
    return out


def _review_markdown(document: DocumentData, markdown: str) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    headings = [line.strip() for line in markdown.splitlines() if line.lstrip().startswith("#")]
    content_lines = [line for line in markdown.splitlines() if line.strip() and not line.lstrip().startswith("#")]

    pseudo_titles = [item for item in headings if SHORT_HEADING_RE.fullmatch(item) or SENTENCE_HEADING_RE.fullmatch(item)]
    auto_table_titles = [item for item in headings if SYNTHETIC_TABLE_TITLE_RE.fullmatch(item)]

    if len(document.章节列表) == 0:
        issues.append({KEY_CONTENT: DOC_CHAIN_MISSING, KEY_REASON: "\u672a\u80fd\u5efa\u7acb\u7a33\u5b9a\u7684\u7ae0\u8282\u7ed3\u6784\uff0cmarkdown \u53ea\u6709\u5143\u6570\u636e\u6216\u6781\u5c11\u6b63\u6587\u3002"})
    if len(headings) <= 2 or len(content_lines) <= 3:
        issues.append({KEY_CONTENT: MARKDOWN_TOO_SHORT, KEY_REASON: "\u5f53\u524d\u8f93\u51fa\u7f3a\u5c11\u8db3\u591f\u7684\u7ed3\u6784\u5316\u6b63\u6587\u5185\u5bb9\u3002"})
    if document.表格列表 and not any(line.startswith("| ") for line in markdown.splitlines()):
        issues.append({KEY_CONTENT: TABLE_VIEW_MISSING, KEY_REASON: "\u5df2\u7ecf\u62bd\u53d6\u51fa\u8868\u683c\uff0c\u4f46 markdown \u4e2d\u6ca1\u6709\u8868\u683c\u53ef\u89c6\u5316\u3002"})
    if auto_table_titles:
        issues.append({KEY_CONTENT: AUTO_TABLE_TITLE_LEFT, KEY_REASON: "markdown \u4e2d\u4ecd\u7136\u51fa\u73b0\u7cfb\u7edf\u751f\u6210\u7684\u9875\u7ea7\u8868\u6807\u9898\uff0c\u8bf4\u660e\u8868\u683c\u89c6\u56fe\u8fd8\u5728\u6c61\u67d3\u6b63\u6587\u4e3b\u94fe\u3002"})

    return {
        KEY_ISSUES: issues,
        PSEUDO_HEADINGS: [{KEY_CONTENT: item, KEY_REASON: "\u6807\u9898\u8fc7\u77ed\u6216\u66f4\u50cf\u53e5\u5b50\u6b8b\u7247\u3002"} for item in pseudo_titles[:20]],
        TABLE_FRAGMENTS: [],
        TOC_RESIDUE: [],
        AUTO_TABLE_TITLES: [{KEY_CONTENT: item, KEY_REASON: "\u9875\u7ea7\u8868\u6807\u9898\u5e94\u4f5c\u4e3a\u8868\u683c\u5143\u6570\u636e\uff0c\u800c\u4e0d\u662f\u6b63\u6587\u6807\u9898\u3002"} for item in auto_table_titles[:20]],
    }


def _review_summary_structure(document: DocumentData, summary: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    chapter_items = summary.get("\u7ae0\u8282\u6458\u8981", [])
    full_summary = normalize_line(str(summary.get("\u5168\u6587\u6458\u8981", "")))

    if document.章节列表 and not chapter_items:
        issues.append({KEY_CONTENT: CHAPTER_SUMMARY_EMPTY, KEY_REASON: "\u5df2\u7ecf\u62bd\u53d6\u51fa\u7ae0\u8282\uff0c\u4f46\u6458\u8981\u6ca1\u6709\u8986\u76d6\u8fd9\u4e9b\u7ae0\u8282\u3002"})
    if not summary.get("_llm_backend") and _looks_like_template_summary(full_summary):
        issues.append({KEY_CONTENT: SUMMARY_TEMPLATE_FALLBACK, KEY_REASON: "\u6458\u8981\u770b\u8d77\u6765\u4ecd\u662f fallback \u6a21\u677f\u53e5\uff0c\u4f46\u6ca1\u6709 LLM \u540e\u7aef\u8bc1\u636e\uff0c\u4e0d\u5e94\u88ab\u9ed8\u8ba4\u89c6\u4e3a\u9ad8\u8d28\u91cf\u6458\u8981\u3002"})

    return {
        KEY_ISSUES: issues,
        ILLEGAL_SECTION_NAMES: [],
        INTERNAL_CODES: [],
        EMPTY_CHAPTER_SUMMARIES: [],
        TABLE_RULE_ERRORS: [],
        PARAM_MULTI_VALUE_ERRORS: [],
        MISSING_MAIN_COVERAGE: [],
        LOW_PARAMETER_COVERAGE: [],
    }


def _review_summary_facts(document: DocumentData, summary: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    param_summary = summary.get("\u53c2\u6570\u6458\u8981", {}) if isinstance(summary.get("\u53c2\u6570\u6458\u8981"), dict) else {}
    numeric_items = param_summary.get("\u6570\u503c\u578b\u53c2\u6570", [])
    parameter_entries = get_parameter_entries(document)

    if parameter_entries and not numeric_items:
        issues.append({KEY_CONTENT: PARAM_SUMMARY_EMPTY, KEY_REASON: "\u5df2\u7ecf\u5efa\u7acb\u53c2\u6570\u4e8b\u5b9e\uff0c\u4f46 summary \u6ca1\u6709\u6d88\u8d39\u8fd9\u4e9b\u53c2\u6570\u3002"})

    return {
        KEY_ISSUES: issues,
        ILLEGAL_SECTION_NAMES: [],
        INTERNAL_CODES: [],
        EMPTY_CHAPTER_SUMMARIES: [],
        TABLE_RULE_ERRORS: [],
        PARAM_MULTI_VALUE_ERRORS: [],
        MISSING_MAIN_COVERAGE: [],
        LOW_PARAMETER_COVERAGE: issues[:1] if parameter_entries and not numeric_items else [],
    }


def _merge_review_issues(*reviews: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for review in reviews:
        for item in review.get(KEY_ISSUES, []):
            key = (item.get(KEY_CONTENT, ""), item.get(KEY_REASON, ""))
            if key in seen:
                continue
            seen.add(key)
            issues.append(item)
    return {KEY_ISSUES: issues}


def _review_tags(document: DocumentData, tags: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    parameter_entries = get_parameter_entries(document)
    standard_entries = get_standard_entries(document)
    product_entries = get_product_entries(document)
    parameter_tags = tags.get("\u53c2\u6570\u6807\u7b7e", []) or []
    noisy_parameter_tags = [normalize_line(str(item)) for item in parameter_tags if _is_suspicious_parameter_tag(str(item))]
    sentence_like_tags = _find_sentence_like_tags(tags)

    if standard_entries and not tags.get("\u6807\u51c6\u5f15\u7528\u6807\u7b7e"):
        issues.append({KEY_CONTENT: STANDARD_TAG_EMPTY, KEY_REASON: "\u5df2\u7ecf\u8bc6\u522b\u5230\u6807\u51c6\u5b9e\u4f53\uff0c\u4f46\u6807\u7b7e\u4e2d\u6ca1\u6709\u4f53\u73b0\u6807\u51c6\u65cf\u3002"})
    if parameter_entries and not tags.get("\u53c2\u6570\u6807\u7b7e"):
        issues.append({KEY_CONTENT: PARAM_TAG_EMPTY, KEY_REASON: "\u5df2\u7ecf\u5efa\u7acb\u53c2\u6570\u4e8b\u5b9e\uff0c\u4f46\u6807\u7b7e\u6ca1\u6709\u5b8c\u6210\u6536\u53e3\u3002"})
    if product_entries and not tags.get("\u4ea7\u54c1\u578b\u53f7\u6807\u7b7e"):
        issues.append({KEY_CONTENT: PRODUCT_MODEL_TAG_EMPTY, KEY_REASON: "\u5df2\u7ecf\u5efa\u7acb\u4ea7\u54c1\u5b9e\u4f53\uff0c\u4f46\u6807\u7b7e\u6ca1\u6709\u4f53\u73b0\u578b\u53f7\u3002"})
    if noisy_parameter_tags:
        issues.append({KEY_CONTENT: NOISY_PARAMETER_TAGS, KEY_REASON: "\u53c2\u6570\u6807\u7b7e\u4e2d\u4ecd\u7136\u6df7\u5165\u4e86\u8868\u5934\u788e\u7247\u3001\u7ef4\u5ea6\u4ee3\u53f7\u6216\u53e5\u5b50\u6b8b\u7247\u3002"})
    if sentence_like_tags:
        issues.append({KEY_CONTENT: SENTENCE_TAG_POLLUTION, KEY_REASON: "\u6807\u7b7e\u4e2d\u51fa\u73b0\u4e86\u6574\u53e5\u89c4\u683c\u8bf4\u660e\u6216\u957f\u53e5\uff0c\u8bf4\u660e OCR \u7ed3\u679c\u8fd8\u6ca1\u6709\u88ab\u6b63\u786e\u538b\u7f29\u4e3a\u6807\u7b7e\u3002"})
    # §2.4 OCR 标签噪音：文档主题标签任一条 >30 字符 且含"为…、…"这种整句说明句式 → B 级扣分
    topic_tags = tags.get("\u6587\u6863\u4e3b\u9898\u6807\u7b7e", []) or []
    ocr_topic_noise = [
        normalize_line(str(tag))
        for tag in topic_tags
        if len(normalize_line(str(tag))) > 30
        and re.search(r"\u4e3a[^\uff0c\u3001\u3002]+[\uff0c\u3001]", normalize_line(str(tag)))
    ]
    if ocr_topic_noise:
        issues.append({KEY_CONTENT: SENTENCE_TAG_POLLUTION, KEY_REASON: "\u6587\u6863\u4e3b\u9898\u6807\u7b7e\u51fa\u73b0\u957f\u53e5\uff08>30 \u5b57\u7b26\u4e14\u542b '\u4e3a...\u3001' \u8fde\u63a5\u8bcd\uff09\uff0c\u5c5e\u4e8e OCR \u9875\u4ea7\u7269\u6c61\u67d3\u3002"})

    return {
        KEY_ISSUES: issues,
        NOISY_TAGS: (
            [{KEY_CONTENT: item, KEY_REASON: "\u4f4e\u4fe1\u53f7\u53c2\u6570\u6807\u7b7e\uff0c\u66f4\u50cf\u8868\u5934\u6216\u7ef4\u5ea6\u4ee3\u53f7\u3002"} for item in noisy_parameter_tags[:20]]
            + [{KEY_CONTENT: item, KEY_REASON: "\u6807\u7b7e\u5df2\u7ecf\u53d8\u6210\u89c4\u683c\u53e5\u6216\u8bf4\u660e\u53e5\uff0c\u4e0d\u518d\u662f\u7d27\u51d1\u6807\u7b7e\u3002"} for item in sentence_like_tags[:20]]
        ),
        MISCLASSIFIED_TAGS: [],
        MISSING_CRITICAL_TAGS: issues,
    }


def _review_ocr_quality(document: DocumentData, markdown: str) -> dict[str, Any]:
    attempted_ocr_pages = [page for page in document.页面列表 if getattr(page, "是否执行OCR", False)]
    injected_ocr_pages = [page for page in attempted_ocr_pages if getattr(page, "OCR是否注入解析", False)]
    issues: list[dict[str, str]] = []

    headings = [line.strip() for line in markdown.splitlines() if line.lstrip().startswith("#")]
    suspicious_headings = [item for item in headings if _is_suspicious_ocr_heading(item)]
    suspicious_parameters = _find_suspicious_parameters(document)
    injected_ratio = len(injected_ocr_pages) / max(1, len(attempted_ocr_pages)) if attempted_ocr_pages else 0.0

    if attempted_ocr_pages and injected_ratio < 0.5:
        issues.append({KEY_CONTENT: OCR_COVERAGE_WEAK, KEY_REASON: "\u5df2\u6267\u884c OCR\uff0c\u4f46\u53ef\u6ce8\u5165 parser \u7684\u9875\u8986\u76d6\u7387\u504f\u4f4e\uff0c\u8bf4\u660e OCR \u76f8\u5f53\u4e00\u90e8\u5206\u7ed3\u679c\u4ecd\u4e0d\u53ef\u4fe1\u3002"})
    if attempted_ocr_pages and 2 <= len(suspicious_headings) < 5:
        issues.append({
            KEY_CONTENT: OCR_HEADING_NOISE_MINOR,
            KEY_REASON: f"markdown 中疑似乱码标题 {len(suspicious_headings)} 条（2≤x<5），B 级扣分但不触发红线。",
        })
    elif attempted_ocr_pages and len(suspicious_headings) >= 5:
        issues.append({
            KEY_CONTENT: OCR_HEADING_NOISE,
            KEY_REASON: f"markdown 中疑似乱码标题 {len(suspicious_headings)} 条（≥5），输出质量不可信。",
        })
    if attempted_ocr_pages and len(suspicious_parameters) >= max(2, len(document.数值参数列表) // 3):
        issues.append({KEY_CONTENT: OCR_PARAMETER_POLLUTION, KEY_REASON: "\u53c2\u6570\u7ed3\u6784\u5316\u7ed3\u679c\u91cc\u6df7\u5165\u4e86\u65e5\u671f\u3001\u6807\u51c6\u53f7\u6216\u6587\u6863\u5143\u6570\u636e\u3002"})

    return {
        KEY_ISSUES: issues,
        "OCR尝试页数": len(attempted_ocr_pages),
        "OCR注入页数": len(injected_ocr_pages),
        "OCR覆盖率": round(injected_ratio, 3),
        "可疑标题": suspicious_headings[:20],
        "可疑参数": suspicious_parameters[:20],
    }


_LLM_STUB_RE = re.compile(
    r"^(?:文档可提取内容极少|当前仅识别到|由于原始文本层缺失|未获得实质性|"
    r"无法从现有原料|当前识别为|已建立\d+个|已抽取\d+条)"
)

_STANDARD_CODE_IN_NAME_RE = re.compile(
    # §3.5 覆盖 "CB 1010-1990" / "CB/T 4196-2011" / "CB_T 4196-2011" / "CB_Z 281-2011"
    # 等形态——OCR 和 Windows 文件名里常以下划线代替 "/" 或空格。
    r"(CB|GB|ISO|CH|IEC|JIS)(?:[/_][TZ])?[\s_]*(\d+)[-—.](\d+)",
    re.IGNORECASE,
)


def _canonicalize_standard_code(text: str) -> str:
    match = STANDARD_CODE_TOKEN_RE.search(normalize_line(text))
    if not match:
        return ""
    base = match.group("base").upper()
    sub = (match.group("sub") or "").upper()
    number = match.group("number")
    year = re.sub(r"[-—–_.一]+", "-", match.group("year"))
    family = f"{base}/{sub}" if sub else base
    return f"{family} {number}-{year}"


def _extract_canonical_standard_codes(text: str) -> set[str]:
    codes: set[str] = set()
    normalized = normalize_line(text)
    for match in STANDARD_CODE_TOKEN_RE.finditer(normalized):
        code = _canonicalize_standard_code(match.group(0))
        if code:
            codes.add(code)
    return codes


def _strip_markdown_metadata(markdown: str) -> str:
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


def _review_skeleton(document: DocumentData, markdown: str) -> dict[str, list[dict[str, str]]]:
    """空骨架检查：章节≤1 且 参数=0 且 标准=0 且 markdown 非空行数 <15 时触发。"""

    issues: list[dict[str, str]] = []
    non_empty_lines = [line for line in markdown.splitlines() if line.strip()]
    if (
        len(document.章节列表) <= 1
        and len(document.数值参数列表) == 0
        and len(document.引用标准列表) == 0
        and len(non_empty_lines) < 15
    ):
        issues.append({
            KEY_CONTENT: DOC_CHAIN_MISSING,
            KEY_REASON: "文档骨架未建立：章节/参数/标准全部为空或缺失，markdown 正文过短。",
        })
    return {KEY_ISSUES: issues}


def _review_summary_llm_stub(summary: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """LLM 自述无内容：摘要开头匹配工程模板句。"""

    issues: list[dict[str, str]] = []
    full_summary = normalize_line(str(summary.get("\u5168\u6587\u6458\u8981", "")))
    if full_summary and _LLM_STUB_RE.match(full_summary):
        issues.append({
            KEY_CONTENT: LLM_STUB_SUMMARY,
            KEY_REASON: "summary.全文摘要 以 LLM 自述无内容的模板句开头，说明下游实际没有可消费正文。",
        })
    return {KEY_ISSUES: issues}


def _review_metadata_consistency(document: DocumentData, markdown: str) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    mismatch_reason = detect_metadata_mismatch_reason(document, markdown)
    if not mismatch_reason:
        return {KEY_ISSUES: issues}
    issues.append({
        KEY_CONTENT: METADATA_MISMATCH,
        KEY_REASON: mismatch_reason,
    })
    return {KEY_ISSUES: issues}


def _review_table_criticality(document: DocumentData, markdown: str) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    if document.表格列表:
        return {KEY_ISSUES: issues}

    file_name = normalize_line(getattr(document.文件元数据, "\u6587\u4ef6\u540d\u79f0", "") or "")
    title = normalize_line(metadata_title(document.文件元数据))
    body_text = _strip_markdown_metadata(markdown)
    title_hit = bool(TABLE_DRIVEN_TITLE_RE.search(f"{file_name} {title}"))
    body_hits = {normalize_line(match.group(0)) for match in TABLE_DRIVEN_BODY_RE.finditer(body_text[:5000])}
    if title_hit and len(body_hits) >= 2:
        issues.append({
            KEY_CONTENT: TABLE_CORE_MISSING,
            KEY_REASON: "文档明显以表格/尺寸对照为核心内容，但结构化结果中未抽取到核心表格。",
        })
    return {KEY_ISSUES: issues}


def _merge_review_issues_preserve(base: dict[str, Any], *others: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """把 others 中的 issues 追加到 base 中，保留 base 其他字段（如 ABNORMAL_PARAM_SOURCES）。"""

    merged = dict(base)
    issues = list(base.get(KEY_ISSUES, []))
    seen: set[tuple[str, str]] = {(i.get(KEY_CONTENT, ""), i.get(KEY_REASON, "")) for i in issues}
    for other in others:
        for item in other.get(KEY_ISSUES, []):
            key = (item.get(KEY_CONTENT, ""), item.get(KEY_REASON, ""))
            if key in seen:
                continue
            seen.add(key)
            issues.append(item)
    merged[KEY_ISSUES] = issues
    return merged


def _review_sources(document: DocumentData, markdown: str) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    title = normalize_line(metadata_title(document.文件元数据))
    parameter_entries = get_parameter_entries(document)
    standard_entries = get_standard_entries(document)
    raw_text = "\n".join(" ".join(page.get("lines", [])) for page in document.原始页面列表)
    source_lines = [
        normalize_line(line)
        for page in getattr(document, "页面列表", []) or []
        for line in str(getattr(page, "原始文本", "") or "").splitlines()
        if normalize_line(line)
    ]

    attempted_ocr_pages = [page for page in document.页面列表 if getattr(page, "是否执行OCR", False)]
    injected_ocr_pages = [page for page in attempted_ocr_pages if getattr(page, "OCR是否注入解析", False)]
    injected_ratio = len(injected_ocr_pages) / max(1, len(attempted_ocr_pages))
    recovered_text = bool(document.文档画像 and document.文档画像.文本行数 >= max(80, len(document.页面列表) * 20))
    has_main_chain = len(document.章节列表) >= 2 and len(markdown.splitlines()) >= 12
    content_indicates_ocr, content_ocr_reasons, _ = needs_ocr_by_text_layer(
        source_lines,
        page_count=max(1, len(document.页面列表)),
    )
    if (
        document.文档画像
        and document.文档画像.是否需要OCR
        and not attempted_ocr_pages
    ):
        issues.append({KEY_CONTENT: SCAN_LIKE, KEY_REASON: f"\u300a{title}\u300b profile \u5224\u5b9a\u9700\u8981 OCR \u4f46\u672c\u8f6e\u672a\u6d3e\u53d1\u8fc7 OCR\uff0c\u5f53\u524d\u7ed3\u679c\u4e0d\u8db3\u4ee5\u652f\u6491\u7a33\u5b9a\u62bd\u53d6\u3002"})
    elif content_indicates_ocr and not attempted_ocr_pages and not (recovered_text and has_main_chain):
        issues.append({
            KEY_CONTENT: SCAN_LIKE,
            KEY_REASON: f"\u300a{title}\u300b\u6587\u672c\u5c42\u867d\u975e\u7eaf\u7a7a\u767d\uff0c\u4f46\u5e7f\u544a/\u5143\u6570\u636e\u4fe1\u53f7\u504f\u91cd\u4e14\u7ed3\u6784\u4fe1\u53f7\u4e0d\u8db3\uff08{', '.join(content_ocr_reasons[:3])}\uff09\uff0c\u5e94\u4f18\u5148\u8d70 OCR \u515c\u5e95\u3002",
        })
    elif attempted_ocr_pages and injected_ratio < 0.5 and not (recovered_text and has_main_chain):
        issues.append({KEY_CONTENT: SCAN_LIKE, KEY_REASON: f"\u300a{title}\u300b\u5df2\u6267\u884c OCR\uff0c\u4f46\u53ef\u6ce8\u5165 parser \u7684\u9875\u5360\u6bd4\u4ecd\u8fc7\u4f4e\uff0c\u7ed3\u679c\u4e0d\u8db3\u4ee5\u652f\u6491\u7a33\u5b9a\u62bd\u53d6\u3002"})
    elif (
        document.文档画像
        and document.文档画像.每页平均字符数 < 20
        and not attempted_ocr_pages
    ):
        issues.append({KEY_CONTENT: SCAN_LIKE, KEY_REASON: f"\u300a{title}\u300b\u6bcf\u9875\u5e73\u5747\u5b57\u7b26\u6570\u6781\u4f4e\uff08<20\uff09\u4f46\u672a\u6d3e\u53d1 OCR\uff0c\u7591\u4f3c\u626b\u63cf\u4ef6\u3002"})
    if document.文档画像 and document.文档画像.文本行数 > 0 and not document.章节列表 and not document.表格列表:
        issues.append({KEY_CONTENT: STRUCTURE_MISSING, KEY_REASON: "\u9875\u9762\u5df2\u6709\u6587\u672c\uff0c\u4f46\u6ca1\u6709\u5efa\u7acb section \u6216 table \u7ed3\u6784\u3002"})
    if document.表格列表 and not parameter_entries:
        issues.append({KEY_CONTENT: TABLE_NOT_CONSUMED, KEY_REASON: "\u8868\u683c\u5b58\u5728\uff0c\u4f46\u6ca1\u6709\u4ea7\u51fa\u53c2\u6570\u4e8b\u5b9e\u3002"})
    if not standard_entries and STANDARD_CODE_RE.search(raw_text):
        issues.append({KEY_CONTENT: STANDARD_ENTITY_MISSING, KEY_REASON: "\u6587\u6863\u770b\u8d77\u6765\u5305\u542b\u6807\u51c6\u53f7\uff0c\u4f46\u7ed3\u6784\u5316\u7ed3\u679c\u91cc\u6ca1\u6709\u5bf9\u5e94\u6807\u51c6\u5b9e\u4f53\u3002"})
    if document.文档画像 and document.文档画像.文本行数 > 0 and not document.结构节点列表:
        issues.append({KEY_CONTENT: STRUCTURED_BACKBONE_MISSING, KEY_REASON: "\u6587\u6863\u5df2\u7ecf\u6709\u6587\u672c\u5c42\uff0c\u4f46\u4fee\u6b63\u540e\u7684\u7ed3\u6784\u5316\u4e3b\u7ebf\u6ca1\u6709\u6210\u529f\u91cd\u5efa\u3002"})

    return {
        KEY_ISSUES: issues,
        ABNORMAL_PARAM_SOURCES: issues if document.表格列表 and not parameter_entries else [],
        ABNORMAL_RULE_SOURCES: [],
    }


def _detect_redlines(
    markdown_review: dict[str, list[dict[str, str]]],
    source_review: dict[str, list[dict[str, str]]],
    summary_review: dict[str, list[dict[str, str]]] | None = None,
    ocr_review: dict[str, list[dict[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    redlines: list[dict[str, Any]] = []
    doc_chain_issue = (
        any(item[KEY_CONTENT] == DOC_CHAIN_MISSING for item in markdown_review[KEY_ISSUES])
        or any(item[KEY_CONTENT] == DOC_CHAIN_MISSING for item in source_review[KEY_ISSUES])
    )
    if doc_chain_issue:
        redlines.append({KEY_REDLINE_NAME: "\u539f\u6587\u89e3\u6790\u672a\u5efa\u7acb\u6b63\u6587\u4e3b\u94fe", KEY_REASON: "markdown \u4e2d\u51e0\u4e4e\u53ea\u6709\u5143\u6570\u636e\uff0c\u8bf4\u660e\u6b63\u6587\u7ae0\u8282\u94fe\u6ca1\u6709\u771f\u6b63\u5efa\u7acb\u3002", KEY_CAP: 59.99})
    if any(item[KEY_CONTENT] == TABLE_NOT_CONSUMED for item in source_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: "\u8868\u683c\u5b58\u5728\u4f46\u53c2\u6570\u672a\u5efa\u7acb", KEY_REASON: "\u8868\u683c\u5df2\u62bd\u53d6\uff0c\u4f46\u6ca1\u6709\u8f6c\u6210\u53c2\u6570\u4e8b\u5b9e\u3002", KEY_CAP: 79.99})
    if any(item[KEY_CONTENT] == TABLE_CORE_MISSING for item in source_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: TABLE_CORE_MISSING, KEY_REASON: "文档明显以表格/尺寸对照为主，但结构化结果没有抽到核心表格。", KEY_CAP: 74.99})
    if any(item[KEY_CONTENT] == SCAN_LIKE for item in source_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: "\u6587\u672c\u5c42\u4e0d\u8db3\u9700\u8981OCR", KEY_REASON: "\u9875\u9762\u6587\u672c\u5c42\u6781\u5f31\uff0c\u5f53\u524d\u7ed3\u679c\u4e0d\u8db3\u4ee5\u652f\u6491\u7a33\u5b9a\u62bd\u53d6\u3002", KEY_CAP: 74.99})
    if any(item[KEY_CONTENT] == METADATA_MISMATCH for item in source_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: METADATA_MISMATCH, KEY_REASON: "\u6587\u4ef6\u540d\u4e0e\u6b63\u6587/\u6807\u51c6\u5217\u8868\u4e2d\u7684\u6807\u51c6\u53f7\u4e0d\u5339\u914d\uff0c\u7591\u4f3c\u6587\u672c\u5c42\u8282\u9e1f\u6362\u5de2\u3002", KEY_CAP: 59.99})
    if summary_review and any(item[KEY_CONTENT] == LLM_STUB_SUMMARY for item in summary_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: LLM_STUB_SUMMARY, KEY_REASON: "summary.\u5168\u6587\u6458\u8981 \u4ee5 LLM \u81ea\u8ff0\u65e0\u5185\u5bb9\u6a21\u677f\u53e5\u5f00\u5934\uff0c\u4e0d\u5e94\u88ab\u5f53\u4f5c\u6709\u6548\u6458\u8981\u3002", KEY_CAP: 59.99})
    if ocr_review and any(item[KEY_CONTENT] == OCR_HEADING_NOISE for item in ocr_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: OCR_HEADING_NOISE, KEY_REASON: "OCR 后 markdown 仍有多条伪标题，输出质量不足以交付。", KEY_CAP: 74.99})
    if ocr_review and any(item[KEY_CONTENT] == OCR_PARAMETER_POLLUTION for item in ocr_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: OCR_PARAMETER_POLLUTION, KEY_REASON: "OCR 后参数事实仍被前言/出版元数据污染，输出质量不足以交付。", KEY_CAP: 74.99})
    return redlines


def _build_problem_list(
    markdown_review: dict[str, list[dict[str, str]]],
    summary_review: dict[str, list[dict[str, str]]],
    tag_review: dict[str, list[dict[str, str]]],
    source_review: dict[str, list[dict[str, str]]],
    ocr_review: dict[str, Any],
) -> list[dict[str, str]]:
    ocr_minor_issues = [item for item in ocr_review[KEY_ISSUES] if item[KEY_CONTENT] == OCR_HEADING_NOISE_MINOR]
    ocr_major_issues = [item for item in ocr_review[KEY_ISSUES] if item[KEY_CONTENT] != OCR_HEADING_NOISE_MINOR]
    mapping = [
        ("S", "\u539f\u6587\u89e3\u6790.md", "\u7ed3\u6784\u7f3a\u5931", markdown_review[KEY_ISSUES]),
        ("A", "summary.json", "\u6458\u8981\u7f3a\u5931", summary_review[KEY_ISSUES]),
        ("B", "tags.json", "\u6807\u7b7e\u7f3a\u5931", tag_review[KEY_ISSUES]),
        ("S", "\u7ed3\u6784\u5316\u7ed3\u679c", "\u6765\u6e90\u5f02\u5e38", source_review[KEY_ISSUES]),
        ("A", "OCR专项检查", "\u8f93\u51fa\u8d28\u91cf\u98ce\u9669", ocr_major_issues),
        ("B", "OCR专项检查", "\u8f93\u51fa\u8d28\u91cf\u98ce\u9669", ocr_minor_issues),
    ]
    problems: list[dict[str, str]] = []
    severity_rank = {"S": 0, "A": 1, "B": 2}
    deduped: dict[str, dict[str, str]] = {}
    for level, target, problem_type, items in mapping:
        for item in items:
            meta = _problem_meta(item[KEY_CONTENT])
            problem = {
                KEY_PROBLEM_ID: meta[KEY_PROBLEM_ID],
                KEY_LEVEL: level,
                KEY_TARGET: target,
                KEY_TYPE: problem_type,
                KEY_POSITION: item[KEY_CONTENT],
                KEY_CONTENT: item[KEY_CONTENT],
                KEY_REASON: item[KEY_REASON],
                KEY_FIX: _suggest_fix(item[KEY_CONTENT]),
                KEY_ROOT_MODULE: meta[KEY_ROOT_MODULE],
                KEY_ACTION: meta[KEY_ACTION],
                KEY_BLOCKING: meta[KEY_BLOCKING],
                KEY_AFFECTED_OUTPUTS: meta[KEY_AFFECTED_OUTPUTS],
            }
            existing = deduped.get(meta[KEY_PROBLEM_ID])
            if existing is None or severity_rank[level] < severity_rank[existing[KEY_LEVEL]]:
                deduped[meta[KEY_PROBLEM_ID]] = problem
    problems.extend(deduped.values())
    problems.sort(key=lambda item: severity_rank.get(item[KEY_LEVEL], 9))
    return problems


def _problem_meta(problem: str) -> dict[str, Any]:
    default = {
        KEY_PROBLEM_ID: problem,
        KEY_ROOT_MODULE: "",
        KEY_ACTION: "",
        KEY_BLOCKING: False,
        KEY_AFFECTED_OUTPUTS: [],
    }
    mapping = {
        DOC_CHAIN_MISSING: {
            KEY_PROBLEM_ID: "doc_chain_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "tags"],
        },
        STRUCTURE_MISSING: {
            KEY_PROBLEM_ID: "structure_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "tags"],
        },
        STRUCTURED_BACKBONE_MISSING: {
            KEY_PROBLEM_ID: "structured_backbone_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "tags"],
        },
        OCR_COVERAGE_WEAK: {
            KEY_PROBLEM_ID: "ocr_coverage_weak",
            KEY_ROOT_MODULE: "ocr",
            KEY_ACTION: "标记需OCR",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "review"],
        },
        OCR_HEADING_NOISE: {
            KEY_PROBLEM_ID: "ocr_heading_noise",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "review"],
        },
        OCR_HEADING_NOISE_MINOR: {
            KEY_PROBLEM_ID: "ocr_heading_noise_minor",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "观察",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "review"],
        },
        OCR_PARAMETER_POLLUTION: {
            KEY_PROBLEM_ID: "ocr_parameter_pollution",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["document", "summary", "tags", "review"],
        },
        SUMMARY_TEMPLATE_FALLBACK: {
            KEY_PROBLEM_ID: "summary_template_fallback",
            KEY_ROOT_MODULE: "summarizer",
            KEY_ACTION: "重建summary",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["summary", "review"],
        },
        LLM_STUB_SUMMARY: {
            KEY_PROBLEM_ID: "llm_stub_summary",
            KEY_ROOT_MODULE: "summarizer",
            KEY_ACTION: "重建summary",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["summary", "review"],
        },
        METADATA_MISMATCH: {
            KEY_PROBLEM_ID: "metadata_mismatch",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "tags", "review"],
        },
        TABLE_NOT_TO_PARAM: {
            KEY_PROBLEM_ID: "table_to_param_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "summary", "tags"],
        },
        TABLE_NOT_CONSUMED: {
            KEY_PROBLEM_ID: "table_to_param_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "summary", "tags"],
        },
        TABLE_CORE_MISSING: {
            KEY_PROBLEM_ID: "table_core_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "review"],
        },
        STANDARD_ENTITY_MISSING: {
            KEY_PROBLEM_ID: "standard_entity_missing",
            KEY_ROOT_MODULE: "parser",
            KEY_ACTION: "重跑parser",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["document", "tags", "trace_map"],
        },
        SCAN_LIKE: {
            KEY_PROBLEM_ID: "scan_like",
            KEY_ROOT_MODULE: "ocr",
            KEY_ACTION: "标记需OCR",
            KEY_BLOCKING: True,
            KEY_AFFECTED_OUTPUTS: ["document", "markdown", "summary", "tags"],
        },
        MARKDOWN_TOO_SHORT: {
            KEY_PROBLEM_ID: "markdown_too_short",
            KEY_ROOT_MODULE: "md_builder",
            KEY_ACTION: "重建markdown",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["markdown"],
        },
        TABLE_VIEW_MISSING: {
            KEY_PROBLEM_ID: "table_view_missing",
            KEY_ROOT_MODULE: "md_builder",
            KEY_ACTION: "重建markdown",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["markdown"],
        },
        AUTO_TABLE_TITLE_LEFT: {
            KEY_PROBLEM_ID: "auto_table_title_left",
            KEY_ROOT_MODULE: "md_builder",
            KEY_ACTION: "重建markdown",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["markdown"],
        },
        CHAPTER_SUMMARY_EMPTY: {
            KEY_PROBLEM_ID: "chapter_summary_empty",
            KEY_ROOT_MODULE: "summarizer",
            KEY_ACTION: "重建summary",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["summary"],
        },
        PARAM_SUMMARY_EMPTY: {
            KEY_PROBLEM_ID: "param_summary_empty",
            KEY_ROOT_MODULE: "summarizer",
            KEY_ACTION: "重建summary",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["summary"],
        },
        STANDARD_TAG_EMPTY: {
            KEY_PROBLEM_ID: "standard_tag_empty",
            KEY_ROOT_MODULE: "tagger",
            KEY_ACTION: "重建tags",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["tags"],
        },
        PARAM_TAG_EMPTY: {
            KEY_PROBLEM_ID: "param_tag_empty",
            KEY_ROOT_MODULE: "tagger",
            KEY_ACTION: "重建tags",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["tags"],
        },
        PRODUCT_MODEL_TAG_EMPTY: {
            KEY_PROBLEM_ID: "product_model_tag_empty",
            KEY_ROOT_MODULE: "tagger",
            KEY_ACTION: "重建tags",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["tags"],
        },
        NOISY_PARAMETER_TAGS: {
            KEY_PROBLEM_ID: "noisy_parameter_tags",
            KEY_ROOT_MODULE: "fixer",
            KEY_ACTION: "清洗标签噪音",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["tags"],
        },
        SENTENCE_TAG_POLLUTION: {
            KEY_PROBLEM_ID: "sentence_tag_pollution",
            KEY_ROOT_MODULE: "tagger",
            KEY_ACTION: "重建tags",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["tags", "review"],
        },
        MISSING_CRITICAL_TAGS: {
            KEY_PROBLEM_ID: "missing_critical_tags",
            KEY_ROOT_MODULE: "tagger",
            KEY_ACTION: "重建tags",
            KEY_BLOCKING: False,
            KEY_AFFECTED_OUTPUTS: ["tags"],
        },
    }
    return mapping.get(problem, default)


def _suggest_fix(problem: str) -> str:
    mapping = {
        DOC_CHAIN_MISSING: "\u4f18\u5148\u4fee\u590d parser \u7684 block/section \u5efa\u7acb\u903b\u8f91\uff0c\u4e0d\u518d\u4f9d\u8d56\u7279\u5b9a\u7ae0\u8282\u6a21\u677f\u3002",
        MARKDOWN_TOO_SHORT: "\u8ba9 markdown \u76f4\u63a5\u6d88\u8d39\u4fee\u6b63\u540e\u7684 sections/tables\uff0c\u800c\u4e0d\u662f\u53ea\u5c55\u793a\u5143\u6570\u636e\u3002",
        TABLE_VIEW_MISSING: "\u8ba9 markdown \u8f93\u51fa\u76f4\u63a5\u6d88\u8d39\u62bd\u53d6\u5230\u7684\u8868\u683c\u7ed3\u6784\u3002",
        AUTO_TABLE_TITLE_LEFT: "\u5c06 synthetic \u8868\u6807\u9898\u4fdd\u7559\u5728 tables \u5143\u6570\u636e\u4e2d\uff0c\u4e0d\u518d\u62ac\u5347\u4e3a\u6b63\u6587\u6807\u9898\u3002",
        CHAPTER_SUMMARY_EMPTY: "summary \u5e94\u4f18\u5148\u6d88\u8d39\u4fee\u6b63\u540e\u7684 sections/facts\uff0c\u800c\u4e0d\u662f\u518d\u4ece\u5c55\u793a\u5c42\u731c\u6d4b\u3002",
        TABLE_NOT_TO_PARAM: "\u5f3a\u5316\u901a\u7528\u8868\u683c\u53c2\u6570\u62bd\u53d6\uff0c\u5e76\u8ba9 facts \u4e3b\u7ebf\u6210\u4e3a\u4e0b\u6e38\u552f\u4e00\u53c2\u6570\u6765\u6e90\u3002",
        PARAM_SUMMARY_EMPTY: "\u8ba9 summary \u76f4\u63a5\u6d88\u8d39 parameter facts\u3002",
        STANDARD_TAG_EMPTY: "\u6807\u51c6\u6807\u7b7e\u5e94\u76f4\u63a5\u4ece\u6807\u51c6\u5b9e\u4f53\u7684 family/code \u5f52\u4e00\u751f\u6210\u3002",
        PARAM_TAG_EMPTY: "\u53c2\u6570\u6807\u7b7e\u5e94\u57fa\u4e8e canonical parameter names \u6c47\u603b\u3002",
        PRODUCT_MODEL_TAG_EMPTY: "\u4ea7\u54c1\u6807\u7b7e\u5e94\u76f4\u63a5\u6d88\u8d39\u7ed3\u6784\u5316 products \u5b9e\u4f53\u3002",
        NOISY_PARAMETER_TAGS: "\u5bf9\u53c2\u6570\u6807\u7b7e\u5355\u72ec\u505a\u6807\u7b7e\u4e13\u7528\u5f52\u4e00\uff0c\u4e0d\u8981\u76f4\u63a5\u4f7f\u7528\u539f\u59cb\u8868\u5934\u5b57\u7b26\u4e32\u3002",
        SENTENCE_TAG_POLLUTION: "\u6807\u7b7e\u751f\u6210\u9700\u8981\u5148\u538b\u7f29 OCR \u957f\u53e5\u548c\u89c4\u683c\u53e5\uff0c\u907f\u514d\u628a\u6574\u53e5\u8bf4\u660e\u76f4\u63a5\u4f5c\u4e3a tag\u3002",
        SCAN_LIKE: "\u5728 intake \u9636\u6bb5\u589e\u52a0 OCR gating\uff0c\u4f4e\u6587\u672c\u91cf\u6587\u6863\u660e\u786e\u964d\u7ea7\u5904\u7406\u3002",
        OCR_COVERAGE_WEAK: "\u4e3a OCR \u5efa\u7acb\u9875\u7ea7\u8bc4\u4f30\uff0c\u8ba9\u4f4e\u8986\u76d6\u6216\u4f4e\u53ef\u7528\u6027 OCR \u9875\u4fdd\u6301\u7ea2\u7ebf\u6216\u8bb0\u5f55\u4e3a\u90e8\u5206\u6210\u529f\u3002",
        OCR_HEADING_NOISE: "\u5728 OCR \u540e reviewer \u4e2d\u5355\u72ec\u68c0\u67e5\u6807\u9898\u566a\u97f3\uff0c\u907f\u514d\u4ec5\u56e0\u6570\u91cf\u589e\u957f\u5c31\u7ed9\u9ad8\u5206\u3002",
        OCR_PARAMETER_POLLUTION: "\u5728 parser \u7684\u53c2\u6570\u62bd\u53d6\u9636\u6bb5\u8fc7\u6ee4\u65e5\u671f\u3001\u6807\u51c6\u53f7\u3001\u5206\u7c7b\u53f7\u7b49 OCR \u5e38\u89c1\u6c61\u67d3\u9879\u3002",
        STRUCTURE_MISSING: "\u9875\u9762\u5df2\u6709\u6587\u672c\u65f6\u5148\u5efa block\uff0c\u518d\u7531 block \u5efa section\u3002",
        STANDARD_ENTITY_MISSING: "\u4ece\u9875\u9762\u6587\u672c\u548c\u8868\u683c\u76f4\u63a5\u626b\u63cf\u6807\u51c6\u53f7\uff0c\u4e0d\u8981\u53ea\u4f9d\u8d56\u7ae0\u8282\u6b63\u6587\u3002",
        TABLE_NOT_CONSUMED: "\u8868\u683c\u62bd\u53d6\u540e\u5fc5\u987b\u8fdb\u5165\u53c2\u6570\u4e8b\u5b9e\u6216\u7ed3\u6784\u5316\u4e8b\u5b9e\u5c42\u3002",
        STRUCTURED_BACKBONE_MISSING: "\u5728\u7ed3\u6784\u4fee\u6b63\u540e\u91cd\u65b0\u5237\u65b0 parsed_view/facts\uff0c\u4fdd\u8bc1\u4e0b\u6e38\u6d88\u8d39\u7684\u662f\u540c\u4e00\u4efd\u4e3b\u7ebf\u3002",
        SUMMARY_TEMPLATE_FALLBACK: "\u5f53 LLM \u540e\u7aef\u4e0d\u53ef\u7528\u65f6\uff0csummary \u9700\u660e\u786e\u964d\u7ea7\u4e3a\u4f4e\u8d28\u91cf\u4ea7\u7269\uff0c\u4e0d\u80fd\u628a fallback \u6a21\u677f\u5f53\u6210\u5408\u683c\u6458\u8981\u3002",
    }
    return mapping.get(problem, "\u7ee7\u7eed\u6536\u7d27\u5bf9\u5e94\u6a21\u5757\u7684\u7ed3\u6784\u5316\u548c\u5f52\u4e00\u5316\u903b\u8f91\u3002")


def _is_suspicious_ocr_heading(text: str) -> bool:
    normalized = normalize_line(text.lstrip("#").strip())
    if not normalized:
        return False
    if re.match(r"^\d+(?:\.\d+)*\s+[\u4e00-\u9fffA-Za-z][^。；;]{0,24}$", normalized):
        return False
    if SUSPICIOUS_OCR_HEADING_RE.fullmatch(text):
        return True
    if re.match(r"^\d{2,}(?:[.,]\d+)?\s+\S+", normalized):
        return True
    compact = normalized.replace(" ", "")
    if len(normalized) <= 24 and sum(char.isdigit() for char in normalized) >= 3 and not re.search(r"^\d+(?:\.\d+)*\s+\S+", normalized):
        return True
    if len(compact) >= 14 and sum(char.isdigit() for char in compact) >= 4 and normalized.count(" ") <= 1:
        return True
    if normalized.endswith(("。", "；", ";")) and not re.match(r"^\d+(?:\.\d+)*\s+", normalized):
        return True
    return False


def _find_suspicious_parameters(document: DocumentData) -> list[str]:
    suspicious: list[str] = []
    seen: set[str] = set()
    for item in get_parameter_entries(document):
        name = normalize_line(str(item.get("参数名称", "")))
        value = normalize_line(str(item.get("参数值文本", "")))
        source_item = normalize_line(str(item.get("来源子项", "")))
        merged = " ".join(part for part in (name, value, source_item) if part)
        if not merged:
            continue
        if merged in seen:
            continue
        if METADATA_PARAM_RE.search(merged) or FRONT_MATTER_PARAM_RE.search(merged) or FRONT_MATTER_VALUE_RE.search(merged) or DATE_LIKE_RE.search(merged):
            suspicious.append(merged)
            seen.add(merged)
            continue
        if STANDARD_CODE_RE.search(name) or STANDARD_CODE_RE.search(value):
            suspicious.append(merged)
            seen.add(merged)
    return suspicious


def _find_sentence_like_tags(tags: dict[str, Any]) -> list[str]:
    suspicious: list[str] = []
    seen: set[str] = set()
    for key, values in tags.items():
        if str(key).startswith("_") or not isinstance(values, list):
            continue
        for value in values:
            normalized = normalize_line(str(value))
            if not normalized or normalized in seen:
                continue
            token_count = len(normalized.replace("/", " ").split())
            has_sentence_punctuation = bool(LONG_SENTENCE_TAG_RE.search(normalized))
            has_unit_phrase = bool(re.search(r"\b(?:MPa|bar|psi|mm|cm|m|kg|℃|°C)\b", normalized, re.IGNORECASE))
            if len(normalized) >= 18 and (has_sentence_punctuation or token_count >= 4 or has_unit_phrase):
                suspicious.append(normalized)
                seen.add(normalized)
    return suspicious


def _looks_like_template_summary(text: str) -> bool:
    normalized = normalize_line(text)
    if not normalized:
        return True
    if re.search(r"已建立\s*\d+|已抽取\s*\d+|已识别\s*\d+", normalized):
        return False
    if TEMPLATE_SUMMARY_RE.search(normalized):
        return True
    if "OCR" in normalized and len(normalized) <= 80:
        return True
    return False


def _is_suspicious_parameter_tag(text: str) -> bool:
    normalized = normalize_line(text)
    if not normalized:
        return False
    if SUSPICIOUS_PARAM_TAG_RE.search(normalized):
        return True
    tokens = normalized.replace("/", " ").replace("-", " ").split()
    if any(token.lower() in {"for", "and", "und", "mit"} for token in tokens) and len(tokens) >= 4:
        return True
    return False
