import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_dummy_hu import (  # noqa: E402
    CMD_HANDSHAKE,
    CMD_KNOCK,
    CMD_OPEN,
    CMD_SELECTPROTO,
    DummyHuSession,
    PhoneClientSession,
    build_handshake,
    summarize,
)
from bcl_framer import DEST_WATCHDOG_DESK, INIT_MAGIC, BclFramer  # noqa: E402


def frames_of(chunks):
    fr = BclFramer()
    out = []
    for c in chunks:
        out.extend(fr.feed(c).frames)
    return out


def run_pair(hu, phone, inits=1):
    """Shuttle bytes between both sessions until quiet."""
    to_hu = [phone.session_init() for _ in range(inits)]
    for _ in range(10):
        to_phone = [r for b in to_hu for r in hu.on_bytes(b)]
        to_hu = [r for b in to_phone for r in phone.on_bytes(b)]
        if not to_hu:
            break


class TestHandshakeBytes(unittest.TestCase):
    def test_desk_example(self):
        self.assertEqual(
            build_handshake(4, 14, 0x8000).hex(),
            "00040000000000080004000e00008000",
        )


class TestDummyHu(unittest.TestCase):
    def test_init_answered_once(self):
        hu = DummyHuSession()
        replies = hu.on_bytes(INIT_MAGIC * 3)
        self.assertEqual(len(replies), 1)
        self.assertEqual(frames_of(replies)[0].cmd, CMD_HANDSHAKE)
        self.assertEqual(hu.on_bytes(INIT_MAGIC), [])
        self.assertEqual(summarize(hu.events)["session_init"], 4)

    def test_init_split_across_reads(self):
        hu = DummyHuSession()
        self.assertEqual(hu.on_bytes(INIT_MAGIC[:2]), [])
        self.assertEqual(len(hu.on_bytes(INIT_MAGIC[2:])), 1)

    def test_watchdog_echo_only_when_enabled(self):
        phone = PhoneClientSession()
        ping = phone.watchdog_ping()
        self.assertEqual(DummyHuSession().on_bytes(ping), [])
        hu = DummyHuSession(echo_watchdog=True)
        (echo,) = hu.on_bytes(ping)
        fr = frames_of([echo])[0]
        self.assertEqual((fr.src, fr.dest), (DEST_WATCHDOG_DESK, 1))


class TestPhoneClientOrder(unittest.TestCase):
    def test_version3_skips_selectproto(self):
        hu, phone = DummyHuSession(version=3), PhoneClientSession()
        run_pair(hu, phone)
        self.assertTrue(phone.active)
        self.assertTrue(hu.knocked)
        self.assertIsNone(hu.selected_proto)

    def test_version4_selects_proto3_before_knock(self):
        hu, phone = DummyHuSession(version=4), PhoneClientSession()
        to_phone = hu.on_bytes(phone.session_init())
        sent = frames_of(phone.on_bytes(to_phone[0]))
        self.assertEqual([f.cmd for f in sent], [CMD_SELECTPROTO, CMD_KNOCK, CMD_OPEN])
        self.assertEqual(sent[1].length, 12)
        for f in sent:
            hu.on_bytes(f.raw)
        self.assertEqual(hu.selected_proto, 3)

    def test_ignores_non_handshake_first(self):
        phone = PhoneClientSession()
        bogus = struct.pack(">HHHH", 2, 0, 0, 0)
        self.assertEqual(phone.on_bytes(bogus), [])
        self.assertFalse(phone.active)


class TestLabVerdict(unittest.TestCase):
    def setUp(self):
        from lab_bcl_dummy_hu_a2dp import verdict

        self.verdict = verdict
        hu, phone = DummyHuSession(), PhoneClientSession()
        run_pair(hu, phone)
        self.hu_events = [{"event": "rfcomm_connected"}] + hu.events
        self.phone_events = [{"event": "handshake_rx", "version": 3}] + phone.events

    def test_synthetic_pass(self):
        gate = {"bclcarlink_gate": True}
        self.assertEqual(self.verdict("synthetic", self.hu_events, self.phone_events, gate, True), "PASS")

    def test_synthetic_gate_fail_unless_overridden(self):
        gate = {"bclcarlink_gate": False}
        self.assertEqual(self.verdict("synthetic", [], [], gate, True), "GATE_A2DP_FAIL")
        self.assertEqual(self.verdict("synthetic", self.hu_events, self.phone_events, gate, False), "PASS")

    def test_external_levels(self):
        self.assertEqual(self.verdict("external", self.hu_events, [], None, True), "BCL_KNOCK_SEEN")
        init_only = [e for e in self.hu_events if e.get("cmd_name") != "KNOCK"]
        self.assertEqual(self.verdict("external", init_only, [], None, True), "BCL_INIT_SEEN")
        self.assertEqual(self.verdict("external", [{"event": "rfcomm_connected"}], [], None, True), "RFCOMM_NO_INIT")
        self.assertEqual(self.verdict("external", [], [], None, True), "NO_RFCOMM")


if __name__ == "__main__":
    unittest.main()
