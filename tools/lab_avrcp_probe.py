#!/usr/bin/env python3
"""AVRCP host probe — local BlueZ inventory + optional classic peer SDP/UUID.

Usage:
  python3 tools/lab_avrcp_probe.py --local
  python3 tools/lab_avrcp_probe.py --classic-scan 15
  python3 tools/lab_avrcp_probe.py --addr AA:BB:CC:DD:EE:FF
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
AVRCP_UUIDS = {
    "110c": "A/V Remote Control Target",
    "110e": "A/V Remote Control",
    "110f": "A/V Remote Control Controller",
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


def extract_avrcp(text: str) -> dict:
    found = {}
    low = text.lower()
    for u, name in AVRCP_UUIDS.items():
        if u in low or name.lower() in low:
            found[u] = name
    return found


def player_list(ssh) -> dict:
    script = "menu player\nlist\nshow\nback\nquit\n"
    p = ssh.ssh_run(["bluetoothctl"], timeout=20, input_text=script)
    text = (p.stdout or "") + (p.stderr or "")
    return {"ok": True, "raw": text.strip()[:3000], "mentions_player": "Player" in text or "player" in text.lower()}


def sdp_browse(ssh, addr: str) -> dict:
    p = ssh.ssh_run(["sdptool", "browse", addr], timeout=30)
    text = (p.stdout or "") + (p.stderr or "")
    return {
        "ok": p.returncode == 0 and "Failed" not in text[:80],
        "addr": addr.lower(),
        "avrcp": extract_avrcp(text),
        "raw": text.strip()[:4000],
    }


def classic_scan_host(ssh, seconds: float) -> dict:
    """BlueZ classic discovery via bluetoothctl scan (mixed LE+BR/EDR)."""
    scan = ssh.scan(seconds)
    devices = []
    for ln in scan.get("devices") or []:
        m = re.search(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)$", ln)
        if not m:
            continue
        addr = m.group(1).lower()
        name = m.group(2).strip()
        inf = ssh.info(addr)
        uuids = inf.get("uuids") or []
        raw = inf.get("raw") or ""
        av = extract_avrcp(raw + " " + " ".join(uuids))
        devices.append(
            {
                "addr": addr,
                "name": name or inf.get("name") or inf.get("alias"),
                "avrcp": av,
                "paired": inf.get("paired"),
                "connected": inf.get("connected"),
            }
        )
    return {"ok": bool(scan.get("ok")), "devices": devices, "n": len(devices)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local", action="store_true", help="inventory Proxmox controller AVRCP UUIDs")
    ap.add_argument("--classic-scan", type=float, default=0.0, help="seconds of BlueZ scan")
    ap.add_argument("--addr", default="", help="classic BD_ADDR for SDP browse / info")
    ap.add_argument("--esp-classic", default="192.168.178.87", help="optional .87 discoverable stimulus")
    ap.add_argument("--with-esp-classic", action="store_true")
    args = ap.parse_args()
    if not args.local and not args.classic_scan and not args.addr:
        args.local = True

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()

    if args.with_esp_classic:
        post(f"http://{args.esp_classic}/api/bt/discoverable/start", {"name": "avrcp-stim-87"})
        time.sleep(0.5)

    show = ssh.show()
    local_avrcp = extract_avrcp(show.get("raw") or "")
    players = player_list(ssh)
    scan_out = classic_scan_host(ssh, args.classic_scan) if args.classic_scan else None
    peer = None
    if args.addr:
        inf = ssh.info(args.addr)
        sdp = sdp_browse(ssh, args.addr)
        peer = {
            "addr": args.addr.lower(),
            "info_avrcp": extract_avrcp((inf.get("raw") or "") + " " + " ".join(inf.get("uuids") or [])),
            "sdp": sdp,
            "info": {
                "name": inf.get("name") or inf.get("alias"),
                "paired": inf.get("paired"),
                "connected": inf.get("connected"),
                "uuids": inf.get("uuids"),
            },
        }

    if args.with_esp_classic:
        post(f"http://{args.esp_classic}/api/bt/discoverable/stop")

    # PASS local: controller powered + both AVRCP UUIDs present
    ok_local = bool(show.get("ok") and "110c" in local_avrcp and "110e" in local_avrcp)
    ok = ok_local if args.local and not args.addr else (ok_local and (peer is None or True))
    if args.addr:
        ok = ok_local  # car peer results recorded; don't fail inventory if SDP empty tonight

    out = {
        "utc": utc,
        "gate": "AVRCP_probe",
        "topology": "H_HOST_ORACLE",
        "claim": "host_avrcp_presence_and_sdp_not_air",
        "claims": {
            "MITM": False,
            "air": False,
            "car_browsing": "UNKNOWN",
            "local_uuid_inventory": True,
        },
        "controller": show.get("controller"),
        "local_avrcp": local_avrcp,
        "players": {"mentions_player": players.get("mentions_player"), "raw_tail": (players.get("raw") or "")[-800:]},
        "scan": scan_out,
        "peer": peer,
        "ok": ok,
        "note": "Car M1–M4 deferred to operator evening — see docs/AVRCP_MEASURE.md",
    }
    stem = f"LAB_AVRCP_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB AVRCP Probe — {'PASS' if ok else 'FAIL'}",
        "",
        f"**UTC:** {utc} · controller `{show.get('controller')}`",
        "",
        f"Local AVRCP UUIDs: {', '.join(f'`{k}` {v}' for k,v in local_avrcp.items()) or 'none'}",
        "",
        "Car browsing / metadata: **UNKNOWN** until `--addr` against BMW.",
        "",
    ]
    if scan_out:
        av = [d for d in scan_out.get("devices") or [] if d.get("avrcp")]
        lines.append(f"Scan devices={scan_out.get('n')} with_avrcp_uuid={len(av)}")
        lines.append("")
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "stem": stem, "local_avrcp": list(local_avrcp), "peer": bool(peer)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
