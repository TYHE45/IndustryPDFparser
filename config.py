from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    input_path: Path
    output_dir: Path
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5.4"))
    use_llm: bool = field(default_factory=lambda: bool(os.getenv("OPENAI_API_KEY")))
    llm_structure_refine_rounds: int = field(default_factory=lambda: int(os.getenv("LLM_STRUCTURE_REFINE_ROUNDS", "2")))
    llm_structure_refine_candidates: int = field(default_factory=lambda: int(os.getenv("LLM_STRUCTURE_REFINE_CANDIDATES", "12")))

    min_text_chars_for_text_pdf: int = 120
    min_chars_per_page_before_ocr_warning: int = 60
    max_heading_words: int = 14

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
