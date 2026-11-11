"""Host tests for tools/hci_tcp_bridge.py H4 splitting (no vhci, no ESP).

  python3 -m unittest tests/host/test_hci_tcp_bridge.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from hci_tcp_bridge import split_h4  # noqa: E402


class SplitH4(unittest.TestCase):
    def test_event_and_acl_in_one_chunk(self):
        buf = bytearray.fromhex("040e0401030c00" "02012003000aabbc")
        pkts = split_h4(buf)
        self.assertEqual([p.hex() for p in pkts], ["040e0401030c00", "02012003000aabbc"])
        self.assertEqual(buf, bytearray())

    def test_partial_packet_stays_buffered(self):
        buf = bytearray.fromhex("040e0401")
        self.assertEqual(split_h4(buf), [])
        buf += bytes.fromhex("030c00")
        self.assertEqual([p.hex() for p in split_h4(buf)], ["040e0401030c00"])

    def test_header_split(self):
        buf = bytearray.fromhex("0201")
        self.assertEqual(split_h4(buf), [])
        self.assertEqual(buf, bytearray.fromhex("0201"))

    def test_iso_length_masks_flags(self):
        buf = bytearray.fromhex("05010001c07f" "04")
        self.assertEqual([p.hex() for p in split_h4(buf)], ["05010001c07f"])
        self.assertEqual(buf, bytearray.fromhex("04"))

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            split_h4(bytearray.fromhex("07"))


if __name__ == "__main__":
    unittest.main()
