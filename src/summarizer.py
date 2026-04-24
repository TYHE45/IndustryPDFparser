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
from src.text_localization import (
    localize_condition_text,
    localize_display_text,
    localize_source_text,
    looks_foreign_text,
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


def _summary_system_prompt() -> str:
    return (
        "\u4f60\u662f\u901a\u7528\u6280\u672f PDF \u6570\u636e\u6574\u7406\u52a9\u624b\u3002"
        "\u8bf7\u4e25\u683c\u57fa\u4e8e\u7ed9\u5b9a\u7684\u7ed3\u6784\u5316\u539f\u6599\u751f\u6210\u6458\u8981\uff0c"
        "\u4e0d\u8981\u7f16\u9020\u539f\u6587\u4e2d\u4e0d\u5b58\u5728\u7684\u4fe1\u606f\uff0c"
        "\u4f18\u5148\u4fdd\u7559\u7ae0\u8282\u3001\u53c2\u6570\u3001\u89c4\u5219\u548c\u6807\u51c6\u4e4b\u95f4\u7684\u5bf9\u5e94\u5173\u7cfb\u3002"
        "\u6240\u6709\u8f93\u51fa\u5fc5\u987b\u4ee5\u7b80\u4f53\u4e2d\u6587\u4e3a\u4e3b\u5e72\u3002"
        "\u9047\u5230\u5916\u6587\u6807\u9898\u3001\u672f\u8bed\u6216\u539f\u6587\u63cf\u8ff0\u65f6\uff0c"
        "\u5148\u7528\u4e2d\u6587\u8868\u8fbe\u5176\u542b\u4e49\uff0c\u53ea\u6709\u5728\u786e\u6709\u5fc5\u8981\u65f6\uff0c"
        "\u624d\u5141\u8bb8\u5199\u6210\u201c\u4e2d\u6587\uff08\u539f\u6587\uff1aX\uff09\u201d\u3002"
        "\u4e0d\u8981\u628a\u5927\u6bb5\u5916\u6587\u539f\u53e5\u76f4\u63a5\u5f53\u4f5c\u6458\u8981\u6b63\u6587\u8fd4\u56de\uff0c"
        "\u4e5f\u4e0d\u8981\u53ea\u8fd4\u56de\u201c\u539f\u6587\uff1aX\u201d\u4f5c\u4e3a\u4e3b\u4f53\u5185\u5bb9\u3002"
        "\u5982\u679c\u539f\u6599\u672c\u8eab\u5df2\u7ecf\u662f\u4e2d\u6587\uff0c"
        "\u4e0d\u8981\u518d\u91cd\u590d\u5305\u88c5\u4e3a\u201c\u539f\u6587\uff1a...\u201d\u6216\u201c\u4e2d\u6587\uff08\u539f\u6587\uff1a\u4e2d\u6587\uff09\u201d\u3002"
    )


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
        "\u6587\u4ef6\u57fa\u7840\u4fe1\u606f": metadata_dict(document.文件元数据),
        PROFILE_KEY: get_profile_dict(document),
        "\u7ae0\u8282\u539f\u6599": _build_chapter_summary(document)[:12],
        "\u53c2\u6570\u539f\u6599": _build_numeric_summary(document)[:24],
        "\u89c4\u5219\u539f\u6599": _build_rule_summary(document)[:16],
        "\u6807\u51c6\u539f\u6599": _build_standard_summary(document)[:20],
        "\u8868\u683c\u539f\u6599": [table_dict(table) for table in document.表格列表[:4]],
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
        system_prompt=_summary_system_prompt(),
        user_payload=payload,
        schema_name="report_summary",
        schema=schema,
    )
    result.setdefault(PROFILE_KEY, get_profile_dict(document))
    if document.文档画像 and document.文档画像.文档类型 == "product_catalog":
        result.setdefault(PRODUCT_SUMMARY, _build_product_summary(document))
    return result, backend


def _build_fallback(document: DocumentData) -> dict[str, Any]:
    chapter_items = _build_chapter_summary(document)
    numeric_items = _build_numeric_summary(document)
    rule_items = _build_rule_summary(document)
    standard_items = _build_standard_summary(document)
    profile = document.文档画像

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
    if profile and profile.文档类型 == "product_catalog":
        result[PRODUCT_SUMMARY] = _build_product_summary(document)
    return result


def _build_full_summary(
    document: DocumentData,
    chapter_items: list[dict[str, str]],
    numeric_items: list[dict[str, str]],
    standard_items: list[dict[str, str]],
) -> str:
    profile = document.文档画像
    meta = metadata_dict(document.文件元数据)
    title = meta[FILE_TITLE] or meta[FILE_NAME]
    doc_type = meta[DOC_TYPE] or TECH_DOC

    if profile and profile.是否需要OCR and profile.文本行数 == 0:
        return f"\u300a{title}\u300b\u6587\u672c\u5c42\u6781\u5f31\uff0c\u5f53\u524d\u66f4\u50cf\u626b\u63cf\u4ef6\u6216\u56fe\u7247\u578b PDF\uff0c\u5efa\u8bae\u5148\u8fdb\u884c OCR \u540e\u518d\u505a\u7a33\u5b9a\u62bd\u53d6\u3002"

    parts = [f"\u300a{title}\u300b\u5f53\u524d\u8bc6\u522b\u4e3a{doc_type}\u3002"]
    if chapter_items:
        parts.append(f"\u5df2\u5efa\u7acb {len(chapter_items)} \u4e2a\u6b63\u6587\u7ae0\u8282\u6458\u8981\u3002")
    elif document.表格列表:
        parts.append(f"\u5f53\u524d\u5c1a\u672a\u7a33\u5b9a\u5efa\u7acb\u7ae0\u8282\u94fe\uff0c\u4f46\u5df2\u62bd\u53d6 {len(document.表格列表)} \u5f20\u8868\u683c\u3002")

    if numeric_items:
        parts.append(f"\u5df2\u62bd\u53d6 {len(numeric_items)} \u6761\u6570\u503c\u578b\u53c2\u6570\u3002")
    if standard_items:
        parts.append(f"\u5df2\u8bc6\u522b {len(standard_items)} \u6761\u5f15\u7528\u6807\u51c6\u3002")
    if profile and profile.是否需要OCR:
        parts.append("\u6587\u6863\u6587\u672c\u5c42\u504f\u5f31\uff0c\u540e\u7eed\u7ed3\u679c\u9700\u8981\u5173\u6ce8 OCR \u8865\u5f3a\u3002")
    return "".join(parts)


def _build_chapter_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for section in document.章节列表[:60]:
        number, title, _, _, body, _ = section_values(section)
        body_text = _clip(body, 220)
        heading = title if str(number).startswith("U") else f"{number} {title}".strip()
        localized_heading = localize_display_text(heading, fallback_prefix="章节主题") or normalize_line(heading)
        if not body_text and title:
            body_text = f"当前仅稳定识别到{localized_heading}，正文仍然较少。"
        elif body_text and looks_foreign_text(body_text):
            body_text = f"本章节主要围绕{localized_heading}展开，已识别到原文正文，当前细节仍以原文为准。"
        items.append({CHAPTER_TITLE: localized_heading, SUMMARY_TEXT: body_text})
    return items


def _build_numeric_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for param in get_parameter_entries(document)[:120]:
        name = param["参数名称"]
        value_text = param["参数值文本"]
        unit = param["单位"]
        lower = param["参数范围下限"]
        upper = param["参数范围上限"]
        comparator = param["比较符号"]
        condition = param["适用条件"]
        section_name = param["所属章节"]
        source_table = param["来源表格"]
        source_item = param["来源子项"]
        key = (normalize_line(name), normalize_line(value_text), normalize_line(condition))
        if key in seen:
            continue
        seen.add(key)
        localized_name = localize_source_text(name, fallback_prefix="参数项") or normalize_line(name)
        localized_condition = localize_condition_text(condition)
        localized_section = localize_display_text(section_name, fallback_prefix="章节主题")
        localized_table = localize_display_text(source_table, fallback_prefix="来源表格")
        localized_source_item = localize_source_text(source_item, fallback_prefix="原文字段")
        items.append(
            {
                PARAM_NAME: localized_name,
                PARAM_OVERVIEW: _parameter_overview(localized_name, value_text, localized_condition),
                PARAM_VALUE: _value_display(value_text, lower, upper, comparator),
                UNIT: normalize_line(unit) or UNSPECIFIED,
                CONDITION: localized_condition,
                SECTION_NAME: localized_section,
                SOURCE_TABLE: localized_table,
                SOURCE_ITEM: localized_source_item,
            }
        )
    return items


def _build_rule_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in get_rule_entries(document)[:100]:
        rule_type = rule["规则类型"]
        content = rule["内容"]
        condition = rule.get("适用条件", "")
        section_name = rule["所属章节"]
        key = (normalize_line(rule_type), normalize_line(content), normalize_line(section_name))
        if key in seen:
            continue
        seen.add(key)
        localized_rule_type = localize_source_text(rule_type, fallback_prefix="规则项") or RULE_REQUIREMENT
        localized_section = localize_display_text(section_name, fallback_prefix="章节主题")
        localized_condition = localize_condition_text(condition)
        localized_content = normalize_line(content)
        if localized_content and looks_foreign_text(localized_content):
            localized_content = f"已识别到与{localized_rule_type}相关的原文规则，当前细节仍以原文为准。"
        items.append(
            {
                PARAM_NAME: localized_rule_type,
                RULE_OVERVIEW: localized_content,
                CONDITION: localized_condition,
                SECTION_NAME: localized_section,
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
    for section in document.章节列表[:20]:
        number, title, _, _, body, _ = section_values(section)
        body_text = _clip(body, 180)
        if body_text:
            localized_section = localize_display_text(
                title if str(number).startswith("U") else f"{number} {title}".strip(),
                fallback_prefix="章节主题",
            )
            if looks_foreign_text(body_text):
                body_text = "本章节已识别到原文说明，当前细节仍以原文为准。"
            fallback.append(
                {
                    REQUIREMENT_TYPE: CHAPTER_NOTE,
                    CONTENT: body_text,
                    CONDITION: "",
                    SECTION_NAME: localized_section,
                }
            )
    return fallback


def _build_standard_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in get_standard_entries(document)[:120]:
        code = item["标准编号"]
        title = item["标准名称"]
        standard_type = item["标准族"]
        section_name = item["所属章节"]
        key = (normalize_line(code), normalize_line(section_name))
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                STANDARD_CODE: normalize_line(code),
                STANDARD_OVERVIEW: localize_source_text(title or standard_type, fallback_prefix="标准标题"),
                SECTION_NAME: localize_display_text(section_name, fallback_prefix="章节主题"),
            }
        )
    return items


def _build_product_summary(document: DocumentData) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for product in get_product_entries(document)[:40]:
        anchor_name = product["显示名称"]
        items.append(
            {
                PRODUCT_NAME: localize_source_text(
                    product["名称"] or anchor_name or product["系列"],
                    fallback_prefix="产品项",
                ),
                MODEL: normalize_line(product["型号"]),
                PRODUCT_OVERVIEW: localize_source_text(
                    anchor_name or product["名称"] or product["系列"],
                    fallback_prefix="产品说明",
                ),
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
    return bool(document.章节列表 or document.数值参数列表 or document.规则列表 or document.引用标准列表 or document.表格列表)


def _should_use_llm(document: DocumentData) -> bool:
    return _has_enough_material(document)
