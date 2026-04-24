from __future__ import annotations

import unittest

from src import reviewer
from tests.helpers import build_sample_document


class ReviewerHitConditionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = build_sample_document()

    def test_summary_structure_flags_count_only_summary_when_chapters_are_low_signal(self) -> None:
        summary = {
            "\u5168\u6587\u6458\u8981": (
                "\u300aKupplungen ohne R\u00fcckschlagventil\u300b\u5f53\u524d\u8bc6\u522b\u4e3a"
                "\u6807\u51c6/\u89c4\u8303\u6587\u6863\u3002\u5df2\u5efa\u7acb 19 \u4e2a\u6b63\u6587"
                "\u7ae0\u8282\u6458\u8981\u3002\u5df2\u62bd\u53d6 63 \u6761\u6570\u503c\u578b\u53c2\u6570\u3002"
                "\u5df2\u8bc6\u522b 13 \u6761\u5f15\u7528\u6807\u51c6\u3002"
            ),
            "\u7ae0\u8282\u6458\u8981": [
                {
                    "\u7ae0\u8282\u6807\u9898": "\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm A\uff09",
                    "\u6458\u8981": "\u5f53\u524d\u4ec5\u7a33\u5b9a\u8bc6\u522b\u5230\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm A\uff09\uff0c\u6b63\u6587\u4ecd\u7136\u8f83\u5c11\u3002",
                },
                {
                    "\u7ae0\u8282\u6807\u9898": "\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm B\uff09",
                    "\u6458\u8981": "\u5f53\u524d\u4ec5\u7a33\u5b9a\u8bc6\u522b\u5230\u7ae0\u8282\u4e3b\u9898\uff08\u539f\u6587\uff1aForm B\uff09\uff0c\u6b63\u6587\u4ecd\u7136\u8f83\u5c11\u3002",
                },
                {
                    "\u7ae0\u8282\u6807\u9898": "Form",
                    "\u6458\u8981": "\u672c\u7ae0\u8282\u4e3b\u8981\u56f4\u7ed5 Form \u5c55\u5f00\uff0c\u5df2\u8bc6\u522b\u5230\u539f\u6587\u6b63\u6587\uff0c\u5f53\u524d\u7ec6\u8282\u4ecd\u4ee5\u539f\u6587\u4e3a\u51c6\u3002",
                },
            ],
        }

        result = reviewer._review_summary_structure(self.document, summary)
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.CHAPTER_SUMMARY_EMPTY, issue_names)
        self.assertIn(reviewer.SUMMARY_TEMPLATE_FALLBACK, issue_names)

    def test_review_tags_flags_foreign_phrase_parameter_tags(self) -> None:
        tags = {
            "\u53c2\u6570\u6807\u7b7e": [
                "\u91cd\u91cf",
                "verwendet f\u00fcr DN",
            ],
        }

        result = reviewer._review_tags(self.document, tags)
        issue_names = [item[reviewer.KEY_CONTENT] for item in result[reviewer.KEY_ISSUES]]

        self.assertIn(reviewer.NOISY_PARAMETER_TAGS, issue_names)


if __name__ == "__main__":
    unittest.main()
