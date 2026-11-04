#!/usr/bin/env python3
"""BT8 — BTAC / JSONL → PCAPNG (LINKTYPE_BLUETOOTH_HCI_H4=201).

Label: HCI capture, NOT RF/Air.

Usage:
  python3 tools/btac_to_pcapng.py capture.btac -o capture.pcapng
  python3 tools/btac_to_pcapng.py capture.jsonl -o capture.pcapng
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import btac  # noqa: E402

LINKTYPE_BLUETOOTH_HCI_H4 = 201


def _block(block_type: int, body: bytes) -> bytes:
    # padded to 32-bit
    pad = (4 - (len(body) % 4)) % 4
    total = 12 + len(body) + pad  # type + length + body + pad + length
    return (
        struct.pack("<II", block_type, total)
        + body
        + (b"\x00" * pad)
        + struct.pack("<I", total)
    )


def write_pcapng(path: Path, packets: list[tuple[int, bytes]]) -> None:
    """packets: list of (ts_us, h4_bytes)."""
    # Section Header Block
    shb_body = struct.pack("<IHHi", 0x1A2B3C4D, 1, 0, -1)  # bom, major, minor, section_len
    # Interface Description Block
    idb_body = struct.pack("<HHI", LINKTYPE_BLUETOOTH_HCI_H4, 0, 0)  # linktype, reserved, snaplen=0
    # optional if_name option: code=2, len, value
    name = b"bt-analyzer-hci"
    idb_body += struct.pack("<HH", 2, len(name)) + name + (b"\x00" * ((4 - len(name) % 4) % 4))
    idb_body += struct.pack("<HH", 0, 0)  # end of options

    with path.open("wb") as f:
        f.write(_block(0x0A0D0D0A, shb_body))
        f.write(_block(1, idb_body))
        for ts_us, payload in packets:
            ts_high = (ts_us >> 32) & 0xFFFFFFFF
            ts_low = ts_us & 0xFFFFFFFF
            epb = struct.pack("<III", 0, ts_high, ts_low)  # if_id, ts_high, ts_low
            epb += struct.pack("<II", len(payload), len(payload))
            epb += payload
            f.write(_block(6, epb))


def frames_from_btac(path: Path) -> list[dict]:
    return list(btac.iter_file(str(path)))


def frames_from_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def to_h4(fr: dict) -> bytes:
    hx = fr.get("payload_hex") or ""
    raw = bytes.fromhex(hx)
    if not raw:
        return b""
    # Already H4 if starts with 01..05
    if raw[0] in (1, 2, 3, 4, 5):
        return raw
    # Synthesize from type field
    t = fr.get("type")
    mapping = {"command": 1, "acl": 2, "sco": 3, "event": 4, "iso": 5}
    prefix = mapping.get(str(t), 4)
    return bytes([prefix]) + raw


def main() -> int:
    ap = argparse.ArgumentParser(description="BTAC/JSONL → PCAPNG HCI (BT8)")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()
    if not args.input.is_file():
        print(f"missing {args.input}", file=sys.stderr)
        return 2
    if args.input.suffix.lower() == ".jsonl":
        frames = frames_from_jsonl(args.input)
    else:
        frames = frames_from_btac(args.input)
    pkts: list[tuple[int, bytes]] = []
    for fr in frames:
        h4 = to_h4(fr)
        if not h4:
            continue
        ts = int(fr.get("ts_us") or 0)
        pkts.append((ts, h4))
    write_pcapng(args.output, pkts)
    print(
        json.dumps(
            {
                "ok": True,
                "input": str(args.input),
                "output": str(args.output),
                "packets": len(pkts),
                "linktype": LINKTYPE_BLUETOOTH_HCI_H4,
                "claim": "HCI_H4_not_RF",
            },
            indent=2,
        )
    )
    return 0 if pkts else 1


if __name__ == "__main__":
    sys.exit(main())
