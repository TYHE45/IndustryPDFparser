# TODO

待办、缺陷与不立项归档；不承载历史时间线或架构契约。

---

## 当前进展（2026-04-30）

Phase 1-4 全部完成，Phase 4.5 全部收口（P0/P1/P2 完成），Phase 5 P0 全部 7 个核心模块单元测试补全完成（707 tests passed，零回归）。

GAPS.md 全量审计（2026-04-29）发现新缺陷已并入本文件。

本轮收口：Phase 4.5 全部完成（P0 阻断性缺陷/P1 数据总线/P2 集成测试）。下一阶段：Phase 5 P2 代码卫生 6 项 + P1 测试套件加固 + P0 Reviewer 复核。

上轮收口：Phase 4.5 P1 数据总线两项（OCR 软超时可配置 + process_log reviewer 集成）+ 三轮修复（来源隔离轮间更新/摘要字段补齐/OCR软超时独立可配）。Phase 5 P0 单元测试：全部 7 模块（utils.py 22 + record_access.py 40 + md_builder.py 42 + openai_compat.py 44 + llm_refiner.py 114 + fixer.py 53 + parser.py 217 = 532 tests）已完成。

上轮收口：Phase 4.5 P0-1（`_pid_is_alive` Windows Bug）、P0-2（Reviewer LLM 误判阻断）、P0-3（OCR 表格桥接诊断验证 — 桥接代码存在且生效，CB 589-95 产出了参数）。Phase 4.5 P1 文档画像领域校验守卫已实现，章节/表格数超限守卫确认已存在。

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

- [x] **OCR 软超时阈值可配置化 + 部分完成标记** — 2026-04-30 收口
  - `config.py`: 新增 `ocr_soft_timeout` property，由 `OCR_SOFT_TIMEOUT_SECONDS` 环境变量独立控制，未设置时回退到 `ocr_timeout_seconds`
  - `fixer.py`: 移除硬编码 180.0，改用 `config.ocr_soft_timeout`
  - `pipeline.py`: `_build_ocr_process_summary` 新增 `OCR完成页数` 字段；`_pre_review_context` 传入 `review_outputs`，轮间刷新 OCR 完成状态
  - *文件：* `config.py`、`src/fixer.py`、`src/pipeline.py`、`.env.example`

- [x] **process_log 作为 reviewer 判据的数据总线** — 2026-04-30 收口
  - `_review_ocr_quality`：OCR 部分完成时区分"软超时停止"vs"OCR 引擎质量问题"
  - `_review_sources`：来源隔离时 SCAN_LIKE 附加上下文说明
  - `_review_summary_llm_stub`：LLM 未调用时跳过 LLM stub 标记（预期行为）
  - `_review_summary_structure`：已有 `process_log` fallback 路径
  - 三轮收口修复（cfc5b50）：来源隔离轮间更新 + 摘要字段补齐 + OCR 软超时独立可配
  - *影响：* GB 39038 软超时后 reviewer 不再按全量 OCR 评估，扣分更合理
  - *文件：* `src/reviewer.py`、`src/pipeline.py`、`config.py`、`.env.example`

### P2 — 集成测试 + 测试套件修复

- [x] **`_SNAPSHOT_KNOWN_MISSING` 清理** — 2026-04-30 收口
  - ANSIB16.5：不在 `_BASELINES` → 纯死代码，删除
  - CB_T 8522：已入库 `_BASELINES`（score=74.0）+ fixture 已生成 → 移出 known_missing，快照比较现已生效
  - `_SNAPSHOT_KNOWN_MISSING` 改为空 `set()`，变量保留（line 221 引用）
  - *文件：* `tests/test_sample_score_baseline.py:27`

- [x] **扫描件 baseline 补充** — 2026-04-30 收口（有限收口）
  - `scanned_version/` 目录仅 2 份 PDF：CB 589-95 + GB 39038-2020（已在 `_BASELINES`）
  - CB 589-95 校准完成：domain guard 正确拦截（置信度 0.28），score=0.0/redline=True/rounds=0
  - `test_scanned_baseline` snapshot 修复为真测试（missing_deductions + _UPDATE_SNAPSHOTS gate + 比较断言）
  - *留尾：* 待后续获取更多扫描件样本后扩充 `_SCANNED_BASELINES`
  - *文件：* `tests/test_sample_score_baseline.py:113-122, 330-358`

- [x] **输出目录互斥** — 2026-04-27 完成 (commit 8b4f3e0)
  - `run_iterative_pipeline` 入口检查输出目录 `.pipeline.lock` PID 文件
  - `src/utils.py`：`try_acquire_pipeline_lock` / `release_pipeline_lock` / `_pid_is_alive`
  - `src/pipeline.py`：入口获取锁、所有返回路径释放锁、僵死锁自动恢复
  - *文件：* `src/pipeline.py`、`src/utils.py`

---

## Phase 5: 业务功能优化 + 测试覆盖补全（可独立推进）

### 已完成

输出中文化收口（章节标题/表格标题/目录短语细分）、OCR 质量债务（标准编号扩充/表格对齐/15 项单元测试）、Batch report 汇总指标、OCR 置信度下沉。

### P0 — Reviewer 命中 + 核心模块测试

- [ ] **Reviewer 命中条件复核（第二轮，扩样本后）**
  - 在扩样本矩阵上逐项回看 `_review_markdown / _review_summary_* / _review_tags / _review_sources / _review_ocr_quality` 的命中门槛
  - *why：* 第一轮收紧在 7 份样例生效，但扩样本后需验证是否过拟合

- [x] **7 个核心模块补单元测试**（来自 GAPS.md §二） — 2026-04-30 全部完成 ✅
  - Phase 3 已给 5 个模块补了测试，以下 7 个仍为零覆盖。管道核心环节出 bug 时 baseline 测试能抓到但无法定位到具体函数。

  | 模块 | 行数 | 测试重点 | 预估 | 状态 |
  |------|------|---------|:----:|:----:|
  | `src/utils.py` | 92 | `normalize_line` / `normalize_cell` / `dedupe_keep_order` / `safe_write_json` / `build_output_dir_from_parts`（22 tests: 6 _pid_is_alive + 16 pure functions） | 0.2d | ✅ |
  | `src/record_access.py` | 269 | 全部 26 个访问函数，9 个 TestCase 类 40 条单测，逐字段验证中文属性封装 | 0.3d | ✅ |
  | `src/md_builder.py` | 129 | Markdown 生成与结构完整性：5 个 TestCase 类 42 条单测（_clean_body / _should_render_table_heading / _should_suppress_section_heading / _collect_standards / build_markdown） | 0.3d | ✅ |
  | `src/openai_compat.py` | 205 | API 兼容层、proxy 处理、重试逻辑、json_schema 回退：7 个 TestCase 类 44 条单测 | 0.5d | ✅ |
  | `src/llm_refiner.py` | 639 | 结构精炼核心逻辑：13 个 TestCase 类 114 条单测（纯函数 67 + 文档变更 + 收集/应用/集成） | 1d | ✅ |
  | `src/fixer.py` | 406 | 多轮修正循环、问题类型路由、修正动作正确性：7 个 TestCase 类 53 条单测 | 1d | ✅ |
  | `src/parser.py` | 1500+ | 纯函数/检测方法：10 个 TestCase 类 217 条单测（heading 分类/表格检测/标准识别/值检测/OCR 碎片/字符串转换/参数命名/表格结构/行处理/章节引用） | 2d | ✅ |

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

### P2 — 代码卫生（来自 GAPS.md §五）— 2026-04-30 收口（Item 4 除外）

- [x] **`_section_ref()` 改用 `record_access.section_ref()`** — 2026-04-30
  - `parser.py`: `_section_ref` 改为委托 `record_access.section_ref()`，消除 `__dict__.values()` 位置依赖
  - `record_access.py`: `section_ref()` 补 `normalize_line()`，与旧实现行为完全等价
  - *文件：* `src/parser.py:1625`、`src/record_access.py:44`

- [x] **两处静默 `except Exception: pass` 加日志** — 2026-04-30
  - OpenAI SDK 导入失败 → `logging.warning("OpenAI SDK 导入失败，LLM 功能将不可用", exc_info=True)`
  - json_schema 回退 → `logging.warning("json_schema 模式不受支持，回退到 json_object 模式", exc_info=True)`
  - *文件：* `src/openai_compat.py`

- [x] **修复误导性报错信息** — 2026-04-30
  - `OPENAI_API_KEY` → `LLM_API_KEY`（`src/summarizer.py:88`）

- [ ] **reviewer 问题 ID 中文化** — **暂缓（HIGH RISK）**
  - 27 个问题 ID 嵌入 baseline snapshots（15+ JSON）+ fixer.py 路由 + reviewer 测试断言
  - 中文化会破坏全部 baseline fixture、下游 JSON 消费者、测试断言
  - *建议：* 待 baseline 快照格式大版本升级时一并处理
  - *文件：* `src/reviewer.py:783-973`

- [x] **管道内重复 `DocumentData` 导入清理** — 2026-04-30
  - 两处 except 处理内重复导入提升为模块级单次导入
  - *文件：* `src/pipeline.py:40`

- [x] **LLM 模块错误处理统一化** — 2026-04-30
  - `summarizer.py` / `tagger.py` 加 `logging.warning()`，与 `ocr.py` 统一策略
  - *文件：* `src/summarizer.py`、`src/tagger.py`

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
