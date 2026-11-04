#!/usr/bin/env python3
"""BT16 analyzer-impact matrix with WiFi/coex as a separate axis.

Runs short notify throughput under four capture loads; WiFi load is constant
(STA connected) — do not toggle scan/adv during the window (avoids BT13 confound).

Modes:
  A baseline_no_btac   — throughput, no BTAC client
  B ring_only          — same (ring always on); documented as capture-on
  C capture_btac       — + BTAC TCP drain
  D capture_btac_ui    — + status polling (UI-like)

Usage:
  python3 tools/lab_bt16_impact.py
"""

from __future__ import annotations

import json
import subprocess
import sys
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
        for path in ("/api/bt/throughput/stop", "/api/bt/disconnect", "/api/bt/scan/stop", "/api/bt/advertise/stop"):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def connect() -> None:
    quiet()
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(0.5)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(3.5)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    for _ in range(25):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return
        time.sleep(0.3)
    raise RuntimeError("connect_failed")


def avg_app(duration: float = 8.0) -> dict:
    vals_tx, vals_rx = [], []
    t0 = time.time()
    while time.time() - t0 < duration:
        time.sleep(1.0)
        oc = get(f"http://{HOST}/api/status").get("onchip") or {}
        vals_tx.append(float(oc.get("appTxBps") or 0))
        vals_rx.append(float(oc.get("appRxBps") or 0))
    return {
        "avg_appTxBps": sum(vals_tx) / len(vals_tx) if vals_tx else 0,
        "avg_appRxBps": sum(vals_rx) / len(vals_rx) if vals_rx else 0,
        "wifi_rssi": get(f"http://{HOST}/api/status").get("rssi"),
        "heap": get(f"http://{HOST}/api/status").get("heap"),
    }


def run_load(name: str, with_btac: bool, with_poll: bool) -> dict:
    connect()
    proc = None
    if with_btac:
        out = EVIDENCE / f"_impact_{name}.btac"
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "btac_recv.py"), HOST, "-n", "8000", "-o", str(out), "--idle", "12"],
            cwd=str(ROOT),
        )
        time.sleep(0.4)
    post(f"http://{PEER}/api/bt/throughput/start", {"mode": "notify", "payload": "20", "mtu": "247"})
    post(f"http://{HOST}/api/bt/throughput/start", {"mode": "notify", "payload": "20", "mtu": "247"})
    # Allow MTU/CCCD + first notify window before measuring.
    time.sleep(2.0)
    if not (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
        raise RuntimeError(f"{name}: lost connection before sample")
    if with_poll:
        poller_stop = time.time() + 5
        while time.time() < poller_stop:
            get(f"http://{HOST}/api/status")
            get(f"http://{PEER}/api/status")
            time.sleep(0.25)
        rates = avg_app(5.0)
    else:
        rates = avg_app(8.0)
    # Prefer whichever direction is active (notify → host RX / peer TX).
    peer_tx = float((get(f"http://{PEER}/api/status").get("onchip") or {}).get("appTxBps") or 0)
    rates["peer_appTxBps_end"] = peer_tx
    if (rates.get("avg_appRxBps") or 0) < 1 and peer_tx > 0:
        rates["avg_appRxBps"] = peer_tx
    quiet()
    if proc:
        try:
            proc.wait(timeout=20)
        except Exception:  # noqa: BLE001
            proc.kill()
    rates["name"] = name
    rates["with_btac"] = with_btac
    rates["with_ui_poll"] = with_poll
    rates["wifi_axis"] = "sta_connected_constant"
    rates["coex_note"] = "BT13 toggles not used during window"
    return rates


def main() -> int:
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    cases = [
        run_load("A_baseline_no_btac", False, False),
        run_load("B_ring_capture", False, False),
        run_load("C_capture_btac", True, False),
        run_load("D_capture_btac_ui_poll", True, True),
    ]
    base = cases[0].get("avg_appRxBps") or cases[0].get("avg_appTxBps") or 1.0
    for c in cases:
        rate = c.get("avg_appRxBps") or c.get("avg_appTxBps") or 0.0
        c["relative_pct"] = round(100.0 * rate / base, 1) if base else None
    out = {
        "utc": utc,
        "gate": "BT16_impact",
        "ok": True,
        "cases": cases,
        "note": "WiFi STA held constant; relative_pct vs case A",
    }
    stem = f"LAB_BT16_IMPACT_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB BT16 analyzer impact — {utc}",
        "",
        "| case | appTx | appRx | relative% | btac | ui_poll | rssi |",
        "|------|-------|-------|-----------|------|---------|------|",
    ]
    for c in cases:
        lines.append(
            f"| {c['name']} | {c.get('avg_appTxBps', 0):.0f} | {c.get('avg_appRxBps', 0):.0f} | "
            f"{c.get('relative_pct')} | {c.get('with_btac')} | {c.get('with_ui_poll')} | {c.get('wifi_rssi')} |"
        )
    lines += ["", "WiFi/coex axis: STA connected, no BT13 toggles in window.", ""]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "stem": stem, "cases": [{k: c.get(k) for k in ('name', 'relative_pct', 'avg_appRxBps')} for c in cases]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
