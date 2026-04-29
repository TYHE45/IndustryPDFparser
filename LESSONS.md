# LESSONS

结构层教训索引；不承载待办状态或完整 changelog。

---

## 工作流教训

- **2026042402 / 2026042403：条件句必须拆成“测量—决策—记录”。** "if condition → do X" 型 plan 条款应改成 "run condition check → record result → act"，强制插入测量步骤，不留“没跑所以没更新”的黑洞。
- **2026042402：scope drift 是健康信号。** 白盒测试先行常发现“生产代码分支不存在对应 contract”，该类 scope drift 是健康信号而不是计划失败，但 plan 编写时应预留“可能推动 src 修正”的弹性。
- **2026042403 / 2026042404 / 2026042405：plan 切片粒度系统性低估。** 三轮均出现“plan 没预估到的 fixup commit”，下轮 plan 起草应主动预算 “N + 1 commit”。
- **2026042404：scope drift 弹性条款应写进 Verification。** “先 fixture/test → 后修齐 src/baseline”是“白盒先行 + 真值锚定”工作流的预期产物，不应再视为 plan 失败。
- **2026042404：commit message 要从 plan 标题起步。** commit message 应在落地前 copy plan §X.Y 标题作为格式起点，最低限度包含 plan stage 标识，便于 `git log --grep` 反查。
- **2026042405：bonus test/commit 已成稳定 N+1 模式。** 连续 3 轮稳定出现 bonus/fixup，plan 模板应直接列 `bonus_test_slot` / `fixup_commit_slot`，不再把它当偶发风险。
- **2026042406：plan 模板固定 Budget 与 Pre-flight。** 下轮 plan 起草直接 copy `tools/plan_template.md`，落地后在 Verification 末段回填两槽实际用途。

## 工程教训

- **2026042404：fixture EOL 必须字节级守卫。** Python 文本读取的 universal newline 会遮蔽 CRLF；跨平台文本资产需要 `.gitattributes`、写入点 `newline="\n"` 与 test 时刻 `read_bytes()` 三层防御。
- **2026042404 / 2026042405：plan 字段命名 drift 需要工具化。** 纯文字教训不够，字段名应通过 `tools/plan_lint.py` 在 plan ready 但未 ExitPlanMode 前检查。
- **2026042404：伪代码 key 与最终实现偏离要写明。** plan 伪代码和最终实现等价但查表 key 不同时，应在 commit message 中显式说明，避免 reader 误以为 bug。
- **2026042405：plan-lint vocab 不能只靠手写。** `KNOWN_DRIFT_MAP` 只适合累积历史 drift，第一次新型 drift 需要 canonical vocab 自动通道兜底。
- **2026042406：叙事文档不能进入 plan-lint vocab。** CHANGELOG / TODO / LESSONS 会保留历史 drift 叙事，把它们 seed 进 canonical vocab 会污染字段契约。
- **2026042406：fixture EOL 守卫不应门控 SLOW_TESTS。** 11 份 JSON 字节读取是 ms 级，应每次全集都跑。
