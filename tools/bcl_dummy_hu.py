#!/usr/bin/env python3
"""BCL session logic for the lab Dummy-HU and a BclCarLink-like phone client.

Pure byte-in / byte-out state machines (no Bluetooth), so the order of the
handshake can be host-tested and reused by bcl_dummy_hu_agent.py on .108.

Desk sequence (BclCarLink BclClientTransport, not own BMW wire FACT):
  phone → HU  12 34 56 78            (repeated ~1 s until HANDSHAKE)
  HU → phone  HANDSHAKE cmd 4, payload version u16 | instanceId u16 | bufferSize u32
  phone → HU  SELECTPROTO            (wire after HS v5: SP4; desk: SP3 if version>3)
  phone → HU  KNOCK
  phone → HU  OPEN / DATA ...        (watchdog: dest 5001, ping 13 37 13 37)

Lab F20 profile (FIELD_STAND / M30–M44): HS v5/iid14/buf 0x4000, DATAACK on RX,
WD echo, optional Etch/SAS/CDS stub on dest 4004.

DATAACK (FIELD 2026-11-15 wire): count = 8 + payload_len per received BCL frame
  (10=SP, 44=KNOCK-body, 4008=8+4000 fragment limit). Not a cumulative counter.
SAS probe stages: none | dataack | challenge | challenge_rhmi | adaptive
  (see bcl_etch_stub). adaptive = challenge on OPEN, escalate on Phone TX.
"""

from __future__ import annotations

import hashlib
import os
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bcl_etch_stub import (
    SAS_PROBE_STAGES,
    EtchSasCdsStub,
    looks_like_knock_envelope,
)
from bcl_framer import (
    DEST_ETCH_DESK,
    DEST_WATCHDOG_DESK,
    INIT_MAGIC,
    BclFrame,
    BclFramer,
    build_synthetic_frame,
    cmd_desk_name,
)
from bcl_phone_tx_classify import classify_phone_frame

CMD_OPEN = 1
CMD_DATA = 2
CMD_CLOSE = 3
CMD_HANDSHAKE = 4
CMD_SELECTPROTO = 5
CMD_DATAACK = 6
CMD_KNOCK = 8

WATCHDOG_PING = bytes([0x13, 0x37, 0x13, 0x37])
WATCHDOG_INTERVAL_S = 5.0
WATCHDOG_TIMEOUT_S = 20.0
SESSION_INIT_INTERVAL_S = 1.0
PHONE_SRC = 1

# BclCarLink doKnock default: empty serial/bt/mac/wifi, appType 0 (A4A), param1 1.
KNOCK_DEFAULT_PAYLOAD = bytes(10) + struct.pack(">H", 1)

# Wire MyBMW after HS v5 (LAB_DUMMY_ETCH): UUID serial + TouchCommand/7.
KNOCK_WIRE_V5_PAYLOAD = (
    struct.pack(">H", 36)
    + b"0e9b90c4-cbe1-4742-8283-d367e9a56619"
    + struct.pack(">HHHHH", 0, 0, 0, 1, 7)
)

HU_PROFILES: dict[str, dict[str, Any]] = {
    "legacy": {
        "version": 3,
        "instance_id": 1,
        "buffer_size": 0x8000,
        "echo_watchdog": False,
        "send_dataack": False,
        "etch_stub": False,
        "sas_probe": "none",
        "handshake_delay_s": 0.0,
        "wd_pong_delay_s": 0.0,
        "etch_reply_src": None,
        "hu_open_srcs": (),
    },
    "f20": {
        "version": 5,
        "instance_id": 14,
        "buffer_size": 0x4000,
        "echo_watchdog": True,
        "send_dataack": True,
        "etch_stub": True,
        "sas_probe": "challenge",
        "handshake_delay_s": 0.0,
        "wd_pong_delay_s": 0.0,
        # 0 = mirror phone_src -> (phone_src, 4004) as on real F20 wire + BclMultiplexer Pair(src,dest)
        "etch_reply_src": 0,
        "hu_open_srcs": (),
    },
    "f20_sim": {
        "version": 5,
        "instance_id": 14,
        "buffer_size": 0x4000,
        "echo_watchdog": True,
        "send_dataack": True,
        "etch_stub": True,
        "sas_probe": "f20_full",
        "handshake_delay_s": 0.0,
        "wd_pong_delay_s": 0.0,
        "etch_reply_src": 0,
        "hu_open_srcs": (),
    },
}


def build_handshake(version: int, instance_id: int, buffer_size: int) -> bytes:
    return build_synthetic_frame(
        CMD_HANDSHAKE, 0, 0, struct.pack(">HHI", version, instance_id, buffer_size)
    )


def build_dataack(byte_count: int) -> bytes:
    """DATAACK src=0 dest=0 payload u32BE(count).

    Wire/BclCarLink: count = 8 + packet.data.size (full BCL frame size).
    Confirmed on F20: 10=8+2, 44=8+36, 4008=8+4000 (MAX_PAYLOAD).
    """
    return build_synthetic_frame(
        CMD_DATAACK, 0, 0, struct.pack(">I", int(byte_count))
    )


def dataack_count_for_frame(frame: BclFrame) -> int:
    """Canonical ACK value for one received BCL frame."""
    return 8 + len(frame.payload)


def parse_handshake(frame: BclFrame) -> dict | None:
    if frame.cmd != CMD_HANDSHAKE or len(frame.payload) != 8:
        return None
    version, instance_id, buffer_size = struct.unpack(">HHI", frame.payload)
    return {"version": version, "instance_id": instance_id, "buffer_size": buffer_size}


def parse_knock(payload: bytes) -> dict:
    """Best-effort BclPacket.Knock: serial_len|serial|…|appType|param1."""
    out: dict[str, Any] = {"raw_len": len(payload), "raw_hex": payload.hex()}
    if len(payload) < 2:
        return out
    sl = int.from_bytes(payload[:2], "big")
    if 2 + sl <= len(payload):
        serial = payload[2 : 2 + sl]
        try:
            out["serial"] = serial.decode("ascii")
        except UnicodeDecodeError:
            out["serial_hex"] = serial.hex()
        rest = payload[2 + sl :]
        # trailing: three u16 lens (often 0) + appType + param1
        if len(rest) >= 10:
            bt_l, mac_l, wifi_l, app_type, param1 = struct.unpack(">HHHHH", rest[:10])
            out.update(
                {
                    "bt_len": bt_l,
                    "mac_len": mac_l,
                    "wifi_len": wifi_l,
                    "appType": app_type,
                    "param1": param1,
                }
            )
    return out


def frame_event(direction: str, frame: BclFrame) -> dict:
    return {
        "event": "frame",
        "dir": direction,
        "cmd": frame.cmd,
        "cmd_name": cmd_desk_name(frame.cmd),
        "src": frame.src,
        "dest": frame.dest,
        "len": frame.length,
        "payload_hex": frame.payload[:64].hex(),
    }


def apply_hu_profile(name: str) -> dict[str, Any]:
    key = (name or "legacy").lower()
    if key not in HU_PROFILES:
        raise ValueError(f"unknown hu-profile {name!r}; choose {sorted(HU_PROFILES)}")
    return dict(HU_PROFILES[key])


@dataclass
class _Session:
    framer: BclFramer = field(default_factory=BclFramer)
    events: list[dict] = field(default_factory=list)

    def _parse(self, data: bytes, direction: str) -> tuple[int, list[BclFrame]]:
        res = self.framer.feed(data)
        for _ in range(res.session_inits):
            self.events.append({"event": "session_init", "dir": direction})
        for fr in res.frames:
            self.events.append(frame_event(direction, fr))
        if res.error:
            self.events.append({"event": "framer_error", "dir": direction, "detail": res.error_detail})
        return res.session_inits, res.frames


@dataclass
class ObserveOnlySession(_Session):
    """B2-B / passive: parse and log only — never emit bytes (tx_allowed=false)."""

    def on_bytes(self, data: bytes) -> list[bytes]:
        self._parse(data, "rx")
        self.events.append(
            {"event": "observe_rx", "n": len(data), "hex": data.hex()}
        )
        return []


@dataclass
class DummyHuSession(_Session):
    """HU role: answer the first session init with HANDSHAKE, then log / stub.

    Set observe_only=True for B2-B field mode (no BCL TX). Prefer ObserveOnlySession
    for clarity; this flag keeps lab_bcl_dummy_hu_a2dp callers simple if needed.
    """

    version: int = 3
    instance_id: int = 1
    buffer_size: int = 0x8000
    echo_watchdog: bool = False
    send_dataack: bool = False
    etch_stub: bool = False
    # SAS probe: none|dataack|challenge|challenge_rhmi|adaptive
    sas_probe: str = "challenge"
    # Field HS arrives ~3.0 s after RFCOMM-up; 0 = immediate (unit tests).
    handshake_delay_s: float = 0.0
    # C-L12 policies (only when echo_watchdog):
    #   wd_pong_max: stop echoing after N pongs (0 = unlimited)
    #   wd_pong_skip_mod: if >1, echo only when ping_index % mod == 1 (1-based)
    #   wd_pong_payload: override echo payload (None = mirror ping)
    #   wd_pong_delay_s: sleep before each pong (WD timeout probe)
    wd_pong_max: int = 0
    wd_pong_skip_mod: int = 0
    wd_pong_payload: bytes | None = None
    wd_pong_delay_s: float = 0.0
    # Etch TX shape: None → src=4004 dest=phone_src (desk);
    # set → src=etch_reply_src dest=4004 (field-shaped experiment).
    etch_reply_src: int | None = None
    # After first KNOCK, HU-initiated OPEN src→4004 for each port (lab probe).
    hu_open_srcs: tuple[int, ...] | list[int] = ()
    # After OPEN challenge, push field-like CDS (VIN/SOC/…) once (lab probe).
    cds_push: bool = False
    observe_only: bool = False
    handshake_sent: bool = False
    knocked: bool = False
    selected_proto: int | None = None
    last_knock: dict | None = None
    wd_ping_seen: int = 0
    wd_pong_sent: int = 0
    dataack_sent: int = 0
    hu_opens_sent: bool = False
    etch: EtchSasCdsStub | None = None

    def __post_init__(self) -> None:
        stage = (self.sas_probe or "challenge").lower()
        if stage not in SAS_PROBE_STAGES:
            raise ValueError(
                f"unknown sas_probe {self.sas_probe!r}; choose {list(SAS_PROBE_STAGES)}"
            )
        self.sas_probe = stage
        if isinstance(self.hu_open_srcs, list):
            self.hu_open_srcs = tuple(int(x) for x in self.hu_open_srcs)
        # Stage none ⇒ no etch replies; dataack/adaptive keep stub for observe/react.
        want_etch = self.etch_stub or stage in (
            "dataack",
            "challenge",
            "challenge_rhmi",
            "adaptive",
            "f20_full",
        )
        if stage == "none":
            want_etch = False
        if want_etch and self.etch is None:
            self.etch = EtchSasCdsStub(
                enabled=True,
                stage=stage,  # type: ignore[arg-type]
                cds_push=bool(self.cds_push),
            )
        elif self.etch is not None:
            self.etch.stage = stage if stage != "none" else "none"  # type: ignore[assignment]
            self.etch.enabled = stage != "none"
            self.etch.cds_push = bool(self.cds_push)

    def _etch_tx_ports(self, phone_src: int) -> tuple[int, int]:
        """Return (src, dest) for HU→Phone etch DATA frames.

        None → legacy desk guess (4004, phone_src);
        0    → F20 wire / BclMultiplexer tuple-invariant (phone_src, 4004);
        >0   → explicit fixed src (etch_reply_src, 4004).
        """
        if self.etch_reply_src is not None:
            src = int(phone_src) if int(self.etch_reply_src) == 0 else int(self.etch_reply_src)
            return src, DEST_ETCH_DESK
        return DEST_ETCH_DESK, int(phone_src)

    def _append_etch_tx(
        self, replies: list[bytes], phone_src: int, body: bytes, *, reason: str
    ) -> None:
        src, dest = self._etch_tx_ports(phone_src)
        replies.append(build_synthetic_frame(CMD_DATA, src, dest, body))
        self.events.append(
            {
                "event": "etch_data_tx",
                "src": src,
                "dest": dest,
                "len": len(body),
                "payload_hex": body[:64].hex(),
                "reason": reason,
                "etch_reply_mode": (
                    "field_src_dest4004"
                    if self.etch_reply_src is not None
                    else "desk_4004_to_phone"
                ),
            }
        )

    def inject_cds(self, updates: dict[str, Any]) -> list[bytes]:
        """Live HU→Phone CDS push for an already-open Dummy-HU session."""
        if self.etch is None:
            return []
        replies: list[bytes] = []
        for phone_src, body in self.etch.inject_cds_updates(updates):
            self._append_etch_tx(replies, phone_src, body, reason="inject_cds")
            if self.send_dataack:
                # No RX frame to ACK — skip DATAACK for unsolicited inject
                pass
        while self.etch.events:
            self.events.append(self.etch.events.pop(0))
        return replies

    def inject_rhmi_action(
        self,
        *,
        src: int,
        handle: int,
        action_id: int,
        args: dict[Any, Any] | None = None,
        ident: str | int = 0,
    ) -> list[bytes]:
        """Live HU→Phone iDrive action (rhmi_onActionEvent), e.g. Spotify skip/list select."""
        if self.etch is None:
            return []
        from etch_codec import encode_etch_packet

        mid = self.etch._next_msg_id()
        ev_args = dict(args) if args is not None else {0: 0}
        body = encode_etch_packet(
            "rhmi_onActionEvent",
            {
                "_messageId": mid,
                "handle": int(handle),
                "ident": ident,
                "actionId": int(action_id),
                "args": ev_args,
            },
        )
        replies: list[bytes] = []
        self._append_etch_tx(replies, int(src), body, reason="inject_rhmi_action")
        self.events.append(
            {
                "event": "rhmi_action_tx",
                "src": int(src),
                "handle": int(handle),
                "actionId": int(action_id),
                "args": ev_args,
                "ident": ident,
                "reason": "inject",
            }
        )
        return replies

    def _maybe_hu_open(self, replies: list[bytes]) -> None:
        if self.hu_opens_sent or not self.hu_open_srcs:
            return
        self.hu_opens_sent = True
        for src in self.hu_open_srcs:
            replies.append(
                build_synthetic_frame(CMD_OPEN, int(src), DEST_ETCH_DESK)
            )
            self.events.append(
                {
                    "event": "hu_open_tx",
                    "src": int(src),
                    "dest": DEST_ETCH_DESK,
                    "note": "LAB HU-initiated OPEN — not proven F20 wire order",
                }
            )

    def _note_knock_envelope(self, data: bytes) -> None:
        if not looks_like_knock_envelope(data):
            return
        self.knocked = True
        self.events.append(
            {
                "event": "knock_envelope_rx",
                "n": len(data),
                "hex": data[:64].hex(),
                "note": "deadbeef+UUID serial — not BclPacket cmd=8",
            }
        )

    def on_bytes(self, data: bytes) -> list[bytes]:
        self._note_knock_envelope(data)
        inits, frames = self._parse(data, "rx")
        if self.observe_only:
            self.events.append(
                {"event": "observe_rx", "n": len(data), "hex": data.hex()}
            )
            return []
        replies: list[bytes] = []
        if inits and not self.handshake_sent:
            if self.handshake_delay_s > 0:
                time.sleep(float(self.handshake_delay_s))
            replies.append(
                build_handshake(self.version, self.instance_id, self.buffer_size)
            )
            self.handshake_sent = True
            self.events.append(
                {
                    "event": "handshake_sent",
                    "version": self.version,
                    "instance_id": self.instance_id,
                    "buffer_size": self.buffer_size,
                    "delay_s": self.handshake_delay_s,
                }
            )
        for fr in frames:
            self.events.append(
                classify_phone_frame(fr.cmd, fr.src, fr.dest, fr.payload)
            )
            if self.send_dataack and fr.cmd != CMD_DATAACK:
                n = dataack_count_for_frame(fr)
                replies.append(build_dataack(n))
                self.dataack_sent += 1
                self.events.append(
                    {
                        "event": "dataack_tx",
                        "acked": n,
                        "payload_len": len(fr.payload),
                        "for_cmd": fr.cmd,
                        "for_cmd_name": cmd_desk_name(fr.cmd),
                    }
                )
            if fr.cmd == CMD_KNOCK:
                self.knocked = True
                self.last_knock = parse_knock(fr.payload)
                self.events.append({"event": "knock_rx", **self.last_knock})
                self._maybe_hu_open(replies)
            elif fr.cmd == CMD_DATA and looks_like_knock_envelope(fr.payload):
                self.knocked = True
                self.events.append(
                    {
                        "event": "knock_envelope_rx",
                        "via": "DATA",
                        "src": fr.src,
                        "dest": fr.dest,
                        "len": fr.length,
                    }
                )
                self._maybe_hu_open(replies)
            elif fr.cmd == CMD_SELECTPROTO and len(fr.payload) == 2:
                self.selected_proto = struct.unpack(">H", fr.payload)[0]
                self.events.append(
                    {"event": "selectproto_rx", "value": self.selected_proto}
                )
            elif fr.cmd == CMD_OPEN and fr.dest == DEST_ETCH_DESK:
                self.events.append(
                    {
                        "event": "etch_open_rx",
                        "src": fr.src,
                        "dest": fr.dest,
                        "sas_probe": self.sas_probe,
                    }
                )
                if self.etch is not None:
                    for body in self.etch.on_etch_open(fr.src):
                        self._append_etch_tx(
                            replies, fr.src, body, reason="open_probe"
                        )
                    while self.etch.events:
                        self.events.append(self.etch.events.pop(0))
            elif fr.cmd == CMD_CLOSE and fr.dest == DEST_ETCH_DESK:
                self.events.append(
                    {"event": "etch_close_rx", "src": fr.src, "dest": fr.dest}
                )
            elif (
                self.echo_watchdog
                and fr.cmd == CMD_DATA
                and fr.dest == DEST_WATCHDOG_DESK
            ):
                self.wd_ping_seen += 1
                idx = self.wd_ping_seen
                skip = self.wd_pong_skip_mod > 1 and (idx % self.wd_pong_skip_mod) != 1
                capped = self.wd_pong_max > 0 and self.wd_pong_sent >= self.wd_pong_max
                if skip or capped:
                    self.events.append(
                        {
                            "event": "watchdog_echo_skipped",
                            "ping_index": idx,
                            "reason": "skip_mod" if skip else "max",
                        }
                    )
                else:
                    if self.wd_pong_delay_s > 0:
                        time.sleep(float(self.wd_pong_delay_s))
                    payload = (
                        self.wd_pong_payload
                        if self.wd_pong_payload is not None
                        else fr.payload
                    )
                    replies.append(
                        build_synthetic_frame(CMD_DATA, fr.dest, fr.src, payload)
                    )
                    self.wd_pong_sent += 1
                    self.events.append(
                        {
                            "event": "watchdog_echo",
                            "ping_index": idx,
                            "pong_index": self.wd_pong_sent,
                            "payload_hex": payload.hex(),
                            "delay_s": self.wd_pong_delay_s,
                        }
                    )
            elif (
                self.etch is not None
                and fr.cmd == CMD_DATA
                and fr.dest == DEST_ETCH_DESK
            ):
                etch_payloads = list(self.etch.on_etch_data(fr.src, fr.payload))
                # adaptive: first Phone etch TX after challenge → escalate RHMI once
                if (
                    self.sas_probe == "adaptive"
                    and self.etch.challenges_sent > 0
                    and self.etch.rhmi_caps_sent == 0
                ):
                    etch_payloads.extend(self.etch.adaptive_escalate_rhmi(fr.src))
                while self.etch.events:
                    self.events.append(self.etch.events.pop(0))
                for body in etch_payloads:
                    self._append_etch_tx(
                        replies, fr.src, body, reason="etch_reply"
                    )
        return replies


# Lab stub PKCS7 blob — not a real cert; f20_sim accepts any sas_certificate bytes.
_STUB_PKCS7 = (
    b"-----BEGIN PKCS7-----\n"
    b"MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfnLABSIM\n"
    b"-----END PKCS7-----\n"
)

# CDS props MyBMW/AAIdrive typically subscribe after cds_create (subset of CDS_STUB_VALUES).
MYBMW_CDS_PROPS: tuple[str, ...] = (
    "vehicle.VIN",
    "vehicle.language",
    "vehicle.time",
    "engine.RPMSpeed",
    "engine.info",
    "sensors.battery",
    "sensors.fuel",
    "sensors.temperatureExterior",
    "driving.speedActual",
    "driving.speedDisplayed",
    "driving.odometer",
    "driving.gear",
    "driving.keyPosition",
    "navigation.GPSExtendedInfo",
    "controls.lights",
)


@dataclass
class PhoneClientSession(_Session):
    """Phone role in BclCarLink order; the caller repeats session_init() until handshake."""

    handshake: dict | None = None
    active: bool = False
    # Desk default 3 when HS version>3; Dummy-Wire used 2; MyBMW after v5 uses 4.
    selectproto: int | None = 3
    # Lab AAIdrive: OPEN src=5001 dst=5001 then OPEN src=10 dst=4004 (Etch).
    wire_open5001: bool = False
    open_etch: bool = False
    etch_src: int = 10
    # knock: None → desk empty A4A; "wire_v5" → UUID TouchCommand/7; bytes → raw
    knock_payload: bytes | str | None = None
    # True → skip CMD_KNOCK entirely (P1 isolation: SP→OPEN5001 without knock)
    skip_knock: bool = False
    # Full MyBMW/AAIdrive Etch client after OPEN 4004 (LAB sim — not real crypto).
    mybmw_sim: bool = False
    _msg_id: int = 1000
    _etch_stage: str = "idle"
    _challenge: bytes | None = None
    _handles: dict = field(default_factory=dict)
    _pending_tx: list = field(default_factory=list)
    _cds_props_queued: bool = False
    # RHMI resource plan (AAIdrive: DESCRIPTION → TEXTDB → IMAGEDB → initialize).
    # checkResource = cache probe; setResource only on miss — never auto-forced on hit.
    _rhmi_plan: list = field(default_factory=list)
    _rhmi_plan_i: int = 0
    _pending_check_mid: int | None = None
    _uploads_done: int = 0
    _cache_hits: int = 0
    # Explicit RHMI lifecycle (audit / W0): not the same as _etch_stage bootstrap tags.
    _rhmi_state: str = "DISCONNECTED"
    # messageId → open Etch transaction (request awaiting reply).
    _open_txns: dict = field(default_factory=dict)
    # W0 isolate: after first DESCRIPTION check, wait for reply only (no TEXTDB/init/setData).
    # Env BCL_RHMI_STOP_AFTER=description_check | off (default).
    rhmi_stop_after: str = ""
    # Phased RHMI soak after RUNTIME_ACTIVE (lab product-path probe).
    rhmi_soak: bool = False
    _soak_t0: float | None = None
    _soak_phase: str = ""
    _soak_next_t: float = 0.0
    _soak_i: int = 0
    _soak_counts: dict = field(default_factory=dict)

    def session_init(self) -> bytes:
        self.events.append({"event": "session_init", "dir": "tx"})
        return INIT_MAGIC

    def _set_rhmi_state(self, state: str, **extra: object) -> None:
        self._rhmi_state = state
        ev: dict = {"event": "mybmw_rhmi_state", "rhmi_state": state}
        ev.update(extra)
        self.events.append(ev)

    def _next_msg(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def forensic_snapshot(self) -> dict:
        """W0: classify why client may be waiting (watchdog ≠ RHMI)."""
        open_txns = [
            {
                "msg_id": mid,
                "method": meta.get("method"),
                "type": meta.get("type"),
                "bcl_src": meta.get("bcl_src"),
                "bcl_dest": meta.get("bcl_dest"),
            }
            for mid, meta in self._open_txns.items()
        ]
        wait_class = None
        if self._pending_check_mid is not None or any(
            t.get("method") == "rhmi_checkResource" for t in open_txns
        ):
            wait_class = "WATCHDOG_MISS_NO_ETCH_REPLY"
        elif self._rhmi_state == "RESOURCE_CHECKING":
            wait_class = "STATE_MACHINE_WAIT"
        elif self._rhmi_state in ("RHMI_INITIALIZED", "RUNTIME_ACTIVE"):
            wait_class = None
        return {
            "rhmi_state": self._rhmi_state,
            "etch_stage": self._etch_stage,
            "pending_check_mid": self._pending_check_mid,
            "open_txns": open_txns,
            "plan_i": self._rhmi_plan_i,
            "uploads": self._uploads_done,
            "cache_hits": self._cache_hits,
            "wait_class": wait_class,
            "soak_phase": self._soak_phase or None,
            "soak_counts": dict(self._soak_counts) if self._soak_counts else {},
            "soak_elapsed_s": (
                None if self._soak_t0 is None else round(time.time() - self._soak_t0, 1)
            ),
        }

    def _knock_bytes(self) -> bytes:
        kp = self.knock_payload
        if kp is None:
            return KNOCK_DEFAULT_PAYLOAD
        if kp == "wire_v5":
            return KNOCK_WIRE_V5_PAYLOAD
        if isinstance(kp, (bytes, bytearray)):
            return bytes(kp)
        raise TypeError("knock_payload must be None, 'wire_v5', or bytes")

    def _etch_data(self, body: bytes) -> bytes:
        return build_synthetic_frame(CMD_DATA, int(self.etch_src), DEST_ETCH_DESK, body)

    def _queue_rpc(self, type_name: str, fields: dict) -> None:
        from etch_codec import encode_etch_packet
        from bcl_framer import MAX_PAYLOAD

        body = encode_etch_packet(type_name, fields)
        mid = fields.get("_messageId")
        # BCL DATA payloads capped at MAX_PAYLOAD (4000); EtchChannelReassembler
        # stitches fragments — matches field cert / DESCRIPTION uploads.
        nfrag = 0
        for off in range(0, max(len(body), 1), MAX_PAYLOAD):
            self._pending_tx.append(self._etch_data(body[off : off + MAX_PAYLOAD]))
            nfrag += 1
        self.events.append(
            {
                "event": "mybmw_rpc_tx",
                "method": type_name,
                "msg_id": mid,
                "len": len(body),
                "fragments": nfrag,
                "bcl_src": int(self.etch_src),
                "bcl_dest": DEST_ETCH_DESK,
            }
        )
        if mid is not None and not str(type_name).startswith("_result_"):
            self._open_txns[int(mid)] = {
                "method": type_name,
                "bcl_src": int(self.etch_src),
                "bcl_dest": DEST_ETCH_DESK,
                "type": fields.get("type"),
                "handle": fields.get("handle"),
            }

    def _start_mybmw(self) -> None:
        if not self.mybmw_sim or self._etch_stage != "idle":
            return
        self._etch_stage = "sas_cert"
        self._queue_rpc(
            "sas_certificate",
            {"_messageId": self._next_msg(), "data": _STUB_PKCS7},
        )
        self.events.append({"event": "mybmw_sim_start", "etch_src": self.etch_src})

    def _queue_bootstrap(self) -> None:
        mid = self._next_msg
        self._queue_rpc("ver_getVersion", {"_messageId": mid()})
        self._queue_rpc("info_getSystemInfo", {"_messageId": mid()})
        self._queue_rpc(
            "rhmi_getCapabilities",
            {"_messageId": mid(), "hash": "", "capabilities": 255},
        )
        self._queue_rpc("cds_create", {"_messageId": mid()})
        self._queue_rpc("am_create", {"_messageId": mid()})
        self._queue_rpc("rhmi_create", {"_messageId": mid()})
        self._queue_rpc("av_create", {"_messageId": mid()})
        self._etch_stage = "bootstrap"

    def _queue_cds_and_apps(self) -> None:
        if self._cds_props_queued:
            return
        stop = (self.rhmi_stop_after or os.environ.get("BCL_RHMI_STOP_AFTER", "")).strip().lower()
        self.rhmi_stop_after = stop
        cds_h = int(self._handles.get("cds_create") or 10)
        am_h = int(self._handles.get("am_create") or 11)
        rhmi_h = int(self._handles.get("rhmi_create") or 12)
        av_h = int(self._handles.get("av_create") or 13)
        # W0: skip CDS flood so checkResource TX is unambiguous on the wire.
        cds_props = () if stop in ("description_check", "check", "w0") else MYBMW_CDS_PROPS
        for prop in cds_props:
            self._queue_rpc(
                "cds_addPropertyChangedEventHandler",
                {
                    "_messageId": self._next_msg(),
                    "handle": cds_h,
                    "ident": "0",
                    "propertyName": prop,
                    "intervalLimit": 0,
                },
            )
            self._queue_rpc(
                "cds_getPropertyAsync",
                {
                    "_messageId": self._next_msg(),
                    "handle": cds_h,
                    "ident": "0",
                    "propertyName": prop,
                },
            )
        # Multi-app AM wave mirroring field 17.11; W0 uses single AAIdrive only.
        am_apps = (
            (("net.basarsoft.a4a", "AAIdrive"),)
            if stop in ("description_check", "check", "w0")
            else (
                ("net.basarsoft.a4a", "AAIdrive"),
                ("androidautoidrive.com.spotify.music", "Spotify"),
                ("androidautoidrive.com.google.android.youtube", "YouTube"),
                (
                    "io.bimmergestalt.idriveconnectaddons.screenmirror",
                    "Screen Mirroring",
                ),
            )
        )
        for app_id, app_name in am_apps:
            self._queue_rpc(
                "am_registerApp",
                {
                    "_messageId": self._next_msg(),
                    "handle": am_h,
                    "id": app_id,
                    "name": app_name,
                    "category": "Multimedia",
                    "appId": app_id,
                    "appName": app_name,
                },
            )
        if stop not in ("description_check", "check", "w0"):
            self._queue_rpc(
                "av_requestConnection",
                {
                    "_messageId": self._next_msg(),
                    "handle": av_h,
                    "connectionType": 0,
                },
            )
        self._cds_props_queued = True
        self._etch_stage = "apps"
        self._set_rhmi_state("AM_REGISTERED", am_apps=len(am_apps))
        self.events.append(
            {
                "event": "mybmw_apps_queued",
                "handles": dict(self._handles),
                "cds_props": list(cds_props),
                "am_apps": len(am_apps),
                "stop_after": stop or None,
            }
        )
        # Start RHMI resource lifecycle (check per type; upload only on miss).
        self._build_rhmi_resource_plan()
        self._set_rhmi_state("RESOURCE_CHECKING")
        self._queue_next_rhmi_check()

    def _load_lab_description(self) -> bytes:
        """Load calendar/News DESCRIPTION fixture (lab-authorized size class ~13.6 KiB)."""
        candidates = [
            Path(os.environ["BCL_RHMI_DESCRIPTION"])
            if os.environ.get("BCL_RHMI_DESCRIPTION")
            else None,
            Path(__file__).resolve().parent / "fixtures" / "rhmi_description_lab_13598.xml",
            Path("/tmp/bcl_dummy/fixtures/rhmi_description_lab_13598.xml"),
        ]
        for p in candidates:
            if p is not None and p.is_file():
                return p.read_bytes()
        # Minimal fallback so dual-ESP smoke still exercises setResource path.
        return (
            b'<pluginApps><pluginApp applicationType="OnlineServices" '
            b'text="lab_menu" applicationWeight="1"></pluginApp></pluginApps>\n'
        )

    def _rtype(self, name: str):
        from etch_codec import EtchStruct

        return EtchStruct(
            "de.bmw.idrive.BMWRemoting.RHMIResourceType",
            {str(name): True},
        )

    def _build_rhmi_resource_plan(self) -> None:
        """AAIdrive order: DESCRIPTION → TEXTDB → IMAGEDB; then initialize.

        Env BCL_RHMI_CACHE_HIT=1: DESCRIPTION hash pre-known to HU → expect
        checkResource=true and no setResource (Fall A). Default: unknown digest
        → miss → setResource (Fall B).
        """
        desc = self._load_lab_description()
        desc_sha = hashlib.sha256(desc).hexdigest()
        if os.environ.get("BCL_RHMI_CACHE_HIT", "").strip() in ("1", "true", "yes"):
            desc_hash = desc_sha  # HU whitelist after prior persist, or seed
            desc_data: bytes | None = desc  # keep payload for optional force
            prefer_hit = True
        else:
            desc_hash = "lab_sim_unknown_digest"
            desc_data = desc
            prefer_hit = False
        stop = (self.rhmi_stop_after or os.environ.get("BCL_RHMI_STOP_AFTER", "")).strip().lower()
        self.rhmi_stop_after = stop
        # TEXTDB/IMAGEDB: no lab fixtures yet — check with stable digests; on miss
        # skip upload (log) rather than inventing F20-compatible DBs.
        self._rhmi_plan = [
            {
                "type_name": "DESCRIPTION",
                "hash": desc_hash,
                "size": len(desc),
                "name": "",
                "data": desc_data,
                "sha256": desc_sha,
                "prefer_hit": prefer_hit,
            },
        ]
        if stop not in ("description_check", "check", "w0"):
            self._rhmi_plan.extend(
                [
                    {
                        "type_name": "TEXTDB",
                        "hash": "lab_textdb_absent",
                        "size": 0,
                        "name": "",
                        "data": None,
                        "sha256": None,
                        "prefer_hit": False,
                    },
                    {
                        "type_name": "IMAGEDB",
                        "hash": "lab_imagedb_absent",
                        "size": 0,
                        "name": "",
                        "data": None,
                        "sha256": None,
                        "prefer_hit": False,
                    },
                ]
            )
        self._rhmi_plan_i = 0
        self._pending_check_mid = None
        self._uploads_done = 0
        self._cache_hits = 0
        self.events.append(
            {
                "event": "mybmw_rhmi_plan",
                "types": [p["type_name"] for p in self._rhmi_plan],
                "cache_hit_mode": prefer_hit,
                "stop_after": stop or None,
            }
        )

    def _queue_next_rhmi_check(self) -> None:
        if self._rhmi_plan_i >= len(self._rhmi_plan):
            # W0 isolate: after DESCRIPTION check (+ optional miss upload), hold — no init/setData.
            if self.rhmi_stop_after in ("description_check", "check", "w0"):
                self._set_rhmi_state(
                    "RESOURCE_CHECKING",
                    note="stop_after_description_check_waiting_reply_or_hold",
                )
                self.events.append(
                    {
                        "event": "mybmw_rhmi_hold_after_check",
                        "stop_after": self.rhmi_stop_after,
                        "uploads": self._uploads_done,
                        "cache_hits": self._cache_hits,
                        "pending_check_mid": self._pending_check_mid,
                        "open_txns": list(self._open_txns),
                    }
                )
                return
            self._queue_rhmi_initialize_and_runtime()
            return
        item = self._rhmi_plan[self._rhmi_plan_i]
        rhmi_h = int(self._handles.get("rhmi_create") or 12)
        mid = self._next_msg()
        self._pending_check_mid = mid
        fields = {
            "_messageId": mid,
            "handle": rhmi_h,
            "hash": item["hash"],
            "type": self._rtype(item["type_name"]),
        }
        if item.get("size") is not None:
            fields["size"] = int(item["size"])
        if item.get("name") is not None:
            fields["name"] = str(item["name"])
        self._queue_rpc("rhmi_checkResource", fields)
        if mid in self._open_txns:
            self._open_txns[int(mid)]["type"] = item["type_name"]
            self._open_txns[int(mid)]["hash"] = item["hash"]
            self._open_txns[int(mid)]["size"] = item.get("size")
        self.events.append(
            {
                "event": "mybmw_check_resource_tx",
                "type": item["type_name"],
                "hash": item["hash"],
                "size": item.get("size"),
                "name": item.get("name"),
                "handle": rhmi_h,
                "msg_id": mid,
                "plan_i": self._rhmi_plan_i,
                "bcl_src": int(self.etch_src),
                "bcl_dest": DEST_ETCH_DESK,
                "rhmi_state": self._rhmi_state,
            }
        )

    def _on_check_resource_result(self, *, result: object, in_reply_to: object) -> None:
        """Cache hit → next type / initialize. Cache miss → setResource only if we have data."""
        if in_reply_to is not None:
            self._open_txns.pop(int(in_reply_to), None)
        if (
            self._pending_check_mid is not None
            and in_reply_to is not None
            and int(in_reply_to) != int(self._pending_check_mid)
        ):
            self.events.append(
                {
                    "event": "mybmw_check_resource_orphan",
                    "inReplyTo": in_reply_to,
                    "expected": self._pending_check_mid,
                    "wait_class": "WATCHDOG_MISS_REPLY_UNMATCHED",
                }
            )
            return
        if self._rhmi_plan_i >= len(self._rhmi_plan):
            return
        item = self._rhmi_plan[self._rhmi_plan_i]
        known = result is True
        self.events.append(
            {
                "event": "mybmw_check_resource_rx",
                "type": item["type_name"],
                "hash": item["hash"],
                "result": result,
                "cache": "hit" if known else "miss",
                "inReplyTo": in_reply_to,
                "msg_id": in_reply_to,
                "plan_i": self._rhmi_plan_i,
                "handle": int(self._handles.get("rhmi_create") or 12),
                "bcl_src": int(self.etch_src),
                "bcl_dest": DEST_ETCH_DESK,
                "rhmi_state": self._rhmi_state,
            }
        )
        if known:
            self._cache_hits += 1
        else:
            data = item.get("data")
            # W0 isolate: observe reply only — do not auto-upload even on miss.
            if self.rhmi_stop_after in ("description_check", "check", "w0"):
                self.events.append(
                    {
                        "event": "mybmw_set_resource_skipped",
                        "type": item["type_name"],
                        "reason": "stop_after_no_upload",
                        "cache": "miss",
                    }
                )
            elif isinstance(data, (bytes, bytearray)) and data:
                self._set_rhmi_state("RESOURCE_UPLOAD", type=item["type_name"])
                rhmi_h = int(self._handles.get("rhmi_create") or 12)
                digest = item.get("sha256") or hashlib.sha256(bytes(data)).hexdigest()
                self._queue_rpc(
                    "rhmi_setResource",
                    {
                        "_messageId": self._next_msg(),
                        "handle": rhmi_h,
                        "hash": digest,
                        "type": self._rtype(item["type_name"]),
                        "data": bytes(data),
                    },
                )
                self._uploads_done += 1
                self.events.append(
                    {
                        "event": "mybmw_set_resource_tx",
                        "type": item["type_name"],
                        "bytes": len(data),
                        "sha256": digest,
                        "bcl_src": int(self.etch_src),
                        "bcl_dest": DEST_ETCH_DESK,
                    }
                )
            else:
                # Miss without local payload: do not invent F20 DBs; advance (lab).
                self.events.append(
                    {
                        "event": "mybmw_set_resource_skipped",
                        "type": item["type_name"],
                        "reason": "cache_miss_no_local_payload",
                    }
                )
        self._rhmi_plan_i += 1
        self._pending_check_mid = None
        if self._rhmi_plan_i < len(self._rhmi_plan):
            self._set_rhmi_state("RESOURCE_CHECKING", next_type=self._rhmi_plan[self._rhmi_plan_i]["type_name"])
        self._queue_next_rhmi_check()

    def queue_set_data(self, model_id: int, value: object, *, reason: str = "soak") -> None:
        """Queue an additional rhmi_setData after bootstrap (own UI data path)."""
        if self._rhmi_state not in ("RHMI_INITIALIZED", "RUNTIME_ACTIVE"):
            return
        rhmi_h = int(self._handles.get("rhmi_create") or 12)
        self._queue_rpc(
            "rhmi_setData",
            {
                "_messageId": self._next_msg(),
                "handle": rhmi_h,
                "modelId": int(model_id),
                "value": value,
            },
        )
        self._soak_counts["setData"] = int(self._soak_counts.get("setData") or 0) + 1
        self.events.append(
            {
                "event": "mybmw_soak_setData",
                "phase": self._soak_phase,
                "reason": reason,
                "modelId": int(model_id),
                "value": value if isinstance(value, (str, int, float, bool)) or value is None else type(value).__name__,
            }
        )

    def queue_set_property(
        self,
        component_id: int,
        property_id: int,
        value: object,
        *,
        reason: str = "soak",
    ) -> None:
        if self._rhmi_state not in ("RHMI_INITIALIZED", "RUNTIME_ACTIVE"):
            return
        rhmi_h = int(self._handles.get("rhmi_create") or 12)
        self._queue_rpc(
            "rhmi_setProperty",
            {
                "_messageId": self._next_msg(),
                "handle": rhmi_h,
                "componentId": int(component_id),
                "propertyId": int(property_id),
                "values": {0: value},
            },
        )
        self._soak_counts["setProperty"] = int(self._soak_counts.get("setProperty") or 0) + 1
        self.events.append(
            {
                "event": "mybmw_soak_setProperty",
                "phase": self._soak_phase,
                "reason": reason,
                "componentId": int(component_id),
                "propertyId": int(property_id),
            }
        )

    def _ack_action_event(self, fields: dict) -> None:
        """Acknowledge HU→phone rhmi_onActionEvent (product interaction path)."""
        rhmi_h = int(fields.get("handle") or self._handles.get("rhmi_create") or 12)
        action_id = fields.get("actionId")
        ident = fields.get("ident", 0)
        mid = fields.get("_messageId")
        self._queue_rpc(
            "rhmi_ackActionEvent",
            {
                "_messageId": self._next_msg(),
                "handle": rhmi_h,
                "actionId": int(action_id) if action_id is not None else 0,
                "ident": ident if ident is not None else 0,
            },
        )
        self._soak_counts["ackAction"] = int(self._soak_counts.get("ackAction") or 0) + 1
        self.events.append(
            {
                "event": "mybmw_action_ack_tx",
                "in_reply_to": mid,
                "handle": rhmi_h,
                "actionId": action_id,
                "ident": ident,
                "phase": self._soak_phase or None,
            }
        )

    def tick_rhmi_soak(self, now: float) -> None:
        """Drive phased post-RUNTIME_ACTIVE RHMI traffic (setData / setProperty).

        Phases (seconds after RUNTIME_ACTIVE):
          0–60   stabilize
          60–180 setData repeat (models 100/101)
          180–300 multi-model setData + light setProperty
          300–420 actions expected from HU (phone only acks)
          420–600 mixed setData + setProperty
        """
        if not self.rhmi_soak or self._rhmi_state != "RUNTIME_ACTIVE":
            return
        if self._soak_t0 is None:
            self._soak_t0 = now
            self._soak_phase = "stabilize"
            self._soak_next_t = now + 60.0
            self.events.append(
                {
                    "event": "mybmw_soak_start",
                    "phase": "stabilize",
                    "note": "0-60s stabilize after RUNTIME_ACTIVE",
                }
            )
            return
        elapsed = now - self._soak_t0
        if elapsed < 60:
            phase = "stabilize"
        elif elapsed < 180:
            phase = "setData_repeat"
        elif elapsed < 300:
            phase = "multi_model"
        elif elapsed < 420:
            phase = "actions_window"
        else:
            phase = "mixed"
        if phase != self._soak_phase:
            self._soak_phase = phase
            self._soak_next_t = now
            self.events.append(
                {
                    "event": "mybmw_soak_phase",
                    "phase": phase,
                    "elapsed_s": round(elapsed, 1),
                    "counts": dict(self._soak_counts),
                }
            )
        if now < self._soak_next_t:
            return
        self._soak_i += 1
        i = self._soak_i
        if phase == "stabilize":
            self._soak_next_t = now + 5.0
            return
        if phase == "setData_repeat":
            # Known-good string models from lifecycle PASS.
            texts = ("PiDrive", "Apps", "Durchsuchen", f"PiDrive-{i}")
            model = 100 if (i % 2) == 0 else 101
            self.queue_set_data(model, texts[i % len(texts)], reason="soak_repeat")
            self._soak_next_t = now + 5.0
            return
        if phase == "multi_model":
            # Stick to accepted string models; avoid modelId 4 (known SE 213).
            combo = (
                (100, f"Apps-{i}"),
                (101, f"Search-{i}"),
                (100, "PiDrive"),
                (101, "PiDrive-Menu"),
            )
            mid, val = combo[i % len(combo)]
            self.queue_set_data(mid, val, reason="soak_multi")
            if i % 4 == 0:
                # Light property poke (component/property ids lab-exploratory).
                self.queue_set_property(1, 18, True, reason="soak_multi")
            self._soak_next_t = now + 4.0
            return
        if phase == "actions_window":
            # HU inject drives actions; phone only acks when events arrive.
            self._soak_next_t = now + 5.0
            return
        # mixed
        model = 100 if (i % 2) == 0 else 101
        self.queue_set_data(model, f"PiDrive-mixed-{i}", reason="soak_mixed")
        if i % 3 == 0:
            self.queue_set_property(1, 18, (i % 2) == 0, reason="soak_mixed")
        self._soak_next_t = now + 4.0

    def _queue_rhmi_initialize_and_runtime(self) -> None:
        """After full check sequence: initialize → setData shell + ImageID←0 probe."""
        if self._etch_stage in ("menu_upload", "rhmi_runtime"):
            return
        from etch_codec import EtchStruct

        rhmi_h = int(self._handles.get("rhmi_create") or 12)
        self._queue_rpc(
            "rhmi_initialize",
            {"_messageId": self._next_msg(), "handle": rhmi_h},
        )
        for model_id, text in ((100, "Apps"), (101, "Durchsuchen")):
            self._queue_rpc(
                "rhmi_setData",
                {
                    "_messageId": self._next_msg(),
                    "handle": rhmi_h,
                    "modelId": model_id,
                    "value": text,
                },
            )
        self._queue_rpc(
            "rhmi_setData",
            {
                "_messageId": self._next_msg(),
                "handle": rhmi_h,
                "modelId": 4,
                "value": EtchStruct(
                    "de.bmw.idrive.BMWRemoting.RHMIResourceIdentifier",
                    {"id": 0},
                ),
            },
        )
        self._etch_stage = "rhmi_runtime"
        self._set_rhmi_state("RHMI_INITIALIZED")
        self._set_rhmi_state("RUNTIME_ACTIVE")
        desc_item = next(
            (p for p in self._rhmi_plan if p["type_name"] == "DESCRIPTION"),
            None,
        )
        self.events.append(
            {
                "event": "mybmw_menu_upload_queued",
                "description_bytes": (desc_item or {}).get("size"),
                "sha256": (desc_item or {}).get("sha256"),
                "uploads": self._uploads_done,
                "cache_hits": self._cache_hits,
                "rhmi_state": self._rhmi_state,
                "note": "initialize after check sequence; setResource only on misses",
            }
        )

    def drain_tx(self) -> list[bytes]:
        """Return and clear queued MyBMW Etch DATA frames (caller sends on RFCOMM)."""
        out = list(self._pending_tx)
        self._pending_tx.clear()
        return out

    def on_bytes(self, data: bytes) -> list[bytes]:
        _, frames = self._parse(data, "rx")
        out: list[bytes] = []
        for fr in frames:
            if self.handshake is None:
                hs = parse_handshake(fr)
                if hs is None:
                    self.events.append({"event": "unexpected_before_handshake", "cmd": fr.cmd})
                    continue
                self.handshake = hs
                sp = self.selectproto
                # Auto wire SP4+UUID knock when HS v5+ and caller left desk default 3.
                if sp == 3 and hs["version"] >= 5:
                    sp = 4
                    self.knock_payload = self.knock_payload or "wire_v5"
                # Explicit SP4+ also gets wire knock unless caller overrode knock_payload.
                elif sp is not None and int(sp) >= 4:
                    self.knock_payload = self.knock_payload or "wire_v5"
                if sp is not None and (hs["version"] > 3 or sp != 3):
                    out.append(
                        build_synthetic_frame(CMD_SELECTPROTO, 0, 0, struct.pack(">H", int(sp)))
                    )
                if not self.skip_knock:
                    out.append(build_synthetic_frame(CMD_KNOCK, 0, 0, self._knock_bytes()))
                else:
                    self.events.append({"event": "knock_skipped", "dir": "tx"})
                if self.wire_open5001:
                    out.append(
                        build_synthetic_frame(CMD_OPEN, DEST_WATCHDOG_DESK, DEST_WATCHDOG_DESK)
                    )
                else:
                    out.append(build_synthetic_frame(CMD_OPEN, PHONE_SRC, DEST_WATCHDOG_DESK))
                if self.open_etch or self.mybmw_sim:
                    self.open_etch = True
                    out.append(
                        build_synthetic_frame(CMD_OPEN, int(self.etch_src), DEST_ETCH_DESK)
                    )
                self.active = True
                if self.mybmw_sim:
                    # Start Etch after OPEN 4004 is on the wire (next poll drains).
                    self._start_mybmw()
                continue

            # Post-handshake: MyBMW Etch reply handling
            if not self.mybmw_sim or fr.cmd != CMD_DATA:
                continue
            # F20 mirrors replies on (phone_src, 4004); accept Etch either way.
            if DEST_ETCH_DESK not in (fr.src, fr.dest) and fr.src != int(self.etch_src):
                continue
            try:
                from etch_codec import decode_etch_message

                dec = decode_etch_message(fr.payload)
            except Exception as exc:  # noqa: BLE001
                self.events.append(
                    {
                        "event": "mybmw_etch_decode_err",
                        "err": str(exc),
                        "len": len(fr.payload),
                    }
                )
                continue
            method = dec.get("method") or ""
            fields = dec.get("raw_fields") or {}
            self.events.append(
                {
                    "event": "mybmw_rpc_rx",
                    "method": method,
                    "len": len(fr.payload),
                }
            )
            # Close open Etch TXN on any _result_* with matching _inReplyTo.
            if method.startswith("_result_") and fields.get("_inReplyTo") is not None:
                self._open_txns.pop(int(fields["_inReplyTo"]), None)

            if method == "_result_sas_certificate":
                chal = fields.get("result")
                if isinstance(chal, (bytes, bytearray)):
                    self._challenge = bytes(chal)
                self._etch_stage = "sas_login"
                sig = (self._challenge or bytes(16)) + bytes(496)
                self._queue_rpc(
                    "sas_login",
                    {"_messageId": self._next_msg(), "data": sig[:512]},
                )
            elif method == "_result_sas_login":
                self._etch_stage = "bootstrap"
                self._set_rhmi_state("SAS_AUTHENTICATED")
                self._queue_bootstrap()
            elif method.startswith("_result_") and method.endswith(
                ("_create", "_create_version")
            ):
                base = method[len("_result_") :]
                if isinstance(fields.get("result"), int):
                    self._handles[base] = int(fields["result"])
                    self.events.append(
                        {
                            "event": "mybmw_handle",
                            "method": base,
                            "handle": int(fields["result"]),
                        }
                    )
                    if base == "rhmi_create":
                        self._set_rhmi_state("RHMI_CREATED", handle=int(fields["result"]))
                # When we have cds+am+rhmi+av, queue subscriptions
                need = ("cds_create", "am_create", "rhmi_create", "av_create")
                if all(k in self._handles for k in need):
                    self._queue_cds_and_apps()
            elif method == "_result_rhmi_checkResource":
                # Cache hit → next type / initialize. Miss → setResource only if payload.
                self._on_check_resource_result(
                    result=fields.get("result"),
                    in_reply_to=fields.get("_inReplyTo"),
                )
            elif method == "_result_rhmi_setData":
                res = fields.get("result")
                from etch_codec import EtchStruct

                if isinstance(res, EtchStruct) and "ServiceException" in res.type_name:
                    self.events.append(
                        {
                            "event": "mybmw_setdata_service_exception",
                            "errorCode": (res.fields or {}).get("errorCode"),
                            "detailMessage": (res.fields or {}).get("detailMessage"),
                        }
                    )
            elif method == "rhmi_onActionEvent":
                self.events.append(
                    {
                        "event": "mybmw_action_event_rx",
                        "handle": fields.get("handle"),
                        "actionId": fields.get("actionId"),
                        "ident": fields.get("ident"),
                        "args": fields.get("args"),
                        "msg_id": fields.get("_messageId"),
                        "phase": self._soak_phase or None,
                    }
                )
                self._soak_counts["actionRx"] = int(self._soak_counts.get("actionRx") or 0) + 1
                self._ack_action_event(fields)
            elif method == "cds_onPropertyChangedEvent":
                self.events.append(
                    {
                        "event": "mybmw_cds_event",
                        "property": fields.get("propertyName"),
                        "value": fields.get("propertyValue"),
                    }
                )
        out.extend(self.drain_tx())
        return out

    def watchdog_ping(self) -> bytes:
        src = DEST_WATCHDOG_DESK if self.wire_open5001 else PHONE_SRC
        return build_synthetic_frame(CMD_DATA, src, DEST_WATCHDOG_DESK, WATCHDOG_PING)


def summarize(events: list[dict]) -> dict:
    """Counts per event kind and per rx/tx command name."""
    out: dict = {"session_init": 0, "frames": {}, "framer_error": False}
    for ev in events:
        if ev["event"] == "session_init":
            out["session_init"] += 1
        elif ev["event"] == "frame":
            key = f"{ev['dir']}:{ev['cmd_name']}"
            out["frames"][key] = out["frames"].get(key, 0) + 1
        elif ev["event"] == "framer_error":
            out["framer_error"] = True
        elif ev["event"] in (
            "handshake_sent",
            "watchdog_echo",
            "dataack_tx",
            "sas_challenge_tx",
            "cds_property_tx",
            "rhmi_capabilities_tx",
            "knock_envelope_rx",
            "etch_open_probe",
        ):
            out[ev["event"]] = out.get(ev["event"], 0) + 1
    return out
