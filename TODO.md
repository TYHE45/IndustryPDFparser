# TODO

待办、缺陷与不立项归档；不承载历史时间线或架构契约。

---

## 当前进展（2026-04-27）

Phase 1-4 全部完成，Phase 4.5 为当前阶段，Phase 5 部分完成（150 tests passed，零回归）。

---

## 实施路线图

```
Phase 1 ✅ → Phase 2 ✅ → Phase 3 ✅ → Phase 4 ✅
                                       ↓
                               Phase 4.5（当前阶段）
                                       ↓
                          Phase 5 (任何时候可独立推进)
                          Phase 6 (选做项)
```

---

## 已完成阶段

### Phase 1: 扫清隐患 ✅

7 项低投入高回报修复：`ocr.py` UnboundLocalError 保护、`config.py` OCR_ENABLED 解析 bug、`pipeline.py` review.get() on None 崩溃、reviewer 死函数/常量清理、models.py/config_signatures.py 未使用导入清理、`_dedupe` 三合一、reviewer `_strip_markdown_metadata` 替换为 source_guard 导入。

### Phase 2: 错误处理加固 ✅

API 切换 DeepSeek、loader/pipeline/fixer 异常防护、AppConfig 运行时字段提取（PipelineContext）、AppConfig 配置校验（OCR 语言码/类型/范围）。

### Phase 3: 测试覆盖与质量基建 ✅

核心模块单元测试（source_guard / profiler / normalizer / ocr_eval / cleaner）、slow baseline 鲁棒性（jitter 重试、wall-clock cap、subprocess isolation）、plan 条件句闭环。

### Phase 4: 架构重构 ✅

管道状态对象化→评审轮次提前终止、来源隔离提前判断、Web 层架构违规修复、数据访问层合并。

---

## Phase 4.5: 数据契约与集成层加固（当前阶段）

*2026-04-27 五份抽样暴露的系统性问题。管道已从单引擎（pdfplumber→parser）进化为多引擎（+OCR+LLM+表格识别），但集成层没有同步进化：每个新能力在自己竖井里工作，跨竖井数据流（OCR→参数、LLM状态→reviewer）没有任何形式化保证。*

#### P0 — 数据桥

- [ ] **OCR 表格结果桥接到参数提取路径**
  - OCR 表格矩阵与 pdfplumber 表格在 parser 入口处合并，统一走 `_extract_parameters_from_tables()`
  - 当前两套表格格式不一致，需加 adapter 转换
  - *影响：* CB 589-95（红线"表格未消费"）、GB 39038（S级"表格未消费"）
  - *文件：* `src/parser.py`（`_extract_page_tables` / `_extract_parameters_from_tables`）、`src/ocr.py`
  - *验证：* 对 CB 589-95 重跑，验证表格→参数链路产出 >0 个参数
  - *预估：* 0.5d

- [ ] **Reviewer 判"LLM不可用"为阻断的误判修复**
  - `_review_summary_content` 标记 `summary_template_fallback` 为阻断前，先查 `process_log["摘要LLM原因"]`，若为"配置关闭LLM摘要生成"或"LLM超时"则降为 A 级非阻断
  - *影响：* 4/5 抽样文件被误扣12分 + 阻断标记
  - *文件：* `src/reviewer.py`（`_review_summary_content`）
  - *验证：* SN544-1 重评后不报阻断；`process_log` 中有 LLM 原因时 reviewer 不误判
  - *预估：* 0.3d

#### P1 — 入口守卫

- [ ] **文档画像后加领域校验守卫**
  - `profile_document()` 产出置信度 < 0.5 或文档类型为 `unknown` 时，跳过全量解析，直接输出"超出处理领域"的简化结果
  - *影响：* 防止英文文档（Dixon 0.73→实际应为0.2）和无法分类文档（GB 39038 0.28）产生废品
  - *文件：* `src/pipeline.py`（`run_iterative_pipeline` 中 profiler 之后）
  - *验证：* 喂入英文文档，管道快速否决不走全量解析
  - *预估：* 1d

- [ ] **章节/表格数超限守卫**
  - 章节数 > 500 或表格数 > 50 时中止当前处理路径，记录 `process_log["结构异常"]`
  - *影响：* 防止 Dixon 类文档产出 31211 章节的废品输出
  - *文件：* `src/pipeline.py`、`src/normalizer.py`
  - *验证：* Dixon.2017 喂入后被守卫拦截
  - *预估：* 0.3d

#### P1 — 数据总线

- [ ] **OCR 软超时阈值可配置化 + 部分完成标记**
  - 软超时阈值从硬编码改为 `config.py` 中 `ocr_soft_timeout` 字段
  - OCR 部分完成后在 `process_log` 中记入 `OCR部分完成=True` 和 `OCR完成页数/target页数`，供 reviewer 区分"完整OCR"和"部分OCR"
  - *影响：* GB 39038 软超时后 reviewer 仍按全量OCR评估，扣分不合理
  - *文件：* `config.py`、`src/ocr.py`、`src/reviewer.py`
  - *验证：* GB 39038 重跑，process_log 记录部分完成标记
  - *预估：* 0.5d

- [ ] **process_log 作为 reviewer 判据的数据总线**
  - 所有 reviewer 的阻断决策必须至少查一次 `process_log` 对应字段（LLM是否跑过、OCR是否完整、来源是否隔离）
  - *why：* 当前 reviewer 完全依赖产物文本质量判定，常忽略执行上下文
  - *文件：* `src/reviewer.py`（各 `_review_*` 函数签名增加 `process_log` 参数）
  - *验证：* 任意阻断项在 process_log 中有对应成因记录
  - *预估：* 1d

#### P2 — 集成测试

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

## Phase 5: 业务功能优化（任何时候可插入）

### 已完成

输出中文化收口（章节标题/表格标题/目录短语细分）、OCR 质量债务（标准编号扩充/表格对齐/15项单元测试）、Batch report 汇总指标、OCR 置信度下沉。

### 待办

#### P0

- [ ] **Reviewer 命中条件复核（第二轮，扩样本后继续做）**
  - 在扩样本矩阵上逐项回看 `_review_markdown / _review_summary_* / _review_tags / _review_sources / _review_ocr_quality` 的命中门槛
  - *why：* 第一轮收紧在 7 份样例生效，但扩样本后需验证是否过拟合

#### P1

- [ ] **样本语料多样化**
  - 补齐德文原版 / 图纸型 PDF / 水印污染样本三类空位
  - 对每类至少放 1 份，跑出 baseline
  - *依赖：* Phase 3 slow baseline 鲁棒性已就绪

---

## Phase 6: 长期优化（选做）

| 条目 | 预估 |
|------|:----:|
| 配置系统现代化（迁移到 pydantic-settings） | 2d |
| LLM / OCR 接口抽象化 | 2d |
| 国际化外置（翻译映射提取到外部 JSON） | 1d |
| 管道步骤耗时监控 / 可观测性 | 2d |
| SHA-1 → SHA-256（FIPS 兼容） | 0.3d |
| plan-lint pre-commit / CI gate（等 vocab 稳定后） | 1d |
| commit message 与 plan 文本对齐 | 0.5d |
| Web UI 历史批次浏览 | 2d |
| 数据模型类名中文化 | 待决策（冻结） |

---

## 不立项

- CB 1010-1990 源文件串档：metadata 红线 cap 59.99，上游人工剔除，不在代码可动空间内
- `DocumentData / DocumentProfile / PageRecord / SectionRecord` 类名中文化：决策文档见 `.agent/plans/类名中文化决策.md`，当前推荐保持现状
