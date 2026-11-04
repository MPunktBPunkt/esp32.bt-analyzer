#!/usr/bin/env python3
"""R2a — Real↔Synthetic profiles: BlueZ link + Analyzer HOGP/FTMS on same ESP stub.

BlueZ often connects to the thin ESP peer without resolving GATT services.
We therefore MEASURE HID/FTMS via .88 analyzer flavors on the same stub, and
record BlueZ connect as host-capability FACT.

Usage:
  python3 tools/lab_r2_bluez_profiles.py
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
HOST = "192.168.178.88"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
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

    for path in ("/api/bt/disconnect", "/api/bt/advertise/stop", "/api/bt/scan/stop"):
        post(f"http://{args.peer}{path}")
        post(f"http://{HOST}{path}")
    time.sleep(0.3)
    st = get(f"http://{args.peer}/api/status")
    bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "r2-hid-ftms"})
    time.sleep(0.8)

    scan = ssh.scan(args.scan_s)
    seen = bd in (scan.get("addrs") or [])
    conn = ssh.connect(bd, timeout_s=35) if seen else {"ok": False, "error": "not_seen"}
    time.sleep(2.0)
    bluez_gatt = ssh.gatt_primary(bd) if conn.get("ok") else {"ok": False}
    ssh.disconnect(bd)
    time.sleep(0.8)

    # Analyzer path MEASURED HID+FTMS on same stub
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "r2-hid-ftms"})
    time.sleep(0.5)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": bd, "addrType": "0"})
    linked = False
    for _ in range(40):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            linked = True
            break
        time.sleep(0.25)
    analyzer = {"ok": False}
    if linked:
        post(f"http://{HOST}/api/bt/flavor/gatt/discover", {"mtu": "247"})
        fl = {}
        for _ in range(40):
            fl = get(f"http://{HOST}/api/status").get("flavor") or {}
            if fl.get("state") in ("ready", "error"):
                break
            time.sleep(0.25)
        svc = [str(s.get("uuid", "")).upper() for s in (fl.get("svc") or [])]
        has_hid = any(u.endswith("1812") for u in svc)
        has_ftms = any(u.endswith("1826") for u in svc)
        post(f"http://{HOST}/api/bt/flavor/hogp/start")
        time.sleep(2.0)
        hogp = get(f"http://{HOST}/api/status").get("hogp") or {}
        post(f"http://{HOST}/api/bt/flavor/ftms/start")
        time.sleep(2.0)
        ftms = get(f"http://{HOST}/api/status").get("ftms") or {}
        analyzer = {
            "ok": has_hid and has_ftms and fl.get("state") == "ready",
            "has_hid": has_hid,
            "has_ftms": has_ftms,
            "hogp_reports": hogp.get("reports"),
            "ftms_notifies": ftms.get("notifies"),
            "flavor_state": fl.get("state"),
        }

    for path in ("/api/bt/disconnect", "/api/bt/advertise/stop"):
        post(f"http://{HOST}{path}")
        post(f"http://{args.peer}{path}")

    ok = bool(seen and conn.get("ok") and analyzer.get("ok"))
    out = {
        "utc": utc,
        "gate": "R2a_bluez_profiles",
        "topology": "H_HOST_ORACLE+F_ONCHIP",
        "claim": "real_synth_bluez_link_plus_analyzer_hid_ftms",
        "peer_bd": bd,
        "bluez": {
            "seen": seen,
            "connect_ok": conn.get("ok"),
            "gatt_resolved": bool(bluez_gatt.get("has_hid") or bluez_gatt.get("has_ftms")),
            "gatt": bluez_gatt,
            "note": "thin ESP stub often leaves BlueZ GATT empty — not a FAIL if analyzer path green",
        },
        "analyzer": analyzer,
        "ok": ok,
        "classification": {
            "PC_BlueZ_can_connect_ESP_stub": conn.get("ok"),
            "Analyzer_resolves_HID_FTMS_on_stub": analyzer.get("ok"),
            "BlueZ_GATT_resolve": bool(bluez_gatt.get("has_hid")),
            "Air_sniffer": False,
        },
    }
    stem = f"LAB_R2_BLUEZ_PROFILES_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB R2a BlueZ Profiles — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · `{bd}`\n"
        f"- BlueZ connect: {conn.get('ok')}\n"
        f"- BlueZ GATT HID/FTMS: {bluez_gatt.get('has_hid')}/{bluez_gatt.get('has_ftms')}\n"
        f"- Analyzer HID+FTMS: {analyzer.get('ok')} reports={analyzer.get('hogp_reports')} "
        f"ftms={analyzer.get('ftms_notifies')}\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": ok,
                "stem": stem,
                "bluez_connect": conn.get("ok"),
                "analyzer_ok": analyzer.get("ok"),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
