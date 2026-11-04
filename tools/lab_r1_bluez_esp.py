#!/usr/bin/env python3
"""R1a — BlueZ (Proxmox) ↔ ESP peripheral as synthetic real-device stand-in.

No external keyboard/headset required: .89 advertises; BlueZ scan/connect/info/disconnect.

Usage:
  python3 tools/lab_r1_bluez_esp.py
  python3 tools/lab_r1_bluez_esp.py --peer 192.168.178.89
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {}
            except json.JSONDecodeError:
                return {"raw": body}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def load_ssh():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", ROOT / "tools" / "lab_bt_host_ssh.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--peer", default="192.168.178.89")
    ap.add_argument("--scan-s", type=float, default=8.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()

    post(f"http://{args.peer}/api/bt/disconnect")
    post(f"http://{args.peer}/api/bt/advertise/stop")
    time.sleep(0.3)
    st = get(f"http://{args.peer}/api/status")
    bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "r1-esp-89"})
    time.sleep(0.8)

    show = ssh.show()
    scan = ssh.scan(args.scan_s)
    seen = bd in (scan.get("addrs") or [])
    conn = ssh.connect(bd) if seen else {"ok": False, "error": "peer_not_in_scan", "addr": bd}
    inf = ssh.info(bd) if conn.get("ok") else {}
    disc = ssh.disconnect(bd) if conn.get("ok") else {"ok": True, "skipped": True}

    ok = bool(show.get("ok") and seen and conn.get("ok") and disc.get("ok"))
    out = {
        "utc": utc,
        "gate": "R1a_bluez_esp",
        "topology": "H_HOST_ORACLE",
        "claim": "bluez_host_vs_esp_peripheral_not_air",
        "peer_ip": args.peer,
        "peer_bd": bd,
        "fw": (st.get("fwVersion") or st.get("version")),
        "show": {"ok": show.get("ok"), "controller": show.get("controller")},
        "scan_seen": seen,
        "connect": conn,
        "info": inf,
        "disconnect": disc,
        "ok": ok,
        "note": "ESP stand-in for external device until operator brings keyboard/headset",
    }
    stem = f"LAB_R1_BLUEZ_ESP_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB R1a BlueZ↔ESP — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · peer `{bd}` @ {args.peer}\n"
        f"- BlueZ saw ESP: {seen}\n- connect: {conn.get('ok')} ({conn.get('elapsed_s')}s)\n"
        f"- disconnect: {disc.get('ok')}\n\n"
        "Claim: BlueZ host path · ESP = synthetic peripheral · not Air.\n",
        encoding="utf-8",
    )
    post(f"http://{args.peer}/api/bt/advertise/stop")
    print(json.dumps({"ok": ok, "stem": stem, "seen": seen, "connected": conn.get("ok")}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
