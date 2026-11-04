#!/usr/bin/env python3
"""BT18 — GATT Client Flavor lab (STIMULUS over HCI, not Air).

Connects .88 → .89, runs service/char/descriptor discovery, optional CCCD
subscribe + Device Name read. Evidence: CAPABILITY vs discovery completeness.

Usage:
  python3 tools/lab_gatt_client.py
  python3 tools/lab_gatt_client.py --mtu 247
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


def get(url: str, timeout: float = 8.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None, timeout: float = 8.0) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode()
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            return {"raw": body}


def quiet() -> None:
    for ip in (HOST, PEER):
        for path in (
            "/api/bt/throughput/stop",
            "/api/bt/scan/stop",
            "/api/bt/advertise/stop",
            "/api/bt/disconnect",
        ):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def ensure_link() -> str:
    quiet()
    time.sleep(0.4)
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(0.8)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    deadline = time.time() + 12
    while time.time() < deadline:
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return peer_bd or ""
        time.sleep(0.3)
    raise RuntimeError("connect_failed")


def wait_flavor(timeout: float = 12.0) -> dict:
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout:
        st = get(f"http://{HOST}/api/status")
        fl = st.get("flavor") or {}
        last = fl
        state = fl.get("state")
        if state in ("ready", "error"):
            return fl
        time.sleep(0.25)
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mtu", type=int, default=23)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    peer_bd = ensure_link()
    post(f"http://{HOST}/api/bt/flavor/gatt/discover", {"mtu": str(args.mtu)})
    fl = wait_flavor(15.0)

    capability = fl.get("state") == "ready" and int(fl.get("services") or 0) >= 1
    has_gap = any(
        (s.get("uuid") or "").upper() in ("0X1800", "0x1800") for s in (fl.get("svc") or [])
    )
    # UUID may be "0x1800" from firmware
    if not has_gap:
        has_gap = any(
            str(s.get("uuid", "")).upper().endswith("1800") for s in (fl.get("svc") or [])
        )
    has_name_chr = int(fl.get("nameHandle") or 0) > 0
    has_cccd = int(fl.get("cccdHandle") or 0) > 0

    read_ok = False
    sub_ok = False
    gatt_name = None
    if capability and has_name_chr:
        post(f"http://{HOST}/api/bt/flavor/gatt/read", {"handle": str(fl.get("nameHandle"))})
        time.sleep(0.6)
        oc = get(f"http://{HOST}/api/status").get("onchip") or {}
        gatt_name = oc.get("gattName")
        read_ok = bool(gatt_name)
    if capability and has_cccd:
        post(
            f"http://{HOST}/api/bt/flavor/gatt/subscribe",
            {"cccd": str(fl.get("cccdHandle")), "enable": "1"},
        )
        time.sleep(0.4)
        fl2 = get(f"http://{HOST}/api/status").get("flavor") or {}
        sub_ok = int(fl2.get("stimulusTx") or 0) > int(fl.get("stimulusTx") or 0)
        fl = fl2

    benchmark = capability and has_gap and has_name_chr and has_cccd and read_ok

    out = {
        "utc": utc,
        "topology": "F_ONCHIP",
        "gate": "BT18",
        "flavor": "gatt_client",
        "claim": "STIMULUS_L2_over_HCI_not_air",
        "fw": "0.3.1",
        "peer_bd": peer_bd,
        "mtu": args.mtu,
        "flavor_status": fl,
        "gatt_name": gatt_name,
        "checks": {
            "capability": capability,
            "has_gap_service": has_gap,
            "has_name_char": has_name_chr,
            "has_cccd": has_cccd,
            "read_name_ok": read_ok,
            "subscribe_tx_ok": sub_ok,
            "benchmark": benchmark,
        },
        "capability_ok": capability,
        "benchmark_ok": benchmark,
        "ok": capability,
    }

    stem = f"LAB_BT18_GATT_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB BT18 GATT Client — capability={'PASS' if capability else 'FAIL'} · "
        f"benchmark={'PASS' if benchmark else 'FAIL'}",
        "",
        f"**UTC:** {utc} · **fw:** 0.3.1 · **mtu:** {args.mtu}",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        f"- state: `{fl.get('state')}`",
        f"- services: {fl.get('services')} · chars: {fl.get('characteristics')} · "
        f"descs: {fl.get('descriptors')}",
        f"- CCCD handle: {fl.get('cccdHandle')} · name handle: {fl.get('nameHandle')}",
        f"- stimulusTx/Rx: {fl.get('stimulusTx')}/{fl.get('stimulusRx')}",
        f"- gattName read: `{gatt_name}`",
        f"- subscribe TX bump: {sub_ok}",
        "",
        "Claim: **STIMULUS** L2 over HCI — not Air, not full GATT stack, not HOGP/FTMS.",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    quiet()
    print(json.dumps({"ok": capability, "benchmark_ok": benchmark, "stem": stem, "flavor": fl}, indent=2))
    return 0 if capability else 1


if __name__ == "__main__":
    raise SystemExit(main())
