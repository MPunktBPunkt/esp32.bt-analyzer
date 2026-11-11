"""Host tests for controller/agent_view.py rates and controller/btmon_live.py parsing.

  python3 -m unittest tests/host/test_controller_live.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from controller.agent_view import rates  # noqa: E402
from controller.btmon_live import BtmonParser  # noqa: E402

BTMON_SAMPLE = """\
Bluetooth monitor ver 5.66
= New Index: C8:C9:A3:CB:7B:0A (Primary,Virtual,hci1)                  [hci1] 0.000001
< HCI Command: Reset (0x03|0x0003) plen 0                          #1 [hci1] 0.004321
> HCI Event: Command Complete (0x0e) plen 4                        #2 [hci1] 0.006789
      Reset (0x03|0x0003) ncmd 1
        Status: Success (0x00)
> ACL Data RX: Handle 11 flags 0x02 dlen 11                        #3 [hci1] 3.120000
      Channel: 64 len 7 [PSM 23 mode Basic (0x00)] {chan 0}
      AVCTP Control: Command: type 0x00 label 0 PID 0x110e
        AVRCP: PASS THROUGH: Play (0x44) Pressed
@ MGMT Event: Command Complete (0x0001) plen 6                {0x0001} [hci1] 3.200000
"""


def parse(text):
    p = BtmonParser()
    blocks = [b for b in (p.feed(line) for line in text.splitlines(True)) if b]
    tail = p.flush()
    return blocks + ([tail] if tail else [])


class Rates(unittest.TestCase):
    def test_delta_per_second(self):
        r = rates({"toCtrlBytes": 100, "toHostBytes": 0}, {"toCtrlBytes": 600, "toHostBytes": 2000}, 2.0)
        self.assertEqual(r["toCtrlBytesPs"], 250.0)
        self.assertEqual(r["toHostBytesPs"], 1000.0)

    def test_no_history_or_reboot_is_zero(self):
        self.assertEqual(rates(None, {"toCtrlBytes": 500}, 1.0)["toCtrlBytesPs"], 0.0)
        self.assertEqual(rates({"toCtrlBytes": 900}, {"toCtrlBytes": 10}, 1.0)["toCtrlBytesPs"], 0.0)


class Btmon(unittest.TestCase):
    def test_blocks_and_fields(self):
        b = parse(BTMON_SAMPLE)
        self.assertEqual([x["dir"] for x in b], ["note", "note", "tx", "rx", "rx", "mgmt"])
        self.assertEqual(b[0]["title"], "Bluetooth monitor ver 5.66")
        self.assertEqual(b[1]["hci"], 1)
        self.assertEqual(b[2]["title"], "HCI Command: Reset (0x03|0x0003) plen 0")
        self.assertEqual(b[2]["meta"], "#1 [hci1] 0.004321")
        self.assertEqual(b[2]["proto"], "CMD")
        self.assertEqual(len(b[3]["details"]), 2)
        self.assertEqual(b[3]["proto"], "EVT")
        self.assertEqual(b[5]["hci"], 1)

    def test_avrcp_detected(self):
        acl = parse(BTMON_SAMPLE)[4]
        self.assertEqual(acl["proto"], "AVRCP")
        self.assertIn("Play (0x44) Pressed", acl["details"][-1])


if __name__ == "__main__":
    unittest.main()
