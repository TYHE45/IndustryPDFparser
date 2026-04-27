"""Run a single baseline sample in a subprocess and print results as JSON.

Usage: python -m tests._run_baseline_sample <sample_path>
Output: JSON line with {sample_path, passed, score, redline, rounds, issues, error}
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import AppConfig
from src.contracts import KEY_PASSED, KEY_PROBLEMS, KEY_REDLINE_TRIGGERED, KEY_TOTAL_SCORE
from src.pipeline import run_iterative_pipeline
from tests.support.baseline_snapshot import (
    build_snapshot,
    find_missing_issue_deductions,
    serialize_snapshot,
)


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "missing sample_path argument"}))
        sys.exit(1)

    sample_path = sys.argv[1]
    input_root = Path("input")
    input_path = input_root / sample_path

    if not input_path.exists():
        print(json.dumps({"sample_path": sample_path, "error": f"file not found: {input_path}"}))
        sys.exit(1)

    try:
        with tempfile.TemporaryDirectory(prefix="baseline_sample_") as tempdir:
            result = run_iterative_pipeline(
                AppConfig(
                    input_path=input_path,
                    output_dir=Path(tempdir),
                )
            )
        review = result.get("review") or {}
        review_rounds = result.get("review_rounds") or []
        process_log = result.get("process_log") or {}
        output: dict[str, object] = {
            "sample_path": sample_path,
            "passed": True,
            "score": float(review.get(KEY_TOTAL_SCORE, 0.0) or 0.0),
            "redline": bool(review.get(KEY_REDLINE_TRIGGERED, False)),
            "rounds": len(review_rounds),
            "issues": len(review.get(KEY_PROBLEMS, []) or []),
            "_review": review,
            "_process_log": process_log,
        }
        # Snapshot fixture comparison data
        try:
            output["_snapshot_serialized"] = serialize_snapshot(build_snapshot(review, process_log))
        except Exception as exc:
            output["_snapshot_error"] = str(exc)
        try:
            output["_missing_deductions"] = find_missing_issue_deductions(review)
        except Exception as exc:
            output["_missing_deductions_error"] = str(exc)
        print(json.dumps(output, ensure_ascii=False, default=str))
    except Exception as exc:
        output = {
            "sample_path": sample_path,
            "passed": False,
            "error": str(exc),
        }
        print(json.dumps(output, ensure_ascii=False, default=str))
        sys.exit(1)


if __name__ == "__main__":
    main()
