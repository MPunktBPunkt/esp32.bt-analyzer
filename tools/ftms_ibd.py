#!/usr/bin/env python3
"""FTMS Indoor Bike Data (0x2AD2) decoder — shared offline/live helper (0.3.15 lite).

Flag rules aligned with esp32.ergo / FW FtmsFlavor::decodeIbd_.
Cadence unit is 1/2 rpm (divide by 2 for display rpm).
"""

from __future__ import annotations


def decode_ibd(payload: bytes | bytearray) -> dict | None:
    if not payload or len(payload) < 2:
        return None
    flags = payload[0] | (payload[1] << 8)
    off = 2
    out: dict = {"flags": flags, "flags_hex": f"0x{flags:04X}"}

    def need(n: int) -> bool:
        return off + n <= len(payload)

    if (flags & 0x0001) == 0:
        if not need(2):
            return out
        speed_raw = payload[off] | (payload[off + 1] << 8)
        out["speed_kmh"] = speed_raw / 100.0
        off += 2
    if flags & 0x0002:
        if not need(2):
            return out
        out["avg_speed_kmh"] = (payload[off] | (payload[off + 1] << 8)) / 100.0
        off += 2
    if flags & 0x0004:
        if not need(2):
            return out
        cad_raw = payload[off] | (payload[off + 1] << 8)
        out["cadence_raw"] = cad_raw
        out["cadence_rpm"] = cad_raw / 2.0
        off += 2
    if flags & 0x0008:
        if not need(2):
            return out
        out["avg_cadence_rpm"] = (payload[off] | (payload[off + 1] << 8)) / 2.0
        off += 2
    if flags & 0x0010:
        if not need(3):
            return out
        out["total_distance_m"] = payload[off] | (payload[off + 1] << 8) | (payload[off + 2] << 16)
        off += 3
    if flags & 0x0020:
        if not need(2):
            return out
        out["resistance"] = payload[off] | (payload[off + 1] << 8)
        off += 2
    if flags & 0x0040:
        if not need(2):
            return out
        out["power_w"] = payload[off] | (payload[off + 1] << 8)
        off += 2
    return out


def decode_ibd_hex(hex_str: str) -> dict | None:
    h = (hex_str or "").replace(" ", "").replace(":", "")
    if not h:
        return None
    return decode_ibd(bytes.fromhex(h))


if __name__ == "__main__":
    import json
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "540b0000ae002600"  # flags+speed+cad+power-ish
    print(json.dumps(decode_ibd_hex(sample), indent=2))
