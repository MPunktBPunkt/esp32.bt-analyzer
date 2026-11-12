#!/usr/bin/env python3
"""Streaming BCL 8-byte-header framer (Python port of hu-probe BclFramer).

Header (desk evidence, not own BMW wire FACT):
  command u16 BE | src u16 BE | dest u16 BE | dataLen u16 BE | payload

Epistemic: synthetic / host tests prove parser mechanics only —
not NBT Evo / AOA / BT wire behaviour.

  python3 -m unittest tests/host/test_bcl_framer.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable

HEADER_SIZE = 8
MAX_PAYLOAD = 4000  # desk practical limit (protocol-bcl.md / BclCarLink)

DEST_ETCH_DESK = 0x0FA4
DEST_WATCHDOG_DESK = 0x1389

CMD_NAMES = {
    1: "OPEN",
    2: "DATA",
    3: "CLOSE",
    4: "HANDSHAKE",
    5: "SELECTPROTO",
    6: "DATAACK",
    7: "ACK",
    8: "KNOCK",
    9: "LAUNCH",
    10: "HANGUP",
    11: "BROADCAST",
    12: "REGISTER",
}


class BclParseError(IntEnum):
    NONE = 0
    PAYLOAD_TOO_LARGE = 1


@dataclass
class BclFrame:
    cmd: int
    src: int
    dest: int
    length: int
    payload: bytes
    raw: bytes

    def as_dict(self) -> dict:
        return {
            "cmd": self.cmd,
            "cmd_name": cmd_desk_name(self.cmd),
            "src": self.src,
            "dest": self.dest,
            "dest_label": dest_desk_label(self.dest),
            "len": self.length,
            "payload_hex": self.payload.hex(),
            "raw_hex": self.raw.hex(),
        }


@dataclass
class BclFeedResult:
    frames: list[BclFrame] = field(default_factory=list)
    incomplete: bool = False
    error: bool = False
    error_code: BclParseError = BclParseError.NONE
    error_detail: str = ""


def cmd_desk_name(cmd: int) -> str:
    return CMD_NAMES.get(cmd, "UNKNOWN")


def dest_desk_label(dest: int) -> str | None:
    if dest == DEST_ETCH_DESK:
        return "Etch"
    if dest == DEST_WATCHDOG_DESK:
        return "Watchdog"
    return None


def _be16(n: int) -> bytes:
    return bytes([(n >> 8) & 0xFF, n & 0xFF])


def _read_be16(buf: bytes | bytearray, off: int) -> int:
    return (buf[off] << 8) | buf[off + 1]


def build_synthetic_frame(
    cmd: int, src: int, dest: int, payload: bytes | bytearray | memoryview = b""
) -> bytes:
    """Build one BCL frame. Raises ValueError if payload > MAX_PAYLOAD."""
    payload = bytes(payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload {len(payload)} > MAX_PAYLOAD {MAX_PAYLOAD}")
    return _be16(cmd) + _be16(src) + _be16(dest) + _be16(len(payload)) + payload


# Fixed chunk sizes from hu-probe CaC1LabBclStream (fragmentation exercise).
CA_C1_LAB_CHUNKS: tuple[int, ...] = (1, 3, 2, 8, 5, 1000)


def build_ca_c1_lab_bcl_stream() -> bytes:
    """Deterministic synthetic stream from hu-probe CaC1LabBclStream.h.

    1) HANDSHAKE cmd=4, 8 zero payload
    2) DATA dest=0x0FA4, payload b'SYNTH01'
    3) Unknown cmd 0x00EE, zero payload
    4) Malformed len=4001 header → PayloadTooLarge
    """
    parts = [
        build_synthetic_frame(4, 0, 0, bytes(8)),
        build_synthetic_frame(2, 1, DEST_ETCH_DESK, b"SYNTH01"),
        build_synthetic_frame(0x00EE, 0, 0, b""),
        bytes([0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x0F, 0xA1]),
    ]
    return b"".join(parts)


def iter_chunks(data: bytes, sizes: Iterable[int]) -> list[bytes]:
    """Split data by successive chunk sizes; remainder is one final chunk."""
    out: list[bytes] = []
    off = 0
    for size in sizes:
        if off >= len(data):
            break
        take = min(size, len(data) - off)
        out.append(data[off : off + take])
        off += take
    if off < len(data):
        out.append(data[off:])
    return out


class BclFramer:
    """Deterministic streaming BCL framer. No DEADBEEF/magic resync."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._error = False
        self._error_code = BclParseError.NONE

    def reset(self) -> None:
        self._buf.clear()
        self._error = False
        self._error_code = BclParseError.NONE

    def has_error(self) -> bool:
        return self._error

    def last_error(self) -> BclParseError:
        return self._error_code

    def buffered(self) -> int:
        return len(self._buf)

    def is_incomplete(self) -> bool:
        return (not self._error) and len(self._buf) > 0

    def feed(self, data: bytes | bytearray | memoryview | None) -> BclFeedResult:
        out = BclFeedResult()
        if self._error:
            out.error = True
            out.error_code = self._error_code
            out.error_detail = "framer_in_error_reset_required"
            return out

        if not data:
            out.incomplete = len(self._buf) > 0
            return out

        self._buf.extend(bytes(data))
        self._try_emit(out)
        if not out.error:
            out.incomplete = len(self._buf) > 0
        return out

    def _try_emit(self, out: BclFeedResult) -> None:
        while not self._error:
            if len(self._buf) < HEADER_SIZE:
                out.incomplete = len(self._buf) > 0
                return

            cmd = _read_be16(self._buf, 0)
            src = _read_be16(self._buf, 2)
            dest = _read_be16(self._buf, 4)
            length = _read_be16(self._buf, 6)

            if length > MAX_PAYLOAD:
                self._error = True
                self._error_code = BclParseError.PAYLOAD_TOO_LARGE
                out.error = True
                out.error_code = BclParseError.PAYLOAD_TOO_LARGE
                out.error_detail = "payload_len_exceeds_kMaxPayload"
                out.incomplete = False
                return

            need = HEADER_SIZE + length
            if len(self._buf) < need:
                out.incomplete = True
                return

            raw = bytes(self._buf[:need])
            frame = BclFrame(
                cmd=cmd,
                src=src,
                dest=dest,
                length=length,
                payload=raw[HEADER_SIZE:],
                raw=raw,
            )
            out.frames.append(frame)
            del self._buf[:need]


def feed_chunked(
    data: bytes, chunk_sizes: Iterable[int] = CA_C1_LAB_CHUNKS
) -> tuple[list[BclFrame], BclFeedResult]:
    """Feed data in chunks; return all frames + final feed result (error sticky)."""
    fr = BclFramer()
    frames: list[BclFrame] = []
    last = BclFeedResult()
    for chunk in iter_chunks(data, chunk_sizes):
        last = fr.feed(chunk)
        frames.extend(last.frames)
        if last.error:
            break
    return frames, last
