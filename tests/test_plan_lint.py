from __future__ import annotations

import unittest

from tools.plan_lint import KNOWN_DRIFT_MAP, lint_text

BT = chr(96)


class PlanLintTests(unittest.TestCase):
    def test_clean_plan_returns_no_issues(self) -> None:
        text = f"# Header\n顶层字段 {BT}快照版本{BT} 与 {BT}提示词签名{BT} 已对齐 FP 契约。"
        self.assertEqual(lint_text(text), [])

    def test_pure_english_snake_case_with_chinese_counterpart_flagged(self) -> None:
        text = f"Stage 1 引入 {BT}snapshot_version{BT} 作为顶层字段。"
        issues = lint_text(text)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].found, "snapshot_version")
        self.assertEqual(issues[0].suggestion, "快照版本")
        self.assertEqual(issues[0].rule, "english_with_chinese_counterpart")

    def test_chinglish_mix_with_pure_chinese_counterpart_flagged(self) -> None:
        text = f"process_log 新增 {BT}prompt_签名{BT} 与 {BT}reviewer_签名{BT} 两字段。"
        issues = lint_text(text)
        self.assertEqual(len(issues), 2)
        suggestions = sorted(issue.suggestion for issue in issues)
        self.assertEqual(suggestions, ["提示词签名", "评审规则签名"])
        for issue in issues:
            self.assertEqual(issue.rule, "chinglish_with_chinese_counterpart")

    def test_known_drift_map_uses_correct_rule_classification(self) -> None:
        # snapshot_version 是纯英文，prompt_签名 是 Chinglish
        issues = lint_text(f"{BT}snapshot_version{BT}\n{BT}prompt_签名{BT}")
        self.assertEqual([issue.rule for issue in issues], [
            "english_with_chinese_counterpart",
            "chinglish_with_chinese_counterpart",
        ])
        self.assertEqual(KNOWN_DRIFT_MAP["reviewer_签名"], "评审规则签名")

    def test_arbitrary_backtick_identifiers_not_in_map_pass_through(self) -> None:
        text = f"调用 {BT}run_iterative_pipeline{BT} 与 {BT}process_log.json{BT} 是合理的。"
        # 这两个不在 KNOWN_DRIFT_MAP 里，应该不报
        self.assertEqual(lint_text(text), [])

    def test_fenced_code_blocks_are_ignored(self) -> None:
        text = f"```python\nfield = {BT}snapshot_version{BT}\n```\n顶层字段 {BT}快照版本{BT}。"
        self.assertEqual(lint_text(text), [])


if __name__ == "__main__":
    unittest.main()
