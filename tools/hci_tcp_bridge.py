#!/usr/bin/env python3
"""Attach an hci-agent ESP (raw H4 over TCP :9754) to Linux as a BlueZ hciN.

The kernel's /dev/vhci creates a virtual controller whose bytes we supply:
packets read from vhci go to the ESP, H4 packets from the ESP are written back.
Needs root and the hci_vhci module where bluetoothd runs (Proxmox host or a VM;
an unprivileged LXC has no AF_BLUETOOTH). TCP loss closes vhci, so the hciN
disappears and BlueZ cleans up; the bridge then reconnects and re-creates it.

Usage:
  sudo python3 tools/hci_tcp_bridge.py 192.168.178.131
  sudo python3 tools/hci_tcp_bridge.py 192.168.178.87 --port 9754 --once
  btmon -i hci1 -w /tmp/car.btsnoop      # capture in parallel
"""

from __future__ import annotations

import argparse
import os
import select
import socket
import sys
import time

H4_HEADER_LEN = {0x01: 3, 0x02: 4, 0x03: 3, 0x04: 2, 0x05: 4}
HOST_TO_CONTROLLER = (0x01, 0x02, 0x03, 0x05)
VHCI_PATH = "/dev/vhci"
VHCI_CREATE_PRIMARY = bytes([0xFF, 0x00])


def h4_payload_len(ptype: int, hdr: bytes) -> int:
    if ptype in (0x01, 0x03):
        return hdr[2]
    if ptype == 0x02:
        return hdr[2] | (hdr[3] << 8)
    if ptype == 0x04:
        return hdr[1]
    if ptype == 0x05:
        return (hdr[2] | (hdr[3] << 8)) & 0x3FFF
    raise ValueError(f"unknown H4 type 0x{ptype:02x}")


def split_h4(buf: bytearray) -> list[bytes]:
    """Remove and return all complete H4 packets from buf (rest stays)."""
    out: list[bytes] = []
    while buf:
        hlen = H4_HEADER_LEN.get(buf[0])
        if hlen is None:
            raise ValueError(f"unknown H4 type 0x{buf[0]:02x}")
        if len(buf) < 1 + hlen:
            break
        total = 1 + hlen + h4_payload_len(buf[0], bytes(buf[1 : 1 + hlen]))
        if len(buf) < total:
            break
        out.append(bytes(buf[:total]))
        del buf[:total]
    return out


def open_vhci() -> tuple[int, int]:
    """Create a primary (BR/EDR+LE) vhci controller; returns (fd, hci index)."""
    fd = os.open(VHCI_PATH, os.O_RDWR)
    try:
        os.write(fd, VHCI_CREATE_PRIMARY)
        ready, _, _ = select.select([fd], [], [], 2.0)
        if not ready:
            raise RuntimeError("vhci: no create response")
        resp = os.read(fd, 4)
        if len(resp) < 4 or resp[0] != 0xFF:
            raise RuntimeError(f"vhci: unexpected create response {resp.hex()}")
        return fd, resp[2] | (resp[3] << 8)
    except Exception:
        os.close(fd)
        raise


def connect_agent(host: str, port: int) -> socket.socket:
    sock = socket.create_connection((host, port), timeout=5)
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    for opt, val in (("TCP_KEEPIDLE", 5), ("TCP_KEEPINTVL", 2), ("TCP_KEEPCNT", 3)):
        if hasattr(socket, opt):
            sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, opt), val)
    return sock


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def run_session(host: str, port: int) -> None:
    sock = connect_agent(host, port)
    try:
        fd, index = open_vhci()
    except Exception:
        sock.close()
        raise
    log(f"hci{index} <-> {host}:{port}")
    stats = {"to_ctrl": 0, "to_host": 0}
    buf = bytearray()
    try:
        while True:
            ready, _, _ = select.select([sock, fd], [], [])
            if fd in ready:
                pkt = os.read(fd, 4096)
                if not pkt:
                    raise ConnectionError("vhci closed")
                if pkt[0] in HOST_TO_CONTROLLER:
                    sock.sendall(pkt)
                    stats["to_ctrl"] += 1
            if sock in ready:
                data = sock.recv(65536)
                if not data:
                    raise ConnectionError("agent closed the connection")
                buf += data
                for pkt in split_h4(buf):
                    os.write(fd, pkt)
                    stats["to_host"] += 1
    finally:
        os.close(fd)
        sock.close()
        log(f"hci{index} removed (to_ctrl={stats['to_ctrl']} to_host={stats['to_host']})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("host", help="hci-agent ESP IP, e.g. 192.168.178.131")
    ap.add_argument("--port", type=int, default=9754)
    ap.add_argument("--once", action="store_true", help="exit after the first session")
    args = ap.parse_args()

    if not os.path.exists(VHCI_PATH):
        print(f"{VHCI_PATH} missing — run: modprobe hci_vhci", file=sys.stderr)
        return 2

    backoff = 2
    while True:
        started = time.monotonic()
        try:
            run_session(args.host, args.port)
        except KeyboardInterrupt:
            return 0
        except (OSError, ConnectionError, RuntimeError, ValueError) as exc:
            log(f"session ended: {exc}")
        if args.once:
            return 1
        backoff = 2 if time.monotonic() - started > 30 else min(backoff * 2, 30)
        time.sleep(backoff)


if __name__ == "__main__":
    sys.exit(main())
