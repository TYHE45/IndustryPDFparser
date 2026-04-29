#!/usr/bin/env python3
"""P0-3: OCR 表格→参数桥接诊断探查

三个探查点：
  A — OCR 引擎召回率 (src/ocr.py:263 run_table_structure_on_pages)
  B — 格式适配 (src/parser.py:265 _adapt_ocr_table_matrix)
  C — 参数提取 (src/parser.py:1131 _extract_parameters_from_table)

设计原则：不修改任何 src/ 代码，通过 unittest.mock.patch 挂载探查点，
产出独立 JSON 诊断报告到 diagnostics/output/。
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

# ── 项目路径 ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import AppConfig
from src.context import PipelineContext
from src.parser import PDFParser
from src.ocr import run_table_structure_on_pages


# ═══════════════════════════════════════════════════════════════════════
# 探查结果数据结构
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ProbeRecord:
    """单个探查点的结果"""
    探查点: str           # "A" | "B" | "C"
    判定: str             # "PASS" | "FAIL" | "SKIP"
    原始数据: dict[str, Any] = field(default_factory=dict)
    备注: str = ""


class ProbeTracker:
    """跨探查点共享的状态容器"""

    def __init__(self):
        # ── Probe A ──
        self.ocr_table_map: dict[int, list[list[list[str]]]] = {}
        self.ocr_runtime_meta: dict[str, Any] = {}

        # ── Probe B: _adapt_ocr_table_matrix 捕获 ──
        self.adapt_records: list[dict[str, Any]] = []

        # ── OCR 来源表格定位 ──
        # (page_index, table_idx_on_page) — table_idx is 1-based per page
        self.ocr_table_locations: list[tuple[int, int]] = []

        # ── Probe C: _extract_parameters_from_table 捕获 (仅 OCR 来源) ──
        self.param_records: list[dict[str, Any]] = []

        # ── 元信息 ──
        self.parser_ran: bool = False
        self.total_pdfplumber_tables: int = 0
        self.total_ocr_tables_injected: int = 0


# ═══════════════════════════════════════════════════════════════════════
# 探查点 A — OCR 引擎召回率
# ═══════════════════════════════════════════════════════════════════════

def run_probe_a(pdf_path: Path, page_indices: list[int],
                dpi: int = 220, batch_size: int = 4) -> tuple[dict, dict]:
    """直接调用 run_table_structure_on_pages 捕获召回数据 (探查点 A)

    Args:
        pdf_path: 目标 PDF 路径
        page_indices: 要识别的页码索引 (0-based)
        dpi: 渲染分辨率
        batch_size: 批大小

    Returns:
        (ocr_table_map, runtime_meta) — 与 src/ocr.py:263 返回值同构
    """
    ocr_table_map, runtime_meta = run_table_structure_on_pages(
        pdf_path,
        page_indices,
        lang="ch",
        dpi=dpi,
        batch_size=batch_size,
    )
    return ocr_table_map, runtime_meta


def assess_probe_a(ocr_table_map: dict[int, list[list[list[str]]]],
                   runtime_meta: dict[str, Any]) -> ProbeRecord:
    """对探查点 A 的结果做 PASS/FAIL 判定

    判定标准:
      - len(ocr_table_map) >= 1  AND
      - 至少一个表格 len(rows) >= 2
    """
    has_pages = len(ocr_table_map) >= 1
    meaningful_tables: list[dict[str, Any]] = []
    for page_idx, tables in ocr_table_map.items():
        for t_idx, rows in enumerate(tables):
            row_count = len(rows)
            col_count = max(len(r) for r in rows) if rows else 0
            row_samples = rows[:3] if row_count > 0 else []
            meaningful_tables.append({
                "页码索引": page_idx,
                "页码(1-based)": page_idx + 1,
                "页内表格序号": t_idx + 1,
                "行数": row_count,
                "列数": col_count,
                "前3行样本": row_samples,
                "满2行": row_count >= 2,
            })
    has_meaningful = any(t["满2行"] for t in meaningful_tables)

    passed = has_pages and has_meaningful
    return ProbeRecord(
        探查点="A",
        判定="PASS" if passed else "FAIL",
        原始数据={
            "命中页码数": len(ocr_table_map),
            "命中页码列表": sorted(ocr_table_map.keys()),
            "命中页码(1-based)列表": [p + 1 for p in sorted(ocr_table_map.keys())],
            "总表格数": sum(len(v) for v in ocr_table_map.values()),
            "表格详情": meaningful_tables,
            "runtime_meta": runtime_meta,
        },
        备注=(f"PASS: {len(ocr_table_map)}页检出{sum(len(v) for v in ocr_table_map.values())}个表格，"
              f"其中{sum(1 for t in meaningful_tables if t['满2行'])}个表格>=2行")
              if passed
              else ("FAIL: 未检测到任何表格" if not has_pages
                    else "FAIL: 检测到表格页但所有表格均不足2行"),
    )


# ═══════════════════════════════════════════════════════════════════════
# 探查点 B — 格式适配 (通过 patch _extract_page_tables 捕获)
# ═══════════════════════════════════════════════════════════════════════

def make_probe_b_patch(tracker: ProbeTracker):
    """构建 PDFParser._extract_page_tables 的 monkey-patch

    在原始方法返回后，遍历 self.context.force_ocr_tables，对每个 OCR 表格
    重新调用 _adapt_ocr_table_matrix 捕获输入/输出矩阵形状，同时记录 OCR
    表格在每页中的序号 (用于探查点 C 的 OCR 来源对照)。
    """
    original_extract_page_tables = PDFParser._extract_page_tables

    def patched_extract_page_tables(self: PDFParser, plumber_doc: Any) -> dict:
        # 统计 pdfplumber 原生表格数（每页），用于计算 OCR 表格序号偏移
        pdfplumber_counts: dict[int, int] = {}
        total_pdfplumber = 0
        for page_index, page in enumerate(plumber_doc.pages):
            tbl_list = page.extract_tables() or []
            non_empty = sum(1 for t in tbl_list
                          if t and any(any((c or "").strip() for c in r if c) for r in t))
            pdfplumber_counts[page_index] = non_empty
            total_pdfplumber += non_empty
        tracker.total_pdfplumber_tables = total_pdfplumber

        # 执行原始方法
        result = original_extract_page_tables(self, plumber_doc)

        # 捕获 OCR 表格适配信息
        force_ocr = self.context.force_ocr_tables
        total_ocr = 0
        for page_index, tables in force_ocr.items():
            base_idx = pdfplumber_counts.get(page_index, 0)  # pdfplumber 表数
            for i, table in enumerate(tables or []):
                total_ocr += 1
                input_rows = len(table)
                input_cols = max(len(r) for r in table) if table else 0

                # 调用适配器获取输出形状
                adapted = self._adapt_ocr_table_matrix(table)
                output_rows = len(adapted)
                output_cols = max(len(r) for r in adapted) if adapted else 0

                ocr_table_idx = base_idx + i + 1  # 1-based index on page
                tracker.ocr_table_locations.append((page_index, ocr_table_idx))

                tracker.adapt_records.append({
                    "页码索引": page_index,
                    "页码(1-based)": page_index + 1,
                    "页内表格序号": ocr_table_idx,
                    "输入形状": [input_rows, input_cols],
                    "输出形状": [output_rows, output_cols],
                    "适配后行数满足(>=2)": output_rows >= 2,
                    "形状保留": input_rows == output_rows and input_cols == output_cols,
                })

        tracker.total_ocr_tables_injected = total_ocr
        return result

    return patched_extract_page_tables


def assess_probe_b(tracker: ProbeTracker) -> ProbeRecord:
    """对探查点 B 的结果做 PASS/FAIL 判定

    判定标准: 至少一个 force_ocr_tables 表格适配后 len(adapted) >= 2
    """
    if not tracker.adapt_records:
        return ProbeRecord(
            探查点="B",
            判定="SKIP",
            原始数据={"说明": "无 OCR 表格需要适配，force_ocr_tables 为空"},
            备注="跳过：未发现 OCR 来源表格",
        )
    passed = any(r["适配后行数满足(>=2)"] for r in tracker.adapt_records)
    valid_count = sum(1 for r in tracker.adapt_records if r["适配后行数满足(>=2)"])
    return ProbeRecord(
        探查点="B",
        判定="PASS" if passed else "FAIL",
        原始数据={
            "总适配调用数": len(tracker.adapt_records),
            "适配后满足2行者": valid_count,
            "适配详情": tracker.adapt_records,
        },
        备注=(f"PASS: {valid_count}/{len(tracker.adapt_records)} 个表格适配后 >=2 行"
              if passed
              else f"FAIL: {len(tracker.adapt_records)} 个表格适配后全部不足2行"),
    )


# ═══════════════════════════════════════════════════════════════════════
# 探查点 C — 参数提取 (通过 patch _extract_parameters_from_table 捕获)
# ═══════════════════════════════════════════════════════════════════════

def make_probe_c_patch(tracker: ProbeTracker):
    """构建 PDFParser._extract_parameters_from_table 的 monkey-patch

    对 OCR 来源表格 (通过表格编号匹配 tracker.ocr_table_locations 判定)，
    捕获 TableRecord.表头、表体前3行、产出参数数。
    """
    original_extract_params = PDFParser._extract_parameters_from_table

    # 构建快速查询集: (page_index, table_idx) -> True
    ocr_loc_set = set(tracker.ocr_table_locations)

    def patched_extract_params(self: PDFParser, table: Any) -> list:
        params = original_extract_params(self, table)

        # 解析表格编号 "第X页_表Y" -> (X-1, Y)
        is_ocr = False
        page_index = -1
        table_idx = -1
        表格编号 = getattr(table, "表格编号", "")
        if 表格编号:
            import re
            m = re.match(r"第(\d+)页_表(\d+)", 表格编号)
            if m:
                page_index = int(m.group(1)) - 1  # 0-based
                table_idx = int(m.group(2))        # 1-based
                is_ocr = (page_index, table_idx) in ocr_loc_set

        if is_ocr:
            表体 = getattr(table, "表体", [])
            tracker.param_records.append({
                "表格编号": 表格编号,
                "页码索引": page_index,
                "页码(1-based)": page_index + 1,
                "页内表格序号": table_idx,
                "表格标题": getattr(table, "表格标题", ""),
                "表头": getattr(table, "表头", []),
                "表体行数": len(表体),
                "表体前3行": 表体[:3],
                "产出参数数": len(params),
                "参数名列表": [getattr(p, "参数名称", "?") for p in params],
            })

        return params

    return patched_extract_params


def assess_probe_c(tracker: ProbeTracker) -> ProbeRecord:
    """对探查点 C 的结果做 PASS/FAIL 判定

    判定标准: 至少一个 OCR 来源表格产出 len(params) >= 1
    """
    if not tracker.param_records:
        if not tracker.parser_ran:
            return ProbeRecord(
                探查点="C",
                判定="SKIP",
                原始数据={"说明": "parser 未运行"},
                备注="跳过：parser 未执行",
            )
        return ProbeRecord(
            探查点="C",
            判定="FAIL",
            原始数据={
                "说明": "parser 已运行但未检测到任何 OCR 来源表格通过参数提取",
                "ocr_table_locations": tracker.ocr_table_locations,
            },
            备注="FAIL: 无 OCR 来源表格进入 _extract_parameters_from_table",
        )
    params_produced = any(r["产出参数数"] >= 1 for r in tracker.param_records)
    total_params = sum(r["产出参数数"] for r in tracker.param_records)
    return ProbeRecord(
        探查点="C",
        判定="PASS" if params_produced else "FAIL",
        原始数据={
            "OCR来源表格数": len(tracker.param_records),
            "总产出参数数": total_params,
            "各表参数详情": tracker.param_records,
        },
        备注=(f"PASS: {len(tracker.param_records)}个OCR表格共提取{total_params}个参数"
              if params_produced
              else f"FAIL: {len(tracker.param_records)}个OCR表格均未提取到参数"),
    )


# ═══════════════════════════════════════════════════════════════════════
# 诊断主流程
# ═══════════════════════════════════════════════════════════════════════

def find_test_samples() -> list[Path]:
    """查找可用的测试样本 (优先扫描版 CB 589-95.pdf)"""
    candidates = [
        ROOT / "input" / "scanned_version" / "CB 589-95.pdf",
        ROOT / "input" / "industry_standard" / "CB 589-95.pdf",
        ROOT / "input" / "industry_standard" / "Shipbuilding_Industry_Standards" / "CB 589-95.pdf",
    ]
    found = [p for p in candidates if p.is_file()]
    # 额外搜索：查找任意含 589 的 PDF
    if not found:
        import glob as _glob
        for pdf in sorted(Path(ROOT, "input").rglob("*589*.pdf")):
            if pdf not in found:
                found.append(pdf)
    return found


def resolve_sample(samples: list[Path]) -> Path | None:
    """从候选样本列表中返回第一个可用的扫描版样本"""
    if not samples:
        return None
    # 优先用 scanned_version
    for p in samples:
        if "scanned" in str(p).lower():
            return p
    return samples[0]


def run_diagnostic(pdf_path: Path, page_indices: list[int] | None = None,
                   dpi: int = 220, batch_size: int = 4) -> dict[str, Any]:
    """执行完整的三探查点诊断流程

    Args:
        pdf_path: 测试 PDF 路径
        page_indices: 要诊断的页码 (0-based)，默认 [0, 1, 2]
        dpi: OCR 渲染分辨率
        batch_size: OCR 批大小

    Returns:
        完整诊断报告字典
    """
    if page_indices is None:
        page_indices = [0, 1, 2]

    tracker = ProbeTracker()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # ── 探查点 A ──
    print(f"[探查A] 对 {pdf_path.name} 第{page_indices}页执行 OCR 表格识别 ...")
    t0 = time.perf_counter()
    ocr_table_map, runtime_meta = run_probe_a(pdf_path, page_indices, dpi=dpi, batch_size=batch_size)
    elapsed_a = time.perf_counter() - t0
    tracker.ocr_table_map = ocr_table_map
    tracker.ocr_runtime_meta = runtime_meta
    runtime_meta["探查A耗时秒"] = round(elapsed_a, 2)
    probe_a = assess_probe_a(ocr_table_map, runtime_meta)
    print(f"  -> {probe_a.判定}: {probe_a.备注}")

    # 如果没有 OCR 表格输出，后续探查点仍可进行但预期 SKIP
    ocr_pages_for_context = sorted(ocr_table_map.keys()) if ocr_table_map else page_indices

    # ── 准备 PipelineContext ──
    ctx = PipelineContext(force_ocr_tables=ocr_table_map)

    # 构建最小化 AppConfig（input_path / output_dir 为必填字段）
    config = AppConfig(
        input_path=pdf_path,
        output_dir=ROOT / "output",
    )

    # ── 探查点 B & C: 通过 patch 挂载 ──
    patched_b = make_probe_b_patch(tracker)
    patched_c = make_probe_c_patch(tracker)

    print("[探查B/C] 通过 monkey-patch 运行 PDFParser 捕获适配与参数提取 ...")
    t1 = time.perf_counter()
    try:
        with patch.object(PDFParser, "_extract_page_tables", patched_b), \
             patch.object(PDFParser, "_extract_parameters_from_table", patched_c):
            parser = PDFParser(config, ctx)
            _ = parser.parse()
            tracker.parser_ran = True
    except Exception as exc:
        print(f"  !! parser.parse() 异常: {exc}")
        import traceback
        traceback.print_exc()
        tracker.parser_ran = False
    elapsed_bc = time.perf_counter() - t1

    probe_b = assess_probe_b(tracker)
    probe_c = assess_probe_c(tracker)
    print(f"  -> B {probe_b.判定}: {probe_b.备注}")
    print(f"  -> C {probe_c.判定}: {probe_c.备注}")

    # ── 桥接诊断 ──
    bridge_verdict, bridge_breakpoint = diagnose_bridge(probe_a, probe_b, probe_c, tracker)

    # ── 组装报告 ──
    report = {
        "报告元信息": {
            "诊断脚本": "diagnostics/p0_3_ocr_table_bridge.py",
            "生成时间": timestamp,
            "样本PDF": str(pdf_path),
            "样本PDF存在": pdf_path.is_file(),
            "OCR页码索引(0-based)": page_indices,
            "OCR页码(1-based)": [p + 1 for p in page_indices],
            "OCR DPI": dpi,
            "OCR批大小": batch_size,
            "探查A耗时秒": elapsed_a,
            "探查B_C耗时秒": elapsed_bc,
            "parser运行成功": tracker.parser_ran,
        },
        "探查点A": {
            "判定": probe_a.判定,
            "备注": probe_a.备注,
            "详情": probe_a.原始数据,
        },
        "探查点B": {
            "判定": probe_b.判定,
            "备注": probe_b.备注,
            "详情": probe_b.原始数据,
        },
        "探查点C": {
            "判定": probe_c.判定,
            "备注": probe_c.备注,
            "详情": probe_c.原始数据,
        },
        "桥接诊断": {
            "总体判定": bridge_verdict,
            "断点定位": bridge_breakpoint,
            "分析": {
                "pdfplumber原生表格数": tracker.total_pdfplumber_tables,
                "OCR注入表格数": tracker.total_ocr_tables_injected,
                "OCR命中页码": sorted(ocr_table_map.keys()),
                "适配调用数": len(tracker.adapt_records),
                "OCR来源参数提取表数": len(tracker.param_records),
            },
        },
    }

    return report


def diagnose_bridge(probe_a: ProbeRecord, probe_b: ProbeRecord,
                    probe_c: ProbeRecord, tracker: ProbeTracker) -> tuple[str, str]:
    """诊断桥接链路并定位断点"""
    results = {
        "A": probe_a.判定,
        "B": probe_b.判定,
        "C": probe_c.判定,
    }

    # 全 PASS
    if all(v == "PASS" for v in results.values()):
        return "链路通畅", "OCR 表格召回 → 格式适配 → 参数提取全链路通过"

    # 确定第一个失败点
    failed_stages = [k for k in ["A", "B", "C"] if results.get(k) != "PASS"]

    if "A" in failed_stages:
        if probe_a.判定 == "SKIP":
            return "待指定样本", "探查点A 跳过（无可用的样本或OCR引擎）"
        # A 失败
        reason = ""
        if not tracker.ocr_table_map:
            reason = "OCR 引擎未检测到任何表格（返回空 dict）"
        else:
            meaningful = sum(
                1 for tables in tracker.ocr_table_map.values()
                for rows in tables if len(rows) >= 2
            )
            reason = (f"OCR 检测到 {sum(len(v) for v in tracker.ocr_table_map.values())} 个表格，"
                      f"但仅 {meaningful} 个行数 >= 2；OCR 召回后段可能丢弃")
        return "断点在A: OCR召回率不足", reason

    if "B" in failed_stages:
        if probe_b.判定 == "SKIP":
            return "断点在A→B: force_ocr_tables未注入", ("探查点A 产生了表格 "
                      f"({len(tracker.ocr_table_map)}页) 但探查点B未收到适配调用")
        valid = sum(1 for r in tracker.adapt_records if r["适配后行数满足(>=2)"])
        return "断点在B: 格式适配丢弃表格", (
            f"{len(tracker.adapt_records)}个OCR表格经 _adapt_ocr_table_matrix 适配后，"
            f"仅 {valid} 个满足 >=2 行要求；其余被丢弃"
        )

    if "C" in failed_stages:
        if probe_c.判定 == "SKIP":
            return "断点在B→C: OCR表格未进入参数提取", "探查点B 适配通过但探查点C 未收到 OCR 来源表格调用"
        return "断点在C: 参数提取无产出", (
            f"{len(tracker.param_records)}个OCR来源表格进入 _extract_parameters_from_table，"
            f"但均未提取到参数；请检查表头/表体格式是否被三路径提取器识别"
        )

    # 有 SKIP 但无 FAIL
    skips = [k for k in ["A", "B", "C"] if results.get(k) == "SKIP"]
    return f"部分跳过: {','.join(skips)}", f"探查点 {','.join(skips)} 因数据不足跳过；请指定有效的扫描型PDF样本重试"


def save_report(report: dict[str, Any]) -> Path:
    """保存诊断报告到 diagnostics/output/"""
    out_dir = ROOT / "diagnostics" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report["报告元信息"]["生成时间"]
    out_path = out_dir / f"p0_3_report_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return out_path


# ═══════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    samples = find_test_samples()
    sample = resolve_sample(samples)

    if sample is None:
        print("=" * 70)
        print("P0-3 诊断: 待指定样本")
        print("  未找到任何 PDF 测试样本。")
        print("  请将扫描版 CB 589-95.pdf 放入 input/scanned_version/ 目录。")
        print("=" * 70)
        # 输出框架报告
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        framework_report = {
            "报告元信息": {
                "诊断脚本": "diagnostics/p0_3_ocr_table_bridge.py",
                "生成时间": timestamp,
                "样本PDF": None,
                "样本PDF存在": False,
                "状态": "待指定样本",
            },
            "探查点A": {"判定": "SKIP", "备注": "未找到测试样本", "详情": {}},
            "探查点B": {"判定": "SKIP", "备注": "未找到测试样本", "详情": {}},
            "探查点C": {"判定": "SKIP", "备注": "未找到测试样本", "详情": {}},
            "桥接诊断": {
                "总体判定": "待指定样本",
                "断点定位": "无可用的 PDF 测试样本",
                "建议": "请将扫描版 PDF (如 CB 589-95.pdf) 放入 input/scanned_version/",
            },
        }
        out_path = save_report(framework_report)
        print(f"  框架报告已保存: {out_path}")
        sys.exit(0)

    print("=" * 70)
    print(f"P0-3 诊断: OCR 表格→参数桥接探查")
    print(f"  样本: {sample}")
    print(f"  候选样本: {[str(s) for s in samples]}")
    print("=" * 70)

    # 默认探查前 3 页
    report = run_diagnostic(sample, page_indices=[0, 1, 2])

    out_path = save_report(report)
    print(f"\n诊断报告已保存: {out_path}")
    print(f"总体判定: {report['桥接诊断']['总体判定']}")
    print(f"断点定位: {report['桥接诊断']['断点定位']}")
