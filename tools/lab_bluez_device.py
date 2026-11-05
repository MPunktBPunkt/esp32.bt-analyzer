#!/usr/bin/env python3
"""R1 foreign-device lab — BlueZ scan/pair/info/disconnect with evidence.

Works with ESP stand-in today; swap --addr for a real keyboard/headset when present.

Usage:
  python3 tools/lab_bluez_device.py --peer 192.168.178.89
  python3 tools/lab_bluez_device.py --addr AA:BB:CC:DD:EE:FF --no-esp
  python3 tools/lab_bluez_device.py --addr AA:BB:CC:DD:EE:FF --pair
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


def post(url: str, fields: dict | None = None) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            r.read()
    except Exception:  # noqa: BLE001
        pass


def load_ssh():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", ROOT / "tools" / "lab_bt_host_ssh.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--peer", default="192.168.178.89", help="ESP advertise stand-in")
    ap.add_argument("--addr", default="", help="foreign BD_ADDR (skips ESP advertise if set with --no-esp)")
    ap.add_argument("--no-esp", action="store_true", help="do not drive ESP advertise")
    ap.add_argument("--pair", action="store_true", help="attempt BlueZ pair/trust (optional)")
    ap.add_argument("--scan-s", type=float, default=8.0)
    ap.add_argument("--label", default="esp_standin", help="evidence peer label")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()

    fw = None
    bd = (args.addr or "").lower()
    if not args.no_esp:
        post(f"http://{args.peer}/api/bt/disconnect")
        st = get(f"http://{args.peer}/api/status")
        fw = st.get("fwVersion") or st.get("version")
        if not bd:
            bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
        try:
            ssh.disconnect(bd)
        except Exception:  # noqa: BLE001
            pass
        post(f"http://{args.peer}/api/bt/advertise/start", {"name": "bluez-dev"})
        time.sleep(0.7)
    if not bd:
        print(json.dumps({"ok": False, "error": "need --addr or ESP --peer"}, indent=2))
        return 1

    show = ssh.show()
    scan = ssh.scan(args.scan_s)
    seen = bd in (scan.get("addrs") or [])
    steps = [{"step": "scan", "ok": seen}]
    pair = {"ok": None, "skipped": True}
    if args.pair:
        pair = ssh.pair(bd)
        steps.append({"step": "pair", "ok": bool(pair.get("ok"))})
    conn = ssh.connect(bd, timeout_s=30) if seen else {"ok": False, "error": "not_seen"}
    steps.append({"step": "connect", "ok": bool(conn.get("ok"))})
    inf = ssh.info(bd) if conn.get("ok") else {}
    steps.append({"step": "info", "ok": bool(inf.get("ok") or inf.get("connected"))})
    disc = ssh.disconnect(bd) if conn.get("ok") else {"ok": True, "skipped": True}
    steps.append({"step": "disconnect", "ok": bool(disc.get("ok"))})

    soft_ok = all(s["ok"] for s in steps if s["step"] != "pair")
    out = {
        "utc": utc,
        "gate": "R1_bluez_device",
        "topology": "H_HOST_ORACLE",
        "claim": "bluez_host_device_path_not_air",
        "label": args.label if args.no_esp else "esp_standin",
        "addr": bd,
        "fw": fw,
        "show": {"ok": show.get("ok"), "controller": show.get("controller")},
        "steps": steps,
        "pair": pair,
        "info": {
            "connected": inf.get("connected"),
            "paired": inf.get("paired"),
            "uuids": inf.get("uuids"),
            "name": inf.get("name") or inf.get("alias"),
        },
        "ok": soft_ok,
        "note": "pair optional; soft_ok = scan/connect/info/disconnect",
    }
    stem = f"LAB_BLUEZ_DEVICE_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB BlueZ Device — {'PASS' if soft_ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · `{bd}` · label `{out['label']}`\n\n"
        + "\n".join(f"- {s['step']}: {s['ok']}" for s in steps)
        + "\n",
        encoding="utf-8",
    )
    if not args.no_esp:
        post(f"http://{args.peer}/api/bt/advertise/stop")
    print(json.dumps({"ok": soft_ok, "stem": stem, "addr": bd, "seen": seen}, indent=2))
    return 0 if soft_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
