#!/usr/bin/env python3
"""Classic RFCOMM performance probe between two BlueZ adapters on .108.

Default DUT = CSR stick 00:1A:7D:DA:71:02 (server), peer = USB phone
C0:B8:83:34:F4:62 (client). Does not touch HU/iDriveSim SPP ch6.

Metrics: connect time, bulk TX/RX Bps both directions, ping RTT, RSSI/LQ.

Usage (on host with AF_BLUETOOTH):
  python3 tools/lab_usb_rfcomm_perf.py
  python3 tools/lab_usb_rfcomm_perf.py --duration 30 --payload 240
"""

from __future__ import annotations

import argparse
import json
import os
import select
import socket
import statistics
import struct
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSR_BD = "00:1A:7D:DA:71:02"
PEER_BD = "C0:B8:83:34:F4:62"
CHANNEL = 22
MAGIC = b"BTAPERF1"


def sh(*args: str, check: bool = False) -> str:
    r = subprocess.run(args, capture_output=True, text=True, check=check)
    return (r.stdout or "") + (r.stderr or "")


def hci_for_bd(bd: str) -> str | None:
    for i in range(0, 8):
        out = sh("hciconfig", f"hci{i}")
        if bd.upper() in out.upper():
            return f"hci{i}"
    return None


def link_stats(hci: str, peer: str) -> dict:
    rssi = sh("hcitool", "-i", hci, "rssi", peer).strip()
    lq = sh("hcitool", "-i", hci, "lq", peer).strip()
    tpl = sh("hcitool", "-i", hci, "tpl", peer).strip()
    con = sh("hcitool", "-i", hci, "con").strip()
    return {"rssi": rssi, "lq": lq, "tpl": tpl, "con": con}


def ensure_adapter(bd: str, alias: str) -> str:
    hci = hci_for_bd(bd)
    if not hci:
        raise RuntimeError(f"adapter {bd} not found")
    sh("hciconfig", hci, "up")
    sh("hciconfig", hci, "piscan")
    path = f"/org/bluez/{hci}"
    sh("busctl", "set-property", "org.bluez", path, "org.bluez.Adapter1", "Alias", "s", alias)
    sh("busctl", "set-property", "org.bluez", path, "org.bluez.Adapter1", "Powered", "b", "true")
    return hci


def bluez_connect(local_hci: str, peer_bd: str, timeout: float = 20.0) -> bool:
    """Best-effort ACL via bluetoothctl on selected controller."""
    local_bd = None
    for line in sh("hciconfig", local_hci).splitlines():
        if "BD Address" in line:
            local_bd = line.split()[2]
            break
    if local_bd:
        sh("bluetoothctl", "select", local_bd)
    sh("bluetoothctl", "power", "on")
    sh("bluetoothctl", "agent", "NoInputNoOutput")
    sh("bluetoothctl", "default-agent")
    sh("bluetoothctl", "pairable", "on")
    sh("bluetoothctl", "trust", peer_bd)
    # pair may already exist
    sh("timeout", "8", "bluetoothctl", "pair", peer_bd)
    t0 = time.time()
    sh("timeout", str(int(timeout)), "bluetoothctl", "connect", peer_bd)
    while time.time() - t0 < timeout:
        con = sh("hcitool", "-i", local_hci, "con")
        if peer_bd.upper() in con.upper():
            return True
        time.sleep(0.4)
    return peer_bd.upper() in sh("hcitool", "-i", local_hci, "con").upper()


def bind_rfcomm(bd: str, channel: int) -> socket.socket:
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bd, channel))
    s.listen(1)
    s.settimeout(30.0)
    return s


def connect_rfcomm(
    local_bd: str, peer_bd: str, channel: int, timeout: float = 20.0
) -> tuple[socket.socket, float]:
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    # bind to local adapter
    s.bind((local_bd, 0))
    s.settimeout(timeout)
    t0 = time.time()
    s.connect((peer_bd, channel))
    s.settimeout(5.0)
    return s, time.time() - t0


def recv_exact(sock: socket.socket, n: int, deadline: float) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        if time.time() > deadline:
            raise TimeoutError(f"recv_exact want={n} got={len(buf)}")
        r, _, _ = select.select([sock], [], [], max(0.0, deadline - time.time()))
        if not r:
            continue
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("eof")
        buf.extend(chunk)
    return bytes(buf)


def ping_rtt(sock: socket.socket, n: int = 20, payload: int = 32) -> dict:
    rtts: list[float] = []
    errors = 0
    for i in range(n):
        body = MAGIC + struct.pack("!I", i) + os.urandom(max(0, payload - 8))
        body = body[:payload]
        frame = struct.pack("!I", len(body)) + body
        t0 = time.perf_counter()
        sock.sendall(frame)
        try:
            hdr = recv_exact(sock, 4, time.time() + 3.0)
            (ln,) = struct.unpack("!I", hdr)
            data = recv_exact(sock, ln, time.time() + 3.0)
            if data[:8] != body[:8]:
                errors += 1
            rtts.append((time.perf_counter() - t0) * 1000.0)
        except Exception:  # noqa: BLE001
            errors += 1
    if not rtts:
        return {"n": n, "errors": errors, "rtt_ms": None}
    return {
        "n": n,
        "errors": errors,
        "rtt_ms": {
            "min": round(min(rtts), 2),
            "median": round(statistics.median(rtts), 2),
            "p90": round(sorted(rtts)[max(0, int(len(rtts) * 0.9) - 1)], 2),
            "max": round(max(rtts), 2),
            "mean": round(statistics.mean(rtts), 2),
        },
    }


def bulk_tx(sock: socket.socket, duration: float, payload: int, role: str) -> dict:
    """Send length-prefixed chunks for duration; peer must echo or sink."""
    sent = 0
    chunks = 0
    t0 = time.perf_counter()
    deadline = t0 + duration
    seq = 0
    while time.perf_counter() < deadline:
        body = MAGIC + struct.pack("!I", seq) + bytes((seq * 17 + i) % 256 for i in range(payload - 8))
        body = body[:payload]
        frame = struct.pack("!I", len(body)) + body
        try:
            sock.sendall(frame)
        except OSError as exc:
            return {
                "role": role,
                "ok": False,
                "error": repr(exc),
                "bytes": sent,
                "chunks": chunks,
                "duration_s": round(time.perf_counter() - t0, 3),
            }
        sent += len(frame)
        chunks += 1
        seq += 1
    dt = time.perf_counter() - t0
    return {
        "role": role,
        "ok": True,
        "bytes": sent,
        "chunks": chunks,
        "duration_s": round(dt, 3),
        "Bps": round(sent / dt, 1) if dt > 0 else 0.0,
        "kBps": round(sent / dt / 1024.0, 2) if dt > 0 else 0.0,
    }


def echo_server_loop(conn: socket.socket, stop: threading.Event, stats: dict) -> None:
    conn.settimeout(1.0)
    rx = 0
    while not stop.is_set():
        try:
            hdr = recv_exact(conn, 4, time.time() + 1.0)
        except TimeoutError:
            continue
        except Exception as exc:  # noqa: BLE001
            stats["error"] = repr(exc)
            break
        (ln,) = struct.unpack("!I", hdr)
        if ln > 1_000_000:
            stats["error"] = f"bad_len={ln}"
            break
        try:
            data = recv_exact(conn, ln, time.time() + 5.0)
            conn.sendall(struct.pack("!I", len(data)) + data)
            rx += 4 + ln
        except Exception as exc:  # noqa: BLE001
            stats["error"] = repr(exc)
            break
    stats["rx_bytes"] = rx


def sink_server_loop(conn: socket.socket, stop: threading.Event, stats: dict) -> None:
    conn.settimeout(1.0)
    rx = 0
    t0 = time.perf_counter()
    while not stop.is_set():
        try:
            hdr = recv_exact(conn, 4, time.time() + 1.0)
        except TimeoutError:
            continue
        except Exception as exc:  # noqa: BLE001
            stats["error"] = repr(exc)
            break
        (ln,) = struct.unpack("!I", hdr)
        try:
            _ = recv_exact(conn, ln, time.time() + 5.0)
            rx += 4 + ln
        except Exception as exc:  # noqa: BLE001
            stats["error"] = repr(exc)
            break
    dt = max(1e-6, time.perf_counter() - t0)
    stats["rx_bytes"] = rx
    stats["rx_kBps"] = round(rx / dt / 1024.0, 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dut", default=CSR_BD, help="DUT BD (CSR stick)")
    ap.add_argument("--peer", default=PEER_BD, help="peer BD (USB phone dongle)")
    ap.add_argument("--channel", type=int, default=CHANNEL)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--payload", type=int, default=240, help="RFCOMM chunk payload bytes")
    ap.add_argument("--pings", type=int, default=25)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    out = args.out or (ROOT / "docs" / "evidence" / f"LAB_CSR_RFCOMM_PERF_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    dut_hci = ensure_adapter(args.dut, "BT-Analyzer-CSR")
    peer_hci = ensure_adapter(args.peer, "BT-Analyzer-Phone")

    report: dict = {
        "claim_level": "LAB FACT",
        "stamp": stamp,
        "dut": {"bd": args.dut, "hci": dut_hci},
        "peer": {"bd": args.peer, "hci": peer_hci},
        "channel": args.channel,
        "duration_s": args.duration,
        "payload": args.payload,
        "dut_hciconfig": sh("hciconfig", dut_hci),
    }

    # Best-effort ACL; RFCOMM connect will page if needed.
    report["acl_connect_ok"] = bluez_connect(peer_hci, args.dut, timeout=12.0)
    report["link_pre"] = link_stats(peer_hci, args.dut)
    # Also try reverse trust so DUT accepts
    sh("bluetoothctl", "select", args.dut)
    sh("bluetoothctl", "trust", args.peer)
    sh("timeout", "5", "bluetoothctl", "pair", args.peer)

    server = bind_rfcomm(args.dut, args.channel)
    report["server_listen"] = {"bd": args.dut, "channel": args.channel}

    client_holder: dict = {}
    err_holder: dict = {}

    def client_thread() -> None:
        time.sleep(0.5)
        try:
            c, conn_s = connect_rfcomm(args.peer, args.dut, args.channel, timeout=25.0)
            client_holder["sock"] = c
            client_holder["connect_s"] = conn_s
        except Exception as exc:  # noqa: BLE001
            err_holder["client"] = repr(exc)

    th = threading.Thread(target=client_thread, daemon=True)
    th.start()
    try:
        conn, addr = server.accept()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"accept_failed: {exc!r}"
        report["client_error"] = err_holder.get("client")
        (out / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
        (out / "SUMMARY.md").write_text(f"# CSR RFCOMM perf FAIL\n\n`{report.get('error')}`\n")
        print(json.dumps(report, indent=2))
        return 2
    th.join(timeout=5.0)
    client = client_holder.get("sock")
    if client is None:
        report["error"] = "client_connect_failed"
        report["client_error"] = err_holder.get("client")
        conn.close()
        server.close()
        (out / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2

    report["rfcomm_accept_addr"] = str(addr)
    report["rfcomm_connect_s"] = client_holder.get("connect_s")
    report["link_connected"] = link_stats(peer_hci, args.dut)

    # Phase 1: echo RTT (server echoes)
    stop = threading.Event()
    echo_stats: dict = {}
    echo_th = threading.Thread(target=echo_server_loop, args=(conn, stop, echo_stats), daemon=True)
    echo_th.start()
    time.sleep(0.2)
    report["ping"] = ping_rtt(client, n=args.pings, payload=min(64, args.payload))
    stop.set()
    echo_th.join(timeout=3.0)
    report["echo_server"] = echo_stats

    # Phase 2: bulk DUT←peer (client TX, server sink) — traffic onto CSR RX
    stop2 = threading.Event()
    sink_stats: dict = {}
    sink_th = threading.Thread(target=sink_server_loop, args=(conn, stop2, sink_stats), daemon=True)
    sink_th.start()
    time.sleep(0.1)
    report["bulk_peer_to_dut"] = bulk_tx(client, args.duration, args.payload, "peer_tx")
    time.sleep(0.3)
    stop2.set()
    sink_th.join(timeout=3.0)
    report["bulk_peer_to_dut"]["server_rx"] = sink_stats

    # Phase 3: bulk DUT→peer (server TX, client sink)
    # Swap roles on same sockets: client sinks, we TX from conn (DUT)
    stop3 = threading.Event()
    sink2: dict = {}
    sink_th2 = threading.Thread(target=sink_server_loop, args=(client, stop3, sink2), daemon=True)
    sink_th2.start()
    time.sleep(0.1)
    report["bulk_dut_to_peer"] = bulk_tx(conn, args.duration, args.payload, "dut_tx")
    time.sleep(0.3)
    stop3.set()
    sink_th2.join(timeout=3.0)
    report["bulk_dut_to_peer"]["peer_rx"] = sink2

    report["link_post"] = link_stats(peer_hci, args.dut)
    report["hci_post"] = {
        "dut": sh("hciconfig", dut_hci),
        "peer": sh("hciconfig", peer_hci),
    }

    # Verdict
    ping_ok = bool(report["ping"].get("rtt_ms")) and report["ping"].get("errors", 99) == 0
    b1 = report["bulk_peer_to_dut"]
    b2 = report["bulk_dut_to_peer"]
    bulk_ok = bool(b1.get("ok") and b2.get("ok") and b1.get("kBps", 0) > 0 and b2.get("kBps", 0) > 0)
    # RFCOMM success implies usable ACL even if bluetoothctl connect flaked.
    report["verdict"] = "PASS" if (ping_ok and bulk_ok) else "FAIL"

    (out / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    md = [
        f"# LAB CSR RFCOMM perf — {stamp}",
        "",
        f"**claim_level:** LAB FACT  ",
        f"**verdict:** {report['verdict']}  ",
        f"**DUT:** `{args.dut}` ({dut_hci}, CSR8510)  ",
        f"**Peer:** `{args.peer}` ({peer_hci})  ",
        f"**RFCOMM ch:** {args.channel} · payload {args.payload} B · duration {args.duration}s/dir",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| ACL connect | {report['acl_connect_ok']} |",
        f"| RFCOMM connect_s | {report.get('rfcomm_connect_s')} |",
        f"| Ping median / p90 / max ms | {((report['ping'].get('rtt_ms') or {}).get('median'))} / "
        f"{((report['ping'].get('rtt_ms') or {}).get('p90'))} / "
        f"{((report['ping'].get('rtt_ms') or {}).get('max'))} |",
        f"| Ping errors | {report['ping'].get('errors')} |",
        f"| Peer→DUT kB/s | {b1.get('kBps')} (bytes={b1.get('bytes')}) |",
        f"| DUT→Peer kB/s | {b2.get('kBps')} (bytes={b2.get('bytes')}) |",
        f"| Link | `{report['link_post'].get('rssi')}` / `{report['link_post'].get('lq')}` |",
        "",
        f"Artifact: `{out}/REPORT.json`",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(md))
    print("\n".join(md))
    print("REPORT", out / "REPORT.json")

    try:
        client.close()
        conn.close()
        server.close()
    except Exception:  # noqa: BLE001
        pass
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
