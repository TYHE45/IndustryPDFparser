from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.reviewer import ISSUE_DEDUCTIONS

SNAPSHOT_VERSION = 1
FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "baseline_snapshots"

_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")

KEY_PROBLEMS = "\u95ee\u9898\u6e05\u5355"
KEY_PROBLEM_ID = "\u95ee\u9898ID"
KEY_LEVEL = "\u7ea7\u522b"
KEY_CONTENT = "\u5185\u5bb9"
KEY_DEDUCTION = "\u6263\u5206"
KEY_TOTAL_SCORE = "\u603b\u5206"
KEY_REDLINE_TRIGGERED = "\u7ea2\u7ebf\u89e6\u53d1"
KEY_REVIEW_ROUNDS = "\u8bc4\u5ba1\u8f6e\u6b21"
KEY_PROMPT_SIGNATURE = "\u63d0\u793a\u8bcd\u7b7e\u540d"
KEY_REVIEWER_SIGNATURE = "\u8bc4\u5ba1\u89c4\u5219\u7b7e\u540d"
KEY_SNAPSHOT_VERSION = "\u5feb\u7167\u7248\u672c"


def build_snapshot(review: dict[str, Any], process_log: dict[str, Any]) -> dict[str, Any]:
    """Compress pipeline output into a stable, diagnosis-oriented snapshot."""
    issues_raw = review.get(KEY_PROBLEMS, []) or []
    issues = []
    for item in issues_raw:
        issue_id = str(item.get(KEY_PROBLEM_ID, ""))
        content = str(item.get(KEY_CONTENT, ""))
        issues.append({
            KEY_PROBLEM_ID: issue_id,
            KEY_LEVEL: str(item.get(KEY_LEVEL, "")),
            KEY_DEDUCTION: float(ISSUE_DEDUCTIONS.get(content, ("", 0.0))[1]),
        })

    issues.sort(key=lambda item: (item[KEY_PROBLEM_ID], item[KEY_LEVEL]))
    return {
        KEY_SNAPSHOT_VERSION: SNAPSHOT_VERSION,
        KEY_TOTAL_SCORE: float(review.get(KEY_TOTAL_SCORE, 0.0) or 0.0),
        KEY_REDLINE_TRIGGERED: bool(review.get(KEY_REDLINE_TRIGGERED, False)),
        KEY_REVIEW_ROUNDS: int(process_log.get(KEY_REVIEW_ROUNDS, 0) or 0),
        KEY_PROMPT_SIGNATURE: str(process_log.get(KEY_PROMPT_SIGNATURE, "")),
        KEY_REVIEWER_SIGNATURE: str(process_log.get(KEY_REVIEWER_SIGNATURE, "")),
        KEY_PROBLEMS: issues,
    }


def find_missing_issue_deductions(review: dict[str, Any]) -> list[str]:
    """Return issue IDs whose source issue content is not covered by ISSUE_DEDUCTIONS."""
    missing: list[str] = []
    for item in review.get(KEY_PROBLEMS, []) or []:
        content = str(item.get(KEY_CONTENT, ""))
        if content not in ISSUE_DEDUCTIONS:
            missing.append(str(item.get(KEY_PROBLEM_ID, content)))
    return sorted(set(missing))


def serialize_snapshot(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def fixture_filename_for(sample_path: str) -> str:
    stem = Path(sample_path).stem
    ascii_part = _SANITIZE_RE.sub("_", stem).strip("_") or "sample"
    return f"{ascii_part}.json"
