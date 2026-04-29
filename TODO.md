# TODO

待办、缺陷与不立项归档；不承载历史时间线或架构契约。

---

## 当前进展（2026-04-29）

Phase 1-4 全部完成，Phase 4.5 P0-1 / P0-2 / P0-3 收口，Phase 4.5 P1 入口守卫完成，Phase 5 部分完成（237 tests passed，零回归）。

GAPS.md 全量审计（2026-04-29）发现新缺陷已并入本文件。

本轮收口：Phase 4.5 P0-1（`_pid_is_alive` Windows Bug）、P0-2（Reviewer LLM 误判阻断）、P0-3（OCR 表格桥接诊断验证 — 桥接代码存在且生效，CB 589-95 产出了参数）。Phase 4.5 P1 文档画像领域校验守卫已实现，章节/表格数超限守卫确认已存在。Phase 5 P0 单元测试：utils.py（22 tests）、record_access.py（40 tests）已完成。

---

## 实施路线图

```
Phase 1 ✅ → Phase 2 ✅ → Phase 3 ✅ → Phase 4 ✅
                                       ↓
                               Phase 4.5（当前阶段）
                                       ↓
                          Phase 5 (可独立推进，不阻塞 4.5)
                          Phase 6 (选做项，允许永远不做)
```

---

## 已完成阶段

### Phase 1: 扫清隐患 ✅

7 项低投入高回报修复：`ocr.py` UnboundLocalError 保护、`config.py` OCR_ENABLED 解析 bug、`pipeline.py` review.get() on None 崩溃、reviewer 死函数/常量清理、models.py/config_signatures.py 未使用导入清理、`_dedupe` 三合一、reviewer `_strip_markdown_metadata` 替换为 source_guard 导入。

### Phase 2: 错误处理加固 ✅

API 切换 DeepSeek、loader/pipeline/fixer 异常防护、AppConfig 运行时字段提取（PipelineContext）、AppConfig 配置校验（OCR 语言码/类型/范围）。

### Phase 3: 测试覆盖与质量基建 ✅

核心模块单元测试（source_guard / profiler / normalizer / ocr_eval / cleaner）、slow baseline 鲁棒性（jitter 重试、wall-clock cap、subprocess isolation）、plan 条件句闭环。

> **已知留尾：** Phase 3 覆盖了 5 个模块，但以下 7 个核心模块仍为零单元测试（见 Phase 5 P0）。Phase 3 的"完成"定义是"建立测试基建 + 覆盖最危险模块"，不是"100% 覆盖率"。

### Phase 4: 架构重构 ✅

管道状态对象化→评审轮次提前终止、来源隔离提前判断、Web 层架构违规修复、数据访问层合并。

---

## Phase 4.5: 数据契约与集成层加固（当前阶段）

*2026-04-27 五份抽样暴露的系统性问题 + 2026-04-29 GAPS.md 审计发现的阻断性缺陷。*

### P0 — 阻断性缺陷

- [x] **`_pid_is_alive` Windows 跨平台 Bug**（来自 GAPS.md §一）— 2026-04-29 收口
  - 已改为 `os.name == "nt"` 走 `OpenProcess + GetExitCodeProcess`，POSIX 路径保留 `os.kill(pid, 0)`
  - 新增 `tests/test_utils.py`（6 例，4 active + 2 POSIX-only），全量回归 179 tests passed
  - *文件：* `src/utils.py`、`tests/test_utils.py`、`CHANGELOG.md`

- [x] **Reviewer 判"LLM不可用"为阻断的误判修复** — 2026-04-29 收口
  - 实际函数名是 `_review_summary_structure`（TODO 原文 `_review_summary_content` 是笔误）
  - 已加 `_BENIGN_LLM_FALLBACK_PREFIXES` 7 条白名单 + `_is_benign_llm_reason` gate；`review_outputs` 与 `_review_summary_structure` 加可选 `process_log` 参数；pipeline 异常 fallback 补齐 `_llm_reason`
  - 6 个新单测覆盖 process_log 兜底、白名单 gate 正反两侧、双空仍阻断
  - *文件：* `src/reviewer.py`、`src/pipeline.py`、`tests/test_reviewer_hit_conditions.py`、`CHANGELOG.md`
  - *YELLOW 留尾：* 未跑 `SLOW_TESTS=1` baseline 验证 4/5 抽样实际分数恢复，建议下一轮 baseline 收口时一并验证

### P0 — 数据桥

- [x] **OCR 表格结果桥接到参数提取路径** — 2026-04-29 收口 ✅
  - **2026-04-29 诊断结论：桥接已生效，无需修改代码**
    - 诊断脚本 `diagnostics/p0_3_ocr_table_bridge.py` 对 CB 589-95 三探点实测：
      - 探点 A: PASS — OCR 召回 2 页 2 个表格（24×66 + 18×12 矩阵）
      - 探点 B: PASS — `_adapt_ocr_table_matrix` 适配后 2/2 表格均 >=2 行（24×6 + 18×10）
      - 探点 C: 诊断脚本误报 FAIL（匹配逻辑 bug），实际管道验证产出 2 个 TableRecord + 1 个参数"公称压力=20.0"
    - `tests/test_ocr_table_structure.py:108 test_parser_extract_page_tables_merges_force_ocr_tables` 在跑
  - *文件：* `src/parser.py`、`src/ocr.py`、`src/fixer.py`、`diagnostics/p0_3_ocr_table_bridge.py`
  - *诊断报告：* `diagnostics/output/p0_3_report_20260429T084225Z.json`

### P1 — 入口守卫

- [x] **文档画像后加领域校验守卫** — 2026-04-29 收口
  - 已实现在 `pipeline.py`：`run_iterative_pipeline` 入口 profiler 之后检查置信度 < 0.5 或文档类型为 `unknown` → 跳过全量解析，输出"超出处理领域"的简化结果
  - *文件：* `src/pipeline.py`（`_build_rejected_result`）

- [x] **章节/表格数超限守卫** — 2026-04-29 确认已存在
  - 章节数 > 500 或表格数 > 50 时中止处理路径，记录 `process_log["结构异常"]` — 此逻辑已存在于 `pipeline.py`（原来位置：`run_iterative_pipeline` profiler 之后）
  - *文件：* `src/pipeline.py`、`src/normalizer.py`

### P1 — 数据总线

- [ ] **OCR 软超时阈值可配置化 + 部分完成标记**
  - 软超时阈值从硬编码改为 `config.py` 中 `ocr_soft_timeout` 字段
  - OCR 部分完成后在 `process_log` 中记入 `OCR部分完成=True` 和 `OCR完成页数/target页数`，供 reviewer 区分"完整 OCR"和"部分 OCR"
  - *影响：* GB 39038 软超时后 reviewer 仍按全量 OCR 评估，扣分不合理
  - *文件：* `config.py`、`src/ocr.py`、`src/reviewer.py`
  - *预估：* 0.5d

- [ ] **process_log 作为 reviewer 判据的数据总线**
  - 所有 reviewer 的阻断决策必须至少查一次 `process_log` 对应字段（LLM 是否跑过、OCR 是否完整、来源是否隔离）
  - *why：* 当前 reviewer 完全依赖产物文本质量判定，常忽略执行上下文
  - *文件：* `src/reviewer.py`（各 `_review_*` 函数签名增加 `process_log` 参数）
  - *预估：* 1d

### P2 — 集成测试 + 测试套件修复

- [ ] **`_SNAPSHOT_KNOWN_MISSING` 清理**（来自 GAPS.md §三.3.1-3.2）
  - `ANSIB16.5法兰尺寸标准.pdf` 存在于 known_missing 但不在 `_BASELINES` 列表中 → 纯死代码，删除
  - `CB_T 8522-2011 舾装码头设计规范.pdf` 快照已生成并入库，应从 known_missing 移除 → 跑一次 `SLOW_TESTS=1` 验证后移除
  - *文件：* `tests/test_sample_score_baseline.py:27-28`

- [ ] **扫描件 baseline 补充**
  - 在 slow baseline 中增加 2-3 份扫描件（CB 589-95 + GB 39038 级别），覆盖 OCR→参数链路
  - 因 OCR 耗时（180s-600s），可单独划为 `SLOW_TESTS=2` 级别的 extended baseline
  - *影响：* 当前 12/12 基线 0 份扫描件，OCR→参数断裂在测试网中不可见
  - *文件：* `tests/test_sample_score_baseline.py`、`tests/_run_baseline_sample.py`
  - *预估：* 0.5d

- [ ] **输出目录互斥**
  - `run_iterative_pipeline` 入口检查输出目录是否有 pid lock 文件，防止多进程冲突
  - *why：* 本次抽样多进程写同一目录，导致 SN544-2 结果出现两个副本
  - *文件：* `src/pipeline.py`、`src/utils.py`
  - *预估：* 0.3d

---

## Phase 5: 业务功能优化 + 测试覆盖补全（可独立推进）

### 已完成

输出中文化收口（章节标题/表格标题/目录短语细分）、OCR 质量债务（标准编号扩充/表格对齐/15 项单元测试）、Batch report 汇总指标、OCR 置信度下沉。

### P0 — Reviewer 命中 + 核心模块测试

- [ ] **Reviewer 命中条件复核（第二轮，扩样本后）**
  - 在扩样本矩阵上逐项回看 `_review_markdown / _review_summary_* / _review_tags / _review_sources / _review_ocr_quality` 的命中门槛
  - *why：* 第一轮收紧在 7 份样例生效，但扩样本后需验证是否过拟合

- [ ] **7 个核心模块补单元测试**（来自 GAPS.md §二）
  - Phase 3 已给 5 个模块补了测试，以下 7 个仍为零覆盖。管道核心环节出 bug 时 baseline 测试能抓到但无法定位到具体函数。

  | 模块 | 行数 | 测试重点 | 预估 | 状态 |
  |------|------|---------|:----:|:----:|
  | `src/utils.py` | 92 | `normalize_line` / `normalize_cell` / `dedupe_keep_order` / `safe_write_json` / `build_output_dir_from_parts`（22 tests: 6 _pid_is_alive + 16 pure functions） | 0.2d | ✅ |
  | `src/record_access.py` | 269 | 全部 26 个访问函数，9 个 TestCase 类 40 条单测，逐字段验证中文属性封装 | 0.3d | ✅ |
  | `src/md_builder.py` | 129 | Markdown 生成与结构完整性 | 0.3d | — |
  | `src/openai_compat.py` | 205 | API 兼容层、proxy 处理、重试逻辑、json_schema 回退 | 0.5d | — |
  | `src/llm_refiner.py` | 639 | 结构精炼核心逻辑（当前只在集成测试里被 mock 掉） | 1d | — |
  | `src/fixer.py` | 406 | 多轮修正循环、问题类型路由、修正动作正确性 | 1d | — |
  | `src/parser.py` | 1500+ | 主 `parse()` 函数（`_should_reject_parameter_candidate` 和 table merge 已有测试） | 2d | — |

### P1 — 样本多样化

- [ ] **样本语料多样化**
  - 补齐德文原版 / 图纸型 PDF / 水印污染样本三类空位
  - 对每类至少放 1 份，跑出 baseline
  - *依赖：* Phase 3 slow baseline 鲁棒性已就绪

### P1 — 测试套件加固

- [ ] **ScannedBaselineTests 改为真测试**（来自 GAPS.md §三.3.3）
  - `test_scanned_baseline` 每跑必覆盖 fixture 文件，从不做 `assertEqual` 比较 → 是日志不是测试
  - *文件：* `tests/test_sample_score_baseline.py:339-340`

- [ ] **单方法测试文件扩充**（来自 GAPS.md §三.3.4）
  - `tests/test_export_contract.py` — 1 个测试方法，只测 happy path
  - `tests/test_pipeline_ocr_summary.py` — 1 个测试方法，只测一个字段

- [ ] **profiler 语言检测测试加强**（来自 GAPS.md §三.3.5）
  - `InspectTextLayerEdgeCaseTests` 的两个测试只断言 `char_count > 0`，不验证语言检测结果
  - *文件：* `tests/test_profiler.py:176-185`

### P2 — 代码卫生（来自 GAPS.md §五）

- [ ] **`_section_ref()` 改用 `record_access.section_ref()`**
  - 当前用 `section.__dict__.values()` 按位置取 `[0]`/`[1]`，字段声明顺序一变就坏
  - *文件：* `src/parser.py:1624-1628`；正确实现在 `src/record_access.py:44`

- [ ] **两处静默 `except Exception: pass` 加日志**
  - `src/openai_compat.py:13` — OpenAI SDK 导入失败无声
  - `src/openai_compat.py:167` — json_schema 回退静默吞错

- [ ] **修复误导性报错信息**
  - `src/summarizer.py:86` 错误消息引用 `OPENAI_API_KEY`，但代码实际检查的是 `LLM_API_KEY`

- [ ] **reviewer 问题 ID 中文化**
  - 29 个问题 ID 全为英文 snake_case（如 `summary_template_fallback`、`llm_stub_summary`），与其余中文契约不一致
  - *文件：* `src/reviewer.py:708-897`

- [ ] **管道内重复 `DocumentData` 导入清理**
  - `src/pipeline.py:91` 异常处理分支里防御性重新导入，模块级已有同名导入

- [ ] **LLM 模块错误处理统一化**
  - `summarizer.py` 在 LLM 失败时把原因写进 dict 但不打 log
  - `tagger.py` 在 LLM 失败时静默返回基础标签不打 log
  - `ocr.py` 总是打 warning
  - 三者对同一类故障的处理策略不统一

---

## Phase 6: 长期优化 + 部署基建（选做，允许永远不做）

### 配置与运维缺口（来自 GAPS.md §四 + 现有条目）

| 条目 | 预估 |
|------|:----:|
| `.env.example` 补全 9 个缺失环境变量（OCR 7 个 + `PIPELINE_TIMEOUT_SECONDS` + `OPENAI_CHAT_MODEL`） | 0.3d |
| Web server host/port 环境变量化（`UVICORN_HOST` / `UVICORN_PORT`） | 0.2d |
| ThreadPoolExecutor 加 shutdown（FastAPI lifespan 或 atexit 注册） | 0.3d |
| `requirements.txt` 加 lock file（`pip-tools` 或 `poetry`） | 0.3d |
| 新增 `Dockerfile` | 0.5d |
| 新增 CI/CD 配置（`.github/workflows/` 或 `.gitlab-ci.yml`） | 1d |
| `pyproject.toml` 或 `setup.py`（支持 `pip install -e .`） | 0.5d |
| `.gitignore` 补 `.pytest_cache/` / `.agent/` | 0.1d |

### 架构演进

| 条目 | 预估 |
|------|:----:|
| 配置系统现代化（迁移到 pydantic-settings） | 2d |
| LLM / OCR 接口抽象化 | 2d |
| 国际化外置（翻译映射提取到外部 JSON） | 1d |
| 管道步骤耗时监控 / 可观测性 | 2d |
| SHA-1 → SHA-256（FIPS 兼容） | 0.3d |

### 流程改进

| 条目 | 预估 |
|------|:----:|
| plan-lint pre-commit / CI gate（等 vocab 稳定后再上） | 1d |
| commit message 与 plan 文本对齐流程 | 0.5d |
| Web UI 历史批次浏览 | 2d |

---

## 不立项

- CB 1010-1990 源文件串档：metadata 红线 cap 59.99，上游人工剔除，不在代码可动空间内
- `DocumentData / DocumentProfile / PageRecord / SectionRecord` 类名中文化：决策文档见 `.agent/plans/类名中文化决策.md`，当前推荐保持现状
