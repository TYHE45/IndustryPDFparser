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

    def test_chinese_industry_standard_codes_matched(self) -> None:
        """Phase 5 P1: Chinese industry standard prefixes in STANDARD_RE."""
        for code in [
            "JB/T 1234-2020",
            "YB/T 5678-2019",
            "HG/T 3456-2018",
            "QC/T 789-2021",
            "LY/T 1001-2017",
            "BB/T 234-2016",
            "MT/T 567-2020",
            "SH/T 345-2019",
            "SY/T 6789-2021",
            "DL/T 789-2018",
            "JJG 123-2020",
            "JJF 456-2019",
        ]:
            with self.subTest(code=code):
                self.assertIsNotNone(STANDARD_RE.fullmatch(code), f"{code} should match STANDARD_RE")

    def test_ics_classification_code_rejected(self) -> None:
        self.assertTrue(
            self.parser._should_reject_parameter_candidate(
                "ICS 23.040.60",
                "",
            )
        )

    def test_standard_code_with_z_suffix_rejected(self) -> None:
        self.assertTrue(
            self.parser._should_reject_parameter_candidate(
                "CB/Z 234-2020",
                "5 mm",
            )
        )

    def test_standard_code_in_name_rejected(self) -> None:
        self.assertTrue(
            self.parser._should_reject_parameter_candidate(
                "GB/T 1234-2020",
                "5 mm",
            )
        )



if __name__ == "__main__":
    unittest.main()
