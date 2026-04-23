# First Principles — 文件解析与结构化处理项目

> **维护规则：** 任何涉及流程、架构、输出规格、Agent 分工的变动，必须第一时间更新本文件，保持本文件与实际实现一致。本文件是项目的唯一权威参考。

---

## 零、工作纪律

以下规则在整个项目开发周期内始终生效：

1. **改代码前必读 First Principles。** 每次动手修改代码之前，必须先阅读本文件，确认改动方向与项目整体规划一致。
2. **改代码后必须汇报。** 每次代码变更完成后，必须向用户汇报：
   - 更改了哪些方面，在哪些方面有确确实实的进步
   - 还有哪些不足，这些不足由什么造成的（流程问题、代码问题、还是其他原因）
   - 分析原因后，是否需要修改 First Principles；如需修改，必须先跟用户确认，不得擅自更改
3. **解析能力必须通用化。** 本项目面向多种类型的文件，分析和修正解析结果的逻辑不能局限于当前 input 文件夹中的样例文件。规则、阈值和评审标准必须适用于未见过的文档。
4. **有问题及时汇报。** 遇到任何需求不明确、技术障碍、方向疑问或需要用户决策的情况，必须第一时间汇报，不得自行猜测或跳过。

---

## 一、项目目标

将公司产品数据及行业标准文件（以 PDF 为主）输入系统，经过解析、清洗与结构化处理后，输出可供公司系统进行分析、调用、阅览的标准化数据文件。所有输出文件的内容均使用中文。

---

## 二、输入规格

| 类型 | 格式 | 说明 |
|------|------|------|
| 主要输入 | PDF | 行业标准、产品规范、技术文件等 |
| 次要输入 | Word (.docx) | 少量，暂不实现，后续迭代 |
| 次要输入 | Excel (.xlsx) | 少量，暂不实现，后续迭代 |

- 支持**批量处理**：一次上传多个文件，系统逐个解析，全部完成后输出汇总报告
- 单文件处理是批量处理的特例（批量中放一个文件即可）

---

## 三、输出规格

每个输入文件处理完成后，在 `output/` 目录下保留输入文件在 `input/` 下的**来源层级**，并在对应来源目录下生成一个以**原文件名（去扩展名）命名**的文件夹，包含以下文件。所有 JSON 文件的字段名与内容均使用中文。

### 必须输出（核心三件）
| 文件名 | 内容 |
|--------|------|
| `原文解析.md` | 原文完整解析，保留章节结构，Markdown 格式 |
| `summary.json` | 文档摘要，由 LLM 生成 |
| `tags.json` | 文档标签，由 LLM 生成 |

### 扩展输出（结构化数据）
| 文件名 | 内容 |
|--------|------|
| `文档画像.json` | 文档类型、语言、页数、布局等基本信息 |
| `章节结构.json` | 文档章节层级与大纲 |
| `表格.json` | 从文档中提取的所有表格数据 |
| `数值型参数.json` | 规格参数、数值、单位、范围 |
| `规则类内容.json` | 条款、要求、规定类文本 |
| `检验与证书.json` | 检验方法、证书要求等 |
| `引用标准.json` | 文档中引用的外部标准编号与名称 |
| `trace_map.json` | 各数据项到原文页码的溯源映射 |

### 过程记录
| 文件名 | 内容 |
|--------|------|
| `process_log.json` | 处理日志（是否调用 LLM、迭代轮次、OCR 调用与耗时等） |
| `review.json` | 最终质量评审结果（评分、是否通过） |
| `review_rounds.json` | 各轮评审与修正的详细记录（评分、问题列表、修正动作、OCR 评估摘要与页级详情） |

### 批量汇总（每批次独立）
| 文件名 | 内容 |
|--------|------|
| `批次/<batch_id>/batch_report.json` | 当前批次的独立汇总报告，记录成功/失败、来源说明与输出索引 |

### 已明确不生成的文件
以下文件在旧版本中存在，现已废除：
- `document_profile.json`（与 `文档画像.json` 重复）
- `内容块.json`（中间处理产物，下游不需要）
- `tables.json`（与 `表格.json` 重复）
- `原文解析.json`（与 `原文解析.md` 内容重叠）
- `facts.json`（各类数据已分散在独立文件中）
- 所有 `_v2` 后缀文件（架构统一后不再需要）

---

## 四、处理流程

```
用户通过 Web UI 选择文件、选择文件夹或拖拽导入一个或多个文件
    ↓
识别文件类型（当前仅支持 PDF）
    ↓
提取原始文本、章节结构、表格
    ↓
数据清洗（去除页眉页脚、噪音、格式标准化）
    ↓
LLM 结构精炼（GPT-5.4，可多轮迭代）
    ↓
生成原文解析.md + 所有结构化 JSON
    ↓
LLM 生成 summary.json 与 tags.json
    ↓
进入评审修正循环（最多 3 轮，见第八节）
    ↓
导出全部输出文件到保留来源层级的目标文件夹
    ↓
批量处理完成后生成当前批次专属的 batch_report.json
```

---

## 五、技术栈

| 组件 | 技术选型 |
|------|---------|
| 后端框架 | Python + FastAPI |
| 前端界面 | HTML/CSS/JS（本地 Web UI，浏览器打开） |
| 实时进度 | Server-Sent Events（SSE） |
| PDF 解析 | PyMuPDF + pdfplumber |
| OCR | PaddleOCR + paddlepaddle（懒加载，仅在评审红线触发 `文本层不足需要OCR` 时调用） |
| LLM | OpenAI API，模型 GPT-5.4，Key 存于 .env 文件 |
| 配置管理 | python-dotenv；OCR 相关配置项：`ocr_enabled` / `ocr_lang`（默认 `ch`）/ `ocr_dpi`（默认 300） |

---

## 六、数据模型规范

**只维护一套数据模型**，以 `DocumentData` 为核心，所有字段名使用中文。

- 废除 v2 系列属性（`pages_v2`、`nodes_v2`、`products_v2`、`parameter_facts_v2`、`rule_facts_v2`、`standard_facts_v2`）
- 废除 `ParsedDocument` 类
- 将 v2 中有价值的溯源能力（`source_refs`、锚点追踪）合并进 `DocumentData` 的字段中，字段名改为中文
- pipeline 只走单一数据流，不再有条件性的 v2 分叉输出

---

## 七、项目文件结构

```
v9work/
├── app.py                  # 主程序入口（待扩展为 Web）
├── config.py               # 配置管理
├── .env                    # API Key（不提交 git）
├── .env.example            # Key 模板，供参考
├── requirements.txt
├── First Principles.md     # 本文件，项目唯一权威参考
├── README.md               # 快速上手说明
├── src/
│   ├── loader.py           # 文件加载（当前仅 PDF）
│   ├── parser.py           # 文本与结构解析
│   ├── cleaner.py          # 数据清洗
│   ├── normalizer.py       # 标准化处理
│   ├── profiler.py         # 文档类型识别与画像
│   ├── llm_refiner.py      # LLM 结构精炼
│   ├── md_builder.py       # 生成原文解析.md
│   ├── summarizer.py       # 生成 summary.json
│   ├── tagger.py           # 生成 tags.json
│   ├── fixer.py            # 定向修正（评审循环使用）
│   ├── reviewer.py         # 质量评审
│   ├── exporter.py         # 导出所有输出文件
│   ├── pipeline.py         # 主流程编排
│   ├── models.py           # 数据模型定义（单一模型）
│   └── utils.py            # 工具函数
├── input/
│   ├── industry_standard/  # 行业标准文件
│   ├── product_sample/     # 产品数据文件
│   └── uploads/            # Web UI 上传文件的溯源证据（按 batch_id 分目录，不自动清理）
└── output/
    ├── 批次/
    │   └── <batch_id>/
    │       └── batch_report.json   # 当前批次独立汇总报告
    └── 来源目录/                   # 保留 input/ 下的相对来源层级
        └── 文件名/                 # 每个文件独立输出文件夹
```

---

## 八、评审修正循环

评审最多执行 3 轮，每轮结果记录进 `review_rounds.json`。

```
构建输出（md + JSON）
    ↓
Review 第 N 轮（N = 1, 2, 3）
    ↓
通过（总分 ≥ 85 且无红线触发）？
    ├─ 是 → 直接进入导出
    └─ 否 → 识别问题类型，定向修正
               ├─ 红线：正文主链缺失 → 重跑 parser
               ├─ 红线：文本层不足需要OCR → 调 PaddleOCR 对低文本层页识别 → 执行 OCR 页级评估 → 仅将评估合格页注入 config.force_ocr_pages → 重跑 parser
               ├─ S级：markdown 结构问题 → 重跑 md_builder
               ├─ A级：summary/tags 问题 → 重跑 summarizer/tagger
               └─ B级：标签噪音 → 局部清洗（fixer）
               ↓
           N < 3 → 返回 Review
           N = 3 → 强制导出，在 review.json 中标记未通过原因
```

**原则：**
- 每轮只修正有问题的模块，不整体重新解析
- 无论最终是否通过，都必须完整导出所有文件
- `review_rounds.json` 记录每轮的评分、问题列表、修正动作，以及 OCR 执行时的评估摘要与页级详情

---

## 九、Agent 分工

开发过程中采用四类 Agent 协作，按模块循环推进：

| Agent | 职责 |
|-------|------|
| **Plan Agent** | 在开始编写每个模块前，设计具体实现方案，明确接口与数据流 |
| **Code Agent** | 按 Plan Agent 的方案编写代码，不过度设计 |
| **Review Agent（代码层）** | 检查代码质量、逻辑漏洞、安全问题 |
| **Review Agent（输出层）** | 运行后检查输出文件的格式合规性与内容质量，触发修正迭代 |

### 开发循环
```
Plan Agent → 设计模块方案
    ↓
Code Agent → 实现代码
    ↓
Review Agent（代码层）→ 审查代码
    ↓
运行，生成输出文件
    ↓
Review Agent（输出层）→ 验收输出质量
    ↓
（不合格）→ 反馈 Code Agent 修改 → 重新循环
（合格）  → 进入下一个模块
```

---

## 十、质量标准（Review 通过条件）

Review 采用三层评分机制，总分 100 分，通过线 85 分：

| 评分层 | 满分 | 评估内容 |
|--------|------|---------|
| 基础质量分 | 35 | 章节完整性、表格提取、markdown 结构清洁度 |
| 事实正确性分 | 40 | summary/tags 与原文一致性，参数值准确性 |
| 一致性与可追溯性分 | 25 | 各输出文件间引用一致，数据可溯源到原文 |

**红线规则**（任一触发则总分上限降至 75 以下，强制不通过）：
- 原文解析未建立正文主链
- 表格存在但参数未建立
- 文本层不足需要 OCR（仅当 `PageRecord.OCR是否注入解析=False` 且 OCR 未能恢复足够正文时保留红线；若 OCR 已成功注入并建立正文主链，则不再永久封顶）

---

## 十一、当前状态与待办

> 最近整理：2026-04-23。本节按「稳定能力」→「近期落地（时间倒序）」→「下一阶段待办（带 why）」→「不立项」的顺序组织，避免同一条目在「缺陷 / 目标 / backlog」里重复出现。

### 稳定能力（已验收，可直接依赖）

- **解析链路**：PDF 加载 → parser（文本 + 章节 + 表格）→ cleaner / normalizer → profiler → LLM 精炼 → md_builder → summarizer / tagger
- **评审循环**：最多 3 轮，fixer 按问题类型定向修正（见 §8）；每轮快照写入 `review_rounds.json`
- **评分契约**：§10 严格 35 / 40 / 25 加权，红线 cap=74（整数），通过条件 `总分 ≥ 85 且 红线列表为空`
- **数据模型**：单一 `DocumentData`，字段全中文（见 §6）；`record_access` / `structured_access` 同步中文契约
- **输出文件**：14 个必需输出（见 §3），6 个旧文件已明确废除；`exporter` 有禁写内部键护栏
- **Web UI**：FastAPI + SSE + 批量处理 + 每批独立 `batch_report.json` + 中文任务卡片字段
- **OCR 能力**：PaddleOCR 懒加载 + 页级评估 + 仅注入合格页 + SCAN_LIKE 已 OCR 自动放行
- **工程护栏**：8 项回归测试（`tests/` 目录）覆盖评分契约 / 输出文件合同 / Web 批次字段 / 中文 fallback
- **中文输出后处理**：`src/text_localization.py`（正则翻译 + "（原文：X）" 兜底），summarizer / tagger 在章节摘要 / 数值参数 / 规则要求 / 标签主题四处接入

### 近期落地（时间倒序）

**2026-04-23（本轮）**

- [x] 回归测试首批 8 项全通过：`test_review_contract`（3）/ `test_export_contract`（1）/ `test_web_batch_contract`（1）/ `test_chinese_output_fallback`（3）
- [x] 样本回归：`SN544-1`（历史 94）重跑得 100；`SN544-2`（历史 69.99 + SCAN_LIKE 红线）经 OCR 注入第 2 轮得 100，`SCAN_LIKE → OCR → 重解析 → 红线放行` 链路验证通过
- [x] reviewer 收口到 §10 严格 35/40/25 + 红线 cap=74；删除 11 处重复函数定义（文件 1254 → 925 行）；`_detect_redlines` 收口到 §10 规定的 3 条红线
- [x] DocumentData / DocumentProfile / PageRecord / SectionRecord 等数据模型属性全面中文化（~20 字段，`src/models.py`），删除 v2 遗留，不保留 shim
- [x] 输出字段名中文化：`summary.json` / `tags.json` / `review.json` / `review_rounds.json` / `process_log.json`（OCR / ID 等约定俗成缩写保留）
- [x] 输出内容中文化后处理：新增 `src/text_localization.py`，summarizer / tagger 四处接入
- [x] record_access / structured_access 访问层同步中文契约；`pipeline.collect_failure_reasons` 公开化给 web/runner 复用
- [x] OCR 规则治理四件套：
  - parser 对 OCR 注入页的标题候选降级（`_looks_like_ocr_fragment_heading`，`src/parser.py:633-654`）：尾部句内标点 / 虚词 / <4 字非 2–3 字纯 CJK / 纯数字或符号
  - profiler 广告/水印/元数据密度识别（`src/profiler.py:32-140`）：`advertisement_line_ratio` / `metadata_line_ratio` / `structural_signal_count` + 3 条 OCR 触发理由（`watermark_only` / `advertisement_without_structure` / `metadata_heavy_low_structure`）
  - ocr_eval 三项碎片化指标（`src/ocr_eval.py:19-48`）：`_isolated_punct_ratio` / `_short_line_ratio` / `_isolated_char_line_ratio`
  - reviewer OCR 标题噪音阈值动态化（`src/reviewer.py:420-429`）：`2 ≤ x < 5` → B 级扣 3.0；`≥ 5` → A 级扣 6.0

**2026-04-21（上一轮）**

- [x] reviewer 四项"假通过"拦截：SCAN_LIKE 条件放宽、空骨架硬检查、LLM 自述无内容检查（`_review_summary_llm_stub`）、metadata↔内容一致性 cap 60（`_review_metadata_consistency`）
- [x] profiler `needs_ocr` 增加字符质量占比 <0.5 二级触发（`_compute_quality_ratio`）
- [x] parser 章节切分 3 条噪音过滤 + 数值参数 4 条 fullmatch 黑名单 + `STANDARD_RE` 扩充 GB/T、CB/T、CH
- [x] `PageRecord` 字段收口（旧 `是否OCR` 合并到 `OCR是否注入解析`）

**更早**

- [x] 评审修正循环（fixer.py + pipeline.py 3 轮 + `review.json` / `review_rounds.json`）
- [x] reviewer 增加 `OCR专项检查`（OCR 标题噪音 / OCR 参数污染）
- [x] PaddleOCR 接入（`src/ocr.py` 懒加载单例，失败返回空字典不抛出）
- [x] fixer `标记需OCR` 改为实跑 OCR，把识别文本注入 `config.force_ocr_pages`；SCAN_LIKE 红线自动放行
- [x] OCR 页级评估（`fixer.py` 仅注入「通过/边缘可用」页）；`review_rounds.json` 记 `OCR评估摘要` / `OCR页级详情`；`process_log.json` 记 OCR 全量运行指标
- [x] 数据模型统一（废除 v2 系列，单一 `DocumentData`）；exporter 精简到 14 文件
- [x] Web UI：FastAPI + SSE + 选择文件/文件夹/拖拽 + 来源层透传 + 上传文件保留到 `input/uploads/<batch_id>/`
- [x] Web UI 代码审查 P1+P2 六项改动（事件历史上限 / 批次状态派生 / traceback 捕获 / pipeline 结果契约 / 状态锁 / "部分完成"状态）
- [x] `batch_report.json` 改为每批次独立落盘（`output/批次/<batch_id>/`）
- [x] Web / API / SSE 文件结果字段统一中文契约（`总分 / 是否通过 / 红线触发 / 未通过原因 / 评审轮次数`）
- [x] `.env.example` 模板 + `load_dotenv()` 修复

### 下一阶段待办（2026-04-23 更新）

**P0 — 评分模型反测（最紧迫，因双样本满分而存疑）**

- [ ] 扩大样本回归：跑 `SN200 / SN545 / SN751 / SN775 / CB 589` 五份已知历史分布的样例，对比历史分数与新评分结果，把结果汇成表追加到本小节
  - *why：* 当前仅 SN544-1 / SN544-2 两份样例均满分 100，不排除 `ISSUE_DEDUCTIONS` 扣分额度整体过宽（"字段齐全 + 无外文泄漏 → 直接满分"）；必须用更大样本反测
  - *产物位置：* `_tmp_review_output/`，结果追加到本小节；如出现"该扣不扣"则补更严的判定；如回归结果与历史分数偏差很大，立项调整扣分表

**P1 — 输出内容中文化收口到 LLM 端**

- [ ] summarizer / tagger 的 prompt 显式要求中文输出；遇外文正文时 LLM 先中文化再生成摘要/标签
  - *why：* 当前只做了"后处理兜底"——对超出 `TRANSLATION_PATTERNS` 的术语会退化为"原文：X"的标注形态，本质上没做到"中文化"；要把中文化责任上移到 LLM 侧，让后处理只做安全网

**P1 — OCR 质量债务（分四小项继续压）**

- [ ] OCR 后数值型参数抽取精度：过滤日期 / 标准号 / 分类号 / 实施日期等误抽项
- [ ] 扩充标准编号识别：覆盖 GB / CB 等中文标准体系的漏抽变体
- [ ] reviewer OCR 专项检查收紧：补标准实体缺失 / 表格漏抽 / 结构化主链质量的更强约束
- [ ] 大扫描件性能优化：DPI 可配 / 分批识别 / 超时与降级策略
- [ ] 集成 PaddleOCR Table 或 PP-StructureV3 的 `table_structure_recognition`：解决纯表格扫描件（如 `CB_T 4196` / `CB_Z 281`）核心表格抽不到
  - *why：* 规则治理四件套（2026-04-23）只解决了"OCR 注入页的标题/参数污染不溢出到评分"，但对"纯表格 PDF 扫描件"这类输入，现在仍是缺能力而不是缺规则

**P2 — 数据模型类名层面中文化（需用户决策）**

- [ ] `DocumentData / DocumentProfile / PageRecord / SectionRecord` 类名是否也中文化
  - *why：* 字段层已全中文；但类名改中文会与 Python 惯例、IDE 类型提示、第三方类型检查生态冲突，是否值得做是产品/风格决策，不是工程问题

**P2 — Web UI 与批处理体验**

- [ ] 历史批次浏览与批次报告回看
- [ ] 浏览器侧端到端验收：任务卡片展示与 API / SSE 字段长期一致性自动化

### 已判为非代码层问题（不立项）

- CB 1010-1990 源文件串档：metadata 红线 cap 59.99，上游人工剔除，不在代码可动空间内
