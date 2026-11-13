#!/usr/bin/env python3
"""BCL session logic for the lab Dummy-HU and a BclCarLink-like phone client.

Pure byte-in / byte-out state machines (no Bluetooth), so the order of the
handshake can be host-tested and reused by bcl_dummy_hu_agent.py on .108.

Desk sequence (BclCarLink BclClientTransport, not own BMW wire FACT):
  phone → HU  12 34 56 78            (repeated ~1 s until HANDSHAKE)
  HU → phone  HANDSHAKE cmd 4, payload version u16 | instanceId u16 | bufferSize u32
  phone → HU  SELECTPROTO(3)         (only if version > 3)
  phone → HU  KNOCK len 12
  phone → HU  OPEN / DATA ...        (watchdog: dest 5001, ping 13 37 13 37 every 5 s)

HU replies after HANDSHAKE are UNKNOWN (no capture); the dummy stays silent
unless echo_watchdog is set.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from bcl_framer import (
    DEST_WATCHDOG_DESK,
    INIT_MAGIC,
    BclFrame,
    BclFramer,
    build_synthetic_frame,
    cmd_desk_name,
)

CMD_OPEN = 1
CMD_DATA = 2
CMD_HANDSHAKE = 4
CMD_SELECTPROTO = 5
CMD_KNOCK = 8

WATCHDOG_PING = bytes([0x13, 0x37, 0x13, 0x37])
WATCHDOG_INTERVAL_S = 5.0
WATCHDOG_TIMEOUT_S = 20.0
SESSION_INIT_INTERVAL_S = 1.0
PHONE_SRC = 1

# BclCarLink doKnock default: empty serial/bt/mac/wifi, appType 0 (A4A), param1 1.
KNOCK_DEFAULT_PAYLOAD = bytes(10) + struct.pack(">H", 1)


def build_handshake(version: int, instance_id: int, buffer_size: int) -> bytes:
    return build_synthetic_frame(
        CMD_HANDSHAKE, 0, 0, struct.pack(">HHI", version, instance_id, buffer_size)
    )


def parse_handshake(frame: BclFrame) -> dict | None:
    if frame.cmd != CMD_HANDSHAKE or len(frame.payload) != 8:
        return None
    version, instance_id, buffer_size = struct.unpack(">HHI", frame.payload)
    return {"version": version, "instance_id": instance_id, "buffer_size": buffer_size}


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
    """HU role: answer the first session init with HANDSHAKE, then log.

    Set observe_only=True for B2-B field mode (no BCL TX). Prefer ObserveOnlySession
    for clarity; this flag keeps lab_bcl_dummy_hu_a2dp callers simple if needed.
    """

    version: int = 3
    instance_id: int = 1
    buffer_size: int = 0x8000
    echo_watchdog: bool = False
    observe_only: bool = False
    handshake_sent: bool = False
    knocked: bool = False
    selected_proto: int | None = None

    def on_bytes(self, data: bytes) -> list[bytes]:
        inits, frames = self._parse(data, "rx")
        if self.observe_only:
            self.events.append(
                {"event": "observe_rx", "n": len(data), "hex": data.hex()}
            )
            return []
        replies: list[bytes] = []
        if inits and not self.handshake_sent:
            replies.append(build_handshake(self.version, self.instance_id, self.buffer_size))
            self.handshake_sent = True
            self.events.append({"event": "handshake_sent", "version": self.version})
        for fr in frames:
            if fr.cmd == CMD_KNOCK:
                self.knocked = True
            elif fr.cmd == CMD_SELECTPROTO and len(fr.payload) == 2:
                self.selected_proto = struct.unpack(">H", fr.payload)[0]
            elif (
                self.echo_watchdog
                and fr.cmd == CMD_DATA
                and fr.dest == DEST_WATCHDOG_DESK
            ):
                replies.append(build_synthetic_frame(CMD_DATA, fr.dest, fr.src, fr.payload))
                self.events.append({"event": "watchdog_echo"})
        return replies


@dataclass
class PhoneClientSession(_Session):
    """Phone role in BclCarLink order; the caller repeats session_init() until handshake."""

    handshake: dict | None = None
    active: bool = False

    def session_init(self) -> bytes:
        self.events.append({"event": "session_init", "dir": "tx"})
        return INIT_MAGIC

    def on_bytes(self, data: bytes) -> list[bytes]:
        _, frames = self._parse(data, "rx")
        out: list[bytes] = []
        for fr in frames:
            if self.handshake is not None:
                continue
            hs = parse_handshake(fr)
            if hs is None:
                self.events.append({"event": "unexpected_before_handshake", "cmd": fr.cmd})
                continue
            self.handshake = hs
            if hs["version"] > 3:
                out.append(build_synthetic_frame(CMD_SELECTPROTO, 0, 0, struct.pack(">H", 3)))
            out.append(build_synthetic_frame(CMD_KNOCK, 0, 0, KNOCK_DEFAULT_PAYLOAD))
            out.append(build_synthetic_frame(CMD_OPEN, PHONE_SRC, DEST_WATCHDOG_DESK))
            self.active = True
        return out

    def watchdog_ping(self) -> bytes:
        return build_synthetic_frame(CMD_DATA, PHONE_SRC, DEST_WATCHDOG_DESK, WATCHDOG_PING)


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
        elif ev["event"] in ("handshake_sent", "watchdog_echo"):
            out[ev["event"]] = out.get(ev["event"], 0) + 1
    return out
