# Context

2026042403plan 已整轮收口（4 commits：`812fbeb / 4a77106 / 5366eca / 84a3397`），包括 B.3 闭合、OCR 白盒 3 条边界断言、`提示词签名 / 评审规则签名` 接入 `process_log.json`。核对时发现两条留尾：

1. **Plan 1.2 的 12 行样例 snapshot 表因 slow baseline 被 ops fragility（429 + OCR 长尾）打断未补齐**
2. **`tests/test_sample_score_baseline.py:15-58` 的 12 份样例期望值全是硬编码 4 标量**，真值产物 `review.json` 不入 git：异地无法复算、FAIL 时无法定位到"是哪条 issue 动了"、只能靠 ±3 数字容差粗筛

用户与 Claude 来回讨论后已明确本轮 plan 的**操作性定义**（写进 plan 作为验收标准）：

> 引入"**可诊断、低噪音、低维护面**"的结构层 baseline snapshot，而不是完整输出产物入库。
>
> - **可诊断**：CI FAIL 时能单凭 `git diff` 定位到"哪条 issue 被加/被删/哪个签名变了"，不用重跑 pipeline
> - **低噪音**：合理的产品演进（LLM 输出顺序变、issue 描述/修复建议文本微调、换行符差异）不触发 FAIL；触发 FAIL 的只有"issue 集合变动 + 签名变动 + 数字跳出 ±3"三类真信号
> - **低维护面**：每份 fixture 字段数极简（顶层 6 键，每条 issue 3 键），总体积 ≤ 30 KB；reviewer 改一条 issue 内部描述不应导致 12 份全红

**本次规划目的：** 用 3 个独立 commit 把结构层 snapshot 落地、生成 12 份 fixture 并入 git、在 FP 固化 2026042403 的 1.2 留尾表格。每个 commit 作用域可控、可单独回滚。

**当前 working tree 状态：**

```
 M First Principles.md   # 2026042403 整轮收口 + 3 条结构层教训已追加，未提交
```

FP 追加内容与本轮 Stage 3 的"FP 入表"天然同 commit。

---

# Plan

## 阶段 1：snapshot 数据契约与测试基础设施

**目标**：新建 `tests/support/baseline_snapshot.py` 定义 snapshot 字段契约 + 规范化写入；扩展 `tests/test_sample_score_baseline.py` 增加 fixture 比对层，支持 `UPDATE_BASELINE_SNAPSHOTS=1` 模式生成/刷新 fixture。**本阶段不产出 fixture 文件**，只铺基建。

### 1.1：新建 `tests/support/baseline_snapshot.py`

依赖 Explore agent 已确认的契约：
- `review["问题清单"]` 每项 12 键中，保留 stable 子集，过滤 noisy
- `process_log["提示词签名"]` / `process_log["评审规则签名"]` 已在 `5366eca / 84a3397` 落地

模块结构：

```python
# tests/support/baseline_snapshot.py
from __future__ import annotations
import json
import re
from pathlib import Path
from src.reviewer import ISSUE_DEDUCTIONS

SNAPSHOT_VERSION = 1  # 未来字段契约升级时递增，fixture 读不到该版本时报错而非误比
FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures" / "baseline_snapshots"

def build_snapshot(review: dict, process_log: dict) -> dict:
    """把 pipeline 产出压成可诊断的最小快照。顶层 6 键 + 每条 issue 3 键。"""
    issues_raw = review.get("问题清单", []) or []
    issues = [
        {
            "问题ID": str(it.get("问题ID", "")),
            "级别": str(it.get("级别", "")),
            "扣分": float(ISSUE_DEDUCTIONS.get(str(it.get("问题ID", "")), ("", 0.0))[1]),
        }
        for it in issues_raw
    ]
    issues.sort(key=lambda x: (x["问题ID"], x["级别"]))  # 规范化顺序，避免 LLM 次序抖动触 FAIL
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "总分": float(review.get("总分", 0.0) or 0.0),
        "红线触发": bool(review.get("红线触发", False)),
        "评审轮次": int(process_log.get("评审轮次", 0) or 0),  # 或从 review_rounds 推断
        "提示词签名": str(process_log.get("提示词签名", "")),
        "评审规则签名": str(process_log.get("评审规则签名", "")),
        "问题清单": issues,
    }

def serialize_snapshot(snapshot: dict) -> str:
    """项目约定：sort_keys + ensure_ascii=False + indent=2，跨平台确定性。"""
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n"

_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")

def fixture_filename_for(sample_path: str) -> str:
    """把样例路径映射到 ASCII-only 稳定 fixture 文件名，避免中文文件名跨平台坑。"""
    stem = Path(sample_path).stem
    ascii_part = _SANITIZE_RE.sub("_", stem).strip("_") or "sample"
    return f"{ascii_part}.json"
```

**关键设计点**：
- 顶层 6 键恰好对应操作性定义（总分 / 红线 / 轮次 / 两个签名 / 问题清单），不多不少
- 每条 issue 仅 `问题ID / 级别 / 扣分`，去掉 noisy 的 `原因 / 修复建议`，以及 stable 但可由 `问题ID` 推导的 `问题类型 / 位置 / 内容 / 根因模块 / 修正动作 / 是否阻断 / 影响输出`（这些若全部入 snapshot，reviewer 改一处映射表就触 12 份全红）
- `sort` 问题清单规范化顺序；`snapshot_version` 为未来字段契约升级留版本门
- 文件名仅 ASCII，避开中文 PDF 文件名的 git cross-platform 问题（用户之前指出的风险）

**需要小检查**：扣分映射 `ISSUE_DEDUCTIONS.get(...)` 若遇未注册 `问题ID` 会落到默认 `("", 0.0)`；Stage 1 时实测全部 12 份样例的 issue IDs 若发现有 `ISSUE_DEDUCTIONS` 缺口，按本阶段 scope drift 弹性条款在同 commit 补 `ISSUE_DEDUCTIONS` 映射（参考 2026042402 `Commit 4` 先例）。

### 1.2：扩展 `tests/test_sample_score_baseline.py`

在现有 `test_sample_score_baselines_stay_within_expected_window` 同类内新增 `test_sample_score_baseline_snapshots_match_fixtures`：

```python
_UPDATE_SNAPSHOTS = os.getenv("UPDATE_BASELINE_SNAPSHOTS") == "1"

def test_sample_score_baseline_snapshots_match_fixtures(self) -> None:
    for baseline in _BASELINES:
        sample_path = Path(str(baseline["sample_path"]))
        input_path = _INPUT_ROOT / sample_path
        fixture_path = FIXTURES_ROOT / fixture_filename_for(str(sample_path))
        with self.subTest(sample=str(sample_path)), tempfile.TemporaryDirectory(...) as tempdir:
            result = run_iterative_pipeline(...)
            actual = build_snapshot(result["review"] or {}, result["process_log"] or {})
            serialized = serialize_snapshot(actual)
            if _UPDATE_SNAPSHOTS:
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_text(serialized, encoding="utf-8")
                continue
            self.assertTrue(fixture_path.exists(),
                            msg=f"{fixture_path.name} 缺失；先用 UPDATE_BASELINE_SNAPSHOTS=1 生成")
            expected = fixture_path.read_text(encoding="utf-8")
            self.assertEqual(serialized, expected, msg=f"{sample_path.name} 结构快照发生变化，看 git diff 定位哪条 issue 动了")
```

- **`UPDATE_BASELINE_SNAPSHOTS=1`** 仿 Jest `--updateSnapshot`，是未来刷 fixture 的标准入口
- 比对时直接 string-level `assertEqual`，而非结构对比：因为 `serialize_snapshot` 是规范化的，字符串差异即为诊断点；diff 工具天然好看
- fixture 缺失（首次）时 **FAIL with clear hint** 而非静默 skip，避免"CI 绿 = fixture 存在且对齐"这层契约被侵蚀

### 1.3：commit 1 — "test(baseline): add structural snapshot layer with UPDATE_BASELINE_SNAPSHOTS mode"

- 文件：`tests/support/__init__.py`（新建，空）+ `tests/support/baseline_snapshot.py`（新建） + `tests/test_sample_score_baseline.py`（扩展）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 仍 40/40 + 1 skipped（新测试与旧一样挂在 `SLOW_TESTS=1` 下，不加测试计数）
- 提交信息要点：新建 snapshot 基础设施；不入 fixture（留 Stage 2）；说明 `UPDATE_BASELINE_SNAPSHOTS=1` 使用方式
- **scope drift 预警**：若 Stage 1 自测时发现 `ISSUE_DEDUCTIONS` 未覆盖某 issue ID，允许同 commit 补映射（commit message 写明 drift 原因）

---

## 阶段 2：生成并入库 12 份 fixture

**目标**：跑一次 `UPDATE_BASELINE_SNAPSHOTS=1 SLOW_TESTS=1 python -m unittest tests.test_sample_score_baseline` 生成 12 份 fixture，commit 入 git，作为首次基线真值。

### 2.1：生成 fixture（带降级预案）

命令：
```
UPDATE_BASELINE_SNAPSHOTS=1 SLOW_TESTS=1 python -m unittest tests.test_sample_score_baseline.SampleScoreBaselineTests.test_sample_score_baseline_snapshots_match_fixtures 2>&1 | tee _tmp_snapshot_gen.log
```

**基于 2026042403 ops fragility 教训的前置降级预案**：
- **触发条件**：任一样例耗时 > 15 分钟，或 OpenAI 429 累计 > 3 次
- **降级目标**：优先生成 5 份代表类型样例的 fixture（扫描 `GB 39038-2020`、表格型 `CB_T 4196-2011`、产品目录 `Dixon.2017`、中文标准 `SN200_2007-02_中文`、英文标准 `SN775_2009-07_e`），剩余 7 份入 `known_missing` 清单挂到 Stage 3 FP 注记
- **降级标识**：commit message 必须写明"本 commit 覆盖 N/12 份 fixture，其余 Y 份因 ops fragility 降级，下轮 slow baseline 完整跑通时补齐"
- **不降级目标**：若全量 12 份在 60 分钟内能完成，一次性生成

### 2.2：手工抽检 3 份 fixture

挑 `SN544-1.pdf`（最简单）、`GB 39038-2020 ...pdf`（最复杂，扫描件）、`CB_T 4196-2011 ...pdf`（红线触发）三份生成的 JSON：
- 顶层 6 键齐全，`提示词签名=d65021f1`、`评审规则签名=21729d3a`（与 FP §11 记录的首次基线一致，否则说明签名漂移，先排查）
- `问题清单` 项数与 `_BASELINES` 里 `issues` 字段一致（±0），每项仅 3 键
- JSON 格式：`indent=2`、末尾 `\n`、`sort_keys=True`、`ensure_ascii=False`（中文直出，不 escape）
- 总分 ≤ 与 `_BASELINES` 里 `expected_score` 差 ±3

### 2.3：commit 2 — "test(baseline): commit first-round baseline snapshots under tests/fixtures/baseline_snapshots/"

- 文件：`tests/fixtures/baseline_snapshots/*.json`（N 份新文件，N ∈ {5, 12}，视降级情况）
- 预检：**关掉 `UPDATE_BASELINE_SNAPSHOTS=1`** 重跑 `SLOW_TESTS=1 python -m unittest ...` 验证 fixture 比对层对生成出来的 fixture 全通过（自 self-check）
- 预检：`python -m unittest discover -s tests -p "test_*.py"`（不带 SLOW_TESTS）仍 40/40 + 1 skipped
- 提交信息要点：列出覆盖的样例名、签名值 `提示词签名=d65021f1 / 评审规则签名=21729d3a`、是否降级及原因
- `_tmp_snapshot_gen.log` 受 `.gitignore` 过滤不入库（核对 `.gitignore` 现有规则覆盖即可）

---

## 阶段 3：FP 收口 + Plan 1.2 留尾补齐

**目标**：
1. 用新 fixture 的实测数据补齐 2026042403plan 1.2 的 12 行样例 snapshot 表（已在 FP §11 挂在留尾位置，补齐后撤掉"留尾"标识）
2. 把 §11「下一阶段待办」里的 `baseline 真值产物入 git` 从 `[ ]` 改 `[x]`
3. 在 §11「近期落地」追加 2026042404plan 整轮收口条目

### 3.1：FP §11 追加"2026042404plan 整轮收口"条目

在现有 "2026042403plan 阶段 1/2/3 + bonus fixup" 条目之后，追加：

```
- [x] 2026042404plan：结构层 baseline snapshot 入 git（3 commits：`<c1> / <c2> / <c3>`）
  - 阶段 1：新建 `tests/support/baseline_snapshot.py` + `UPDATE_BASELINE_SNAPSHOTS=1` 模式
  - 阶段 2：生成并入库 N/12 份 fixture 至 `tests/fixtures/baseline_snapshots/`
  - 阶段 3：FP §11 补齐 1.2 snapshot 表 + 标 "baseline 真值入 git" [x]
  - snapshot 契约：顶层 6 键（总分 / 红线触发 / 评审轮次 / 提示词签名 / 评审规则签名 / 问题清单）+ 每条 issue 3 键（问题ID / 级别 / 扣分），规范化 JSON（sort_keys + ensure_ascii=False + indent=2）
  - **验证侧重点：** 本 fixture 是"诊断加速器"而非"新契约"——CI FAIL 时先看 fixture diff 定位 issue，然后决定是修代码还是 UPDATE_BASELINE_SNAPSHOTS=1 重刷；刷 fixture 本身不算回归
  - 12 行 snapshot 表（或降级覆盖的 N 行）：见下方
  - [snapshot 表格]
```

### 3.2：FP §11「下一阶段待办」更新

- `baseline 真值产物入 git` 条目：`[ ]` → `[x]`，追加 "本轮用结构层 snapshot 而非完整产物入库的理由"（链接本 plan Context 段的操作性定义）
- 若 Stage 2 降级（覆盖 < 12 份），本条保持 `[x]` 但追加 known_missing 清单和"下轮完整 slow baseline 时补齐"待办

### 3.3：commit 3 — "docs(fp): close 2026042404 baseline-snapshot plan + fill 2026042403 plan 1.2 snapshot table"

- 文件：`First Principles.md`（必改）
- 预检：`python -m unittest discover -s tests -p "test_*.py"` 40/40 + 1 skipped（不加不减，docs-only）
- 提交信息要点：FP 三处改动（新条目 + 1.2 表补齐 + 下一阶段待办标勾）

---

## 最终：推送与收口

- `git log origin/main..HEAD --oneline` 应为 3 条（commit 1–3）
- `git push origin main`
- 本地 `git status --short` 干净
- 至此 2026042403 留尾完全闭合，slow baseline 从"4 标量断言"升级为"4 标量断言 + 结构快照断言"双层

---

# Critical Files

| 路径 | 本轮作用 |
|------|---------|
| `tests/support/baseline_snapshot.py` | 阶段 1：新建。`build_snapshot` / `serialize_snapshot` / `fixture_filename_for` 三函数 + `SNAPSHOT_VERSION` 常量 |
| `tests/support/__init__.py` | 阶段 1：新建空文件，让 `tests.support` 可导入 |
| `tests/test_sample_score_baseline.py` | 阶段 1：增 `test_sample_score_baseline_snapshots_match_fixtures` 方法 + `_UPDATE_SNAPSHOTS` 开关；现有 `test_sample_score_baselines_stay_within_expected_window` 不改 |
| `tests/fixtures/baseline_snapshots/*.json` | 阶段 2：新建 N ∈ {5, 12} 份 fixture，规范化 JSON 格式 |
| `First Principles.md` | 阶段 3：§11 追加 2026042404 收口条目 + 补 2026042403 plan 1.2 的 12 行表 + 标 "baseline 真值入 git" [x] |
| `src/reviewer.py` | 阶段 1 **只读**（可能 scope drift：补 `ISSUE_DEDUCTIONS` 缺项时写）。签名依赖 `ISSUE_DEDUCTIONS` 稳定接口 |
| `src/pipeline.py` | 阶段 1 **只读**。snapshot 依赖 `result["review"]` / `result["process_log"]` 稳定返回契约（src/pipeline.py:246-270） |
| `src/config_signatures.py` | 阶段 2 **只读**。首次基线签名 `d65021f1 / 21729d3a` 是 fixture 内容对照的锚点 |

---

# Verification

**阶段 1（commit 1 前）：**
- 不带 `SLOW_TESTS=1` 跑 `python -m unittest discover -s tests -p "test_*.py"`：40/40 + 1 skipped，新方法挂在 skipped 里
- 手工在 Python REPL 里 `from tests.support.baseline_snapshot import build_snapshot, serialize_snapshot, fixture_filename_for` 全部可导入
- `fixture_filename_for("industry_standard/SN544-1.pdf")` → `"SN544-1.json"`；`fixture_filename_for("scanned_version/GB 39038-2020 船舶与海上技术 ...pdf")` → `"GB_39038-2020_船舶..."` 退化后为纯 ASCII（中文被过滤，验证跨平台安全）

**阶段 2（commit 2 前）：**
- `UPDATE_BASELINE_SNAPSHOTS=1 SLOW_TESTS=1 python -m unittest ...` 产出 N ∈ {5, 12} 份 JSON，无异常
- 关掉 `UPDATE_BASELINE_SNAPSHOTS` 重跑：`SLOW_TESTS=1 python -m unittest tests.test_sample_score_baseline` 全部 PASS，证明 fixture 自洽
- 抽检 3 份 JSON：`提示词签名=d65021f1`、`评审规则签名=21729d3a`、顶层 6 键齐、每条 issue 3 键、JSON 格式规范
- 若降级到 5 份：commit message 明确列 known_missing 7 份

**阶段 3（commit 3 前）：**
- `git log origin/main..HEAD --oneline` = 3 条
- FP §11 三处改动齐：新条目、1.2 表补齐（12 行或 N 行+known_missing 注记）、`[baseline 真值产物入 git]` 从 `[ ]` 改 `[x]`
- `python -m unittest discover -s tests -p "test_*.py"` 40/40 + 1 skipped 无变化

**全部完成后：**
- `git push origin main` 成功
- `git status --short` 干净
- 下次 slow baseline FAIL 时，第一步操作从"手跑一轮看 review.json"变为"看 fixture diff"

---

# 风险与回滚点

- **阶段 1 scope drift**：若 `ISSUE_DEDUCTIONS` 未覆盖某 issue ID 导致 snapshot 扣分字段全 0.0，按 2026042402 `Commit 4` 先例在同 commit 补 `src/reviewer.py:151-179` 映射；commit message 写明 drift 原因
- **阶段 2 ops fragility 复发**：已有明确降级预案（5 份核心样例 + known_missing 清单），不重蹈 2026042403 只跑 1 份的覆辙
- **阶段 2 Windows/Linux JSON 字节差异**：`serialize_snapshot` 显式 `indent=2 + sort_keys + ensure_ascii=False` + 尾部 `\n`，但跨平台换行符风险需要实际在两端验证一次（本项目默认在 Windows 开发 + 单端提交，短期内非阻塞）；若未来接入 CI-Linux 出现换行符 diff，再加 `.gitattributes` 强制 LF
- **签名漂移风险**：若 Stage 2 生成的 fixture 里 `提示词签名 / 评审规则签名` 不是 `d65021f1 / 21729d3a`，说明 `src/summarizer.py` / `src/tagger.py` / `ISSUE_DEDUCTIONS` 在 2026042403 之后被动过——这是比 fixture 本身更严重的信号，需要立即停下查原因，不能直接入库新签名值
- **fixture 与 `_BASELINES` 列表协议漂移**：若未来添加新样例但忘记 `UPDATE_BASELINE_SNAPSHOTS=1` 生成 fixture，Stage 1 的 `assertTrue(fixture_path.exists())` 会明确 FAIL with 清晰 hint；这是设计上的护栏，不是缺陷
- **snapshot 字段契约未来演进**：`SNAPSHOT_VERSION = 1` 为未来加字段留版本门；下次字段扩展时先升版本常量 → 老 fixture 读到不匹配 `snapshot_version` 时 FAIL with 明确重生成提示，避免静默半新半旧比对
