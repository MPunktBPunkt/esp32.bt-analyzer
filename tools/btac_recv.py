#!/usr/bin/env python3
"""Receive BTAC v1 HCI capture stream from a bt-analyzer node (Gate BT4).

Usage:
  python3 tools/btac_recv.py 192.168.178.88
  python3 tools/btac_recv.py 192.168.178.87 -o /tmp/cap.btac --jsonl /tmp/cap.jsonl -n 64
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import btac  # noqa: E402


def read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf.extend(chunk)
    return bytes(buf)


def recv_frame(sock: socket.socket) -> dict:
    hdr = read_exact(sock, btac.HDR_SIZE)
    # length from header without full validate yet
    import struct
    import zlib

    magic, ver, _flags, _sid, seq, _ts, _d, _t, _e, _r, length = struct.unpack(btac.HDR_FMT, hdr)
    if magic != btac.MAGIC:
        raise ValueError(f"bad magic {magic!r}")
    if ver != 1:
        raise ValueError(f"unsupported version {ver}")
    if length > 1024:
        raise ValueError(f"length {length} exceeds max")
    payload = read_exact(sock, length) if length else b""
    crc_raw = read_exact(sock, 4)
    crc_wire = struct.unpack("<I", crc_raw)[0]
    crc_calc = zlib.crc32(hdr + payload) & 0xFFFFFFFF
    if crc_calc != crc_wire:
        raise ValueError(f"crc mismatch seq={seq} wire={crc_wire:08x} calc={crc_calc:08x}")
    fr = btac.frame_to_dict(hdr, payload, crc_ok=True)
    fr["_raw"] = hdr + payload + crc_raw
    return fr


def main() -> int:
    ap = argparse.ArgumentParser(description="BTAC v1 receiver (bt-analyzer BT4)")
    ap.add_argument("host", help="ESP node IP")
    ap.add_argument("-p", "--port", type=int, default=9753)
    ap.add_argument("-o", "--output", type=Path, help="write raw BTAC frames")
    ap.add_argument("--jsonl", type=Path, help="write decoded JSONL")
    ap.add_argument("-n", "--max-frames", type=int, default=0, help="0 = until Ctrl-C")
    ap.add_argument("-t", "--timeout", type=float, default=30.0, help="connect timeout s")
    ap.add_argument("--idle", type=float, default=0.0, help="exit after N s without frames")
    args = ap.parse_args()

    sock = socket.create_connection((args.host, args.port), timeout=args.timeout)
    sock.settimeout(2.0)
    print(f"[btac] connected {args.host}:{args.port}", flush=True)

    out_f = args.output.open("wb") if args.output else None
    jsonl_f = args.jsonl.open("w", encoding="utf-8") if args.jsonl else None

    frames = 0
    bytes_in = 0
    gaps = 0
    last_seq = None
    last_frame_at = time.time()
    t0 = time.time()

    try:
        while True:
            if args.max_frames and frames >= args.max_frames:
                break
            try:
                fr = recv_frame(sock)
            except socket.timeout:
                if args.idle and (time.time() - last_frame_at) >= args.idle:
                    print("[btac] idle timeout", flush=True)
                    break
                continue
            except (EOFError, OSError) as exc:
                print(f"[btac] disconnect: {exc}", flush=True)
                break

            last_frame_at = time.time()
            if last_seq is not None and fr["seq"] > last_seq + 1:
                gaps += fr["seq"] - last_seq - 1
            last_seq = fr["seq"]
            frames += 1
            raw = fr.pop("_raw")
            bytes_in += len(raw)
            if out_f:
                out_f.write(raw)
            if jsonl_f:
                jsonl_f.write(json.dumps(fr, ensure_ascii=False) + "\n")
            if frames <= 5 or frames % 50 == 0:
                print(
                    f"[btac] #{frames} stream={fr['stream_id']} seq={fr['seq']} "
                    f"{fr['dir']} {fr['type']} len={fr['length']}",
                    flush=True,
                )
    finally:
        sock.close()
        if out_f:
            out_f.close()
        if jsonl_f:
            jsonl_f.close()

    dt = max(time.time() - t0, 1e-6)
    print(
        json.dumps(
            {
                "ok": True,
                "host": args.host,
                "port": args.port,
                "frames": frames,
                "bytes": bytes_in,
                "gaps": gaps,
                "duration_s": round(dt, 3),
                "fps": round(frames / dt, 1),
                "output": str(args.output) if args.output else None,
                "jsonl": str(args.jsonl) if args.jsonl else None,
            },
            indent=2,
        )
    )
    return 0 if frames > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
