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
│   ├── ocr.py              # PaddleOCR 懒加载 + 运行计划 + 表格结构识别
│   ├── ocr_eval.py         # OCR 页级评估（孤立标点率 / 短行率 / 孤立单字率）
│   ├── record_access.py    # DocumentData 访问层（中文属性封装）
│   ├── structured_access.py # 结构化数据访问层
│   ├── text_localization.py # 输出内容中文化后处理（带 warning 安全网）
│   ├── source_guard.py     # 标准码规范化与来源核验
│   ├── openai_compat.py    # OpenAI/LLM 客户端封装（结构化 JSON 请求）
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

> 最近整理：2026-04-24。本节按「稳定能力」→「近期落地（时间倒序）」→「本轮盘点新发现的缺陷」→「下一阶段待办（带 why）」→「不立项」的顺序组织，避免同一条目在多处重复出现。

### 稳定能力（已验收，可直接依赖）

- **解析链路**：PDF 加载 → parser（文本 + 章节 + 表格）→ cleaner / normalizer → profiler → LLM 精炼 → md_builder → summarizer / tagger
- **评审循环**：最多 3 轮，fixer 按问题类型定向修正（见 §8）；每轮快照写入 `review_rounds.json`
- **评分契约**：§10 严格 35 / 40 / 25 加权，红线 cap=74（整数），通过条件 `总分 ≥ 85 且 红线列表为空`
- **数据模型**：单一 `DocumentData`，字段全中文（见 §6）；`record_access` / `structured_access` 同步中文契约
- **输出文件**：14 个必需输出（见 §3），6 个旧文件已明确废除；`exporter` 有禁写内部键护栏
- **Web UI**：FastAPI + SSE + 批量处理 + 每批独立 `batch_report.json` + 中文任务卡片字段
- **OCR 能力**：PaddleOCR 懒加载 + 页级评估 + 仅注入合格页 + SCAN_LIKE 已 OCR 自动放行
- **工程护栏**：19 项回归测试（`tests/` 目录）覆盖评分契约 / 输出文件合同 / Web 批次字段 / 中文 fallback / LLM 中文 prompt 约束 / reviewer OCR 专项检查 / OCR 运行计划与 process_log 汇总 / OCR 表格结构识别接入
- **中文输出后处理**：`src/text_localization.py`（正则翻译 + "（原文：X）" 兜底 + warning 可观测性），summarizer / tagger 在章节摘要 / 数值参数 / 规则要求 / 标签主题四处接入

### 近期落地（时间倒序）

**2026-04-23（本轮）**

- [x] D 类名中文化决策文档已产出（仅讨论，不改代码）
  - 产物：`.agent/plans/类名中文化决策.md`
  - 文档包含三种方案：全量中文化 / 只改核心类 / 保持现状，并分别给出收益、风险、改动面和回归成本
  - 当前推荐结论是“保持现状”，原因不是做不到，而是这项工作的收益主要是风格一致性，而当前更高优先级仍是 reviewer 命中条件、OCR 文本质量和表格单元格对齐精度
  - 这意味着 **阶段 D 已完成**；当前剩余的不是“缺少方案”，而是“是否要实施方案二或方案一”的用户决策

- [x] C5 表格结构识别新能力接入（PaddleOCR `TableStructureRecognition`）
  - `config.py`：新增 `OCR_TABLE_ENABLED` 开关，以及运行期注入字段 `force_ocr_tables`
  - `src/ocr.py`：新增 `get_table_structure_engine()` 与 `run_table_structure_on_pages()`；在不引入 `paddlex[ocr]` 额外依赖的前提下，直接复用当前环境可用的 `paddleocr.TableStructureRecognition`
  - 表格识别结果会和页面 OCR 文本框做轻量合并，产出标准二维表格矩阵；失败时优雅降级为空结果，不阻断原有 OCR / parser 主链
  - `src/fixer.py`：OCR 修正动作在拿到可注入页后，会额外尝试 OCR 表格识别，把结果写入 `fix_meta / review_rounds.json`，并通过 `force_ocr_tables` 注入到下一轮 parser
  - `src/parser.py`：`_extract_page_tables()` 现在会合并 `pdfplumber` 原生表格与 `force_ocr_tables` 注入表格，继续复用既有 `表格列表 -> 数值参数 -> exporter` 主链
  - 新增 `tests/test_ocr_table_structure.py` 两项测试：覆盖“表格结构识别结果转二维矩阵”和“parser 合并 OCR 表格注入”
  - 全量测试从 17 → 19，`python -m unittest discover -s tests -p "test_*.py"` 全通过
  - 运行验证：
    - 合成表格 PDF 烟测：`run_table_structure_on_pages()` 能跑通并返回 1 个表格矩阵
    - 真实样例回归：`SN544-2.pdf` 全流程重跑后仍为 `100.0`，`review_rounds.json` 第 1 轮已带 `OCR表格识别结果`
  - 当前边界：该能力已经接入主链，但“结构框正确、文字识别偏弱”仍可能发生；后续若要继续提质，重点不在接线，而在 OCR 文本质量和表格单元格对齐精度

- [x] C4 大扫描件 OCR 性能优化
  - `config.py`：补 `OCR_PAGE_BATCH_SIZE / OCR_TIMEOUT_SECONDS / OCR_LARGE_DOC_PAGE_THRESHOLD / OCR_REDUCED_DPI` 四个运行参数；`OCR_DPI` 本来就已存在，本轮不是重复加配置，而是把“大样本降 DPI / 分批 / 软超时”补齐
  - `src/ocr.py`：新增 `build_ocr_runtime_plan()`；`run_ocr_on_pages()` 改为按批执行，并在批次边界应用软超时，超时后保留已完成页的部分结果
  - `src/fixer.py`：OCR 修正动作现在会记录执行计划（原始 DPI / 实际 DPI / 批大小 / 超时秒数）和执行结果（执行页数 / 成功页数 / 是否超时）
  - `src/pipeline.py`：把 `OCR评估摘要` 的 `OCR分辨率DPI` 正确透传到 `process_log.json`，同时把 `OCR执行计划 / OCR执行结果` 带进 `review_rounds.json`
  - 新增 `tests/test_ocr_runtime.py` 两项测试：覆盖“大样本自动降 DPI”和“软超时保留部分结果”；新增 `tests/test_pipeline_ocr_summary.py` 一项测试：覆盖 `process_log` 读取 `OCR分辨率DPI` 的字段名契约
  - 全量测试从 14 → 17，`python -m unittest discover -s tests -p "test_*.py"` 全通过
  - 样例回归：`SN544-2.pdf` 真实 OCR 路径重跑后仍为 `100.0`，未因分批/软超时机制回退
- [x] C3 reviewer OCR 专项检查收紧
  - `src/reviewer.py`：OCR 专项检查除了标题噪音 / 参数污染之外，新增对三类“OCR 已恢复但结构化没跟上”的强约束补命中：
    - `STANDARD_ENTITY_MISSING`：OCR 页文本已出现标准号，但结构化结果仍无标准实体
    - `TABLE_CORE_MISSING`：OCR 页文本明显呈现表格驱动信号，但结构化结果仍未抽出核心表格
    - `STRUCTURED_BACKBONE_MISSING`：OCR 后只有极弱骨架（章节/节点 ≤1、正文线不足、事实层不足）
  - 同时把 `TABLE_NOT_CONSUMED / STANDARD_ENTITY_MISSING / STRUCTURED_BACKBONE_MISSING / TABLE_CORE_MISSING` 的 reason 常量化，保证 OCR 专项检查与来源检查复用同一条 issue 语义，不会因为不同 reason 文案造成双重扣分
  - 新增 `tests/test_reviewer_ocr_quality.py` 三项测试，覆盖“标准实体缺失 / 表格漏抽 / 主链弱骨架”三条命中条件
  - 全量测试从 11 → 14，`python -m unittest discover -s tests -p "test_*.py"` 全通过
  - 样例回归：`SN544-1.pdf` 与 `SN544-2.pdf` 重跑后仍均为 `100.0`，未出现 OCR 样例回退
- [x] B2 第一阶段落地：LLM 中文化 prompt 收口到主路径
  - `src/summarizer.py`：system prompt 明确约束“**简体中文主干** / 外文仅允许作为必要括注 / 不得直接回传大段外文原句 / 中文原料不得再包装成‘原文：…’”
  - `src/tagger.py`：英文 tag prompt 改为中文契约，要求标签以中文名词短语为主，禁止退化成长句或“原文：X”
  - `src/text_localization.py`：从纯后处理工具退位为**带 warning 的安全网**；一旦真的触发原文兜底，会在日志中留下 `"text_localization 安全网已触发"`，便于后续统计主路径命中率
  - 新增 `tests/test_llm_chinese_prompt.py` 三项测试：英文摘要 prompt / 德文标签 prompt / 混合输入保持中文主干并验证 safety-net warning
  - 当前总测试数从 8 → 11，`python -m unittest discover -s tests -p "test_*.py"` 全通过
  - 样例验证：`SN775_2009-07_e.pdf` 与 `SN544-1.pdf` 重跑后都仍为 `100.0`，未出现英文样例倒退或中文样例被污染成整段“原文：…”的评分回归
  - 结论：**B2 的“prompt 约束 + safety-net 可观测性”已完成**；但真实样例运行时仍出现大量 safety-net warning，说明 LLM 中文化主路径虽然已经收紧，但安全网仍在高频介入，后续还需要继续观察并压低 fallback 触发率
- [x] P0 评分模型反测（`_tmp_review_output/p0_score_backtest/`）：5 份样例全部成功产出 14 个必需文件，0 个废除文件，未见未处理异常
  | 样例 | 历史分数 | 本轮总分 | 是否通过 | 评审轮次 | 红线 | 最大扣分项 |
  |------|----------|----------|----------|----------|------|------------|
  | `SN200_2007-02_中文.pdf` | 84.99 + 红线 | 90.0 | 是 | 1 | 无 | 参数标签存在噪音 / 标签存在句子污染（各 5.0） |
  | `SN545-1.pdf` | 79.99 + 红线 | 100.0 | 是 | 1 | 无 | 无 |
  | `SN751.pdf` | 69.99 + 红线 | 97.0 | 是 | 2 | 无 | OCR 标题噪音轻度（3.0） |
  | `SN775_2009-07_e.pdf` | 94 | 100.0 | 是 | 1 | 无 | 无 |
  | `CB 589-95.pdf` | 未跑过 | 100.0 | 是 | 2 | 无 | 无 |
  - 观察：结果不是“5/5 满分”，说明扣分表并非完全失效；但 `SN545-1`（历史未通过）直接变成 0 问题 100 分，说明当前风险已从“扣分数字过宽”转成“部分 issue 根本没被命中”
  - 分岔结论：按保守路径进入 B1，先做一次只改数字的最小校准，验证“继续拉紧扣分额度”是否还有收益
- [x] B1 扣分表最小校准（仅改 `ISSUE_DEDUCTIONS` 数字，不改 35/40/25、不改红线）
  - 调整项：`NOISY_PARAMETER_TAGS 5.0 → 7.0`、`SENTENCE_TAG_POLLUTION 5.0 → 7.0`、`OCR_HEADING_NOISE_MINOR 3.0 → 5.0`
  - 7 份样例重跑落盘到 `_tmp_review_output/p0_score_backtest_b1/`
  | 样例 | B1 后总分 | 是否通过 | 说明 |
  |------|-----------|----------|------|
  | `SN200_2007-02_中文.pdf` | 86.0 | 是 | 标签噪音类问题被拉低 4 分 |
  | `SN545-1.pdf` | 100.0 | 是 | 仍为 0 问题 100 分 |
  | `SN751.pdf` | 95.0 | 是 | OCR 轻度噪音被拉低 2 分 |
  | `SN775_2009-07_e.pdf` | 100.0 | 是 | 英文高分样例未倒退 |
  | `CB 589-95.pdf` | 100.0 | 是 | 新样例未命中问题 |
  | `SN544-1.pdf` | 100.0 | 是 | 历史高分样例未倒退 |
  | `SN544-2.pdf` | 100.0 | 是 | OCR 样例仍为 0 问题 100 分 |
  - 结论：B1 证明“继续调扣分数字”只能压低已命中的问题，无法影响 `SN545-1 / SN544-1 / SN544-2` 这类“0 issue → 100 分”样例；下一步若还要继续处理评分可信度，重点应转向 **issue 命中条件复核**，而不是继续加重扣分
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
  - reviewer OCR 标题噪音阈值动态化（`src/reviewer.py:420-429`）：`2 ≤ x < 5` → B 级扣 5.0；`≥ 5` → A 级扣 6.0

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

### 本轮盘点新发现的缺陷（2026-04-24）

这一节只登记 2026-04-23 那一轮整理之后又浮现的新问题。已知但已在下一阶段待办里展开的条目不在此重复。

- [ ] **工程卫生红灯**：2026-04-23 本轮 `A → B1 → B2 → C3 → C4 → C5 → D` 的全部成果（10 个 src 文件 / 5 个新测试 / 2 个新 src 模块 `openai_compat.py` `source_guard.py` / 2 个新 plan 文档 / FP 本身的更新 / 5 个 `_tmp_review_output` 子目录）仍整体堆在 working tree 未提交；上次 commit 仍是 4-23 的 `c6306c5`
  - *风险：* 工作量大、跨 7 个阶段的改动堆在一次 diff 里，既难 review 又难回滚，任何误操作都会一次性丢失全部成果
  - *应对方向：* 必须先分 7–8 个按阶段切片的 small commit（B2 / C3 / C4 / C5 / D / FP / 新文件补位）再推送

- [ ] **缺少分数快照回归保护**：当前 19 项测试覆盖"评分契约 / 输出文件合同 / LLM 中文 prompt / OCR 专项命中 / OCR 运行计划"，但没有一项锁定"具体样例的真实得分"
  - *风险：* 若将来某次改动让 `SN544-1` 从 100 悄悄降到 92、`SN200` 从 86 漂到 74，现有测试全部会过，只能靠人肉重跑样例才能发现
  - *应对方向：* 至少把 `SN544-1 = 100 / SN544-2 = 100 / SN200 = 86 / SN751 = 95 / SN545-1 = 100 / SN775 = 100 / CB 589-95 = 100` 钉成 baseline；改动后若超出 ±3 分容差必须先在测试里更新 baseline 才能合入

- [ ] **样本语料仍然窄**：`input/industry_standard/` 绝大多数是 SN5xx 中文系列 + 1 份英文 SN775 + 1 份 CB 589；产品目录 / 图纸密 PDF / 纯表格扫描件 / 原版 DIN/ISO / 德文标准几乎未覆盖
  - *风险：* §0 工作纪律第 3 条（通用性）现在没有数据支撑；正则 / 阈值 / blacklist 其实只在 SN5xx 系列下被验证过
  - *应对方向：* 先定义"类型矩阵"再补样例（至少覆盖：中文标准 / 英文标准 / 德文标准 / 产品目录 / 图纸型 PDF / 纯表格扫描 / 水印污染样本）

- [ ] **OCR 子系统单测深度不足**：本轮 `src/ocr.py` +503 行（懒加载 + 运行计划 + 表格结构识别 + 软超时），对应测试仅 6 条（`test_ocr_runtime` 2 + `test_ocr_table_structure` 2 + `test_pipeline_ocr_summary` 1 + `test_reviewer_ocr_quality` 3）
  - *风险：* 引擎不可用降级 / 批次中途软超时恢复 / 表格结构与 OCR 文本合并边界 / 多页批次对齐失败 等路径没被断言
  - *应对方向：* 在 reviewer 命中条件复核完成后，针对 OCR 子系统再补 4–6 条 white-box 测试

- [ ] **safety-net 触发率缺乏量化**：`text_localization` 已从主动翻译退位为带 warning 的安全网，但现在仍然是"看日志"；没有任何地方把"本次运行触发了 N 次 safety-net"落到 `process_log.json` 或 `review.json`
  - *风险：* B2 的关键 KPI（主路径占比）没有可量化证据；在本轮待办里"压低 warning 触发率"只能靠 grep 日志，不能纳入回归测试
  - *应对方向：* 在 `process_log.json` 增加 `安全网触发次数` 字段；可作为 P1 的前置 1–2 小时收尾

### 下一阶段待办（2026-04-24 更新）

待办按 P0 / P1 / P2 排列。每条都注明 why；避免重复写本节上方"新发现缺陷"里已展开的条目。

**P0 — 工程卫生（最紧迫，先于任何新功能）**

- [ ] 把 2026-04-23 本轮 A→D 的全部改动按阶段切成 7–8 个小 commit 并推送到 `origin/main`
  - *why：* 见上文"新发现的缺陷"第 1 条
  - *粒度建议：* ①B2 LLM prompt + safety-net warning ②C3 reviewer OCR 三条补命中 ③C4 OCR 大样本 + 软超时 + runtime plan ④C5 OCR 表格结构识别 ⑤`openai_compat.py` / `source_guard.py` 模块补位 ⑥FP §7 + §11 同步更新 ⑦`.agent/plans/类名中文化决策.md`；每个 commit 都必须跑通 19 项测试

**P0 — reviewer issue 命中条件复核（比继续调分值更紧迫）**

- [ ] 回溯 `SN545-1 / SN544-1 / SN544-2 / CB 589-95` 为什么都走到"0 问题 → 100 分"
  - *why：* P0 反测 + B1 已证明当前主要瓶颈不再是 `ISSUE_DEDUCTIONS` 数字太轻，而是若 reviewer 子检查没命中 issue，再重的扣分也不会生效；继续调数字收益很低
  - *实施方向：* 逐项回看 `_review_markdown / _review_summary_* / _review_tags / _review_sources / _review_ocr_quality` 的命中门槛，优先补"该命中却没命中"的 issue，再决定是否需要第二轮扣分表校准

**P1 — 分数快照回归保护**

- [ ] 新增 `tests/test_sample_score_baseline.py`，把 7 份样例得分钉成 baseline；容差 ±3 分
  - *why：* 见上文"新发现的缺陷"第 2 条
  - *可选升级：* 每份样例再锁"红线触发 / 评审轮次 / 问题数" 三个维度，比单纯总分更稳

**P1 — 样本语料多样化**

- [ ] 先定义类型矩阵（中文标准 / 英文标准 / 德文标准 / 产品目录 / 图纸型 / 纯表格扫描 / 水印污染），再补样例到 `input/`
  - *why：* 见上文"新发现的缺陷"第 3 条
  - *产物：* 对每类至少放 1 份，跑出 baseline，再决定要不要为某类补"该扣不扣"的 issue

**P1 — 输出内容中文化继续收口到 LLM 主路径**

- [ ] 在真实样例上验证并压低 `text_localization` warning 触发率，让安全网回到"少量兜底"而不是高频参与
  - *why：* B2 已经把 summarizer / tagger 的 LLM prompt 收紧到"中文主干 + 外文括注"并补了 3 条测试，但 `SN775 / SN544-1` 实跑日志里 safety-net 仍高频触发，说明真正的主路径占比还不够高
  - *前置：* 先按"新发现的缺陷"第 5 条把触发次数落到 `process_log.json`，让触发率可被量化

**P1 — OCR 质量债务（继续压）**

- [ ] OCR 后数值型参数抽取精度：过滤日期 / 标准号 / 分类号 / 实施日期等误抽项
- [ ] 扩充标准编号识别：覆盖 GB / CB 等中文标准体系的漏抽变体
- [ ] 继续提高 OCR 表格文本质量与单元格对齐精度：解决"结构框能出来，但单元格文字识别偏弱"的剩余问题
  - *why：* `table_structure_recognition` 已经接入主链，但当前更大的剩余风险已从"完全抽不到表格"转成"抽到了表格结构，但 OCR 文本质量和单元格归属还有提升空间"
- [ ] OCR 子系统补 4–6 条 white-box 测试（见"新发现的缺陷"第 4 条）

**P2 — 数据模型类名层面中文化（需用户决策）**

- [ ] `DocumentData / DocumentProfile / PageRecord / SectionRecord` 类名是否也中文化
  - *why：* 字段层已全中文；但类名改中文会与 Python 惯例、IDE 类型提示、第三方类型检查生态冲突，是否值得做是产品/风格决策，不是工程问题
  - *现状：* 决策文档已产出，见 `.agent/plans/类名中文化决策.md`；当前推荐是"保持现状"，除非后续用户明确要求进入方案二或方案一

**P2 — Web UI 与批处理体验**

- [ ] 历史批次浏览与批次报告回看
- [ ] 浏览器侧端到端验收：任务卡片展示与 API / SSE 字段长期一致性自动化

### 已判为非代码层问题（不立项）

- CB 1010-1990 源文件串档：metadata 红线 cap 59.99，上游人工剔除，不在代码可动空间内
