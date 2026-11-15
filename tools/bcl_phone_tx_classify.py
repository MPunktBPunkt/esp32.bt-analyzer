#!/usr/bin/env python3
"""Classify Phone→HU BCL frames for adaptive Dummy probing (LAB only).

Does not claim SAS/RHMI wire FACT — heuristic tags for jsonl correlation.
"""

from __future__ import annotations

from bcl_etch_stub import ETCH_MAGIC, KNOCK_UUID_SERIAL, looks_like_knock_envelope
from bcl_framer import DEST_ETCH_DESK, DEST_WATCHDOG_DESK, cmd_desk_name

CMD_OPEN = 1
CMD_DATA = 2
CMD_CLOSE = 3
CMD_SELECTPROTO = 5
CMD_DATAACK = 6
CMD_KNOCK = 8


def _ascii_frags(b: bytes, min_len: int = 4) -> list[str]:
    out: list[str] = []
    cur = bytearray()
    for x in b:
        if 32 <= x < 127:
            cur.append(x)
        else:
            if len(cur) >= min_len:
                out.append(cur.decode("ascii"))
            cur.clear()
    if len(cur) >= min_len:
        out.append(cur.decode("ascii"))
    return out[:12]


def classify_phone_frame(cmd: int, src: int, dest: int, payload: bytes) -> dict:
    """Return epistemic tags for one Phone→HU frame."""
    tags: list[str] = []
    name = cmd_desk_name(cmd)
    if cmd == CMD_SELECTPROTO:
        tags.append("SP")
    elif cmd == CMD_KNOCK:
        tags.append("KNOCK")
    elif cmd == CMD_OPEN:
        if dest == DEST_ETCH_DESK:
            tags.append("OPEN_ETCH")
        elif dest == DEST_WATCHDOG_DESK:
            tags.append("OPEN_WD")
        else:
            tags.append("OPEN")
    elif cmd == CMD_CLOSE:
        tags.append("CLOSE")
    elif cmd == CMD_DATAACK:
        tags.append("DATAACK")
    elif cmd == CMD_DATA:
        if dest == DEST_WATCHDOG_DESK:
            tags.append("WD_PING")
        elif dest == DEST_ETCH_DESK:
            tags.append("ETCH_DATA")
            if payload.startswith(ETCH_MAGIC):
                tags.append("DEADBEEF")
            if b"-----BEGIN" in payload and b"PKCS7" in payload:
                tags.append("SAS_CERT_CANDIDATE")
            if b"sas_" in payload.lower() or b"SAS" in payload:
                tags.append("SAS_ASCII")
            if b"rhmi" in payload.lower() or b"RHMI" in payload:
                tags.append("RHMI_ASCII")
            if any(
                x in payload
                for x in (
                    b"sensors.",
                    b"driving.",
                    b"vehicle.",
                    b"_ENT_",
                    b"iva_MYV",
                )
            ):
                tags.append("CDS_ASCII")
        if looks_like_knock_envelope(payload):
            tags.append("KNOCK_ENVELOPE")
        if KNOCK_UUID_SERIAL in payload:
            tags.append("KNOCK_UUID")
    if not tags:
        tags.append(name)

    return {
        "event": "phone_tx_classified",
        "cmd": cmd,
        "cmd_name": name,
        "src": src,
        "dest": dest,
        "len": len(payload),
        "tags": tags,
        "ascii": _ascii_frags(payload),
        "payload_hex": payload[:64].hex(),
    }
