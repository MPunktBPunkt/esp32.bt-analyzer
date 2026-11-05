"""BTAC v1 framing helpers (shared by recv / decode — Gate BT4/BT7)."""

from __future__ import annotations

import struct
import zlib
from typing import BinaryIO, Iterator

MAGIC = b"BTAC"
HDR_FMT = "<4sBBHIQBBBBH"
HDR_SIZE = struct.calcsize(HDR_FMT)
assert HDR_SIZE == 26

DIR_NAME = {0: "unknown", 1: "host_to_controller", 2: "controller_to_host"}
TYPE_NAME = {
    0: "unknown",
    1: "command",
    2: "event",
    3: "acl",
    4: "sco",
    5: "iso",
    0xFE: "meta",  # session START/STOP/MARK (not on-air HCI)
}


def frame_to_dict(
    hdr: bytes,
    payload: bytes,
    *,
    crc_ok: bool,
    include_raw: bool = False,
) -> dict:
    magic, ver, flags, stream_id, seq, ts_us, direction, ptype, endpoint, _res, length = (
        struct.unpack(HDR_FMT, hdr)
    )
    out = {
        "version": ver,
        "flags": flags,
        "stream_id": stream_id,
        "seq": seq,
        "ts_us": ts_us,
        "dir": DIR_NAME.get(direction, str(direction)),
        "type": TYPE_NAME.get(ptype, str(ptype)),
        "endpoint": endpoint,
        "length": length,
        "payload_hex": payload.hex(),
        "crc_ok": crc_ok,
        "transport": "onchip_vhci",
    }
    if include_raw:
        out["_raw"] = hdr + payload + b""  # caller may append crc
    return out


def parse_frame_bytes(blob: bytes) -> tuple[dict, int]:
    """Parse one BTAC frame from blob start. Returns (dict, bytes_consumed)."""
    if len(blob) < HDR_SIZE + 4:
        raise ValueError("short buffer")
    hdr = blob[:HDR_SIZE]
    magic, ver, flags, stream_id, seq, ts_us, direction, ptype, endpoint, _res, length = (
        struct.unpack(HDR_FMT, hdr)
    )
    if magic != MAGIC:
        raise ValueError(f"bad magic {magic!r}")
    if ver != 1:
        raise ValueError(f"unsupported version {ver}")
    if length > 1024:
        raise ValueError(f"length {length} exceeds max")
    need = HDR_SIZE + length + 4
    if len(blob) < need:
        raise ValueError("incomplete frame")
    payload = blob[HDR_SIZE : HDR_SIZE + length]
    crc_wire = struct.unpack("<I", blob[HDR_SIZE + length : need])[0]
    crc_calc = zlib.crc32(hdr + payload) & 0xFFFFFFFF
    fr = frame_to_dict(hdr, payload, crc_ok=(crc_calc == crc_wire))
    if crc_calc != crc_wire:
        fr["crc_wire"] = f"{crc_wire:08x}"
        fr["crc_calc"] = f"{crc_calc:08x}"
    return fr, need


def iter_file(path_or_file: BinaryIO | str) -> Iterator[dict]:
    if isinstance(path_or_file, str):
        with open(path_or_file, "rb") as f:
            yield from iter_file(f)
        return
    buf = bytearray()
    while True:
        chunk = path_or_file.read(4096)
        if chunk:
            buf.extend(chunk)
        while True:
            try:
                fr, n = parse_frame_bytes(bytes(buf))
            except ValueError as exc:
                msg = str(exc)
                if msg in ("short buffer", "incomplete frame") and chunk:
                    break
                if msg in ("short buffer", "incomplete frame") and not chunk:
                    return
                # resync on bad magic: skip 1 byte
                if "bad magic" in msg and len(buf) > 0:
                    del buf[0]
                    continue
                raise
            del buf[:n]
            yield fr
        if not chunk:
            return


def summarize(frames: list[dict]) -> dict:
    """Summarize frames.

    ``gaps`` = forward seq holes within a contiguous run only.
    Seq decreases / stream_id changes count as ``resync`` (corrupt/partial
    frame or session boundary) — not as application capture loss.
    """
    gaps = 0
    resync = 0
    crc_fail = 0
    last = None
    last_stream = None
    by_type: dict[str, int] = {}
    for fr in frames:
        if not fr.get("crc_ok", True):
            crc_fail += 1
        t = str(fr.get("type"))
        by_type[t] = by_type.get(t, 0) + 1
        seq = fr.get("seq")
        sid = fr.get("stream_id")
        if not isinstance(seq, int):
            continue
        if last is not None:
            if isinstance(sid, int) and isinstance(last_stream, int) and sid != last_stream:
                resync += 1
                last = seq
                last_stream = sid
                continue
            if seq < last:
                # Likely partial-frame desync inventing seq=0 — ignore phantom.
                resync += 1
                continue
            if seq > last + 1:
                gaps += seq - last - 1
        last = seq
        if isinstance(sid, int):
            last_stream = sid
    return {
        "frames": len(frames),
        "gaps": gaps,
        "resync": resync,
        "crc_fail": crc_fail,
        "by_type": by_type,
        "seq_first": frames[0]["seq"] if frames else None,
        "seq_last": frames[-1]["seq"] if frames else None,
    }
