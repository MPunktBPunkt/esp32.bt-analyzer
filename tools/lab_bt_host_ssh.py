#!/usr/bin/env python3
"""SSH bridge to Proxmox host BlueZ (Cursor LXC has no AF_BLUETOOTH).

Default host: root@192.168.178.108 (ThinkCentre / Proxmox).
Override: BT_HOST_SSH=user@host

Usage:
  python3 tools/lab_bt_host_ssh.py show|scan|devices
  python3 tools/lab_bt_host_ssh.py connect AA:BB:CC:DD:EE:FF
  python3 tools/lab_bt_host_ssh.py disconnect AA:BB:…
  python3 tools/lab_bt_host_ssh.py info AA:BB:…
  python3 tools/lab_bt_host_ssh.py pair AA:BB:…
  python3 tools/lab_bt_host_ssh.py remove AA:BB:…
  python3 tools/lab_bt_host_ssh.py gatt-primary AA:BB:…
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from typing import Any

DEFAULT_SSH = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")
ADDR_RE = re.compile(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")


def ssh_run(args: list[str], timeout: float = 30.0, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
        DEFAULT_SSH,
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
    )


def host_reachable() -> dict[str, Any]:
    try:
        p = ssh_run(["true"], timeout=8)
        return {
            "ok": p.returncode == 0,
            "ssh": DEFAULT_SSH,
            "stderr": (p.stderr or "").strip() or None,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "ssh": DEFAULT_SSH, "error": str(exc)}


def bluetoothctl(*ctl_args: str, timeout: float = 20.0) -> dict[str, Any]:
    p = ssh_run(["bluetoothctl", *ctl_args], timeout=timeout)
    return {
        "ok": p.returncode == 0,
        "args": list(ctl_args),
        "stdout": p.stdout or "",
        "stderr": p.stderr or "",
        "returncode": p.returncode,
    }


def ensure_agent() -> bool:
    """Power on and check that bt-pair-agent answers pairing (docs/PAIRING.md).

    A one-shot `bluetoothctl agent …` dies with its process, so it cannot be the
    fallback. One-shot `bluetoothctl pair X` registers no agent of its own, so
    both sides are answered by the default agent — the service.
    """
    bluetoothctl("power", "on", timeout=10)
    p = ssh_run(["systemctl", "is-active", "bt-pair-agent"], timeout=10)
    active = (p.stdout or "").strip() == "active"
    if not active:
        print("WARN: bt-pair-agent not active on BlueZ host — pairing requests stay unanswered "
              "(python3 tools/lab_pair_agent.py deploy)", file=sys.stderr)
    return active


def show() -> dict[str, Any]:
    r = bluetoothctl("show")
    text = r.get("stdout") or ""
    addr = None
    m = re.search(r"Controller\s+([0-9A-Fa-f:]{17})", text)
    if m:
        addr = m.group(1).lower()
    powered = "Powered: yes" in text
    return {
        "ok": bool(r.get("ok") and powered),
        "controller": addr,
        "powered": powered,
        "raw": text.strip(),
        "ssh": DEFAULT_SSH,
        "error": None if r.get("ok") else (r.get("stderr") or "bluetoothctl_show_failed"),
    }


def scan(seconds: float = 8.0) -> dict[str, Any]:
    """Non-interactive scan on Proxmox: `bluetoothctl --timeout N scan on`."""
    ensure_agent()
    sec = max(3, int(seconds))
    p = ssh_run(
        ["bluetoothctl", f"--timeout={sec}", "scan", "on"],
        timeout=float(sec) + 15.0,
    )
    scan_text = (p.stdout or "") + (p.stderr or "")
    dev = bluetoothctl("devices", timeout=15)
    text = (dev.get("stdout") or "") + "\n" + scan_text
    addrs = sorted({m.group(1).lower() for m in ADDR_RE.finditer(text)})
    lines = [ln.strip() for ln in (dev.get("stdout") or "").splitlines() if ln.strip()]
    return {
        "ok": bool(dev.get("ok") or addrs),
        "seconds": sec,
        "addrs": addrs,
        "devices": lines,
        "scan_log_tail": "\n".join(scan_text.strip().splitlines()[-30:]),
        "ssh": DEFAULT_SSH,
        "error": None if (dev.get("ok") or addrs) else (dev.get("stderr") or "scan_failed"),
    }


def info(addr: str) -> dict[str, Any]:
    r = bluetoothctl("info", addr, timeout=15)
    text = r.get("stdout") or ""
    return {
        "ok": "Device " in text or r.get("ok"),
        "addr": addr.lower(),
        "connected": "Connected: yes" in text,
        "paired": "Paired: yes" in text,
        "trusted": "Trusted: yes" in text,
        "name": _field(text, "Name"),
        "alias": _field(text, "Alias"),
        "uuids": re.findall(r"UUID:\s+[^\n(]+\(([0-9a-fA-F-]{36}|0x[0-9a-fA-F]+)\)", text)
        or re.findall(r"UUID:\s+([0-9a-fA-F-]{36})", text),
        "raw": text.strip(),
        "ssh": DEFAULT_SSH,
    }


def _field(text: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


def connect(addr: str, timeout_s: float = 20.0) -> dict[str, Any]:
    ensure_agent()
    t0 = time.time()
    try:
        r = bluetoothctl("connect", addr, timeout=timeout_s + 5)
        text = (r.get("stdout") or "") + (r.get("stderr") or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        inf = info(addr)
        return {
            "ok": bool(inf.get("connected")),
            "addr": addr.lower(),
            "elapsed_s": round(time.time() - t0, 3),
            "connect_raw": str(exc),
            "info": inf,
            "ssh": DEFAULT_SSH,
        }
    inf = info(addr)
    ok = inf.get("connected") or ("Connection successful" in text)
    return {
        "ok": bool(ok),
        "addr": addr.lower(),
        "elapsed_s": round(time.time() - t0, 3),
        "connect_raw": text.strip(),
        "info": inf,
        "ssh": DEFAULT_SSH,
    }


def disconnect(addr: str) -> dict[str, Any]:
    r = bluetoothctl("disconnect", addr, timeout=15)
    time.sleep(0.5)
    inf = info(addr)
    return {
        "ok": not inf.get("connected"),
        "addr": addr.lower(),
        "raw": (r.get("stdout") or "") + (r.get("stderr") or ""),
        "info": inf,
        "ssh": DEFAULT_SSH,
    }


def pair(addr: str) -> dict[str, Any]:
    agent = ensure_agent()
    t0 = time.time()
    r = bluetoothctl("pair", addr, timeout=45)
    text = (r.get("stdout") or "") + (r.get("stderr") or "")
    bluetoothctl("trust", addr, timeout=10)
    inf = info(addr)
    return {
        "ok": bool(inf.get("paired") or "Pairing successful" in text),
        "pair_agent": agent,
        "addr": addr.lower(),
        "elapsed_s": round(time.time() - t0, 3),
        "raw": text.strip(),
        "info": inf,
        "ssh": DEFAULT_SSH,
    }


def remove(addr: str) -> dict[str, Any]:
    disconnect(addr)
    r = bluetoothctl("remove", addr, timeout=15)
    return {
        "ok": r.get("ok") or "been removed" in ((r.get("stdout") or "") + (r.get("stderr") or "")).lower(),
        "addr": addr.lower(),
        "raw": ((r.get("stdout") or "") + (r.get("stderr") or "")).strip(),
        "ssh": DEFAULT_SSH,
    }


def gatt_primary(addr: str) -> dict[str, Any]:
    """List GATT attributes via bluetoothctl (device must already be connected).

    Note: thin ESP peer stubs often do not complete BlueZ service resolution;
    callers should also MEASURE profiles via analyzer HOGP/FTMS on the same stub.
    """
    # Wait briefly for ServicesResolved
    time.sleep(1.5)
    script = f"menu gatt\nlist-attributes {addr}\nback\nquit\n"
    p = ssh_run(["bluetoothctl"], timeout=25, input_text=script)
    text = (p.stdout or "") + (p.stderr or "")
    # Fallback: gatttool only if not busy (no active bluetoothctl connection)
    if "1812" not in text and "1826" not in text and "1800" not in text:
        gt = ssh_run(["gatttool", "-b", addr, "--primary"], timeout=20)
        text += "\n" + ((gt.stdout or "") + (gt.stderr or ""))
    uuids = sorted(set(re.findall(r"([0-9a-fA-F-]{4,36})", text)))
    has_hid = "1812" in text.lower() or any(u.lower().endswith("1812") for u in uuids)
    has_ftms = "1826" in text.lower() or any(u.lower().endswith("1826") for u in uuids)
    has_gap = "1800" in text.lower() or any(u.lower().endswith("1800") for u in uuids)
    return {
        "ok": has_gap or has_hid or has_ftms or ("Attribute" in text),
        "addr": addr.lower(),
        "services": [],
        "uuids_guess": uuids[:40],
        "has_gap": has_gap,
        "has_hid": has_hid,
        "has_ftms": has_ftms,
        "raw": text.strip()[:4000],
        "ssh": DEFAULT_SSH,
        "note": "thin_esp_stub_may_not_resolve_under_bluez",
    }


def gatt_read(addr: str, handle: str) -> dict[str, Any]:
    p = ssh_run(["gatttool", "-b", addr, "--char-read", "-a", handle], timeout=20)
    text = (p.stdout or "") + (p.stderr or "")
    return {
        "ok": "Characteristic value" in text or p.returncode == 0,
        "addr": addr.lower(),
        "handle": handle,
        "raw": text.strip(),
        "ssh": DEFAULT_SSH,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "cmd",
        choices=(
            "ping",
            "show",
            "scan",
            "devices",
            "connect",
            "disconnect",
            "info",
            "pair",
            "remove",
            "gatt-primary",
            "gatt-read",
        ),
    )
    ap.add_argument("addr", nargs="?", default="")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--handle", default="0x0012", help="for gatt-read")
    args = ap.parse_args()

    if args.cmd == "ping":
        out = host_reachable()
    elif args.cmd == "show":
        out = show()
    elif args.cmd == "devices":
        out = bluetoothctl("devices")
        text = out.get("stdout") or ""
        out = {
            "ok": out.get("ok"),
            "addrs": sorted({m.group(1).lower() for m in ADDR_RE.finditer(text)}),
            "devices": [ln.strip() for ln in text.splitlines() if ln.strip()],
            "ssh": DEFAULT_SSH,
        }
    elif args.cmd == "scan":
        out = scan(args.seconds)
    else:
        if not args.addr:
            print(json.dumps({"ok": False, "error": "addr_required"}))
            return 1
        addr = args.addr
        if args.cmd == "connect":
            out = connect(addr)
        elif args.cmd == "disconnect":
            out = disconnect(addr)
        elif args.cmd == "info":
            out = info(addr)
        elif args.cmd == "pair":
            out = pair(addr)
        elif args.cmd == "remove":
            out = remove(addr)
        elif args.cmd == "gatt-primary":
            out = gatt_primary(addr)
        else:
            out = gatt_read(addr, args.handle)

    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
