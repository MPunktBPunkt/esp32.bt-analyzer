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


# Drain queued VHCI packets into one TCP write (no timed delay — a 2 ms wait
# per lone HCI frame capped A2DP-class flows). Larger socket buffers help the
# ESP's still-small LwIP window until the agent firmware bump is flashed.
SOCK_BUF = 256 * 1024


def connect_agent(host: str, port: int) -> socket.socket:
    sock = socket.create_connection((host, port), timeout=5)
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCK_BUF)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCK_BUF)
    for opt, val in (("TCP_KEEPIDLE", 5), ("TCP_KEEPINTVL", 2), ("TCP_KEEPCNT", 3)):
        if hasattr(socket, opt):
            sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, opt), val)
    return sock


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# HCI Write Local Name (OGF 0x03 / OCF 0x0013) · Read Local Name OCF 0x0014.
_HCI_OP_WRITE_LOCAL_NAME = 0x0C13
_HCI_OP_READ_LOCAL_NAME = 0x0C14


def _padded_local_name(name: str, size: int = 248) -> bytes:
    raw = name.encode("utf-8", errors="replace")[: size - 1]
    return raw + b"\x00" * (size - len(raw))


def rewrite_hci_local_name(pkt: bytes, pinned: str) -> bytes:
    """Force a fixed local name on Write Local Name and Read Local Name complete.

    Lab ESPs default to names like ``BT-Analyzer-.87`` after panic/reinit; BlueZ
    then mirrors that into Adapter.Alias and the phone stops treating the peer
    as a BMW. Pinning on the bridge keeps the air name stable without relying
    on userspace pin races.
    """
    if not pinned or len(pkt) < 4:
        return pkt
    # Host → controller command
    if pkt[0] == 0x01 and len(pkt) >= 4:
        opcode = pkt[1] | (pkt[2] << 8)
        if opcode == _HCI_OP_WRITE_LOCAL_NAME:
            body = _padded_local_name(pinned, 248)
            return bytes([0x01, 0x13, 0x0C, 248]) + body
        return pkt
    # Controller → host event: Command Complete (0x0e) for Read Local Name
    if pkt[0] == 0x04 and len(pkt) >= 7 and pkt[1] == 0x0E:
        # H4 evt, evtcode, plen, ncmd(1), opcode(2), status(1), name...
        opcode = pkt[4] | (pkt[5] << 8)
        if opcode == _HCI_OP_READ_LOCAL_NAME and len(pkt) >= 7:
            plen = pkt[2]
            # Keep ncmd + opcode + status, replace name tail with pad to plen-4
            if plen >= 4:
                status = pkt[6] if len(pkt) > 6 else 0
                name_len = plen - 4
                name = _padded_local_name(pinned, name_len) if name_len > 0 else b""
                return bytes([0x04, 0x0E, plen, pkt[3], 0x14, 0x0C, status]) + name
    return pkt


def apply_agent_coex(host: str, mode: str = "prefer_bt") -> None:
    """Best-effort HTTP POST /api/hci/coex so even 0.3.19 nodes prioritize BT."""
    if not mode or mode == "keep":
        return
    import urllib.request

    try:
        req = urllib.request.Request(
            f"http://{host}/api/hci/coex",
            data=f"mode={mode}".encode("ascii"),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.0):
            log(f"set {host} coex={mode}")
    except Exception as exc:  # noqa: BLE001
        log(f"coex={mode} skipped on {host}: {exc}")


def run_session(
    host: str, port: int, coex: str = "prefer_bt", local_name: str | None = None
) -> None:
    apply_agent_coex(host, coex)
    sock = connect_agent(host, port)
    try:
        fd, index = open_vhci()
    except Exception:
        sock.close()
        raise
    pin = (local_name or "").strip()
    log(f"hci{index} <-> {host}:{port}" + (f" pin_name={pin!r}" if pin else ""))
    stats = {"to_ctrl": 0, "to_host": 0, "name_pin": 0}
    buf = bytearray()
    host_buf = bytearray()
    try:
        while True:
            ready, _, _ = select.select([sock, fd], [], [])
            if fd in ready:
                out = bytearray()
                pkt = os.read(fd, 4096)
                if not pkt:
                    raise ConnectionError("vhci closed")
                host_buf += pkt
                # Drain anything already queued without waiting.
                os.set_blocking(fd, False)
                try:
                    while True:
                        try:
                            pkt = os.read(fd, 4096)
                        except BlockingIOError:
                            break
                        if not pkt:
                            raise ConnectionError("vhci closed")
                        host_buf += pkt
                finally:
                    os.set_blocking(fd, True)
                for pkt in split_h4(host_buf):
                    if pkt[0] not in HOST_TO_CONTROLLER:
                        continue
                    if pin:
                        new = rewrite_hci_local_name(pkt, pin)
                        if new != pkt:
                            stats["name_pin"] += 1
                        pkt = new
                    out += pkt
                    stats["to_ctrl"] += 1
                if out:
                    sock.sendall(out)
            if sock in ready:
                data = sock.recv(65536)
                if not data:
                    raise ConnectionError("agent closed the connection")
                buf += data
                for pkt in split_h4(buf):
                    if pin:
                        new = rewrite_hci_local_name(pkt, pin)
                        if new != pkt:
                            stats["name_pin"] += 1
                        pkt = new
                    os.write(fd, pkt)
                    stats["to_host"] += 1
    finally:
        os.close(fd)
        sock.close()
        log(
            f"hci{index} removed (to_ctrl={stats['to_ctrl']} "
            f"to_host={stats['to_host']} name_pin={stats['name_pin']})"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("host", help="hci-agent ESP IP, e.g. 192.168.178.131")
    ap.add_argument("--port", type=int, default=9754)
    ap.add_argument("--once", action="store_true", help="exit after the first session")
    ap.add_argument(
        "--coex",
        default="prefer_bt",
        choices=("prefer_bt", "a2dp", "default", "keep"),
        help="ESP BT/WiFi coex policy to apply on connect (default: prefer_bt)",
    )
    ap.add_argument(
        "--local-name",
        default=os.environ.get("HCI_PIN_LOCAL_NAME", ""),
        help="pin HCI local name (e.g. 'BMW 38304'); also HCI_PIN_LOCAL_NAME env",
    )
    args = ap.parse_args()

    if not os.path.exists(VHCI_PATH):
        print(f"{VHCI_PATH} missing — run: modprobe hci_vhci", file=sys.stderr)
        return 2

    backoff = 2
    while True:
        started = time.monotonic()
        try:
            run_session(args.host, args.port, args.coex, args.local_name or None)
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
