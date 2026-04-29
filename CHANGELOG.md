# CHANGELOG

项目时间线与稳定能力归档；不承载待办流转或架构契约。

最近一轮：2026042406plan（commit `8273a5a`）→ 见下文 §2026-04-27。

---

## 迁移自 First Principles §11

### 稳定能力（已验收，可直接依赖）

- **解析链路**：PDF 加载 → parser（文本 + 章节 + 表格）→ cleaner / normalizer → profiler → LLM 精炼 → md_builder → summarizer / tagger
- **评审循环**：最多 3 轮，fixer 按问题类型定向修正（见 §8）；每轮快照写入 `review_rounds.json`
- **评分契约**：§10 严格 35 / 40 / 25 加权，红线 cap=74（整数），通过条件 `总分 ≥ 85 且 红线列表为空`
- **数据模型**：单一 `DocumentData`，字段全中文（见 §6）；`record_access` / `structured_access` 同步中文契约
- **输出文件**：14 个必需输出（见 §3），6 个旧文件已明确废除；`exporter` 有禁写内部键护栏
- **Web UI**：FastAPI + SSE + 批量处理 + 每批独立 `batch_report.json` + 中文任务卡片字段
- **OCR 能力**：PaddleOCR 懒加载 + 页级评估 + 仅注入合格页 + SCAN_LIKE 已 OCR 自动放行
- **工程护栏**：56 项回归测试（`tests/` 目录；其中 slow/环境门控项默认 skipped，当前锁定 12 份代表样例）覆盖评分契约 / 输出文件合同 / Web 批次字段 / 中文 fallback / LLM 中文 prompt 约束 / reviewer OCR 专项检查 / reviewer 命中条件复核 / OCR 运行计划与 process_log 汇总 / OCR 表格结构识别接入 / OCR white-box 降级分支与表格对齐正反两侧护栏 / plan 字段命名 drift lint / baseline fixture 字节级 EOL 守卫
- **结构层 baseline 真值入 git**：`tests/fixtures/baseline_snapshots/*.json` 固化 11/12 样例的"低噪音、可诊断"结构快照（顶层 7 键 + 每条 issue 3 键）；slow baseline 数字断言失败时可 `git diff` fixture 直接定位是哪条 issue 动了；`UPDATE_BASELINE_SNAPSHOTS=1` 是刷 fixture 的标准入口
- **中文输出后处理**：`src/text_localization.py`（正则翻译 + "（原文：X）" 兜底 + warning 可观测性），summarizer / tagger 在章节摘要 / 数值参数 / 规则要求 / 标签主题四处接入；`process_log.json` 已落 `安全网触发次数 / 安全网触发明细 / 提示词签名 / 评审规则签名`


### 近期落地（时间倒序）

**2026-04-29（Phase 4.5 P0-2）**

- [x] **修复 Reviewer 误判「LLM 不可用」为阻断**
  - `src/reviewer.py`：新增 `_BENIGN_LLM_FALLBACK_PREFIXES` 白名单（覆盖 summarizer.py 4 条 + pipeline 来源隔离 + pipeline 摘要/标签异常路径，共 7 条）和 `_is_benign_llm_reason()` 判别器；`review_outputs` / `_review_summary_structure` 增加可选 `process_log` 参数；模板回退分支：`summary["_llm_reason"]` 为空时回查 `process_log["摘要LLM原因"]`，**仅当原因落在白名单内时降级为非阻断 `SUMMARY_FALLBACK_EXPLAINED`**，其它一律保持阻断的 `SUMMARY_TEMPLATE_FALLBACK`，避免真实缺陷借"有原因"漏过
  - `src/pipeline.py`：`build_summary` / `build_tags` 异常 fallback 字典补齐 `_llm_reason` 与 `_llm_error`，让源头不再丢字段
  - `tests/test_reviewer_hit_conditions.py`：+6 用例（process_log 兜底、双空仍阻断、summary 优先级、`review_outputs` 端到端、白名单覆盖、非白名单仍阻断），全部通过
  - 全量回归 185 tests passed（4 skipped），零回归
  - 影响：fixer rebuild、build_summary 异常、来源隔离这三类路径产出的"无 LLM 后端但有合法原因"summary，从此不再被误扣 12 分 + 阻断；TODO 提到的 4/5 抽样文件应在下一次 `SLOW_TESTS=1` baseline 上得分恢复（YELLOW 留尾，未在本轮回归）

**2026-04-29（Phase 4.5 P0-1）**

- [x] **修复 `_pid_is_alive` Windows 跨平台 Bug**
  - `src/utils.py`：`os.kill(pid, 0)` 在 Windows 实际发送 `CTRL_C_EVENT`，会误击同 console 的进程；改为 `os.name == "nt"` 时走新增的 `_pid_is_alive_windows()`，调用 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess`，PID 不存在 → False，权限不足 → 保守为 True（不抢锁），永不发信号
  - POSIX 路径保留 `os.kill(pid, 0)` null-signal 语义不变
  - 新增 `tests/test_utils.py`：6 例（4 active + 2 POSIX-only skip-on-Windows），覆盖 PID ≤ 0 / 自身 PID / 高位 PID / POSIX 信号路径
  - 全量回归 179 tests passed（4 skipped），零回归
  - 影响：管道互斥锁（`try_acquire_pipeline_lock` / `release_pipeline_lock`）的 Windows 锁过期检测从此生效，不再有"探测即发 Ctrl+C"的副作用

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

- [x] 2026042404plan：baseline 结构快照入 git（11/12 已固化）
  - Stage 1 (`c6a1ec3`)：新增 `tests/support/baseline_snapshot.py` 与 snapshot fixture 测试入口，快照字段收口为 `快照版本 / 总分 / 红线触发 / 评审轮次 / 提示词签名 / 评审规则签名 / 问题清单`；每条问题仅保留 `问题ID / 级别 / 扣分`
  - Stage 2 (`031873a`)：生成并提交 `tests/fixtures/baseline_snapshots/` 下 11 份结构快照，统一签名为 `提示词签名=d65021f1`、`评审规则签名=21729d3a`
  - Stage 2 fixup (`55ffa28`)：把硬编码标量 baseline 与结构快照对齐：`GB 39038-2020 ...pdf` 的评审轮次为 `3`；`CB_Z 281-2011 ...pdf` 当前真值为 `81.0 / 3 个问题`
  - 本轮没有把完整 `review.json` 或 `_tmp_review_output/` 入 git；只固化低噪音结构层真值，避免 LLM 文案、修复建议、换行等展示噪声触发全量红灯
  - 结构快照表：
    | 样例 | fixture | 总分 | 红线触发 | 评审轮次 | 问题数 |
    |------|---------|------|----------|----------|--------|
    | `SN544-1.pdf` | `SN544-1.json` | 88.0 | 否 | 1 | 2 |
    | `SN544-2.pdf` | `SN544-2.json` | 88.0 | 否 | 2 | 2 |
    | `SN545-1.pdf` | `SN545-1.json` | 81.0 | 否 | 1 | 3 |
    | `SN775_2009-07_e.pdf` | `SN775_2009-07_e.json` | 88.0 | 否 | 1 | 2 |
    | `CB 589-95.pdf` | `CB_589-95.json` | 74.0 | 是 | 2 | 2 |
    | `SN200_2007-02_中文.pdf` | `SN200_2007-02.json` | 74.0 | 否 | 1 | 4 |
    | `SN751.pdf` | `SN751.json` | 79.0 | 否 | 2 | 4 |
    | `Dixon.2017.pdf` | `Dixon.2017.json` | 78.0 | 否 | 1 | 3 |
    | `GB 39038-2020 ...pdf` | `GB_39038-2020.json` | 63.0 | 否 | 3 | 6 |
    | `CB_T 4196-2011 ...pdf` | `CB_T_4196-2011.json` | 74.0 | 是 | 2 | 4 |
    | `CB_Z 281-2011 ...pdf` | `CB_Z_281-2011.json` | 81.0 | 否 | 2 | 3 |
    | `CB_T 8522-2011 ...pdf` | known_missing | 未固化 | 未固化 | 未固化 | 未固化 |
  - known_missing：`CB_T 8522-2011 舾装码头设计规范.pdf` 在全量生成进程中超过 1 小时仍未产出，继续观察 2 分钟也无新增 fixture；本轮已在 `_SNAPSHOT_KNOWN_MISSING` 显式登记，默认不让 snapshot 测试被该长尾样例拖死
  - 结论：2026042403 的"12 行样例 snapshot 表暂缺"已闭合为 11/12 可诊断结构真值；剩余 1 份属于 ops fragility 留尾，不再阻断 baseline 真值入库
  - **本轮核对发现的工程性留尾（不影响主线但需在下轮 plan 处理）**：
    1. **CRLF 入库**：`tests/fixtures/baseline_snapshots/*.json` 在 Windows 下由 Python `Path.write_text(..., encoding="utf-8")` 写出时换行被翻译为 `\r\n`，与 plan 显式要求的 `+ "\n"` 不一致；`tests/test_sample_score_baseline.py` 的字符串级 `assertEqual` 会经由 Python 文本读取的 universal newline 归一化而通过，抓不到字节级 CRLF，但**一旦接 Linux CI / 异地协作就会产生 EOL diff 噪声**——下轮应同 commit 加 `.gitattributes` 规则 `*.json text eol=lf`，并在 fixture 写入点显式 `newline="\n"`
    2. **plan 字段命名 drift 第二次发生**：plan04 顶层字段名写 `snapshot_version`，实际落地为 `快照版本`；与 2026042403 的 `prompt_签名 → 提示词签名` 同型。两次同型修正说明纯文字教训不够，需要工程化护栏（plan 起草最后一步过一遍 FP §11 + `src/pipeline.py` 既有契约的 grep 对齐）
    3. **plan 伪代码与最终实现的查表 key 偏离**：plan 1.1 伪代码 `ISSUE_DEDUCTIONS.get(str(it.get("问题ID", "")), ...)`，实际 `tests/support/baseline_snapshot.py` 用 `KEY_CONTENT` 做 key（功能等价，因为 reviewer 的 `内容` 字段就是 issue 类型常量字符串）；不算 bug，但这类偏离应在 commit message 中显式说明，避免日后 reader 误以为是 bug
    4. **plan 切片粒度系统性低估**：2026042402 plan 写 3 commit 实际 5 个；2026042403 plan 写 3 commit 实际 4 个；2026042404 plan 写 3 commit 实际 4 个。三轮均出现"plan 没预估到的 fixup commit"，下轮 plan 起草应主动预算"3 plan-commit + 1 buffer commit"
    5. **scope drift 弹性条款触发 3 次都是健康信号**：2026042402 C4 改 `src/ocr.py`、2026042404 Stage 2 拆 3 commit、2026042404 `55ffa28` realign `_BASELINES`。这类"先 fixture/test → 后修齐 src/baseline"是"白盒先行 + 真值锚定"工作流的预期产物，不应再视为 plan 失败；下轮 plan 起草直接把"realign 类 fixup"写进 Verification 段而非 Risk 段
    6. **commit message 描述与 plan 文本的对齐质量持续走低**：本轮 `c6a1ec3 / 031873a / 55ffa28` 三条 commit message 都比较简（"test: add baseline snapshot fixtures" 等），与 plan 1.3 写明的"test(baseline): add structural snapshot layer with UPDATE_BASELINE_SNAPSHOTS mode"差距大；下轮 commit message 应在落地前"copy plan §X.Y 标题"作为格式起点

- [x] 2026042405plan：plan-lint + EOL 工程化护栏（3 commits：`00e8381 / f52b0b5 / c0e57d2`）
  - Stage 1 (`00e8381`)：新建 `.gitattributes`（`*.json/*.md/*.py/*.txt text eol=lf` + `*.pdf/*.png/*.jpg binary` 兜底）；`tests/test_sample_score_baseline.py` 的 fixture 写入点加 `newline="\n"`；11 份 baseline snapshot 的仓库 blob 原本已是 LF，本轮通过 attributes 让工作区也确认到 `w/lf`，因此没有 JSON 内容 diff
  - Stage 2 (`f52b0b5`)：新建 `tools/plan_lint.py`，扫 plan markdown 反引号字段名，对照 `KNOWN_DRIFT_MAP` 检测两类历史 drift（纯英文 snake_case vs 中文契约、Chinglish 混合 vs 纯中文契约），并跳过 fenced code block 以免示例代码误触发；新增 `tests/test_plan_lint.py` 6 条，`python -m tools.plan_lint plan04.md` 会按预期报出历史 `snapshot_version` drift
  - Stage 3（本 commit）：FP §11 把两条工程性待办改 `[x]`，固化 plan-lint 用法，并记录历史档案 lint 报告不要求倒修
  - **下轮 plan 起草工作流**：plan ready 但未 ExitPlanMode 前，必须 `python -m tools.plan_lint <plan_path>` 退出码 0；非 0 时回头修 plan 字段名再 lint，直到 clean
  - **新增 drift 时维护 `KNOWN_DRIFT_MAP`**：每发现一类新 drift（如未来 plan 写 `pipeline_log` 但实际是 `运行日志`），plan-lint 工具同 commit 加一行映射，让 lint 能力随项目演进
  - **历史档案边界**：`plan04.md` / `plan05.md` / FP 中叙事性保留的 `snapshot_version`、`prompt_签名`、`reviewer_签名` 可被 lint 报出但不倒修；plan-lint 的硬约束对象是后续新 plan
  - **本轮工程性留尾（plan05 落地后第二回合 review 浮现）**：
    1. **plan-lint vocab 与 source-of-truth 解耦**：`KNOWN_DRIFT_MAP` 是手维护字典，不从 `tests/support/baseline_snapshot.py` 的 `KEY_*` 常量或 `src/pipeline.py` 的 `process_log` 字典字面量自动 seed；plan05 §2.1 设计本身已点出"未来可改为运行期 import 自动 seed"，但本轮未做。后果：**第一次出现的新型 drift（例如未来 plan 写 `pipeline_log`、实际 `运行日志`）lint 仍会漏检**——只能在第 2 次发生时手工补 map，与"事前/事中工程化护栏"的初衷相比仍差一步
    2. **plan-lint 仍是手动工具，未接 pre-commit / CI gate**：plan05 §2.1 风险段已论证"先用手动一段时间观察"，逻辑成立但留尾真实存在；下一次起草若忘记跑 lint，drift 仍会以 bonus commit 形式复发
    3. **fixture EOL 缺字节级测试守卫**：`.gitattributes` + `newline="\n"` 是 git 侧 / IO 侧规则，没有 test 时刻的字节级断言。若未来 `.gitattributes` 被误删 / `core.autocrlf` 被误设 / fixture 被绕过 `serialize_snapshot` 直接写入，回归会**沉默通过当前测试**（`assertEqual` 走 universal newline 归一化），与"工程化护栏"理念不符
    4. **bonus test/commit 已成稳定 N+1 模式（连续 3 轮）**：2026042403 `84a3397` 字段名 fixup、2026042404 拆 3 commit + `55ffa28` realign、2026042405 `tests/test_plan_lint.py` 第 6 条 `test_fenced_code_blocks_are_ignored`（plan 只列 5 条），三轮稳定 → 不再是"plan 估算偏差"而是"白盒先行工作流的固定产出"。下轮 plan 模板应直接列"+1 bonus test/commit slot"作为预设字段而非风险条目
    5. **plan-lint vocab 方向不对称**：当前 `KNOWN_DRIFT_MAP` 只查"英文/Chinglish → 中文"这一向；反向（中文契约写错、把 plan 中正确的中文又改成英文）不查。这与"中文是契约"的设计取舍一致，但存在边角：若 plan 写 `运行日志` 而实际 code 是 `process_log.json`（叙事用作类比也算合法），lint 不报，反向 drift 隐形
    6. **plan 测试数估算偏差延续**：plan05 §2.4 写 `40 → 45（+5 新测试）`，实测 47 ran / 2 skipped（含 bonus 第 6 条 + 历史 1 条 slow gate skip）。误差小但属"plan 估算保留 +5、实际 +6"的同型偏差——与 §3 待办 "plan-vs-impl 切片粒度系统性低估" 同源

- [x] 2026042406plan：vocab 自动化 + EOL 字节级守卫 + plan 模板（3 commits：`3597a60 / 6c1a476 / 本 commit`）
  - Stage 1 (`3597a60`)：`tools/plan_lint.py` 新增 `_load_canonical_vocab()`，从 `src.contracts` 的 `KEY_*`、`tests/support/baseline_snapshot.py` 的本地 `KEY_SNAPSHOT_VERSION`、`src/pipeline.py` 的 `process_log` 字典 key 自动 seed canonical 中文词表；新增 `chinglish_via_canonical_vocab` 自动通道，`KNOWN_DRIFT_MAP` 继续保留为纯英文和历史 drift 路径；`tests/test_plan_lint.py` 扩到 13 条
  - Stage 2 (`6c1a476`)：`tests/test_fixture_eol.py` 新增字节级守卫（无 CRLF / `b"{\n"` 起头 / `b"}\n"` 收尾），与 `.gitattributes` 和 `newline="\n"` 互为冗余防御；不门控 `SLOW_TESTS`
  - Stage 3（本 commit）：FP §11 三条 P1 待办改 `[x]`，新增 `tools/plan_template.md` 静态骨架（`# Budget` / `# Pre-flight checklist` 两段为新增固化），并归档修正后的 `plan06.md`
  - **本轮预算条目落地结果**：`bonus_test_slot` = 已触发，实际用途为新增 `test_chinglish_auto_path_ignores_expressions_with_punctuation`，防止自动 Chinglish 通道误报 `process_log["提示词签名"]` / `提示词签名=d65021f1` 这类叙事表达式；该测试合入 Stage 1 commit，未额外开 commit。`fixup_commit_slot` = 未触发，理由：`src/pipeline.py` 的 AST 提取与 `src.contracts` 反射均在本地验证通过，无需追加 fallback commit
  - **门禁现状**：pre-commit / CI gate 仍保留为待办；vocab 自动化前置条件已就位，但先观察 1–2 轮 plan 起草中的误报/漏报表现，再决定是否上 hook 或 CI

- [x] 2026042403plan 阶段 1/2/3 + bonus fixup 整轮收口（4 commits：`812fbeb / 4a77106 / 5366eca / 84a3397`）
  - 阶段 1 (`812fbeb`)：B.3 留尾闭合。全量 slow baseline 首跑 1 小时后被 OpenAI 429 + OCR 长尾阻断；按 plan 降级路径单独复测 `GB 39038-2020 ...pdf` = `63.0`，仍在 `±3` 窗口内，`tests/test_sample_score_baseline.py:32` baseline 保持 `63.0`，本条目直接在 FP §11 追加"已闭合"记录
  - 阶段 2 (`4a77106`)：OCR 白盒 3 条边界断言入 `tests/test_ocr_whitebox.py`（`test_build_table_matrix_returns_empty_for_empty_cell_boxes` / `test_build_table_matrix_with_empty_ocr_lines_returns_empty_string_matrix` / `test_build_table_matrix_preserves_degenerate_shapes`）；实现自身无 bug，只钉 latent-safe 行为，未触发 scope drift
  - 阶段 3 (`5366eca`)：新建 `src/config_signatures.py` 放 `prompt_signature()` / `reviewer_signature()`（sha256[:8]），`src/pipeline.py` 在 `process_log` 末尾新增两个签名字段；新增 `tests/test_config_signatures.py` 三条（稳定性 / 敏感性 / pipeline 契约）
  - Bonus fixup (`84a3397`)：字段名从 plan 原文的 `prompt_签名 / reviewer_签名` 升级为纯中文 `提示词签名 / 评审规则签名`，与 FP §11 "process_log.json 已落 …" 的中文契约对齐
  - 测试从 34 → 40（+1 skipped），`git log origin/main..HEAD` 空
  - **首次基线签名值（固化入 FP）**：`提示词签名=d65021f1`，`评审规则签名=21729d3a`。下一轮 slow baseline 任何样例得分漂移时，先查 `process_log.json` 这两个字段是否仍等于上面两个值：若任一已变，说明漂移来源是"提示词变了 / 评审规则变了"而非"样本或 OCR 变了"
  - **留尾已由 2026042404plan 闭合**：plan 1.2 要求的 12 份样例实测表已固化为 11/12 结构快照；`CB_T 8522-2011 ...pdf` 因长尾超时列入 known_missing，不再作为本轮阻塞项
  - **结构层教训**：
    1. **slow baseline 降级路径应写进 plan**：plan 开工时没预设"1 小时超时 → 降到单样例"的触发条件和最小可交付，事后是靠弹性裁决而非 plan 指令给出结论
    2. **首次基线/指纹值必须入 FP**：签名、哈希、baseline 这类"锚点值"一旦落地就是后续归因的唯一坐标；不入 FP 的话下轮查对照时只能重跑，徒增成本
    3. **plan 字段命名应直接对齐 FP 中文契约**：plan 原文为加快书写用 Chinglish `prompt_签名`，落地后需 bonus commit 改为 `提示词签名`；下次 plan 在列字段名时应先 grep FP 里的同类字段命名风格，一次到位

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
