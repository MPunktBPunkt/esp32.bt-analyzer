"""Golden LAB positive SAS login fixture — byte + transition anchor."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from lab_auth_golden import DEFAULT_FIXTURE, validate_fixture  # noqa: E402


class TestAuthGoldenFixture(unittest.TestCase):
    def test_fixture_present_and_valid(self):
        self.assertTrue(DEFAULT_FIXTURE.is_file(), msg=str(DEFAULT_FIXTURE))
        fixture = json.loads(DEFAULT_FIXTURE.read_text())
        self.assertEqual(fixture.get("claim_level"), "LAB")
        self.assertEqual(fixture.get("final_auth_state"), "AUTHENTICATED")
        seq = fixture.get("sequence") or []
        methods = [s.get("method") for s in seq]
        self.assertEqual(
            methods,
            [
                "sas_certificate",
                "_result_sas_certificate",
                "sas_login",
                "_result_sas_login",
            ],
        )
        login_tx = seq[2]
        login_rx = seq[3]
        self.assertEqual(login_rx.get("in_reply_to"), login_tx.get("msg_id"))
        self.assertEqual(login_rx.get("classification"), "VOID_OK")
        self.assertGreater(login_rx.get("etch_body_len") or 0, 0)
        self.assertTrue(login_rx.get("etch_body_hex"))
        errs = validate_fixture(fixture)
        self.assertEqual(errs, [], msg=errs)


if __name__ == "__main__":
    unittest.main()
