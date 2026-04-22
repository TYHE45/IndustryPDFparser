"""PaddleOCR 封装：仅在被调用时实例化模型，失败时返回空字典而不抛出。

外部调用入口：
- ``run_ocr_on_pages(pdf_path, page_indices, lang, dpi)`` -> ``{页码索引: 识别文本}``
- ``get_engine_version()`` -> 用于 PageRecord.OCR来源 的溯源标记

设计约束：
1. 不在模块导入时加载 PaddleOCR，避免未安装依赖的用户无法使用其他功能。
2. 同一进程内对相同语言的模型复用单例（paddleocr 模型体积约 500MB）。
3. 出错时打印警告并返回空结果，让调用方（fixer）决定是否继续走其他修正动作。
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import fitz

_LOGGER = logging.getLogger(__name__)

_ENGINE_LOCK = threading.Lock()
_ENGINE_CACHE: dict[str, Any] = {}
_PADDLE_AVAILABLE: bool | None = None
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


def run_ocr_on_pages(
    pdf_path: Path,
    page_indices: list[int],
    lang: str = "ch",
    dpi: int = 300,
) -> dict[int, str]:
    """对 ``pdf_path`` 的指定页（0-based）跑 OCR，返回 ``{页码索引: 识别文本}``。

    - 渲染通过 PyMuPDF ``page.get_pixmap(matrix)`` 以 ``dpi`` 分辨率输出图像；
    - 若 PaddleOCR 不可用（未安装、初始化失败），返回空字典；
    - 单页识别失败不影响其他页，记录 warning 后跳过。
    """

    if not page_indices:
        return {}

    engine = get_ocr_engine(lang)
    if engine is None:
        return {}

    results: dict[int, str] = {}
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        _LOGGER.warning("PyMuPDF 打开 PDF 失败（%s）：%s", pdf_path, exc)
        return {}

    try:
        zoom = max(1.0, dpi / 72.0)
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in page_indices:
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
                continue

            try:
                # v3 的 .ocr 不再接受 cls 参数；v2 可接受。做兼容调用。
                try:
                    raw = engine.ocr(image_array)
                except TypeError:
                    raw = engine.ocr(image_array, cls=True)  # type: ignore[call-arg]
            except Exception as exc:
                _LOGGER.warning("PaddleOCR 识别第 %d 页失败：%s", page_index, exc)
                continue

            text = _flatten_paddle_result(raw)
            if text.strip():
                results[page_index] = text
    finally:
        doc.close()

    return results


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


__all__ = ["get_ocr_engine", "get_engine_version", "run_ocr_on_pages"]
