from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from config import AppConfig
from src.pipeline import run_iterative_pipeline
from tests.support.baseline_snapshot import (
    FIXTURES_ROOT,
    build_snapshot,
    find_missing_issue_deductions,
    fixture_filename_for,
    serialize_snapshot,
)


_ENABLE_SLOW_TESTS = os.getenv("SLOW_TESTS") == "1"
_UPDATE_SNAPSHOTS = os.getenv("UPDATE_BASELINE_SNAPSHOTS") == "1"
_INPUT_ROOT = Path("input")
_SCORE_TOLERANCE = 3.0
_SNAPSHOT_KNOWN_MISSING = {
    "industry_standard/Shipbuilding_Industry_Standards/CB_T 8522-2011 舾装码头设计规范.pdf",
}
_BASELINES: list[dict[str, object]] = [
    {"sample_path": "industry_standard/SN544-1.pdf", "expected_score": 88.0, "redline": False, "rounds": 1, "issues": 2},
    {"sample_path": "industry_standard/SN544-2.pdf", "expected_score": 88.0, "redline": False, "rounds": 2, "issues": 2},
    {"sample_path": "industry_standard/SN545-1.pdf", "expected_score": 81.0, "redline": False, "rounds": 1, "issues": 3},
    {"sample_path": "industry_standard/SN775_2009-07_e.pdf", "expected_score": 88.0, "redline": False, "rounds": 1, "issues": 2},
    {"sample_path": "industry_standard/CB 589-95.pdf", "expected_score": 74.0, "redline": True, "rounds": 2, "issues": 2},
    {"sample_path": "industry_standard/SN200_2007-02_中文.pdf", "expected_score": 74.0, "redline": False, "rounds": 1, "issues": 4},
    {"sample_path": "industry_standard/SN751.pdf", "expected_score": 79.0, "redline": False, "rounds": 2, "issues": 4},
    {
        "sample_path": "product_sample/Dixon.2017.pdf",
        "expected_score": 78.0,
        "redline": False,
        "rounds": 1,
        "issues": 3,
    },
    {
        "sample_path": "scanned_version/GB 39038-2020 船舶与海上技术 液化天然气加注干式快速接头技术要求.pdf",
        "expected_score": 63.0,
        "redline": False,
        "rounds": 3,
        "issues": 6,
    },
    {
        "sample_path": "industry_standard/Shipbuilding_Industry_Standards/CB_T 4196-2011 船用法兰　连接尺寸和密封面.pdf",
        "expected_score": 74.0,
        "redline": True,
        "rounds": 2,
        "issues": 4,
    },
    {
        "sample_path": "industry_standard/Shipbuilding_Industry_Standards/CB_Z 281-2011 船舶管路系统用垫片和填料选用指南.pdf",
        "expected_score": 81.0,
        "redline": False,
        "rounds": 2,
        "issues": 3,
    },
    {
        "sample_path": "industry_standard/Shipbuilding_Industry_Standards/CB_T 8522-2011 舾装码头设计规范.pdf",
        "expected_score": 82.0,
        "redline": False,
        "rounds": 3,
        "issues": 3,
    },
]


@unittest.skipUnless(_ENABLE_SLOW_TESTS, "需要显式设置 SLOW_TESTS=1 才运行样例得分快照测试。")
class SampleScoreBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_names = [fixture_filename_for(str(item["sample_path"])) for item in _BASELINES]
        if len(fixture_names) != len(set(fixture_names)):
            raise RuntimeError("样例结构快照 fixture 文件名存在冲突，请调整 fixture_filename_for。")

        missing = [str(item["sample_path"]) for item in _BASELINES if not (_INPUT_ROOT / str(item["sample_path"])).exists()]
        if missing:
            raise unittest.SkipTest(f"缺少样例语料，跳过慢速基线测试：{', '.join(missing)}")

    def test_sample_score_baselines_stay_within_expected_window(self) -> None:
        for baseline in _BASELINES:
            sample_path = Path(str(baseline["sample_path"]))
            display_name = sample_path.name
            input_path = _INPUT_ROOT / sample_path
            with self.subTest(sample=str(sample_path)), tempfile.TemporaryDirectory(prefix="sample_score_baseline_") as tempdir:
                result = run_iterative_pipeline(
                    AppConfig(
                        input_path=input_path,
                        output_dir=Path(tempdir),
                    )
                )

                review = result["review"] or {}
                review_rounds = result["review_rounds"] or []
                actual_score = float(review.get("总分", 0.0) or 0.0)
                actual_redline = bool(review.get("红线触发", False))
                actual_rounds = len(review_rounds)
                actual_issue_count = len(review.get("问题清单", []) or [])

                self.assertLessEqual(
                    abs(actual_score - float(baseline["expected_score"])),
                    _SCORE_TOLERANCE,
                    msg=f"{display_name} 总分漂移超过允许范围。",
                )
                self.assertEqual(actual_redline, bool(baseline["redline"]), msg=f"{display_name} 红线状态发生变化。")
                self.assertEqual(actual_rounds, int(baseline["rounds"]), msg=f"{display_name} 评审轮次发生变化。")
                self.assertEqual(actual_issue_count, int(baseline["issues"]), msg=f"{display_name} 问题数量发生变化。")

    def test_sample_score_baseline_snapshots_match_fixtures(self) -> None:
        for baseline in _BASELINES:
            sample_key = str(baseline["sample_path"])
            if sample_key in _SNAPSHOT_KNOWN_MISSING:
                continue

            sample_path = Path(str(baseline["sample_path"]))
            input_path = _INPUT_ROOT / sample_path
            fixture_path = FIXTURES_ROOT / fixture_filename_for(str(sample_path))
            with self.subTest(sample=str(sample_path)), tempfile.TemporaryDirectory(prefix="sample_score_snapshot_") as tempdir:
                result = run_iterative_pipeline(
                    AppConfig(
                        input_path=input_path,
                        output_dir=Path(tempdir),
                    )
                )

                review = result["review"] or {}
                process_log = result["process_log"] or {}
                missing_deductions = find_missing_issue_deductions(review)
                self.assertEqual(
                    missing_deductions,
                    [],
                    msg=f"{sample_path.name} 存在 ISSUE_DEDUCTIONS 映射缺口：{missing_deductions}",
                )

                serialized = serialize_snapshot(build_snapshot(review, process_log))
                if _UPDATE_SNAPSHOTS:
                    fixture_path.parent.mkdir(parents=True, exist_ok=True)
                    fixture_path.write_text(serialized, encoding="utf-8")
                    continue

                self.assertTrue(
                    fixture_path.exists(),
                    msg=f"{fixture_path.name} 缺失；先用 UPDATE_BASELINE_SNAPSHOTS=1 生成",
                )
                expected = fixture_path.read_text(encoding="utf-8")
                self.assertEqual(
                    serialized,
                    expected,
                    msg=f"{sample_path.name} 结构快照发生变化，看 git diff 定位哪条 issue 动了",
                )


if __name__ == "__main__":
    unittest.main()
