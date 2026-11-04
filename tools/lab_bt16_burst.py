#!/usr/bin/env python3
"""BT16 burst — idle → short notify bursts → idle; capture drop/gap diagnostics.

Usage:
  python3 tools/lab_bt16_burst.py
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
HOST = "192.168.178.88"
PEER = "192.168.178.89"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        r.read()


def quiet() -> None:
    for ip in (HOST, PEER):
        for path in ("/api/bt/throughput/stop", "/api/bt/scan/stop", "/api/bt/advertise/stop", "/api/bt/disconnect"):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def ensure_link() -> None:
    quiet()
    time.sleep(0.3)
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "burst-89"})
    time.sleep(0.6)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return
        time.sleep(0.25)
    raise RuntimeError("connect_failed")


def snap() -> dict:
    h = get(f"http://{HOST}/api/status")
    oc = h.get("onchip") or {}
    cap = h.get("capture") or {}
    bt = h.get("btac") or {}
    return {
        "appRx": oc.get("appRxPackets"),
        "appTx": oc.get("appTxPackets"),
        "appRxBps": oc.get("appRxBps"),
        "dropsS": cap.get("droppedSession"),
        "fill": cap.get("fill"),
        "btacGapsS": bt.get("seqGapsSession"),
        "le": oc.get("leConnected"),
    }


def main() -> int:
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ensure_link()
    phases = []
    # idle
    time.sleep(2.0)
    phases.append({"phase": "idle0", **snap()})
    bursts = [10, 100]
    for n_hint in bursts:
        # start notify short burst (~ n_hint packets via duration)
        dur = max(1.5, n_hint * 0.02)
        post(f"http://{PEER}/api/bt/throughput/start", {"mode": "notify", "payload": "20", "mtu": "23", "pace_ms": "10"})
        post(f"http://{HOST}/api/bt/throughput/start", {"mode": "notify", "payload": "20", "mtu": "23", "pace_ms": "10"})
        time.sleep(dur)
        mid = snap()
        post(f"http://{HOST}/api/bt/throughput/stop")
        post(f"http://{PEER}/api/bt/throughput/stop")
        time.sleep(1.5)
        phases.append({"phase": f"burst_{n_hint}", "dur_s": dur, **mid})
        phases.append({"phase": f"idle_after_{n_hint}", **snap()})

    quiet()
    ok = all(p.get("le") for p in phases if p["phase"].startswith("burst")) and phases[-1].get("le")
    # also require some RX growth
    rx0 = int(phases[0].get("appRx") or 0)
    rx1 = int(phases[-2].get("appRx") or 0)
    ok = bool(ok and rx1 > rx0)
    out = {
        "utc": utc,
        "gate": "BT16_burst",
        "claim": "L2_ATT_burst_over_HCI_not_air",
        "phases": phases,
        "ok": ok,
    }
    stem = f"LAB_BT16_BURST_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB BT16 Burst — {'PASS' if ok else 'FAIL'}\n\n"
        + "\n".join(f"- {p['phase']}: appRx={p.get('appRx')} Bps={p.get('appRxBps')} dropsS={p.get('dropsS')}" for p in phases)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "rx0": rx0, "rx_last_burst": rx1}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
