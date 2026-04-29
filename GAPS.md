# GAPS — TODO.md 之外的项目差距

2026-04-29 全量审计发现，不重复 TODO.md / CHANGELOG.md / LESSONS.md 已有内容。

---

## 一、严重：跨平台 Bug

### `_pid_is_alive` 在 Windows 上是破坏性的

[src/utils.py:84-92](src/utils.py#L84-L92)

`os.kill(pid, 0)` 在 Unix 上用来探测进程是否存在（信号 0 是 null signal），但在 Windows 上会**真的发送 Ctrl+C** 给目标进程。

**影响：**
- 管道互斥锁（`try_acquire_pipeline_lock` / `release_pipeline_lock`）在 Windows 下不可靠 — 锁过期检测无效
- 可能误杀正在运行的管道进程（发送 Ctrl+C 给同 console 的所有进程）

**修复方向：** Windows 上用 `psutil.pid_exists(pid)` 或 `ctypes.windll.kernel32.OpenProcess(...)` 替代 `os.kill(pid, 0)`。

---

## 二、高：核心模块零单元测试

Phase 3 已给 5 个模块补了测试，但以下 7 个模块**零覆盖**：

| 模块 | 行数 | 说明 |
|------|------|------|
| `src/llm_refiner.py` | 639 | refiner 核心逻辑，只在集成测试里被 mock 掉 |
| `src/fixer.py` | 406 | 多轮修正循环，completely untested |
| `src/parser.py` | 1500+ | 只有 `_should_reject_parameter_candidate` 和 table merge 有测试，主 `parse()` 零覆盖 |
| `src/openai_compat.py` | 205 | API 兼容层、proxy 处理、重试逻辑，零测试 |
| `src/record_access.py` | 269 | 纯数据访问函数，极易测试但零测试 |
| `src/md_builder.py` | 129 | 零测试 |
| `src/utils.py` | 92 | 纯工具函数（`normalize_line`、`normalize_cell`、`dedupe_keep_order`），零测试 |

**影响：** 这些是管道核心环节。`fixer.py` 和 `llm_refiner.py` 出 bug 时，baseline 测试能抓到但无法定位到具体函数。

---

## 三、中：测试套件自身问题

### 3.1 `_SNAPSHOT_KNOWN_MISSING` 有死条目

[tests/test_sample_score_baseline.py:27-30](tests/test_sample_score_baseline.py#L27-L30)

`ANSIB16.5法兰尺寸标准.pdf` 存在于 `_SNAPSHOT_KNOWN_MISSING`，但**不在 `_BASELINES` 列表中**。放在 known_missing 里什么也不做 — 纯死代码。

### 3.2 CB_T 8522 fixture 存在但被跳过

[tests/test_sample_score_baseline.py:28](tests/test_sample_score_baseline.py#L28)

`CB_T_8522-2011.json` 快照已生成并入库（commit `01fcdd5`），但仍在 `_SNAPSHOT_KNOWN_MISSING` 中，导致快照对比被跳过。应跑一次 `SLOW_TESTS=1` 验证能否从 known_missing 移除。

### 3.3 ScannedBaselineTests 只写不测

[tests/test_sample_score_baseline.py:339-340](tests/test_sample_score_baseline.py#L339-L340)

`test_scanned_baseline` 方法每跑必覆盖 fixture 文件，从不做 `assertEqual` 比较。是个日志，不是测试。

### 3.4 单方法测试文件

- `tests/test_export_contract.py` — 1 个测试方法，只测 happy path
- `tests/test_pipeline_ocr_summary.py` — 1 个测试方法，只测一个字段

### 3.5 profiler 语言检测测试太弱

[tests/test_profiler.py:176-185](tests/test_profiler.py#L176-L185)

`InspectTextLayerEdgeCaseTests` 的两个测试只断言 `char_count > 0`，不验证语言检测结果是否正确。

---

## 四、中：配置和运维缺口

### 4.1 `.env.example` 缺 9 个环境变量

OCR 全部 7 个变量（`OCR_ENABLED`、`OCR_LANG`、`OCR_DPI`、`OCR_PAGE_BATCH_SIZE`、`OCR_TIMEOUT_SECONDS`、`OCR_LARGE_DOC_PAGE_THRESHOLD`、`OCR_REDUCED_DPI`、`OCR_TABLE_ENABLED`）加 `PIPELINE_TIMEOUT_SECONDS`、`OPENAI_CHAT_MODEL` 在 `.env.example` 中全无文档。

### 4.2 Web server host/port 硬编码

[web/server.py:29](web/server.py#L29)

`uvicorn.run("web.server:app", host="127.0.0.1", port=8080, reload=False)` — 容器部署或远程访问直接不可用。应读 `UVICORN_HOST` / `UVICORN_PORT` 环境变量。

### 4.3 ThreadPoolExecutor 永不 shutdown

[web/api.py:39](web/api.py#L39)

`_EXECUTOR = ThreadPoolExecutor(max_workers=2)` 是模块级全局变量，进程退出时正在进行的 OCR/LLM 任务被强杀。应用 FastAPI lifespan 或 atexit 注册清理。

### 4.4 `requirements.txt` 全用 `>=` 无锁

所有依赖都是 `>=` 下限，无 lock file。`pip install` 随时拉入 breaking change。应加 `requirements.lock` 或改用 `pip-tools` / `poetry`。

### 4.5 缺少部署基础设施

- 无 `Dockerfile`
- 无 CI/CD 配置（`.github/workflows/`、`.gitlab-ci.yml` 等）
- 无 `pyproject.toml` 或 `setup.py`（无法 `pip install -e .`）

### 4.6 `.gitignore` 缺口

- `_debug_*.json` 文件未 ignore
- `.pytest_cache/` 未 ignore
- `.agent/` 目录未明确处理

---

## 五、低：代码卫生（选做级）

### 5.1 `_section_ref()` 脆弱的 `__dict__` 位置索引

[src/parser.py:1624-1628](src/parser.py#L1624-L1628)

用 `section.__dict__.values()` 按位置取 `[0]` / `[1]` 作为编号和标题。`SectionRecord` 字段声明顺序一变就坏。`record_access.py:44` 已有正确实现 `section_ref()`，parser 应改用那个。

### 5.2 两处静默 `except Exception: pass`

- [src/openai_compat.py:13](src/openai_compat.py#L13) — OpenAI SDK 导入失败无声无日志
- [src/openai_compat.py:167](src/openai_compat.py#L167) — json_schema 回退静默吞错

### 5.3 报错信息引用了旧变量名

[src/summarizer.py:86](src/summarizer.py#L86)

错误消息："缺少可用的 OpenAI SDK 或 `OPENAI_API_KEY`" — 但代码实际检查的是 `LLM_API_KEY`。

### 5.4 reviewer 问题 ID 全英文

[src/reviewer.py:708-897](src/reviewer.py#L708-L897)

29 个问题 ID（如 `summary_template_fallback`、`llm_stub_summary`、`table_core_missing`）全是英文 snake_case，与其余中文契约不一致。

### 5.5 管道内重复定义 `DocumentData`

[src/pipeline.py:91](src/pipeline.py#L91)

异常处理分支里 `from src.models import DocumentData, DocumentProfile, FileMetadata` 是防御性重新导入，模块级已有同名导入。

### 5.6 LLM 模块错误处理不一致

`summarizer.py` 在 LLM 失败时把原因写进 dict 但不打 log；`tagger.py` 在 LLM 失败时静默返回基础标签不打 log；`ocr.py` 总是打 warning。三者对同一类故障的处理策略不统一。
