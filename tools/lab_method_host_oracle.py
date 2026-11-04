#!/usr/bin/env python3
"""Method H — Host BlueZ oracle vs ESP multi-scan (cross-visibility).

When AF_BLUETOOTH/BlueZ works on this host: LE scan via bluetoothctl, parallel
ESP scans on .88/.89/.87, intersect BD_ADDR sets (foreign devices).

When blocked (typical unprivileged LXC): write BLOCKED evidence + still run the
ESP half as baseline. Never claims Air/RF sniffer.

Usage:
  python3 tools/lab_method_host_oracle.py
  python3 tools/lab_method_host_oracle.py --scan-s 10
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
NODES = {
    "88": "192.168.178.88",
    "89": "192.168.178.89",
    "87": "192.168.178.87",
}

ADDR_RE = re.compile(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            r.read()
    except Exception:  # noqa: BLE001
        pass


def load_probe() -> dict:
    import importlib.util

    path = ROOT / "tools" / "lab_host_bt_probe.py"
    spec = importlib.util.spec_from_file_location("lab_host_bt_probe", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.probe()


def quiet_esp() -> None:
    for ip in NODES.values():
        for path in (
            "/api/bt/scan/stop",
            "/api/bt/advertise/stop",
            "/api/bt/inquiry/stop",
            "/api/bt/disconnect",
        ):
            post(f"http://{ip}{path}")


def esp_meta() -> dict:
    meta = {}
    for name, ip in NODES.items():
        st = get(f"http://{ip}/api/status")
        oc = st.get("onchip") or {}
        meta[name] = {
            "ip": ip,
            "bd_addr": oc.get("bdAddr"),
            "ready": bool(oc.get("ready")),
            "fw": st.get("fwVersion"),
        }
    return meta


def esp_advertise_window(meta: dict, scan_s: float) -> dict:
    """All lab nodes advertise so a host oracle can observe them (no ESP scan)."""
    started = {}
    for name, ip in NODES.items():
        post(f"http://{ip}/api/bt/advertise/start", {"name": f"oracle-{name}"})
        started[name] = True
    time.sleep(scan_s)
    return {"started": started, "duration_s": scan_s}


def esp_lab_visibility(meta: dict, scan_s: float) -> dict:
    """Sequential advertise/scan (Method G lite) — avoids dual-role scan starvation."""
    lab_bds = {
        str(m.get("bd_addr") or "").lower() for m in meta.values() if m.get("bd_addr")
    }
    views: dict[str, dict] = {n: {"addrs": set(), "ok": True} for n in NODES}
    for adv, adv_ip in NODES.items():
        if not meta[adv].get("bd_addr"):
            continue
        quiet_esp()
        time.sleep(0.25)
        post(f"http://{adv_ip}/api/bt/advertise/start", {"name": f"oracle-{adv}"})
        time.sleep(0.4)
        scanners = [n for n in NODES if n != adv]
        for sc in scanners:
            post(f"http://{NODES[sc]}/api/bt/scan/start")
        time.sleep(scan_s)
        adv_bd = str(meta[adv]["bd_addr"]).lower()
        for sc in scanners:
            post(f"http://{NODES[sc]}/api/bt/scan/stop")
            try:
                devices = (get(f"http://{NODES[sc]}/api/bt/devices").get("devices")) or []
            except Exception as exc:  # noqa: BLE001
                views[sc]["ok"] = False
                views[sc]["error"] = str(exc)
                continue
            for d in devices:
                addr = str(d.get("addr") or "").lower()
                if addr:
                    views[sc]["addrs"].add(addr)
            if adv_bd not in views[sc]["addrs"]:
                views[sc].setdefault("missed", []).append(adv)
        post(f"http://{adv_ip}/api/bt/advertise/stop")

    lab_visibility = {}
    for name, v in views.items():
        own = str((meta[name].get("bd_addr") or "")).lower()
        others = lab_bds - {own}
        addrs = set(v.get("addrs") or [])
        seen = others & addrs
        lab_visibility[name] = {
            "sees_lab_peers": sorted(seen),
            "missing_lab_peers": sorted(others - seen),
            "foreign_n": len(addrs - lab_bds),
            "ok": others <= addrs and v.get("ok", True),
        }
    return {
        "views": {
            k: {
                "addrs": sorted(v["addrs"]),
                "ok": v.get("ok", True),
                "error": v.get("error"),
                "missed": v.get("missed"),
            }
            for k, v in views.items()
        },
        "lab_visibility": lab_visibility,
        "lab_ok": all(x.get("ok") for x in lab_visibility.values()) and len(lab_visibility) == 3,
    }


def bluez_scan(scan_s: float) -> dict:
    """BlueZ LE/Classic device scan — local bluetoothctl or SSH→Proxmox host."""
    # Prefer SSH bridge when local AF_BLUETOOTH is unavailable (Cursor LXC).
    try:
        import importlib.util

        bridge = ROOT / "tools" / "lab_bt_host_ssh.py"
        spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", bridge)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if mod.host_reachable().get("ok"):
                out = mod.scan(scan_s)
                return {
                    "ok": bool(out.get("ok")),
                    "addrs": out.get("addrs") or [],
                    "raw_devices": out.get("devices") or [],
                    "via": "ssh_proxmox",
                    "ssh": out.get("ssh"),
                    "error": out.get("error"),
                }
    except Exception as exc:  # noqa: BLE001
        ssh_err = str(exc)
    else:
        ssh_err = None

    script = "power on\nscan on\n"
    try:
        subprocess.run(
            ["bluetoothctl"],
            input=script,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "error": f"bluetoothctl_start: {exc}",
            "addrs": [],
            "via": "local",
            "ssh_error": ssh_err,
        }

    time.sleep(scan_s)
    try:
        p = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        text = p.stdout or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, text=True, timeout=5)
        return {"ok": False, "error": str(exc), "addrs": [], "via": "local"}

    subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, text=True, timeout=5)
    addrs = sorted({m.group(1).lower() for m in ADDR_RE.finditer(text)})
    return {
        "ok": True,
        "addrs": addrs,
        "raw_devices": text.strip().splitlines()[:50],
        "via": "local",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan-s", type=float, default=10.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    probe = load_probe()
    quiet_esp()
    time.sleep(0.3)
    meta = esp_meta()
    lab_bds = {
        str(m.get("bd_addr") or "").lower() for m in meta.values() if m.get("bd_addr")
    }

    oracle_ready = bool(probe.get("userspace_oracle_ready"))
    ssh_oracle = probe.get("ssh_oracle") or {}
    local_blocked = bool(probe.get("userspace_bt_blocked")) and not bool(
        probe.get("local_oracle_ready")
    )
    host_scan: dict
    if not oracle_ready:
        adv = esp_advertise_window(meta, min(args.scan_s, 4.0))
        quiet_esp()
        host_scan = {
            "ok": False,
            "skipped": True,
            "reason": "userspace_oracle_not_ready",
            "af_bluetooth": probe.get("af_bluetooth"),
            "userspace_bt_blocked": probe.get("userspace_bt_blocked"),
            "ssh_oracle": ssh_oracle,
            "esp_advertise": adv,
        }
        blocked = True
    else:
        # Host (local or SSH→Proxmox) scans while ESPs advertise.
        for name, ip in NODES.items():
            post(f"http://{ip}/api/bt/advertise/start", {"name": f"oracle-{name}"})
        time.sleep(0.5)
        host_scan = bluez_scan(args.scan_s)
        quiet_esp()
        blocked = False

    # ESP lab visibility = Method G lite (separate phase, no dual-role).
    vis = esp_lab_visibility(meta, max(4.0, args.scan_s * 0.6))
    esp_lab_ok = bool(vis.get("lab_ok"))
    esp_union = set()
    for v in (vis.get("views") or {}).values():
        esp_union.update(v.get("addrs") or [])

    host_addrs = set(host_scan.get("addrs") or [])
    host_sees_lab = sorted(host_addrs & lab_bds)
    foreign_esp = esp_union - lab_bds
    foreign_host = host_addrs - lab_bds
    foreign_both = sorted(foreign_esp & foreign_host)

    if blocked:
        ok = bool(probe.get("hardware_present")) and esp_lab_ok
        status = "BLOCKED_HOST_ORACLE" if ok else "FAIL"
    else:
        ok = bool(host_scan.get("ok")) and len(host_sees_lab) >= 2 and esp_lab_ok
        status = "PASS" if ok else "FAIL"

    out = {
        "utc": utc,
        "topology": "H_HOST_ORACLE",
        "gate": "BT9_host_oracle",
        "method": "H_host_bluez_oracle",
        "claim": "host_oracle_vs_esp_scan_intersection_not_air_phy",
        "status": status,
        "ok": ok,
        "blocked_host_userspace": blocked,
        "local_af_bluetooth_blocked": local_blocked,
        "oracle_via": host_scan.get("via") or ("ssh" if ssh_oracle.get("ok") else None),
        "probe": {
            "hardware_present": probe.get("hardware_present"),
            "userspace_oracle_ready": probe.get("userspace_oracle_ready"),
            "local_oracle_ready": probe.get("local_oracle_ready"),
            "ssh_oracle": ssh_oracle,
            "userspace_bt_blocked": probe.get("userspace_bt_blocked"),
            "af_bluetooth": probe.get("af_bluetooth"),
            "lsusb_bt": probe.get("lsusb_bt"),
        },
        "scan_s": args.scan_s,
        "esp": {"meta": meta, "views": vis.get("views")},
        "host_scan": host_scan,
        "lab_bd_addrs": sorted(lab_bds),
        "host_sees_lab": host_sees_lab,
        "foreign_intersection": foreign_both,
        "lab_visibility": vis.get("lab_visibility"),
        "next": probe.get("next"),
    }
    stem = f"LAB_METHOD_H_ORACLE_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    md = [
        f"# LAB Method H Host Oracle — {status}",
        "",
        f"**UTC:** {utc} · **topology:** H_HOST_ORACLE",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        f"- host oracle ready: {probe.get('userspace_oracle_ready')}",
        f"- userspace BT blocked: {probe.get('userspace_bt_blocked')} "
        f"(af_bluetooth={ (probe.get('af_bluetooth') or {}).get('supported') })",
        f"- ESP lab peer visibility: {esp_lab_ok}",
        f"- host sees lab ESPs: {host_sees_lab or '(n/a)'}",
        f"- foreign BD intersection host∩ESP: {foreign_both or '(none)'}",
        "",
        "### Classification",
        "",
        "| Claim | Status |",
        "|-------|--------|",
        f"| Host radio present (sysfs/USB) | FACT |" if probe.get("hardware_present") else "| Host radio | UNKNOWN |",
        f"| AF_BLUETOOTH in this CT | {'REJECTED/blocked' if blocked else 'FACT'} |",
        f"| ESP lab LE visibility | {'MEASURED' if esp_lab_ok else 'FAIL'} |",
        "| BlueZ scan oracle | "
        + ("BLOCKED" if blocked else ("MEASURED" if host_scan.get("ok") else "FAIL"))
        + " |",
        "| Air/RF PHY sniffer | REJECTED |",
        "",
        "### NEXT TEST",
        "- Unblock: BlueZ on Proxmox host or BT-capable CT, re-run this tool",
        "- Method G multiview for full RSSI matrix",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    quiet_esp()
    print(
        json.dumps(
            {
                "ok": ok,
                "status": status,
                "stem": stem,
                "blocked": blocked,
                "esp_lab_ok": esp_lab_ok,
                "host_sees_lab": host_sees_lab,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
