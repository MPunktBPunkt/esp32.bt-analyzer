"""LAB Auth A/B gate matrix + freeze-on-AUTHENTICATED."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from lab_auth_ab_matrix import run_matrix  # noqa: E402


class TestLabAuthAbMatrix(unittest.TestCase):
    def test_all_arms_pass(self):
        results = run_matrix(
            field_jsonl=ROOT
            / "docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/phone.jsonl"
        )
        by = {r.arm: r for r in results}
        self.assertIn("A_LABSIM_REJECT", by)
        self.assertIn("B_LAB_STUB_ACCEPT_FREEZE", by)
        self.assertIn("B_LAB_STUB_ACCEPT_FULL", by)
        self.assertIn("C_FIELD_REPLAY", by)
        for r in results:
            self.assertTrue(r.pass_, msg=f"{r.arm}: {r.to_dict()}")
        freeze = by["B_LAB_STUB_ACCEPT_FREEZE"]
        self.assertEqual(freeze.auth_state, "AUTHENTICATED")
        self.assertFalse(freeze.continued_past_auth)
        self.assertIn(
            freeze.freeze_snapshot.get("freeze_event"),
            ("AUTHENTICATED", None),  # may be set on snap
        )


if __name__ == "__main__":
    unittest.main()
