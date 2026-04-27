from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


def normalize_line(line: str) -> str:
    line = line.replace("\u3000", " ")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_output_dir_from_parts(
    source_name: str,
    parent_parts: tuple[str, ...],
    base_output_dir: Path,
) -> Path:
    if parent_parts:
        return base_output_dir.joinpath(*parent_parts, source_name)
    return base_output_dir / source_name


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
