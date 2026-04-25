# Context

2026042404plan 已整轮收口（4 commits：`c6a1ec3 / 031873a / 55ffa28 / 4c732f0`），结构层 baseline snapshot 入 git 完成 11/12，FP §11 已固化"诊断加速器"主题。本轮核对发现 **2 条工程纪律层留尾，且都是历史教训未被工程化导致的复发**：

1. **`tests/fixtures/baseline_snapshots/*.json` 11 份全部以 CRLF 落盘**（Windows 下 `Path.write_text` 默认行为），与 `serialize_snapshot` 显式 `+ "\n"` 约定不一致。当前 Windows 单端 `assertEqual` 仍通过，但接 Linux CI / 异地协作即爆 diff。同型风险延伸到所有 `tests/fixtures/`、`*.md`。`.gitattributes` 在仓库根目录**完全不存在**。
2. **plan 字段命名 drift 已发生 2 次**：2026042403 `prompt_签名 → 提示词签名`（commit `84a3397` bonus fixup），2026042404 `snapshot_version → 快照版本`（plan04 §1.1 伪代码与实际 `tests/support/baseline_snapshot.py:15-25` `KEY_*` 常量不一致）。教训写进 FP 后仍复发，说明纯文字护栏失效，需要工程化检查。

**本轮 plan 用户已选定 A+B（工程纪律层）方向**，操作性目标：

> 把"plan 字段命名"和"fixture/资产 EOL"两类 drift 从"事后 fixup"升级到"事前/事中工程化护栏"，让历史教训不再以 bonus commit 形式复发。

3 个 commit 收口：B（EOL 修齐 + fixture LF 重生成）、A（plan-lint 工具 + 单元测试）、FP §11 落幕。

**当前 working tree 状态：**

```
 M First Principles.md   # plan04 核对 + 6 条工程性留尾 + 4 条新 P1 待办已追加，未提交
```

FP 改动与本轮 Stage 3 同 commit。

---

# Plan

## 阶段 1（B）：fixture / 文本资产跨平台 EOL 工程化

**目标**：让 fixture / md 资产落盘永远 LF，杜绝 Windows ↔ Linux EOL 差异 diff。

### 1.1：新建 `.gitattributes`

仓库根目录新建（survey 已确认绝对不存在）：

```
# Force LF for text artifacts that participate in byte-exact diff (fixtures, docs)
*.json text eol=lf
*.md text eol=lf
*.py text eol=lf
*.txt text eol=lf

# Binary fences
*.pdf binary
*.png binary
*.jpg binary
```

设计要点：
- `*.json text eol=lf` 是核心：覆盖 `tests/fixtures/baseline_snapshots/*.json` + `output/**/*.json` 两条线
- `*.md text eol=lf` 覆盖 `First Principles.md` + `plan*.md` + `.agent/plans/*.md`
- `*.py text eol=lf` 是顺手的工程卫生（Python 源码本来就该 LF）
- `*.pdf / *.png / *.jpg binary` 是兜底，防止 git 把扫描件 PDF 误识别为文本做 EOL 转换

### 1.2：`tests/test_sample_score_baseline.py:142` 修 `newline=`

把：
```python
fixture_path.write_text(serialized, encoding="utf-8")
```
改成：
```python
fixture_path.write_text(serialized, encoding="utf-8", newline="\n")
```

**why 改在调用处而非 `serialize_snapshot`**：`serialize_snapshot` 仅 return string，无 IO 责任；保持单一职责，把"如何写文件"留给 caller。

### 1.3：重生成 11 份 fixture 为 LF

命令：
```
UPDATE_BASELINE_SNAPSHOTS=1 SLOW_TESTS=1 python -m unittest tests.test_sample_score_baseline.SampleScoreBaselineTests.test_sample_score_baseline_snapshots_match_fixtures 2>&1 | tee _tmp_eol_regen.log
```

**ops fragility 预案（沿用 plan04 教训）**：
- 触发：单样例 > 15 分钟 或 OpenAI 429 累计 > 3 次
- 降级：保留现有 11 份不动，跳过本步——只要 `.gitattributes` + `newline="\n"` 已就位，**未来任何 `UPDATE_BASELINE_SNAPSHOTS=1` 重生成都会自动 LF**，本轮即使不重生成也已闭合"未来不再 CRLF"
- 不降级目标：60 分钟内全跑完一次性 LF 化

### 1.4：验收

```bash
# Windows 上验证：
git ls-files --eol tests/fixtures/baseline_snapshots/*.json  # 应全 i/lf
python -c "print(repr(open('tests/fixtures/baseline_snapshots/SN544-1.json','rb').read()[:20]))"
# 期望看到 b'{\n  "...' 而非 b'{\r\n  "...'
```

### 1.5：commit 1 — `chore(fixtures): enforce LF eol for json/md/py via .gitattributes`

- 文件：`.gitattributes`（新建）+ `tests/test_sample_score_baseline.py`（1 行改）+ `tests/fixtures/baseline_snapshots/*.json`（重生成时全部 LF；若降级则保留 CRLF 待下轮自动 LF 化）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 仍 40/40 + 1 skipped；`SLOW_TESTS=1` 验证 fixture 字符串级比对仍通过
- 提交信息要点：`.gitattributes` 三类规则起源、`newline="\n"` 修复点、是否降级及后果（"未来 LF" vs "本轮即 LF"）

---

## 阶段 2（A）：plan-lint 工具

**目标**：写一个轻量 lint 工具，扫 plan markdown 文件里所有反引号字段名，对照"已知字段词典"检测 2 类历史 drift（纯英文 snake_case 替换 vs 中文契约 / Chinglish 替换 vs 纯中文契约）。每次起草新 plan 时手动跑一次 `python -m tools.plan_lint <plan_path>`，落地前最后一道检查。

### 2.1：新建 `tools/__init__.py` + `tools/plan_lint.py`

仓库根目录建 `tools/`（survey 确认目录约定不存在；选 `tools/` 而非 `_tools/` 因为 `_` 前缀在本项目内部约定是 transient/gitignored，工具脚本应该入 git）。

`tools/__init__.py`：空文件。

`tools/plan_lint.py` 结构：

```python
"""Plan-doc field-name drift linter.

Usage:
    python -m tools.plan_lint plan04.md
    python tools/plan_lint.py path/to/plan.md

Catches two historical drift patterns:
  - Pure English snake_case (e.g., `snapshot_version`) where Chinese counterpart exists
  - Chinglish mix (e.g., `prompt_签名`) where pure Chinese counterpart exists

Vocabulary sources (loaded at lint time):
  - tests/support/baseline_snapshot.py KEY_* constants
  - src/config_signatures.py public function semantics (manual seed)
  - First Principles.md §11 backtick-quoted field references (auto-extracted)
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

# 反引号包裹、长度 1–40 的标识符（避开行内代码块整段）
_BACKTICK_RE = re.compile(r"`([^`\n]{1,40})`")
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
    for line_no, line in enumerate(text.splitlines(), start=1):
        for m in _BACKTICK_RE.finditer(line):
            ident = m.group(1)
            if ident in KNOWN_DRIFT_MAP:
                rule = "chinglish_with_chinese_counterpart" if _CHINGLISH_RE.match(ident) else "english_with_chinese_counterpart"
                issues.append(LintIssue(line=line_no, found=ident, suggestion=KNOWN_DRIFT_MAP[ident], rule=rule))
    return issues


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
    for it in issues:
        print(f"  {it.render()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

**关键设计点**：
- **不引入新依赖**，只用 stdlib
- **核心是 `KNOWN_DRIFT_MAP` 显式词典**，不试图自动推断"哪些英文字段在 FP 里有中文对应"——自动推断容易误报，显式映射清单则是"已发生过的 drift"的累积记录，每发生新一类 drift 就加一行
- **不限定 plan 文件路径**：传 `plan04.md` / `plan05.md` / `tests/test_xxx.py` 任何文件都能扫
- **退出码契约**：0 = clean，1 = 发现 drift，2 = 用法错误。便于未来接 pre-commit hook 或 CI step

### 2.2：新建 `tests/test_plan_lint.py`

```python
from __future__ import annotations
import unittest
from tools.plan_lint import lint_text, KNOWN_DRIFT_MAP


class PlanLintTests(unittest.TestCase):
    def test_clean_plan_returns_no_issues(self) -> None:
        text = "# Header\n顶层字段 `快照版本` 与 `提示词签名` 已对齐 FP 契约。"
        self.assertEqual(lint_text(text), [])

    def test_pure_english_snake_case_with_chinese_counterpart_flagged(self) -> None:
        text = "Stage 1 引入 `snapshot_version` 作为顶层字段。"
        issues = lint_text(text)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].found, "snapshot_version")
        self.assertEqual(issues[0].suggestion, "快照版本")
        self.assertEqual(issues[0].rule, "english_with_chinese_counterpart")

    def test_chinglish_mix_with_pure_chinese_counterpart_flagged(self) -> None:
        text = "process_log 新增 `prompt_签名` 与 `reviewer_签名` 两字段。"
        issues = lint_text(text)
        self.assertEqual(len(issues), 2)
        suggestions = sorted(it.suggestion for it in issues)
        self.assertEqual(suggestions, ["提示词签名", "评审规则签名"])
        for it in issues:
            self.assertEqual(it.rule, "chinglish_with_chinese_counterpart")

    def test_known_drift_map_uses_correct_rule_classification(self) -> None:
        # snapshot_version 是纯英文，prompt_签名 是 Chinglish
        self.assertNotIn("\u4e00", "snapshot_version")  # no Chinese chars
        self.assertTrue(any("\u4e00" <= c <= "\u9fff" for c in "prompt_签名"))

    def test_arbitrary_backtick_identifiers_not_in_map_pass_through(self) -> None:
        text = "调用 `run_iterative_pipeline` 与 `process_log.json` 是合理的。"
        # 这两个不在 KNOWN_DRIFT_MAP 里，应该不报
        self.assertEqual(lint_text(text), [])


if __name__ == "__main__":
    unittest.main()
```

设计要点：
- 5 条断言覆盖：clean pass / 纯英文规则 / Chinglish 规则 / 规则分类正确性 / 未知字段不误报
- 不跑实际文件 IO，只测纯函数 `lint_text(str) -> list[LintIssue]`
- 测试文件名 `test_plan_lint.py` 自动被 `unittest discover -p "test_*.py"` 收

### 2.3：手测 `python -m tools.plan_lint plan04.md`

预期输出：
```
DRIFT in plan04.md（共 N 条）：
  L66: `snapshot_version` → 建议改成 `快照版本`（规则：english_with_chinese_counterpart）
  ...
```

**这里是关键诚实点**：plan04 已经收口入 git，`snapshot_version` 是 plan 文档里**历史伪代码**的偏离，不是 fixture 实际偏离（实际 fixture 已是 `快照版本`）。所以 lint 报出来不需要修 plan04 文档，**lint 的价值是给 plan05+ 起草时用**。本步只是验收 lint 工具能否检测出已知 drift。

### 2.4：commit 2 — `feat(tools): add plan-lint to catch field-name drift before plan landing`

- 文件：`tools/__init__.py`（新建）+ `tools/plan_lint.py`（新建）+ `tests/test_plan_lint.py`（新建）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 40 → 45（+5 新测试）全通过
- 预检：`python -m tools.plan_lint plan04.md` 报告至少 1 条 drift（验证 lint 真在工作）
- 提交信息要点：lint 检测的两类 drift 模式起源（哪两次历史 fixup）；`KNOWN_DRIFT_MAP` 是手维护清单不是自动推断；用法 `python -m tools.plan_lint <plan_path>`；退出码契约

---

## 阶段 3：FP §11 收口

**目标**：把 §11「下一阶段待办」里的两条工程性条目从 `[ ]` 改 `[x]` + 新增"2026042405plan 整轮收口"条目记录本轮 commit hash + 链接 plan-lint 用法。

### 3.1：FP §11 改动清单

1. 「整体流程再审视」段：
   - `- [ ] **fixture / 文本资产的跨平台 EOL 工程化**` → `- [x]`，追加 commit hash 与 `.gitattributes` 落地说明
   - `- [ ] **plan 字段命名对齐 FP 中文契约**` 升级段：把"下轮起加一条 plan 起草最后一步 lint"从设想改为"已落地为 `tools/plan_lint.py`"，附用法示例

2. 「近期落地」段（在 2026042404plan 整轮收口条目之后）追加：
```
- [x] 2026042405plan：plan-lint + EOL 工程化护栏（3 commits：`<c1> / <c2> / <c3>`）
  - Stage 1（`<c1>`）：新建 `.gitattributes`（`*.json/*.md/*.py text eol=lf` + `*.pdf binary` 兜底）；`tests/test_sample_score_baseline.py:142` 写 fixture 加 `newline="\n"`；按 ops fragility 预案 [全量 LF 重生成 11 份 / 仅就位未来 LF 化] 二选一
  - Stage 2（`<c2>`）：新建 `tools/plan_lint.py`，扫 plan markdown 反引号字段名，对照 `KNOWN_DRIFT_MAP` 检测两类历史 drift（纯英文 snake_case vs 中文契约、Chinglish 混合 vs 纯中文契约）；新增 `tests/test_plan_lint.py` 5 条
  - Stage 3（本 commit）：FP §11 把两条工程性待办改 `[x]`，固化 plan-lint 用法
  - **下轮 plan 起草工作流（写进本条目以备查）**：plan ready 但未 ExitPlanMode 前，必须 `python -m tools.plan_lint <plan_path>` 退出码 0；非 0 时回头修 plan 字段名再 lint，直到 clean
  - **新增 drift 时维护 `KNOWN_DRIFT_MAP`**：每发现一类新 drift（如未来 plan 写 `pipeline_log` 但实际是 `运行日志`），plan-lint 工具同 commit 加一行映射，让 lint 能力随项目演进
```

### 3.2：commit 3 — `docs(fp): close 2026042405 plan-lint+EOL plan and document workflow integration`

- 文件：仅 `First Principles.md`
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 仍 45/45 + 1 skipped
- 预检：`python -m tools.plan_lint "First Principles.md"` 退出码 0 或报告 → 若报告，说明 FP 自身仍含历史 drift 引用（如把"`prompt_签名`"作历史叙事保留），这种情况记入 commit message 但不修——因为 FP 是历史档案而非新合约

---

## 最终：推送与收口

- `git log origin/main..HEAD --oneline` 应为 3 条（commit 1–3）
- `git push origin main`
- 本地 `git status --short` 干净
- 至此工程纪律层 2 类高频 drift 都升级到工程化护栏；下一轮 plan 起草将首次受 plan-lint 保护

---

# Critical Files

| 路径 | 本轮作用 |
|------|---------|
| `.gitattributes` | 阶段 1：新建。`*.json/*.md/*.py text eol=lf` + `*.pdf/*.png/*.jpg binary` |
| `tests/test_sample_score_baseline.py` | 阶段 1：第 142 行 `write_text` 加 `newline="\n"`，单行改 |
| `tests/fixtures/baseline_snapshots/*.json` | 阶段 1：重生成时全部 LF；若降级则保留 CRLF 待下轮自动 LF 化 |
| `tools/__init__.py` | 阶段 2：新建空 package marker |
| `tools/plan_lint.py` | 阶段 2：新建。`lint_text` / `lint_file` / `main` + `KNOWN_DRIFT_MAP` 显式词典 |
| `tests/test_plan_lint.py` | 阶段 2：新建。5 条断言覆盖 clean / 两类规则 / 规则分类 / 未知字段不误报 |
| `First Principles.md` | 阶段 3：§11 两条工程性待办改 `[x]` + 追加 2026042405 整轮收口条目 |
| `tests/support/baseline_snapshot.py` | 阶段 2 **只读**。其 `KEY_*` 常量是 `KNOWN_DRIFT_MAP` 中文侧的 ground truth 来源（未来 plan-lint 升级时可改为运行期 import 这些常量自动 seed） |
| `src/pipeline.py` | 阶段 1/2 **只读**。process_log 字典字面量 230-260 行是 plan-lint 未来扩展 vocab 的参考点 |

---

# Verification

**阶段 1（commit 1 前）：**
- 新 `.gitattributes` 内容核对：4 条 text eol=lf + 3 条 binary
- `tests/test_sample_score_baseline.py:142` 改动 `git diff` 仅 1 行 `newline="\n"` 增量
- 若全量重生成成功：`git ls-files --eol tests/fixtures/baseline_snapshots/*.json` 全部 `i/lf`；其中 3 份用 `python -c "print(repr(open(...,'rb').read()[:20]))"` 验证 b'{\n' 起头
- 若降级未重生成：fixture 仍 CRLF，但 `.gitattributes` 已就位，下次 `UPDATE_BASELINE_SNAPSHOTS=1` 自动 LF。commit message 必须明示降级
- `python -m unittest discover -s tests -p "test_*.py"`：40/40 + 1 skipped 不变

**阶段 2（commit 2 前）：**
- `python -m unittest discover -s tests -p "test_*.py"`：40 → 45 全通过
- `python -m tools.plan_lint plan04.md` 退出码 1 + 至少报出 1 条 drift（验证 lint 真在工作；若 plan04 内不再含 `snapshot_version` 反引号引用，需查 plan04 实际内容确认；本验证目的是"lint 工具自身可用"）
- `python -m tools.plan_lint nonexistent.md` 退出码 2（用法错误）
- `python -m tools.plan_lint tests/test_plan_lint.py` 退出码 0（lint 可处理任意 markdown 文件以外的 plain text）

**阶段 3（commit 3 前）：**
- `git log origin/main..HEAD --oneline` = 3 条
- FP §11 改动核对：两条 `[ ] → [x]`、追加新「近期落地」条目
- `python -m unittest discover -s tests -p "test_*.py"` 45/45 + 1 skipped 不变

**全部完成后：**
- `git push origin main` 成功
- `git status --short` 干净
- 下次起草 plan05 时，最后一步 `python -m tools.plan_lint <plan>.md` 退出码 0 才能 ExitPlanMode（手动工作流，非自动门禁；自动化进 pre-commit hook 留给后续）

---

# 风险与回滚点

- **阶段 1 ops fragility 复发**：plan04 第 12 份样例 `CB_T 8522-2011` 已 known_missing，本轮全量重生成有同样风险。降级路径已写明（`.gitattributes` + `newline="\n"` 就位即关闭"未来 CRLF"风险，本轮即使不重生成也算闭合）；commit message 必须显式说明降级与否
- **阶段 1 `.gitattributes` 对已入库文件的回填行为**：git 添加 `.gitattributes` 不会自动重写已入库文件的 EOL；只影响新增/修改的文件。所以"重生成 11 份 fixture"和"`.gitattributes` 落地"是双写需求，缺一会留半套 CRLF。若降级跳过重生成，FP §11 必须明记"现有 11 份仍 CRLF，下轮 `UPDATE_BASELINE_SNAPSHOTS=1` 会自动 LF 化"
- **阶段 2 `KNOWN_DRIFT_MAP` 维护成本**：手维护意味着每发现新 drift 要加映射；好处是零误报、起步即可用、随项目演进。坏处是新 drift 第一次发生时仍会漏检（lint 不能未卜先知）。这是设计折中，不是缺陷
- **阶段 2 plan-lint 与 pre-commit hook 的边界**：本轮**不**接 pre-commit hook，只是手动工具。原因：(a) 项目目前无 hook 基础设施，引入 `pre-commit` 框架是另一类改动；(b) lint 工具自身需要先在几轮 plan 中被实际使用、词典需要积累再上自动化；(c) 自动门禁挡住合法 plan（如某 plan 故意叙事性引用历史 `prompt_签名` 字符串）会推高摩擦，先用手动一段时间观察
- **阶段 2 plan-lint 误报历史 plan 文档**：plan02–04 的历史 markdown 里都含 `prompt_签名` / `snapshot_version` 等字面引用（作为叙事讨论），`python -m tools.plan_lint plan04.md` 大概率报多条。这不是 lint 缺陷，是历史叙事场景；plan-lint 在 commit message 中说明"未来新 plan 应 clean，老 plan 报多条是档案性质"
- **阶段 3 FP §11 自身 lint 报多条**：FP §11 大量历史叙事性引用 `prompt_签名`、`snapshot_version`，`python -m tools.plan_lint "First Principles.md"` 必然报多条。同上属档案性质。Verification 段已写明"FP 自身报告不修"
