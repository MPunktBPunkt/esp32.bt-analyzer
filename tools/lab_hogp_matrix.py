#!/usr/bin/env python3
"""P0 — HOGP matrix: Report Map, Input Report notifies, Output Report writes, sizes/burst.

Usage:
  python3 tools/lab_hogp_matrix.py
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {"ok": True}
            except json.JSONDecodeError:
                return {"raw": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            j = json.loads(body) if body else {}
        except json.JSONDecodeError:
            j = {"raw": body}
        j["ok"] = False
        return j
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def quiet(*ips: str) -> None:
    for ip in ips:
        for p in ("disconnect", "advertise/stop", "scan/stop", "throughput/stop"):
            post(f"http://{ip}/api/bt/{p}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analyzer", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    ap.add_argument("--listen-s", type=float, default=5.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    quiet(args.analyzer, args.peer)
    time.sleep(0.3)
    bd = ((get(f"http://{args.peer}/api/status").get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "hogp-mx", "hid": "1", "ftms": "1"})
    time.sleep(0.7)
    post(f"http://{args.analyzer}/api/bt/scan/start")
    time.sleep(3.0)
    post(f"http://{args.analyzer}/api/bt/scan/stop")
    post(f"http://{args.analyzer}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{args.analyzer}/api/status").get("onchip") or {}).get("leConnected"):
            break
        time.sleep(0.25)

    post(f"http://{args.analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    for _ in range(80):
        fl = get(f"http://{args.analyzer}/api/status").get("flavor") or {}
        if fl.get("state") == "ready":
            break
        time.sleep(0.25)

    post(f"http://{args.analyzer}/api/bt/flavor/hogp/start")
    hogp = {}
    for _ in range(40):
        time.sleep(0.25)
        hogp = get(f"http://{args.analyzer}/api/status").get("hogp") or {}
        if hogp.get("state") == "ready" and int(hogp.get("reports") or 0) >= 1:
            break

    map_ok = int(hogp.get("reportMapLen") or 0) >= 8
    input_ok = hogp.get("state") == "ready" and int(hogp.get("reports") or 0) >= 1

    # Output writes: 1 / 8 byte patterns
    outs = []
    for hexdata in ("02", "0000040000000000", "ffffffffffffffff"):
        before = int((get(f"http://{args.analyzer}/api/status").get("hogp") or {}).get("outputWrites") or 0)
        r = post(f"http://{args.analyzer}/api/bt/flavor/hogp/output", {"data": hexdata})
        time.sleep(0.3)
        after = int((get(f"http://{args.analyzer}/api/status").get("hogp") or {}).get("outputWrites") or 0)
        outs.append({"data": hexdata, "tx_ok": bool(r.get("ok")), "delta": after - before, "ok": after > before})

    # Burst: enable peer fault burst while listening
    post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "burst"})
    r0 = int((get(f"http://{args.analyzer}/api/status").get("hogp") or {}).get("reports") or 0)
    time.sleep(args.listen_s)
    r1 = int((get(f"http://{args.analyzer}/api/status").get("hogp") or {}).get("reports") or 0)
    post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "off"})
    burst_ok = (r1 - r0) >= 5

    # Soft reconnect while notifications
    post(f"http://{args.analyzer}/api/bt/disconnect")
    time.sleep(0.5)
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "hogp-mx", "hid": "1", "ftms": "1"})
    time.sleep(0.5)
    post(f"http://{args.analyzer}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{args.analyzer}/api/status").get("onchip") or {}).get("leConnected"):
            break
        time.sleep(0.25)
    post(f"http://{args.analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    for _ in range(60):
        if (get(f"http://{args.analyzer}/api/status").get("flavor") or {}).get("state") == "ready":
            break
        time.sleep(0.25)
    post(f"http://{args.analyzer}/api/bt/flavor/hogp/start")
    for _ in range(40):
        time.sleep(0.25)
        hogp2 = get(f"http://{args.analyzer}/api/status").get("hogp") or {}
        if hogp2.get("state") == "ready" and int(hogp2.get("reports") or 0) >= 1:
            break
    else:
        hogp2 = get(f"http://{args.analyzer}/api/status").get("hogp") or {}
    reconnect_ok = hogp2.get("state") == "ready" and int(hogp2.get("reports") or 0) >= 1

    ok = map_ok and input_ok and all(o["ok"] for o in outs) and burst_ok and reconnect_ok
    out = {
        "utc": utc,
        "gate": "HOGP_matrix",
        "claim": "STIMULUS_HOGP_over_HCI_not_air",
        "peer_bd": bd,
        "report_map_ok": map_ok,
        "report_map_len": hogp.get("reportMapLen"),
        "input_reports": hogp.get("reports"),
        "input_ok": input_ok,
        "output_writes": outs,
        "burst": {"delta": r1 - r0, "ok": burst_ok},
        "reconnect": {"ok": reconnect_ok, "reports": hogp2.get("reports")},
        "ok": ok,
    }
    stem = f"LAB_HOGP_MATRIX_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB HOGP Matrix — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc}\n\n"
        f"- Report Map: {map_ok} (len={hogp.get('reportMapLen')})\n"
        f"- Input reports: {input_ok} (n={hogp.get('reports')})\n"
        f"- Output writes: {sum(1 for o in outs if o['ok'])}/{len(outs)}\n"
        f"- Burst Δ: {r1 - r0}\n"
        f"- Reconnect: {reconnect_ok}\n",
        encoding="utf-8",
    )
    quiet(args.analyzer, args.peer)
    print(json.dumps({"ok": ok, "stem": stem}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
