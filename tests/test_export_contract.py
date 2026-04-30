from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.exporter import export_all
from tests.helpers import build_sample_document


class ExportContractTests(unittest.TestCase):
    def test_export_all_writes_required_files_and_filters_internal_keys(self) -> None:
        document = build_sample_document()
        summary = {
            "文档概述": "这是一份用于测试导出契约的摘要。",
            "_llm_backend": "mock",
        }
        tags = {
            "主题标签": ["阀门", "标准"],
            "_llm_reason": "fallback",
        }
        process_log = {
            "最终是否通过": True,
            "最终总分": 95.0,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "out"
            export_all(
                output_dir,
                document,
                "# 1 范围\n用于测试导出契约的正文。",
                summary,
                tags,
                process_log,
            )

            expected_files = {
                "文档画像.json",
                "章节结构.json",
                "表格.json",
                "数值型参数.json",
                "规则类内容.json",
                "检验与证书.json",
                "引用标准.json",
                "trace_map.json",
                "原文解析.md",
                "summary.json",
                "tags.json",
                "process_log.json",
            }
            actual_files = {path.name for path in output_dir.iterdir() if path.is_file()}
            self.assertEqual(actual_files, expected_files)

            summary_payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            tags_payload = json.loads((output_dir / "tags.json").read_text(encoding="utf-8"))
            self.assertNotIn("_llm_backend", summary_payload)
            self.assertNotIn("_llm_reason", tags_payload)
            self.assertEqual(summary_payload["文档概述"], summary["文档概述"])
            self.assertEqual(tags_payload["主题标签"], tags["主题标签"])

            deprecated_files = {
                "document_profile.json",
                "内容块.json",
                "tables.json",
                "原文解析.json",
                "facts.json",
            }
            self.assertTrue(deprecated_files.isdisjoint(actual_files))

    def test_export_all_empty_document_writes_structure_skel(self):
        from src.models import DocumentData, FileMetadata
        empty_doc = DocumentData(文件元数据=FileMetadata(
            文件名称="empty.pdf", 文件类型="pdf", 文档标题="空文档",
            文档类型="standard", 标准编号="", 版本日期="", 适用范围="",
        ))
        with tempfile.TemporaryDirectory() as tmpdir:
            export_all(Path(tmpdir), empty_doc, "", {}, {}, {})
            files = os.listdir(tmpdir)
            self.assertIn("文档画像.json", files)
            self.assertIn("章节结构.json", files)
            # Empty sections produce valid JSON
            sections_path = Path(tmpdir) / "章节结构.json"
            self.assertTrue(sections_path.exists())
            data = json.loads(sections_path.read_text(encoding="utf-8"))
            self.assertEqual(data, [])

    def test_export_all_with_ocr_confidence_writes_file(self):
        doc = build_sample_document()
        with tempfile.TemporaryDirectory() as tmpdir:
            export_all(Path(tmpdir), doc, "", {}, {}, {}, ocr_confidence={"page_0": 0.95})
            ocr_conf_path = Path(tmpdir) / "OCR置信度.json"
            self.assertTrue(ocr_conf_path.exists())
            data = json.loads(ocr_conf_path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"page_0": 0.95})

    def test_export_all_process_log_not_filtered(self):
        doc = build_sample_document()
        process_log = {"_internal_key": "keep_me", "normal_key": "value"}
        with tempfile.TemporaryDirectory() as tmpdir:
            export_all(Path(tmpdir), doc, "", {}, {}, process_log)
            pl_path = Path(tmpdir) / "process_log.json"
            self.assertTrue(pl_path.exists())
            data = json.loads(pl_path.read_text(encoding="utf-8"))
            self.assertIn("_internal_key", data)
            self.assertEqual(data["_internal_key"], "keep_me")

    def test_export_all_chinese_content_survives_roundtrip(self):
        doc = build_sample_document()
        summary = {"文档概述": "本标准规定了“阀门”的技术要求——包括密封性。"}
        with tempfile.TemporaryDirectory() as tmpdir:
            export_all(Path(tmpdir), doc, "", summary, {}, {})
            s_path = Path(tmpdir) / "summary.json"
            data = json.loads(s_path.read_text(encoding="utf-8"))
            self.assertEqual(data["文档概述"], summary["文档概述"])


if __name__ == "__main__":
    unittest.main()
