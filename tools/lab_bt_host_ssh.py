#!/usr/bin/env python3
"""SSH bridge to Proxmox host BlueZ (Cursor LXC has no AF_BLUETOOTH).

Default host: root@192.168.178.108 (ThinkCentre / Proxmox).
Override: BT_HOST_SSH=user@host

Usage:
  python3 tools/lab_bt_host_ssh.py show
  python3 tools/lab_bt_host_ssh.py scan --seconds 8
  python3 tools/lab_bt_host_ssh.py devices
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
    bluetoothctl("power", "on", timeout=10)
    sec = max(3, int(seconds))
    # BlueZ 5.82: --timeout ends discovery; stdout lists NEW devices during scan.
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("ping", "show", "scan", "devices"))
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--json", action="store_true")
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
    else:
        out = scan(args.seconds)

    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
