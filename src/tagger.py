from __future__ import annotations

import re
from typing import Any

from config import AppConfig
from src.models import DocumentData
from src.openai_compat import llm_available, request_structured_json
from src.record_access import metadata_doc_type, section_values, table_values
from src.structured_access import get_parameter_entries, get_product_entries, get_standard_entries
from src.text_localization import is_symbol_heavy, localize_tag_text
from src.utils import dedupe_keep_order, normalize_line

DOC_TYPE_TAGS = "\u6587\u6863\u7c7b\u578b\u6807\u7b7e"
TOPIC_TAGS = "\u6587\u6863\u4e3b\u9898\u6807\u7b7e"
PROCESS_TAGS = "\u5de5\u827a\u6d41\u7a0b\u6807\u7b7e"
PARAMETER_TAGS = "\u53c2\u6570\u6807\u7b7e"
INSPECTION_TAGS = "\u68c0\u9a8c\u6807\u7b7e"
STANDARD_TAGS = "\u6807\u51c6\u5f15\u7528\u6807\u7b7e"
PRODUCT_SERIES_TAGS = "\u4ea7\u54c1\u7cfb\u5217\u6807\u7b7e"
PRODUCT_MODEL_TAGS = "\u4ea7\u54c1\u578b\u53f7\u6807\u7b7e"
APPLICATION_TAGS = "\u5e94\u7528\u6807\u7b7e"
CERTIFICATION_TAGS = "\u8ba4\u8bc1\u6807\u7b7e"
DEFECT_TAGS = "\u7f3a\u9677\u6807\u7b7e"
WELD_TYPE_TAGS = "\u710a\u7f1d\u7c7b\u578b\u6807\u7b7e"
REGION_TAGS = "\u533a\u57df\u6807\u7b7e"

STANDARD_FAMILY_RE = re.compile(r"^(DIN EN ISO|DIN ISO|DIN EN|DIN|EN|ISO|SN|SEW|DVS|AD)", re.IGNORECASE)
APPLICATION_HINT_RE = re.compile(
    r"(?:\u9002\u7528\u8303\u56f4|\u5e94\u7528\u8303\u56f4|\u5e94\u7528\u573a\u666f|\u7528\u9014|application|scope|anwendungsbereich)\s*[:\uff1a]?\s*(.+)",
    re.IGNORECASE,
)
CERTIFICATION_RE = re.compile(r"\b(?:CE|UL|CSA|ATEX|IECEx|RoHS|REACH|CCC|TUV|T\u00dcV|FDA|EHEDG|3-A)\b", re.IGNORECASE)
LOW_SIGNAL_PARAMETER_RE = re.compile(r"^(?:-|\(?[A-Z]\)?|DN|d\s*\d+\)?|l\s*\d+|s\d*|b|h|w)$", re.IGNORECASE)
DIMENSION_TOKEN_RE = re.compile(r"^(?:DN|d\d+\)?|l\d+|s\d*|b|h|w)$", re.IGNORECASE)
NUMBER_HEAVY_RE = re.compile(r"(?:\d+[.)/]?\s*){2,}")
ABBREV_HEAVY_RE = re.compile(r"(?:\b[a-z]{1,3}\b\s*){2,}", re.IGNORECASE)
PARAMETER_TAG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:pressure|druck|betriebsdruck|working pressure|psi|bar)\b", re.IGNORECASE), "\u538b\u529b"),
    (re.compile(r"\b(?:weight|gewicht)\b", re.IGNORECASE), "\u91cd\u91cf"),
    (re.compile(r"\b(?:radius|biegeradius|halbmesser)\b", re.IGNORECASE), "\u534a\u5f84"),
    (re.compile(r"\b(?:length|l\u00e4nge|laenge)\b", re.IGNORECASE), "\u957f\u5ea6"),
    (re.compile(r"\b(?:width|breite)\b", re.IGNORECASE), "\u5bbd\u5ea6"),
    (re.compile(r"\b(?:height|h\u00f6he|hoehe)\b", re.IGNORECASE), "\u9ad8\u5ea6"),
    (re.compile(r"\b(?:temperature|temperatur)\b", re.IGNORECASE), "\u6e29\u5ea6"),
    (re.compile(r"\b(?:tolerance|abweichung)\b", re.IGNORECASE), "\u516c\u5dee"),
    (re.compile(r"\b(?:schl(?:u|ü|ue)sselweite)\b", re.IGNORECASE), "\u5c3a\u5bf8"),
    (re.compile(r"\b(?:size|gr\u00f6\u00dfe|gr\u00f6sse|groesse|nenngr\u00f6\u00dfe|nenngroesse|dimension)\b", re.IGNORECASE), "\u5c3a\u5bf8"),
    (re.compile(r"\b(?:thickness|wanddicke|wall thickness)\b", re.IGNORECASE), "\u539a\u5ea6"),
]
PROCESS_HINTS = [
    "\u94f8\u9020",
    "\u953b\u9020",
    "\u5207\u524a\u52a0\u5de5",
    "\u88c5\u914d",
    "\u710a\u63a5",
    "\u9632\u8150",
    "\u6807\u8bb0",
    "\u5305\u88c5",
    "\u68c0\u9a8c",
    "inspection",
    "packaging",
]
TOPIC_STOPWORDS = {
    "\u57fa\u672c\u89c4\u5b9a",
    "\u5e94\u7528\u8303\u56f4\u548c\u76ee\u7684",
    "\u8303\u56f4",
    "scope",
    "application",
    "anwendungsbereich",
}
SERIES_NOISE_RE = re.compile(r"(\u4ea7\u54c1\u6837\u672c|\u4ea7\u54c1\u76ee\u5f55|catalog|brochure|sample)", re.IGNORECASE)


def build_tags(document: DocumentData, config: AppConfig | None = None) -> dict[str, Any]:
    text_pool = _build_text_pool(document)
    base_tags: dict[str, Any] = {
        DOC_TYPE_TAGS: _build_doc_type_tags(document),
        TOPIC_TAGS: _build_topic_tags(document),
        PROCESS_TAGS: _build_process_tags(text_pool),
        PARAMETER_TAGS: _build_parameter_tags(document),
        INSPECTION_TAGS: _build_inspection_tags(document),
        STANDARD_TAGS: _build_standard_tags(document),
        PRODUCT_SERIES_TAGS: _build_product_series_tags(document),
        PRODUCT_MODEL_TAGS: _build_product_model_tags(document),
        APPLICATION_TAGS: _build_application_tags(text_pool),
        CERTIFICATION_TAGS: _build_certification_tags(text_pool),
        DEFECT_TAGS: [],
        WELD_TYPE_TAGS: [],
        REGION_TAGS: [],
    }
    if config and config.use_llm and llm_available():
        try:
            refined_tags, backend = _build_tags_with_llm(document, base_tags, config)
            refined_tags["_llm_backend"] = backend
            return refined_tags
        except Exception as exc:
            base_tags["_llm_error"] = str(exc)
    return base_tags


def _build_doc_type_tags(document: DocumentData) -> list[str]:
    profile = document.文档画像
    doc_type = profile.文档类型 if profile else "unknown"
    labels = {
        "standard": ["\u6807\u51c6\u89c4\u8303", "\u6807\u51c6/\u89c4\u8303\u6587\u6863"],
        "product_catalog": ["\u4ea7\u54c1\u6837\u672c", "\u4ea7\u54c1/\u89c4\u683c\u8d44\u6599"],
        "manual": ["\u6280\u672f\u624b\u518c", "\u8bf4\u660e\u6587\u6863"],
        "report": ["\u62a5\u544a\u6587\u6863", "\u68c0\u9a8c/\u8bc1\u4e66"],
        "unknown": ["\u672a\u77e5\u6587\u6863", "\u6280\u672f\u8d44\u6599"],
    }
    tags = list(labels.get(doc_type, labels["unknown"]))
    if profile and profile.是否需要OCR:
        tags.append("\u7591\u4f3c\u626b\u63cf\u4ef6")
    raw_doc_type = normalize_line(metadata_doc_type(document.文件元数据))
    localized_raw_doc_type = localize_tag_text(raw_doc_type)
    if localized_raw_doc_type and localized_raw_doc_type not in tags:
        tags.append(localized_raw_doc_type)
    return dedupe_keep_order(tags)


def _build_topic_tags(document: DocumentData) -> list[str]:
    candidates: list[str] = []
    for section in document.章节列表[:30]:
        _, title, _, _, _, _ = section_values(section)
        title = _normalize_topic_tag_candidate(title)
        if title:
            candidates.append(title)
    for table in document.表格列表[:20]:
        _, title, _, _, _ = table_values(table)
        title = _normalize_topic_tag_candidate(title)
        if title:
            candidates.append(title)
    return dedupe_keep_order(candidates)[:20]


def _build_process_tags(text_pool: list[str]) -> list[str]:
    joined = "\n".join(text_pool).lower()
    tags: list[str] = []
    for item in PROCESS_HINTS:
        if item.lower() in joined:
            if item.lower() == "inspection":
                tags.append("\u68c0\u9a8c")
            elif item.lower() == "packaging":
                tags.append("\u5305\u88c5")
            else:
                tags.append(item)
    return dedupe_keep_order(tags)


def _build_parameter_tags(document: DocumentData) -> list[str]:
    names: list[str] = []
    for item in get_parameter_entries(document):
        name = _normalize_parameter_tag_candidate(item["参数名称"])
        if _keep_parameter_tag(name):
            names.append(name)
    return dedupe_keep_order(names)[:30]


def _build_inspection_tags(document: DocumentData) -> list[str]:
    tags: list[str] = []
    for item in document.检验列表:
        values = tuple(item.__dict__.values())
        if len(values) >= 2:
            method = normalize_line(str(values[1]))
            localized_method = method if any("\u4e00" <= ch <= "\u9fff" for ch in method) else localize_tag_text(method)
            if localized_method and len(localized_method) <= 40:
                tags.append(localized_method)
    return dedupe_keep_order(tags)


def _build_standard_tags(document: DocumentData) -> list[str]:
    tags: list[str] = []
    for item in get_standard_entries(document):
        code = normalize_line(item["标准编号"])
        match = STANDARD_FAMILY_RE.match(code)
        if match:
            tags.append(match.group(1).upper())
        else:
            standard_type = normalize_line(item["标准族"])
            if standard_type:
                tags.append(standard_type)
    return dedupe_keep_order(tags)


def _build_product_series_tags(document: DocumentData) -> list[str]:
    items: list[str] = []
    for item in get_product_entries(document):
        series = SERIES_NOISE_RE.sub("", normalize_line(item["系列"])).strip(" -/")
        if series:
            items.append(series)
    return dedupe_keep_order(items)


def _build_product_model_tags(document: DocumentData) -> list[str]:
    return dedupe_keep_order([normalize_line(item["型号"]) for item in get_product_entries(document) if normalize_line(item["型号"])])


def _build_application_tags(text_pool: list[str]) -> list[str]:
    tags: list[str] = []
    for text in text_pool:
        match = APPLICATION_HINT_RE.search(text)
        if not match:
            continue
        candidate = normalize_line(match.group(1))
        localized = localize_tag_text(candidate)
        if not localized and any("\u4e00" <= ch <= "\u9fff" for ch in candidate):
            localized = candidate
        if localized and 2 <= len(localized) <= 60:
            tags.append(localized)
    return dedupe_keep_order(tags)[:15]


def _build_certification_tags(text_pool: list[str]) -> list[str]:
    tags: list[str] = []
    for text in text_pool:
        tags.extend(match.group(0).upper() for match in CERTIFICATION_RE.finditer(text))
    return dedupe_keep_order(tags)


def _build_text_pool(document: DocumentData) -> list[str]:
    pool: list[str] = []
    for section in document.章节列表:
        _, title, _, _, body, _ = section_values(section)
        pool.append(title)
        pool.extend(str(body).splitlines()[:10])
    for table in document.表格列表:
        _, title, _, _, _ = table_values(table)
        pool.append(title)
    return [normalize_line(item) for item in pool if normalize_line(item)]


def _keep_topic(text: str) -> bool:
    text = normalize_line(text)
    lowered = text.lower()
    if not text:
        return False
    if is_symbol_heavy(text):
        return False
    if lowered in TOPIC_STOPWORDS:
        return False
    if re.fullmatch(r"(?:SN|DIN|ISO|EN)\s*\d+(?:[-/]\d+)?", text, re.IGNORECASE):
        return False
    if len(text) <= 1 or len(text) > 60:
        return False
    return True


def _normalize_topic_tag_candidate(text: str) -> str:
    text = normalize_line(text)
    if not text or is_symbol_heavy(text):
        return ""
    if not _keep_topic(text):
        return ""
    localized = localize_tag_text(text)
    return localized or (text if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "")


def _keep_parameter_tag(text: str) -> bool:
    text = normalize_line(text)
    if not text:
        return False
    if len(text) > 40:
        return False
    if NUMBER_HEAVY_RE.search(text):
        return False
    if LOW_SIGNAL_PARAMETER_RE.fullmatch(text):
        return False
    if ABBREV_HEAVY_RE.search(text) and len(text.split()) >= 3:
        return False
    tokens = text.replace("/", " ").replace("-", " ").split()
    if tokens and all(DIMENSION_TOKEN_RE.fullmatch(token) for token in tokens):
        return False
    if any(token.lower() in {"for", "and", "und", "mit"} for token in tokens) and len(tokens) >= 4:
        return False
    return True


def _normalize_parameter_tag_candidate(text: str) -> str:
    text = normalize_line(text)
    if not text:
        return ""
    for pattern, replacement in PARAMETER_TAG_PATTERNS:
        if pattern.search(text):
            return replacement
    cleaned = re.sub(r"\s+", " ", text)
    cleaned = re.sub(r"[()]+", "", cleaned).strip(" -/:;,.")
    return cleaned


def _build_tags_with_llm(document: DocumentData, base_tags: dict[str, Any], config: AppConfig) -> tuple[dict[str, Any], str]:
    payload = {
        "profile": document.文档画像.to_dict() if document.文档画像 else {},
        "base_tags": base_tags,
        "section_titles": [normalize_line(section_values(item)[1]) for item in document.章节列表[:25]],
        "parameter_names": [normalize_line(item["参数名称"]) for item in get_parameter_entries(document)[:40]],
        "standard_codes": [normalize_line(item["标准编号"]) for item in get_standard_entries(document)[:30]],
        "product_names": [normalize_line(item["显示名称"]) for item in get_product_entries(document)[:20]],
    }
    schema = {
        "type": "object",
        "properties": {
            "doc_type_tags": {"type": "array", "items": {"type": "string"}},
            "topic_tags": {"type": "array", "items": {"type": "string"}},
            "process_tags": {"type": "array", "items": {"type": "string"}},
            "parameter_tags": {"type": "array", "items": {"type": "string"}},
            "inspection_tags": {"type": "array", "items": {"type": "string"}},
            "standard_tags": {"type": "array", "items": {"type": "string"}},
            "product_series_tags": {"type": "array", "items": {"type": "string"}},
            "product_model_tags": {"type": "array", "items": {"type": "string"}},
            "application_tags": {"type": "array", "items": {"type": "string"}},
            "certification_tags": {"type": "array", "items": {"type": "string"}},
            "defect_tags": {"type": "array", "items": {"type": "string"}},
            "weld_type_tags": {"type": "array", "items": {"type": "string"}},
            "region_tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "doc_type_tags",
            "topic_tags",
            "process_tags",
            "parameter_tags",
            "inspection_tags",
            "standard_tags",
            "product_series_tags",
            "product_model_tags",
            "application_tags",
            "certification_tags",
            "defect_tags",
            "weld_type_tags",
            "region_tags",
        ],
        "additionalProperties": False,
    }
    result, backend = request_structured_json(
        model=config.openai_model,
        system_prompt=(
            "You clean and normalize tags for structured technical PDF outputs. "
            "Use the provided evidence to remove noisy tags, merge near-duplicates, and add only stable tags that are clearly supported. "
            "Prefer concise noun phrases. Do not invent unsupported tags."
        ),
        user_payload=payload,
        schema_name="normalized_tags",
        schema=schema,
        timeout=25.0,
    )
    return _map_llm_tag_result(result), backend


def _map_llm_tag_result(result: dict[str, Any]) -> dict[str, Any]:
    mapped = {
        DOC_TYPE_TAGS: result.get("doc_type_tags", []),
        TOPIC_TAGS: result.get("topic_tags", []),
        PROCESS_TAGS: result.get("process_tags", []),
        PARAMETER_TAGS: result.get("parameter_tags", []),
        INSPECTION_TAGS: result.get("inspection_tags", []),
        STANDARD_TAGS: result.get("standard_tags", []),
        PRODUCT_SERIES_TAGS: result.get("product_series_tags", []),
        PRODUCT_MODEL_TAGS: result.get("product_model_tags", []),
        APPLICATION_TAGS: result.get("application_tags", []),
        CERTIFICATION_TAGS: result.get("certification_tags", []),
        DEFECT_TAGS: result.get("defect_tags", []),
        WELD_TYPE_TAGS: result.get("weld_type_tags", []),
        REGION_TAGS: result.get("region_tags", []),
    }
    cleaned: dict[str, Any] = {}
    for key, values in mapped.items():
        cleaned[key] = dedupe_keep_order([normalize_line(str(item)) for item in values if normalize_line(str(item))])
    return cleaned
