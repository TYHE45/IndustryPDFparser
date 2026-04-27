"""Byte-level EOL guard for baseline snapshot fixtures."""
from __future__ import annotations

import unittest
from pathlib import Path

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "baseline_snapshots"


class FixtureEolByteGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixtures = sorted(FIXTURES_ROOT.glob("*.json"))
        self.assertGreaterEqual(
            len(self.fixtures),
            11,
            f"expected >= 11 baseline fixtures, found {len(self.fixtures)} in {FIXTURES_ROOT}",
        )

    def test_no_crlf_in_any_fixture(self) -> None:
        offenders = []
        for fixture in self.fixtures:
            raw = fixture.read_bytes()
            if b"\r\n" in raw:
                offenders.append(fixture.name)
        self.assertEqual(offenders, [], f"fixtures with CRLF: {offenders}")

    def test_each_fixture_starts_with_open_brace_and_lf(self) -> None:
        offenders = []
        for fixture in self.fixtures:
            raw = fixture.read_bytes()
            if not raw.startswith(b"{\n"):
                offenders.append(f"{fixture.name}: head={raw[:8]!r}")
        self.assertEqual(offenders, [])

    def test_each_fixture_ends_with_close_brace_and_trailing_lf(self) -> None:
        offenders = []
        for fixture in self.fixtures:
            raw = fixture.read_bytes()
            if not raw.endswith(b"}\n"):
                offenders.append(f"{fixture.name}: tail={raw[-8:]!r}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
