# Context

写清上一轮已完成内容（参考 `CHANGELOG.md`）、当前目标来源（参考 `TODO.md`）、当前工作区状态、明确不在本轮处理的事项。

---

# Budget（预算条目，plan 起草时即列出）

- **`bonus_test_slot`**：用途预测 = 。**落地后必填**：实际用途或 "未触发，理由：..."。
- **`fixup_commit_slot`**：用途预测 = 。**落地后必填**：实际用途或 "未触发，理由：..."。

若两槽都未用上，commit 数为 N；若用上 1 个，为 N+1；都用上为 N+2。Verification 末尾必须回填这两槽。

---

# Pre-flight checklist（ExitPlanMode 之前必跑）

```bash
python -m tools.plan_lint <plan_path>
```

退出码必须为 0；非 0 时回头修 plan 字段名再 lint，直到 clean。

### 条件句纪律

任何带 `if X then Y` 的 plan 条目必须：
1. 显式排一个 "run X-check" 子步骤（如"跑慢基线确认 X 是否成立"）
2. 在 Verification 段追加对应的验证命令

---

# Plan

## 阶段 1：<阶段标题>

**目标**：

### 1.1：<子任务>

- 实施要点：
- 设计边界：
- 不做事项：

### 1.X：commit 1 — `<commit message>`

- 文件：
- 预检：
- 提交信息要点：

## 阶段 2：<阶段标题>

**目标**：

### 2.1：<子任务>

- 实施要点：
- 设计边界：
- 不做事项：

### 2.X：commit 2 — `<commit message>`

- 文件：
- 预检：
- 提交信息要点：

---

# Critical Files

| 路径 | 本轮作用 |
|------|---------|
| `<path>` | `<作用>` |

---

# Verification

**阶段 1（commit 1 前）：**
- `<command>`：`<expected>`

**阶段 2（commit 2 前）：**
- `<command>`：`<expected>`

**全部完成后：**
- `git log <base>..HEAD --oneline`：应为 N 条（若预算槽触发则 N+1/N+2）
- `git push origin main` 成功
- `git status --short` 符合本轮工作区约定
- **预算条目回填**：`bonus_test_slot` / `fixup_commit_slot` 均已替换为实际用途或未触发理由

---

# 风险与回滚点

- **<风险名>**：<触发条件 / 影响 / 回滚或降级方式>

---

# FP 四拆后的文档地图

**FP 四拆后的文档地图**：[`First Principles.md`](../First%20Principles.md) / [`CHANGELOG.md`](../CHANGELOG.md) / [`TODO.md`](../TODO.md) / [`LESSONS.md`](../LESSONS.md)
