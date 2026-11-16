import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_dummy_hu import (  # noqa: E402
    CMD_DATAACK,
    CMD_HANDSHAKE,
    CMD_KNOCK,
    CMD_OPEN,
    CMD_SELECTPROTO,
    DummyHuSession,
    HU_PROFILES,
    PhoneClientSession,
    apply_hu_profile,
    build_dataack,
    build_handshake,
    dataack_count_for_frame,
    summarize,
)
from bcl_etch_stub import (  # noqa: E402
    KNOCK_UUID_SERIAL,
    wrap_etch_body,
)
from bcl_framer import (  # noqa: E402
    DEST_ETCH_DESK,
    DEST_WATCHDOG_DESK,
    INIT_MAGIC,
    BclFrame,
    BclFramer,
    build_synthetic_frame,
)


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

    def test_f20_profile_handshake_fingerprint(self):
        p = apply_hu_profile("f20")
        hu = DummyHuSession(**{k: p[k] for k in (
            "version", "instance_id", "buffer_size", "echo_watchdog",
            "send_dataack", "etch_stub", "sas_probe", "handshake_delay_s",
        )})
        (hs,) = hu.on_bytes(INIT_MAGIC)
        self.assertEqual(hs, build_handshake(5, 14, 0x4000))
        self.assertEqual(HU_PROFILES["f20"]["version"], 5)

    def test_dataack_open_is_8(self):
        hu = DummyHuSession(send_dataack=True, sas_probe="dataack")
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        replies = hu.on_bytes(open_fr)
        self.assertEqual(replies[0], build_dataack(8))
        fr = frames_of(replies)[0]
        self.assertEqual(fr.cmd, CMD_DATAACK)
        self.assertEqual(fr.payload, b"\x00\x00\x00\x08")

    def test_dataack_8_plus_len_wire_values(self):
        # FIELD: 10=SP, 44=KNOCK-ish, 4008=8+4000 fragment limit
        self.assertEqual(
            dataack_count_for_frame(
                BclFrame(5, 0, 0, 2, b"\x00\x04", b"")
            ),
            10,
        )
        self.assertEqual(
            dataack_count_for_frame(
                BclFrame(8, 0, 0, 36, bytes(36), b"")
            ),
            44,
        )
        self.assertEqual(
            dataack_count_for_frame(
                BclFrame(2, 12, DEST_ETCH_DESK, 4000, bytes(4000), b"")
            ),
            4008,
        )

    def test_dataack_wd_then_echo(self):
        hu = DummyHuSession(echo_watchdog=True, send_dataack=True, sas_probe="none")
        ping = PhoneClientSession().watchdog_ping()
        replies = hu.on_bytes(ping)
        self.assertEqual(len(replies), 2)
        ack, echo = frames_of(replies)
        self.assertEqual(ack.cmd, CMD_DATAACK)
        self.assertEqual(ack.payload, b"\x00\x00\x00\x0c")  # 8+4
        self.assertEqual(echo.dest, 1)

    def test_etch_stub_challenge_after_pkcs7(self):
        hu = DummyHuSession(etch_stub=True, send_dataack=True, sas_probe="challenge")
        pem = b"-----BEGIN PKCS7-----\nabc\n-----END PKCS7-----\n"
        body = wrap_etch_body(b"\x00" * 16 + pem)
        data = build_synthetic_frame(2, 10, DEST_ETCH_DESK, body)
        replies = hu.on_bytes(data)
        # DATAACK + etch challenge DATA
        self.assertGreaterEqual(len(replies), 2)
        frames = frames_of(replies)
        self.assertEqual(frames[0].cmd, CMD_DATAACK)
        etch_tx = [f for f in frames if f.cmd == 2 and f.src == DEST_ETCH_DESK]
        self.assertEqual(len(etch_tx), 1)
        self.assertTrue(any(e["event"] == "sas_challenge_tx" for e in hu.events))

    def test_sas_probe_none_silent_on_open(self):
        hu = DummyHuSession(send_dataack=True, sas_probe="none")
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        replies = hu.on_bytes(open_fr)
        self.assertEqual(replies, [build_dataack(8)])
        self.assertFalse(any(e["event"] == "sas_challenge_tx" for e in hu.events))

    def test_sas_probe_challenge_on_open(self):
        hu = DummyHuSession(send_dataack=True, sas_probe="challenge")
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        replies = hu.on_bytes(open_fr)
        frames = frames_of(replies)
        self.assertEqual(frames[0].cmd, CMD_DATAACK)
        etch_tx = [f for f in frames if f.cmd == 2]
        self.assertEqual(len(etch_tx), 1)
        self.assertTrue(any(e["event"] == "sas_challenge_tx" for e in hu.events))

    def test_sas_probe_challenge_rhmi_on_open(self):
        hu = DummyHuSession(send_dataack=True, sas_probe="challenge_rhmi")
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        frames = frames_of(hu.on_bytes(open_fr))
        etch_tx = [f for f in frames if f.cmd == 2]
        self.assertEqual(len(etch_tx), 2)
        self.assertTrue(any(e["event"] == "rhmi_capabilities_tx" for e in hu.events))

    def test_phone_tx_classified_on_every_frame(self):
        hu = DummyHuSession(sas_probe="none")
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        hu.on_bytes(open_fr)
        cls = [e for e in hu.events if e.get("event") == "phone_tx_classified"]
        self.assertEqual(len(cls), 1)
        self.assertIn("OPEN_ETCH", cls[0]["tags"])

    def test_sas_probe_adaptive_escalates_after_phone_etch(self):
        hu = DummyHuSession(send_dataack=True, sas_probe="adaptive")
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        frames = frames_of(hu.on_bytes(open_fr))
        etch_tx = [f for f in frames if f.cmd == 2]
        self.assertEqual(len(etch_tx), 1)  # challenge only
        self.assertFalse(any(e["event"] == "rhmi_capabilities_tx" for e in hu.events))
        # Phone etch TX after challenge → RHMI escalate
        body = wrap_etch_body(b"Z" * 40)
        data = build_synthetic_frame(2, 10, DEST_ETCH_DESK, body)
        frames2 = frames_of(hu.on_bytes(data))
        etch2 = [f for f in frames2 if f.cmd == 2]
        self.assertGreaterEqual(len(etch2), 1)
        self.assertTrue(any(e["event"] == "rhmi_capabilities_tx" for e in hu.events))

    def test_hu_open_srcs_after_knock(self):
        hu = DummyHuSession(sas_probe="none", hu_open_srcs=(10, 12))
        knock = build_synthetic_frame(CMD_KNOCK, 0, 0, bytes(12))
        frames = frames_of(hu.on_bytes(knock))
        opens = [f for f in frames if f.cmd == CMD_OPEN]
        self.assertEqual([(o.src, o.dest) for o in opens], [(10, DEST_ETCH_DESK), (12, DEST_ETCH_DESK)])
        self.assertTrue(any(e["event"] == "hu_open_tx" for e in hu.events))

    def test_etch_reply_src_field_shape(self):
        hu = DummyHuSession(
            send_dataack=True, sas_probe="challenge", etch_reply_src=12
        )
        open_fr = build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK)
        frames = frames_of(hu.on_bytes(open_fr))
        etch_tx = [f for f in frames if f.cmd == 2]
        self.assertEqual(len(etch_tx), 1)
        self.assertEqual((etch_tx[0].src, etch_tx[0].dest), (12, DEST_ETCH_DESK))

    def test_f20_profile_mirrors_phone_src_on_etch_reply(self):
        from bcl_dummy_hu import apply_hu_profile

        prof = apply_hu_profile("f20")
        hu = DummyHuSession(**prof)
        for ch_src in (10, 15):
            frames = frames_of(hu.on_bytes(build_synthetic_frame(CMD_OPEN, ch_src, DEST_ETCH_DESK)))
            etch_tx = [f for f in frames if f.cmd == 2]
            self.assertEqual(len(etch_tx), 1)
            self.assertEqual((etch_tx[0].src, etch_tx[0].dest), (ch_src, DEST_ETCH_DESK))

    def test_knock_envelope_accepted(self):
        hu = DummyHuSession(sas_probe="none")
        blob = (
            bytes.fromhex("deadbeefdead010000002c0101")
            + KNOCK_UUID_SERIAL
            + b"\x00"
            + bytes.fromhex("deadbeefbeef")
        )
        self.assertEqual(hu.on_bytes(blob), [])
        self.assertTrue(hu.knocked)
        self.assertTrue(any(e["event"] == "knock_envelope_rx" for e in hu.events))

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

    def test_version5_auto_sp4_and_wire_knock(self):
        hu, phone = DummyHuSession(version=5, instance_id=14, buffer_size=0x4000), PhoneClientSession()
        to_phone = hu.on_bytes(phone.session_init())
        sent = frames_of(phone.on_bytes(to_phone[0]))
        self.assertEqual(sent[0].cmd, CMD_SELECTPROTO)
        self.assertEqual(sent[0].payload, b"\x00\x04")
        self.assertEqual(sent[1].cmd, CMD_KNOCK)
        self.assertGreater(sent[1].length, 12)  # UUID knock
        for f in sent:
            hu.on_bytes(f.raw)
        self.assertEqual(hu.selected_proto, 4)
        self.assertEqual(hu.last_knock.get("appType"), 1)
        self.assertEqual(hu.last_knock.get("param1"), 7)

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
