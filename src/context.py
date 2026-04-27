from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    """管道运行期上下文 —— 承载非配置的中间状态，与 AppConfig 分离。

    包含 OCR 注入结果、页级评估等运行时产物，这些数据在管道各阶段之间
    （fixer → parser → pipeline）传递，但不应驻留在用户配置对象中。
    """

    force_ocr_pages: dict[int, str] = field(default_factory=dict)
    force_ocr_tables: dict[int, list[list[list[str]]]] = field(default_factory=dict)
    ocr_page_evaluations: dict[int, dict[str, Any]] = field(default_factory=dict)
