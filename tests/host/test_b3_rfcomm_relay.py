"""B3 transparent relay — byte identity + BCL/Etch decode (LAB)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from b3_rfcomm_relay import run_selftest  # noqa: E402


class TestB3RfcommRelay(unittest.TestCase):
    def test_selftest_byte_identity(self):
        with tempfile.TemporaryDirectory() as td:
            rc = run_selftest(Path(td))
            self.assertEqual(rc, 0)
            report = (Path(td) / "SELFTEST.json").read_text()
            self.assertIn('"byte_identity": true', report)


if __name__ == "__main__":
    unittest.main()
