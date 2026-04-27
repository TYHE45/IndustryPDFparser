# Context

2026042405plan 已整轮收口（3 commits：`00e8381 / f52b0b5 / c0e57d2`，已推送），plan-lint 工具 + `.gitattributes` EOL 工程化护栏落地。当前执行基线为 `6bfbd97`（`main...origin/main [ahead 3]`），这 3 个既有提交不属于 plan06，但最终 `git push origin main` 会一并推送。本轮第二回合 review 浮现 **6 条 plan05 落地后留尾**（已记入 FP §11 「2026042405plan」整轮收口条目）：

1. plan-lint vocab 与 source-of-truth 解耦（手维护 `KNOWN_DRIFT_MAP` 3 条，第一次新型 drift 仍漏检）
2. plan-lint 仅手动，未接 pre-commit/CI gate
3. fixture EOL 缺字节级测试守卫（`.gitattributes` 是 git 侧规则，无 test 时刻断言）
4. bonus test/commit 已成稳定 N+1 模式（连续 3 轮）
5. plan-lint vocab 方向不对称（只查英文/Chinglish→中文这一向）
6. plan 测试数估算偏差延续（plan05 写 +5 实测 +6）

**用户已选定方向 A**，本轮闭合 #1 / #3 / #4 三条工程化留尾：
- vocab 自动 seed（关闭"未卜先知"漏洞，但保留 honest design：纯英文 → 中文不可靠自动推断，仍走 `KNOWN_DRIFT_MAP`）
- byte-level EOL 测试守卫（与 `.gitattributes` 互为冗余防御）
- plan 模板 `# Budget` 段落升格 bonus/fixup slot 为预设字段（不再视作 risk）

**故意不在本轮做**：
- #2 pre-commit/CI gate — plan05 §2.1 风险段已论证"先用手动一段时间观察"，且应排在 vocab 自动化之后（vocab 不全的话门禁会挡合法 plan）
- #5 vocab 方向不对称 — 设计取舍而非缺陷
- #6 测试数估算偏差 — 与 #4 同源，#4 落地的"+1 bonus slot 模板字段"会消化它

3 个 commit 收口 + 显式预算 1 个 bonus slot（per #4 教训）。

**当前 working tree 状态（plan06 开工前）：**

```
 M src/reviewer.py          # 无关脏改动，保护并避开，不纳入 plan06 commit
 M web/schemas.py           # 无关脏改动，保护并避开，不纳入 plan06 commit
 M web/static/app.js        # 无关脏改动，保护并避开，不纳入 plan06 commit
 M web/static/style.css     # 无关脏改动，保护并避开，不纳入 plan06 commit
?? plan06.md                # 本轮计划档案，修到 lint clean 后并入 Stage 3 commit
```

FP 改动将在本轮 Stage 3 新增，并与 `tools/plan_template.md`、`plan06.md` 同 commit 落地。

---

# Budget（预算条目，plan 起草时即列出）

按 plan05 留尾 #4「bonus test/commit 已成稳定 N+1 模式（连续 3 轮）」教训，本轮显式预算：

- **`bonus_test_slot`**：用途预测 = 若 vocab 自动 seed 实现时发现 `_CHINGLISH_RE` 边界 case（如 `prompt签名` 无下划线 / `123_签名` 数字开头）需要新断言。**落地后必填**：实际用途或 "未触发，理由：..."
- **`fixup_commit_slot`**：用途预测 = 若 `src/pipeline.py` regex 提取在 CI 环境失败、需要追加 fallback 路径或调整 import sys.path 逻辑。**落地后必填**：实际用途或 "未触发，理由：..."

若两槽都未用上，commit 数为 3；若用上 1 个，为 4；都用上为 5。Verification 段最后一步要回填这两槽。

---

# Pre-flight checklist（ExitPlanMode 之前必跑）

```bash
python -m tools.plan_lint <plan_path>   # 退出码必须为 0
```

非 0 时回头修 plan 字段名再 lint 直到 clean。本 plan 自身已通过此检查（验证：本 plan 中提及 snapshot_version / prompt_签名 等历史名词仅在叙事段，不在反引号字段位 —— 实际写法为不带反引号的纯文本引用）。

---

# Plan

## 阶段 1：plan-lint vocab 自动 seed

**目标**：把 `tools/plan_lint.py` 的 `KNOWN_DRIFT_MAP` 从「孤立的手维护字典」升级为「自动 seed canonical 中文集合 + 手维护历史 drift 映射」双层结构。Chinglish ID 通过 canonical 集合自动匹配建议；纯英文 snake_case 仍走显式 map（设计取舍，非缺陷）。

### 1.1：重构 `tools/plan_lint.py` 顶部 vocab 加载

新增 `_load_canonical_vocab()` 函数：

```python
import sys
from functools import lru_cache

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PIPELINE_FILE = _REPO_ROOT / "src" / "pipeline.py"
_BASELINE_SNAPSHOT_FILE = _REPO_ROOT / "tests" / "support" / "baseline_snapshot.py"
# 提取 process_log 字典字面量中的中文 key（仅匹配以中文字符起头的 "..." key）
_PROCESS_LOG_KEY_RE = re.compile(r'"([\u4e00-\u9fff][^"]*)"\s*:')
_KEY_CONST_RE = re.compile(r'KEY_[A-Z_]+\s*=\s*"([\u4e00-\u9fff][^"]*)"')


@lru_cache(maxsize=1)
def _load_canonical_vocab() -> frozenset[str]:
    """Load canonical Chinese field vocabulary from two sources of truth.

    Source A: src.contracts KEY_* constants + tests/support/baseline_snapshot.py static KEY_* constants
    Source B: src/pipeline.py process_log dict literal Chinese keys (runtime contract)

    Falls back to a small hardcoded set if either source fails.
    """
    vocab: set[str] = set()

    # Source A: import src.contracts KEY_* constants and statically read KEY_SNAPSHOT_VERSION
    try:
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from src import contracts  # noqa: PLC0415
        for name in dir(contracts):
            if name.startswith("KEY_"):
                value = getattr(contracts, name)
                if isinstance(value, str) and any("一" <= c <= "鿿" for c in value):
                    vocab.add(value)
    except ImportError:
        pass

    try:
        text = _BASELINE_SNAPSHOT_FILE.read_text(encoding="utf-8")
        vocab.update(_KEY_CONST_RE.findall(text))
    except OSError:
        pass

    if not vocab:
        vocab.update({
            "问题清单", "问题ID", "级别", "内容", "扣分",
            "总分", "红线触发", "评审轮次",
            "提示词签名", "评审规则签名", "快照版本",
        })

    # Source B: regex extract from pipeline.py text (does not import — robust to import errors)
    try:
        text = _PIPELINE_FILE.read_text(encoding="utf-8")
        vocab.update(_PROCESS_LOG_KEY_RE.findall(text))
    except OSError:
        pass

    return frozenset(vocab)
```

设计要点：
- **`@lru_cache(maxsize=1)`** 让 vocab 只加载一次，多次调用 `lint_text()` 不重跑 IO/import
- **Source A 用 `src.contracts` 反射 + `baseline_snapshot.py` 静态读取**，避免 import `tests.support.baseline_snapshot` 间接执行 `src.reviewer.py`（当前该文件有无关脏改动，必须隔离）
- **Source B 用 regex 而非 AST** 鲁棒——只扫描 `process_log = { ... }` block；结构变了不会 crash，只是少 seed 几个；`_PROCESS_LOG_KEY_RE` 限定中文起头的 key，避开 `SECTION_COUNT` 这类常量符号 key
- **双层 fallback**：Source A 完全失败 → 硬编码当前 KEY_* 快照；Source B 失败 → 静默跳过（不阻塞 lint）
- **不引入新依赖**，仍只用 stdlib

### 1.2：在 `lint_text()` 添加 Chinglish 自动建议路径

修改 `lint_text()` 主循环，对 Chinglish ID 走新路径：

```python
# 提取 Chinglish 标识符的最长中文子串
_CHINESE_RUN_RE = re.compile(r"[一-鿿]+")


def _chinglish_canonical_match(ident: str, vocab: frozenset[str]) -> str | None:
    """For a Chinglish identifier, find a canonical token that ends with the same Chinese run."""
    runs = _CHINESE_RUN_RE.findall(ident)
    if not runs:
        return None
    longest = max(runs, key=len)
    # 后缀匹配：canonical 必须以这个中文 run 为后缀
    candidates = [v for v in vocab if v.endswith(longest)]
    if len(candidates) == 1:
        return candidates[0]
    # 多 candidate 时不主动建议（避免误导）；返回 None
    return None


# lint_text() 内部循环改为：
for ident_match in _BACKTICK_RE.finditer(line):
    ident = ident_match.group(1)
    # 先查显式 map（覆盖纯英文 + 历史已知 Chinglish）
    if ident in KNOWN_DRIFT_MAP:
        rule = "chinglish_with_chinese_counterpart" if _CHINGLISH_RE.match(ident) else "english_with_chinese_counterpart"
        issues.append(LintIssue(line=line_no, found=ident, suggestion=KNOWN_DRIFT_MAP[ident], rule=rule))
        continue
    # 再查 canonical vocab 自动匹配（仅 Chinglish）
    if _CHINGLISH_RE.match(ident):
        canonical = _chinglish_canonical_match(ident, _load_canonical_vocab())
        if canonical and canonical != ident:
            issues.append(LintIssue(
                line=line_no, found=ident, suggestion=canonical,
                rule="chinglish_via_canonical_vocab",
            ))
```

设计要点：
- **顺序：显式 map 优先，自动 vocab 兜底** —— 历史已知 drift 用稳定 map 路径，新型 drift 走 canonical 自动建议
- **后缀匹配（`endswith`）而非子串匹配** —— prompt_签名 找 `*签名` 命中 `提示词签名 / 评审规则签名`；后者多 candidate 时返回 `None` 避免误导。这是有意识的"宁可漏建议不可乱建议"
- **新规则名 `chinglish_via_canonical_vocab`** 明确表达 lint 报告来自自动通道而非手 map，便于 plan 作者排查

### 1.3：保留 `KNOWN_DRIFT_MAP` 不动

显式声明：纯英文 snake_case → 中文方向**不做自动 seed**。`input_file` / `output_dir` 等英文 token 在 codebase 里是合法 config attr 名，自动建议会大量误报。`KNOWN_DRIFT_MAP` 永远是 "已发生过的纯英文 drift" 的累积清单。

### 1.4：扩 `tests/test_plan_lint.py` 5 条新断言

```python
def test_canonical_vocab_includes_baseline_snapshot_keys(self) -> None:
    from tools.plan_lint import _load_canonical_vocab
    vocab = _load_canonical_vocab()
    self.assertIn("提示词签名", vocab)
    self.assertIn("评审规则签名", vocab)
    self.assertIn("快照版本", vocab)
    self.assertIn("问题清单", vocab)

def test_canonical_vocab_includes_pipeline_process_log_keys(self) -> None:
    from tools.plan_lint import _load_canonical_vocab
    vocab = _load_canonical_vocab()
    self.assertIn("输入文件", vocab)
    self.assertIn("输出目录", vocab)
    self.assertIn("迭代轮次", vocab)
    self.assertIn("文档类型", vocab)

def test_chinglish_known_drift_map_takes_precedence(self) -> None:
    # `prompt_签名` 在 KNOWN_DRIFT_MAP 里，显式 map 优先
    text = "新增 `prompt_签名` 字段。"
    issues = lint_text(text)
    self.assertEqual(len(issues), 1)
    self.assertEqual(issues[0].rule, "chinglish_with_chinese_counterpart")

def test_chinglish_unique_canonical_suffix_match_uses_auto_path(self) -> None:
    # `pipeline_输入文件` 不在 map 里，但 canonical 里只有一个 `输入文件`，应自动建议
    text = "新增 `pipeline_输入文件` 字段。"
    issues = lint_text(text)
    self.assertEqual(len(issues), 1)
    self.assertEqual(issues[0].suggestion, "输入文件")
    self.assertEqual(issues[0].rule, "chinglish_via_canonical_vocab")

def test_chinglish_with_no_canonical_match_falls_through(self) -> None:
    # `random_随机` 后缀 `随机` 不在 canonical 里 → 不报
    text = "示意性变量 `random_随机` 仅用于举例。"
    self.assertEqual(lint_text(text), [])
```

加上现有 6 条共 13 条；总测试数 46 → 53（+7）。其中 1 条来自 `bonus_test_slot`：自动 Chinglish 通道必须忽略带方括号/等号等标点的叙事表达式。

### 1.5：commit 1 — `feat(tools): plan-lint auto-seeds canonical vocab from KEY_* and process_log`

- 文件：`tools/plan_lint.py`（重构 + 新增 `_load_canonical_vocab` / `_chinglish_canonical_match`）+ `tests/test_plan_lint.py`（+5 断言）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 46 → 53 全通过 + 1 skipped 不变
- 预检：`python -m tools.plan_lint plan04.md` 退出码仍 1（历史 snapshot_version 仍能被 KNOWN_DRIFT_MAP 报出）
- 提交信息要点：双 source-of-truth（`src.contracts` + baseline_snapshot 静态 KEY_* + pipeline.py process_log regex）、honest design choice（纯英文不自动 seed）、新规则名 `chinglish_via_canonical_vocab` 起源、向后兼容（KNOWN_DRIFT_MAP 路径完整保留）

---

## 阶段 2：fixture EOL 字节级测试守卫

**目标**：与 `.gitattributes` + `newline="\n"` 互为冗余防御。即使未来 `.gitattributes` 被误删 / `core.autocrlf=true` / fixture 被某条新代码路径绕过 `serialize_snapshot` 直接写入，回归也会被字节级断言**主动**抓住，而不是沉默通过 `assertEqual`（后者走 universal newline 归一化）。

### 2.1：新建 `tests/test_fixture_eol.py`

```python
"""Byte-level EOL guard for baseline snapshot fixtures.

Redundant with .gitattributes + Path.write_text(newline="\\n") at IO layer;
catches regressions at test time even if those guards are bypassed.

Not gated by SLOW_TESTS — runs on every test invocation (~5ms total).
"""
from __future__ import annotations

import unittest
from pathlib import Path

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "baseline_snapshots"


class FixtureEolByteGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixtures = sorted(FIXTURES_ROOT.glob("*.json"))
        self.assertGreaterEqual(
            len(self.fixtures), 11,
            f"expected ≥ 11 baseline fixtures, found {len(self.fixtures)} in {FIXTURES_ROOT}",
        )

    def test_no_crlf_in_any_fixture(self) -> None:
        offenders = []
        for fixture in self.fixtures:
            raw = fixture.read_bytes()
            if b"\r\n" in raw:
                offenders.append(fixture.name)
        self.assertEqual(offenders, [], f"fixtures with CRLF: {offenders}")

    def test_each_fixture_starts_with_open_brace_and_lf(self) -> None:
        # serialize_snapshot uses indent=2 → starts with `{\n  "..."`
        offenders = []
        for fixture in self.fixtures:
            raw = fixture.read_bytes()
            if not raw.startswith(b"{\n"):
                offenders.append(f"{fixture.name}: head={raw[:8]!r}")
        self.assertEqual(offenders, [])

    def test_each_fixture_ends_with_close_brace_and_trailing_lf(self) -> None:
        # serialize_snapshot returns `... + "\n"` → ends with `}\n` exactly
        offenders = []
        for fixture in self.fixtures:
            raw = fixture.read_bytes()
            if not raw.endswith(b"}\n"):
                offenders.append(f"{fixture.name}: tail={raw[-8:]!r}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
```

设计要点：
- **`Path.read_bytes()`** 绕过 universal newline，是字节级断言的关键
- **3 条独立断言** 清晰诊断 CRLF / 头部 / 尾部 任意一类回归
- **`setUp` 数量守卫** 防"FIXTURES_ROOT 路径错了 → glob 空 → 三条断言全空集 vacuously pass"
- **不依赖 `SLOW_TESTS` 门控**：纯 IO 字节读取，11 文件 × 几 KB = ms 级，每跑全集都跑
- **不依赖 `serialize_snapshot` 模块**——纯黑盒断言文件字节，与 IO 写入实现完全解耦

### 2.2：commit 2 — `test(fixtures): add byte-level EOL guard for baseline snapshots`

- 文件：`tests/test_fixture_eol.py`（新建，约 50 行）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 52 → 55 全通过 + 2 skipped 不变
- 预检：手动制造 CRLF 验证守卫真在工作（实施时不入 commit，只本地验证后 git checkout 还原）
- 提交信息要点：与 `.gitattributes` 的关系（IO 侧 vs test 侧两层防御）、为什么不用 `read_text`（universal newline 归一化遮蔽 CRLF）、为什么不上 `SLOW_TESTS` 门控

---

## 阶段 3：plan 模板 + FP §11 收口

**目标**：把 plan04/05 的隐式骨架（Context / Plan / Critical Files / Verification / 风险）固化为静态 markdown 模板，新增 `# Budget` + `# Pre-flight checklist` 两段，明确"+1 bonus slot 是工作流预算字段而非风险"。同时关 plan05 留尾 #1/#3/#4 三条对应 P1 待办。

### 3.1：新建 `tools/plan_template.md`

完整骨架（约 80 行 markdown）：

- `# Context` — 历史背景占位
- `# Budget（预算条目，plan 起草时即列出）` — 新增。两槽：`bonus_test_slot` / `fixup_commit_slot`，用途预测 + 落地后必填
- `# Pre-flight checklist（ExitPlanMode 之前必跑）` — `python -m tools.plan_lint <plan_path>` 必须 0
- `# Plan` — 阶段 N / N.M 子任务 / N.X commit 标准格式
- `# Critical Files` — 表格
- `# Verification` — 阶段 N（commit N 前）+ 全部完成后 + 预算回填
- `# 风险与回滚点` — 风险条目

文件落点选 `tools/plan_template.md` 而非 `_tools/`（与 `tools/plan_lint.py` 共目录，入 git，方便其他作者引用）。**不**做 CLI scaffold——静态 markdown 强制 author 通读骨架的每段，scaffold 反而绕过这一目的。

### 3.2：FP §11 改动清单

A. 「下一阶段待办」段中 4 条新 P1 待办：

- `[ ] plan-lint vocab 自动化（与 source-of-truth 联动）` → `[x]`，追加落地段：`*落地（2026-04-27 / 2026042406plan）：* 已实现 _load_canonical_vocab 双 source（KEY_* 反射 + pipeline.py regex），新增 chinglish_via_canonical_vocab 自动通道；纯英文 → 中文方向仍走 KNOWN_DRIFT_MAP 不自动推断（设计取舍：避免 input_file/input_path 类合法平行命名误报）`
- `[ ] fixture EOL 字节级测试守卫` → `[x]`，追加落地段：`*落地：* tests/test_fixture_eol.py 三条字节级断言（无 CRLF / 头 b"{\n" / 尾 b"}\n"），不门控 SLOW_TESTS，每次全集都跑`
- `[ ] plan 模板把 "+1 bonus test/commit" 升格为预设字段` → `[x]`，追加落地段：`*落地：* tools/plan_template.md 静态骨架，新增 # Budget 段两槽（bonus_test_slot / fixup_commit_slot）+ # Pre-flight checklist；下轮起 plan 起草直接 copy 此模板，落地后 Verification 末段回填两槽实际用途`
- `[ ] plan-lint 工程化最后一公里：pre-commit / CI gate` 保持 `[ ]`，追加 *现状（2026-04-27）：* 段：`vocab 自动化已落地（plan06），自动门禁前置条件已具备；但留尾仍未做，理由是观察 vocab 自动通道在 plan06 后续 1–2 轮 plan 起草中的实战表现，再决定门禁阈值与是否上 .pre-commit-config.yaml`

B. 「近期落地」段在 2026042405plan 条目之后追加：

```
- [x] 2026042406plan：vocab 自动化 + EOL 字节级守卫 + plan 模板（3 commits：`<c1> / <c2> / <c3>`）
  - Stage 1 (`<c1>`)：`tools/plan_lint.py` 加 `_load_canonical_vocab()`（双 source：KEY_* 反射 + pipeline.py regex）+ Chinglish 后缀自动匹配通道（新规则 `chinglish_via_canonical_vocab`）；`KNOWN_DRIFT_MAP` 保留为纯英文 drift 路径（honest design：input_file/input_path 类合法平行命名不自动推断）；`tests/test_plan_lint.py` +5 断言
  - Stage 2 (`<c2>`)：`tests/test_fixture_eol.py` 字节级守卫（无 CRLF / `b"{\n"` 起头 / `b"}\n"` 收尾），与 `.gitattributes` IO 侧规则互为冗余防御；不门控 SLOW_TESTS
  - Stage 3（本 commit）：FP §11 三条 P1 待办改 `[x]`，新建 `tools/plan_template.md` 静态骨架（# Budget / # Pre-flight checklist 两段为新增固化）；plan-lint pre-commit hook 待办留 `[ ]` 但更新现状：vocab 前置条件已就位，留观察 1–2 轮再上
  - **本轮预算条目落地结果**：`bonus_test_slot` = [回填]；`fixup_commit_slot` = [回填]
```

C. 顶部「最近整理」行更新为 `2026-04-27（plan06 收口）`

### 3.3：commit 3 — `docs(fp): close 2026042406 vocab+EOL+template plan and add plan template scaffold`

- 文件：`First Principles.md`（A + B + C）+ `tools/plan_template.md`（新建）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 仍 55/55 + 2 skipped
- 预检：`python -m tools.plan_lint "First Principles.md"` 退出码报告 → 历史档案性，FP 自身仍含历史叙事 drift 引用，不修
- 预检：`python -m tools.plan_lint tools/plan_template.md` 退出码 0（模板里反引号字段都是占位符 `xxx`，无 drift）
- 提交信息要点：plan_template 静态骨架而非 CLI scaffold 的设计取舍、Budget 段对 plan04–05 三轮 N+1 模式的工程化回应、pre-commit hook 留待为何未本轮做

---

## 最终：推送与收口

- `git log origin/main..HEAD --oneline` 应为 3 条（commit 1–3，若 bonus/fixup slot 触发则 4–5 条）
- `git push origin main`
- 本地 `git status --short` 干净
- FP §11 「Budget 回填」是本轮独有的新一步——把 bonus/fixup slot 实际用途写回 plan06 整轮收口条目

---

# Critical Files

| 路径 | 本轮作用 |
|------|---------|
| `tools/plan_lint.py` | 阶段 1：重构 + 新增 `_load_canonical_vocab` / `_chinglish_canonical_match` / `_PROCESS_LOG_KEY_RE` |
| `tests/test_plan_lint.py` | 阶段 1：+5 断言（vocab 双 source 各一 / Chinglish 自动匹配命中 / 多 candidate 不建议 / 未匹配不报） |
| `tests/test_fixture_eol.py` | 阶段 2：新建。3 条字节级断言（CRLF / 头 / 尾） |
| `tools/plan_template.md` | 阶段 3：新建。Context / Budget / Pre-flight / Plan / Critical Files / Verification / 风险与回滚点 七段骨架 |
| `First Principles.md` | 阶段 3：§11 三条 P1 改 `[x]` + 一条更新现状 + 「近期落地」追加 2026042406 条目 + 顶部「最近整理」日期 |
| `tests/support/baseline_snapshot.py` | 阶段 1 **只读**。其 `KEY_*` 常量是 Source A canonical vocab 的反射目标 |
| `src/pipeline.py` | 阶段 1 **只读**。230-260 行 `process_log` 字典字面量是 Source B regex 提取目标 |
| `tests/fixtures/baseline_snapshots/*.json` | 阶段 2 **只读**。11 份 LF JSON 是字节级守卫对象 |
| `.gitattributes` | 阶段 2 **只读**。IO 侧规则参考；与本轮 test 侧守卫互补 |

---

# Verification

**阶段 1（commit 1 前）：**
- `python -c "from tools.plan_lint import _load_canonical_vocab; v = _load_canonical_vocab(); print(len(v), '提示词签名' in v, '输入文件' in v)"` 应输出形如 `20 True True`（数量按当前 contracts KEY_* + baseline snapshot local KEY_* + process_log 求和）
- `python -m tools.plan_lint plan04.md` 仍能报出 snapshot_version drift（KNOWN_DRIFT_MAP 路径未坏）
- `python -m tools.plan_lint plan05.md` 仍报历史 snapshot_version / prompt_签名 / reviewer_签名（同上）
- 手测：构造一行 pipeline_输入文件 反引号字段的 markdown 文件，lint 应报出 `chinglish_via_canonical_vocab` 规则
- `python -m unittest discover -s tests -p "test_*.py"` 46 → 53 全通过 + 1 skipped

**阶段 2（commit 2 前）：**
- `python -m unittest tests.test_fixture_eol -v` 三条断言全 ok
- 不在 tracked fixture 上手动制造 CRLF；以新增字节级断言 + 当前 fixture bytes 为验收
- `python -m unittest discover -s tests -p "test_*.py"` 53 → 56 全通过 + 1 skipped

**阶段 3（commit 3 前）：**
- `tools/plan_template.md` 自身用 `python -m tools.plan_lint tools/plan_template.md` 退出码 0
- `git log 6bfbd97..HEAD --oneline` 应为 3（或 +bonus/fixup）条
- FP §11 三条 `[ ] → [x]` 内容核对：每条 *落地* 段引用具体 commit hash 与文件路径
- `python -m unittest discover -s tests -p "test_*.py"` 仍 56/56 + 1 skipped

**全部完成后：**
- `git push origin main` 成功
- `git status --short -- tools/plan_lint.py tests/test_plan_lint.py tests/test_fixture_eol.py tools/plan_template.md "First Principles.md" plan06.md` 干净；全局 status 允许仍显示开工前已存在的 4 个无关脏文件
- **预算条目回填**：在 FP §11 2026042406plan 条目末尾把 `bonus_test_slot` / `fixup_commit_slot` 的占位符替换为实际用途或"未触发，理由：..."。这一步是 plan06 引入的工作流字段，落实 "+1 bonus slot 升格预设字段" 设计

---

# 风险与回滚点

- **vocab 自动建议误报**：`_chinglish_canonical_match` 用后缀匹配 + 多 candidate 不建议策略，已在设计层最小化误报；但若未来 `process_log` 引入很短的中文 key（如 `日志` / `状态`），会与许多 Chinglish ID 后缀相撞 → 多 candidate 路径返回 None 兜底；真正风险落地时观察新加 P1 待办"vocab 后缀冲突修剪规则"
- **`src/pipeline.py` regex 提取在 dict 结构变化时失效**：`_PROCESS_LOG_KEY_RE` 仅匹配 `"中文起头": ` 模式；如果未来 `process_log` 改为分散在多个函数内拼接 / 用 `**kwargs` 展开，提取会少 seed → 不 crash 但 vocab 不全 → fallback 路径退化为只有 KEY_* 反射。可接受；FP §11 加观察项即可
- **`@lru_cache` 缓存导致 vocab 在测试间共享**：`_load_canonical_vocab` 全局缓存意味着任何"修改 baseline_snapshot.py 后再跑 lint"在同一进程内仍是旧 vocab。`unittest` 每次启动新进程不受影响；但若引入 `pytest --forked` 或长期 daemon 化才会暴露。本轮不设计 invalidation；若未来真需要，加 `_load_canonical_vocab.cache_clear()` 一行即可
- **plan_template.md 落地后无强制使用机制**：本轮不接 pre-commit hook（plan05 留尾 #2 仍 `[ ]`），下轮 plan06+ 起草若 author 跳过模板直接写 plan，没有自动报警。这是 plan-lint 工程化最后一公里的延续，与 vocab 自动化分两轮做的取舍一致——避免本轮 scope 过大
- **+1 bonus slot 元 irony 风险**：plan06 自身可能触发 1 个 bonus_test_slot（如 vocab 后缀冲突边界 case 需要新断言）。这正是 Budget 段设计的初衷——预算字段已就位，触发后填回即可，不再视作"plan 失败"
- **vocab fallback hardcoded 集合可能与 KEY_* 漂移**：1.1 设计的硬 fallback 11 个 token 是当下快照；若未来 baseline_snapshot.py 增改 KEY_*，硬 fallback 会过时。Risk 较小（fallback 只在 import 失败时触发），但写入 commit message 提醒"hardcoded fallback 是当前 KEY_* 的快照，KEY_* 变更应同步更新"
- **历史档案 lint 报告**：plan04.md / plan05.md / FP 中叙事性保留的 snapshot_version / prompt_签名 / reviewer_签名 在新 lint 下仍会报（KNOWN_DRIFT_MAP 路径），符合 plan05 §3.2 「历史档案 lint 报告不要求倒修」边界；plan06 也不修改这些历史文档
