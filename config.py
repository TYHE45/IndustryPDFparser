from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    input_path: Path
    output_dir: Path
    openai_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5.4"))
    use_llm: bool = field(default_factory=lambda: bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")))
    llm_structure_refine_rounds: int = field(default_factory=lambda: int(os.getenv("LLM_STRUCTURE_REFINE_ROUNDS", "2")))
    llm_structure_refine_candidates: int = field(default_factory=lambda: int(os.getenv("LLM_STRUCTURE_REFINE_CANDIDATES", "12")))

    min_text_chars_for_text_pdf: int = 120
    min_chars_per_page_before_ocr_warning: int = 60
    max_heading_words: int = 14

    # OCR 相关配置（PaddleOCR）
    ocr_enabled: bool = field(default_factory=lambda: os.getenv("OCR_ENABLED", "1",).strip().lower() not in ("0", "false", ""))
    ocr_lang: str = field(default_factory=lambda: os.getenv("OCR_LANG", "ch"))
    ocr_dpi: int = field(default_factory=lambda: int(os.getenv("OCR_DPI", "300")))
    ocr_page_batch_size: int = field(default_factory=lambda: int(os.getenv("OCR_PAGE_BATCH_SIZE", "6")))
    ocr_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("OCR_TIMEOUT_SECONDS", "180")))
    ocr_large_doc_page_threshold: int = field(default_factory=lambda: int(os.getenv("OCR_LARGE_DOC_PAGE_THRESHOLD", "8")))
    ocr_reduced_dpi: int = field(default_factory=lambda: int(os.getenv("OCR_REDUCED_DPI", "220")))
    ocr_table_enabled: bool = field(default_factory=lambda: os.getenv("OCR_TABLE_ENABLED", "1").strip().lower() not in ("0", "false", ""))
    # 运行期状态见 PipelineContext（src/context.py）

    def __post_init__(self) -> None:
        _valid_ocr_langs = {"ch", "en", "chinese_cht", "ja", "ko", "th", "fr", "de", "ru", "es", "pt", "it", "ar", "vi"}
        if self.ocr_lang and self.ocr_lang.strip().lower() not in _valid_ocr_langs:
            raise ValueError(
                f"ocr_lang={self.ocr_lang!r} 不是支持的 PaddleOCR 语言码。"
                f" 有效值：{', '.join(sorted(_valid_ocr_langs))}"
            )
        if not isinstance(self.ocr_enabled, bool):
            raise ValueError(f"ocr_enabled 必须是 bool，实际为 {type(self.ocr_enabled).__name__}={self.ocr_enabled!r}")
        if not isinstance(self.ocr_table_enabled, bool):
            raise ValueError(f"ocr_table_enabled 必须是 bool，实际为 {type(self.ocr_table_enabled).__name__}={self.ocr_table_enabled!r}")
        if self.ocr_page_batch_size < 1:
            raise ValueError(f"ocr_page_batch_size 必须 >= 1，实际为 {self.ocr_page_batch_size}")
        if self.ocr_timeout_seconds <= 0:
            raise ValueError(f"ocr_timeout_seconds 必须 > 0，实际为 {self.ocr_timeout_seconds}")
        if not 72 <= self.ocr_dpi <= 1200:
            raise ValueError(f"ocr_dpi 必须在 72-1200 范围内，实际为 {self.ocr_dpi}")
        if not 72 <= self.ocr_reduced_dpi <= 1200:
            raise ValueError(f"ocr_reduced_dpi 必须在 72-1200 范围内，实际为 {self.ocr_reduced_dpi}")
        if self.ocr_large_doc_page_threshold < 1:
            raise ValueError(f"ocr_large_doc_page_threshold 必须 >= 1，实际为 {self.ocr_large_doc_page_threshold}")
        if self.llm_structure_refine_rounds < 0:
            raise ValueError(f"llm_structure_refine_rounds 必须 >= 0，实际为 {self.llm_structure_refine_rounds}")
        if self.llm_structure_refine_candidates < 1:
            raise ValueError(f"llm_structure_refine_candidates 必须 >= 1，实际为 {self.llm_structure_refine_candidates}")
        if self.min_chars_per_page_before_ocr_warning < 0:
            raise ValueError(f"min_chars_per_page_before_ocr_warning 必须 >= 0，实际为 {self.min_chars_per_page_before_ocr_warning}")
        if self.max_heading_words < 1:
            raise ValueError(f"max_heading_words 必须 >= 1，实际为 {self.max_heading_words}")

    header_footer_patterns: tuple[str, ...] = (
        r"^\d+\s*/\s*\d+$",
        r"^第\s*\d+\s*页$",
        r"^Page\s+\d+$",
        r"^Page\s+\d+\s+of\s+\d+$",
        r"^Seite\s+\d+$",
        r"^Seite\s+\d+\s*[:\-]\s*.*$",
        r"^\d{4}[-/]\d{2}$",
        r"^[A-Z]{1,5}\s+\d+(?:[-/]\d+)?\s*(?:Teil|Part)?\s*\d*$",
    )

    skip_line_contains: tuple[str, ...] = (
        "The reproduction, distribution and utilization of this document",
        "All rights reserved in case of patent/utility model/trademark protection.",
        "未经书面许可不得复制",
        "如有疑问，一概以最新德文本为准",
        "This document remains the property of",
    )

    banned_heading_exact: tuple[str, ...] = (
        "mm",
        "bar",
        "%",
        "°C",
        "DN",
        "kg",
        "x",
        "X",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "图 1",
        "图 2",
        "图 3",
        "表 1",
        "表 2",
        "表 3",
    )
