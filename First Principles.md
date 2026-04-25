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
- **工程护栏**：40 项回归测试（`tests/` 目录；其中 1 项慢速样例基线测试默认 gated，当前锁定 12 份代表样例）覆盖评分契约 / 输出文件合同 / Web 批次字段 / 中文 fallback / LLM 中文 prompt 约束 / reviewer OCR 专项检查 / reviewer 命中条件复核 / OCR 运行计划与 process_log 汇总 / OCR 表格结构识别接入 / OCR white-box 降级分支与表格对齐正反两侧护栏
- **中文输出后处理**：`src/text_localization.py`（正则翻译 + "（原文：X）" 兜底 + warning 可观测性），summarizer / tagger 在章节摘要 / 数值参数 / 规则要求 / 标签主题四处接入；`process_log.json` 已落 `安全网触发次数 / 安全网触发明细 / 提示词签名 / 评审规则签名`

### 近期落地（时间倒序）

**2026-04-24（本轮追加）**

- [x] **2026042401plan 阶段 0–5 第一批整体收口**
  - 阶段 0（工程卫生）：5 个有边界的 commit 已推送 origin/main（`5208ad8 / 0dd652e / 57552cd / 9e75257 / 15372bd`）
  - 阶段 1（分数快照）/ 2（safety-net 可观测）/ 3（reviewer 命中第一轮）/ 4（样本矩阵第一批）/ 5（OCR white-box 第一批）均在 `2b8c262 / fabfa65` 两个提交里继续落地
  - 回归测试从 19 → 27（其中 1 项 slow baseline 默认 gated）
  - 阶段 6（P1/P2）与各阶段"第二批"作为下一阶段待办，不在本轮收口里

- [x] 阶段 1：样例得分快照 baseline 已建立并扩到 12 份代表样例
  - 新增 `tests/test_sample_score_baseline.py`，默认仅在 `SLOW_TESTS=1` 时运行，避免每次单测都全量跑长流程
  - 首批 7 份基线来自 `_tmp_review_output/stage3_score_baseline_refresh/`；阶段 4 又把产品目录 / 扫描标准 / 表格型标准 / 选型指南 / 长文档规范 5 类样例并入同一份 slow baseline
  - 当前 slow baseline 锁定 12 份样例的 `总分 / 红线触发 / 评审轮次 / 问题数`
  - 首批 7 份基线为：
    | 样例 | 总分 | 是否通过 | 红线触发 | 评审轮次 | 问题数 |
    |------|------|----------|----------|----------|--------|
    | `SN544-1.pdf` | 88.0 | 是 | 否 | 1 | 2 |
    | `SN544-2.pdf` | 88.0 | 是 | 否 | 2 | 2 |
    | `SN545-1.pdf` | 81.0 | 否 | 否 | 1 | 3 |
    | `SN775_2009-07_e.pdf` | 88.0 | 是 | 否 | 1 | 2 |
    | `CB 589-95.pdf` | 74.0 | 否 | 是 | 2 | 2 |
    | `SN200_2007-02_中文.pdf` | 74.0 | 否 | 否 | 1 | 4 |
    | `SN751.pdf` | 79.0 | 否 | 否 | 2 | 4 |
  - 阶段 4 追加的 5 份样例为：
    | 样例 | 类型 | 总分 | 是否通过 | 红线触发 | 评审轮次 | 最大扣分项 |
    |------|------|------|----------|----------|----------|------------|
    | `Dixon.2017.pdf` | 产品目录 | 78.0 | 否 | 否 | 1 | 标签存在句子污染（7.0） |
    | `GB 39038-2020 ...pdf` | 扫描标准 | 63.0 | 否 | 否 | 2 | 文件名与正文不一致（10.0） |
    | `CB_T 4196-2011 ...pdf` | 表格型标准 | 74.0 | 否 | 是 | 2 | 表格未消费（8.0） |
    | `CB_Z 281-2011 ...pdf` | 选型指南 | 87.0 | 是 | 否 | 2 | 标签存在句子污染（7.0） |
    | `CB_T 8522-2011 ...pdf` | 长文档规范 | 82.0 | 否 | 否 | 3 | 标签存在句子污染（7.0） |

- [x] 阶段 2：safety-net 触发次数已落到 `process_log.json`
  - `src/text_localization.py`：新增全局计数器与 `reset/get_safety_net_trigger_count()`
  - `src/pipeline.py`：每次 `run_iterative_pipeline()` 开始时重置计数，并把 `安全网触发次数 / 安全网触发明细` 写入 `process_log.json`
  - 新增 `tests/test_pipeline_safety_net_count.py`，验证同一轮运行里 display/tag 两类 safety-net 命中会被正确汇总，且 `安全网触发明细` 四类之和等于总数

- [x] 2026042402plan 阶段 A 第一轮已完成到“分布基线 + 回滚结论”
  - A.4 proxy 5 样例预采样结果：`显示 283 / 来源 158 / 条件 126 / 标签 39`，触发最高的是 `显示`
  - A.4 全量 12 样例前测结果：`显示 357 / 来源 240 / 条件 156 / 标签 58`，总触发 `811`
  - A.5 仅针对 `summarizer` 的显示类标题补了 few-shot，没有同时改 `tagger`
  - A.6 全量 12 样例后测结果：`显示 357 / 来源 239 / 条件 161 / 标签 58`，总触发 `815`
  - 判定：本轮没有达到压降目标，且 `CB_Z 281-2011` 的总分从 `87.0` 掉到 `81.0`，超出 slow baseline `±3` 容差；因此 **prompt 改动已回滚，不进入主线提交**。当前保留的是“按场景拆桶计数 + 分布基线 + 回滚结论”，不是这次 few-shot 本身
  - 说明：`_tmp_safety_net_baseline_pre_full/`、`_tmp_safety_net_baseline_post_full/` 这类目录是 benchmark 聚合产物，只固化顶层 `summary.json` 供前后对照，不等同于 `output/` 正式 14 文件输出合同；正式输出合同仍以主流程 `output/` 目录为准

- [x] 2026042402plan 阶段 B + C + 最终 push 整轮收口（5 commits：`6ed8793 / c72784a / ed3de0f / b87bdec / ac8fc46`）
  - 阶段 B (`ed3de0f`)：`src/parser.py:1347` 新增 `_contains_banned_substring`，在 `_should_reject_parameter_candidate` 仅对**名称字段**升级为 contains 语义，value 侧 `PURE_NUMERIC_VALUE_RE.fullmatch` 逻辑不动；`tests/test_parser_numeric_blacklist.py` 新建 4 条（plan 要求 3 条 + 1 条"value 含标准号不应被名称层拒绝"反向护栏）
  - 阶段 C (`b87bdec`)：`tests/test_ocr_whitebox.py` 新增 `test_build_table_matrix_gracefully_handles_alignment_miss`（2×2 cell_boxes + 越界 ocr_lines → 断言返回全 `""` 矩阵、不抛异常）
  - 计划外补刀 (`ac8fc46`)：反向护栏 `test_build_table_matrix_keeps_nearby_line_with_small_alignment_drift`（cx=94 距右边界 90 仅 4px，仍归属 cell[0,0]）+ parser 额外护栏 + FP benchmark 输出合同澄清
  - 当前 HEAD：`Ran 34 tests in 0.193s / OK (skipped=1)`，`git log origin/main..HEAD` 空
  - **留尾 1（阶段 B scope drift）**：`Commit 4` plan 原文说"只动 tests"，实际同时改了 `src/ocr.py:551-561`（`_match_ocr_line_to_cell` 加 `max(8.0, rect_w*0.25)` tolerance 门槛），否则原 fallback 会把越界点就近塞进 cell，测试无法断言空串。FP 记一笔：**白盒测试先行常发现"生产代码分支不存在对应 contract"，该类 scope drift 是健康信号而不是计划失败，但 plan 编写时应预留"可能推动 src 修正"的弹性**
  - **B.3 已闭合（2026042403plan 阶段 1）**：已补跑基线判定。全量 12 样例 slow baseline 首次运行 1 小时后因 OpenAI 429 重试与后段 OCR 耗时叠加被终止；随后按 plan 的时间受限降级路径单独复测 `GB 39038-2020 ...pdf`，结果为 `63.0` 分、无红线、2 轮、6 个问题，仍在 `expected_score=63.0 ±3` 窗口内。结论：`parser contains` 升级没有显著拉升该样例分数，`tests/test_sample_score_baseline.py` 的 baseline 保持不变。结构层教训保留：**"if condition → do X" 型 plan 条款应改成"run condition check → record result → act"，强制插入测量步骤，不留"没跑所以没更新"的黑洞**
  - **OCR 白盒边界已继续补齐（2026042403plan 阶段 2）**：`_build_table_matrix_from_cells` 已覆盖"明显越界 → 空串"、"轻微漂移 → 就近归属"、`cell_boxes=[]`、`ocr_lines=[]`、1×N 退化形状五类路径；N×1 可后续按需补充，但不再属于本轮明确缺口

- [x] 阶段 3：reviewer 命中条件复核第一轮已完成
  - `src/reviewer.py`：`_review_summary_structure()` 现在会识别“全文摘要只有计数模板句 + 章节摘要大面积低信息占位句”的假摘要；`_is_suspicious_parameter_tag()` 现在会识别 `verwendet für DN` 这类外语短句型参数标签污染
  - 新增 `tests/test_reviewer_hit_conditions.py` 两项测试，分别钉住“低信息章节摘要占位”与“外语短句参数标签”两类漏检
  - 小样本实跑结果：
    - `SN545-1.pdf`：`100.0 -> 81.0`，从“0 问题 100 分”回落为“不通过”
    - `SN544-1.pdf`：`100.0 -> 88.0`，仍通过，但不再是虚高满分
    - `SN775_2009-07_e.pdf`：`100.0 -> 88.0`，英文样例未倒退到不通过
  - 结论：当前主要问题已经不再是“扣分数字过轻”，而是“低信息占位摘要/标签此前没被 reviewer 命中”

- [x] 阶段 4：扩样本矩阵第一批已纳入 slow baseline
  - 以 `input/product_sample/`、`input/scanned_version/` 和 `input/industry_standard/Shipbuilding_Industry_Standards/` 为样本池，补进了 5 份代表样例：产品目录、扫描标准、表格型标准、选型指南、长文档规范
  - 这 5 份样例的实跑结果已经写回 `tests/test_sample_score_baseline.py`，后续 reviewer / OCR / prompt 调整如果引起得分飘移，会先被 slow baseline 卡住
  - 当前第一批矩阵已覆盖：中文标准 / 英文标准 / 产品目录 / 扫描标准 / 表格型标准 / 选型指南 / 长文档规范
  - 仍待补的空位：德文原版、图纸型 PDF、水印污染样本

- [x] 阶段 5：OCR white-box 测试第一批已补齐
  - 新增 `tests/test_ocr_whitebox.py` 4 项测试，覆盖：
    - `get_table_structure_engine()` 导入失败时降级为 `None`
    - `run_ocr_on_pages()` 在 OCR 引擎不可用时返回空结果而不抛异常
    - `run_table_structure_on_pages()` 在软超时后保留已完成页的部分结果
    - `run_table_structure_on_pages()` 在文本 OCR 引擎缺失时优雅降级
  - 当前 OCR 相关测试已从“只覆盖 happy path”扩展到“降级 / 超时 / 部分成功”路径

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

- [x] **工程卫生红灯已解除**：2026-04-23 留下的跨阶段大 diff 已在历史提交 `5208ad8 / 0dd652e / 57552cd / 9e75257 / 15372bd` 收口；2026-04-24 本轮新增的 reviewer 命中条件复核、safety-net 可观测性、score baseline 扩容与 OCR white-box 也已继续拆分提交，不再以 working tree 形式堆积
  - *结果：* 当前仓库已经恢复到“改动有提交边界、可 review、可回滚”的正常工程卫生状态

- [x] **样例得分快照回归保护已补齐并完成第一批扩容**：`tests/test_sample_score_baseline.py` 已建立 12 份样例的慢速 baseline，锁定 `总分 / 红线触发 / 评审轮次 / 问题数`
  - *当前剩余：* 后续若继续扩样本类型，需要把德文原版 / 图纸型 PDF / 水印污染样本继续纳入 baseline，而不是只停留在当前第一批矩阵

- [x] **样本类型第一批扩容已纳入 baseline**：`product_sample/`、`scanned_version/` 和 `industry_standard/Shipbuilding_Industry_Standards/` 中的代表样例已进入 slow baseline
  - *当前剩余：* §0 工作纪律第 3 条（通用性）还缺德文原版 / 图纸型 PDF / 水印污染样本三类空位；下一步应围绕这三类继续补矩阵，而不是重复增加同类型 SN5xx 样例

- [x] **OCR 子系统 white-box 第一批已补齐**：当前 OCR 相关测试已覆盖运行计划、软超时、表格结构接入、reviewer OCR 专项命中，以及引擎不可用降级 / 表格识别软超时 / 文本引擎缺失等 white-box 分支
  - *补充：* OCR 表格对齐现在已经同时有“明显错位返回空矩阵”和“轻微漂移仍就近归属单元格”两侧护栏，不再只覆盖一边
  - *当前剩余：* 还没有把“多页批次对齐失败 / OCR 表格矩阵边界失真 / 真扫描件长批次性能”变成更细的断言

- [x] **safety-net 触发次数已量化**：`process_log.json` 已新增 `安全网触发次数`，并有 `tests/test_pipeline_safety_net_count.py` 回归保护
  - *当前剩余：* 真正的下一步已经从“先把次数记下来”变成“基于这个计数继续压低 safety-net 高频参与”

### 下一阶段待办（2026-04-24 更新）

待办按 P0 / P1 / P2 排列。每条都注明 why；避免重复写本节上方"新发现缺陷"里已展开的条目。

**P0 — 工程卫生**

- [x] 2026-04-23～2026-04-24 的新增改动已经收口到带边界的提交，不再以跨阶段 working tree 大 diff 形式存在
  - *结果：* 后续可以在干净基线上继续做 reviewer 第二轮复核，而不是先花时间抢救工程卫生

**P0 — reviewer issue 命中条件复核（第二轮，扩样本后继续做）**

- [x] 第一轮已完成：`SN545-1 / SN544-1 / SN544-2 / CB 589-95 / SN200 / SN751 / SN775` 不再整体停留在"0 问题 → 100 分"
  - *结果：* 当前 reviewer 已能稳定命中“低信息占位章节摘要 / 模板化全文摘要 / 外语短句型参数标签噪音”等此前漏检的问题
- [ ] 第二轮在扩样本矩阵上继续复核命中条件
  - *why：* 第一轮收紧先在首批 7 份样例上生效，阶段 4 又把 `product_sample / scanned_version / Shipbuilding_Industry_Standards` 的 5 份代表样例纳入了 baseline；下一步要看这些命中门槛在扩样本矩阵上是否仍然成立，而不是再次回到 SN5xx 过拟合
  - *实施方向：* 先为每类样本选 1 份代表件，再逐项回看 `_review_markdown / _review_summary_* / _review_tags / _review_sources / _review_ocr_quality` 的命中门槛

**P1 — 分数快照回归保护**

- [x] `tests/test_sample_score_baseline.py` 已建立 12 份样例 baseline，容差 ±3 分，并同步锁定 `红线触发 / 评审轮次 / 问题数`
  - *下一步：* 继续把德文原版 / 图纸型 PDF / 水印污染样本纳入 baseline，而不是只停留在当前第一批矩阵

**P1 — 样本语料多样化**

- [ ] 在第一批矩阵基础上继续补齐剩余空位：德文标准 / 图纸型 PDF / 水印污染样本
  - *why：* 当前 slow baseline 已覆盖中文标准 / 英文标准 / 产品目录 / 扫描标准 / 表格型标准 / 选型指南 / 长文档规范，但 §0 工作纪律第 3 条（通用性）要站稳，还需要把剩余三类高风险样本补齐
  - *产物：* 对每类至少放 1 份，跑出 baseline，再决定要不要为某类补"该扣不扣"的 issue

**P1 — 输出内容中文化继续收口到 LLM 主路径**

- [ ] 在真实样例上验证并压低 `text_localization` warning 触发率，让安全网回到"少量兜底"而不是高频参与
  - *why：* B2 已经把 summarizer / tagger 的 LLM prompt 收紧到"中文主干 + 外文括注"并补了 3 条测试，但 `SN775 / SN544-1` 实跑日志里 safety-net 仍高频触发，说明真正的主路径占比还不够高
  - *现状：* `process_log.json` 已经有 `安全网触发次数 / 安全网触发明细`；2026042402plan 阶段 A 第一轮已试过“只收紧 summarizer 显示类 few-shot”，但 12 样例总触发 `811 → 815` 且 `CB_Z 281-2011` 超出 ±3 容差，因此已回滚。下一轮应继续细分 `显示` 场景里的子类型（章节标题 / 表格标题 / 目录短语），而不是再做一轮笼统 few-shot

**P1 — OCR 质量债务（继续压）**

- [ ] OCR 后数值型参数抽取精度：过滤日期 / 标准号 / 分类号 / 实施日期等误抽项
- [ ] 扩充标准编号识别：覆盖 GB / CB 等中文标准体系的漏抽变体
- [ ] 继续提高 OCR 表格文本质量与单元格对齐精度：解决"结构框能出来，但单元格文字识别偏弱"的剩余问题
  - *why：* `table_structure_recognition` 已经接入主链，但当前更大的剩余风险已从"完全抽不到表格"转成"抽到了表格结构，但 OCR 文本质量和单元格归属还有提升空间"
- [x] OCR 子系统继续补更细的 white-box 测试：`_build_table_matrix_from_cells` 已补 `cell_boxes=[]`、`ocr_lines=[]`、1×N 退化形状三条边界断言
  - *当前剩余：* 多页批次对齐失败 / N×1 退化形状 / OCR 表格矩阵边界失真 / 真扫描件长批次性能仍可作为后续更细测试继续补

**P1 — 整体流程再审视（2026042401plan 收口后浮出的结构层改进）**

这一块不是单点缺陷，而是把 plan 收口后再通盘看一眼时，从流程/工程化维度新发现的下一圈改进机会。这些条目都还没开始做，why 写清楚避免与上面 P0 / P1 条目重复。

- [x] **prompt / reviewer 规则版本化签名**
  - *结果：* 新增 `src/config_signatures.py`，基于 `summarizer/tagger` system prompt 和 `ISSUE_DEDUCTIONS` 生成 8-hex 签名；`process_log.json` 已新增 `提示词签名 / 评审规则签名`，用于 slow baseline 飘移时快速判断是提示词、评审规则还是输入样本变化
  - *边界：* 当前 reviewer 签名只覆盖 `ISSUE_DEDUCTIONS`，不覆盖 `_review_*` 命中函数体；若后续 reviewer 命中逻辑频繁变化，再单独扩展 `评审代码签名`

- [ ] **baseline 真值产物入 git**
  - *why：* `tests/test_sample_score_baseline.py` 的期望值是硬编码数字，真值来源是本地 `_tmp_review_output/`，但该目录已 gitignore；异地重建环境后无法从真值产物复算 baseline，只能相信 commit 当时人的结果
  - *方向：* `tests/fixtures/baseline_snapshots/` 提交固化的 12 份 `review.json` 关键片段，slow baseline 同时比对"数字"与"issue 列表结构"两层

- [ ] **评审轮次终止条件非机械化**
  - *why：* 当前固定 3 轮；第 2 轮已通过仍会跑第 3 轮，浪费 LLM / OCR；若第 3 轮分数反而下降仍以最后一轮为准；slow baseline 全量耗时不小，其中相当一部分属无效迭代
  - *方向：* 评审循环增加"本轮得分不升反降则回退到上一轮"机制，并在早轮已满足通过条件时短路

- [x] **safety-net 触发次数拆场景**
  - *结果：* `process_log.json` 已新增 `安全网触发明细 = {"显示": X, "来源": Y, "条件": Z, "标签": W}`，`tests/test_pipeline_safety_net_count` 也已同步扩展
  - *当前剩余：* 第一轮基于该拆桶结果做的 `summarizer` 显示类 few-shot 收紧没有带来压降（`811 → 815`，未采纳），下一步应继续细分 `显示` 类内部模式再做更窄的优化

- [ ] **batch_report 汇总指标**
  - *why：* `output/批次/<batch_id>/batch_report.json` 只列了每份成功/失败，没有"本批共 N 份 / K 份通过 / 红线触发率 / 最常见扣分项 Top3"，Web UI 历史回看只能逐份点开
  - *方向：* `batch_report.json` 增加 `汇总` 字段，并作为后续 Web UI 历史批次页面的前置

- [ ] **OCR 置信度下沉到下游**
  - *why：* OCR 页级评估只给"合格 / 边缘可用 / 不合格"三态；reviewer 和 fixer 看不到每段文字 / 每个单元格的原始置信度，"结构框对了但单元格字识别错"只能靠启发式后检，没法凭置信度直接命中
  - *方向：* OCR 结果保留 per-token confidence，写入独立 `OCR置信度.json`（属于扩展输出，不进必需 14 件）

- [ ] **plan 条件句的"测量—决策—记录"闭环**
  - *why：* 2026042402plan B.3 写的是"若 `GB 39038-2020` 回升到 > 65 分则更新 baseline"，阶段 B 落地后没跑慢速基线就提交，baseline 既没更新、FP 也没追加"未更新 + 为什么"的记录；事后看不出是"真没回升"还是"没测过"
  - *方向：* 任何 plan 条款一旦带 "if X then Y" 结构，必须 1) 显式排 "run X-check" 子步骤，2) 在 FP §11 强制追加一行结果（即使是"未触发"也要写），避免条件句变成黑洞

- [ ] **plan-vs-impl 的 scope drift 弹性条款**
  - *why：* 2026042402plan `Commit 4` 原文"只动 tests"，实际同时改了 `src/ocr.py:551-561` 加 tolerance 门槛——这是白盒测试先行在发现"生产代码分支缺对应 contract"后被动推出的健康修正，不是 plan 失败
  - *方向：* 白盒测试先行的 plan 条目显式写"若发现 src 缺失对应分支，允许在同一 commit 内同步修正生产代码，但须在 commit message 记明 drift 原因"，并保留"rollback scope 仅限 src 部分"作为兜底

**P2 — 数据模型类名层面中文化（需用户决策）**

- [ ] `DocumentData / DocumentProfile / PageRecord / SectionRecord` 类名是否也中文化
  - *why：* 字段层已全中文；但类名改中文会与 Python 惯例、IDE 类型提示、第三方类型检查生态冲突，是否值得做是产品/风格决策，不是工程问题
  - *现状：* 决策文档已产出，见 `.agent/plans/类名中文化决策.md`；当前推荐是"保持现状"，除非后续用户明确要求进入方案二或方案一

**P2 — Web UI 与批处理体验**

- [ ] 历史批次浏览与批次报告回看
- [ ] 浏览器侧端到端验收：任务卡片展示与 API / SSE 字段长期一致性自动化

### 已判为非代码层问题（不立项）

- CB 1010-1990 源文件串档：metadata 红线 cap 59.99，上游人工剔除，不在代码可动空间内
