#!/usr/bin/env python3
"""Probe Debian/Proxmox lab host for onboard / USB Bluetooth (no BlueZ required).

FACT only from sysfs / lsusb / lsmod / rfkill. Does not bring up HCI or scan.

Usage:
  python3 tools/lab_host_bt_probe.py
  python3 tools/lab_host_bt_probe.py --json-only
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def rfkill_rows() -> list[dict]:
    rows = []
    base = Path("/sys/class/rfkill")
    if not base.is_dir():
        return rows
    for d in sorted(base.glob("rfkill*")):
        rows.append(
            {
                "id": d.name,
                "name": _read(d / "name"),
                "type": _read(d / "type"),
                "state": _read(d / "state"),
                "soft": _read(d / "soft"),
                "hard": _read(d / "hard"),
            }
        )
    return rows


def hci_sysfs() -> list[dict]:
    out = []
    base = Path("/sys/class/bluetooth")
    if not base.is_dir():
        return out
    for d in sorted(base.glob("hci*")):
        device = (d / "device").resolve() if (d / "device").exists() else None
        row = {
            "name": d.name,
            "path": str(d),
            "uevent": _read(d / "uevent"),
            "device_link": str(device) if device else None,
        }
        for key in (
            "address",
            "name",
            "type",
            "bus_type",
            "manufacturer",
            "hci_ver",
            "hci_rev",
            "lmp_ver",
            "lmp_subver",
        ):
            # kernel exposes these only after full HCI bring-up
            val = _read(d / key)
            if val is not None:
                row[key] = val
        out.append(row)
    return out


def lsusb_bt() -> list[str]:
    code, text = _run(["lsusb"])
    if code != 0:
        return []
    keys = ("bluetooth", "8087:0025", "0a12:", "0b05:", "0a5c:", "33fa:")
    lines = []
    for line in text.splitlines():
        low = line.lower()
        if any(k in low or k in line for k in keys):
            lines.append(line.strip())
    return lines


def bt_modules() -> list[str]:
    code, text = _run(["lsmod"])
    if code != 0:
        return []
    want = {
        "bluetooth",
        "btusb",
        "btintel",
        "btrtl",
        "btbcm",
        "btmtk",
        "rfcomm",
        "bnep",
        "hci_uart",
    }
    found = []
    for line in text.splitlines():
        name = line.split()[0] if line.split() else ""
        if name in want:
            found.append(name)
    return found


def af_bluetooth_probe() -> dict:
    """Can this userspace open AF_BLUETOOTH? (often NO inside unprivileged LXC)."""
    import socket

    af = getattr(socket, "AF_BLUETOOTH", 31)
    try:
        s = socket.socket(af, socket.SOCK_RAW, 1)  # BTPROTO_HCI
        s.close()
        return {"supported": True, "errno": None, "error": None}
    except OSError as exc:
        return {
            "supported": False,
            "errno": exc.errno,
            "error": str(exc),
            "hint": (
                "EAFNOSUPPORT in LXC ⇒ host radio may show in sysfs but BlueZ/oracle "
                "must run on Proxmox host (or privileged BT-capable CT), not this container"
                if getattr(exc, "errno", None) == 97
                else "AF_BLUETOOTH socket failed"
            ),
        }


def cap_effective_empty() -> bool | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("CapEff:"):
                return line.split(":", 1)[1].strip().strip("0") == "" or int(
                    line.split(":", 1)[1].strip(), 16
                ) == 0
    except (OSError, ValueError):
        return None
    return None


def probe() -> dict:
    hostname = _read(Path("/etc/hostname")) or platform.node()
    bluez_bin = Path("/usr/bin/bluetoothctl").exists()
    hci = hci_sysfs()
    usb = lsusb_bt()
    mods = bt_modules()
    rf = rfkill_rows()
    bt_rf = [r for r in rf if (r.get("type") or "") == "bluetooth"]
    soft_blocked = any((r.get("soft") or "0") != "0" for r in bt_rf)
    hard_blocked = any((r.get("hard") or "0") != "0" for r in bt_rf)
    af = af_bluetooth_probe()
    unpriv = cap_effective_empty()

    hw_present = bool(usb) or bool(hci) or any(m in mods for m in ("btusb", "btintel", "hci_uart"))
    kernel_hci = bool(hci)
    # BlueZ uses AF_BLUETOOTH sockets; /dev/hci* is uncommon. Oracle needs bluetoothd.
    code_svc, svc_out = _run(["systemctl", "is-active", "bluetooth"])
    bluetoothd = (svc_out.strip() == "active") if code_svc == 0 else False
    userspace_blocked = not af["supported"]
    local_oracle_ready = bool(
        bluez_bin
        and bluetoothd
        and kernel_hci
        and af["supported"]
        and not soft_blocked
        and not hard_blocked
    )

    # Unprivileged LXC cannot use AF_BLUETOOTH (own netns). Control Proxmox BlueZ via SSH.
    ssh_oracle: dict = {"ok": False}
    try:
        import importlib.util

        bridge = ROOT / "tools" / "lab_bt_host_ssh.py"
        spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", bridge)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            reach = mod.host_reachable()
            if reach.get("ok"):
                info = mod.show()
                ssh_oracle = {
                    "ok": bool(info.get("ok")),
                    "ssh": reach.get("ssh"),
                    "controller": info.get("controller"),
                    "powered": info.get("powered"),
                    "mode": "ssh_bluez_on_proxmox_host",
                }
            else:
                ssh_oracle = {"ok": False, "ssh": reach.get("ssh"), "error": reach.get("error") or reach.get("stderr")}
    except Exception as exc:  # noqa: BLE001
        ssh_oracle = {"ok": False, "error": str(exc)}

    oracle_ready = bool(local_oracle_ready or ssh_oracle.get("ok"))

    next_steps: dict[str, str] = {
        "oracle_role": "Debian BlueZ as independent host/oracle vs ESP VHCI analyzer (not MITM)",
        "do_not": "Do not claim Air/RF from this probe",
        "control": "python3 tools/lab_bt_host_ssh.py show|scan  (SSH → Proxmox BlueZ)",
    }
    if not oracle_ready:
        next_steps["deeper_now"] = "Use Method G until host oracle ready"
    if not bluez_bin and not ssh_oracle.get("ok"):
        next_steps["if_no_bluez"] = "On Proxmox host: apt install bluez && systemctl enable --now bluetooth"
    if userspace_blocked and ssh_oracle.get("ok"):
        next_steps["if_lxc_blocked"] = (
            "AF_BLUETOOTH blocked in CT (expected) — oracle via SSH bridge is active"
        )
    elif userspace_blocked:
        next_steps["if_lxc_blocked"] = (
            "AF_BLUETOOTH blocked in CT — install BlueZ on Proxmox host and ensure "
            "ssh root@192.168.178.108 works from this CT"
        )

    return {
        "gate": "HOST_BT_probe",
        "claim": "FACT_host_radio_inventory_not_air_sniffer",
        "hostname": hostname,
        "kernel": platform.release(),
        "machine": platform.machine(),
        "utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "hardware_present": hw_present,
        "kernel_hci_class": kernel_hci,
        "af_bluetooth": af,
        "unprivileged_container": unpriv,
        "userspace_bt_blocked": userspace_blocked,
        "bluez_installed": bluez_bin,
        "bluetoothd_active": bluetoothd,
        "local_oracle_ready": local_oracle_ready,
        "ssh_oracle": ssh_oracle,
        "userspace_oracle_ready": oracle_ready,
        "lsusb_bt": usb,
        "modules": mods,
        "hci": hci,
        "rfkill_bluetooth": bt_rf,
        "soft_blocked": soft_blocked,
        "hard_blocked": hard_blocked,
        "next": next_steps,
        "ok": hw_present,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--no-evidence", action="store_true")
    args = ap.parse_args()
    data = probe()
    if not args.json_only and not args.no_evidence:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        stem = f"LAB_HOST_BT_{data['utc']}"
        (EVIDENCE / f"{stem}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        md = [
            f"# LAB HOST BT — {'PASS' if data['ok'] else 'FAIL'}",
            "",
            f"**UTC:** {data['utc']} · **host:** {data['hostname']}",
            f"**Raw:** [`{stem}.json`]({stem}.json)",
            "",
            f"- hardware_present: {data['hardware_present']}",
            f"- kernel hci class: {data['kernel_hci_class']} ({', '.join(h['name'] for h in data['hci']) or 'none'})",
            f"- af_bluetooth: {(data.get('af_bluetooth') or {}).get('supported')} · "
            f"userspace_bt_blocked: {data.get('userspace_bt_blocked')}",
            f"- bluez_installed: {data['bluez_installed']} · bluetoothd: {data['bluetoothd_active']}",
            f"- oracle_ready: {data['userspace_oracle_ready']}",
            "",
            "USB:",
        ]
        md.extend(f"- `{l}`" for l in data["lsusb_bt"] or [])
        if not data["lsusb_bt"]:
            md.append("- (none)")
        md += [
            "",
            "Modules: " + (", ".join(data["modules"]) or "(none)"),
            "",
            "Claim: host radio inventory only — not Air/RF sniffer.",
            "",
        ]
        (EVIDENCE / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        data["evidence_stem"] = stem
    print(json.dumps(data, indent=2))
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
