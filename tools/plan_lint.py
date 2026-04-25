"""Plan-doc field-name drift linter.

Usage:
    python -m tools.plan_lint plan04.md
    python tools/plan_lint.py path/to/plan.md

Catches two historical drift patterns:
  - Pure English snake_case (e.g., `snapshot_version`) where Chinese counterpart exists
  - Chinglish mix (e.g., `prompt_签名`) where pure Chinese counterpart exists

Vocabulary source:
  - KNOWN_DRIFT_MAP is a manually maintained list of drift patterns already seen.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# 历史 drift 显式映射（每发生一次新的 drift, 加一行）
KNOWN_DRIFT_MAP: dict[str, str] = {
    "snapshot_version": "快照版本",
    "prompt_签名": "提示词签名",
    "reviewer_签名": "评审规则签名",
}

# 反引号包裹、长度 1-40 的标识符（避开行内代码块整段）
_BACKTICK_RE = re.compile(r"`([^`\n]{1,40})`")
_FENCE_RE = re.compile(r"^\s*```")
# 纯英文 snake_case
_PURE_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]+$")
# Chinglish: ASCII 字母 + 中文字符共存
_CHINGLISH_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*[\u4e00-\u9fff]).+$")


@dataclass
class LintIssue:
    line: int
    found: str
    suggestion: str
    rule: str  # "english_with_chinese_counterpart" | "chinglish_with_chinese_counterpart"

    def render(self) -> str:
        return f"L{self.line}: `{self.found}` → 建议改成 `{self.suggestion}`（规则：{self.rule}）"


def lint_text(text: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    in_fenced_code = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fenced_code = not in_fenced_code
            continue
        if in_fenced_code:
            continue
        for match in _BACKTICK_RE.finditer(line):
            ident = match.group(1)
            if ident in KNOWN_DRIFT_MAP:
                rule = _classify_rule(ident)
                issues.append(
                    LintIssue(
                        line=line_no,
                        found=ident,
                        suggestion=KNOWN_DRIFT_MAP[ident],
                        rule=rule,
                    )
                )
    return issues


def _classify_rule(ident: str) -> str:
    if _CHINGLISH_RE.match(ident):
        return "chinglish_with_chinese_counterpart"
    if _PURE_SNAKE_RE.match(ident):
        return "english_with_chinese_counterpart"
    return "english_with_chinese_counterpart"


def lint_file(path: Path) -> list[LintIssue]:
    return lint_text(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m tools.plan_lint <plan.md>", file=sys.stderr)
        return 2
    target = Path(argv[0])
    if not target.exists():
        print(f"file not found: {target}", file=sys.stderr)
        return 2
    issues = lint_file(target)
    if not issues:
        print(f"OK: no field-name drift in {target}")
        return 0
    print(f"DRIFT in {target}（共 {len(issues)} 条）：")
    for issue in issues:
        print(f"  {issue.render()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
