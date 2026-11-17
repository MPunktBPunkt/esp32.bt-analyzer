#!/usr/bin/env python3
"""Minimal lab Etch/SAS/CDS stub for Dummy-HU (not a full Apache Etch stack).

SAS probe stages (no crypto verification — LAB experiment only):
  none            — no etch replies (transport/WD only)
  dataack         — outer DummyHu DATAACK only; stub silent
  challenge       — non-zero SAS-challenge on OPEN 4004 and after PKCS7
  challenge_rhmi  — challenge + stub RHMI/capabilities blob
  adaptive        — challenge on OPEN; RHMI escalate after Phone etch TX

Epistemic: LAB stub only — framing mirrors deadbeef + u32BE(len) from LAB_DUMMY_ETCH_*
and field CDS ASCII from FIELD_AAIDRIVE_BTLOG_20261115.
Does NOT reconstruct real SAS/RHMI; discovers what Phone needs to advance.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal

ETCH_MAGIC = b"\xde\xad\xbe\xef"


def etch_sdbm_hash(name: str) -> int:
    """Apache Etch BinaryTaggedData type/field hash (org.apache.etch.util.Hash, seed 5381)."""
    h = 5381
    for b in name.encode("utf-8"):
        h = (b + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h


# Verified against F20 field logs (102058 / 173520 / 173553) + BMWRemoting.etch (2026-11-16).
ETCH_TYPE_SAS_CERTIFICATE = etch_sdbm_hash("de.bmw.idrive.BMWRemoting.sas_certificate")          # 0x304ba8bb
ETCH_TYPE_RESULT_SAS_CERTIFICATE = etch_sdbm_hash("de.bmw.idrive.BMWRemoting._result_sas_certificate")  # 0x9c6372b8
ETCH_TYPE_SAS_LOGIN = etch_sdbm_hash("de.bmw.idrive.BMWRemoting.sas_login")                      # 0x7e002a4d
ETCH_TYPE_RESULT_SAS_LOGIN = etch_sdbm_hash("de.bmw.idrive.BMWRemoting._result_sas_login")       # 0xa6b0ffca
ETCH_TYPE_RHMI_GET_CAPS = etch_sdbm_hash("de.bmw.idrive.BMWRemoting.rhmi_getCapabilities")       # 0x06688121
ETCH_TYPE_RESULT_RHMI_GET_CAPS = etch_sdbm_hash("de.bmw.idrive.BMWRemoting._result_rhmi_getCapabilities")  # 0x19481364
ETCH_TYPE_CDS_ON_PROP_CHANGED = etch_sdbm_hash("de.bmw.idrive.BMWRemoting.cds_onPropertyChangedEvent")     # 0xae0d3d69

ETCH_FIELD_MESSAGE_ID = etch_sdbm_hash("_messageId")   # 0x6306b468
ETCH_FIELD_IN_REPLY_TO = etch_sdbm_hash("_inReplyTo")  # 0xeda8c9a6
ETCH_FIELD_RESULT = etch_sdbm_hash("result")           # 0x8104fdc2
ETCH_FIELD_DATA = etch_sdbm_hash("data")               # 0x144a776f

# 16-byte prefix observed before PEM in lab Phone→HU sas_certificate msgs (src10).
_LAB_ETCH_HDR = bytes.fromhex("0386304ba8bb0286144a776f8b8517c7")
_LAB_ETCH_TRAILER = bytes.fromhex("866306b46887000001a1da8f000081")

# Field-seen void/ack trailer shape — _inReplyTo field in 36-byte void replies.
_FIELD_VOID_TRAILER = bytes.fromhex("0286eda8c9a687000001")

SasProbeStage = Literal[
    "none", "dataack", "challenge", "challenge_rhmi", "adaptive", "f20_full"
]
SAS_PROBE_STAGES: tuple[str, ...] = (
    "none",
    "dataack",
    "challenge",
    "challenge_rhmi",
    "adaptive",
    "f20_full",
)

# Realistic F20 capability map returned by `f20_full` on `rhmi_getCapabilities("", 255)`
F20_FULL_CAPABILITIES: dict[str, str] = {
    "hmi.type": "BMW ID5",
    "hmi.version": "NBTevo_S_F20_LabSim",
    "hmi.display-width": "1280",
    "hmi.display-height": "480",
    "hmi.role": "HU",
    "vehicle.type": "F20",
    "vehicle.country": "DE",
    "a4axl": "true",
    "tts": "true",
    "navi": "true",
    "map": "true",
    "voice": "true",
    "inbox": "true",
    "pia": "true",
    "speedlock": "true",
    "touch_command": "false",
    "alignment-right": "false",
    "_ENT_MTP_OFF": "false",
    "iva_ENT_USB_COVER_ART_IPOD": "true",
    "iva_MYV_LIGHT_INTERIOR": "false",
    "iva_TC_REAR_WINDOW_C": "not_active",
}

# CDS property → JSON returned by `f20_full` on `cds_getPropertyAsync` / `cds_addPropertyChangedEventHandler`
CDS_STUB_VALUES: dict[str, str] = {
    "vehicle.VIN": json.dumps({"VIN": "WBA1S51080V838304"}),
    "vehicle.language": json.dumps({"language": 1}),
    "vehicle.country": json.dumps({"country": 4}),
    "vehicle.type": json.dumps({"type": 15}),
    "vehicle.units": json.dumps({"units": {"distance": 1, "fuel": 1, "temperature": 1}}),
    "vehicle.time": json.dumps({"time": {"hour": 14, "minute": 20, "second": 0, "date": 16, "month": 11, "year": 2026}}),
    "hmi.iDrive": json.dumps({"iDrive": 5}),
    "hmi.graphicalContext": json.dumps({"graphicalContext": {"app": "Connected", "visible": 1}}),
    "engine.RPMSpeed": json.dumps({"RPMSpeed": 830}),
    "engine.info": json.dumps({"info": {"fuelType": 5, "numCylinders": 4, "capacity": 1995}}),
    "engine.status": json.dumps({"status": 2}),
    "engine.temperature": json.dumps({"temperature": {"engine": 90, "oil": 95}}),
    "engine.consumption": json.dumps({"consumption": 5.1}),
    "sensors.battery": json.dumps({"battery": 84}),
    "sensors.SOCBattery": json.dumps({"SOCBattery": 255.0}),
    "sensors.SOCBatteryHybrid": json.dumps({"SOCBatteryHybrid": 255.0}),
    "sensors.batteryTemp": json.dumps({"batteryTemp": 21}),
    "sensors.fuel": json.dumps({"fuel": {"range": 640, "reserve": 0, "tanklevel": 38}}),
    "sensors.temperatureExterior": json.dumps({"temperatureExterior": 14.0}),
    "sensors.temperatureInterior": json.dumps({"temperatureInterior": 21.0}),
    "sensors.doors": json.dumps({"doors": {"driver": 0, "passenger": 0, "driverRear": 0, "passengerRear": 0}}),
    "sensors.trunk": json.dumps({"trunk": 0}),
    "sensors.lid": json.dumps({"lid": 0}),
    "driving.speedActual": json.dumps({"speedActual": 0}),
    "driving.speedDisplayed": json.dumps({"speedDisplayed": 0}),
    "driving.odometer": json.dumps({"odometer": 114280}),
    "driving.gear": json.dumps({"gear": 0}),
    "driving.parkingBrake": json.dumps({"parkingBrake": 2}),
    "driving.keyPosition": json.dumps({"keyPosition": {"running": 1, "accessory": 1}}),
    "driving.mode": json.dumps({"mode": 0}),
    "controls.lights": json.dumps({"lights": {"brights": 0, "fogRear": 0, "parking": 1}}),
    "controls.headlights": json.dumps({"headlights": 1}),
    "navigation.GPSExtendedInfo": json.dumps({"GPSExtendedInfo": {"latitude": 48137154, "longitude": 11576124, "altitude": 520, "heading": 90}}),
    "entertainment.mtp": json.dumps({"_ENT_MTP_OFF": False}),
    "iva_MYV_LIGHT_INTERIOR": json.dumps({"iva_MYV_LIGHT_INTERIOR": False}),
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


def extract_etch_type_hash(msg: bytes) -> int | None:
    """Return the 32-bit Etch struct type hash from a deadbeef-wrapped or raw Etch body."""
    body = msg[8:] if len(msg) >= 8 and msg[:4] == ETCH_MAGIC else msg
    if len(body) >= 6 and body[0] == 0x03 and body[1] == 0x86:
        return int.from_bytes(body[2:6], "big")
    return None


def extract_etch_message_id(msg: bytes) -> int | None:
    """Extract int64/int32 `_messageId` (field 0x6306b468) from an Etch message."""
    body = msg[8:] if len(msg) >= 8 and msg[:4] == ETCH_MAGIC else msg
    needle = b"\x86" + struct.pack(">I", ETCH_FIELD_MESSAGE_ID)
    idx = body.rfind(needle)
    if idx < 0 or idx + 6 > len(body):
        return None
    vtag = body[idx + 5]
    pos = idx + 6
    if vtag <= 0x1F:
        return vtag
    if vtag == 0x84 and pos + 1 <= len(body):
        return struct.unpack(">b", body[pos : pos + 1])[0]
    if vtag == 0x85 and pos + 2 <= len(body):
        return struct.unpack(">h", body[pos : pos + 2])[0]
    if vtag == 0x86 and pos + 4 <= len(body):
        return struct.unpack(">i", body[pos : pos + 4])[0]
    if vtag == 0x87 and pos + 8 <= len(body):
        return struct.unpack(">q", body[pos : pos + 8])[0]
    return None


def build_sas_challenge_payload(
    challenge: bytes | None = None,
    *,
    in_reply_to: int = 1,
    msg_id: int = 1,
) -> bytes:
    """Wire-exact F20 `_result_sas_certificate` (59 B Etch / 67 B wrapped, E-553 17:36:33.611)."""
    ch = challenge if challenge is not None else bytes(16)
    if len(ch) != 16:
        raise ValueError("SAS challenge must be 16 bytes")
    body = (
        b"\x03\x86"
        + struct.pack(">I", ETCH_TYPE_RESULT_SAS_CERTIFICATE)
        + b"\x03"  # nfields = 3 (result, _inReplyTo, _messageId)
        + b"\x86"
        + struct.pack(">I", ETCH_FIELD_RESULT)
        + b"\x8b\x10"  # BYTES, tiny int length = 16
        + ch
        + b"\x86"
        + struct.pack(">I", ETCH_FIELD_IN_REPLY_TO)
        + b"\x87"
        + struct.pack(">q", in_reply_to)
        + b"\x86"
        + struct.pack(">I", ETCH_FIELD_MESSAGE_ID)
        + b"\x87"
        + struct.pack(">q", msg_id)
        + b"\x81"  # END
    )
    return wrap_etch_body(body)


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


def build_sas_login_ok_payload(*, in_reply_to: int = 1, msg_id: int = 2) -> bytes:
    """Wire-exact F20 `_result_sas_login` (36 B Etch / 44 B wrapped, S-B 10:21:31.972)."""
    body = (
        b"\x03\x86"
        + struct.pack(">I", ETCH_TYPE_RESULT_SAS_LOGIN)
        + b"\x02"  # nfields = 2 (_inReplyTo, _messageId)
        + b"\x86"
        + struct.pack(">I", ETCH_FIELD_IN_REPLY_TO)
        + b"\x87"
        + struct.pack(">q", in_reply_to)
        + b"\x86"
        + struct.pack(">I", ETCH_FIELD_MESSAGE_ID)
        + b"\x87"
        + struct.pack(">q", msg_id)
        + b"\x81"
    )
    return wrap_etch_body(body)


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


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_service_exception(
    *, error_code: int = 213, detail: str = "SetData was not successful."
):
    """F20-shaped BMWRemoting.ServiceException (nested TC_CUSTOM on wire)."""
    from etch_codec import EtchStruct

    return EtchStruct(
        "de.bmw.idrive.BMWRemoting.ServiceException",
        {"errorCode": int(error_code), "detailMessage": str(detail)},
    )


def _is_imageid_zero(value: Any) -> bool:
    """True when value is RHMIResourceIdentifier{id=0} (MockBMWRemotingServer 2019 rule)."""
    from etch_codec import EtchStruct

    def _id_is_zero(fields: dict) -> bool:
        if "id" not in fields:
            return False
        rid = fields.get("id")
        # id=0 is falsy — must not use `rid or …`
        try:
            return int(rid) == 0
        except (TypeError, ValueError):
            return False

    if isinstance(value, EtchStruct):
        short = value.type_name.rsplit(".", 1)[-1]
        if "RHMIResourceIdentifier" in short or short == "RHMIResourceIdentifier":
            return _id_is_zero(value.fields)
        # Some stacks nest identifier fields without full type name on partial decode
        if _id_is_zero(value.fields) and (
            "type" in value.fields or "IMAGEID" in str(value.fields)
        ):
            return True
    if isinstance(value, dict) and _id_is_zero(value):
        return True
    return False


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
    # LAB: after OPEN challenge, also push a few field-like CDS values (unsolicited).
    cds_push: bool = False
    cds_push_sent: int = 0
    next_handle: int = 10
    msg_seq: int = 200
    resources_rx: int = 0
    events: list[dict] = field(default_factory=list)
    # Active CDS subscriptions from Phone (src, handle, propertyName) for live inject.
    subscriptions: list[dict] = field(default_factory=list)
    # SHA-256 digests the "HU" already knows (checkResource→True). Seeded from
    # setResource uploads and optional /tmp/bcl_dummy/rhmi_digests.txt.
    known_digests: set[str] = field(default_factory=set)
    setdata_reject: int = 0
    check_resource_hits: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Seed whitelist from lab digest file if present (one hex digest per line).
        path = Path(os.environ.get("BCL_RHMI_DIGESTS", "/tmp/bcl_dummy/rhmi_digests.txt"))
        try:
            if path.is_file():
                for line in path.read_text().splitlines():
                    d = line.strip().lower()
                    if len(d) == 64 and all(c in "0123456789abcdef" for c in d):
                        self.known_digests.add(d)
        except OSError:
            pass

    # Minimal field-seen set for unsolicited push experiments.
    CDS_PUSH_NAMES: ClassVar[tuple[str, ...]] = (
        "sensors.SOCBattery",
        "iva_MYV_LIGHT_INTERIOR",
        "vehicle.VIN",
    )

    def inject_cds_updates(self, updates: dict[str, Any]) -> list[tuple[int, bytes]]:
        """Build HU→Phone cds_onPropertyChangedEvent payloads for live inject.

        Returns list of (phone_src, etch_body) for each matching subscription.
        Unknown properties still update CDS_STUB_VALUES for the next getPropertyAsync.
        """
        from etch_codec import CDS_BY_NAME, encode_etch_packet

        out: list[tuple[int, bytes]] = []
        for prop, value in updates.items():
            if isinstance(value, str):
                # Accept raw JSON string or plain string
                try:
                    json.loads(value)
                    val_json = value
                except json.JSONDecodeError:
                    leaf = str(prop).split(".")[-1]
                    val_json = json.dumps({leaf: value})
            else:
                leaf = str(prop).split(".")[-1]
                if isinstance(value, dict):
                    val_json = json.dumps(value)
                else:
                    val_json = json.dumps({leaf: value})
            CDS_STUB_VALUES[str(prop)] = val_json
            matched = [s for s in self.subscriptions if s.get("property") == prop]
            if not matched:
                # Fan-out to every known CDS channel so Phone still sees an event
                matched = [
                    {"src": s["src"], "handle": s["handle"], "property": prop}
                    for s in { (x["src"], x["handle"]): x for x in self.subscriptions }.values()
                ]
            for sub in matched:
                src = int(sub["src"])
                handle = int(sub["handle"])
                ident = str(CDS_BY_NAME.get(prop, "0"))
                pkt = encode_etch_packet(
                    "cds_onPropertyChangedEvent",
                    {
                        "_messageId": self._next_msg_id(),
                        "handle": handle,
                        "ident": ident,
                        "propertyName": prop,
                        "propertyValue": val_json,
                    },
                )
                out.append((src, pkt))
                self.events.append(
                    {
                        "event": "cds_property_tx",
                        "src": src,
                        "property": prop,
                        "value_json": val_json,
                        "reason": "inject",
                        "handle": handle,
                    }
                )
        return out

    def on_etch_open(self, src: int) -> list[bytes]:
        """Reply right after Phone OPEN dest=4004 (static stages + adaptive; f20_full stays silent like real F20!)."""
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
        if self.stage == "f20_full":
            # Real F20 sends ONLY outer DATAACK(8) on OPEN(src, 4004) and waits for sas_certificate.
            return []
        # adaptive: challenge first; escalate to RHMI only after phone TX evidence
        if self.stage in ("challenge", "challenge_rhmi", "adaptive"):
            include_rhmi = self.stage == "challenge_rhmi"
            out = self._emit_challenge_stack(
                src, reason="open", include_rhmi=include_rhmi
            )
            out.extend(self._emit_cds_push(src, reason="open"))
            return out
        return []

    def _emit_cds_push(self, src: int, *, reason: str) -> list[bytes]:
        if not self.cds_push or self.cds_push_sent > 0:
            return []
        out: list[bytes] = []
        for name in self.CDS_PUSH_NAMES:
            val = CDS_STUB_VALUES.get(name)
            if val is None:
                continue
            out.append(build_cds_property_payload(name, val))
            self.cds_hits.append(name)
            self.events.append(
                {
                    "event": "cds_property_tx",
                    "src": src,
                    "property": name,
                    "reason": f"cds_push_{reason}",
                    "note": "LAB unsolicited CDS — not proven F20 order",
                }
            )
        self.cds_push_sent += 1
        return out

    def on_etch_data(self, src: int, payload: bytes) -> list[bytes]:
        if not self.enabled or self.stage == "none":
            return []
        if self.stage == "dataack":
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

    def _emit_challenge_stack(
        self,
        src: int,
        *,
        reason: str,
        include_rhmi: bool | None = None,
        in_reply_to: int = 1,
    ) -> list[bytes]:
        out: list[bytes] = []
        self.challenges_sent += 1
        out.append(
            build_sas_challenge_payload(
                self.challenge,
                in_reply_to=in_reply_to,
                msg_id=self.challenges_sent,
            )
        )
        self.events.append(
            {
                "event": "sas_challenge_tx",
                "src": src,
                "challenge_hex": self.challenge.hex(),
                "in_reply_to": in_reply_to,
                "index": self.challenges_sent,
                "reason": reason,
                "stage": self.stage,
            }
        )
        want_rhmi = (
            include_rhmi
            if include_rhmi is not None
            else self.stage == "challenge_rhmi"
        )
        if want_rhmi:
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

    def adaptive_escalate_rhmi(self, src: int) -> list[bytes]:
        """After Phone post-challenge TX in adaptive mode — one RHMI stub."""
        if self.stage != "adaptive" or self.rhmi_caps_sent > 0:
            return []
        out = [build_rhmi_capabilities_stub()]
        self.rhmi_caps_sent += 1
        self.events.append(
            {
                "event": "rhmi_capabilities_tx",
                "src": src,
                "index": self.rhmi_caps_sent,
                "stage": "adaptive",
                "reason": "phone_tx_after_challenge",
            }
        )
        return out

    def _next_msg_id(self) -> int:
        self.msg_seq += 1
        return self.msg_seq

    def _alloc_handle(self) -> int:
        h = self.next_handle
        self.next_handle += 1
        return h

    def _handle_f20_full_rpc(self, src: int, msg: bytes) -> list[bytes]:
        """Full BMWRemoting server responder for real OnePlus + MyBMW + AAIdrive sessions."""
        from etch_codec import (
            CDS_BY_NAME,
            HASH_REGISTRY,
            EtchStruct,
            build_cds_event,
            decode_etch_message,
            encode_etch_packet,
            inspect_pkcs7_bundle,
        )

        th = extract_etch_type_hash(msg)
        req_msg_id = extract_etch_message_id(msg)
        reply_to = req_msg_id if req_msg_id is not None else 1
        method = HASH_REGISTRY.get(th or 0, f"0x{(th or 0):08x}")
        raw_fields: dict = {}
        try:
            dec = decode_etch_message(msg)
            method = dec["method"]
            raw_fields = dec["raw_fields"]
            if isinstance(raw_fields.get("_messageId"), int):
                reply_to = raw_fields["_messageId"]
        except Exception as exc:  # noqa: BLE001
            self.events.append({"event": "etch_decode_partial", "src": src, "method": method, "err": str(exc)})

        rpc_ev: dict[str, Any] = {
            "event": "f20_rpc_rx",
            "src": src,
            "method": method,
            "req_msg_id": reply_to,
            "len": len(msg),
        }
        # Promote decoded RHMI fields so NP/menu analysis does not need payload_hex reassembly.
        if method == "rhmi_setData":
            rpc_ev["handle"] = raw_fields.get("handle")
            rpc_ev["modelId"] = raw_fields.get("modelId")
            val = raw_fields.get("value")
            if isinstance(val, (str, int, float, bool)) or val is None:
                rpc_ev["value"] = val
            elif isinstance(val, (bytes, bytearray)):
                rpc_ev["value_len"] = len(val)
                rpc_ev["value_hex_prefix"] = bytes(val)[:64].hex()
            else:
                # EtchStruct / tables / maps — compact type tag only
                tname = getattr(val, "type_name", None) or type(val).__name__
                rpc_ev["value_type"] = tname
                if hasattr(val, "fields") and isinstance(val.fields, dict):
                    data = val.fields.get("data")
                    if isinstance(data, list):
                        rpc_ev["value_rows"] = len(data)
        elif method == "rhmi_setProperty":
            rpc_ev["handle"] = raw_fields.get("handle")
            rpc_ev["componentId"] = raw_fields.get("componentId")
            rpc_ev["propertyId"] = raw_fields.get("propertyId")
            rpc_ev["values"] = raw_fields.get("values")
        elif method == "am_registerApp":
            for k in ("handle", "id", "name", "category", "appId", "appName"):
                if k in raw_fields:
                    rpc_ev[k] = raw_fields.get(k)
        self.events.append(rpc_ev)
        out: list[bytes] = []

        if method == "sas_certificate":
            self.certs_seen += 1
            cert_bytes = raw_fields.get("data")
            cert_meta = None
            if isinstance(cert_bytes, (bytes, bytearray)):
                try:
                    cert_meta = inspect_pkcs7_bundle(bytes(cert_bytes))
                except Exception:  # noqa: BLE001
                    cert_meta = None
            self.challenges_sent += 1
            out.append(
                build_sas_challenge_payload(
                    self.challenge, in_reply_to=reply_to, msg_id=self._next_msg_id()
                )
            )
            self.events.append(
                {
                    "event": "sas_challenge_tx",
                    "src": src,
                    "in_reply_to": reply_to,
                    "cert_cns": (cert_meta or {}).get("cns"),
                }
            )
            return out

        if method == "sas_login":
            self.logins_seen += 1
            sig = raw_fields.get("data")
            out.append(
                build_sas_login_ok_payload(
                    in_reply_to=reply_to, msg_id=self._next_msg_id()
                )
            )
            self.events.append(
                {
                    "event": "sas_login_ok_tx",
                    "src": src,
                    "sig_len": len(sig) if isinstance(sig, (bytes, bytearray)) else None,
                }
            )
            return out

        if method == "sas_permission":
            out.append(
                encode_etch_packet(
                    "_result_sas_permission",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": "true"},
                )
            )
            return out

        if method == "ver_getVersion" or method == "cds_getVersion":
            vstruct = EtchStruct("VersionInfo", {"major": 4, "minor": 0, "revision": 0})
            out.append(
                encode_etch_packet(
                    f"_result_{method}",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": vstruct},
                )
            )
            return out

        if method == "info_getSystemInfo":
            out.append(
                encode_etch_packet(
                    "_result_info_getSystemInfo",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": {"build": "F20_LabSim"}},
                )
            )
            return out

        if method == "rhmi_getCapabilities":
            self.rhmi_caps_sent += 1
            out.append(
                encode_etch_packet(
                    "_result_rhmi_getCapabilities",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": dict(F20_FULL_CAPABILITIES)},
                )
            )
            self.events.append({"event": "rhmi_capabilities_tx", "src": src, "count": len(F20_FULL_CAPABILITIES)})
            return out

        if method in ("cds_create", "am_create", "rhmi_create", "rhmi_create_version", "av_create", "map_create"):
            h = self._alloc_handle()
            out.append(
                encode_etch_packet(
                    f"_result_{method}",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": h},
                )
            )
            self.events.append({"event": "handle_created", "src": src, "method": method, "handle": h})
            return out

        if method == "rhmi_checkResource":
            # Digest whitelist: known → True (skip upload); unknown → False (force setResource).
            # Matches F20 behaviour once SAS.Digests.RHMIDescriptions is satisfied.
            raw_hash = raw_fields.get("hash")
            digest = ""
            if isinstance(raw_hash, str):
                digest = raw_hash.strip().lower()
            elif isinstance(raw_hash, (bytes, bytearray)):
                digest = bytes(raw_hash).hex()
            known = bool(digest) and digest in self.known_digests
            self.check_resource_hits.append(
                {"src": src, "hash": digest or None, "known": known, "type": raw_fields.get("type")}
            )
            self.events.append(
                {
                    "event": "rhmi_check_resource",
                    "src": src,
                    "hash": digest or None,
                    "known": known,
                    "result": known,
                }
            )
            out.append(
                encode_etch_packet(
                    "_result_rhmi_checkResource",
                    {
                        "_inReplyTo": reply_to,
                        "_messageId": self._next_msg_id(),
                        "result": known,
                    },
                )
            )
            return out

        if method == "rhmi_setData":
            # P0: F20 rejects ImageID←0 with ServiceException(213, ...) — field 17.11.
            if _is_imageid_zero(raw_fields.get("value")):
                self.setdata_reject += 1
                self.events.append(
                    {
                        "event": "rhmi_setdata_reject",
                        "src": src,
                        "handle": raw_fields.get("handle"),
                        "modelId": raw_fields.get("modelId"),
                        "errorCode": 213,
                    }
                )
                out.append(
                    encode_etch_packet(
                        "_result_rhmi_setData",
                        {
                            "_inReplyTo": reply_to,
                            "_messageId": self._next_msg_id(),
                            "result": build_service_exception(),
                        },
                    )
                )
                return out
            # void OK (fall through to default below by not returning early with empty —
            # emit void here for clarity)
            out.append(
                encode_etch_packet(
                    "_result_rhmi_setData",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id()},
                )
            )
            return out

        if method == "rhmi_getState":
            out.append(
                encode_etch_packet(
                    "_result_rhmi_getState",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": 0},
                )
            )
            return out

        if method == "map_initializeImport":
            out.append(
                encode_etch_packet(
                    "_result_map_initializeImport",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id(), "result": 0},
                )
            )
            return out

        if method in ("cds_addPropertyChangedEventHandler", "cds_getPropertyAsync"):
            out.append(
                encode_etch_packet(
                    f"_result_{method}",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id()},
                )
            )
            pname = str(raw_fields.get("propertyName") or "")
            handle = int(raw_fields.get("handle") or 10)
            ident = str(raw_fields.get("ident") or CDS_BY_NAME.get(pname, "0"))
            if pname:
                self.cds_hits.append(pname)
                if method == "cds_addPropertyChangedEventHandler":
                    self.subscriptions.append(
                        {"src": src, "handle": handle, "property": pname}
                    )
                    self.events.append(
                        {
                            "event": "cds_subscribed",
                            "src": src,
                            "handle": handle,
                            "property": pname,
                        }
                    )
                leaf = pname.split(".")[-1]
                val_json = CDS_STUB_VALUES.get(pname) or json.dumps({leaf: 0})
                ev_pkt = encode_etch_packet(
                    "cds_onPropertyChangedEvent",
                    {
                        "_messageId": self._next_msg_id(),
                        "handle": handle,
                        "ident": ident,
                        "propertyName": pname,
                        "propertyValue": val_json,
                    },
                )
                # Push initial/current CDS value on both addPropertyChangedEventHandler and getPropertyAsync
                out.append(ev_pkt)
                self.events.append({"event": "cds_property_tx", "src": src, "property": pname, "value_json": val_json})
            return out

        if method == "av_requestConnection":
            out.append(
                encode_etch_packet(
                    "_result_av_requestConnection",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id()},
                )
            )
            handle = int(raw_fields.get("handle") or 10)
            ctype = raw_fields.get("connectionType")
            if ctype is not None:
                out.append(
                    encode_etch_packet(
                        "av_connectionGranted",
                        {"_messageId": self._next_msg_id(), "handle": handle, "connectionType": ctype},
                    )
                )
            return out

        if method == "rhmi_setResource":
            self.resources_rx += 1
            data_b = raw_fields.get("data")
            rtype = raw_fields.get("type")
            rhash = raw_fields.get("hash")
            nbytes = len(data_b) if isinstance(data_b, (bytes, bytearray)) else None
            saved = None
            digest = None
            if isinstance(data_b, (bytes, bytearray)) and data_b:
                # Persist for rhmi_db / cover offline parse (LAB only).
                try:
                    out_dir = Path(
                        os.environ.get("BCL_RHMI_RESOURCES", "/tmp/bcl_dummy/resources")
                    )
                    out_dir.mkdir(parents=True, exist_ok=True)
                    digest = _sha256_hex(bytes(data_b))
                    self.known_digests.add(digest)
                    # Prefer caller-supplied hash string if it looks like sha256
                    if isinstance(rhash, str) and len(rhash.strip()) == 64:
                        self.known_digests.add(rhash.strip().lower())
                    fname = (
                        f"src{src}_h{raw_fields.get('handle')}_"
                        f"sha{digest[:12]}_{nbytes}.bin"
                    )
                    path = out_dir / fname
                    if not path.exists():
                        path.write_bytes(bytes(data_b))
                    saved = str(path)
                    # Keep digest index for checkResource whitelist reloads
                    idx = out_dir.parent / "rhmi_digests.txt"
                    try:
                        existing = set()
                        if idx.is_file():
                            existing = {
                                ln.strip().lower()
                                for ln in idx.read_text().splitlines()
                                if len(ln.strip()) == 64
                            }
                        if digest not in existing:
                            with idx.open("a") as fh:
                                fh.write(digest + "\n")
                    except OSError:
                        pass
                except OSError:
                    saved = None
            self.events.append(
                {
                    "event": "rhmi_resource_rx",
                    "src": src,
                    "handle": raw_fields.get("handle"),
                    "type": str(rtype)[:120] if rtype is not None else None,
                    "hash": rhash if isinstance(rhash, (str, int)) else None,
                    "sha256": digest,
                    "bytes": nbytes,
                    "saved": saved,
                }
            )

        # Default void RPC completion for all remaining BMWRemoting methods
        if not method.startswith("0x") and not method.startswith("_result_"):
            out.append(
                encode_etch_packet(
                    f"_result_{method}",
                    {"_inReplyTo": reply_to, "_messageId": self._next_msg_id()},
                )
            )
        return out

    def _handle_msg(self, src: int, msg: bytes) -> list[bytes]:
        if self.stage == "f20_full":
            return self._handle_f20_full_rpc(src, msg)
        th = extract_etch_type_hash(msg)
        req_msg_id = extract_etch_message_id(msg)
        has_pkcs7 = (b"-----BEGIN" in msg and b"PKCS7" in msg) or th == ETCH_TYPE_SAS_CERTIFICATE
        is_sas_login = th == ETCH_TYPE_SAS_LOGIN
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
                "type_hash": f"0x{th:08x}" if th is not None else None,
                "req_msg_id": req_msg_id,
                "has_pkcs7": has_pkcs7,
                "is_sas_login": is_sas_login,
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
                    "req_msg_id": req_msg_id,
                    "len": len(msg),
                }
            )
            out.extend(
                self._emit_challenge_stack(
                    src,
                    reason="pkcs7",
                    in_reply_to=req_msg_id if req_msg_id is not None else 1,
                )
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
        # Explicit sas_login (0x7e002a4d) or lab follow-up after challenge
        if is_sas_login or (self.challenges_sent > 0 and len(msg) >= 24):
            self.logins_seen += 1
            self.events.append(
                {
                    "event": "sas_login_rx",
                    "src": src,
                    "len": len(msg),
                    "req_msg_id": req_msg_id,
                    "wire_verified_type": is_sas_login,
                    "index": self.logins_seen,
                }
            )
            out.append(
                build_sas_login_ok_payload(
                    in_reply_to=req_msg_id if req_msg_id is not None else 1,
                    msg_id=100 + self.logins_seen,
                )
            )
            self.events.append({"event": "sas_login_ok_tx", "src": src})
            if self.stage == "challenge_rhmi" and self.rhmi_caps_sent == 0:
                out.extend(
                    self._emit_challenge_stack(
                        src, reason="post_login", include_rhmi=True
                    )[1:]
                )
            elif self.stage == "adaptive":
                out.extend(self.adaptive_escalate_rhmi(src))
        return out
