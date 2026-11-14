#!/usr/bin/env python3
"""Minimal lab Etch/SAS/CDS stub for Dummy-HU (not a full Apache Etch stack).

After Phone→HU PKCS7 on BCL dest 4004, emit a challenge-shaped reply and accept
follow-up login/CDS probes so lab jsonl captures phone RPC beyond cert push.

Epistemic: LAB stub only — crypto not verified; framing mirrors observed
deadbeef + u32BE(len) envelopes from LAB_DUMMY_ETCH_*.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field

ETCH_MAGIC = b"\xde\xad\xbe\xef"
# 16-byte prefix observed before PEM in lab Phone→HU cert msgs (src10).
_LAB_ETCH_HDR = bytes.fromhex("0386304ba8bb0286144a776f8b8517c7")
_LAB_ETCH_TRAILER = bytes.fromhex("866306b46887000001a1da8f000081")

# CDS property → JSON value (BMWConnectedAnalysis/cds table, stub constants).
CDS_STUB_VALUES: dict[str, str] = {
    "engine.temperature": json.dumps({"temperature": {"engine": 90, "oil": 95}}),
    "sensors.battery": json.dumps({"battery": 72}),
    "sensors.batteryTemp": json.dumps({"batteryTemp": 28}),
    "sensors.fuel": json.dumps({"fuel": {"range": 400, "reserve": 0, "tanklevel": 45}}),
    "sensors.temperatureExterior": json.dumps({"temperatureExterior": 14.0}),
    "sensors.temperatureInterior": json.dumps({"temperatureInterior": 21.0}),
    "driving.speedActual": json.dumps({"speedActual": 0}),
    "driving.odometer": json.dumps({"odometer": 41811}),
    "driving.gear": json.dumps({"gear": 3}),
    "vehicle.VIN": json.dumps({"VIN": "LABSTUBVIN0000000"}),
}

_CDS_NAME_RE = re.compile(
    rb"(engine\.temperature|sensors\.batteryTemp|sensors\.battery|sensors\.fuel|"
    rb"sensors\.temperatureExterior|sensors\.temperatureInterior|"
    rb"driving\.speedActual|driving\.odometer|driving\.gear|vehicle\.VIN)"
)


def wrap_etch_body(body: bytes) -> bytes:
    """deadbeef | u32BE(len(body)) | body — same envelope as lab cert msgs."""
    return ETCH_MAGIC + struct.pack(">I", len(body)) + body


def build_sas_challenge_payload(challenge: bytes | None = None) -> bytes:
    """Best-effort HU→Phone challenge blob (16 bytes, Mock/Simulator style)."""
    ch = challenge if challenge is not None else bytes(16)
    if len(ch) != 16:
        raise ValueError("SAS challenge must be 16 bytes")
    return wrap_etch_body(_LAB_ETCH_HDR + ch + _LAB_ETCH_TRAILER)


def build_cds_property_payload(property_name: str, value_json: str) -> bytes:
    """Envelope carrying property name + JSON for lab observation / soft clients."""
    blob = property_name.encode("ascii") + b"\x00" + value_json.encode("utf-8")
    return wrap_etch_body(_LAB_ETCH_HDR + blob + _LAB_ETCH_TRAILER)


def build_sas_login_ok_payload() -> bytes:
    return wrap_etch_body(_LAB_ETCH_HDR + b"\x00" + _LAB_ETCH_TRAILER)


@dataclass
class EtchChannelReassembler:
    """Reassemble fragmented BCL DATA payloads per src→4004 stream."""

    buf: bytearray = field(default_factory=bytearray)
    need: int | None = None

    def feed(self, chunk: bytes) -> list[bytes]:
        out: list[bytes] = []
        self.buf.extend(chunk)
        while True:
            if self.need is None:
                if len(self.buf) < 8:
                    return out
                if self.buf[:4] != ETCH_MAGIC:
                    # Resync: drop until magic or clear junk
                    idx = self.buf.find(ETCH_MAGIC)
                    if idx < 0:
                        self.buf.clear()
                        return out
                    del self.buf[:idx]
                    if len(self.buf) < 8:
                        return out
                body_len = int.from_bytes(self.buf[4:8], "big")
                self.need = 8 + body_len
            if len(self.buf) < self.need:
                return out
            msg = bytes(self.buf[: self.need])
            del self.buf[: self.need]
            self.need = None
            out.append(msg)
        return out


@dataclass
class EtchSasCdsStub:
    """Per-connection stub state for dest 4004."""

    enabled: bool = True
    challenge: bytes = field(default_factory=lambda: bytes(16))
    channels: dict[int, EtchChannelReassembler] = field(default_factory=dict)
    certs_seen: int = 0
    challenges_sent: int = 0
    logins_seen: int = 0
    cds_hits: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)

    def on_etch_data(self, src: int, payload: bytes) -> list[bytes]:
        if not self.enabled:
            return []
        ch = self.channels.setdefault(src, EtchChannelReassembler())
        replies: list[bytes] = []
        for msg in ch.feed(payload):
            replies.extend(self._handle_msg(src, msg))
        return replies

    def _handle_msg(self, src: int, msg: bytes) -> list[bytes]:
        has_pkcs7 = b"-----BEGIN" in msg and b"PKCS7" in msg
        cds_names = [m.group(0).decode("ascii") for m in _CDS_NAME_RE.finditer(msg)]
        self.events.append(
            {
                "event": "etch_msg_rx",
                "src": src,
                "len": len(msg),
                "has_pkcs7": has_pkcs7,
                "cds_names": cds_names,
            }
        )
        out: list[bytes] = []
        if has_pkcs7:
            self.certs_seen += 1
            self.events.append(
                {
                    "event": "sas_certificate_rx",
                    "src": src,
                    "cert_index": self.certs_seen,
                    "len": len(msg),
                }
            )
            out.append(build_sas_challenge_payload(self.challenge))
            self.challenges_sent += 1
            self.events.append(
                {
                    "event": "sas_challenge_tx",
                    "src": src,
                    "challenge_hex": self.challenge.hex(),
                    "index": self.challenges_sent,
                }
            )
            return out
        if cds_names:
            for name in cds_names:
                val = CDS_STUB_VALUES.get(name)
                if not val:
                    continue
                self.cds_hits.append(name)
                self.events.append(
                    {
                        "event": "cds_property_rx",
                        "src": src,
                        "property": name,
                    }
                )
                out.append(build_cds_property_payload(name, val))
                self.events.append(
                    {
                        "event": "cds_property_tx",
                        "src": src,
                        "property": name,
                        "value_json": val,
                    }
                )
            return out
        # Non-cert follow-up after at least one challenge → treat as login/RPC
        if self.challenges_sent > 0 and len(msg) >= 24:
            self.logins_seen += 1
            self.events.append(
                {
                    "event": "sas_login_rx",
                    "src": src,
                    "len": len(msg),
                    "index": self.logins_seen,
                }
            )
            out.append(build_sas_login_ok_payload())
            self.events.append({"event": "sas_login_ok_tx", "src": src})
        return out
