from __future__ import annotations

import re

from src.utils import normalize_line

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
        return f"{translated}（原文：{normalized}）"
    return f"{fallback_prefix}（原文：{normalized}）"


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
        return f"{translated}（原文：{normalized}）"
    return f"{fallback_prefix}（原文：{normalized}）"


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
        return f"{translated}条件（原文：{normalized}）"
    return f"原文条件：{normalized}"


def localize_tag_text(text: str) -> str:
    normalized = normalize_line(text)
    if not normalized or is_symbol_heavy(normalized):
        return ""
    if contains_cjk(normalized):
        return normalized
    translated = translate_phrase(normalized)
    return translated if translated != normalized else ""
