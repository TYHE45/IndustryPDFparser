from __future__ import annotations

import unittest
from pathlib import Path

from config import AppConfig
from src.parser import PDFParser, STANDARD_RE


class ParserNumericBlacklistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = PDFParser(
            AppConfig(
                input_path=Path("sample.pdf"),
                output_dir=Path("output"),
                use_llm=False,
            )
        )

    def test_date_in_descriptive_name_rejected(self) -> None:
        self.assertTrue(
            self.parser._should_reject_parameter_candidate(
                "发布 2020-01",
                "10 mm",
            )
        )

    def test_year_suffix_from_standard_code_rejected(self) -> None:
        self.assertTrue(
            self.parser._should_reject_parameter_candidate(
                "2020",
                "10 mm",
            )
        )

    def test_standard_code_with_year_suffix_matched(self) -> None:
        self.assertIsNotNone(STANDARD_RE.fullmatch("GB 39038-2020"))
        self.assertIsNotNone(STANDARD_RE.fullmatch("CH/T 1234-2020"))

    def test_value_containing_standard_code_substring_is_not_rejected_by_name_blacklist(self) -> None:
        self.assertFalse(
            self.parser._should_reject_parameter_candidate(
                "Pressure",
                "10 mm (GB 39038-2020)",
            )
        )


if __name__ == "__main__":
    unittest.main()
