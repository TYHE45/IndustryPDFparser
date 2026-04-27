"""Plan-doc field-name drift linter.

Usage:
    python -m tools.plan_lint plan04.md
    python tools/plan_lint.py path/to/plan.md

Catches two historical drift patterns:
  - Pure English snake_case (e.g., `snapshot_version`) where Chinese counterpart exists
  - Chinglish mix (e.g., `prompt_签名`) where pure Chinese counterpart exists

Vocabulary sources:
  - KNOWN_DRIFT_MAP is a manually maintained list of drift patterns already seen
  - src.contracts KEY_* constants
  - tests/support/baseline_snapshot.py KEY_SNAPSHOT_VERSION
  - src/pipeline.py process_log string keys
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_SNAPSHOT_FILE = _REPO_ROOT / "tests" / "support" / "baseline_snapshot.py"
_PIPELINE_FILE = _REPO_ROOT / "src" / "pipeline.py"
_FALLBACK_CANONICAL_VOCAB = frozenset({
    "问题清单",
    "问题ID",
    "级别",
    "内容",
    "扣分",
    "总分",
    "红线触发",
    "评审轮次",
    "提示词签名",
    "评审规则签名",
    "快照版本",
})

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
_AUTO_CHINGLISH_IDENTIFIER_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*[\u4e00-\u9fff])[A-Za-z0-9_\u4e00-\u9fff]+$")
_CHINESE_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


@dataclass
class LintIssue:
    line: int
    found: str
    suggestion: str
    rule: str  # english_with_chinese_counterpart | chinglish_with_chinese_counterpart | chinglish_via_canonical_vocab

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
                continue
            if _AUTO_CHINGLISH_IDENTIFIER_RE.match(ident):
                canonical = _chinglish_canonical_match(ident, _load_canonical_vocab())
                if canonical and canonical != ident:
                    issues.append(
                        LintIssue(
                            line=line_no,
                            found=ident,
                            suggestion=canonical,
                            rule="chinglish_via_canonical_vocab",
                        )
                    )
    return issues


@lru_cache(maxsize=1)
def _load_canonical_vocab() -> frozenset[str]:
    vocab: set[str] = set()
    vocab.update(_load_contract_key_values())

    snapshot_version_key = _load_baseline_snapshot_version_key()
    if snapshot_version_key:
        vocab.add(snapshot_version_key)

    vocab.update(_load_process_log_string_keys())
    if not vocab:
        vocab.update(_FALLBACK_CANONICAL_VOCAB)
    return frozenset(vocab)


def _load_contract_key_values() -> set[str]:
    try:
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from src import contracts
    except Exception:
        return set()

    values: set[str] = set()
    for name in dir(contracts):
        if name.startswith("KEY_"):
            value = getattr(contracts, name)
            if isinstance(value, str) and _has_chinese(value):
                values.add(value)
    return values


def _load_baseline_snapshot_version_key() -> str | None:
    try:
        tree = ast.parse(_BASELINE_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None

    for node in tree.body:
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "KEY_SNAPSHOT_VERSION" for target in node.targets):
                value_node = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "KEY_SNAPSHOT_VERSION"
        ):
            value_node = node.value

        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            return value_node.value
    return None


def _load_process_log_string_keys() -> set[str]:
    try:
        tree = ast.parse(_PIPELINE_FILE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "process_log" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        keys: set[str] = set()
        for key_node in node.value.keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str) and _starts_with_chinese(key_node.value):
                keys.add(key_node.value)
        return keys
    return set()


def _chinglish_canonical_match(ident: str, vocab: frozenset[str]) -> str | None:
    runs = _CHINESE_RUN_RE.findall(ident)
    if not runs:
        return None
    longest = max(runs, key=len)
    candidates = [token for token in vocab if token.endswith(longest)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _classify_rule(ident: str) -> str:
    if _CHINGLISH_RE.match(ident):
        return "chinglish_with_chinese_counterpart"
    if _PURE_SNAKE_RE.match(ident):
        return "english_with_chinese_counterpart"
    return "english_with_chinese_counterpart"


def _has_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _starts_with_chinese(value: str) -> bool:
    return bool(value) and "\u4e00" <= value[0] <= "\u9fff"


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
