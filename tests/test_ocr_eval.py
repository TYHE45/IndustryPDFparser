from __future__ import annotations

import unittest

from src.ocr_eval import (
    build_force_ocr_payload,
    build_page_eval_map,
    evaluate_ocr_batch,
    evaluate_single_ocr_page,
    normalize_ocr_text,
)
from src.models import OCRBatchEvaluation, OCRPageEvaluation


class NormalizeOcrTextTests(unittest.TestCase):
    def test_strips_empty_lines(self):
        self.assertEqual(normalize_ocr_text("a\n\nb\n  \nc"), "a\nb\nc")

    def test_empty_text(self):
        self.assertEqual(normalize_ocr_text(""), "")

    def test_none_text(self):
        self.assertEqual(normalize_ocr_text(None), "")


class EvaluateSingleOcrPageTests(unittest.TestCase):
    def test_empty_ocr_text_rejected(self):
        result = evaluate_single_ocr_page(page_index=0, native_text="", ocr_text="")
        self.assertEqual(result.评估等级, "拒绝")
        self.assertFalse(result.是否注入解析)

    def test_high_quality_text_passed(self):
        ocr_text = "\n".join([
            "1 范围",
            "本标准适用于压力容器设计。",
            "2 规范性引用文件",
            "GB/T 1234-2020 基础标准",
            "3 术语和定义",
            "下列术语和定义适用于本标准。",
            "3.1 工作压力",
            "容器在正常工作条件下承受的压力。",
            "4 分类",
            "按公称压力分为以下等级。",
        ])
        result = evaluate_single_ocr_page(page_index=0, native_text="", ocr_text=ocr_text)
        self.assertEqual(result.评估等级, "通过")
        self.assertTrue(result.是否注入解析)

    def test_marginal_with_structural_signal(self):
        ocr_text = "\n".join([
            "1 范围",
            "本标准适用于压力容器设计制造。",
            "GB/T 1234-2020 基础标准",
            "CB/T 589-1995 船用阀门",
        ])
        result = evaluate_single_ocr_page(page_index=0, native_text="", ocr_text=ocr_text)
        self.assertIn(result.评估等级, {"通过", "边缘"})

    def test_very_short_text_rejected(self):
        ocr_text = "短文本"
        result = evaluate_single_ocr_page(page_index=0, native_text="", ocr_text=ocr_text)
        self.assertEqual(result.评估等级, "拒绝")

    def test_fragmentation_downgrades_pass_to_marginal(self):
        # Isolated punctuation on short lines triggers fragmentation
        # Each line ends with Chinese period and has no CJK content on either side
        ocr_text = "\n".join([
            "范围。",
            "适用。",
            "压力。",
            "温度。",
            "材料。",
            "标准。",
        ])
        result = evaluate_single_ocr_page(page_index=0, native_text="", ocr_text=ocr_text)
        # Fragmentation may downgrade 通过→边缘 or 边缘→拒绝
        self.assertIn(result.评估等级, {"边缘", "拒绝"})

    def test_high_punctuation_noise_rejected(self):
        lines = ["。" * 30, "。" * 30, "。" * 30]
        ocr_text = "\n".join(lines)
        result = evaluate_single_ocr_page(page_index=0, native_text="", ocr_text=ocr_text)
        self.assertEqual(result.评估等级, "拒绝")

    def test_preserves_page_index(self):
        result = evaluate_single_ocr_page(page_index=5, native_text="", ocr_text="有内容")
        self.assertEqual(result.页码索引, 5)


class EvaluateOcrBatchTests(unittest.TestCase):
    def test_empty_target_pages(self):
        batch = evaluate_ocr_batch(
            native_page_texts={},
            target_pages=[],
            ocr_map={},
            engine="test",
            lang="ch",
            dpi=300,
            elapsed_seconds=0.5,
        )
        self.assertFalse(batch.是否执行OCR)
        self.assertEqual(batch.目标页数, 0)

    def test_single_accepted_page(self):
        target = [0]
        ocr_text = "\n".join([
            "1 范围",
            "本标准适用于压力容器设计制造。",
            "GB/T 1234-2020 基础标准",
            "CB/T 589-1995 船用阀门",
        ])
        ocr_map = {0: ocr_text}
        batch = evaluate_ocr_batch(
            native_page_texts={0: ""},
            target_pages=target,
            ocr_map=ocr_map,
            engine="test",
            lang="ch",
            dpi=300,
            elapsed_seconds=1.0,
        )
        self.assertTrue(batch.是否执行OCR)
        self.assertEqual(batch.目标页数, 1)
        self.assertEqual(batch.识别成功页数, 1)
        self.assertIn(0, batch.注入页码列表)

    def test_all_rejected(self):
        target = [0, 1]
        ocr_map = {0: "a", 1: ""}
        batch = evaluate_ocr_batch(
            native_page_texts={0: "", 1: ""},
            target_pages=target,
            ocr_map=ocr_map,
            engine="test",
            lang="ch",
            dpi=300,
            elapsed_seconds=0.5,
        )
        self.assertGreater(batch.拒绝页数, 0)

    def test_evaluation_conclusion(self):
        target = [0]
        ocr_map = {0: "有内容的文本行"}
        batch = evaluate_ocr_batch(
            native_page_texts={0: ""},
            target_pages=target,
            ocr_map=ocr_map,
            engine="test",
            lang="ch",
            dpi=300,
            elapsed_seconds=0.3,
        )
        self.assertIn(batch.评估结论, {"成功", "部分成功", "失败"})


class BuildForceOcrPayloadTests(unittest.TestCase):
    def test_filters_by_accepted_pages(self):
        ocr_map = {0: "文本A", 1: "文本B", 2: "文本C"}
        batch_eval = OCRBatchEvaluation(
            是否执行OCR=True,
            OCR引擎="test",
            OCR语言="ch",
            OCR_DPI=300,
            目标页数=3,
            注入页码列表=[0, 2],
        )
        payload = build_force_ocr_payload(ocr_map, batch_eval)
        self.assertIn(0, payload)
        self.assertIn(2, payload)
        self.assertNotIn(1, payload)

    def test_skips_empty_accepted(self):
        ocr_map = {0: "文本"}
        batch_eval = OCRBatchEvaluation(
            是否执行OCR=True,
            OCR引擎="test",
            OCR语言="ch",
            OCR_DPI=300,
            目标页数=1,
            注入页码列表=[],
        )
        payload = build_force_ocr_payload(ocr_map, batch_eval)
        self.assertEqual(payload, {})

    def test_normalizes_ocr_text(self):
        ocr_map = {0: " 文本  \n\n 更多  "}
        batch_eval = OCRBatchEvaluation(
            是否执行OCR=True,
            OCR引擎="test",
            OCR语言="ch",
            OCR_DPI=300,
            目标页数=1,
            注入页码列表=[0],
        )
        payload = build_force_ocr_payload(ocr_map, batch_eval)
        self.assertEqual(payload[0], "文本\n更多")


class BuildPageEvalMapTests(unittest.TestCase):
    def test_builds_page_map(self):
        page_eval = OCRPageEvaluation(页码索引=0, 有效字符数=100, 评估等级="通过", 判定原因=["OK"])
        batch_eval = OCRBatchEvaluation(
            是否执行OCR=True,
            OCR引擎="test",
            OCR语言="ch",
            OCR_DPI=300,
            目标页数=1,
            页级详情=[page_eval],
        )
        page_map = build_page_eval_map(batch_eval)
        self.assertIn(0, page_map)
        self.assertEqual(page_map[0]["有效字符数"], 100)


if __name__ == "__main__":
    unittest.main()
