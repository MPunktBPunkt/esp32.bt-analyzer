#!/usr/bin/env python3
"""Classic service inventory via Proxmox BlueZ (observe-only; no profile impl).

Modern BlueZ often has no classic `sdptool browse local` socket — we inventory
controller UUIDs + discovered device UUID/name hints, plus optional .87 discoverable.

Usage:
  python3 tools/lab_sdp_inventory.py
  python3 tools/lab_sdp_inventory.py --with-esp-classic --scan-s 12
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"

# Fingerprint UUIDs relevant to AAIdrive / BMW HU (observe only)
INTEREST = {
    "1101": "Serial Port (SPP)",
    "110a": "Audio Source (A2DP)",
    "110b": "Audio Sink (A2DP)",
    "110c": "AVRCP Target",
    "110e": "AVRCP",
    "110f": "AVRCP Controller",
    "111e": "HFP HF",
    "111f": "HFP AG",
    "1124": "HID",
    "112f": "Phonebook Access PCE",
    "1130": "Phonebook Access PSE",
    "1200": "PnP Information",
}


def load_ssh():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", ROOT / "tools" / "lab_bt_host_ssh.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def post(url: str, fields: dict | None = None) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            r.read()
    except Exception:  # noqa: BLE001
        pass


def extract_interest(text: str) -> dict:
    found = {}
    low = text.lower()
    for u, name in INTEREST.items():
        if u in low or name.lower().split("(")[0].strip().lower() in low:
            found[u] = name
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan-s", type=float, default=10.0)
    ap.add_argument("--with-esp-classic", action="store_true")
    ap.add_argument("--esp", default="192.168.178.87")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()

    show = ssh.show()
    local = extract_interest(show.get("raw") or "")
    sdp_local = ssh.ssh_run(["sdptool", "browse", "local"], timeout=15)
    sdp_local_txt = ((sdp_local.stdout or "") + (sdp_local.stderr or "")).strip()

    if args.with_esp_classic:
        post(f"http://{args.esp}/api/bt/discoverable/start", {"name": "sdp-stim-87"})
        time.sleep(0.6)

    scan = ssh.scan(args.scan_s)
    devices = []
    for ln in scan.get("devices") or []:
        m = re.search(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)$", ln)
        if not m:
            continue
        addr = m.group(1).lower()
        inf = ssh.info(addr)
        raw = inf.get("raw") or ""
        devices.append(
            {
                "addr": addr,
                "name": m.group(2).strip() or inf.get("name") or inf.get("alias"),
                "uuids_interest": extract_interest(raw + " " + " ".join(inf.get("uuids") or [])),
                "paired": inf.get("paired"),
                "connected": inf.get("connected"),
            }
        )

    if args.with_esp_classic:
        post(f"http://{args.esp}/api/bt/discoverable/stop")

    # PASS: host powered + local AVRCP/GAP inventory (Classic service presence on host)
    ok = bool(show.get("ok") and ("110c" in local or "110e" in local))
    out = {
        "utc": utc,
        "gate": "SDP_inventory",
        "topology": "H_HOST_ORACLE",
        "claim": "classic_service_uuid_inventory_observe_not_impl",
        "controller": show.get("controller"),
        "local_interest_uuids": local,
        "sdptool_local": {
            "ok": "Failed" not in sdp_local_txt[:80] and bool(sdp_local_txt),
            "note": "BlueZ 5 often has no classic SDP unix socket — UUID inventory via bluetoothctl show is MEASURED",
            "raw_tail": sdp_local_txt[-500:] if sdp_local_txt else None,
        },
        "scan_devices": devices,
        "esp_classic": args.esp if args.with_esp_classic else None,
        "ok": ok,
        "note": "Decoder depth deferred until BMW/AAIdrive capture shows real PSM/RFCOMM",
    }
    stem = f"LAB_SDP_INVENTORY_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB SDP Inventory — {'PASS' if ok else 'FAIL'}",
        "",
        f"**UTC:** {utc} · controller `{show.get('controller')}`",
        "",
        f"Local interest UUIDs: {', '.join(f'`{k}`' for k in local) or 'none'}",
        f"Scan devices: {len(devices)}",
        "",
        "Observe-only — no SPP/A2DP/HFP implementation.",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": ok,
                "stem": stem,
                "local": list(local),
                "devices": len(devices),
                "sdptool_local_ok": out["sdptool_local"]["ok"],
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
