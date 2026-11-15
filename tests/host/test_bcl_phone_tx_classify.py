import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_framer import DEST_ETCH_DESK, DEST_WATCHDOG_DESK  # noqa: E402
from bcl_phone_tx_classify import classify_phone_frame  # noqa: E402


class TestPhoneTxClassify(unittest.TestCase):
    def test_open_etch(self):
        ev = classify_phone_frame(1, 10, DEST_ETCH_DESK, b"")
        self.assertEqual(ev["event"], "phone_tx_classified")
        self.assertIn("OPEN_ETCH", ev["tags"])

    def test_etch_cds_ascii(self):
        ev = classify_phone_frame(2, 12, DEST_ETCH_DESK, b"xxsensors.SOCBatteryyy")
        self.assertIn("ETCH_DATA", ev["tags"])
        self.assertIn("CDS_ASCII", ev["tags"])

    def test_wd_ping(self):
        ev = classify_phone_frame(2, 1, DEST_WATCHDOG_DESK, b"\x13\x37\x13\x37")
        self.assertIn("WD_PING", ev["tags"])


if __name__ == "__main__":
    unittest.main()
