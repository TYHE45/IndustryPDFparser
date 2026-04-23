from __future__ import annotations

import re
from typing import Any

from config import AppConfig
from src.cleaner import LineCleaner, detect_repeated_noise
from src.loader import open_pdf
from src.models import (
    AnchorRef,
    BlockRecord,
    DocumentData,
    FileMetadata,
    InspectionRecord,
    NumericParameter,
    PageRecord,
    ProductRecord,
    RuleRecord,
    SectionRecord,
    SourceRef,
    StandardReference,
    StructureNode,
    TableRecord,
)
from src.profiler import profile_document
from src.utils import normalize_cell, normalize_line

FRONT_MATTER_CUE_RE = re.compile(
    r"(?:备案号|邮政编码|邮编|电话|传真|网址|网站|印数|定价|出版|发行|版权|ISBN|地址|前言|免费标准下载|标准分享网)",
    re.IGNORECASE,
)
FRONT_MATTER_SECTION_RE = re.compile(r"(?:前言|文件基础信息|版权|出版|发行)", re.IGNORECASE)

NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:[.)])?\s+(.+)$")
PART_HEADING_RE = re.compile(r"^(第\s*\d+\s*部分|Part\s+\d+|Teil\s+\d+)(?:\s*[:\-]\s*(.+))?$", re.IGNORECASE)
# §2.3 扩充：支持 GB/T、CB/T、CB/Z 等带斜杠后缀；连字符允许 OCR 常见的噪音变体
# （普通 `-`、U+2014 `—`、U+2013 `–`、U+2500 `─`、连续多个）；前缀后允许多空格。
# 贪心匹配尾部数字/连字符串，避免在 "GB 600-91" 这种形态下被提前截断。
STANDARD_RE = re.compile(
    r"\b((?:DIN|EN|ISO|IEC|JIS|ASTM|SN|SEW|DVS|AD|TRbF|GB|CB|CH)(?:/[TZ])?(?:\s+[A-Z]+)?\s*[0-9][0-9A-Za-z./\-—–─_]*)\b"
)
TABLE_CAPTION_RE = re.compile(r"^(?:表|Table|Tabelle)\s*\d+[:\s\-]?(.*)$", re.IGNORECASE)
FIGURE_CAPTION_RE = re.compile(r"^(?:图|Figure|Fig\.?)\s*\d+[:\s\-]?(.*)$", re.IGNORECASE)
GENERIC_SHORT_HEADING_RE = re.compile(
    r"(application|scope|dimensions|requirements|inspection|material|packaging|marking|summary|"
    r"anwendungsbereich|maße|werkstoff|zitierte normen|prüfung|dichtung|"
    r"standard lengths|admissible length deviation|specification in the bill of materials|"
    r"weitere maße|bezeichnungsbeispiel)",
    re.IGNORECASE,
)
LEGAL_NOTICE_RE = re.compile(r"(all rights reserved|copyright|patent|utility model|未经书面许可不得复制)", re.IGNORECASE)
BOILERPLATE_FRAGMENT_RE = re.compile(
    r"(?:express authorization is prohibited|offenders will be held liable|this copy will not be updated|latest german-language version|of this standard shall be taken as authoritative)",
    re.IGNORECASE,
)
ADVERTISEMENT_NOISE_RE = re.compile(r"(?:https?://|www\.|17jzw|bzfxw|分享网|免费下载|标准下载|道客巴巴|文库|淘宝)", re.IGNORECASE)
REVISION_RE = re.compile(r"(修订|修订记录|变更|revision|change log|änderung)", re.IGNORECASE)
MODEL_RE = re.compile(r"\b[A-Z]{1,5}(?:[-/][A-Z0-9]{2,}|\d{2,}[A-Z0-9/-]*)\b")
PRODUCT_HINT_RE = re.compile(r"(型号|系列|规格|参数|订货|选型|model|series|specification|ordering|type)", re.IGNORECASE)
APPLICATION_HINT_RE = re.compile(r"(应用|适用|用途|application|scope|anwendungsbereich)", re.IGNORECASE)
INSPECTION_HINT_RE = re.compile(r"(检验|检测|试验|inspection|test|prüfung|pruefung)", re.IGNORECASE)
RULE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(不得|禁止|不允许|must not|shall not|darf nicht|dürfen nicht)", re.IGNORECASE), "禁止"),
    (re.compile(r"(必须|应当|应|shall|must|muss|müssen|ist zu)", re.IGNORECASE), "必须"),
    (re.compile(r"(建议|宜|should|recommended|sollte|sollen)", re.IGNORECASE), "建议"),
]
UNIT_TOKEN_RE = re.compile(r"(mm|cm|m|μm|µm|um|bar|psi|°C|℃|K|%|A/m|N/mm2|N/mm²|kN/m2|kg|g|°)")
RANGE_RE = re.compile(
    r"(?P<lower>\d+(?:[.,]\d+)?)\s*(?:to|bis|至|~|～|—|-+)\s*(?P<upper>\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<unit>mm|cm|m|μm|µm|um|bar|psi|°C|℃|K|%|A/m|N/mm2|N/mm²|kN/m2|kg|g|°))?",
    re.IGNORECASE,
)
COMPARE_RE = re.compile(
    r"(?P<cmp>≤|≥|<|>|=|\+/-|±)\s*(?P<value>\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<unit>mm|cm|m|μm|µm|um|bar|psi|°C|℃|K|%|A/m|N/mm2|N/mm²|kN/m2|kg|g|°))?",
    re.IGNORECASE,
)
HEADER_VALUE_RE = re.compile(r"^(?:DN|d\d+|l\d+|s|t|h|w|weight|gewicht|mass|length|angle)$", re.IGNORECASE)
GENERIC_NOISE_HEADING_RE = re.compile(r"^(?:sn\s*\d+|din\s*\d+|en\s*\d+|iso\s*\d+|page\s+\d+|seite\s+\d+)$", re.IGNORECASE)
NOISE_MARKER_RE = re.compile(r"^(?:bearbeitet:?|edited:?|draft|status)$", re.IGNORECASE)
SECTION_NUMBER_ONLY_RE = re.compile(r"^\d+[.)]?$")
SPLIT_HEADING_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*[.)]?$")
SHORT_TOKEN_RE = re.compile(r"^[A-Z]{1,3}$")
LETTER_RANGE_RE = re.compile(r"^[A-Z](?:\s*-\s*[A-Z])+$")
VALUE_FRAGMENT_RE = re.compile(r"^(?:[+\-]|≤|≥|<|>)?\s*(?:DN\s*)?\d+(?:[.,]\d+)?\s*%?$", re.IGNORECASE)
LOWERCASE_FRAGMENT_RE = re.compile(r"^[a-zäöü]")
LEADING_CONJUNCTION_RE = re.compile(r"^(?:and|und|or|oder)\b", re.IGNORECASE)
ICS_RE = re.compile(r"^ICS\s+\d+(?:\.\d+)*$", re.IGNORECASE)
SENTENCE_VERB_RE = re.compile(r"\b(?:beträgt|ist|sind|muss|müssen|werden|wird|can|shall|must|used|pointing|given)\b", re.IGNORECASE)
LOW_SIGNAL_TABLE_TITLE_RE = re.compile(
    r"^(?:"
    r"zitierte normen|引用标准|reference(?:s)?|references|"
    r"weitere normen|further standards|additional standards|"
    r"frühere ausgaben|fruhere ausgaben|earlier editions"
    r")$",
    re.IGNORECASE,
)
REFERENCE_SECTION_TITLE_RE = re.compile(
    r"^(?:zitierte normen|引用标准|references|reference standards|referenced standards|weitere normen|further standards|additional standards)$",
    re.IGNORECASE,
)
REVISION_SECTION_TITLE_RE = re.compile(r"^(?:frühere ausgaben|fruhere ausgaben|earlier editions)$", re.IGNORECASE)
TOC_LINE_RE = re.compile(r"(?:\.|…){5,}\s*\d+(?:\+\d+)?\s*$")
TOC_HEADER_RE = re.compile(r"\b(?:contents|inhalt|目录)\b", re.IGNORECASE)
METADATA_LABEL_RE = re.compile(r"^(?:normenstelle|normungsstelle)$", re.IGNORECASE)
TOTAL_PAGES_RE = re.compile(r"^(?:total number of pages|gesamtseitenzahl)\s+\d+\b", re.IGNORECASE)
EDITION_HEADER_RE = re.compile(r"^(?:[A-Z]{1,4}\s*\d+(?:[-/]\d+)?\s*:\s*)?\d{4}(?:-\d{2})?\s+edition\b", re.IGNORECASE)
PAGE_HEADER_NOISE_RE = re.compile(r"^(?:page|supersedes|contents|index)$", re.IGNORECASE)
DOC_VERSION_RE = re.compile(r"^(?:DIN|EN|ISO|SN|SEW|DVS|AD|TRbF)\s+\d[\dA-Za-z./\-]*(?:\s*:\s*\d{4}(?:-\d{2})?)?$", re.IGNORECASE)
CORPORATE_NOTICE_RE = re.compile(r"(?:SMS\s+Demag\s+AG|all rights reserved|no guarantee can be given)", re.IGNORECASE)
FOOTNOTE_CONTINUE_RE = re.compile(r"^(?:footnotes?\s+see\s+page\s+\d+|continued\s+on\s+page\s+\d+)$", re.IGNORECASE)
METADATA_PREFIX_RE = re.compile(r"^(?:bearbeitet|edited)\s*:", re.IGNORECASE)
FOOTNOTE_MARKER_RE = re.compile(r"^\d+\)$")
TABLE_HEADER_FRAGMENT_RE = re.compile(
    r"^(?:operat(?:ing)?\.?\s*pressure|pressure|bending|radius|rmin|dynamic|static|weight|kg\s*/\s*m|bar|dn|min\.?|max\.?)$",
    re.IGNORECASE,
)
HEADER_TOKEN_FRAGMENT_RE = re.compile(r"^(?:[dls]\s*\d(?:\)\s*\d+)?|r\s*min)$", re.IGNORECASE)
DATE_PREFIX_HEADING_RE = re.compile(r"^\d{2}\.\d{2}\.\d{2}\s+(Shape\s+[A-Z])$", re.IGNORECASE)
NUMERIC_PREFIX_HEADING_RE = re.compile(r"^\d{3,4}\s+(Admissible length deviation)$", re.IGNORECASE)
SCAN_TEXT_RE = re.compile(r"[A-Za-z\u4e00-\u9fff]")
DATE_LIKE_RE = re.compile(r"\b\d{4}(?:[-—–/.]{1,2}\d{1,2}){1,2}\b")
METADATA_PARAM_RE = re.compile(r"(?:分类号|发布|实施|代替|计划项目代号|标准编号|版本日期|ICS)", re.IGNORECASE)
SPEC_TOKEN_RE = re.compile(
    r"(?:PN\s*\d+(?:[.,]\d+)?|M\d+(?:X\d+(?:[.,]\d+)?)?|DN\s*\d+|\d+(?:[.,]\d+)?\s*(?:MPa|bar|mm|cm|m|kg|g|℃|°C|%))",
    re.IGNORECASE,
)
SENTENCE_DATA_CUE_RE = re.compile(r"[，、；。]|(?:为|按|采用|公称|通径|规格|尺寸|材料)")
LEADING_NUMERIC_CJK_GLUE_RE = re.compile(r"^(?:[+\-]|≤|≥|<|>|=|±)?\s*\d+(?:[.,]\d+)?(?=[\u4e00-\u9fff])")
SENTENCE_HEADING_CUE_RE = re.compile(r"(?:应|必须|不得|不允许|注明|持续时间|内容|说明|采用|关闭|打开|提交|进行)")
PURE_NUMERIC_VALUE_RE = re.compile(
    r"^(?:[+\-]|≤|≥|<|>|=|±)?\s*\d+(?:[.,]\d+)?(?:\s*(?:MPa|kPa|Pa|mm|cm|m|μm|µm|um|bar|psi|°C|℃|K|%|A/m|N/mm2|N/mm²|kN/m2|kg|g|°))?$",
    re.IGNORECASE,
)
DIMENSION_VALUE_RE = re.compile(
    r"^\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?){1,3}(?:\s*(?:MPa|kPa|Pa|mm|cm|m|μm|µm|um|bar|psi|°C|℃|K|%|A/m|N/mm2|N/mm²|kN/m2|kg|g|°))?$",
    re.IGNORECASE,
)
CODE_LIKE_VALUE_RE = re.compile(r"^[A-Za-z]{1,8}\d+(?:[-—–/][A-Za-z0-9.]+)+$", re.IGNORECASE)
COMMON_SHORT_CJK_HEADING_RE = re.compile(
    r"^(?:范围|前言|术语|定义|要求|代号|分类|标记|包装|运输|贮存|材料|尺寸|结构|检验|试验|说明|附录|引用文件|规范性引用文件)$"
)
UNIT_ONLY_FRAGMENT_RE = re.compile(r"^[()（）\[\]]*(?:mm|cm|m|kg|g|℃|°C|bar|MPa|kPa|Pa|DN|PN|个)[()（）\[\]]*[；;。.]?$", re.IGNORECASE)
LETTER_MARKER_RE = re.compile(r"^[A-Za-z][.)]?$")


class UniversalPDFParser:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.cleaner = LineCleaner(config)

    def parse(self) -> DocumentData:
        fitz_doc, plumber_doc = open_pdf(self.config.input_path)
        try:
            raw_pages = self._extract_pages(fitz_doc, plumber_doc)
            repeated_noise = detect_repeated_noise([page["lines"] for page in raw_pages], min_repeat=max(2, len(raw_pages) // 2))
            cleaned_pages = self._clean_pages(raw_pages, repeated_noise)
            page_tables = self._extract_page_tables(plumber_doc)
            profile = profile_document(self.config.input_path.name, cleaned_pages, page_tables)
            metadata = self._extract_metadata(cleaned_pages, profile)
            blocks = self._extract_blocks(cleaned_pages, profile, page_tables)
            sections = self._build_sections(blocks, cleaned_pages)
            tables = self._extract_tables(page_tables, cleaned_pages, sections)
            self._attach_table_sections(tables, sections)
            sections = self._prune_empty_table_title_sections(sections, tables)
            standards = self._extract_standards(cleaned_pages, blocks, tables, sections)
            numeric_parameters = self._extract_numeric_parameters(tables, sections)
            rules = self._extract_rules(blocks)
            inspections = self._extract_inspections(blocks)
            products = self._extract_products(blocks, profile)
            metadata.标准编号 = metadata.标准编号 or self._pick_standard_code(standards)
            metadata.适用范围 = self._extract_scope(sections, blocks)

            document = DocumentData(
                文件元数据=metadata,
                原始页面列表=cleaned_pages,
                章节列表=sections,
                表格列表=tables,
                数值参数列表=numeric_parameters,
                规则列表=rules,
                检验列表=inspections,
                引用标准列表=standards,
                内容块列表=blocks,
                文档画像=profile,
            )
            document.页面列表 = self._build_page_records(cleaned_pages)
            if document.文档画像:
                ocr_attempted_pages = [page for page in document.页面列表 if page.是否执行OCR]
                ocr_injected_pages = [page for page in ocr_attempted_pages if page.OCR是否注入解析]
                document.文档画像.是否执行过OCR = bool(ocr_attempted_pages)
                document.文档画像.OCR尝试页数 = len(ocr_attempted_pages)
                document.文档画像.OCR注入页数 = len(ocr_injected_pages)
            document.产品列表 = products
            document.结构节点列表 = self._build_structure_nodes(sections, products)
            self._enrich_parameters(document.数值参数列表, products)
            self._enrich_rules(document.规则列表)
            self._enrich_standards(document.引用标准列表)
            return document
        finally:
            plumber_doc.close()
            fitz_doc.close()

    def _extract_pages(self, fitz_doc: Any, plumber_doc: Any) -> list[dict[str, Any]]:
        force_ocr_pages: dict[int, str] = getattr(self.config, "force_ocr_pages", {}) or {}
        pages: list[dict[str, Any]] = []
        for page_index in range(len(fitz_doc)):
            fitz_page = fitz_doc.load_page(page_index)
            ocr_text = force_ocr_pages.get(page_index, "")
            ocr_used = bool(ocr_text)
            if ocr_used:
                text = ocr_text
            else:
                text = fitz_page.get_text("text") or ""
                if not text and page_index < len(plumber_doc.pages):
                    text = plumber_doc.pages[page_index].extract_text() or ""
            lines = [normalize_line(line) for line in text.splitlines() if normalize_line(line)]
            pages.append(
                {
                    "page_index": page_index,
                    "width": float(fitz_page.rect.width),
                    "height": float(fitz_page.rect.height),
                    "lines": lines,
                    "ocr_used": ocr_used,
                }
            )
        return pages

    def _clean_pages(self, raw_pages: list[dict[str, Any]], repeated_noise: set[str]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for page in raw_pages:
            cleaned.append(
                {
                    "page_index": page["page_index"],
                    "width": page["width"],
                    "height": page["height"],
                    "lines": self.cleaner.clean_lines(page["lines"], repeated_noise),
                    "ocr_used": bool(page.get("ocr_used", False)),
                }
            )
        return cleaned

    def _extract_page_tables(self, plumber_doc: Any) -> dict[int, list[list[list[str]]]]:
        page_tables: dict[int, list[list[list[str]]]] = {}
        for page_index, page in enumerate(plumber_doc.pages):
            cleaned_tables: list[list[list[str]]] = []
            for table in page.extract_tables() or []:
                cleaned_rows: list[list[str]] = []
                for row in table or []:
                    clean_row = [normalize_cell(cell) for cell in row]
                    if any(clean_row):
                        cleaned_rows.append(clean_row)
                if cleaned_rows:
                    cleaned_tables.append(cleaned_rows)
            page_tables[page_index] = cleaned_tables
        return page_tables

    def _extract_metadata(self, pages: list[dict[str, Any]], profile: Any) -> FileMetadata:
        first_lines: list[str] = []
        for page in pages[:2]:
            first_lines.extend(page["lines"][:12])
        title = self._pick_document_title(first_lines)
        standard_code = ""
        for line in first_lines:
            match = STANDARD_RE.search(line)
            if match:
                standard_code = normalize_line(match.group(1))
                break
        return FileMetadata(
            文件名称=self.config.input_path.name,
            文件类型=self.config.input_path.suffix.lstrip(".").lower(),
            文档标题=title or self.config.input_path.stem,
            文档类型=self._profile_label(profile),
            标准编号=standard_code,
            版本日期=self._pick_version_date(first_lines),
            适用范围="",
        )

    def _pick_document_title(self, lines: list[str]) -> str:
        for line in lines:
            if not line or len(line) < 3:
                continue
            if STANDARD_RE.fullmatch(line):
                continue
            if NUMBERED_HEADING_RE.match(line):
                continue
            if GENERIC_NOISE_HEADING_RE.match(line):
                continue
            if re.match(r"^\w+\s+\d{4}$", line):
                continue
            return line
        return self.config.input_path.stem

    def _pick_version_date(self, lines: list[str]) -> str:
        patterns = [
            re.compile(r"\b\d{4}-\d{2}\b"),
            re.compile(r"\b\d{4}/\d{2}\b"),
            re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b", re.IGNORECASE),
            re.compile(r"\b(?:Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}\b", re.IGNORECASE),
        ]
        for line in lines:
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    return normalize_line(match.group(0))
        return ""

    def _extract_blocks(
        self,
        pages: list[dict[str, Any]],
        profile: Any,
        page_tables: dict[int, list[list[list[str]]]],
    ) -> list[BlockRecord]:
        blocks: list[BlockRecord] = []
        for page in pages:
            page_index = page["page_index"]
            page_table_cells = self._build_page_table_cell_set(page_tables.get(page_index, []))
            page_ocr_fragmented = self._is_fragmented_ocr_page(page_index)
            lines = page["lines"]
            idx = 0
            while idx < len(lines):
                line = lines[idx]
                prev_line = lines[idx - 1] if idx > 0 else ""
                next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
                after_next = lines[idx + 2] if idx + 2 < len(lines) else ""
                merged_heading = self._merge_split_heading(line, next_line, profile, page_table_cells)
                line = merged_heading or line
                line = self._strip_heading_noise_prefix(line)
                lookahead = after_next if merged_heading else next_line
                consumed = 2 if merged_heading else 1
                idx += consumed
                block_type = self._classify_line(
                    line,
                    prev_line,
                    lookahead,
                    profile,
                    page_table_cells,
                    bool(page.get("ocr_used", False)),
                    page_ocr_fragmented,
                )
                if block_type == "跳过":
                    continue
                blocks.append(
                    BlockRecord(
                        块类型=block_type,
                        标题=line if block_type == "标题" else "",
                        内容=line,
                        来源页码=page_index + 1,
                    )
                )
        return blocks

    def _is_fragmented_ocr_page(self, page_index: int) -> bool:
        page_eval_map: dict[int, dict[str, Any]] = getattr(self.config, "ocr_page_evaluations", {}) or {}
        page_eval = page_eval_map.get(page_index) or {}
        if not page_eval or not bool(page_eval.get("是否注入解析", False)):
            return False
        reasons = " ".join(str(item) for item in page_eval.get("判定原因", []) if str(item))
        return (
            float(page_eval.get("单字符碎片率", 0.0) or 0.0) >= 0.18
            or float(page_eval.get("重复行率", 0.0) or 0.0) >= 0.18
            or float(page_eval.get("标点噪音率", 0.0) or 0.0) >= 0.32
            or str(page_eval.get("评估等级", "")) == "边缘"
            or "碎片化特征命中" in reasons
            or "评级降档" in reasons
        )

    def _merge_split_heading(
        self,
        line: str,
        next_line: str,
        profile: Any,
        page_table_cells: set[str],
    ) -> str | None:
        number = normalize_line(line)
        title = normalize_line(next_line.rstrip(":锛?"))
        if not SPLIT_HEADING_NUMBER_RE.fullmatch(number):
            return None
        if not title or len(title) > 100:
            return None
        if self._looks_like_heading_fragment(title):
            return None
        if self._looks_like_table_fragment(title, page_table_cells):
            return None
        if self._looks_like_standard_line(title):
            return None
        if PAGE_HEADER_NOISE_RE.fullmatch(title):
            return None
        if DOC_VERSION_RE.fullmatch(title):
            return None
        if FOOTNOTE_CONTINUE_RE.fullmatch(title):
            return None
        if len(title.split()) > max(self.config.max_heading_words + 2, 8):
            return None
        if LOWERCASE_FRAGMENT_RE.match(title):
            return None
        return f"{number} {title}"

    def _strip_heading_noise_prefix(self, line: str) -> str:
        normalized = normalize_line(line)
        date_prefixed = DATE_PREFIX_HEADING_RE.match(normalized)
        if date_prefixed:
            return normalize_line(date_prefixed.group(1))
        numeric_prefixed = NUMERIC_PREFIX_HEADING_RE.match(normalized)
        if numeric_prefixed:
            return normalize_line(numeric_prefixed.group(1))
        return line

    def _build_page_table_cell_set(self, tables: list[list[list[str]]]) -> set[str]:
        return {normalize_line(cell) for table in tables for row in table for cell in row if normalize_line(cell)}

    def _classify_line(
        self,
        line: str,
        prev_line: str,
        next_line: str,
        profile: Any,
        page_table_cells: set[str],
        page_ocr_used: bool = False,
        page_ocr_fragmented: bool = False,
    ) -> str:
        normalized = normalize_line(line)
        if not normalized:
            return "跳过"
        if LEGAL_NOTICE_RE.search(normalized):
            return "跳过"
        if BOILERPLATE_FRAGMENT_RE.search(normalized):
            return "跳过"
        if ADVERTISEMENT_NOISE_RE.search(normalized):
            return "跳过"
        if CORPORATE_NOTICE_RE.search(normalized):
            return "跳过"
        if PAGE_HEADER_NOISE_RE.fullmatch(normalized):
            return "跳过"
        if METADATA_PREFIX_RE.match(normalized):
            return "跳过"
        if FOOTNOTE_CONTINUE_RE.fullmatch(normalized):
            return "跳过"
        if DOC_VERSION_RE.fullmatch(normalized):
            return "跳过"
        if ICS_RE.fullmatch(normalized):
            return "跳过"
        if self._looks_like_toc_line(normalized):
            return "跳过"
        if METADATA_LABEL_RE.match(normalized):
            return "跳过"
        if TOTAL_PAGES_RE.match(normalized):
            return "跳过"
        if EDITION_HEADER_RE.match(normalized):
            return "跳过"
        if self._looks_like_part_heading(normalized):
            return "部分标题"
        if self._looks_like_heading(normalized, prev_line, next_line, profile, page_table_cells, page_ocr_used, page_ocr_fragmented):
            return "标题"
        if self._looks_like_standard_line(normalized):
            return "标准引用"
        if REVISION_RE.search(normalized):
            return "修订记录"
        if self._looks_like_caption(normalized):
            return "图示说明"
        if self._looks_like_table_fragment(normalized, page_table_cells):
            return "表格碎片"
        return "正文"

    def _looks_like_part_heading(self, line: str) -> bool:
        return bool(PART_HEADING_RE.match(line))

    def _looks_like_toc_line(self, line: str) -> bool:
        normalized = normalize_line(line)
        if not normalized:
            return False
        lowered = normalized.casefold()
        if TOC_LINE_RE.search(normalized):
            return True
        if lowered in {"contents", "inhalt", "目录"}:
            return True
        if TOC_HEADER_RE.search(normalized) and any(ch.isdigit() for ch in normalized):
            return True
        if lowered.endswith(" contents") or lowered.endswith(" inhalt"):
            return True
        return False

    def _looks_like_heading(
        self,
        line: str,
        prev_line: str,
        next_line: str,
        profile: Any,
        page_table_cells: set[str],
        page_ocr_used: bool = False,
        page_ocr_fragmented: bool = False,
    ) -> bool:
        candidate = line.rstrip(":：").strip()
        if not candidate or len(candidate) > 100:
            return False
        if candidate in self.config.banned_heading_exact:
            return False
        if GENERIC_NOISE_HEADING_RE.match(candidate):
            return False
        if PAGE_HEADER_NOISE_RE.fullmatch(candidate):
            return False
        if NOISE_MARKER_RE.match(candidate):
            return False
        if DOC_VERSION_RE.fullmatch(candidate):
            return False
        if ICS_RE.fullmatch(candidate):
            return False
        if CORPORATE_NOTICE_RE.search(candidate):
            return False
        if FOOTNOTE_CONTINUE_RE.fullmatch(candidate):
            return False
        if self._looks_like_standard_line(candidate):
            return False
        if self._looks_like_table_fragment(candidate, page_table_cells):
            return False
        if self._looks_like_heading_fragment(candidate):
            return False
        if self._looks_like_metadata_line(candidate):
            return False
        if self._looks_like_ocr_noise_heading(candidate):
            return False
        if page_ocr_used and self._looks_like_ocr_fragment_heading(candidate):
            return False
        compact_candidate = re.sub(r"\s+", "", candidate)
        if (
            page_ocr_fragmented
            and len(compact_candidate) <= 6
            and not COMMON_SHORT_CJK_HEADING_RE.fullmatch(compact_candidate)
            and not GENERIC_SHORT_HEADING_RE.search(candidate)
        ):
            return False

        numbered = NUMBERED_HEADING_RE.match(candidate)
        if numbered:
            number = normalize_line(numbered.group(1))
            title = normalize_line(numbered.group(2))
            return (
                bool(title)
                and not self._looks_like_number_noise_heading(number, title)
                and not (
                    page_ocr_fragmented
                    and number.isdigit()
                    and int(number) >= 10
                    and len(re.sub(r"\s+", "", title)) <= 4
                )
                and len(title.split()) <= self.config.max_heading_words
                and not self._looks_like_table_fragment(title, page_table_cells)
                and not self._looks_like_heading_fragment(title)
                and not self._looks_like_metadata_line(title)
                and not self._looks_like_ocr_noise_heading(title)
                and not (page_ocr_used and self._looks_like_ocr_fragment_heading(title))
            )

        if re.fullmatch(r"(?:Form|Shape)\s+[A-Z0-9]+", candidate, re.IGNORECASE):
            return True
        if TABLE_CAPTION_RE.match(candidate) or FIGURE_CAPTION_RE.match(candidate):
            return False
        if GENERIC_SHORT_HEADING_RE.search(candidate):
            return True
        if line.endswith((":", "：")) and len(candidate.split()) <= self.config.max_heading_words:
            return True
        if (
            1 <= len(candidate.split()) <= 6
            and next_line
            and len(next_line) > len(candidate) + 12
            and not prev_line.endswith((".", ";", ":", "："))
            and not self._looks_like_ocr_noise_heading(candidate)
        ):
            return True
        if profile.语言 in {"en", "de"} and candidate.isupper() and len(candidate.split()) <= 8:
            return True
        return False

    def _looks_like_heading_fragment(self, line: str) -> bool:
        candidate = normalize_line(line)
        if not candidate:
            return False
        if self._looks_like_metadata_line(candidate):
            return True
        if self._looks_like_ocr_noise_heading(candidate):
            return True
        if ADVERTISEMENT_NOISE_RE.search(candidate):
            return True
        if candidate[0] in "(+-≤≥":
            return True
        if candidate.endswith(("-", "/")):
            return True
        if LEADING_CONJUNCTION_RE.match(candidate):
            return True
        if LOWERCASE_FRAGMENT_RE.match(candidate):
            return True
        if SECTION_NUMBER_ONLY_RE.fullmatch(candidate):
            return True
        if SHORT_TOKEN_RE.fullmatch(candidate):
            return True
        if LETTER_RANGE_RE.fullmatch(candidate):
            return True
        if VALUE_FRAGMENT_RE.fullmatch(candidate):
            return True
        if SENTENCE_VERB_RE.search(candidate) and len(candidate.split()) >= 3:
            return True
        if candidate.endswith((".", ",", ";")) and len(candidate.split()) >= 2:
            return True
        if candidate.count("(") != candidate.count(")"):
            return True
        return False

    def _looks_like_metadata_line(self, text: str) -> bool:
        candidate = normalize_line(text)
        if not candidate:
            return False
        return bool(METADATA_PARAM_RE.search(candidate) or DATE_LIKE_RE.search(candidate))

    def _looks_like_ocr_noise_heading(self, text: str) -> bool:
        candidate = normalize_line(text)
        if not candidate:
            return False
        if LEADING_NUMERIC_CJK_GLUE_RE.match(candidate):
            return True
        if len(candidate) >= 12 and SENTENCE_HEADING_CUE_RE.search(candidate) and (SENTENCE_DATA_CUE_RE.search(candidate) or re.search(r"\d", candidate)):
            return True
        digit_count = sum(char.isdigit() for char in candidate)
        spec_hits = len(SPEC_TOKEN_RE.findall(candidate))
        if digit_count >= 4 and spec_hits >= 1:
            return True
        if digit_count >= 5 and SENTENCE_DATA_CUE_RE.search(candidate):
            return True
        if len(candidate) >= 18 and SENTENCE_DATA_CUE_RE.search(candidate) and digit_count >= 2:
            return True
        if candidate.count(" ") <= 1 and spec_hits >= 2:
            return True
        return False

    def _looks_like_ocr_fragment_heading(self, text: str) -> bool:
        candidate = normalize_line(text)
        if not candidate:
            return False
        stripped = candidate.strip()
        if UNIT_ONLY_FRAGMENT_RE.fullmatch(stripped):
            return True
        if LETTER_MARKER_RE.fullmatch(stripped):
            return True
        if stripped and stripped[-1] in "。，；：．":
            return True
        if re.search(r"[的是为被及与和或]", stripped):
            return True
        compact = re.sub(r"\s+", "", stripped)
        # 关键修正：纯 2-3 字 CJK 标题（如"范围""要求"）不算片段
        if len(compact) < 4 and not re.fullmatch(r"[\u4e00-\u9fff]{2,3}", compact):
            return True
        if compact and not re.search(r"[\u4e00-\u9fffA-Za-z]", compact):
            return True
        if compact.count("(") != compact.count(")"):
            return True
        return False

    def _looks_like_number_noise_heading(self, number: str, title: str) -> bool:
        parts = [part for part in number.split(".") if part]
        if len(parts) >= 3 and all(part.isdigit() and len(part) <= 2 for part in parts):
            return True
        if len(parts) == 2 and parts[1] == "0" and parts[0].isdigit() and int(parts[0]) >= 10:
            return True
        if number.isdigit() and len(number) >= 4:
            return True
        if FOOTNOTE_MARKER_RE.fullmatch(number):
            return True
        if title.casefold() == "shape d" and len(parts) >= 3:
            return True
        # §2.1 表格行噪音：浮点章节号（如 "20.0"、"25.0"）配一段数字尾巴或连续章节号开头
        # —— 这是表格单元把"数值+尾字"被当作章节的典型模式，一律拒绝。
        if (
            len(parts) == 2
            and parts[1] == "0"
            and parts[0].isdigit()
            and int(parts[0]) >= 20
        ):
            return True
        # §2.1 型号特征混在标题里（如 "74 M27X1.5"、"56 M39X2"）——螺纹/型号代号
        if re.search(r"\bM\d{2,3}[Xx×][\d.]+", title):
            return True
        # §2.1 单个 "0"/"*" 这种纯符号/零章节 → 拒绝
        if number == "0" or all(ch in "*·•●■◆" for ch in title.strip()):
            return True
        return False

    def _looks_like_standard_line(self, line: str) -> bool:
        if not STANDARD_RE.findall(line):
            return False
        return not NUMBERED_HEADING_RE.match(line) and len(line) <= 180

    def _looks_like_caption(self, line: str) -> bool:
        return bool(TABLE_CAPTION_RE.match(line) or FIGURE_CAPTION_RE.match(line) or re.match(r"^(?:Legend|Symbol|图例|符号|说明)\b", line, re.IGNORECASE))

    def _looks_like_table_fragment(self, line: str, page_table_cells: set[str]) -> bool:
        normalized = normalize_line(line)
        if not normalized:
            return False
        if normalized in page_table_cells and len(normalized) <= 120:
            return True
        if NOISE_MARKER_RE.match(normalized):
            return True
        if FOOTNOTE_CONTINUE_RE.fullmatch(normalized):
            return True
        if normalized.endswith(("-", "/")):
            return True
        if LEADING_CONJUNCTION_RE.match(normalized):
            return True
        if SHORT_TOKEN_RE.fullmatch(normalized):
            return True
        if LETTER_RANGE_RE.fullmatch(normalized):
            return True
        if VALUE_FRAGMENT_RE.fullmatch(normalized):
            return True
        if FOOTNOTE_MARKER_RE.fullmatch(normalized):
            return True
        if TABLE_HEADER_FRAGMENT_RE.fullmatch(normalized):
            return True
        if HEADER_TOKEN_FRAGMENT_RE.fullmatch(normalized):
            return True
        if SENTENCE_VERB_RE.search(normalized) and len(normalized.split()) >= 3:
            return True
        if LOWERCASE_FRAGMENT_RE.match(normalized) and len(normalized) <= 40 and len(normalized.split()) <= 5:
            return True
        if re.match(r"^\d+(?:\s+\d+){2,}$", normalized):
            return True
        if HEADER_VALUE_RE.fullmatch(normalized):
            return True
        if len(re.findall(r"\d", normalized)) >= 3 and len(normalized) <= 40 and not SCAN_TEXT_RE.search(normalized.replace(" ", "")):
            return True
        if re.search(r"\bDN\b", normalized) and len(normalized.split()) >= 3:
            return True
        return False

    def _build_sections(self, blocks: list[BlockRecord], pages: list[dict[str, Any]]) -> list[SectionRecord]:
        sections: list[SectionRecord] = []
        current_section: SectionRecord | None = None
        current_part = ""
        synthetic_counter = 0

        for block in blocks:
            line = block.内容
            if block.块类型 == "部分标题":
                current_part = line
                block.所属部分 = current_part
                continue
            if block.块类型 == "标题":
                if current_section and self._should_absorb_heading_into_section(current_section, line):
                    block.所属部分 = current_part
                    block.所属章节 = self._section_ref(current_section)
                    current_section.章节清洗文本 = self._append_line(current_section.章节清洗文本, line)
                    continue
                numbered = NUMBERED_HEADING_RE.match(line)
                if numbered:
                    number = normalize_line(numbered.group(1))
                    title = normalize_line(numbered.group(2))
                    level = number.count(".") + 1
                    parent_number = ".".join(number.split(".")[:-1]) if "." in number else ""
                else:
                    synthetic_counter += 1
                    number = f"U{synthetic_counter}"
                    title = normalize_line(line.rstrip(":："))
                    level = 1
                    parent_number = ""
                current_section = SectionRecord(
                    章节编号=number,
                    章节标题=title or number,
                    章节层级=level,
                    父章节编号=parent_number,
                    章节清洗文本="",
                    所属部分=current_part,
                )
                sections.append(current_section)
                block.所属部分 = current_part
                block.所属章节 = self._section_ref(current_section)
                continue
            if block.块类型 in {"正文", "标准引用", "图示说明", "修订记录"}:
                if current_section is None:
                    synthetic_counter += 1
                    title = "概述" if synthetic_counter == 1 else f"页面{block.来源页码}内容"
                    current_section = SectionRecord(
                        章节编号=f"U{synthetic_counter}",
                        章节标题=title,
                        章节层级=1,
                        父章节编号="",
                        章节清洗文本="",
                        所属部分=current_part,
                    )
                    sections.append(current_section)
                block.所属部分 = current_part
                block.所属章节 = self._section_ref(current_section)
                if block.块类型 in {"正文", "标准引用"}:
                    current_section.章节清洗文本 = self._append_line(current_section.章节清洗文本, line)

        if not sections:
            sections = self._build_page_sections(pages)
            self._backfill_block_sections(blocks, sections)
        return self._cleanup_sections(sections)

    def _should_absorb_heading_into_section(self, current_section: SectionRecord, line: str) -> bool:
        numbered = NUMBERED_HEADING_RE.match(line)
        if numbered:
            return False
        section_title = normalize_line(current_section.章节标题)
        candidate = normalize_line(line.rstrip(":："))
        if not section_title or not candidate:
            return False
        if REFERENCE_SECTION_TITLE_RE.fullmatch(section_title):
            return True
        if REVISION_SECTION_TITLE_RE.fullmatch(section_title):
            if candidate.endswith(",") or SENTENCE_VERB_RE.search(candidate) or len(candidate.split()) >= 3:
                return True
        return False

    def _build_page_sections(self, pages: list[dict[str, Any]]) -> list[SectionRecord]:
        sections: list[SectionRecord] = []
        for idx, page in enumerate(pages, 1):
            text_lines = [line for line in page["lines"] if line and not self._looks_like_table_fragment(line, set())]
            if not text_lines:
                continue
            sections.append(
                SectionRecord(
                    章节编号=f"U{idx}",
                    章节标题="概述" if idx == 1 else f"页面{idx}内容",
                    章节层级=1,
                    章节清洗文本="\n".join(text_lines[:40]),
                )
            )
        return sections

    def _backfill_block_sections(self, blocks: list[BlockRecord], sections: list[SectionRecord]) -> None:
        if not sections:
            return
        default_ref = self._section_ref(sections[0])
        for block in blocks:
            if block.块类型 != "部分标题" and not block.所属章节:
                block.所属章节 = default_ref

    def _cleanup_sections(self, sections: list[SectionRecord]) -> list[SectionRecord]:
        cleaned: list[SectionRecord] = []
        seen: set[tuple[str, str]] = set()
        for section in sections:
            section.章节标题 = normalize_line(section.章节标题)
            section.章节清洗文本 = "\n".join(self._dedupe_lines(section.章节清洗文本.splitlines()))
            key = (section.章节编号, section.章节标题)
            if key in seen:
                continue
            seen.add(key)
            if section.章节标题 or section.章节清洗文本:
                cleaned.append(section)
        return cleaned

    def _dedupe_lines(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for line in lines:
            normalized = normalize_line(line)
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)
        return out

    def _append_line(self, current: str, line: str) -> str:
        line = normalize_line(line)
        if not line:
            return current
        if not current:
            return line
        if current.splitlines() and current.splitlines()[-1] == line:
            return current
        return f"{current}\n{line}"

    def _extract_tables(
        self,
        page_tables: dict[int, list[list[list[str]]]],
        pages: list[dict[str, Any]],
        sections: list[SectionRecord],
    ) -> list[TableRecord]:
        tables: list[TableRecord] = []
        page_to_section = self._build_page_to_section_map(sections, pages)
        for page_index, tables_on_page in page_tables.items():
            page_lines = pages[page_index]["lines"] if page_index < len(pages) else []
            for table_idx, table in enumerate(tables_on_page, start=1):
                if not self._is_valid_table(table):
                    continue
                title = self._pick_table_title(page_lines, table_idx)
                header, body = self._split_table_header_body(table)
                tables.append(
                    TableRecord(
                        表格编号=f"第{page_index + 1}页_表{table_idx}",
                        表格标题=title or f"第{page_index + 1}页表{table_idx}",
                        所属章节=page_to_section.get(page_index, ""),
                        表头=header,
                        表体=body,
                    )
                )
        return self._dedupe_tables(tables)

    def _build_page_to_section_map(self, sections: list[SectionRecord], pages: list[dict[str, Any]]) -> dict[int, str]:
        mapping: dict[int, str] = {}
        if not sections:
            return mapping
        current_index = 0
        current_ref = self._section_ref(sections[0])
        for page in pages:
            page_lines = {
                normalize_line(line)
                for line in page["lines"]
                if normalize_line(line)
                and not self._looks_like_toc_line(line)
                and not PAGE_HEADER_NOISE_RE.fullmatch(normalize_line(line))
            }
            while current_index + 1 < len(sections):
                next_section = sections[current_index + 1]
                next_title = normalize_line(next_section.章节标题)
                if not next_title or next_title not in page_lines:
                    break
                current_index += 1
                current_ref = self._section_ref(next_section)
            mapping[page["page_index"]] = current_ref
        return mapping

    def _pick_table_title(self, page_lines: list[str], table_idx: int) -> str:
        candidates = [
            line
            for line in page_lines
            if TABLE_CAPTION_RE.match(line)
            or GENERIC_SHORT_HEADING_RE.search(line)
            or re.fullmatch(r"(?:Form|Shape)\s+[A-Z0-9]+", line, re.IGNORECASE)
        ]
        if len(candidates) >= table_idx:
            picked = normalize_line(candidates[table_idx - 1])
            if not LOW_SIGNAL_TABLE_TITLE_RE.fullmatch(picked):
                return picked
        for candidate in candidates:
            picked = normalize_line(candidate)
            if picked and not LOW_SIGNAL_TABLE_TITLE_RE.fullmatch(picked):
                return picked
        return ""

    def _is_valid_table(self, table: list[list[str]]) -> bool:
        non_empty_cells = sum(1 for row in table for cell in row if normalize_cell(cell))
        return non_empty_cells >= 4

    def _split_table_header_body(self, table: list[list[str]]) -> tuple[list[str], list[list[str]]]:
        if not table:
            return [], []
        header = [normalize_cell(cell) for cell in table[0]]
        body = [[normalize_cell(cell) for cell in row] for row in table[1:]]
        return header, body

    def _dedupe_tables(self, tables: list[TableRecord]) -> list[TableRecord]:
        unique: dict[tuple[str, str, str], TableRecord] = {}
        for table in tables:
            sig = (table.所属章节, table.表格标题, "|".join(table.表头[:6]))
            current = unique.get(sig)
            current_size = len(current.表头) + sum(len(row) for row in current.表体) if current else -1
            new_size = len(table.表头) + sum(len(row) for row in table.表体)
            if current is None or new_size > current_size:
                unique[sig] = table
        return list(unique.values())

    def _attach_table_sections(self, tables: list[TableRecord], sections: list[SectionRecord]) -> None:
        fallback = self._section_ref(sections[0]) if sections else ""
        for table in tables:
            if not table.所属章节:
                table.所属章节 = fallback

    def _prune_empty_table_title_sections(self, sections: list[SectionRecord], tables: list[TableRecord]) -> list[SectionRecord]:
        table_titles = {normalize_line(table.表格标题).casefold() for table in tables if normalize_line(table.表格标题)}
        table_section_refs = {normalize_line(table.所属章节) for table in tables if normalize_line(table.所属章节)}
        cleaned: list[SectionRecord] = []
        for section in sections:
            section_id = normalize_line(section.章节编号)
            section_title = normalize_line(section.章节标题)
            section_ref = self._section_ref(section)
            has_body = bool(normalize_line(section.章节清洗文本))
            if (
                section_id.startswith("U")
                and not has_body
                and section_title.casefold() in table_titles
                and normalize_line(section_ref) not in table_section_refs
            ):
                continue
            cleaned.append(section)
        return cleaned

    def _extract_standards(
        self,
        pages: list[dict[str, Any]],
        blocks: list[BlockRecord],
        tables: list[TableRecord],
        sections: list[SectionRecord],
    ) -> list[StandardReference]:
        references: list[StandardReference] = []
        seen: set[tuple[str, str]] = set()
        candidates: list[tuple[str, str]] = []
        for block in blocks:
            candidates.append((block.内容, block.所属章节))
        for table in tables:
            candidates.append((table.表格标题, table.所属章节))
            for row in [table.表头] + table.表体:
                candidates.append((" ".join(row), table.所属章节))
        for page in pages:
            page_ref = self._page_section_guess(page["lines"], sections)
            for line in page["lines"]:
                candidates.append((line, page_ref))

        for text, section_ref in candidates:
            if self._looks_like_front_matter_context(text, section_ref):
                continue
            for match in STANDARD_RE.findall(text):
                code = normalize_line(match)
                key = (code, section_ref)
                if key in seen:
                    continue
                seen.add(key)
                references.append(
                    StandardReference(
                        标准编号=code,
                        标准名称=normalize_line(text) if len(normalize_line(text)) <= 160 else "",
                        标准类型=self._classify_standard_family(code),
                        所属章节=section_ref,
                    )
                )
        return references

    def _page_section_guess(self, page_lines: list[str], sections: list[SectionRecord]) -> str:
        text = "\n".join(page_lines)
        for section in sections:
            if section.章节标题 and section.章节标题 in text:
                return self._section_ref(section)
        return self._section_ref(sections[0]) if sections else ""

    def _looks_like_front_matter_context(self, *parts: str) -> bool:
        merged = normalize_line(" ".join(part for part in parts if part))
        if not merged:
            return False
        if FRONT_MATTER_CUE_RE.search(merged):
            return True
        if FRONT_MATTER_SECTION_RE.search(merged):
            return True
        return False

    def _extract_numeric_parameters(self, tables: list[TableRecord], sections: list[SectionRecord]) -> list[NumericParameter]:
        params: list[NumericParameter] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for table in tables:
            for param in self._extract_parameters_from_table(table):
                key = (param.参数名称, param.参数值清洗值, param.适用条件, param.所属章节, param.来源表格)
                if key not in seen:
                    seen.add(key)
                    params.append(param)
        for section in sections:
            lines = [normalize_line(line) for line in section.章节清洗文本.splitlines() if normalize_line(line)]
            for idx, line in enumerate(lines):
                param = self._extract_parameter_from_text_line(line, lines[idx - 1] if idx > 0 else "", section)
                if not param:
                    continue
                key = (param.参数名称, param.参数值清洗值, param.适用条件, param.所属章节, param.来源表格)
                if key not in seen:
                    seen.add(key)
                    params.append(param)
        return params

    def _extract_parameters_from_table(self, table: TableRecord) -> list[NumericParameter]:
        headers = [normalize_line(cell) for cell in table.表头]
        body = [[normalize_line(cell) for cell in row] for row in table.表体]
        if not headers and body:
            headers = body[0]
            body = body[1:]

        params: list[NumericParameter] = []
        model_columns = self._find_model_columns(headers, body)
        if model_columns:
            params.extend(self._extract_model_table_parameters(table, headers, body, model_columns))
        params.extend(self._extract_matrix_table_parameters(table, headers, body))
        params.extend(self._extract_key_value_table_parameters(table, headers, body))

        unique: dict[tuple[str, str, str, str, str], NumericParameter] = {}
        for param in params:
            if param:
                key = (param.参数名称, param.参数值清洗值, param.适用条件, param.所属章节, param.来源表格)
                unique[key] = param
        return list(unique.values())

    def _find_model_columns(self, headers: list[str], body: list[list[str]]) -> list[tuple[int, str]]:
        candidates = self._extract_model_columns_from_cells(headers)
        if candidates:
            return candidates
        for row in body[:2]:
            candidates = self._extract_model_columns_from_cells(row)
            if candidates:
                return candidates
        return []

    def _extract_model_columns_from_cells(self, cells: list[str]) -> list[tuple[int, str]]:
        columns: list[tuple[int, str]] = []
        seen: set[str] = set()
        for idx, cell in enumerate(cells):
            if not cell:
                continue
            match = MODEL_RE.search(cell)
            if not match:
                continue
            label = normalize_line(match.group(0))
            if label not in seen:
                seen.add(label)
                columns.append((idx, label))
        return columns

    def _extract_model_table_parameters(
        self,
        table: TableRecord,
        headers: list[str],
        body: list[list[str]],
        model_columns: list[tuple[int, str]],
    ) -> list[NumericParameter]:
        params: list[NumericParameter] = []
        unit_col = self._find_unit_column(headers)
        for row in body:
            row_label = self._pick_row_label(row, model_columns, unit_col)
            if not row_label:
                continue
            unit_hint = row[unit_col] if unit_col is not None and unit_col < len(row) else ""
            for col_idx, model in model_columns:
                if col_idx >= len(row):
                    continue
                value = normalize_line(row[col_idx])
                if not self._looks_like_value(value):
                    continue
                param = self._make_param(
                    name=self._canonicalize_parameter_name(row_label, table.表格标题) or row_label,
                    value=value,
                    condition=model,
                    section_ref=table.所属章节 or table.表格标题,
                    table_name=table.表格标题,
                    source_item=row_label,
                    unit_hint=unit_hint,
                )
                if param:
                    params.append(param)
        return params

    def _extract_matrix_table_parameters(self, table: TableRecord, headers: list[str], body: list[list[str]]) -> list[NumericParameter]:
        params: list[NumericParameter] = []
        if len(headers) < 2 or not body:
            return params
        label_header = headers[0]
        usable_headers = [(idx, header) for idx, header in enumerate(headers[1:], start=1) if header and not self._looks_like_unit_token(header)]
        for row in body:
            if not row or not normalize_line(row[0]):
                continue
            condition = f"{label_header}={normalize_line(row[0])}" if label_header else normalize_line(row[0])
            for col_idx, header in usable_headers:
                if col_idx >= len(row):
                    continue
                value = normalize_line(row[col_idx])
                if not self._looks_like_value(value):
                    continue
                name = self._canonicalize_parameter_name(header, table.表格标题) or header
                param = self._make_param(
                    name=name,
                    value=value,
                    condition=condition if condition != name else "",
                    section_ref=table.所属章节 or table.表格标题,
                    table_name=table.表格标题,
                    source_item=header,
                )
                if param:
                    params.append(param)
        return params

    def _extract_key_value_table_parameters(self, table: TableRecord, headers: list[str], body: list[list[str]]) -> list[NumericParameter]:
        params: list[NumericParameter] = []
        context = f"{table.表格标题} {' '.join(headers)}"
        for row in body:
            if len(row) < 2:
                continue
            label = normalize_line(row[0])
            if not label or self._looks_like_value(label):
                continue
            value = ""
            condition_parts: list[str] = []
            for cell in row[1:]:
                cell = normalize_line(cell)
                if not cell:
                    continue
                if not value and self._looks_like_value(cell):
                    value = cell
                elif cell != value and len(cell) <= 40:
                    condition_parts.append(cell)
            if not value:
                continue
            name = self._canonicalize_parameter_name(label, context) or label
            param = self._make_param(
                name=name,
                value=value,
                condition=" / ".join(condition_parts[:2]),
                section_ref=table.所属章节 or table.表格标题,
                table_name=table.表格标题,
                source_item=label,
                unit_hint=self._infer_unit_from_context(context),
            )
            if param:
                params.append(param)
        return params

    def _find_unit_column(self, headers: list[str]) -> int | None:
        for idx, header in enumerate(headers):
            if self._looks_like_unit_token(header):
                return idx
        return None

    def _pick_row_label(self, row: list[str], model_columns: list[tuple[int, str]], unit_col: int | None) -> str:
        excluded = {idx for idx, _ in model_columns}
        if unit_col is not None:
            excluded.add(unit_col)
        for idx, cell in enumerate(row):
            if idx in excluded:
                continue
            cell = normalize_line(cell)
            if cell and not self._looks_like_value(cell):
                return cell
        return ""

    def _extract_parameter_from_text_line(self, line: str, previous_line: str, section: SectionRecord) -> NumericParameter | None:
        if len(line) > 160 or STANDARD_RE.search(line) or self._should_reject_parameter_candidate(line, line, section.章节标题):
            return None
        label = ""
        value = ""
        if ":" in line or "：" in line:
            left, right = re.split(r"[:：]", line, maxsplit=1)
            if self._looks_like_value(right):
                label = normalize_line(left)
                value = normalize_line(right)
        if not value:
            range_match = RANGE_RE.search(line)
            compare_match = COMPARE_RE.search(line)
            if range_match:
                value = normalize_line(range_match.group(0))
            elif compare_match:
                value = normalize_line(compare_match.group(0))
            else:
                return None
            label = self._canonicalize_parameter_name(line, section.章节标题) or self._guess_name_from_previous_line(previous_line)
        if not label:
            return None
        return self._make_param(
            name=label,
            value=value,
            condition="",
            section_ref=self._section_ref(section),
            table_name="",
            source_item=label,
        )

    def _guess_name_from_previous_line(self, previous_line: str) -> str:
        previous_line = normalize_line(previous_line)
        if previous_line and len(previous_line) <= 40 and not self._looks_like_value(previous_line):
            return previous_line
        return ""

    def _make_param(
        self,
        name: str,
        value: str,
        condition: str,
        section_ref: str,
        table_name: str,
        source_item: str,
        unit_hint: str = "",
    ) -> NumericParameter | None:
        name = normalize_line(name)
        value = normalize_line(value)
        if not name or not value or self._should_reject_parameter_candidate(name, value, f"{condition} {source_item} {section_ref}"):
            return None
        range_match = RANGE_RE.search(value)
        compare_match = COMPARE_RE.search(value)
        unit = ""
        lower = ""
        upper = ""
        comparator = ""
        clean_value = value
        if range_match:
            lower = range_match.group("lower").replace(",", ".")
            upper = range_match.group("upper").replace(",", ".")
            unit = self._normalize_unit(range_match.group("unit") or unit_hint)
            clean_value = f"{lower}~{upper}"
            comparator = "范围"
        elif compare_match:
            unit = self._normalize_unit(compare_match.group("unit") or unit_hint)
            clean_value = compare_match.group("value").replace(",", ".")
            comparator = compare_match.group("cmp")
        elif re.search(r"\d", value):
            unit = self._normalize_unit(unit_hint or self._infer_unit_from_context(value))
        else:
            return None
        return NumericParameter(
            参数名称=name,
            参数值清洗值=clean_value,
            参数单位=unit,
            参数范围下限=lower,
            参数范围上限=upper,
            比较符号=comparator,
            适用条件=normalize_line(condition),
            所属章节=section_ref,
            来源表格=table_name,
            来源子项=source_item,
        )

    def _normalize_unit(self, unit: str) -> str:
        unit = normalize_line(unit).replace("µ", "μ")
        mapping = {"um": "μm", "μm": "μm", "°c": "℃", "n/mm²": "N/mm2", "n/mm2": "N/mm2", "kn/m2": "kN/m2"}
        return mapping.get(unit.lower(), unit)

    def _infer_unit_from_context(self, text: str) -> str:
        match = UNIT_TOKEN_RE.search(text)
        return self._normalize_unit(match.group(0)) if match else ""

    def _looks_like_unit_token(self, text: str) -> bool:
        text = normalize_line(text)
        return bool(text) and bool(re.fullmatch(r"(unit|einheit|单位|mm|cm|m|μm|µm|um|bar|psi|°C|℃|K|%|A/m|N/mm2|N/mm²|kN/m2|kg|g|°)", text, re.IGNORECASE))

    def _looks_like_value(self, text: str) -> bool:
        text = normalize_line(text)
        if not text or DATE_LIKE_RE.search(text) or METADATA_PARAM_RE.search(text) or STANDARD_RE.search(text):
            return False
        range_match = RANGE_RE.search(text)
        compare_match = COMPARE_RE.search(text)
        return bool(text) and (
            bool(range_match and normalize_line(range_match.group(0)) == text)
            or bool(compare_match and normalize_line(compare_match.group(0)) == text)
            or bool(DIMENSION_VALUE_RE.fullmatch(text))
            or bool(PURE_NUMERIC_VALUE_RE.fullmatch(text))
        )

    def _should_reject_parameter_candidate(self, name: str, value: str, context: str = "") -> bool:
        name = normalize_line(name)
        value = normalize_line(value)
        context = normalize_line(context)
        merged = normalize_line(" ".join(part for part in (name, value, context) if part))
        if not merged:
            return True
        # §2.2 fullmatch 黑名单：日期发布句/标准号/分类号/替代号作为独立参数一律拒绝
        for candidate in (name, value, merged):
            if not candidate:
                continue
            if re.fullmatch(r"\d{4}[-—/.]\d{1,2}[-—/.]{1,2}\d{1,2}(?:\s*[发实施布]+)?", candidate):
                return True
            if re.fullmatch(
                r"(?:GB|CB|ISO|IEC|EN|DIN|JIS|ASTM|SN|SEW|DVS|AD|TRbF|CH)(?:/T)?\s*\d+[-—–─.]\d+",
                candidate,
            ):
                return True
            if re.fullmatch(r"(?:分类号|U)\s*[:：]?\s*[A-Z]?\d+", candidate):
                return True
            if re.fullmatch(r"代替.+", candidate):
                return True
        if self._looks_like_front_matter_context(name, value, context):
            return True
        if METADATA_PARAM_RE.search(merged) or DATE_LIKE_RE.search(merged):
            return True
        if STANDARD_RE.search(merged):
            return True
        if name and not re.search(r"[A-Za-z\u4e00-\u9fff]", name):
            return True
        if LEADING_NUMERIC_CJK_GLUE_RE.match(name) or LEADING_NUMERIC_CJK_GLUE_RE.match(value):
            return True
        if CODE_LIKE_VALUE_RE.fullmatch(name) or CODE_LIKE_VALUE_RE.fullmatch(value):
            return True
        spec_hits = len(SPEC_TOKEN_RE.findall(merged))
        if spec_hits >= 2 and not RANGE_RE.search(merged) and not COMPARE_RE.search(merged) and not self._looks_like_value(value):
            return True
        if len(merged) >= 20 and SENTENCE_DATA_CUE_RE.search(merged) and spec_hits >= 1 and "：" not in merged and ":" not in merged:
            return True
        if len(merged) <= 6 and not re.search(r"\d", merged):
            return True
        return False

    def _canonicalize_parameter_name(self, text: str, context: str = "") -> str:
        source = f"{normalize_line(text)} {normalize_line(context)}".lower()
        mapping = [
            (r"\b(weight|gewicht)\b", "重量"),
            (r"\b(length|länge|laenge)\b", "长度"),
            (r"\b(width|breite)\b", "宽度"),
            (r"\b(height|höhe|hoehe)\b", "高度"),
            (r"\b(diameter|durchmesser|dn|d\d+)\b", normalize_line(text)),
            (r"\b(radius|halbmesser|r)\b", "半径"),
            (r"\b(thickness|wanddicke|wall thickness|厚度|壁厚)\b", "厚度"),
            (r"\b(pressure|druck)\b", "压力"),
            (r"\b(temperature|temperatur)\b", "温度"),
            (r"\b(tolerance|abweichung)\b", "公差"),
            (r"\b(roughness|ra|rz)\b", "粗糙度"),
            (r"\b(angle|winkel)\b", "角度"),
        ]
        for pattern, value in mapping:
            if re.search(pattern, source, re.IGNORECASE):
                return value
        text = normalize_line(text)
        return text if len(text) <= 40 else ""

    def _extract_rules(self, blocks: list[BlockRecord]) -> list[RuleRecord]:
        rules: list[RuleRecord] = []
        seen: set[tuple[str, str, str]] = set()
        for block in blocks:
            if block.块类型 != "正文":
                continue
            for pattern, rule_type in RULE_PATTERNS:
                if pattern.search(block.内容):
                    key = (rule_type, block.内容, block.所属章节)
                    if key not in seen:
                        seen.add(key)
                        rules.append(RuleRecord(规则类型=rule_type, 规则内容=block.内容, 所属章节=block.所属章节))
                    break
        return rules

    def _extract_inspections(self, blocks: list[BlockRecord]) -> list[InspectionRecord]:
        inspections: list[InspectionRecord] = []
        seen: set[tuple[str, str, str]] = set()
        for block in blocks:
            if not INSPECTION_HINT_RE.search(block.内容):
                continue
            method = self._pick_inspection_method(block.内容)
            key = (method, block.所属章节, block.内容)
            if key in seen:
                continue
            seen.add(key)
            inspections.append(InspectionRecord(检验对象=block.所属章节 or "文档", 检验方法=method, 检验要求=block.内容, 所属章节=block.所属章节))
        return inspections

    def _pick_inspection_method(self, text: str) -> str:
        lowered = text.lower()
        for needle, label in [("超声", "超声波检测"), ("磁粉", "磁粉检测"), ("渗透", "渗透检测"), ("硬度", "硬度检验"), ("pressure test", "压力检验"), ("prüfung", "检验"), ("inspection", "检验"), ("test", "试验")]:
            if needle in lowered or needle in text:
                return label
        return "检验"

    def _extract_products(self, blocks: list[BlockRecord], profile: Any) -> list[ProductRecord]:
        if profile.文档类型 != "product_catalog":
            return []
        products: list[ProductRecord] = []
        seen: set[str] = set()
        for block in blocks:
            text = normalize_line(block.内容)
            if not text or not (PRODUCT_HINT_RE.search(text) or MODEL_RE.search(text)):
                continue
            model_match = MODEL_RE.search(text)
            model = normalize_line(model_match.group(0)) if model_match else ""
            display = model or text
            if display in seen:
                continue
            seen.add(display)
            anchor = AnchorRef(锚点类型="product", 锚点ID=display, 显示名称=display)
            products.append(ProductRecord(产品ID=f"product-{len(products) + 1}", 型号=model, 名称=text, 锚点=anchor, 来源引用列表=[SourceRef(页码索引=max(0, block.来源页码 - 1), 摘录文本=text[:160])]))
        return products

    def _build_page_records(self, pages: list[dict[str, Any]]) -> list[PageRecord]:
        from src.ocr import get_engine_version

        ocr_source = get_engine_version() if any(page.get("ocr_used") for page in pages) else ""
        page_eval_map: dict[int, dict[str, Any]] = getattr(self.config, "ocr_page_evaluations", {}) or {}
        return [
            PageRecord(
                页码索引=page["page_index"],
                原始文本="\n".join(page["lines"]),
                页面宽度=page["width"],
                页面高度=page["height"],
                是否执行OCR=bool(page_eval_map.get(page["page_index"])),
                OCR来源=(
                    str(page_eval_map.get(page["page_index"], {}).get("OCR来源", ""))  # type: ignore[union-attr]
                    or (ocr_source if page.get("ocr_used") or page_eval_map.get(page["page_index"]) else "")
                ),
                OCR评估等级=str(page_eval_map.get(page["page_index"], {}).get("评估等级", "")),
                OCR是否注入解析=bool(page_eval_map.get(page["page_index"], {}).get("是否注入解析", False)),
                OCR评估原因列表=[
                    str(item)
                    for item in page_eval_map.get(page["page_index"], {}).get("判定原因", [])
                    if str(item)
                ],
                OCR有效字符数=int(page_eval_map.get(page["page_index"], {}).get("有效字符数", 0) or 0),
            )
            for page in pages
        ]

    def _build_structure_nodes(self, sections: list[SectionRecord], products: list[ProductRecord]) -> list[StructureNode]:
        nodes = [StructureNode(节点ID=f"section:{self._section_ref(section)}", 节点类型="section", 节点标题=self._section_ref(section), 节点层级=section.章节层级, 父节点ID=f"section:{section.父章节编号}" if section.父章节编号 else "") for section in sections]
        nodes.extend(
            StructureNode(节点ID=f"product:{product.产品ID}", 节点类型="product", 节点标题=product.锚点.显示名称 if product.锚点 else (product.型号 or product.名称), 节点层级=1)
            for product in products
        )
        return nodes

    def _enrich_parameters(self, params: list[NumericParameter], products: list[ProductRecord]) -> None:
        for idx, param in enumerate(params, 1):
            param.参数ID = f"param-{idx}"
            param.主体锚点 = self._resolve_parameter_anchor(param, products)
            param.来源引用列表 = [SourceRef(页码索引=0, 摘录文本=param.来源子项 or param.参数名称)]
            param.置信度 = 0.75

    def _resolve_parameter_anchor(self, param: NumericParameter, products: list[ProductRecord]) -> AnchorRef:
        condition = normalize_line(param.适用条件)
        for product in products:
            display = product.锚点.显示名称 if product.锚点 else (product.型号 or product.名称)
            if display and display in condition:
                return AnchorRef(锚点类型="product", 锚点ID=product.产品ID, 显示名称=display)
        display = normalize_line(param.所属章节) or "文档"
        return AnchorRef(锚点类型="section", 锚点ID=display, 显示名称=display)

    def _enrich_rules(self, rules: list[RuleRecord]) -> None:
        for idx, rule in enumerate(rules, 1):
            rule.规则ID = f"rule-{idx}"
            display = normalize_line(rule.所属章节) or "文档"
            rule.主体锚点 = AnchorRef(锚点类型="section", 锚点ID=display, 显示名称=display)
            rule.来源引用列表 = [SourceRef(页码索引=0, 摘录文本=rule.规则内容[:160])]

    def _enrich_standards(self, standards: list[StandardReference]) -> None:
        for item in standards:
            item.标准族 = item.标准类型
            display = normalize_line(item.所属章节) or "文档"
            item.主体锚点 = AnchorRef(锚点类型="section", 锚点ID=display, 显示名称=display)
            item.来源引用列表 = [SourceRef(页码索引=0, 摘录文本=item.标准名称[:160] or item.标准编号)]

    def _extract_scope(self, sections: list[SectionRecord], blocks: list[BlockRecord]) -> str:
        for section in sections:
            if APPLICATION_HINT_RE.search(section.章节标题):
                return normalize_line(section.章节清洗文本[:240])
        for block in blocks:
            if APPLICATION_HINT_RE.search(block.内容):
                return normalize_line(block.内容[:240])
        return ""

    def _pick_standard_code(self, standards: list[StandardReference]) -> str:
        return standards[0].标准编号 if standards else ""

    def _profile_label(self, profile: Any) -> str:
        return {"standard": "标准/规范文档", "product_catalog": "产品样本/规格资料", "manual": "技术手册", "report": "报告文档", "unknown": "技术资料"}.get(profile.文档类型, "技术资料")

    def _classify_standard_family(self, code: str) -> str:
        for prefix in ["DIN EN ISO", "DIN ISO", "DIN EN", "DIN", "EN", "ISO", "SN", "SEW", "DVS", "AD", "TRbF", "GB", "CB"]:
            if code.startswith(prefix):
                return prefix
        return "其他"

    def _section_ref(self, section: SectionRecord) -> str:
        values = list(section.__dict__.values())
        number = normalize_line(str(values[0])) if len(values) > 0 else ""
        title = normalize_line(str(values[1])) if len(values) > 1 else ""
        return f"{number} {title}".strip()


PDFParser = UniversalPDFParser

__all__ = ["PDFParser", "UniversalPDFParser"]
