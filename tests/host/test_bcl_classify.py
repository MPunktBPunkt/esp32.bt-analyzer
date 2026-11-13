"""Host tests for tools/bcl_classify.py (synthetic only)."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_classify import classify_bytes  # noqa: E402
from bcl_framer import INIT_MAGIC, build_synthetic_frame  # noqa: E402
from bcl_dummy_hu import ObserveOnlySession, DummyHuSession  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_empty_unknown(self):
        self.assertEqual(classify_bytes(b"")["bcl_classification"], "UNKNOWN")

    def test_magic_alone_candidate(self):
        r = classify_bytes(INIT_MAGIC)
        self.assertEqual(r["bcl_classification"], "BCL_CANDIDATE")
        self.assertEqual(r["magic_count"], 1)

    def test_magic_not_confirmed(self):
        r = classify_bytes(INIT_MAGIC * 3)
        self.assertEqual(r["bcl_classification"], "BCL_CANDIDATE")
        self.assertIsNone(r["handshake"])

    def test_handshake_confirmed(self):
        payload = struct.pack(">HHI", 3, 14, 0x8000)
        raw = INIT_MAGIC + build_synthetic_frame(4, 0, 0, payload)
        r = classify_bytes(raw)
        self.assertEqual(r["bcl_classification"], "BCL_FIELD_CONFIRMED")
        self.assertEqual(r["handshake"]["version"], 3)
        self.assertEqual(r["handshake"]["instance_id"], 14)

    def test_valid_data_strong(self):
        raw = build_synthetic_frame(2, 1, 0x0FA4, b"SYNTH01")
        r = classify_bytes(raw)
        self.assertEqual(r["bcl_classification"], "STRONG_BCL_CANDIDATE")


class TestObserveOnly(unittest.TestCase):
    def test_never_replies(self):
        s = ObserveOnlySession()
        self.assertEqual(s.on_bytes(INIT_MAGIC * 2), [])
        self.assertEqual(s.on_bytes(build_synthetic_frame(4, 0, 0, bytes(8))), [])

    def test_flag_on_dummy(self):
        s = DummyHuSession(observe_only=True)
        self.assertEqual(s.on_bytes(INIT_MAGIC), [])
        self.assertFalse(s.handshake_sent)


if __name__ == "__main__":
    unittest.main()
