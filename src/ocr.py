"""PaddleOCR 封装：仅在被调用时实例化模型，失败时返回空字典而不抛出。

外部调用入口：
- ``build_ocr_runtime_plan(...)`` -> OCR 运行计划（DPI / 批大小 / 超时）
- ``run_ocr_on_pages(pdf_path, page_indices, lang, dpi, batch_size, timeout_seconds)``
   -> ``({页码索引: 识别文本}, 运行元数据)``
- ``get_engine_version()`` -> 用于 PageRecord.OCR来源 的溯源标记

设计约束：
1. 不在模块导入时加载 PaddleOCR，避免未安装依赖的用户无法使用其他功能。
2. 同一进程内对相同语言的模型复用单例（paddleocr 模型体积约 500MB）。
3. 出错时打印警告并返回空结果，让调用方（fixer）决定是否继续走其他修正动作。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import fitz

_LOGGER = logging.getLogger(__name__)

_ENGINE_LOCK = threading.Lock()
_ENGINE_CACHE: dict[str, Any] = {}
_TABLE_ENGINE_CACHE: Any | None = None
_PADDLE_AVAILABLE: bool | None = None
_TABLE_ENGINE_AVAILABLE: bool | None = None
_PADDLEOCR_VERSION: str = ""


def _ensure_paddleocr_available() -> bool:
    """探测 paddleocr 是否可导入。结果缓存，避免反复抛出 ImportError。

    对 ``_PADDLE_AVAILABLE`` / ``_PADDLEOCR_VERSION`` 两个全局变量的读写一律放在
    ``_ENGINE_LOCK`` 内（虽然 Python import 本身持有 GIL 保护，但把"探测+写标志"合并
    成一个原子段更干净，避免未来加入异步路径时重复初始化）。
    """

    global _PADDLE_AVAILABLE, _PADDLEOCR_VERSION
    with _ENGINE_LOCK:
        if _PADDLE_AVAILABLE is not None:
            return _PADDLE_AVAILABLE

        try:
            import paddleocr  # noqa: F401

            _PADDLEOCR_VERSION = getattr(paddleocr, "__version__", "unknown")
            _PADDLE_AVAILABLE = True
        except Exception as exc:  # pragma: no cover - 取决于用户环境
            _LOGGER.warning("PaddleOCR 未安装或加载失败，OCR 功能将被跳过：%s", exc)
            _PADDLE_AVAILABLE = False
        return _PADDLE_AVAILABLE


def get_engine_version() -> str:
    """返回 paddleocr 版本字符串，用于写入 PageRecord.OCR来源。"""

    if _PADDLE_AVAILABLE is None:
        _ensure_paddleocr_available()
    return f"paddleocr-{_PADDLEOCR_VERSION}" if _PADDLEOCR_VERSION else "paddleocr"


def get_ocr_engine(lang: str = "ch") -> Any | None:
    """懒初始化 PaddleOCR 模型。失败返回 None，不抛出。"""

    if not _ensure_paddleocr_available():
        return None

    with _ENGINE_LOCK:
        if lang in _ENGINE_CACHE:
            return _ENGINE_CACHE[lang]
        try:
            from paddleocr import PaddleOCR

            # PaddleOCR v3.x: 使用 use_textline_orientation 取代 v2 的 use_angle_cls；
            # enable_mkldnn=False 规避 paddlepaddle 3.x + OneDNN + PIR 执行器的已知 bug
            # （"ConvertPirAttribute2RuntimeAttribute not support" 运行期异常）；
            # 关闭 doc_orientation_classify / doc_unwarping：这两个可选前处理模块在
            # paddlepaddle 3.3.1 + PP-OCRv5_server 组合下会触发原生段错误（exit 139），
            # 关掉只保留 det+rec+textline_ori，识别通路就稳定了。
            try:
                engine = PaddleOCR(
                    lang=lang,
                    ocr_version="PP-OCRv4",  # v5 server 模型在 paddlepaddle 3.3.1 下段错误，v4 稳定
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=True,
                    enable_mkldnn=False,
                )
            except TypeError:
                # v2 老接口不认识 enable_mkldnn / use_textline_orientation / use_doc_*
                engine = PaddleOCR(lang=lang, use_angle_cls=True)  # type: ignore[call-arg]
            _ENGINE_CACHE[lang] = engine
            return engine
        except Exception as exc:  # pragma: no cover - 取决于用户环境
            _LOGGER.warning("PaddleOCR 初始化失败（lang=%s）：%s", lang, exc)
            return None


def get_table_structure_engine() -> Any | None:
    """懒初始化表格结构识别模型。失败时返回 ``None``，不抛出。"""

    global _TABLE_ENGINE_AVAILABLE, _TABLE_ENGINE_CACHE
    with _ENGINE_LOCK:
        if _TABLE_ENGINE_CACHE is not None:
            return _TABLE_ENGINE_CACHE
        if _TABLE_ENGINE_AVAILABLE is False:
            return None

        try:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import TableStructureRecognition

            _TABLE_ENGINE_CACHE = TableStructureRecognition()
            _TABLE_ENGINE_AVAILABLE = True
            return _TABLE_ENGINE_CACHE
        except Exception as exc:  # pragma: no cover - 取决于用户环境
            _TABLE_ENGINE_AVAILABLE = False
            _LOGGER.warning("表格结构识别模型初始化失败：%s", exc)
            return None


def build_ocr_runtime_plan(
    *,
    page_count: int,
    requested_dpi: int,
    batch_size: int,
    timeout_seconds: float,
    large_doc_page_threshold: int,
    reduced_dpi: int,
) -> dict[str, Any]:
    normalized_page_count = max(0, int(page_count))
    normalized_batch_size = max(1, int(batch_size))
    normalized_requested_dpi = max(72, int(requested_dpi))
    normalized_reduced_dpi = max(72, int(reduced_dpi))
    effective_dpi = normalized_requested_dpi
    dpi_downgraded = False
    if (
        normalized_page_count >= max(1, int(large_doc_page_threshold))
        and normalized_reduced_dpi < normalized_requested_dpi
    ):
        effective_dpi = normalized_reduced_dpi
        dpi_downgraded = True
    return {
        "page_count": normalized_page_count,
        "requested_dpi": normalized_requested_dpi,
        "effective_dpi": effective_dpi,
        "dpi_downgraded": dpi_downgraded,
        "batch_size": normalized_batch_size,
        "timeout_seconds": max(0.0, float(timeout_seconds)),
    }


def run_ocr_on_pages(
    pdf_path: Path,
    page_indices: list[int],
    lang: str = "ch",
    dpi: int = 300,
    batch_size: int = 6,
    timeout_seconds: float | None = None,
) -> tuple[dict[int, str], dict[str, Any]]:
    """对 ``pdf_path`` 的指定页（0-based）跑 OCR，返回 ``({页码索引: 识别文本}, 运行元数据)``。

    - 渲染通过 PyMuPDF ``page.get_pixmap(matrix)`` 以 ``dpi`` 分辨率输出图像；
    - 若 PaddleOCR 不可用（未安装、初始化失败），返回空字典；
    - 单页识别失败不影响其他页，记录 warning 后跳过；
    - 对大样本按 ``batch_size`` 分批执行，并在批次边界应用软超时。
    """

    normalized_batch_size = max(1, int(batch_size))
    normalized_timeout_seconds = None if timeout_seconds is None else max(0.0, float(timeout_seconds))
    runtime_meta = {
        "requested_pages": len(page_indices),
        "executed_pages": 0,
        "successful_pages": 0,
        "batch_count": 0,
        "batch_size": normalized_batch_size,
        "timeout_seconds": normalized_timeout_seconds or 0.0,
        "timed_out": False,
    }
    if not page_indices:
        return {}, runtime_meta

    engine = get_ocr_engine(lang)
    if engine is None:
        return {}, runtime_meta

    results: dict[int, str] = {}
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        _LOGGER.warning("PyMuPDF 打开 PDF 失败（%s）：%s", pdf_path, exc)
        return {}, runtime_meta

    try:
        zoom = max(1.0, dpi / 72.0)
        matrix = fitz.Matrix(zoom, zoom)
        started_at = time.perf_counter()
        batches = _chunk_page_indices(page_indices, normalized_batch_size)
        for batch_index, batch in enumerate(batches, start=1):
            if normalized_timeout_seconds is not None and time.perf_counter() - started_at >= normalized_timeout_seconds:
                runtime_meta["timed_out"] = True
                _LOGGER.warning(
                    "OCR 达到软超时阈值，提前停止：已执行 %d / %d 页（批次 %d / %d）。",
                    runtime_meta["executed_pages"],
                    len(page_indices),
                    batch_index - 1,
                    len(batches),
                )
                break
            runtime_meta["batch_count"] = batch_index
            for page_index in batch:
                if page_index < 0 or page_index >= len(doc):
                    continue
                try:
                    page = doc.load_page(page_index)
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    # PaddleOCR v3 只接受 numpy.ndarray / str（路径）。将 pixmap 直接转 numpy。
                    import numpy as np

                    image_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height, pixmap.width, pixmap.n
                    )
                    # PaddleOCR 预期 BGR；PyMuPDF 默认 RGB，需要翻转通道
                    if pixmap.n >= 3:
                        image_array = image_array[:, :, [2, 1, 0]].copy()
                except Exception as exc:
                    _LOGGER.warning("渲染第 %d 页失败：%s", page_index, exc)
                    runtime_meta["executed_pages"] += 1
                    continue

                try:
                    # v3 的 .ocr 不再接受 cls 参数；v2 可接受。做兼容调用。
                    try:
                        raw = engine.ocr(image_array)
                    except TypeError:
                        raw = engine.ocr(image_array, cls=True)  # type: ignore[call-arg]
                except Exception as exc:
                    _LOGGER.warning("PaddleOCR 识别第 %d 页失败：%s", page_index, exc)
                    runtime_meta["executed_pages"] += 1
                    continue

                runtime_meta["executed_pages"] += 1
                text = _flatten_paddle_result(raw)
                if text.strip():
                    results[page_index] = text
                    runtime_meta["successful_pages"] += 1
    finally:
        doc.close()

    return results, runtime_meta


def run_table_structure_on_pages(
    pdf_path: Path,
    page_indices: list[int],
    lang: str = "ch",
    dpi: int = 220,
    batch_size: int = 4,
    timeout_seconds: float | None = None,
) -> tuple[dict[int, list[list[list[str]]]], dict[str, Any]]:
    """对指定页做表格结构识别，返回 ``{页码索引: [表格矩阵, ...]}`` 与运行元数据。"""

    normalized_batch_size = max(1, int(batch_size))
    normalized_timeout_seconds = None if timeout_seconds is None else max(0.0, float(timeout_seconds))
    runtime_meta = {
        "requested_pages": len(page_indices),
        "executed_pages": 0,
        "detected_table_pages": 0,
        "extracted_table_count": 0,
        "batch_count": 0,
        "batch_size": normalized_batch_size,
        "timeout_seconds": normalized_timeout_seconds or 0.0,
        "timed_out": False,
    }
    if not page_indices:
        return {}, runtime_meta

    table_engine = get_table_structure_engine()
    if table_engine is None:
        return {}, runtime_meta

    text_engine = get_ocr_engine(lang)
    if text_engine is None:
        _LOGGER.warning("表格结构识别需要 OCR 文本框辅助，但 OCR 引擎不可用。")
        return {}, runtime_meta

    results: dict[int, list[list[list[str]]]] = {}
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        _LOGGER.warning("PyMuPDF 打开 PDF 失败（%s）：%s", pdf_path, exc)
        return {}, runtime_meta

    try:
        zoom = max(1.0, dpi / 72.0)
        matrix = fitz.Matrix(zoom, zoom)
        started_at = time.perf_counter()
        batches = _chunk_page_indices(page_indices, normalized_batch_size)
        for batch_index, batch in enumerate(batches, start=1):
            if normalized_timeout_seconds is not None and time.perf_counter() - started_at >= normalized_timeout_seconds:
                runtime_meta["timed_out"] = True
                _LOGGER.warning(
                    "表格结构识别达到软超时阈值，提前停止：已执行 %d / %d 页（批次 %d / %d）。",
                    runtime_meta["executed_pages"],
                    len(page_indices),
                    batch_index - 1,
                    len(batches),
                )
                break
            runtime_meta["batch_count"] = batch_index
            for page_index in batch:
                if page_index < 0 or page_index >= len(doc):
                    continue
                try:
                    page = doc.load_page(page_index)
                    image_array = _render_page_to_bgr_array(page, matrix)
                except Exception as exc:
                    _LOGGER.warning("表格结构识别渲染第 %d 页失败：%s", page_index, exc)
                    runtime_meta["executed_pages"] += 1
                    continue

                runtime_meta["executed_pages"] += 1
                try:
                    table_raw = table_engine.predict(image_array)
                except Exception as exc:
                    _LOGGER.warning("表格结构识别第 %d 页失败：%s", page_index, exc)
                    continue

                try:
                    ocr_raw = _run_paddle_ocr_raw(text_engine, image_array)
                except Exception as exc:
                    _LOGGER.warning("表格结构识别辅助 OCR 在第 %d 页失败：%s", page_index, exc)
                    continue

                ocr_lines = _extract_paddle_ocr_lines_with_boxes(ocr_raw)
                page_tables = _extract_table_matrices(table_raw, ocr_lines)
                if not page_tables:
                    continue
                results[page_index] = page_tables
                runtime_meta["detected_table_pages"] += 1
                runtime_meta["extracted_table_count"] += len(page_tables)
    finally:
        doc.close()

    return results, runtime_meta


def _chunk_page_indices(page_indices: list[int], batch_size: int) -> list[list[int]]:
    normalized_batch_size = max(1, int(batch_size))
    return [
        page_indices[index:index + normalized_batch_size]
        for index in range(0, len(page_indices), normalized_batch_size)
    ]


def _render_page_to_bgr_array(page: Any, matrix: Any) -> Any:
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    import numpy as np

    image_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
    if pixmap.n >= 3:
        image_array = image_array[:, :, [2, 1, 0]].copy()
    return image_array


def _run_paddle_ocr_raw(engine: Any, image_array: Any) -> Any:
    try:
        return engine.ocr(image_array)
    except TypeError:
        return engine.ocr(image_array, cls=True)  # type: ignore[call-arg]


def _extract_table_matrices(raw: Any, ocr_lines: list[dict[str, Any]]) -> list[list[list[str]]]:
    entries = raw if isinstance(raw, list) else [raw]
    tables: list[list[list[str]]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cell_boxes = entry.get("bbox", [])
        table = _build_table_matrix_from_cells(cell_boxes, ocr_lines)
        if _is_meaningful_table_matrix(table):
            tables.append(table)
    return tables


def _build_table_matrix_from_cells(cell_boxes: Any, ocr_lines: list[dict[str, Any]]) -> list[list[str]]:
    cells: list[dict[str, Any]] = []
    for box in cell_boxes or []:
        rect = _normalize_rect(box)
        if rect is None:
            continue
        x1, y1, x2, y2 = rect
        cells.append(
            {
                "rect": rect,
                "cx": (x1 + x2) / 2.0,
                "cy": (y1 + y2) / 2.0,
                "height": max(1.0, y2 - y1),
                "texts": [],
            }
        )
    if not cells:
        return []

    cells.sort(key=lambda item: (item["cy"], item["cx"]))
    heights = sorted(item["height"] for item in cells)
    median_height = heights[len(heights) // 2] if heights else 20.0
    row_threshold = max(12.0, float(median_height) * 0.6)

    rows: list[dict[str, Any]] = []
    for cell in cells:
        if not rows or abs(cell["cy"] - rows[-1]["cy"]) > row_threshold:
            rows.append({"cy": cell["cy"], "cells": [cell]})
            continue
        rows[-1]["cells"].append(cell)
        rows[-1]["cy"] = sum(item["cy"] for item in rows[-1]["cells"]) / len(rows[-1]["cells"])

    for row in rows:
        row["cells"].sort(key=lambda item: item["cx"])

    for line in ocr_lines:
        text = str(line.get("text", "")).strip()
        rect = line.get("rect")
        if not text or rect is None:
            continue
        cell = _match_ocr_line_to_cell(rect, cells)
        if cell is None:
            continue
        cell["texts"].append((float(line.get("cy", 0.0)), float(line.get("cx", 0.0)), text))

    max_cols = max((len(row["cells"]) for row in rows), default=0)
    table: list[list[str]] = []
    for row in rows:
        values = [_merge_cell_texts(cell["texts"]) for cell in row["cells"]]
        if max_cols > len(values):
            values.extend([""] * (max_cols - len(values)))
        table.append(values)
    return table


def _extract_paddle_ocr_lines_with_boxes(raw: Any) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    if not raw:
        return lines

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                texts = list(item.get("rec_texts") or [])
                polys = list(item.get("rec_polys") or item.get("dt_polys") or [])
                for text, poly in zip(texts, polys):
                    normalized = _normalize_rect(poly)
                    stripped = str(text).strip()
                    if normalized is None or not stripped:
                        continue
                    x1, y1, x2, y2 = normalized
                    lines.append(
                        {
                            "text": stripped,
                            "rect": normalized,
                            "cx": (x1 + x2) / 2.0,
                            "cy": (y1 + y2) / 2.0,
                        }
                    )
                continue
            if (
                isinstance(item, list)
                and len(item) == 2
                and isinstance(item[1], (tuple, list))
                and item[1]
                and isinstance(item[1][0], str)
            ):
                normalized = _normalize_rect(item[0])
                stripped = str(item[1][0]).strip()
                if normalized is None or not stripped:
                    continue
                x1, y1, x2, y2 = normalized
                lines.append(
                    {
                        "text": stripped,
                        "rect": normalized,
                        "cx": (x1 + x2) / 2.0,
                        "cy": (y1 + y2) / 2.0,
                    }
                )
                continue
            if isinstance(item, list):
                lines.extend(_extract_paddle_ocr_lines_with_boxes(item))
    lines.sort(key=lambda item: (item["cy"], item["cx"]))
    return lines


def _normalize_rect(box: Any) -> tuple[float, float, float, float] | None:
    if box is None:
        return None
    if hasattr(box, "tolist"):
        box = box.tolist()
    if not isinstance(box, (list, tuple)):
        return None
    if len(box) == 4 and all(not isinstance(item, (list, tuple)) for item in box):
        x1, y1, x2, y2 = [float(item) for item in box]
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    flat: list[float] = []
    for item in box:
        if hasattr(item, "tolist"):
            item = item.tolist()
        if isinstance(item, (list, tuple)):
            flat.extend(float(value) for value in item)
        else:
            flat.append(float(item))
    if len(flat) < 4:
        return None
    if len(flat) % 2 != 0:
        return None
    xs = flat[0::2]
    ys = flat[1::2]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _match_ocr_line_to_cell(line_rect: tuple[float, float, float, float], cells: list[dict[str, Any]]) -> dict[str, Any] | None:
    cx = (line_rect[0] + line_rect[2]) / 2.0
    cy = (line_rect[1] + line_rect[3]) / 2.0
    inside_candidates: list[tuple[float, dict[str, Any]]] = []
    overlap_candidates: list[tuple[float, dict[str, Any]]] = []
    nearest_cell: dict[str, Any] | None = None
    nearest_distance: float | None = None

    for cell in cells:
        rect = cell["rect"]
        overlap = _rect_overlap_area(rect, line_rect)
        if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]:
            inside_candidates.append((overlap, cell))
        elif overlap > 0:
            overlap_candidates.append((overlap, cell))

        distance = (cell["cx"] - cx) ** 2 + (cell["cy"] - cy) ** 2
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_cell = cell

    if inside_candidates:
        return max(inside_candidates, key=lambda item: item[0])[1]
    if overlap_candidates:
        return max(overlap_candidates, key=lambda item: item[0])[1]
    return nearest_cell


def _rect_overlap_area(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def _merge_cell_texts(items: list[tuple[float, float, str]]) -> str:
    if not items:
        return ""
    ordered = sorted(items, key=lambda item: (item[0], item[1]))
    merged: list[str] = []
    for _, _, text in ordered:
        clean_text = str(text).strip()
        if not clean_text:
            continue
        if merged and merged[-1] == clean_text:
            continue
        merged.append(clean_text)
    return " ".join(merged)


def _is_meaningful_table_matrix(table: list[list[str]]) -> bool:
    if not table:
        return False
    non_empty_cells = sum(1 for row in table for cell in row if str(cell).strip())
    return non_empty_cells >= 4


def _flatten_paddle_result(raw: Any) -> str:
    """将 PaddleOCR 返回的嵌套结构展平为按行文本。

    兼容两种主要版本：
    - PaddleOCR v2.x ``.ocr(img)`` 返回 ``[[ [box, (text, conf)], ... ]]``
    - PaddleOCR v3.x ``.ocr(img)`` / ``.predict(img)`` 返回 ``[OCRResult, ...]``，每个
      OCRResult 是字典式对象，包含键 ``rec_texts``（按行文本列表）。
    """

    if not raw:
        return ""
    lines: list[str] = []

    def _walk(node: Any) -> None:
        # v3: OCRResult（Mapping-like），优先按 rec_texts 提取
        try:
            rec_texts = node["rec_texts"]  # type: ignore[index]
        except Exception:
            rec_texts = None
        if isinstance(rec_texts, (list, tuple)):
            for text in rec_texts:
                if isinstance(text, str) and text.strip():
                    lines.append(text)
            return

        if isinstance(node, str):
            lines.append(node)
            return
        if isinstance(node, tuple) and node:
            first = node[0]
            if isinstance(first, str):
                lines.append(first)
                return
        if isinstance(node, list):
            # v2 形如 [box, (text, conf)]
            if (
                len(node) == 2
                and isinstance(node[1], (tuple, list))
                and node[1]
                and isinstance(node[1][0], str)
            ):
                lines.append(node[1][0])
                return
            for child in node:
                _walk(child)

    _walk(raw)
    return "\n".join(line.strip() for line in lines if line and line.strip())


__all__ = [
    "build_ocr_runtime_plan",
    "get_ocr_engine",
    "get_engine_version",
    "get_table_structure_engine",
    "run_ocr_on_pages",
    "run_table_structure_on_pages",
]
