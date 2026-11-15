#!/usr/bin/env python3
"""Minimal lab Etch/SAS/CDS stub for Dummy-HU (not a full Apache Etch stack).

SAS probe stages (adaptive, no crypto verification):
  none            — no etch replies (transport/WD only)
  dataack         — outer DummyHu DATAACK only; stub silent
  challenge       — non-zero SAS-challenge on OPEN 4004 and after PKCS7
  challenge_rhmi  — challenge + stub RHMI/capabilities blob

Epistemic: LAB stub only — framing mirrors deadbeef + u32BE(len) from LAB_DUMMY_ETCH_*
and field CDS ASCII from FIELD_AAIDRIVE_BTLOG_20261115.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from typing import Literal

ETCH_MAGIC = b"\xde\xad\xbe\xef"
# 16-byte prefix observed before PEM in lab Phone→HU cert msgs (src10).
_LAB_ETCH_HDR = bytes.fromhex("0386304ba8bb0286144a776f8b8517c7")
_LAB_ETCH_TRAILER = bytes.fromhex("866306b46887000001a1da8f000081")

# Field-seen void/ack trailer shape (FIELD M38) — used in short completions.
_FIELD_VOID_TRAILER = bytes.fromhex("0286eda8c9a687000001")

SasProbeStage = Literal["none", "dataack", "challenge", "challenge_rhmi"]
SAS_PROBE_STAGES: tuple[str, ...] = ("none", "dataack", "challenge", "challenge_rhmi")

# CDS property → JSON (BMWConnectedAnalysis + field fragments 2026-11-15).
CDS_STUB_VALUES: dict[str, str] = {
    "engine.temperature": json.dumps({"temperature": {"engine": 90, "oil": 95}}),
    "sensors.battery": json.dumps({"battery": 72}),
    "sensors.SOCBattery": json.dumps({"SOCBattery": 255.0}),
    "sensors.batteryTemp": json.dumps({"batteryTemp": 28}),
    "sensors.fuel": json.dumps({"fuel": {"range": 400, "reserve": 0, "tanklevel": 45}}),
    "sensors.temperatureExterior": json.dumps({"temperatureExterior": 14.0}),
    "sensors.temperatureInterior": json.dumps({"temperatureInterior": 21.0}),
    "driving.speedActual": json.dumps({"speedActual": 0}),
    "driving.odometer": json.dumps({"odometer": 41811}),
    "driving.gear": json.dumps({"gear": 3}),
    "entertainment.mtp": json.dumps({"_ENT_MTP_OFF": True}),
    "iva_MYV_LIGHT_INTERIOR": json.dumps({"iva_MYV_LIGHT_INTERIOR": False}),
    "vehicle.VIN": json.dumps({"VIN": "WBA1S51080V838304"}),
}

_CDS_NAME_RE = re.compile(
    rb"(engine\.temperature|sensors\.SOCBattery|sensors\.batteryTemp|sensors\.battery|"
    rb"sensors\.fuel|sensors\.temperatureExterior|sensors\.temperatureInterior|"
    rb"driving\.speedActual|driving\.odometer|driving\.gear|"
    rb"entertainment\.mtp|iva_MYV_LIGHT_INTERIOR|vehicle\.VIN|"
    rb"_ENT_MTP_OFF)"
)

# Silent-HU 56-B KNOCK-related envelope UUID (LAB_SILENT_HU_INIT_KNOCK).
KNOCK_UUID_SERIAL = b"0e9b90c4-cbe1-4742-8283-d367e9a56619"
KNOCK_ENVELOPE_TRAILER = bytes.fromhex("deadbeefbeef")


def wrap_etch_body(body: bytes) -> bytes:
    """deadbeef | u32BE(len(body)) | body — same envelope as lab cert msgs."""
    return ETCH_MAGIC + struct.pack(">I", len(body)) + body


def build_sas_challenge_payload(challenge: bytes | None = None) -> bytes:
    """Best-effort HU→Phone challenge blob (16 bytes, Mock/Simulator style)."""
    ch = challenge if challenge is not None else bytes(16)
    if len(ch) != 16:
        raise ValueError("SAS challenge must be 16 bytes")
    return wrap_etch_body(_LAB_ETCH_HDR + ch + _LAB_ETCH_TRAILER)


def fresh_sas_challenge() -> bytes:
    """Non-zero lab challenge — zeros were ignored by Phone (LAB_LIVE_GREEN)."""
    import os

    while True:
        ch = os.urandom(16)
        if any(ch):
            return ch


def build_cds_property_payload(property_name: str, value_json: str) -> bytes:
    """Envelope carrying property name + JSON for lab observation / soft clients."""
    blob = property_name.encode("ascii") + b"\x00" + value_json.encode("utf-8")
    return wrap_etch_body(_LAB_ETCH_HDR + blob + _LAB_ETCH_TRAILER)


def build_sas_login_ok_payload() -> bytes:
    return wrap_etch_body(_LAB_ETCH_HDR + b"\x00" + _LAB_ETCH_TRAILER)


def build_rhmi_capabilities_stub() -> bytes:
    """LAB-only RHMI/capabilities-shaped reply for sas_probe=challenge_rhmi.

    Not a decoded F20 body — ASCII marker + field-like void trailer so Phone
    progress past challenge can be observed in jsonl.
    """
    body = (
        _LAB_ETCH_HDR
        + b"\x93\x12rhmi_capabilities"
        + b"\x93\x0b_ENT_MTP_OFF"
        + b"\x93\x05false"
        + _FIELD_VOID_TRAILER
    )
    return wrap_etch_body(body)


def looks_like_knock_envelope(data: bytes) -> bool:
    """True if raw bytes look like Silent-HU 56-B KNOCK-related blob."""
    if KNOCK_UUID_SERIAL in data and (
        data.startswith(ETCH_MAGIC) or ETCH_MAGIC in data[:8]
    ):
        return True
    if KNOCK_UUID_SERIAL in data and KNOCK_ENVELOPE_TRAILER in data:
        return True
    return False


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
    stage: SasProbeStage = "challenge"
    # Non-zero by default — LAB_LIVE_GREEN showed Phone ignores all-zero challenge.
    challenge: bytes = field(default_factory=fresh_sas_challenge)
    channels: dict[int, EtchChannelReassembler] = field(default_factory=dict)
    certs_seen: int = 0
    challenges_sent: int = 0
    logins_seen: int = 0
    opens_seen: int = 0
    rhmi_caps_sent: int = 0
    cds_hits: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)

    def on_etch_open(self, src: int) -> list[bytes]:
        """Adaptive reply right after Phone OPEN dest=4004."""
        if not self.enabled or self.stage in ("none", "dataack"):
            return []
        self.opens_seen += 1
        self.events.append(
            {
                "event": "etch_open_probe",
                "src": src,
                "stage": self.stage,
                "index": self.opens_seen,
            }
        )
        return self._emit_challenge_stack(src, reason="open")

    def on_etch_data(self, src: int, payload: bytes) -> list[bytes]:
        if not self.enabled or self.stage == "none":
            return []
        if self.stage == "dataack":
            # Observe only — outer DummyHu already sent DATAACK(8+len).
            ch = self.channels.setdefault(src, EtchChannelReassembler())
            for msg in ch.feed(payload):
                self.events.append(
                    {
                        "event": "etch_msg_rx",
                        "src": src,
                        "len": len(msg),
                        "stage": self.stage,
                        "silent": True,
                    }
                )
            return []
        ch = self.channels.setdefault(src, EtchChannelReassembler())
        replies: list[bytes] = []
        for msg in ch.feed(payload):
            replies.extend(self._handle_msg(src, msg))
        return replies

    def _emit_challenge_stack(self, src: int, *, reason: str) -> list[bytes]:
        out: list[bytes] = []
        out.append(build_sas_challenge_payload(self.challenge))
        self.challenges_sent += 1
        self.events.append(
            {
                "event": "sas_challenge_tx",
                "src": src,
                "challenge_hex": self.challenge.hex(),
                "index": self.challenges_sent,
                "reason": reason,
                "stage": self.stage,
            }
        )
        if self.stage == "challenge_rhmi":
            out.append(build_rhmi_capabilities_stub())
            self.rhmi_caps_sent += 1
            self.events.append(
                {
                    "event": "rhmi_capabilities_tx",
                    "src": src,
                    "index": self.rhmi_caps_sent,
                    "stage": self.stage,
                }
            )
        return out

    def _handle_msg(self, src: int, msg: bytes) -> list[bytes]:
        has_pkcs7 = b"-----BEGIN" in msg and b"PKCS7" in msg
        cds_names = [m.group(0).decode("ascii") for m in _CDS_NAME_RE.finditer(msg)]
        # Normalize field ASCII alias
        cds_names = [
            "entertainment.mtp" if n == "_ENT_MTP_OFF" else n for n in cds_names
        ]
        self.events.append(
            {
                "event": "etch_msg_rx",
                "src": src,
                "len": len(msg),
                "has_pkcs7": has_pkcs7,
                "cds_names": cds_names,
                "stage": self.stage,
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
            out.extend(self._emit_challenge_stack(src, reason="pkcs7"))
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
            if self.stage == "challenge_rhmi" and self.rhmi_caps_sent == 0:
                out.extend(self._emit_challenge_stack(src, reason="post_login")[1:])
        return out
