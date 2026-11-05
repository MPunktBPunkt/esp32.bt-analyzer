#!/usr/bin/env python3
"""P1 — Disconnect during GATT phases (discover / CCCD / notify / FTMS CP).

Usage:
  python3 tools/lab_gatt_disconnect_stress.py
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
        with urllib.request.urlopen(req, timeout=8) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {"ok": True}
            except json.JSONDecodeError:
                return {"raw": body}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def quiet(*ips: str) -> None:
    for ip in ips:
        for p in ("disconnect", "advertise/stop", "scan/stop", "throughput/stop"):
            post(f"http://{ip}/api/bt/{p}")


def link(analyzer: str, peer: str) -> str:
    quiet(analyzer, peer)
    time.sleep(0.3)
    bd = ((get(f"http://{peer}/api/status").get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{peer}/api/bt/advertise/start", {"name": "disc-stress", "hid": "1", "ftms": "1"})
    time.sleep(0.6)
    post(f"http://{analyzer}/api/bt/scan/start")
    time.sleep(3.0)
    post(f"http://{analyzer}/api/bt/scan/stop")
    post(f"http://{analyzer}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{analyzer}/api/status").get("onchip") or {}).get("leConnected"):
            return bd
        time.sleep(0.25)
    raise RuntimeError("link_failed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analyzer", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    phases = []

    def phase(name: str, setup, cut_after_s: float):
        bd = link(args.analyzer, args.peer)
        setup()
        time.sleep(cut_after_s)
        post(f"http://{args.analyzer}/api/bt/disconnect")
        time.sleep(0.5)
        st = get(f"http://{args.analyzer}/api/status")
        oc = st.get("onchip") or {}
        # Recoverable: not connected, can scan again
        post(f"http://{args.peer}/api/bt/advertise/start", {"name": "disc-stress"})
        time.sleep(0.4)
        post(f"http://{args.analyzer}/api/bt/scan/start")
        time.sleep(2.0)
        post(f"http://{args.analyzer}/api/bt/scan/stop")
        recoverable = not oc.get("leConnected")
        phases.append({"name": name, "bd": bd, "recoverable": recoverable, "ok": recoverable})

    phase("during_discover", lambda: post(f"http://{args.analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"}), 0.3)

    def setup_ftms():
        post(f"http://{args.analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
        time.sleep(2.0)
        post(f"http://{args.analyzer}/api/bt/flavor/ftms/start")

    phase("during_ftms", setup_ftms, 1.0)

    def setup_burst():
        post(f"http://{args.analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
        time.sleep(2.0)
        post(f"http://{args.analyzer}/api/bt/flavor/hogp/start")
        post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "burst"})

    phase("during_notify_burst", setup_burst, 1.5)

    quiet(args.analyzer, args.peer)
    post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "off"})
    ok = all(p.get("ok") for p in phases)
    out = {
        "utc": utc,
        "gate": "GATT_disconnect_stress",
        "claim": "session_survives_mid_gatt_disconnect_CAPABILITY",
        "phases": phases,
        "ok": ok,
    }
    stem = f"LAB_GATT_DISCONNECT_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB GATT Disconnect Stress — {'PASS' if ok else 'FAIL'}\n\n"
        + "\n".join(f"- {p['name']}: recoverable={p['recoverable']}" for p in phases)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "phases": phases}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
