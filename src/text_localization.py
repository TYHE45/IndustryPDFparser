from __future__ import annotations

import logging
import re

from src.utils import normalize_line

LOGGER = logging.getLogger(__name__)
_WARNED_SAFETY_NETS: set[tuple[str, str]] = set()

# 按场景分桶计数。键为中文场景名，值为本轮累计触发次数。
# 场景映射：display→显示、source→来源、condition→条件、tag→标签。
_KIND_TO_ZH: dict[str, str] = {
    "display": "显示",
    "source": "来源",
    "condition": "条件",
    "tag": "标签",
}
_SAFETY_NET_TRIGGER_DETAIL: dict[str, int] = {zh: 0 for zh in _KIND_TO_ZH.values()}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-zÄÖÜäöüß]")
SYMBOL_NOISE_RE = re.compile(r"[Ω⋅]")
TECH_TOKEN_RE = re.compile(r"^(?:[A-Za-z]{1,6}\d{0,3}|\d{0,3}[A-Za-z]{1,6}|[A-Za-z]\d{1,3})$")

TRANSLATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:ma(?:ß|ss)e)\s+(?:und|&)\s+(?:bezeichnungsbeispiel|designation example)", re.IGNORECASE), "尺寸与命名示例"),
    (re.compile(r"(?:werkstoff)\s+(?:und|&)\s+(?:ausf(?:ü|ue)hrung|construction|design)", re.IGNORECASE), "材料与结构"),
    (re.compile(r"(?:zitierte?\s+normen|cited?\s+standards?|referenced?\s+standards?)", re.IGNORECASE), "引用标准"),
    (re.compile(r"(?:weitere?\s+normen|additional\s+standards?|other\s+standards?)", re.IGNORECASE), "其他标准"),
    (re.compile(r"(?:innenschicht|inner\s*layer|lining)", re.IGNORECASE), "内层"),
    (re.compile(r"(?:au(?:ß|ss)enschicht|outer\s*layer|cover)", re.IGNORECASE), "外层"),
    (re.compile(r"(?:kennzeichnung|marking|labeling)", re.IGNORECASE), "标识"),
    (re.compile(r"(?:anwendungsbereich|application(?:\s+range)?|scope)", re.IGNORECASE), "适用范围"),
    (re.compile(r"(?:k(?:leinster)?\s*biegeradius|bend radius|radius)", re.IGNORECASE), "弯曲半径"),
    (re.compile(r"(?:nenn(?:gr(?:ö|oe)ße|groesse)|nominal size)", re.IGNORECASE), "公称尺寸"),
    (re.compile(r"(?:ma(?:ß|ss)e|dimension(?:s)?|size)", re.IGNORECASE), "尺寸"),
    (re.compile(r"(?:bezeichnungsbeispiel|designation example)", re.IGNORECASE), "命名示例"),
    (re.compile(r"(?:werkstoff|material)", re.IGNORECASE), "材料"),
    (re.compile(r"(?:ausf(?:ü|ue)hrung|construction|design)", re.IGNORECASE), "结构"),
    (re.compile(r"(?:norm(?:en)?|standard(?:s)?)", re.IGNORECASE), "标准"),
    (re.compile(r"(?:temperatur|temperature)", re.IGNORECASE), "温度"),
    (re.compile(r"(?:druck|pressure|betriebsdruck)", re.IGNORECASE), "压力"),
    (re.compile(r"(?:gewicht|weight)", re.IGNORECASE), "重量"),
    (re.compile(r"(?:l(?:ä|ae)nge|length)", re.IGNORECASE), "长度"),
    (re.compile(r"(?:breite|width)", re.IGNORECASE), "宽度"),
    (re.compile(r"(?:h(?:ö|oe)he|height)", re.IGNORECASE), "高度"),
    (re.compile(r"(?:dicke|thickness)", re.IGNORECASE), "厚度"),
    (re.compile(r"(?:pr(?:ü|ue)fung|inspection|test)", re.IGNORECASE), "检验"),
    (re.compile(r"(?:anwendung|application)", re.IGNORECASE), "应用"),
    (re.compile(r"(?:montage|installation)", re.IGNORECASE), "安装"),
    (re.compile(r"(?:wartung|maintenance)", re.IGNORECASE), "维护"),
]


def _warn_safety_net(kind: str, text: str, rendered: str) -> None:
    key = (kind, text)
    if key in _WARNED_SAFETY_NETS:
        return
    _WARNED_SAFETY_NETS.add(key)
    zh_kind = _KIND_TO_ZH.get(kind, kind)
    _SAFETY_NET_TRIGGER_DETAIL[zh_kind] = _SAFETY_NET_TRIGGER_DETAIL.get(zh_kind, 0) + 1
    LOGGER.warning("text_localization 安全网已触发：%s -> %s（类型=%s）", text, rendered, kind)


def reset_safety_net_trigger_count() -> None:
    _WARNED_SAFETY_NETS.clear()
    for zh in _KIND_TO_ZH.values():
        _SAFETY_NET_TRIGGER_DETAIL[zh] = 0


def get_safety_net_trigger_count() -> int:
    return int(sum(_SAFETY_NET_TRIGGER_DETAIL.values()))


def get_safety_net_trigger_detail() -> dict[str, int]:
    """返回按场景分桶的 safety-net 触发次数（本轮累计，键为中文场景名）。"""
    return {zh: int(_SAFETY_NET_TRIGGER_DETAIL.get(zh, 0)) for zh in _KIND_TO_ZH.values()}


def contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(normalize_line(text)))


def looks_foreign_text(text: str) -> bool:
    normalized = normalize_line(text)
    return bool(normalized) and not contains_cjk(normalized) and bool(LATIN_RE.search(normalized))


def is_symbol_heavy(text: str) -> bool:
    normalized = normalize_line(text)
    if not normalized:
        return True
    if SYMBOL_NOISE_RE.search(normalized):
        return True
    signal = sum(1 for ch in normalized if ch.isalnum() or ch in "ÄÖÜäöüß")
    return signal / max(len(normalized), 1) < 0.45


def translate_phrase(text: str) -> str:
    normalized = normalize_line(text)
    if not normalized:
        return ""
    if contains_cjk(normalized):
        return normalized
    for pattern, translated in TRANSLATION_PATTERNS:
        if pattern.search(normalized):
            return translated
    return ""


def should_preserve_token(text: str) -> bool:
    normalized = normalize_line(text)
    if not normalized or contains_cjk(normalized) or " " in normalized:
        return False
    return len(normalized) <= 8 and bool(TECH_TOKEN_RE.fullmatch(normalized))


def localize_display_text(text: str, *, fallback_prefix: str) -> str:
    normalized = normalize_line(text)
    if not normalized:
        return ""
    if contains_cjk(normalized):
        return normalized
    if should_preserve_token(normalized):
        return normalized
    translated = translate_phrase(normalized)
    if translated and translated != normalized:
        rendered = f"{translated}（原文：{normalized}）"
        _warn_safety_net("display", normalized, rendered)
        return rendered
    rendered = f"{fallback_prefix}（原文：{normalized}）"
    _warn_safety_net("display", normalized, rendered)
    return rendered


def localize_source_text(text: str, *, fallback_prefix: str) -> str:
    normalized = normalize_line(text)
    if not normalized:
        return ""
    if contains_cjk(normalized):
        return normalized
    if should_preserve_token(normalized):
        return normalized
    translated = translate_phrase(normalized)
    if translated and translated != normalized:
        rendered = f"{translated}（原文：{normalized}）"
        _warn_safety_net("source", normalized, rendered)
        return rendered
    rendered = f"{fallback_prefix}（原文：{normalized}）"
    _warn_safety_net("source", normalized, rendered)
    return rendered


def localize_condition_text(text: str) -> str:
    normalized = normalize_line(text)
    if not normalized:
        return ""
    if contains_cjk(normalized):
        return normalized
    if should_preserve_token(normalized):
        return normalized
    translated = translate_phrase(normalized)
    if translated and translated != normalized:
        rendered = f"{translated}条件（原文：{normalized}）"
        _warn_safety_net("condition", normalized, rendered)
        return rendered
    rendered = f"原文条件：{normalized}"
    _warn_safety_net("condition", normalized, rendered)
    return rendered


def localize_tag_text(text: str) -> str:
    normalized = normalize_line(text)
    if not normalized or is_symbol_heavy(normalized):
        return ""
    if contains_cjk(normalized):
        return normalized
    translated = translate_phrase(normalized)
    if translated and translated != normalized:
        _warn_safety_net("tag", normalized, translated)
        return translated
    return ""
