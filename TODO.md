# TODO

待办、缺陷与不立项归档；不承载历史时间线或架构契约。

---

## 当前进展（2026-04-27）

Phase 1-4 全部完成，Phase 5 部分完成（150 tests passed，零回归）。

已完成的 Phase 5 条目：Batch report 汇总指标、输出中文化收口、标准编号扩充。

---

## 实施路线图

执行顺序原则：

```
Phase 1 ✅ → Phase 2 ✅ → Phase 3 ✅ → Phase 4 ✅
                                     ↓
                          Phase 5 (任何时候可独立推进)
                          Phase 6 (选做项)
```

- Phase 5 业务优化可随时并行插入，不阻塞架构推进
- Phase 6 为选做项，可永久搁置

---

### Phase 1: 扫清隐患 ✅ 已完成

从独立代码审查发现的低投入高回报改进，已全部完成并验证。

| 条目 | 来源 | 状态 |
|---|---|---|
| `src/ocr.py` finally UnboundLocalError 保护 | 独立审查 | ✅ |
| `config.py` OCR_ENABLED "FALSE" 解析 bug 修复 | 独立审查 | ✅ |
| `src/pipeline.py` review.get() on None 崩溃修复 | 独立审查 | ✅ |
| `src/reviewer.py` 死函数（_canonicalize_standard_code 等）和未引用常量清理 | 独立审查 | ✅ |
| `src/models.py` / `src/config_signatures.py` 未使用导入清理 | 独立审查 | ✅ |
| `_dedupe` 三合一 → `utils.dedupe_keep_order`（normalizer.py / ocr_eval.py） | 独立审查 | ✅ |
| `reviewer.py` _strip_markdown_metadata 替换为 source_guard 导入 | 独立审查 | ✅ |

---

### Phase 2: 错误处理加固 ✅ 已完成

#### ✅ 已完成

- [x] **API 从 OpenAI 切换为 DeepSeek**（用户要求）
  - `src/openai_compat.py`：支持 `LLM_BASE_URL` / `LLM_API_KEY` 环境变量，非 OpenAI 后端跳过 responses API，`json_schema` 不支持时自动降级为 `json_object`
  - `config.py`：`use_llm` / `openai_model` 优先读取 `LLM_*` 系变量
  - `.env` / `.env.example`：新增 DeepSeek 配置模板
  - 效果验证：SN544-1 评审分 88→93，摘要从模板占位句变为有内容的真实中文摘要，标签精度显著提升
  - *文件：* `src/openai_compat.py`、`config.py`、`.env`、`.env.example`

- [x] **`src/loader.py` 异常防护**
  - `fitz.open()` / `pdfplumber.open()` 分别加 `try/except`，任一处失败返回 `(None, None)`
  - `PDFParser.parse()` 新增 `None` 返回检测，返回空 DocumentData 而非崩溃
  - *why：* 损坏 PDF 直接传播到 `app.py` 崩溃，无任何输出
  - *文件：* `src/loader.py`、`src/parser.py`

- [x] **`src/pipeline.py` 分步错误处理**
  - 解析阶段（parser → normalizer → llm_refiner）整体 `try/except`，失败时返回空文档骨架
  - markdown / summary / tags 各自 `try/except`，失败时返回 safe default
  - 评审循环 `review_outputs` 加 `try/except`，失败时返回崩溃评审记录
  - `process_log` 新增 `"管道错误": [...]` 字段记录所有已捕获异常
  - *why：* 中间步骤失败不会丢失全部执行记录
  - *文件：* `src/pipeline.py`

- [x] **`src/fixer.py` 延迟导入加固**
  - OCR 运行时导入（`build_ocr_runtime_plan` 等）移到文件级，以 `try/except ImportError` 包裹
  - 运行时检查 `_OCR_IMPORT_OK` 标志，不可用时报"PaddleOCR 不可用"并提前终止
  - *why：* paddlepaddle/PaddleX 不可用时提前暴露，而非运行到 OCR 才崩
  - *文件：* `src/fixer.py`

- [x] **`AppConfig` 运行时字段提取**
  - 将 `force_ocr_pages`、`force_ocr_tables`、`ocr_page_evaluations` 移至新的 `PipelineContext` dataclass
  - 修改 `config.py`、`src/parser.py`、`src/fixer.py`、`src/pipeline.py` 中的引用路径
  - *文件：* `config.py`、`src/context.py`（新建）、`src/pipeline.py`、`src/parser.py`、`src/fixer.py`、`tests/test_ocr_table_structure.py`

- [x] **`AppConfig.__post_init__` 配置校验**
  - OCR 语言码合法性、`ocr_enabled`/`ocr_table_enabled` 类型检查、dpi/批大小/超时范围检查
  - *why：* 当前无效值在管道深处才暴露
  - *文件：* `config.py`

---

### Phase 3: 测试覆盖与质量基建 ✅ 已完成

#### P0 — 核心未测试模块补单元测试 ✅

| 模块 | 测试重点 | 文件 | 状态 |
|---|---|---|---|
| `source_guard.py` | `detect_metadata_mismatch_reason` 匹配/不匹配/冲突，`canonicalize_standard_code` 2位/4位年份展开 | `tests/test_source_guard.py` | ✅ |
| `profiler.py` | `profile_document` 对标准/手册/产品目录/扫描件的分类决策 | `tests/test_profiler.py` | ✅ |
| `normalizer.py` | `normalize_document` 去重、参数规范化、空章节等边界 | `tests/test_normalizer.py` | ✅ |
| `ocr_eval.py` | `evaluate_ocr_batch` 质量评分阈值逻辑，`build_force_ocr_payload` | `tests/test_ocr_eval.py` | ✅ |
| `cleaner.py` | 页眉页脚去除、重复噪音行检测 | `tests/test_cleaner.py` | ✅ |

#### P1 — 测试基建 ✅

- [x] **Slow baseline 12/12 工程鲁棒性**
  - 429 重试加 jitter 替代纯指数退避
  - `run_iterative_pipeline()` 加单样例 wall-clock 硬 cap（默认 20 分钟），超时记 `process_log["运行被截断"]=True` 但不 abort
  - `tests/test_sample_score_baseline.py` 改为 sample-level subprocess isolation，单样例 fail/timeout 不影响其他 11 份
  - *why：* 连续两轮被 `CB_T 8522-2011` 阻断 >1 小时，known_missing 已成留尾
  - *来源：* 原 TODO.md P1 "slow baseline ops fragility"
  - *文件：* `src/openai_compat.py`、`src/pipeline.py`、`config.py`、`tests/test_sample_score_baseline.py`、`tests/_run_baseline_sample.py`

- [x] **plan 条件句的"测量—决策—记录"闭环**
  - 任何带 `if X then Y` 的 plan 条目必须：1) 显式排 "run X-check" 子步骤，2) 在 FP §11 强制追加一行结果
  - *why：* 2026042402 B.3 条件落地后没跑慢基线也没记原因
  - *来源：* 原 TODO.md P1

---

### Phase 4: 架构重构（高风险，须 Phase 2 错误处理已加固 + Phase 3 测试网就绪）

#### P0 — 评审轮次前置 ✅

- [x] **管道状态对象化 → 评审轮次提前终止**
  - 先：`document / markdown / summary / tags` 封装为 `PipelineState` dataclass
  - 再：评审循环增加"本轮得分不升反降则回退到上一轮" + "早轮已通过则短路"
  - *why：* 当前固定 3 轮，第 2 轮已通过仍跑第 3 轮，浪费 LLM/OCR 调用
  - *来源：* 独立分析（状态对象化） + 原 TODO.md P1（提前终止）
  - *文件：* `src/pipeline.py`

#### P1 — 小重构 ✅

- [x] **来源隔离提前判断**
  - `detect_metadata_mismatch_reason()` 移到 `build_summary()` / `build_tags()` 之前
  - 触发隔离时直接输出隔离版摘要/标签，避免构建废品
  - *文件：* `src/pipeline.py`

- [x] **Web 层架构违规修复**
  - `_build_output_dir_from_parts` 从 `app.py` 提取到 `src/utils.py`
  - `web/runner.py` 改为从 `utils` 导入
  - *why：* Web 层导入 CLI 层私有函数是架构违规
  - *文件：* `app.py`、`src/utils.py`、`web/runner.py`

#### P2 — 大重构（需要全量 baseline 回归保护）

- [x] **合并数据访问层**
  - `to_dict()` + `record_access.py` + `structured_access.py` 三合一
  - *why：* 三者以略微不同的方式做同样的事
  - *风险：* 高，必须 Phase 3 测试网完备后才能动

---

### Phase 5: 业务功能优化（任何时候可插入，与 Phase 2-4 无阻塞关系）

#### P0

- [ ] **Reviewer 命中条件复核（第二轮，扩样本后继续做）**
  - 在扩样本矩阵上逐项回看 `_review_markdown / _review_summary_* / _review_tags / _review_sources / _review_ocr_quality` 的命中门槛
  - *why：* 第一轮收紧在 7 份样例生效，但扩样本后需验证是否过拟合
  - *来源：* 原 TODO.md P0

#### P1

- [ ] **样本语料多样化**
  - 补齐德文原版 / 图纸型 PDF / 水印污染样本三类空位
  - 对每类至少放 1 份，跑出 baseline
  - *依赖：* Phase 3 slow baseline 鲁棒性已就绪
  - *来源：* 原 TODO.md P1

- [x] **输出中文化继续收口到 LLM 主路径**
  - 细分 `显示` 类子类型（章节标题 / 表格标题 / 目录短语），压降 safety-net 触发率
  - *来源：* 原 TODO.md P1

- [x] **OCR 质量债务：扩充标准编号识别 & 参数误抽过滤（部分完成）**
  - [x] 扩充标准编号识别：STANDARD_RE 新增 JB/YB/HG/QC/LY/BB/MT/SH/SY/DL/JJG/JJF 行业标准前缀
  - [x] 更新 _classify_standard_family 同步新增前缀，更新参数候选拒绝模式支持 /Z 后缀和 ICS 分类号
  - [ ] 继续提高 OCR 表格文本质量与单元格对齐精度（待做）
  - *依赖：* Phase 2 AppConfig 运行时字段已分离
  - *来源：* 原 TODO.md P1

- [x] **Batch report 汇总指标**
  - `batch_report.json` 增加本批共 N 份 / K 份通过 / 红线触发率 / 最常见扣分项 Top3
  - *来源：* 原 TODO.md P1

- [ ] **OCR 置信度下沉到下游**
  - OCR 结果保留 per-token confidence，写入独立 `OCR置信度.json`
  - *来源：* 原 TODO.md P1

---

### Phase 6: 长期优化（Phase 4 完成后可选做）

| 条目 | 来源 | 预估 |
|---|---|---|
| 配置系统现代化（迁移到 pydantic-settings） | 独立审查 | 2d |
| LLM / OCR 接口抽象化 | 独立审查 | 2d |
| 国际化外置（翻译映射提取到外部 JSON） | 独立审查 | 1d |
| 管道步骤耗时监控 / 可观测性 | 独立审查 | 2d |
| SHA-1 → SHA-256（FIPS 兼容） | 独立审查 | 0.3d |
| plan-lint pre-commit / CI gate（等 vocab 稳定后） | 原 TODO.md P2 | 1d |
| commit message 与 plan 文本对齐 | 原 TODO.md P2 | 0.5d |
| Web UI 历史批次浏览 | 原 TODO.md P2 | 2d |
| 数据模型类名中文化 | 原 TODO.md P2（冻结） | 待决策 |

---

### 已判为非代码层问题（不立项）

- CB 1010-1990 源文件串档：metadata 红线 cap 59.99，上游人工剔除，不在代码可动空间内
- `DocumentData / DocumentProfile / PageRecord / SectionRecord` 类名中文化：决策文档见 `.agent/plans/类名中文化决策.md`，当前推荐保持现状
