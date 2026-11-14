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
    DEST_ETCH_DESK,
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
    # C-L12 policies (only when echo_watchdog):
    #   wd_pong_max: stop echoing after N pongs (0 = unlimited)
    #   wd_pong_skip_mod: if >1, echo only when ping_index % mod == 1 (1-based)
    #   wd_pong_payload: override echo payload (None = mirror ping)
    wd_pong_max: int = 0
    wd_pong_skip_mod: int = 0
    wd_pong_payload: bytes | None = None
    observe_only: bool = False
    handshake_sent: bool = False
    knocked: bool = False
    selected_proto: int | None = None
    wd_ping_seen: int = 0
    wd_pong_sent: int = 0

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
                    continue
                payload = (
                    self.wd_pong_payload
                    if self.wd_pong_payload is not None
                    else fr.payload
                )
                replies.append(build_synthetic_frame(CMD_DATA, fr.dest, fr.src, payload))
                self.wd_pong_sent += 1
                self.events.append(
                    {
                        "event": "watchdog_echo",
                        "ping_index": idx,
                        "pong_index": self.wd_pong_sent,
                        "payload_hex": payload.hex(),
                    }
                )
        return replies


@dataclass
class PhoneClientSession(_Session):
    """Phone role in BclCarLink order; the caller repeats session_init() until handshake."""

    handshake: dict | None = None
    active: bool = False
    # Desk default 3 when HS version>3; Dummy-Wire used 2 — set via field --selectproto.
    selectproto: int | None = 3
    # Lab AAIdrive: OPEN src=5001 dst=5001 then OPEN src=10 dst=4004 (Etch).
    wire_open5001: bool = False
    open_etch: bool = False
    etch_src: int = 10

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
            sp = self.selectproto
            if sp is not None and (hs["version"] > 3 or sp != 3):
                # version>3 → always SP; explicit non-3 (e.g. wire SP2) also after any HS
                out.append(
                    build_synthetic_frame(CMD_SELECTPROTO, 0, 0, struct.pack(">H", int(sp)))
                )
            out.append(build_synthetic_frame(CMD_KNOCK, 0, 0, KNOCK_DEFAULT_PAYLOAD))
            if self.wire_open5001:
                # Lab wire: OPEN watchdog with src=dest=5001
                out.append(
                    build_synthetic_frame(CMD_OPEN, DEST_WATCHDOG_DESK, DEST_WATCHDOG_DESK)
                )
            else:
                out.append(build_synthetic_frame(CMD_OPEN, PHONE_SRC, DEST_WATCHDOG_DESK))
            if self.open_etch:
                out.append(
                    build_synthetic_frame(CMD_OPEN, int(self.etch_src), DEST_ETCH_DESK)
                )
            self.active = True
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
        elif ev["event"] in ("handshake_sent", "watchdog_echo"):
            out[ev["event"]] = out.get(ev["event"], 0) + 1
    return out
