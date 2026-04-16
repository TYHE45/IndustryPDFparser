from __future__ import annotations

import re
from collections import Counter
from typing import Any

from src.models import DocumentData
from src.record_access import metadata_title
from src.structured_access import get_parameter_entries, get_product_entries, get_standard_entries
from src.utils import normalize_line

STANDARD_CODE_RE = re.compile(r"\b(?:DIN|EN|ISO|SN|SEW|DVS|AD|TRbF)(?:\s+[A-Z]+)?\s*[0-9][0-9A-Za-z./\-]*\b")
SYNTHETIC_TABLE_TITLE_RE = re.compile(r"^#+\s+\u7b2c\d+\u9875\u8868\d+$")
SHORT_HEADING_RE = re.compile(r"^#+\s+[A-Z]{1,3}$")
SENTENCE_HEADING_RE = re.compile(r"^#+\s+.*[.;]$")
SUSPICIOUS_PARAM_TAG_RE = re.compile(r"(?:\d+[.)/]?\s*){2,}|(?:\b[a-z]{1,3}\b\s*){2,}", re.IGNORECASE)

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
STRUCTURE_MISSING = "\u7ed3\u6784\u672a\u5efa\u7acb"
TABLE_NOT_CONSUMED = "\u8868\u683c\u672a\u6d88\u8d39"
STANDARD_ENTITY_MISSING = "\u6807\u51c6\u5b9e\u4f53\u7f3a\u5931"
STRUCTURED_BACKBONE_MISSING = "\u7ed3\u6784\u4e3b\u7ebf\u7f3a\u5931"


def review_outputs(document: DocumentData, markdown: str, summary: dict[str, Any], tags: dict[str, Any]) -> dict[str, Any]:
    markdown_review = _review_markdown(document, markdown)
    summary_review = _review_summary(document, summary)
    tag_review = _review_tags(document, tags)
    source_review = _review_sources(document)

    problems = _build_problem_list(markdown_review, summary_review, tag_review, source_review)
    redlines = _detect_redlines(markdown_review, source_review)

    markdown_score = max(0.0, 25.0 - 5.0 * len(markdown_review[KEY_ISSUES]))
    summary_score = max(0.0, 35.0 - 4.0 * len(summary_review[KEY_ISSUES]))
    tag_score = max(0.0, 15.0 - 2.0 * len(tag_review[KEY_ISSUES]))
    source_score = max(0.0, 25.0 - 5.0 * len(source_review[KEY_ISSUES]))

    base_quality = round(markdown_score + min(10.0, tag_score), 2)
    factual_quality = round(min(20.0, summary_score * 0.6) + min(20.0, source_score * 0.8), 2)
    consistency_quality = round(min(20.0, summary_score * 0.4) + min(5.0, tag_score * 0.4), 2)

    total = round(base_quality + factual_quality + consistency_quality, 2)
    if redlines:
        total = min(total, min(item[KEY_CAP] for item in redlines))

    severity_counter = Counter(item[KEY_LEVEL] for item in problems)
    is_pass = total >= 85.0 and not redlines
    return {
        BASE_SCORE_KEY: base_quality,
        FACTUAL_SCORE_KEY: factual_quality,
        CONSISTENCY_SCORE_KEY: consistency_quality,
        TOTAL_SCORE_KEY: total,
        REDLINE_TRIGGERED_KEY: bool(redlines),
        REDLINE_LIST_KEY: redlines,
        FINAL_PASS_KEY: is_pass,
        PROBLEM_STATS_KEY: {
            "\u0053\u7ea7\u95ee\u9898\u6570": float(severity_counter.get("S", 0)),
            "\u0041\u7ea7\u95ee\u9898\u6570": float(severity_counter.get("A", 0)),
            "\u0042\u7ea7\u95ee\u9898\u6570": float(severity_counter.get("B", 0)),
        },
        SUBSCORES_KEY: {
            "markdown\u7ed3\u6784\u6e05\u6d01\u5ea6": markdown_score,
            "summary\u7ed3\u6784\u89c4\u8303\u5ea6": summary_score,
            "tags\u6e05\u6d01\u5ea6": tag_score,
            "\u6765\u6e90\u8d28\u91cf": source_score,
        },
        PROBLEMS_KEY: problems,
        MARKDOWN_REVIEW_KEY: markdown_review,
        SUMMARY_STRUCTURE_REVIEW_KEY: summary_review,
        SUMMARY_FACT_REVIEW_KEY: summary_review,
        TAG_REVIEW_KEY: tag_review,
        CONSISTENCY_REVIEW_KEY: {"\u7ae0\u8282\u5f15\u7528\u4e0d\u4e00\u81f4": [], "\u6807\u7b7e\u6765\u6e90\u4e0d\u4e00\u81f4": []},
        SOURCE_REVIEW_KEY: source_review,
        TYPE_REVIEW_KEY: {},
        DOC_TYPE_KEY: document.profile.doc_type if document.profile else "unknown",
        TOTAL_KEY: total,
        PASS_KEY: is_pass,
        MUST_FIX_KEY: [item[KEY_REDLINE_NAME] for item in redlines] or [item[KEY_TYPE] for item in problems if item[KEY_LEVEL] == "S"],
    }


def _review_markdown(document: DocumentData, markdown: str) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    headings = [line.strip() for line in markdown.splitlines() if line.lstrip().startswith("#")]
    content_lines = [line for line in markdown.splitlines() if line.strip() and not line.lstrip().startswith("#")]

    pseudo_titles = [item for item in headings if SHORT_HEADING_RE.fullmatch(item) or SENTENCE_HEADING_RE.fullmatch(item)]
    auto_table_titles = [item for item in headings if SYNTHETIC_TABLE_TITLE_RE.fullmatch(item)]

    if len(document.sections) == 0:
        issues.append({KEY_CONTENT: DOC_CHAIN_MISSING, KEY_REASON: "\u672a\u80fd\u5efa\u7acb\u7a33\u5b9a\u7684\u7ae0\u8282\u7ed3\u6784\uff0cmarkdown \u53ea\u6709\u5143\u6570\u636e\u6216\u6781\u5c11\u6b63\u6587\u3002"})
    if len(headings) <= 2 or len(content_lines) <= 3:
        issues.append({KEY_CONTENT: MARKDOWN_TOO_SHORT, KEY_REASON: "\u5f53\u524d\u8f93\u51fa\u7f3a\u5c11\u8db3\u591f\u7684\u7ed3\u6784\u5316\u6b63\u6587\u5185\u5bb9\u3002"})
    if document.tables and not any(line.startswith("| ") for line in markdown.splitlines()):
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


def _review_summary(document: DocumentData, summary: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    chapter_items = summary.get("\u7ae0\u8282\u6458\u8981", [])
    param_summary = summary.get("\u53c2\u6570\u6458\u8981", {}) if isinstance(summary.get("\u53c2\u6570\u6458\u8981"), dict) else {}
    numeric_items = param_summary.get("\u6570\u503c\u578b\u53c2\u6570", [])
    parameter_entries = get_parameter_entries(document)

    if document.sections and not chapter_items:
        issues.append({KEY_CONTENT: CHAPTER_SUMMARY_EMPTY, KEY_REASON: "\u5df2\u7ecf\u62bd\u53d6\u51fa\u7ae0\u8282\uff0c\u4f46\u6458\u8981\u6ca1\u6709\u8986\u76d6\u8fd9\u4e9b\u7ae0\u8282\u3002"})
    if document.tables and not parameter_entries:
        issues.append({KEY_CONTENT: TABLE_NOT_TO_PARAM, KEY_REASON: "\u8868\u683c\u5df2\u7ecf\u62bd\u53d6\uff0c\u4f46\u6ca1\u6709\u5efa\u7acb\u53c2\u6570\u4e8b\u5b9e\u3002"})
    if parameter_entries and not numeric_items:
        issues.append({KEY_CONTENT: PARAM_SUMMARY_EMPTY, KEY_REASON: "\u5df2\u7ecf\u5efa\u7acb\u53c2\u6570\u4e8b\u5b9e\uff0c\u4f46 summary \u6ca1\u6709\u6d88\u8d39\u8fd9\u4e9b\u53c2\u6570\u3002"})
    if document.profile and document.profile.needs_ocr and document.profile.text_line_count == 0:
        issues.append({KEY_CONTENT: SCAN_LIKE, KEY_REASON: "\u6587\u672c\u5c42\u8fc7\u5f31\uff0c\u5f53\u524d\u7ed3\u679c\u9700\u8981 OCR \u515c\u5e95\u3002"})

    return {
        KEY_ISSUES: issues,
        ILLEGAL_SECTION_NAMES: [],
        INTERNAL_CODES: [],
        EMPTY_CHAPTER_SUMMARIES: [],
        TABLE_RULE_ERRORS: [],
        PARAM_MULTI_VALUE_ERRORS: [],
        MISSING_MAIN_COVERAGE: [],
        LOW_PARAMETER_COVERAGE: issues[:1] if document.tables and not parameter_entries else [],
    }


def _review_tags(document: DocumentData, tags: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    parameter_entries = get_parameter_entries(document)
    standard_entries = get_standard_entries(document)
    product_entries = get_product_entries(document)
    parameter_tags = tags.get("\u53c2\u6570\u6807\u7b7e", []) or []
    noisy_parameter_tags = [normalize_line(str(item)) for item in parameter_tags if _is_suspicious_parameter_tag(str(item))]

    if standard_entries and not tags.get("\u6807\u51c6\u5f15\u7528\u6807\u7b7e"):
        issues.append({KEY_CONTENT: STANDARD_TAG_EMPTY, KEY_REASON: "\u5df2\u7ecf\u8bc6\u522b\u5230\u6807\u51c6\u5b9e\u4f53\uff0c\u4f46\u6807\u7b7e\u4e2d\u6ca1\u6709\u4f53\u73b0\u6807\u51c6\u65cf\u3002"})
    if parameter_entries and not tags.get("\u53c2\u6570\u6807\u7b7e"):
        issues.append({KEY_CONTENT: PARAM_TAG_EMPTY, KEY_REASON: "\u5df2\u7ecf\u5efa\u7acb\u53c2\u6570\u4e8b\u5b9e\uff0c\u4f46\u6807\u7b7e\u6ca1\u6709\u5b8c\u6210\u6536\u53e3\u3002"})
    if product_entries and not tags.get("\u4ea7\u54c1\u578b\u53f7\u6807\u7b7e"):
        issues.append({KEY_CONTENT: PRODUCT_MODEL_TAG_EMPTY, KEY_REASON: "\u5df2\u7ecf\u5efa\u7acb\u4ea7\u54c1\u5b9e\u4f53\uff0c\u4f46\u6807\u7b7e\u6ca1\u6709\u4f53\u73b0\u578b\u53f7\u3002"})
    if noisy_parameter_tags:
        issues.append({KEY_CONTENT: NOISY_PARAMETER_TAGS, KEY_REASON: "\u53c2\u6570\u6807\u7b7e\u4e2d\u4ecd\u7136\u6df7\u5165\u4e86\u8868\u5934\u788e\u7247\u3001\u7ef4\u5ea6\u4ee3\u53f7\u6216\u53e5\u5b50\u6b8b\u7247\u3002"})

    return {
        KEY_ISSUES: issues,
        NOISY_TAGS: [{KEY_CONTENT: item, KEY_REASON: "\u4f4e\u4fe1\u53f7\u53c2\u6570\u6807\u7b7e\uff0c\u66f4\u50cf\u8868\u5934\u6216\u7ef4\u5ea6\u4ee3\u53f7\u3002"} for item in noisy_parameter_tags[:20]],
        MISCLASSIFIED_TAGS: [],
        MISSING_CRITICAL_TAGS: issues,
    }


def _review_sources(document: DocumentData) -> dict[str, list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    title = normalize_line(metadata_title(document.metadata))
    parameter_entries = get_parameter_entries(document)
    standard_entries = get_standard_entries(document)
    raw_text = "\n".join(" ".join(page.get("lines", [])) for page in document.raw_pages)

    if document.profile and document.profile.needs_ocr and document.profile.text_line_count == 0:
        issues.append({KEY_CONTENT: SCAN_LIKE, KEY_REASON: f"\u300a{title}\u300b\u6587\u672c\u5c42\u51e0\u4e4e\u4e3a\u7a7a\uff0c\u5f53\u524d\u6d41\u7a0b\u9700\u8981 OCR \u515c\u5e95\u3002"})
    if document.profile and document.profile.text_line_count > 0 and not document.sections and not document.tables:
        issues.append({KEY_CONTENT: STRUCTURE_MISSING, KEY_REASON: "\u9875\u9762\u5df2\u6709\u6587\u672c\uff0c\u4f46\u6ca1\u6709\u5efa\u7acb section \u6216 table \u7ed3\u6784\u3002"})
    if document.tables and not parameter_entries:
        issues.append({KEY_CONTENT: TABLE_NOT_CONSUMED, KEY_REASON: "\u8868\u683c\u5b58\u5728\uff0c\u4f46\u6ca1\u6709\u4ea7\u51fa\u53c2\u6570\u4e8b\u5b9e\u3002"})
    if not standard_entries and STANDARD_CODE_RE.search(raw_text):
        issues.append({KEY_CONTENT: STANDARD_ENTITY_MISSING, KEY_REASON: "\u6587\u6863\u770b\u8d77\u6765\u5305\u542b\u6807\u51c6\u53f7\uff0c\u4f46\u7ed3\u6784\u5316\u7ed3\u679c\u91cc\u6ca1\u6709\u5bf9\u5e94\u6807\u51c6\u5b9e\u4f53\u3002"})
    if document.profile and document.profile.text_line_count > 0 and getattr(document, "parsed_view", None) is None:
        issues.append({KEY_CONTENT: STRUCTURED_BACKBONE_MISSING, KEY_REASON: "\u6587\u6863\u5df2\u7ecf\u6709\u6587\u672c\u5c42\uff0c\u4f46\u4fee\u6b63\u540e\u7684\u7ed3\u6784\u5316\u4e3b\u7ebf\u6ca1\u6709\u6210\u529f\u91cd\u5efa\u3002"})

    return {
        KEY_ISSUES: issues,
        ABNORMAL_PARAM_SOURCES: issues if document.tables and not parameter_entries else [],
        ABNORMAL_RULE_SOURCES: [],
    }


def _detect_redlines(
    markdown_review: dict[str, list[dict[str, str]]],
    source_review: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    redlines: list[dict[str, Any]] = []
    if any(item[KEY_CONTENT] == DOC_CHAIN_MISSING for item in markdown_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: "\u539f\u6587\u89e3\u6790\u672a\u5efa\u7acb\u6b63\u6587\u4e3b\u94fe", KEY_REASON: "markdown \u4e2d\u51e0\u4e4e\u53ea\u6709\u5143\u6570\u636e\uff0c\u8bf4\u660e\u6b63\u6587\u7ae0\u8282\u94fe\u6ca1\u6709\u771f\u6b63\u5efa\u7acb\u3002", KEY_CAP: 69.99})
    if any(item[KEY_CONTENT] == TABLE_NOT_CONSUMED for item in source_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: "\u8868\u683c\u5b58\u5728\u4f46\u53c2\u6570\u672a\u5efa\u7acb", KEY_REASON: "\u8868\u683c\u5df2\u62bd\u53d6\uff0c\u4f46\u6ca1\u6709\u8f6c\u6210\u53c2\u6570\u4e8b\u5b9e\u3002", KEY_CAP: 79.99})
    if any(item[KEY_CONTENT] == SCAN_LIKE for item in source_review[KEY_ISSUES]):
        redlines.append({KEY_REDLINE_NAME: "\u6587\u672c\u5c42\u4e0d\u8db3\u9700\u8981OCR", KEY_REASON: "\u9875\u9762\u6587\u672c\u5c42\u6781\u5f31\uff0c\u5f53\u524d\u7ed3\u679c\u4e0d\u8db3\u4ee5\u652f\u6491\u7a33\u5b9a\u62bd\u53d6\u3002", KEY_CAP: 74.99})
    return redlines


def _build_problem_list(
    markdown_review: dict[str, list[dict[str, str]]],
    summary_review: dict[str, list[dict[str, str]]],
    tag_review: dict[str, list[dict[str, str]]],
    source_review: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    mapping = [
        ("S", "\u539f\u6587\u89e3\u6790.md", "\u7ed3\u6784\u7f3a\u5931", markdown_review[KEY_ISSUES]),
        ("A", "summary.json", "\u6458\u8981\u7f3a\u5931", summary_review[KEY_ISSUES]),
        ("B", "tags.json", "\u6807\u7b7e\u7f3a\u5931", tag_review[KEY_ISSUES]),
        ("S", "\u7ed3\u6784\u5316\u7ed3\u679c", "\u6765\u6e90\u5f02\u5e38", source_review[KEY_ISSUES]),
    ]
    problems: list[dict[str, str]] = []
    for level, target, problem_type, items in mapping:
        for item in items:
            problems.append({KEY_LEVEL: level, KEY_TARGET: target, KEY_TYPE: problem_type, KEY_POSITION: item[KEY_CONTENT], KEY_CONTENT: item[KEY_CONTENT], KEY_REASON: item[KEY_REASON], KEY_FIX: _suggest_fix(item[KEY_CONTENT])})
    return problems


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
        SCAN_LIKE: "\u5728 intake \u9636\u6bb5\u589e\u52a0 OCR gating\uff0c\u4f4e\u6587\u672c\u91cf\u6587\u6863\u660e\u786e\u964d\u7ea7\u5904\u7406\u3002",
        STRUCTURE_MISSING: "\u9875\u9762\u5df2\u6709\u6587\u672c\u65f6\u5148\u5efa block\uff0c\u518d\u7531 block \u5efa section\u3002",
        STANDARD_ENTITY_MISSING: "\u4ece\u9875\u9762\u6587\u672c\u548c\u8868\u683c\u76f4\u63a5\u626b\u63cf\u6807\u51c6\u53f7\uff0c\u4e0d\u8981\u53ea\u4f9d\u8d56\u7ae0\u8282\u6b63\u6587\u3002",
        TABLE_NOT_CONSUMED: "\u8868\u683c\u62bd\u53d6\u540e\u5fc5\u987b\u8fdb\u5165\u53c2\u6570\u4e8b\u5b9e\u6216\u7ed3\u6784\u5316\u4e8b\u5b9e\u5c42\u3002",
        STRUCTURED_BACKBONE_MISSING: "\u5728\u7ed3\u6784\u4fee\u6b63\u540e\u91cd\u65b0\u5237\u65b0 parsed_view/facts\uff0c\u4fdd\u8bc1\u4e0b\u6e38\u6d88\u8d39\u7684\u662f\u540c\u4e00\u4efd\u4e3b\u7ebf\u3002",
    }
    return mapping.get(problem, "\u7ee7\u7eed\u6536\u7d27\u5bf9\u5e94\u6a21\u5757\u7684\u7ed3\u6784\u5316\u548c\u5f52\u4e00\u5316\u903b\u8f91\u3002")


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
