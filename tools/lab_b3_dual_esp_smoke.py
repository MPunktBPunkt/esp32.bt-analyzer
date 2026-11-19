#!/usr/bin/env python3
"""Lab smoke: USB/phone → .131 (B3 listen) → air RFCOMM → .87 raw f20_sim HU.

Evening topology stand-in (car replaced by f20_sim on .87):
  Phone  →  .131 BMW  →  B3 relay  →  .87  →  DummyHuSession(f20_sim)

BlueZ Profile ch6 is host-global, so the HU side uses a raw RFCOMM bind on .87
instead of ProfileManager — frees ch6 on .131 for B3 listen.

Usage (on .108, tools in /tmp/bcl_dummy or PYTHONPATH=tools):
  python3 lab_b3_dual_esp_smoke.py --out /tmp/bcl_dummy/B3_LAB_...
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, "/tmp/bcl_dummy")

from bcl_dummy_hu import DummyHuSession, apply_hu_profile  # noqa: E402
from bcl_framer import BclFramer  # noqa: E402

BMW131 = "C8:C9:A3:CB:7B:0A"
HU87 = "C8:C9:A3:CB:37:96"
USB = "C0:B8:83:34:F4:62"


def sh(cmd: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)


def busctl_set(path: str, prop: str, typ: str, val: str) -> None:
    sh(["busctl", "set-property", "org.bluez", path, "org.bluez.Adapter1", prop, typ, val])


def prep_adapters() -> None:
    # hci2=.131 BMW, hci1=.87, hci0=USB; CSR off
    for path, alias, powered in (
        ("/org/bluez/hci2", "BMW 38304", "true"),
        ("/org/bluez/hci1", "BT-Analyzer-Phone", "true"),
        ("/org/bluez/hci0", "BT-Analyzer-PhoneUSB", "true"),
    ):
        busctl_set(path, "Powered", "b", powered)
        busctl_set(path, "Alias", "s", alias)
        busctl_set(path, "Discoverable", "b", "true")
        busctl_set(path, "Pairable", "b", "true")
    busctl_set("/org/bluez/hci3", "Powered", "b", "false")


def ensure_connected(adapter_bd: str, peer: str, timeout_s: float = 25) -> bool:
    sh(["bluetoothctl", "select", adapter_bd])
    sh(["bluetoothctl", "trust", peer])
    p = sh(["timeout", str(int(timeout_s)), "bluetoothctl", "connect", peer])
    out = (p.stdout or "") + (p.stderr or "")
    return "Connection successful" in out or "AlreadyConnected" in out or p.returncode == 0


def run_raw_hu(out: Path, hold_s: float) -> int:
    """Raw RFCOMM server on .87 ch6 + f20_sim DummyHuSession."""
    log_path = out / "hu_raw.jsonl"

    def log(obj: dict) -> None:
        with log_path.open("a") as fh:
            fh.write(json.dumps(obj) + "\n")

    srv = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HU87, 6))
    srv.listen(1)
    log({"event": "raw_hu_listening", "adapter": HU87, "channel": 6})
    (out / "hu_raw.ready").write_text("listening\n")
    print(f"raw HU listening {HU87} ch6", flush=True)
    srv.settimeout(hold_s)
    try:
        conn, info = srv.accept()
    except socket.timeout:
        log({"event": "raw_hu_timeout"})
        return 2
    log({"event": "raw_hu_accepted", "peer_info": repr(info)})
    print(f"raw HU accepted {info}", flush=True)
    conn.settimeout(1.0)
    prof = apply_hu_profile("f20_sim")
    sess = DummyHuSession(
        version=int(prof["version"]),
        instance_id=int(prof["instance_id"]),
        buffer_size=int(prof["buffer_size"]),
        echo_watchdog=bool(prof["echo_watchdog"]),
        send_dataack=bool(prof["send_dataack"]),
        etch_stub=bool(prof["etch_stub"]),
        sas_probe=str(prof["sas_probe"]),
        handshake_delay_s=float(prof.get("handshake_delay_s") or 0.0),
        etch_reply_src=prof.get("etch_reply_src"),
    )
    framer = BclFramer()
    t_end = time.time() + hold_s
    while time.time() < t_end:
        try:
            data = conn.recv(4096)
        except socket.timeout:
            data = b""
        except OSError as exc:
            log({"event": "raw_hu_recv_err", "error": str(exc)})
            break
        if data:
            log({"event": "rx_bytes", "n": len(data), "hex": data.hex()})
            fed = framer.feed(data)
            for frame in fed.frames:
                log(
                    {
                        "event": "frame",
                        "cmd": frame.cmd,
                        "src": frame.src,
                        "dest": frame.dest,
                        "len": len(frame.payload or b""),
                    }
                )
            for chunk in sess.on_bytes(data):
                if chunk:
                    conn.sendall(chunk)
                    log({"event": "tx_bytes", "n": len(chunk), "hex": chunk.hex()})
    try:
        conn.close()
    except OSError:
        pass
    srv.close()
    log({"event": "raw_hu_done"})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hold", type=float, default=90.0)
    ap.add_argument(
        "--role",
        choices=("orchestrate", "raw-hu"),
        default="orchestrate",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.role == "raw-hu":
        return run_raw_hu(args.out, args.hold)

    # --- orchestrate on .108 ---
    for pat in (
        "/tmp/bcl_dummy/bcl_dummy_hu_agent",
        "tools/bcl_dummy_hu_agent",
        "/tmp/bcl_dummy/b3_rfcomm_relay",
        "tools/b3_rfcomm_relay",
        "lab_b3_dual_esp_smoke.py --role raw-hu",
    ):
        subprocess.run(["pkill", "-f", pat], check=False)

    subprocess.run(
        ["systemctl", "stop", "idrivesim-rfcomm-bridge.service"], check=False
    )
    prep_adapters()

    print("pair/connect .131↔.87 and USB↔.131", flush=True)
    ensure_connected(BMW131, HU87)
    ensure_connected(HU87, BMW131)
    ensure_connected(USB, BMW131)

    # raw HU on .87
    hu_proc = subprocess.Popen(
        [sys.executable, __file__, "--role", "raw-hu", "--out", str(args.out), "--hold", str(args.hold)],
        stdout=(args.out / "hu_raw.out").open("w"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(50):
        if (args.out / "hu_raw.ready").exists():
            break
        time.sleep(0.1)
    if not (args.out / "hu_raw.ready").exists():
        print("FAIL: raw HU did not become ready", file=sys.stderr)
        hu_proc.kill()
        return 1
    print("raw HU ready", flush=True)

    # B3: listen .131 → connect via .131 → .87
    b3_out = (args.out / "b3.out").open("w")
    b3 = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "b3_rfcomm_relay.py"),
            "rfcomm",
            "--adapter-bd",
            BMW131,
            "--connect-adapter-bd",
            BMW131,
            "--listen-channel",
            "6",
            "--peer",
            HU87,
            "--peer-channel",
            "6",
            "--log",
            str(args.out / "b3.jsonl"),
            "--raw-dir",
            str(args.out / "raw"),
            "--max-s",
            str(args.hold),
        ],
        cwd=str(Path(__file__).resolve().parent),
        stdout=b3_out,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent)},
    )
    time.sleep(1)
    if b3.poll() is not None:
        print("FAIL: B3 exited early:", (args.out / "b3.out").read_text()[-500:], file=sys.stderr)
        hu_proc.kill()
        return 1
    print("B3 listening on .131 ch6", flush=True)

    # Phone client: USB → .131 ch6 (through B3)
    phone_log = args.out / "phone.jsonl"
    phone = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "bcl_dummy_hu_agent.py"),
            "b2a-tx",
            "--adapter-bd",
            USB,
            "--hu-bd",
            BMW131,
            "--channel",
            "6",
            "--full-client",
            "--knock",
            "wire_v5",
            "--selectproto",
            "4",
            "--seconds",
            str(min(60, int(args.hold))),
            "--log",
            str(phone_log),
        ],
        cwd=str(Path(__file__).resolve().parent),
        stdout=(args.out / "phone.out").open("w"),
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent)},
    )

    phone.wait(timeout=args.hold + 30)
    time.sleep(2)
    b3.send_signal(signal.SIGINT)
    try:
        b3.wait(timeout=10)
    except subprocess.TimeoutExpired:
        b3.kill()
    try:
        hu_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        hu_proc.kill()

    # summarize
    summary = {
        "phone_rc": phone.returncode,
        "b3_rc": b3.returncode,
        "hu_rc": hu_proc.returncode,
        "b3_events": [],
        "hu_events": [],
        "phone_events": [],
    }
    for label, path in (
        ("b3_events", args.out / "b3.jsonl"),
        ("hu_events", args.out / "hu_raw.jsonl"),
        ("phone_events", phone_log),
    ):
        if not path.exists():
            continue
        ev = []
        for ln in path.read_text().splitlines():
            try:
                o = json.loads(ln)
            except json.JSONDecodeError:
                continue
            e = o.get("event")
            if e:
                ev.append(e)
        summary[label] = ev[:80]
        summary[f"{label}_n"] = len(ev)

    (args.out / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    want = {"rfcomm_accepted", "rfcomm_connected_hu", "raw_hu_accepted"}
    b3ev = set(summary.get("b3_events") or [])
    huev = set(summary.get("hu_events") or [])
    ok = bool(want & b3ev) or ("raw_hu_accepted" in huev and "rfcomm_accepted" in b3ev)
    # stronger: bytes through relay
    through = "etch" in json.dumps(summary).lower() or any(
        e in (summary.get("hu_events") or []) for e in ("frame", "rx_bytes", "tx_bytes")
    )
    md = [
        f"# B3 dual-ESP lab smoke",
        "",
        f"- out: `{args.out}`",
        f"- phone_rc={phone.returncode} b3_rc={b3.returncode} hu_rc={hu_proc.returncode}",
        f"- relay_accept: **{'yes' if 'rfcomm_accepted' in b3ev else 'no'}**",
        f"- hu_accept: **{'yes' if 'raw_hu_accepted' in huev else 'no'}**",
        f"- bytes_on_hu: **{'yes' if through else 'no'}**",
        f"- claim: LAB only (f20_sim stand-in for F20)",
        "",
    ]
    (args.out / "SUMMARY.md").write_text("\n".join(md))
    print("\n".join(md), flush=True)
    print(json.dumps({k: summary[k] for k in summary if k.endswith("_n") or k.endswith("_rc")}, indent=2))
    return 0 if ("rfcomm_accepted" in b3ev and "raw_hu_accepted" in huev and through) else 1


if __name__ == "__main__":
    raise SystemExit(main())
