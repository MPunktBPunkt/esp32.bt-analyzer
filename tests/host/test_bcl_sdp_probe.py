"""Host tests for tools/bcl_sdp_probe.py parsing (no BlueZ, no radio).

  python3 -m unittest tests/host/test_bcl_sdp_probe.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from bcl_sdp_probe import classify, parse_bluetoothctl_info, parse_sdptool, verdict  # noqa: E402

SDPTOOL = """Browsing AA:BB:CC:DD:EE:FF ...
Service Name: Hands-Free unit
Service RecHandle: 0x10001
Service Class ID List:
  "Handsfree" (0x111e)
  "Generic Audio" (0x1203)
Protocol Descriptor List:
  "L2CAP" (0x0100)
  "RFCOMM" (0x0003)
    Channel: 3

Service Name: BMW Connected
Service RecHandle: 0x10002
Service Class ID List:
  "Serial Port" (0x1101)
Protocol Descriptor List:
  "L2CAP" (0x0100)
  "RFCOMM" (0x0003)
    Channel: 5
Profile Descriptor List:
  "Serial Port" (0x1101)
    Version: 0x0102

Service RecHandle: 0x10003
Service Class ID List:
  UUID 128: 00000000-deca-fade-deca-deafdecacaff
Protocol Descriptor List:
  "L2CAP" (0x0100)
  "RFCOMM" (0x0003)
    Channel: 7
"""

CTL_INFO = """Device AA:BB:CC:DD:EE:FF (public)
	Name: BMW 12345
	UUID: Serial Port               (00001101-0000-1000-8000-00805f9b34fb)
	UUID: Vendor specific           (12345678-1234-5678-1234-567812345678)
"""


class ParseSdptool(unittest.TestCase):
    def setUp(self):
        self.recs = parse_sdptool(SDPTOOL)

    def test_record_split_including_nameless(self):
        self.assertEqual([r["handle"] for r in self.recs], ["0x10001", "0x10002", "0x10003"])
        self.assertEqual(self.recs[2]["name"], "")

    def test_rfcomm_channels(self):
        self.assertEqual([r["rfcomm"] for r in self.recs], [3, 5, 7])

    def test_profile_list_not_mixed_into_classes(self):
        self.assertEqual(self.recs[1]["classes"], ["0x1101"])

    def test_classify(self):
        self.assertEqual(classify(self.recs[0]), ["rfcomm3"])
        self.assertEqual(classify(self.recs[1]), ["spp", "rfcomm5", "name_hint"])
        self.assertEqual(classify(self.recs[2]), ["iap2", "rfcomm7"])

    def test_verdict(self):
        self.assertTrue(verdict(self.recs).startswith("CANDIDATE_STRONG"))
        self.assertTrue(verdict(self.recs[2:]).startswith("IAP2_ONLY"))
        self.assertTrue(verdict(self.recs[:1]).startswith("NONE"))


GATT_ONLY_VENDOR = """Service Name: MIDI
Service RecHandle: 0x10010
Service Class ID List:
  UUID 128: 03b80e5a-ede8-4b33-a751-6ce34ec4c700
Protocol Descriptor List:
  "L2CAP" (0x0100)
    PSM: 31
  "ATT" (0x0007)
"""


class GattOnlyVendor(unittest.TestCase):
    def test_vendor_uuid_without_rfcomm_is_not_candidate(self):
        recs = parse_sdptool(GATT_ONLY_VENDOR)
        self.assertEqual(classify(recs[0]), ["vendor128"])
        self.assertTrue(verdict(recs).startswith("NONE"))


class ParseBluetoothctl(unittest.TestCase):
    def test_uuids(self):
        recs = parse_bluetoothctl_info(CTL_INFO)
        self.assertEqual([r["classes"][0] for r in recs],
                         ["0x1101", "12345678-1234-5678-1234-567812345678"])
        self.assertEqual(verdict(recs), "CANDIDATE: RFCOMM data service present (SPP or vendor UUID)")


if __name__ == "__main__":
    unittest.main()
