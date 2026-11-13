"""Host tests for tools/lab_hfp_stack.py (parsing only, no SSH)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from lab_hfp_stack import DROPIN_04, DROPIN_05, dropin_for, parse_diag  # noqa: E402

PIPEWIRE = """## ps
root bluetoothd /usr/libexec/bluetooth/bluetoothd
pi pipewire /usr/bin/pipewire
pi wireplumber /usr/bin/wireplumber
## versions
pipewire: /usr/bin/pipewire Compiled with libpipewire 1.2.7 Linked with libpipewire 1.2.7
wireplumber: wireplumber Compiled with libwireplumber 0.5.8 Linked with libwireplumber 0.5.8
bluetoothd: 5.66
## roles
## dropins
## uuids
Controller C8:C9:A3:CB:37:96 BT-Analyzer-Phone [default]
	UUID: Handsfree Audio Gateway   (0000111f-0000-1000-8000-00805f9b34fb)
"""


class TestParse(unittest.TestCase):
    def test_pipewire_native(self):
        d = parse_diag(PIPEWIRE)
        self.assertEqual(d["hfp_stack_guess"], "pipewire-native")
        self.assertEqual(d["wireplumber_version"], (0, 5))
        self.assertFalse(d["hfp_off_active"])
        self.assertTrue(any("Handsfree Audio Gateway" in u for u in d["adapter_uuids"]))

    def test_ofono_wins(self):
        d = parse_diag(PIPEWIRE.replace("pi wireplumber", "root ofonod /usr/sbin/ofonod\npi wireplumber"))
        self.assertEqual(d["hfp_stack_guess"], "ofono")

    def test_dropin_detected(self):
        d = parse_diag(PIPEWIRE.replace("## dropins\n", "## dropins\n51-bt-analyzer-no-hfp.conf\n"))
        self.assertTrue(d["hfp_off_active"])

    def test_dropin_format_by_version(self):
        self.assertEqual(dropin_for((0, 4))[0], DROPIN_04)
        self.assertEqual(dropin_for((0, 5))[0], DROPIN_05)
        self.assertIn("a2dp_sink a2dp_source", dropin_for((0, 5))[1])


if __name__ == "__main__":
    unittest.main()
