#!/usr/bin/env python3
"""P0 — MTU × payload matrix → ACL/L2CAP fragmentation counters (HCI plane).

Uses BT16 throughput notify path; records attMtu, aclFragStart/Cont, app gaps.

Usage:
  python3 tools/lab_l2cap_mtu_matrix.py
  python3 tools/lab_l2cap_mtu_matrix.py --quick
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
PEER = "192.168.178.89"

# Valid notify payloads for ATT MTU: value ≤ mtu-3; thr header uses 12 bytes
CELLS = [
    (23, 20),
    (64, 20),
    (64, 50),
    (128, 20),
    (128, 100),
    (247, 20),
    (247, 200),
    (247, 244),
]


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()


def quiet() -> None:
    for ip in (HOST, PEER):
        for p in ("throughput/stop", "scan/stop", "advertise/stop", "disconnect"):
            try:
                post(f"http://{ip}/api/bt/{p}")
            except Exception:  # noqa: BLE001
                pass


def ensure_link() -> str:
    quiet()
    time.sleep(0.4)
    bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "l2-mtu"})
    time.sleep(0.7)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(3.5)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return str(bd)
        time.sleep(0.25)
    raise RuntimeError("connect_failed")


def run_cell(mtu: int, payload: int, duration: float) -> dict:
    quiet()
    time.sleep(0.3)
    ensure_link()
    # MTU exchange from central; notify thr runs on peripheral (.89)
    post(f"http://{HOST}/api/bt/att/mtu", {"mtu": str(mtu)})
    time.sleep(0.5)
    st0 = get(f"http://{HOST}/api/status")
    oc0 = st0.get("onchip") or {}
    post(
        f"http://{PEER}/api/bt/throughput/start",
        {"mode": "notify", "payload": str(payload), "mtu": str(mtu), "pace_ms": "10"},
    )
    # Central enables thr RX path / CCCD via matching start on host write or peer notify subscribe
    post(
        f"http://{HOST}/api/bt/throughput/start",
        {"mode": "notify", "payload": str(payload), "mtu": str(mtu), "pace_ms": "10"},
    )
    time.sleep(duration)
    st1 = get(f"http://{HOST}/api/status")
    oc1 = st1.get("onchip") or {}
    st1p = get(f"http://{PEER}/api/status")
    oc1p = st1p.get("onchip") or {}
    post(f"http://{HOST}/api/bt/throughput/stop")
    post(f"http://{PEER}/api/bt/throughput/stop")
    frag_start = int(oc1.get("aclFragStart") or 0) - int(oc0.get("aclFragStart") or 0)
    frag_cont = int(oc1.get("aclFragCont") or 0) - int(oc0.get("aclFragCont") or 0)
    expect_frag = payload >= 100 or mtu >= 128
    rx = int(oc1.get("appRxPackets") or 0)
    tx_peer = int(oc1p.get("appTxPackets") or 0)
    ok = rx > 0 or tx_peer > 0
    return {
        "mtu": mtu,
        "payload": payload,
        "attMtu": oc1.get("attMtu"),
        "appTxPackets": oc1p.get("appTxPackets"),
        "appRxPackets": oc1.get("appRxPackets"),
        "appSeqGaps": oc1.get("appSeqGaps"),
        "aclFragStart_delta": frag_start,
        "aclFragCont_delta": frag_cont,
        "expect_frag_hint": expect_frag,
        "ok": ok,
        "claim": "CAPABILITY_L2CAP_ACL_fragment_observe",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=6.0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--host", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    args = ap.parse_args()
    global HOST, PEER
    HOST = args.host
    PEER = args.peer
    cells = CELLS[:3] if args.quick else CELLS
    dur = 3.0 if args.quick else args.duration
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    rows = []
    for mtu, payload in cells:
        try:
            rows.append(run_cell(mtu, payload, dur))
        except Exception as exc:  # noqa: BLE001
            rows.append({"mtu": mtu, "payload": payload, "ok": False, "error": str(exc)})
        quiet()
        time.sleep(0.5)

    ok = all(r.get("ok") for r in rows) and len(rows) == len(cells)
    out = {
        "utc": utc,
        "gate": "L2CAP_MTU_matrix",
        "claim": "HCI_ACL_L2CAP_fragmentation_CAPABILITY_not_air",
        "cells": rows,
        "ok": ok,
        "note": "Fragment counters are CAPABILITY/observe; controller ACL size dependent",
    }
    stem = f"LAB_L2CAP_MTU_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB L2CAP/MTU Matrix — {'PASS' if ok else 'FAIL'}",
        "",
        f"**UTC:** {utc}",
        "",
        "| mtu | payload | attMtu | tx | rx | fragStartΔ | fragContΔ | ok |",
        "|-----|---------|--------|----|----|------------|-----------|----|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('mtu')} | {r.get('payload')} | {r.get('attMtu')} | {r.get('appTxPackets')} | "
            f"{r.get('appRxPackets')} | {r.get('aclFragStart_delta')} | {r.get('aclFragCont_delta')} | {r.get('ok')} |"
        )
    lines.append("")
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    quiet()
    print(json.dumps({"ok": ok, "stem": stem, "n": len(rows)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
