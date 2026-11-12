"""Host tests for tools/a2dp_budget.py (SBC math + btmon Set Configuration parser).

  python3 -m unittest tests/host/test_a2dp_budget.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from a2dp_budget import (  # noqa: E402
    leg_report,
    max_bitpool_for,
    parse_btmon_setconf,
    sbc_bitrate,
    sbc_frame_len,
    wire_Bps,
)

BTMON = """< ACL Data TX: Handle 256 flags 0x00 dlen 22          #40 [hci2] 12.345678
      Channel: 65 len 18 [PSM 25 mode Basic (0x00)] {chan 1}
      AVDTP: Set Configuration (0x03) Command (0x00) type 0x00 label 2 nosp 0
        ACP SEID: 1
        INT SEID: 3
        Service Category: Media Transport (0x01)
        Service Category: Media Codec (0x07)
          Media Type: Audio (0x00)
          Media Codec: SBC (0x00)
            Frequency: 44100 (0x20)
            Channel Mode: Joint Stereo (0x01)
            Block Length: 16 (0x10)
            Subbands: 8 (0x01)
            Allocation Method: Loudness (0x01)
            Minimum Bitpool: 2
            Maximum Bitpool: 53
> ACL Data RX: Handle 256 flags 0x02 dlen 6            #41 [hci2] 12.360000
      AVDTP: Set Configuration (0x03) Response Accept (0x02) type 0x00 label 2 nosp 0
> ACL Data RX: Handle 512 flags 0x02 dlen 22           #90 [hci1] 20.000000
      AVDTP: Set Configuration (0x03) Command (0x00) type 0x00 label 0 nosp 0
        Service Category: Media Codec (0x07)
          Media Codec: SBC (0x00)
            Frequency: 48000 (0x10)
            Channel Mode: Joint Stereo (0x01)
            Block Length: 16 (0x10)
            Subbands: 8 (0x01)
            Allocation Method: Loudness (0x01)
            Minimum Bitpool: 2
            Maximum Bitpool: 32
"""


class SbcMath(unittest.TestCase):
    def test_frame_len_joint_stereo(self):
        self.assertEqual(sbc_frame_len(53), 119)
        self.assertEqual(sbc_frame_len(35), 83)

    def test_frame_len_mono_and_dual(self):
        self.assertEqual(sbc_frame_len(32, "Mono"), 4 + 4 + 64)
        self.assertEqual(sbc_frame_len(32, "Dual Channel"), 4 + 8 + 128)

    def test_bitrate(self):
        self.assertAlmostEqual(sbc_bitrate(53) / 1000, 328.0, delta=0.5)
        self.assertAlmostEqual(sbc_bitrate(35) / 1000, 228.8, delta=0.5)

    def test_wire_rate_adds_small_overhead(self):
        codec = sbc_bitrate(53) / 8
        self.assertGreater(wire_Bps(53), codec)
        self.assertLess(wire_Bps(53), codec * 1.05)

    def test_max_bitpool_fits_budget(self):
        bp = max_bitpool_for(38.0)
        self.assertLessEqual(wire_Bps(bp), 38000 * 0.8)
        self.assertGreater(wire_Bps(bp + 1), 38000 * 0.8)
        self.assertLess(bp, 53)


class ParseBtmon(unittest.TestCase):
    def test_commands_only_with_hci_and_direction(self):
        cfgs = parse_btmon_setconf(BTMON)
        self.assertEqual([(c["hci"], c["direction"], c["max_bitpool"], c["freq"]) for c in cfgs],
                         [("hci2", "tx", 53, 44100), ("hci1", "rx", 32, 48000)])

    def test_leg_report(self):
        cfgs = parse_btmon_setconf(BTMON)
        over = leg_report(cfgs[0], 38.0, 895)
        self.assertFalse(over["fits_80pct"])
        self.assertGreater(over["load"], 1.0)
        ok = leg_report(cfgs[1], 38.0, 895)
        self.assertTrue(ok["fits_80pct"])


if __name__ == "__main__":
    unittest.main()
