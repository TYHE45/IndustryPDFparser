from __future__ import annotations

from typing import Any

from config import AppConfig
from src.models import DocumentData
from src.openai_compat import llm_available, request_structured_json
from src.record_access import metadata_dict, section_values, table_dict
from src.structured_access import (
    get_parameter_entries,
    get_product_entries,
    get_profile_dict,
    get_rule_entries,
    get_standard_entries,
)
from src.utils import normalize_line

FULL_SUMMARY = "\u5168\u6587\u6458\u8981"
CHAPTER_SUMMARY = "\u7ae0\u8282\u6458\u8981"
PARAM_SUMMARY = "\u53c2\u6570\u6458\u8981"
NUMERIC_PARAMS = "\u6570\u503c\u578b\u53c2\u6570"
RULE_PARAMS = "\u89c4\u5219\u578b\u53c2\u6570"
REQUIREMENT_SUMMARY = "\u8981\u6c42\u6458\u8981"
STANDARD_SUMMARY = "\u5f15\u7528\u6807\u51c6\u6458\u8981"
PROFILE_KEY = "\u6587\u6863\u753b\u50cf"
PRODUCT_SUMMARY = "\u4ea7\u54c1\u6458\u8981"
CHAPTER_TITLE = "\u7ae0\u8282\u6807\u9898"
SUMMARY_TEXT = "\u6458\u8981"
PARAM_NAME = "\u53c2\u6570\u540d\u79f0"
PARAM_OVERVIEW = "\u53c2\u6570\u6982\u8ff0"
PARAM_VALUE = "\u53c2\u6570\u503c\u6216\u8303\u56f4"
UNIT = "\u5355\u4f4d"
CONDITION = "\u9002\u7528\u6761\u4ef6"
SECTION_NAME = "\u6240\u5c5e\u7ae0\u8282"
SOURCE_TABLE = "\u6765\u6e90\u8868\u683c"
SOURCE_ITEM = "\u6765\u6e90\u5b50\u9879"
RULE_OVERVIEW = "\u89c4\u5219\u6982\u8ff0"
REQUIREMENT_TYPE = "\u8981\u6c42\u7c7b\u578b"
CONTENT = "\u5185\u5bb9"
STANDARD_CODE = "\u6807\u51c6\u7f16\u53f7"
STANDARD_OVERVIEW = "\u6807\u51c6\u6982\u8ff0"
PRODUCT_NAME = "\u4ea7\u54c1\u540d\u79f0"
MODEL = "\u578b\u53f7"
PRODUCT_OVERVIEW = "\u4ea7\u54c1\u6982\u8ff0"
FILE_TITLE = "\u6587\u6863\u6807\u9898"
FILE_NAME = "\u6587\u4ef6\u540d\u79f0"
DOC_TYPE = "\u6587\u6863\u7c7b\u578b"
UNSPECIFIED = "\u672a\u6ce8\u660e"
RULE_REQUIREMENT = "\u89c4\u5219\u8981\u6c42"
CHAPTER_NOTE = "\u7ae0\u8282\u8bf4\u660e"
TECH_DOC = "\u6280\u672f\u8d44\u6599"


def build_summary(document: DocumentData, config: AppConfig) -> dict[str, Any]:
    if not config.use_llm:
        result = _build_fallback(document)
        result["_llm_reason"] = "配置关闭LLM摘要生成"
        return result
    if not llm_available():
        result = _build_fallback(document)
        result["_llm_reason"] = "LLM不可用：缺少可用的 OpenAI SDK 或 OPENAI_API_KEY"
        return result
    if not _should_use_llm(document):
        result = _build_fallback(document)
        result["_llm_reason"] = "结构化原料不足，跳过LLM摘要生成"
        return result

    try:
        result, backend = _build_with_llm(document, config)
        result["_llm_backend"] = backend
        return result
    except Exception as exc:
        result = _build_fallback(document)
        result["_llm_error"] = str(exc)
        result["_llm_reason"] = "LLM摘要生成失败，已回退到规则摘要"
        return result


def _build_with_llm(document: DocumentData, config: AppConfig) -> tuple[dict[str, Any], str]:
    payload = {
        "\u6587\u4ef6\u57fa\u7840\u4fe1\u606f": metadata_dict(document.metadata),
        PROFILE_KEY: get_profile_dict(document),
        "\u7ae0\u8282\u539f\u6599": _build_chapter_summary(document)[:12],
        "\u53c2\u6570\u539f\u6599": _build_numeric_summary(document)[:24],
        "\u89c4\u5219\u539f\u6599": _build_rule_summary(document)[:16],
        "\u6807\u51c6\u539f\u6599": _build_standard_summary(document)[:20],
        "\u8868\u683c\u539f\u6599": [table_dict(table) for table in document.tables[:4]],
    }
    schema = {
        "type": "object",
        "properties": {
            FULL_SUMMARY: {"type": "string"},
            CHAPTER_SUMMARY: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        CHAPTER_TITLE: {"type": "string"},
                        SUMMARY_TEXT: {"type": "string"},
                    },
                    "required": [CHAPTER_TITLE, SUMMARY_TEXT],
                    "additionalProperties": False,
                },
            },
            PARAM_SUMMARY: {
                "type": "object",
                "properties": {
                    NUMERIC_PARAMS: {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                PARAM_NAME: {"type": "string"},
                                PARAM_OVERVIEW: {"type": "string"},
                                PARAM_VALUE: {"type": "string"},
                                UNIT: {"type": "string"},
                                CONDITION: {"type": "string"},
                                SECTION_NAME: {"type": "string"},
                                SOURCE_TABLE: {"type": "string"},
                                SOURCE_ITEM: {"type": "string"},
                            },
                            "required": [PARAM_NAME, PARAM_OVERVIEW, PARAM_VALUE, UNIT, CONDITION, SECTION_NAME, SOURCE_TABLE, SOURCE_ITEM],
                            "additionalProperties": False,
                        },
                    },
                    RULE_PARAMS: {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                PARAM_NAME: {"type": "string"},
                                RULE_OVERVIEW: {"type": "string"},
                                CONDITION: {"type": "string"},
                                SECTION_NAME: {"type": "string"},
                            },
                            "required": [PARAM_NAME, RULE_OVERVIEW, CONDITION, SECTION_NAME],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [NUMERIC_PARAMS, RULE_PARAMS],
                "additionalProperties": False,
            },
            REQUIREMENT_SUMMARY: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        REQUIREMENT_TYPE: {"type": "string"},
                        CONTENT: {"type": "string"},
                        CONDITION: {"type": "string"},
                        SECTION_NAME: {"type": "string"},
                    },
                    "required": [REQUIREMENT_TYPE, CONTENT, CONDITION, SECTION_NAME],
                    "additionalProperties": False,
                },
            },
            STANDARD_SUMMARY: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        STANDARD_CODE: {"type": "string"},
                        STANDARD_OVERVIEW: {"type": "string"},
                        SECTION_NAME: {"type": "string"},
                    },
                    "required": [STANDARD_CODE, STANDARD_OVERVIEW, SECTION_NAME],
                    "additionalProperties": False,
                },
            },
        },
        "required": [FULL_SUMMARY, CHAPTER_SUMMARY, PARAM_SUMMARY, REQUIREMENT_SUMMARY, STANDARD_SUMMARY],
        "additionalProperties": False,
    }
    result, backend = request_structured_json(
        model=config.openai_model,
        system_prompt=(
            "\u4f60\u662f\u901a\u7528\u6280\u672f PDF \u6570\u636e\u6574\u7406\u52a9\u624b\u3002"
            "\u8bf7\u57fa\u4e8e\u7ed9\u5b9a\u7684\u7ed3\u6784\u5316\u539f\u6599\u751f\u6210\u4e2d\u6587\u6458\u8981\uff0c\u4e0d\u8981\u7f16\u9020\u539f\u6587\u4e2d\u4e0d\u5b58\u5728\u7684\u4fe1\u606f\uff0c"
            "\u4f18\u5148\u4fdd\u7559\u7ae0\u8282\u3001\u53c2\u6570\u3001\u89c4\u5219\u548c\u6807\u51c6\u4e4b\u95f4\u7684\u5bf9\u5e94\u5173\u7cfb\u3002"
        ),
        user_payload=payload,
        schema_name="report_summary",
        schema=schema,
    )
    result.setdefault(PROFILE_KEY, get_profile_dict(document))
    if document.profile and document.profile.doc_type == "product_catalog":
        result.setdefault(PRODUCT_SUMMARY, _build_product_summary(document))
    return result, backend


def _build_fallback(document: DocumentData) -> dict[str, Any]:
    chapter_items = _build_chapter_summary(document)
    numeric_items = _build_numeric_summary(document)
    rule_items = _build_rule_summary(document)
    standard_items = _build_standard_summary(document)
    profile = document.profile

    result: dict[str, Any] = {
        FULL_SUMMARY: _build_full_summary(document, chapter_items, numeric_items, standard_items),
        CHAPTER_SUMMARY: chapter_items,
        PARAM_SUMMARY: {
            NUMERIC_PARAMS: numeric_items,
            RULE_PARAMS: rule_items,
        },
        REQUIREMENT_SUMMARY: _build_requirement_summary(document),
        STANDARD_SUMMARY: standard_items,
        PROFILE_KEY: get_profile_dict(document),
    }
    if profile and profile.doc_type == "product_catalog":
        result[PRODUCT_SUMMARY] = _build_product_summary(document)
    return result


def _build_full_summary(
    document: DocumentData,
    chapter_items: list[dict[str, str]],
    numeric_items: list[dict[str, str]],
    standard_items: list[dict[str, str]],
) -> str:
    profile = document.profile
    meta = metadata_dict(document.metadata)
    title = meta[FILE_TITLE] or meta[FILE_NAME]
    doc_type = meta[DOC_TYPE] or TECH_DOC

    if profile and profile.needs_ocr and profile.text_line_count == 0:
        return f"\u300a{title}\u300b\u6587\u672c\u5c42\u6781\u5f31\uff0c\u5f53\u524d\u66f4\u50cf\u626b\u63cf\u4ef6\u6216\u56fe\u7247\u578b PDF\uff0c\u5efa\u8bae\u5148\u8fdb\u884c OCR \u540e\u518d\u505a\u7a33\u5b9a\u62bd\u53d6\u3002"

    parts = [f"\u300a{title}\u300b\u5f53\u524d\u8bc6\u522b\u4e3a{doc_type}\u3002"]
    if chapter_items:
        parts.append(f"\u5df2\u5efa\u7acb {len(chapter_items)} \u4e2a\u6b63\u6587\u7ae0\u8282\u6458\u8981\u3002")
    elif document.tables:
        parts.append(f"\u5f53\u524d\u5c1a\u672a\u7a33\u5b9a\u5efa\u7acb\u7ae0\u8282\u94fe\uff0c\u4f46\u5df2\u62bd\u53d6 {len(document.tables)} \u5f20\u8868\u683c\u3002")

    if numeric_items:
        parts.append(f"\u5df2\u62bd\u53d6 {len(numeric_items)} \u6761\u6570\u503c\u578b\u53c2\u6570\u3002")
    if standard_items:
        parts.append(f"\u5df2\u8bc6\u522b {len(standard_items)} \u6761\u5f15\u7528\u6807\u51c6\u3002")
    if profile and profile.needs_ocr:
        parts.append("\u6587\u6863\u6587\u672c\u5c42\u504f\u5f31\uff0c\u540e\u7eed\u7ed3\u679c\u9700\u8981\u5173\u6ce8 OCR \u8865\u5f3a\u3002")
    return "".join(parts)


def _build_chapter_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for section in document.sections[:60]:
        number, title, _, _, body, _ = section_values(section)
        body_text = _clip(body, 220)
        if not body_text and title:
            body_text = f"\u5f53\u524d\u4ec5\u7a33\u5b9a\u8bc6\u522b\u5230\u6807\u9898\u201c{normalize_line(title)}\u201d\uff0c\u6b63\u6587\u4ecd\u7136\u8f83\u5c11\u3002"
        heading = title if str(number).startswith("U") else f"{number} {title}".strip()
        items.append({CHAPTER_TITLE: normalize_line(heading), SUMMARY_TEXT: body_text})
    return items


def _build_numeric_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for param in get_parameter_entries(document)[:120]:
        name = param["name"]
        value_text = param["value_text"]
        unit = param["unit"]
        lower = param["value_min"]
        upper = param["value_max"]
        comparator = param["comparator"]
        condition = param["condition"]
        section_name = param["section_name"]
        source_table = param["source_table"]
        source_item = param["source_item"]
        key = (normalize_line(name), normalize_line(value_text), normalize_line(condition))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                PARAM_NAME: normalize_line(name),
                PARAM_OVERVIEW: _parameter_overview(name, value_text, condition),
                PARAM_VALUE: _value_display(value_text, lower, upper, comparator),
                UNIT: normalize_line(unit) or UNSPECIFIED,
                CONDITION: normalize_line(condition),
                SECTION_NAME: normalize_line(section_name),
                SOURCE_TABLE: normalize_line(source_table),
                SOURCE_ITEM: normalize_line(source_item),
            }
        )
    return items


def _build_rule_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in get_rule_entries(document)[:100]:
        rule_type = rule["rule_type"]
        content = rule["content"]
        condition = rule.get("condition", "")
        section_name = rule["section_name"]
        key = (normalize_line(rule_type), normalize_line(content), normalize_line(section_name))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                PARAM_NAME: normalize_line(rule_type) or RULE_REQUIREMENT,
                RULE_OVERVIEW: normalize_line(content),
                CONDITION: normalize_line(condition),
                SECTION_NAME: normalize_line(section_name),
            }
        )
    return items


def _build_requirement_summary(document: DocumentData) -> list[dict[str, str]]:
    items = [
        {
            REQUIREMENT_TYPE: item[PARAM_NAME],
            CONTENT: item[RULE_OVERVIEW],
            CONDITION: item[CONDITION],
            SECTION_NAME: item[SECTION_NAME],
        }
        for item in _build_rule_summary(document)
    ]
    if items:
        return items[:60]

    fallback: list[dict[str, str]] = []
    for section in document.sections[:20]:
        number, title, _, _, body, _ = section_values(section)
        body_text = _clip(body, 180)
        if body_text:
            fallback.append(
                {
                    REQUIREMENT_TYPE: CHAPTER_NOTE,
                    CONTENT: body_text,
                    CONDITION: "",
                    SECTION_NAME: normalize_line(title if str(number).startswith("U") else f"{number} {title}".strip()),
                }
            )
    return fallback


def _build_standard_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in get_standard_entries(document)[:120]:
        code = item["code"]
        title = item["title"]
        standard_type = item["family"]
        section_name = item["section_name"]
        key = (normalize_line(code), normalize_line(section_name))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                STANDARD_CODE: normalize_line(code),
                STANDARD_OVERVIEW: normalize_line(title) or normalize_line(standard_type),
                SECTION_NAME: normalize_line(section_name),
            }
        )
    return items


def _build_product_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for product in get_product_entries(document)[:40]:
        anchor_name = product["display_name"]
        items.append(
            {
                PRODUCT_NAME: normalize_line(product["name"]) or anchor_name or normalize_line(product["series"]),
                MODEL: normalize_line(product["model"]),
                PRODUCT_OVERVIEW: anchor_name or normalize_line(product["name"]) or normalize_line(product["series"]),
            }
        )
    return items


def _parameter_overview(name: str, value_text: str, condition: str) -> str:
    name = normalize_line(name)
    value_text = normalize_line(value_text)
    condition = normalize_line(condition)
    if condition:
        return f"{name}\u5728{condition}\u6761\u4ef6\u4e0b\u53d6\u503c\u4e3a{value_text}\u3002"
    return f"{name}\u53d6\u503c\u4e3a{value_text}\u3002"


def _value_display(value_text: str, lower: str, upper: str, comparator: str) -> str:
    value_text = normalize_line(value_text)
    if value_text:
        return value_text
    lower = normalize_line(lower)
    upper = normalize_line(upper)
    comparator = normalize_line(comparator)
    if lower and upper:
        return f"{lower} ~ {upper}"
    if comparator and upper:
        return f"{comparator} {upper}"
    return lower or upper


def _clip(text: str, limit: int) -> str:
    text = normalize_line(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _has_enough_material(document: DocumentData) -> bool:
    return bool(document.sections or document.numeric_parameters or document.rules or document.standards or document.tables)


def _should_use_llm(document: DocumentData) -> bool:
    return _has_enough_material(document)
