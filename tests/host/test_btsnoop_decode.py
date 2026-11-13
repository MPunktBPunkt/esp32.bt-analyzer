"""Host tests for tools/btsnoop_decode.py (synthetic captures only)."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_framer import INIT_MAGIC, build_synthetic_frame  # noqa: E402
from btsnoop_decode import aac_fields, decode, evidence_rows, parse_element, sbc_fields  # noqa: E402

BD = "D4:36:39:CF:E1:B5"
H = 0x81


# ── SDP data element encoders ───────────────────────────────────────────────

def de_u8(v): return bytes([0x08, v])
def de_u16(v): return b"\x09" + struct.pack(">H", v)
def de_uuid16(v): return b"\x19" + struct.pack(">H", v)
def de_str(s): return bytes([0x25, len(s)]) + s.encode()
def de_seq(*items):
    body = b"".join(items)
    return bytes([0x35, len(body)]) + body


def spp_record(handle: int, channel: int, name: str) -> bytes:
    return de_seq(
        de_u16(0x0000), b"\x0a" + struct.pack(">I", handle),
        de_u16(0x0001), de_seq(de_uuid16(0x1101)),
        de_u16(0x0004), de_seq(de_seq(de_uuid16(0x0100)), de_seq(de_uuid16(0x0003), de_u8(channel))),
        de_u16(0x0009), de_seq(de_seq(de_uuid16(0x1101), de_u16(0x0102))),
        de_u16(0x0100), de_str(name),
    )


# ── capture builders ────────────────────────────────────────────────────────

class Capture:
    def __init__(self, link: int = 2001):
        self.link = link
        self.records: list[bytes] = []
        self.ts = 0x00E03AB44A676000

    def add(self, kind: str, pkt: bytes) -> None:
        self.ts += 1000
        if self.link == 2001:
            flags = {"cmd": 2, "evt": 3, "acl_tx": 4, "acl_rx": 5}[kind]
        else:
            pkt = bytes([{"cmd": 1, "evt": 4, "acl_tx": 2, "acl_rx": 2}[kind]]) + pkt
            flags = (1 if kind in ("acl_rx", "evt") else 0) | (2 if kind in ("cmd", "evt") else 0)
        self.records.append(struct.pack(">IIIIq", len(pkt), len(pkt), flags, 0, self.ts) + pkt)

    def conn_complete(self) -> None:
        bd = bytes(int(x, 16) for x in reversed(BD.split(":")))
        self.add("evt", bytes([0x03, 11, 0]) + struct.pack("<H", H) + bd + b"\x01\x00")

    def l2cap(self, kind: str, cid: int, payload: bytes) -> None:
        l2 = struct.pack("<HH", len(payload), cid) + payload
        self.add(kind, struct.pack("<HH", H | (2 << 12), len(l2)) + l2)

    def connect(self, by: str, psm: int, scid: int, dcid: int) -> None:
        other = "acl_rx" if by == "acl_tx" else "acl_tx"
        self.l2cap(by, 1, bytes([0x02, 1]) + struct.pack("<HHH", 4, psm, scid))
        self.l2cap(other, 1, bytes([0x03, 1]) + struct.pack("<HHHHH", 8, dcid, scid, 0, 0))

    def bytes(self) -> bytes:
        return b"btsnoop\0" + struct.pack(">II", 1, self.link) + b"".join(self.records)


def rfcomm(dlci: int, ctrl: int, data: bytes = b"", credits: int | None = None) -> bytes:
    body = (bytes([credits]) if credits is not None else b"") + data
    return bytes([(dlci << 2) | 0x03, ctrl, (len(data) << 1) | 1]) + body + b"\x00"


def scenario(link: int = 2001) -> bytes:
    """Local reads remote SDP, opens channel 6 and sends BCL; remote opens channel 13 for HFP."""
    c = Capture(link)
    c.conn_complete()
    c.connect("acl_tx", 0x0001, 0x0040, 0x0050)
    blob = de_seq(spp_record(0x10009, 6, "SPP Server 1"), spp_record(0x10001, 5, "SPP Server 0"))
    half = len(blob) // 2
    for i, (part, cont) in enumerate(((blob[:half], b"\x01\x07"), (blob[half:], b"\x00"))):
        params = struct.pack(">H", len(part)) + part + cont
        c.l2cap("acl_rx", 0x0040, bytes([0x07]) + struct.pack(">HH", i, len(params)) + params)
    c.connect("acl_tx", 0x0003, 0x0041, 0x0051)
    c.l2cap("acl_tx", 0x0051, rfcomm(12, 0x3F))
    c.l2cap("acl_rx", 0x0041, rfcomm(12, 0x73))
    hello = INIT_MAGIC + build_synthetic_frame(4, 0, 0, struct.pack(">HHI", 3, 14, 0x8000))
    c.l2cap("acl_tx", 0x0051, rfcomm(12, 0xFF, hello, credits=7))
    c.l2cap("acl_rx", 0x0041, rfcomm(12, 0xFF, b"", credits=33))
    c.l2cap("acl_tx", 0x0051, rfcomm(12, 0x53))
    c.connect("acl_rx", 0x0003, 0x0060, 0x0042)
    c.l2cap("acl_rx", 0x0042, rfcomm(27, 0x3F))
    c.l2cap("acl_tx", 0x0060, rfcomm(27, 0x73))
    c.l2cap("acl_rx", 0x0042, rfcomm(27, 0xEF, b"AT+CHLD=?\r"))
    c.l2cap("acl_tx", 0x0060, rfcomm(27, 0xEF, b"\r\nERROR\r\n"))
    c.l2cap("acl_rx", 0x0042, rfcomm(27, 0x53))
    return c.bytes()


class TestElements(unittest.TestCase):
    def test_uuid128_and_base(self):
        raw = b"\x1c" + bytes.fromhex("00000000decafadedecadeafdecacaff")
        self.assertEqual(parse_element(raw)[0], ("uuid", "00000000-deca-fade-deca-deafdecacaff"))
        base = b"\x1c" + bytes.fromhex("0000110100001000800000805f9b34fb")
        self.assertEqual(parse_element(base)[0], ("uuid", "0x1101"))

    def test_sbc_and_aac_fields(self):
        cfg = sbc_fields(bytes.fromhex("11150235"))
        self.assertEqual((cfg["rates"], cfg["modes"], cfg["blocks"], cfg["subbands"], cfg["bitpool"]),
                         (["48000"], ["joint"], ["16"], ["8"], [2, 53]))
        aac = aac_fields(bytes.fromhex("c0018c800080"))
        self.assertEqual(aac["rates"], ["44100", "48000"])
        self.assertTrue(aac["vbr"])


class TestDecode(unittest.TestCase):
    def check(self, out):
        self.assertEqual(out["handles"][f"0/{H}"]["bd"], BD)
        chans = sorted(r["rfcomm_channel"] for r in out["sdp_remote"])
        self.assertEqual(chans, [5, 6])
        ch6 = next(r for r in out["sdp_remote"] if r["rfcomm_channel"] == 6)
        self.assertEqual(ch6["name"], "SPP Server 1")
        self.assertEqual(ch6["profiles"], {"0x1101 SPP": "1.2"})

        bcl, hfp = out["rfcomm_sessions"]
        self.assertEqual((bcl["channel"], bcl["opened_by"], bcl["closed_by"]), (6, "local", "local"))
        self.assertEqual(bcl["service"], "SPP Server 1")
        self.assertTrue(bcl["accepted"])
        self.assertEqual(bcl["payload"]["local"]["bcl_classification"], "BCL_FIELD_CONFIRMED")
        self.assertNotIn("remote", bcl["payload"])

        self.assertEqual((hfp["channel"], hfp["opened_by"], hfp["server"]), (13, "remote", "local"))
        self.assertEqual(hfp["payload"]["kind"], "AT")
        self.assertEqual(hfp["payload"]["last_command"], "AT+CHLD=?")
        self.assertTrue(hfp["payload"]["ends_with_error"])

    def test_monitor_format(self):
        self.check(decode(scenario(2001)))

    def test_evidence_rows(self):
        rows = evidence_rows(decode(scenario()), "S", "hci2", "C8:C9:A3:CB:37:96")
        bcl, hfp = rows
        self.assertEqual(bcl["session_id"], "S-rfcomm1")
        self.assertEqual((bcl["remote_bdaddr"], bcl["rfcomm_dlci"]), (BD, 12))
        self.assertEqual((bcl["sabm"], bcl["ua"], bcl["uih"], bcl["disc"]), (1, 1, 2, 1))
        self.assertEqual(bcl["first_uih_direction"], "local")
        self.assertTrue(bcl["payload_hex"].startswith(INIT_MAGIC.hex()))
        self.assertEqual(bcl["bcl_classification"], "BCL_FIELD_CONFIRMED")
        self.assertEqual((hfp["connection_state"], hfp["payload_kind"]), ("closed_by_remote", "AT"))

    def test_h4_format(self):
        self.check(decode(scenario(1002)))

    def test_rejects_non_btsnoop(self):
        with self.assertRaises(ValueError):
            decode(b"not a capture")


if __name__ == "__main__":
    unittest.main()
