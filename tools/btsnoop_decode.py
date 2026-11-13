#!/usr/bin/env python3
"""Passive decode of a btsnoop capture: SDP records, RFCOMM sessions, AVDTP codecs.

Reads `btmon -w` (Linux monitor, datalink 2001) and Android/H4 btsnoop (1002).
Answers the B1/B2 questions without Wireshark: which services and RFCOMM
channels the peer offers, who opened which channel (SABM), what the first
payload was (AT/HFP or BCL classification via bcl_classify), which codecs.

  python3 tools/btsnoop_decode.py capture.btsnoop            # markdown summary
  python3 tools/btsnoop_decode.py capture.btsnoop --json     # full decode

Direction: `local` = sent by the BlueZ host of this capture, `remote` = received.
Epistemic: decodes what is in the capture; absence of a frame ≠ absence on air.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from bcl_classify import classify_bytes  # noqa: E402

PSM_SDP, PSM_RFCOMM, PSM_AVCTP, PSM_AVDTP, PSM_AVCTP_BROWSE = 0x0001, 0x0003, 0x0017, 0x0019, 0x001B

UUID16 = {
    0x0001: "SDP", 0x0003: "RFCOMM", 0x0008: "OBEX", 0x0017: "AVCTP", 0x0019: "AVDTP", 0x0100: "L2CAP",
    0x1101: "SPP", 0x1105: "OPP", 0x1108: "HSP", 0x110A: "A2DP-Source", 0x110B: "A2DP-Sink",
    0x110C: "AVRCP-Target", 0x110D: "A2DP", 0x110E: "AVRCP", 0x110F: "AVRCP-Controller",
    0x1112: "HSP-AG", 0x1115: "PANU", 0x1116: "NAP", 0x111E: "HFP", 0x111F: "HFP-AG",
    0x112E: "PBAP-PCE", 0x112F: "PBAP-PSE", 0x1130: "PBAP", 0x1132: "MAP-MAS", 0x1133: "MAP-MNS",
    0x1134: "MAP", 0x1200: "PnP", 0x1203: "GenericAudio", 0x1204: "GenericTelephony",
}
ATTR = {0x0000: "handle", 0x0001: "classes", 0x0004: "protocols", 0x0009: "profiles",
        0x0100: "name", 0x0101: "description", 0x0102: "provider", 0x0311: "features"}
RFCOMM_FRAMES = {0x2F: "SABM", 0x63: "UA", 0x0F: "DM", 0x43: "DISC", 0xEF: "UIH"}
AVDTP_SIGNALS = {1: "DISCOVER", 2: "GET_CAPS", 3: "SET_CONF", 4: "GET_CONF", 5: "RECONF", 6: "OPEN",
                 7: "START", 8: "CLOSE", 9: "SUSPEND", 10: "ABORT", 11: "SECURITY", 12: "GET_ALL_CAPS",
                 13: "DELAY_REPORT"}
AVDTP_MSG = ("CMD", "GEN_REJ", "ACC", "REJ")
AVRCP_PDU = {0x10: "GetCapabilities", 0x11: "ListPlayerAppSettingAttributes", 0x12: "ListPlayerAppSettingValues",
             0x13: "GetCurrentPlayerAppSettingValue", 0x20: "GetElementAttributes", 0x30: "GetPlayStatus",
             0x31: "RegisterNotification", 0x50: "SetAbsoluteVolume", 0x60: "SetAddressedPlayer"}
AVRCP_CTYPE = {0x0: "CONTROL", 0x1: "STATUS", 0x3: "NOTIFY", 0x8: "NOT_IMPLEMENTED", 0x9: "ACCEPTED",
               0xA: "REJECTED", 0xC: "STABLE", 0xD: "CHANGED", 0xF: "INTERIM"}
AVRCP_BROWSE = {0x69: "SetBrowsedPlayer", 0x71: "GetFolderItems",
                 0x72: "ChangePath", 0x73: "GetItemAttributes", 0x80: "Search", 0xA0: "GeneralReject"}
PASS_THROUGH = {0x41: "VOLUME_UP", 0x42: "VOLUME_DOWN", 0x44: "PLAY", 0x45: "STOP", 0x46: "PAUSE",
                0x4B: "FORWARD", 0x4C: "BACKWARD", 0x48: "REWIND", 0x49: "FAST_FORWARD"}
CODECS = {0x00: "SBC", 0x01: "MPEG-1,2", 0x02: "AAC", 0x04: "ATRAC", 0xFF: "vendor"}


# ── SDP data elements ────────────────────────────────────────────────────────

def uuid_str(raw: bytes) -> str:
    if len(raw) == 2:
        u = int.from_bytes(raw, "big")
        return f"0x{u:04x}"
    if len(raw) == 4:
        return f"0x{int.from_bytes(raw, 'big'):08x}"
    h = raw.hex()
    base = h[8:] == "00001000800000805f9b34fb"
    if base and h[:4] == "0000":
        return f"0x{h[4:8]}"
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def uuid_label(u: str) -> str:
    if u.startswith("0x") and len(u) == 6:
        name = UUID16.get(int(u, 16))
        return f"{u} {name}" if name else u
    return u


def parse_element(buf: bytes, i: int = 0):
    """SDP data element at buf[i] → (value, next index). UUIDs come back as `("uuid", str)`."""
    h = buf[i]
    typ, size = h >> 3, h & 7
    i += 1
    if typ == 0:
        return None, i
    if size < 5:
        n = (1, 2, 4, 8, 16)[size]
    else:
        width = (1, 2, 4)[size - 5]
        n = int.from_bytes(buf[i:i + width], "big")
        i += width
    raw = buf[i:i + n]
    end = i + n
    if len(raw) != n:
        raise ValueError("truncated SDP element")
    if typ == 1:
        return int.from_bytes(raw, "big"), end
    if typ == 2:
        return int.from_bytes(raw, "big", signed=True), end
    if typ == 3:
        return ("uuid", uuid_str(raw)), end
    if typ in (4, 8):
        return raw.decode("utf-8", "replace").rstrip("\x00"), end
    if typ == 5:
        return bool(raw[0]), end
    if typ in (6, 7):
        items, k = [], 0
        while k < n:
            v, k = parse_element(raw, k)
            items.append(v)
        return items, end
    return raw.hex(), end


def _uuids(v) -> list[str]:
    if isinstance(v, tuple) and v[0] == "uuid":
        return [v[1]]
    if isinstance(v, list):
        return [u for x in v for u in _uuids(x)]
    return []


def normalize_record(attrs: list) -> dict:
    """Flat SDP attribute list [id, value, id, value, …] → readable record."""
    raw = {attrs[k]: attrs[k + 1] for k in range(0, len(attrs) - 1, 2) if isinstance(attrs[k], int)}
    rec: dict = {"handle": raw.get(0x0000)}
    rec["classes"] = [uuid_label(u) for u in _uuids(raw.get(0x0001))]
    for key in ("name", "description", "provider"):
        attr_id = {"name": 0x0100, "description": 0x0101, "provider": 0x0102}[key]
        if isinstance(raw.get(attr_id), str):
            rec[key] = raw[attr_id]
    for layer in raw.get(0x0004) or []:
        if not isinstance(layer, list) or not layer:
            continue
        proto = _uuids(layer[:1])
        param = layer[1] if len(layer) > 1 and isinstance(layer[1], int) else None
        if proto == ["0x0003"] and param is not None:
            rec["rfcomm_channel"] = param
        elif proto == ["0x0100"] and param is not None:
            rec["l2cap_psm"] = param
        elif proto == ["0x0008"]:
            rec["obex"] = True
    profiles = {}
    for p in raw.get(0x0009) or []:
        if isinstance(p, list) and len(p) == 2 and isinstance(p[1], int):
            u = _uuids(p[:1])
            if u:
                profiles[uuid_label(u[0])] = f"{p[1] >> 8}.{p[1] & 0xFF}"
    if profiles:
        rec["profiles"] = profiles
    if isinstance(raw.get(0x0311), int):
        rec["features"] = f"0x{raw[0x0311]:04x}"
    rec["attr_ids"] = sorted(f"0x{a:04x}" for a in raw)
    return rec


# ── capture records ──────────────────────────────────────────────────────────

def iter_packets(data: bytes):
    """Yield (ts_us, adapter_index, kind, payload); kind in cmd/evt/acl_tx/acl_rx."""
    if data[:8] != b"btsnoop\0":
        raise ValueError("not a btsnoop file")
    link = struct.unpack(">I", data[12:16])[0]
    i = 16
    while i + 24 <= len(data):
        _olen, ilen, flags, _drops, ts = struct.unpack(">IIIIq", data[i:i + 24])
        pkt = data[i + 24:i + 24 + ilen]
        i += 24 + ilen
        if link == 2001:
            kind = {2: "cmd", 3: "evt", 4: "acl_tx", 5: "acl_rx"}.get(flags & 0xFFFF)
            idx = flags >> 16
        elif link == 1002 and pkt:
            kind = {1: "cmd", 2: "acl", 4: "evt"}.get(pkt[0])
            pkt, idx = pkt[1:], 0
            if kind == "acl":
                kind = "acl_rx" if flags & 1 else "acl_tx"
        elif link == 1001:
            idx = 0
            if flags & 2:
                kind = "evt" if flags & 1 else "cmd"
            else:
                kind = "acl_rx" if flags & 1 else "acl_tx"
        else:
            continue
        if kind:
            yield ts, idx, kind, pkt


def side(kind: str) -> str:
    return "local" if kind == "acl_tx" else "remote"


# ── decoder ──────────────────────────────────────────────────────────────────

class Decoder:
    def __init__(self) -> None:
        self.t0 = None
        self.handles: dict[str, dict] = {}
        self.l2cap: list[dict] = []
        self.sdp: dict[str, list] = {"remote": [], "local": []}
        self.rfcomm: list[dict] = []
        self.avdtp: list[dict] = []
        self.avctp = Counter()
        self.media_bytes = Counter()
        self._frag: dict = {}
        self._pending: dict = {}
        self._chan: dict = {}          # (idx, h, sender_kind, dest_cid) -> (psm, ordinal)
        self._psm_seen = Counter()
        self._sdp_buf = defaultdict(bytes)
        self._avdtp_label_seid: dict = {}

    def rel(self, ts: int) -> float:
        if self.t0 is None:
            self.t0 = ts
        return round((ts - self.t0) / 1e6, 3)

    # -- HCI ------------------------------------------------------------------

    def event(self, ts, idx, pkt) -> None:
        if len(pkt) < 2:
            return
        code = pkt[0]
        if code == 0x03 and len(pkt) >= 13 and pkt[2] == 0:
            h = struct.unpack("<H", pkt[3:5])[0]
            bd = ":".join(f"{b:02X}" for b in reversed(pkt[5:11]))
            self.handles[f"{idx}/{h}"] = {"bd": bd, "connected_t": self.rel(ts)}
        elif code == 0x05 and len(pkt) >= 6:
            h = struct.unpack("<H", pkt[3:5])[0]
            entry = self.handles.setdefault(f"{idx}/{h}", {})
            entry.update(disconnected_t=self.rel(ts), reason=f"0x{pkt[5]:02x}")

    def acl(self, ts, idx, kind, pkt) -> None:
        if len(pkt) < 4:
            return
        hf, ln = struct.unpack("<HH", pkt[:4])
        h, pb = hf & 0x0FFF, (hf >> 12) & 3
        key = (idx, h, kind)
        body = pkt[4:4 + ln]
        self._frag[key] = body if pb in (0, 2) else self._frag.get(key, b"") + body
        buf = self._frag[key]
        if len(buf) < 4:
            return
        l2len, cid = struct.unpack("<HH", buf[:4])
        if len(buf) < 4 + l2len:
            return
        self._frag[key] = b""
        payload = buf[4:4 + l2len]
        if cid == 0x0001:
            self.signaling(ts, idx, h, kind, payload)
            return
        psm, ordinal = self._chan.get((idx, h, kind, cid), (None, 0))
        if psm == PSM_SDP:
            self.sdp_pdu(idx, h, kind, payload)
        elif psm == PSM_RFCOMM:
            self.rfcomm_frame(ts, kind, payload)
        elif psm == PSM_AVDTP:
            if ordinal == 0:
                self.avdtp_signal(ts, kind, payload)
            else:
                self.media_bytes[side(kind)] += len(payload)
        elif psm in (PSM_AVCTP, PSM_AVCTP_BROWSE):
            self.avctp_frame(psm, kind, payload)

    def signaling(self, ts, idx, h, kind, payload) -> None:
        j = 0
        while j + 4 <= len(payload):
            code, _ident, ln = payload[j], payload[j + 1], struct.unpack("<H", payload[j + 2:j + 4])[0]
            d = payload[j + 4:j + 4 + ln]
            j += 4 + ln
            if code == 0x02 and len(d) >= 4:
                psm, scid = struct.unpack("<HH", d[:4])
                self._pending[(idx, h, scid)] = (psm, kind)
                self.l2cap.append({"t": self.rel(ts), "by": side(kind), "psm": f"0x{psm:04x}"})
            elif code == 0x03 and len(d) >= 8:
                dcid, scid, result = struct.unpack("<HHH", d[:6])
                if result != 0 or (idx, h, scid) not in self._pending:
                    continue
                psm, req_kind = self._pending.pop((idx, h, scid))
                ordinal = self._psm_seen[(idx, h, psm)]
                self._psm_seen[(idx, h, psm)] += 1
                rsp_kind = "acl_rx" if req_kind == "acl_tx" else "acl_tx"
                self._chan[(idx, h, req_kind, dcid)] = (psm, ordinal)
                self._chan[(idx, h, rsp_kind, scid)] = (psm, ordinal)
            elif code == 0x06 and len(d) >= 4:
                dcid, scid = struct.unpack("<HH", d[:4])
                other = "acl_rx" if kind == "acl_tx" else "acl_tx"
                gone = self._chan.pop((idx, h, kind, dcid), None)
                self._chan.pop((idx, h, other, scid), None)
                if gone:
                    psm = gone[0]
                    self._psm_seen[(idx, h, psm)] = max(0, self._psm_seen[(idx, h, psm)] - 1)

    # -- SDP ------------------------------------------------------------------

    def sdp_pdu(self, idx, h, kind, payload) -> None:
        if len(payload) < 7 or payload[0] not in (0x05, 0x07):
            return
        plen = struct.unpack(">H", payload[3:5])[0]
        p = payload[5:5 + plen]
        count = struct.unpack(">H", p[:2])[0]
        key = (idx, h, kind)
        self._sdp_buf[key] += p[2:2 + count]
        cont = p[2 + count:]
        if cont[:1] not in (b"\x00", b""):
            return
        blob = self._sdp_buf.pop(key)
        try:
            lists, _ = parse_element(blob, 0)
        except (ValueError, IndexError):
            return
        if not lists:
            return
        if not isinstance(lists[0], list):
            lists = [lists]
        for attrs in lists:
            if isinstance(attrs, list):
                rec = normalize_record(attrs)
                bucket = self.sdp[side(kind)]
                if rec not in bucket:
                    bucket.append(rec)

    # -- RFCOMM ---------------------------------------------------------------

    def rfcomm_frame(self, ts, kind, payload) -> None:
        if len(payload) < 3:
            return
        dlci = payload[0] >> 2
        ctrl = payload[1]
        name = RFCOMM_FRAMES.get(ctrl & 0xEF, f"0x{ctrl:02x}")
        ln = payload[2]
        off = 3 if ln & 1 else 4
        length = ln >> 1 if ln & 1 else (ln >> 1) | (payload[3] << 7)
        credits = None
        if name == "UIH" and ctrl & 0x10 and dlci != 0:
            credits = payload[off]
            off += 1
        data = payload[off:off + length]
        self.rfcomm.append({"t": self.rel(ts), "by": side(kind), "dlci": dlci, "channel": dlci >> 1,
                            "frame": name, "credits": credits, "data": data})

    def rfcomm_sessions(self) -> list[dict]:
        sessions, open_ = [], {}
        for f in self.rfcomm:
            if f["dlci"] == 0:
                continue
            d = f["dlci"]
            if f["frame"] == "SABM":
                open_[d] = {"channel": f["channel"], "dlci": d, "opened_by": f["by"], "t_open": f["t"],
                            "t_close": None, "closed_by": None, "accepted": None,
                            "frames": Counter(), "first_uih": None,
                            "bytes": {"local": b"", "remote": b""}}
                sessions.append(open_[d])
            s = open_.get(d)
            if s is None:
                continue
            s["frames"][f["frame"]] += 1
            if f["frame"] == "UIH" and f["data"] and s["first_uih"] is None:
                s["first_uih"] = {"t": f["t"], "by": f["by"], "len": len(f["data"]), "hex": f["data"][:64].hex()}
            if f["frame"] == "UA" and s["accepted"] is None:
                s["accepted"] = True
            elif f["frame"] == "DM" and s["accepted"] is None:
                s["accepted"] = False
                open_.pop(d)
            elif f["frame"] == "DISC":
                s["t_close"], s["closed_by"] = f["t"], f["by"]
                open_.pop(d)
            elif f["frame"] == "UIH" and f["data"]:
                s["bytes"][f["by"]] += f["data"]
        for s in sessions:
            server = "remote" if s["opened_by"] == "local" else "local"
            svc = next((r for r in self.sdp[server] if r.get("rfcomm_channel") == s["channel"]), None)
            s["server"] = server
            s["service"] = (svc.get("name") or ", ".join(svc["classes"])) if svc else None
            raw = s.pop("bytes")
            s["frames"] = dict(s["frames"])
            s["bytes_local"], s["bytes_remote"] = len(raw["local"]), len(raw["remote"])
            s["payload"] = classify_session(raw["local"], raw["remote"])
        return sessions

    # -- AVDTP / AVCTP ---------------------------------------------------------

    def avdtp_signal(self, ts, kind, p) -> None:
        if len(p) < 2 or (p[0] >> 2) & 3:
            return
        label, msg = p[0] >> 4, p[0] & 3
        sig = p[1] & 0x3F
        entry = {"t": self.rel(ts), "by": side(kind), "signal": AVDTP_SIGNALS.get(sig, sig),
                 "msg": AVDTP_MSG[msg]}
        if sig in (2, 12) and msg == 0 and len(p) >= 3:
            self._avdtp_label_seid[label] = p[2] >> 2
        elif sig in (2, 12) and msg == 2:
            entry["seid"] = self._avdtp_label_seid.get(label)
            entry["caps"] = parse_service_caps(p[2:])
        elif sig == 3 and msg == 0 and len(p) >= 4:
            entry["seid"] = p[2] >> 2
            entry["caps"] = parse_service_caps(p[4:])
        elif sig == 1 and msg == 2:
            entry["endpoints"] = [{"seid": p[k] >> 2, "in_use": bool(p[k] & 2), "sink": bool(p[k + 1] & 8)}
                                  for k in range(2, len(p) - 1, 2)]
        self.avdtp.append(entry)

    def avctp_frame(self, psm, kind, p) -> None:
        if psm == PSM_AVCTP_BROWSE:
            # Browsing runs in L2CAP ERTM: 2-byte control in front, 2-byte FCS at the end.
            if len(p) < 2 or p[0] & 1:
                self.avctp[f"browse {side(kind)} ertm s-frame"] += 1
                return
            p = p[2:-2]
            if len(p) >= 4:
                label = AVRCP_BROWSE.get(p[3], f"0x{p[3]:02x}")
                status = f" status 0x{p[6]:02x}" if p[0] & 2 and len(p) >= 7 else ""
                self.avctp[f"browse {side(kind)} {label}{status}"] += 1
        elif len(p) >= 7 and p[4] == 0x48 and p[5] == 0x7C:
            op = PASS_THROUGH.get(p[6] & 0x7F, f"0x{p[6] & 0x7F:02x}")
            state = "released" if p[6] & 0x80 else "pressed"
            ctype = AVRCP_CTYPE.get(p[3] & 0x0F, f"0x{p[3] & 0x0F:x}")
            self.avctp[f"pass-through {side(kind)} {ctype} {op} {state}"] += 1
        elif len(p) >= 10 and p[6:9] == b"\x00\x19\x58":
            ctype = AVRCP_CTYPE.get(p[3] & 0x0F, f"0x{p[3] & 0x0F:x}")
            pdu = AVRCP_PDU.get(p[9], f"0x{p[9]:02x}")
            # RegisterNotification: first parameter is the event id (or the error code if REJECTED)
            arg = f" 0x{p[13]:02x}" if p[9] == 0x31 and len(p) >= 14 else ""
            self.avctp[f"avrcp {side(kind)} {ctype} {pdu}{arg}"] += 1
        else:
            self.avctp[f"avctp {side(kind)} other"] += 1

    def summary(self) -> dict:
        return {
            "handles": self.handles,
            "l2cap_connects": self.l2cap,
            "sdp_remote": self.sdp["remote"],
            "sdp_local": self.sdp["local"],
            "rfcomm_sessions": self.rfcomm_sessions(),
            "avdtp": self.avdtp,
            "a2dp_media_bytes": dict(self.media_bytes),
            "avctp": dict(self.avctp),
        }


def parse_service_caps(b: bytes) -> list[dict]:
    caps, i = [], 0
    while i + 2 <= len(b):
        cat, ln = b[i], b[i + 1]
        v = b[i + 2:i + 2 + ln]
        i += 2 + ln
        if cat == 7 and len(v) >= 2:
            c = {"codec": CODECS.get(v[1], f"0x{v[1]:02x}"), "info": v[2:].hex()}
            if v[1] == 0 and len(v) >= 6:
                c.update(sbc_fields(v[2:6]))
            elif v[1] == 2 and len(v) >= 8:
                c.update(aac_fields(v[2:8]))
            caps.append(c)
        elif cat == 4 and len(v) >= 2:
            caps.append({"content_protection": "SCMS-T" if v[:2] == b"\x02\x00" else v.hex()})
        elif cat == 8:
            caps.append({"delay_reporting": True})
    return caps


def _bits(value: int, table: list[tuple[int, str]]) -> list[str]:
    return [name for mask, name in table if value & mask]


def sbc_fields(b: bytes) -> dict:
    """A2DP spec 4.3.2: one bit per supported value; a configuration has exactly one per field."""
    return {
        "rates": _bits(b[0], [(0x80, "16000"), (0x40, "32000"), (0x20, "44100"), (0x10, "48000")]),
        "modes": _bits(b[0], [(0x08, "mono"), (0x04, "dual"), (0x02, "stereo"), (0x01, "joint")]),
        "blocks": _bits(b[1], [(0x80, "4"), (0x40, "8"), (0x20, "12"), (0x10, "16")]),
        "subbands": _bits(b[1], [(0x08, "4"), (0x04, "8")]),
        "allocation": _bits(b[1], [(0x02, "snr"), (0x01, "loudness")]),
        "bitpool": [b[2], b[3]],
    }


def aac_fields(b: bytes) -> dict:
    """A2DP spec 4.5.2: object type, 12-bit rate mask, channels, VBR, 23-bit bitrate."""
    rates = ["8000", "11025", "12000", "16000", "22050", "24000", "32000", "44100", "48000", "64000",
             "88200", "96000"]
    rate_mask = (b[1] << 4) | (b[2] >> 4)
    return {
        "object_types": _bits(b[0], [(0x80, "MPEG-2 AAC LC"), (0x40, "MPEG-4 AAC LC"), (0x20, "MPEG-4 LTP"),
                                     (0x10, "MPEG-4 scalable")]),
        "rates": [r for k, r in enumerate(rates) if rate_mask & (0x800 >> k)],
        "channels": _bits(b[2], [(0x08, "1"), (0x04, "2")]),
        "vbr": bool(b[3] & 0x80),
        "bitrate": ((b[3] & 0x7F) << 16) | (b[4] << 8) | b[5],
    }


def classify_session(local: bytes, remote: bytes) -> dict:
    first = remote if remote[:2] in (b"AT", b"at") else local
    if first[:2] in (b"AT", b"at") or local[:2] in (b"\r\n",):
        return {"kind": "AT", **at_dialog(local, remote)}
    out = {"kind": "binary" if (local or remote) else "empty"}
    for name, data in (("local", local), ("remote", remote)):
        if data:
            c = classify_bytes(data)
            out[name] = {"bcl_classification": c["bcl_classification"], "len": len(data),
                         "head": data[:16].hex(), "handshake": c.get("handshake")}
    return out


def at_dialog(local: bytes, remote: bytes) -> dict:
    def lines(b):
        return [ln.strip() for ln in b.decode("ascii", "replace").replace("\r", "\n").split("\n") if ln.strip()]
    cmds, resp = lines(remote), lines(local)
    if local[:2] in (b"AT", b"at"):
        cmds, resp = lines(local), lines(remote)
    last_cmd = cmds[-1] if cmds else None
    failed = resp[-1] == "ERROR" if resp else False
    return {"commands": cmds, "responses": resp, "last_command": last_cmd, "ends_with_error": failed}


def decode(data: bytes) -> dict:
    dec = Decoder()
    for ts, idx, kind, pkt in iter_packets(data):
        dec.rel(ts)
        if kind == "evt":
            dec.event(ts, idx, pkt)
        elif kind in ("acl_tx", "acl_rx"):
            dec.acl(ts, idx, kind, pkt)
    return dec.summary()


def evidence_rows(out: dict, session_prefix: str, hci_adapter: str | None, local_bdaddr: str | None) -> list[dict]:
    """One row per RFCOMM session in the capture schema of BCL_RFCOMM_TWO_MODE_20261113.md."""
    remote = next(iter(out["handles"].values()), {}).get("bd")
    rows = []
    for n, s in enumerate(out["rfcomm_sessions"], 1):
        first = s["first_uih"] or {}
        rows.append({
            "session_id": f"{session_prefix}-rfcomm{n}",
            "hci_adapter": hci_adapter, "local_bdaddr": local_bdaddr, "remote_bdaddr": remote,
            "hci_timestamp": s["t_open"], "rfcomm_channel": s["channel"], "rfcomm_dlci": s["dlci"],
            "opened_by": s["opened_by"], "service": s["service"],
            "sabm": s["frames"].get("SABM", 0), "ua": s["frames"].get("UA", 0), "dm": s["frames"].get("DM", 0),
            "disc": s["frames"].get("DISC", 0), "uih": s["frames"].get("UIH", 0),
            "payload_length": s["bytes_local"] + s["bytes_remote"], "payload_hex": first.get("hex"),
            "first_uih_timestamp": first.get("t"), "first_uih_direction": first.get("by"),
            "connection_state": ("rejected" if s["accepted"] is False else
                                 f"closed_by_{s['closed_by']}" if s["closed_by"] else "open_at_end"),
            "payload_kind": s["payload"]["kind"],
            "bcl_classification": max((v["bcl_classification"] for v in s["payload"].values()
                                       if isinstance(v, dict)), default="UNKNOWN", key=_bcl_rank),
        })
    return rows


def _bcl_rank(level: str) -> int:
    order = ["UNKNOWN", "BCL_CANDIDATE", "STRONG_BCL_CANDIDATE", "BCL_FIELD_CONFIRMED"]
    return order.index(level) if level in order else 0


def to_markdown(out: dict, title: str) -> str:
    md = [f"# {title}", ""]
    for key, h in out["handles"].items():
        md.append(f"- ACL `{key}` → `{h.get('bd')}` connected {h.get('connected_t')} s"
                  + (f", disconnected {h['disconnected_t']} s reason {h['reason']}" if "disconnected_t" in h else ""))
    md += ["", "## SDP records of the remote device", "",
           "| Handle | Name | Classes | RFCOMM | L2CAP PSM | Profiles |", "|---|---|---|---|---|---|"]
    for r in sorted(out["sdp_remote"], key=lambda r: (r.get("rfcomm_channel") or 99, r.get("l2cap_psm") or 0)):
        md.append(f"| {r.get('handle')} | {r.get('name', '')} | {', '.join(r['classes'])} | "
                  f"{r.get('rfcomm_channel', '')} | {r.get('l2cap_psm', '')} | "
                  f"{', '.join(f'{k} {v}' for k, v in r.get('profiles', {}).items())} |")
    md += ["", "## RFCOMM sessions", "",
           "| t open | Channel | Opened by | Service | Accepted | Closed by | Payload |", "|---|---|---|---|---|---|---|"]
    for s in out["rfcomm_sessions"]:
        p = s["payload"]
        if p["kind"] == "AT":
            what = f"AT, last `{p['last_command']}`" + (" → ERROR" if p["ends_with_error"] else "")
        else:
            what = "; ".join(f"{k}: {v['bcl_classification']} ({v['len']} B)" for k, v in p.items()
                             if isinstance(v, dict)) or p["kind"]
        md.append(f"| {s['t_open']} | {s['channel']} | {s['opened_by']} | {s['service'] or '?'} | "
                  f"{s['accepted']} | {s['closed_by'] or '-'} | {what} |")
    md += ["", "## AVDTP", ""]
    for a in out["avdtp"]:
        extra = ""
        if a.get("caps"):
            extra = " " + json.dumps(a["caps"])
        if a.get("endpoints"):
            extra = " " + json.dumps(a["endpoints"])
        md.append(f"- {a['t']} s {a['by']} {a['signal']} {a['msg']}"
                  + (f" seid {a['seid']}" if a.get("seid") is not None else "") + extra)
    md += ["", f"A2DP media bytes: `{json.dumps(out['a2dp_media_bytes'])}`", ""]
    return "\n".join(md)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", type=Path)
    ap.add_argument("--json", action="store_true", help="full decode as JSON")
    ap.add_argument("--session-id", help="prefix for evidence rows (default: capture stem)")
    ap.add_argument("--hci-adapter", help="adapter name for evidence rows, e.g. hci2")
    ap.add_argument("--local-bdaddr", help="local BD address for evidence rows")
    args = ap.parse_args()
    out = decode(args.capture.read_bytes())
    out["evidence_rows"] = evidence_rows(out, args.session_id or args.capture.stem,
                                         args.hci_adapter, args.local_bdaddr)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(to_markdown(out, args.capture.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
