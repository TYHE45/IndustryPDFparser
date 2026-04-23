from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
