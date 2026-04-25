from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from src.config_signatures import prompt_signature, reviewer_signature
from src.contracts import KEY_PROMPT_SIGNATURE, KEY_REVIEWER_SIGNATURE
from tests.test_pipeline_safety_net_count import _run_pipeline_with_two_safety_net_hits


_SIGNATURE_RE = re.compile(r"^[0-9a-f]{8}$")


class ConfigSignatureTests(unittest.TestCase):
    def test_prompt_signature_is_8_hex_and_stable(self) -> None:
        first = prompt_signature()
        second = prompt_signature()

        self.assertEqual(first, second)
        self.assertRegex(first, _SIGNATURE_RE)

    def test_reviewer_signature_changes_when_issue_deductions_changes(self) -> None:
        original = reviewer_signature()

        with patch("src.config_signatures.ISSUE_DEDUCTIONS", {"测试问题": ("测试扣分", 1.25)}):
            changed = reviewer_signature()

        self.assertRegex(changed, _SIGNATURE_RE)
        self.assertNotEqual(changed, original)
        self.assertEqual(reviewer_signature(), original)

    def test_pipeline_process_log_contains_prompt_and_reviewer_signatures(self) -> None:
        result = _run_pipeline_with_two_safety_net_hits()
        process_log = result["process_log"]

        self.assertRegex(process_log[KEY_PROMPT_SIGNATURE], _SIGNATURE_RE)
        self.assertRegex(process_log[KEY_REVIEWER_SIGNATURE], _SIGNATURE_RE)


if __name__ == "__main__":
    unittest.main()
