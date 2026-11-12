import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import bt_pair_agent as pa  # noqa: E402

PHONE_SIDE = "C8:C9:A3:CB:7B:0A"
CAR_SIDE = "C8:C9:A3:CB:37:96"


class AdapterSpec(unittest.TestCase):
    def test_role_and_alias(self):
        a = pa.parse_adapter_spec("c8:c9:a3:cb:37:96=phone:BT-Analyzer-Phone")
        self.assertEqual(a, {"bd": CAR_SIDE, "role": "phone", "alias": "BT-Analyzer-Phone", "cls": 0x5A020C})

    def test_role_only_and_none(self):
        self.assertEqual(pa.parse_adapter_spec(f"{PHONE_SIDE}=car_audio")["cls"], 0x200420)
        self.assertIsNone(pa.parse_adapter_spec(PHONE_SIDE)["cls"])

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            pa.parse_adapter_spec("hci1=phone")
        with self.assertRaises(ValueError):
            pa.parse_adapter_spec(f"{PHONE_SIDE}=headset")


class Decide(unittest.TestCase):
    def test_rules_on_configured_adapter(self):
        self.assertTrue(pa.decide_confirm("always", 0, False, True)[0])
        self.assertFalse(pa.decide_confirm("never", 99, False, True)[0])
        self.assertTrue(pa.decide_confirm("window", 30, False, True)[0])
        self.assertFalse(pa.decide_confirm("window", 0, False, True)[0])

    def test_already_paired_wins(self):
        self.assertTrue(pa.decide_confirm("never", 0, True, True)[0])

    def test_unconfigured_adapter_needs_window(self):
        ok, reason = pa.decide_confirm("always", 0, False, False)
        self.assertFalse(ok)
        self.assertIn("unconfigured", reason)
        self.assertTrue(pa.decide_confirm("always", 10, False, False)[0])


class Window(unittest.TestCase):
    def test_open_expire_garbage(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "win")
            self.assertEqual(pa.window_remaining(path), 0.0)
            pa.open_window(60, path)
            self.assertTrue(55 < pa.window_remaining(path) <= 60)
            Path(path).write_text(str(time.time() - 1))
            self.assertEqual(pa.window_remaining(path), 0.0)
            Path(path).write_text("x")
            self.assertEqual(pa.window_remaining(path), 0.0)


class ClassOfDevice(unittest.TestCase):
    def test_extra_service_bits_from_bluez_are_fine(self):
        self.assertTrue(pa.class_matches(0x6C0420, 0x200420))
        self.assertTrue(pa.class_matches(0x5A020C, 0x5A020C))

    def test_wrong_device_class_or_missing_service(self):
        self.assertFalse(pa.class_matches(0x6C0408, 0x200420))   # hands-free, not car audio
        self.assertFalse(pa.class_matches(0x00020C, 0x5A020C))   # services missing
        self.assertIsNone(pa.class_matches(0x000000, None))


class Objects(unittest.TestCase):
    def test_split_device_path(self):
        self.assertEqual(pa.split_device_path("/org/bluez/hci2/dev_AA_BB_CC_DD_EE_FF"),
                         ("/org/bluez/hci2", "AA:BB:CC:DD:EE:FF"))
        self.assertEqual(pa.split_device_path("/org/bluez/hci1"), ("/org/bluez/hci1", ""))
        self.assertEqual(pa.split_device_path(""), ("", ""))

    def test_summarize_objects(self):
        cfg = {CAR_SIDE: pa.parse_adapter_spec(f"{CAR_SIDE}=phone:X")}
        objects = {
            "/org/bluez/hci1": {"org.bluez.Adapter1": {
                "Address": CAR_SIDE, "Alias": "X", "Powered": True, "Discoverable": True,
                "Pairable": True, "Class": 0x5A020C}},
            "/org/bluez/hci0": {"org.bluez.Adapter1": {"Address": "00:11:22:33:44:55", "Class": 0}},
            "/org/bluez/hci1/dev_11_22_33_44_55_66": {"org.bluez.Device1": {
                "Alias": "BMW 38304", "Paired": True, "Trusted": True, "Connected": False}},
            "/org/bluez/hci1/dev_77_77_77_77_77_77": {"org.bluez.Device1": {"Alias": "seen only"}},
        }
        out = pa.summarize_objects(objects, cfg)
        self.assertEqual([a["hci"] for a in out], ["hci0", "hci1"])
        self.assertEqual(out[0]["role"], "unconfigured")
        car = out[1]
        self.assertEqual((car["role"], car["cls"], car["cls_wanted"]), ("phone", "0x5a020c", "0x5a020c"))
        self.assertEqual(car["devices"], [{"mac": "11:22:33:44:55:66", "name": "BMW 38304",
                                           "paired": True, "trusted": True, "connected": False}])


class Status(unittest.TestCase):
    def test_read_status_merges_files(self):
        with tempfile.TemporaryDirectory() as d:
            saved = (pa.STATE_FILE, pa.EVENTS_FILE, pa.WINDOW_FILE)
            pa.STATE_FILE, pa.EVENTS_FILE, pa.WINDOW_FILE = (os.path.join(d, n) for n in ("s", "e", "w"))
            try:
                Path(pa.STATE_FILE).write_text(json.dumps({"running": True, "mode": "always"}))
                Path(pa.EVENTS_FILE).write_text(
                    "\n".join(json.dumps({"id": i, "method": "Connected"}) for i in range(40)) + "\n")
                st = pa.read_status(events_n=5)
            finally:
                pa.STATE_FILE, pa.EVENTS_FILE, pa.WINDOW_FILE = saved
        self.assertTrue(st["running"])
        self.assertEqual([e["id"] for e in st["events"]], [35, 36, 37, 38, 39])
        self.assertEqual(st["window_s"], 0.0)
        self.assertIn("service", st)


if __name__ == "__main__":
    unittest.main()
