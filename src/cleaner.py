from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from config import AppConfig
from src.utils import normalize_line


class LineCleaner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._compiled_header_footer = [re.compile(p) for p in config.header_footer_patterns]

    def clean_lines(self, lines: Iterable[str], repeated_noise: set[str] | None = None) -> list[str]:
        repeated_noise = repeated_noise or set()
        cleaned: list[str] = []
        for raw in lines:
            line = normalize_line(raw)
            if not line:
                continue
            if self._is_noise(line, repeated_noise):
                continue
            cleaned.append(line)
        return cleaned

    def _is_noise(self, line: str, repeated_noise: set[str]) -> bool:
        if line in repeated_noise:
            return True
        if any(fragment in line for fragment in self.config.skip_line_contains):
            return True
        return any(pattern.match(line) for pattern in self._compiled_header_footer)


def detect_repeated_noise(all_pages_lines: list[list[str]], min_repeat: int = 6) -> set[str]:
    counter: Counter[str] = Counter()
    for page_lines in all_pages_lines:
        for line in {normalize_line(x) for x in page_lines if normalize_line(x)}:
            counter[line] += 1

    repeated: set[str] = set()
    for line, count in counter.items():
        if count < min_repeat:
            continue
        if len(line) <= 50:
            repeated.add(line)
        elif re.search(r"SN\s*200|第\s*\d+\s*页|2007\s*年\s*\d+\s*月", line):
            repeated.add(line)
    return repeated
