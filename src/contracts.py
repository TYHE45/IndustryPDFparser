from __future__ import annotations

# Centralized schema keys shared by review, pipeline logs, Web payloads, and tests.
# Keep values in Chinese because they are part of the project's public JSON contract.

KEY_TOTAL_SCORE = "总分"
KEY_PASSED = "是否通过"
KEY_REDLINE_TRIGGERED = "红线触发"
KEY_REVIEW_ROUNDS = "评审轮次"
KEY_WEB_REVIEW_ROUNDS = "评审轮次数"
KEY_PROMPT_SIGNATURE = "提示词签名"
KEY_REVIEWER_SIGNATURE = "评审规则签名"
KEY_PROBLEMS = "问题清单"
KEY_PROBLEM_ID = "问题ID"
KEY_LEVEL = "级别"
KEY_CONTENT = "内容"
KEY_DEDUCTION = "扣分"
KEY_FINAL_PASSED = "最终是否通过"
KEY_FINAL_SCORE = "最终总分"
