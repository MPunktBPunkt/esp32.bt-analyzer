#!/usr/bin/env python3
"""Simulate Auto-node capture: session on .89, BTAC drain from .89, stimulus from .88.

Models: Haus triggers capture on car ESP; local BT stays on .89; TCP only drains.

Usage:
  python3 tools/lab_capture_car_node.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
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
        with urllib.request.urlopen(req, timeout=10) as r:
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--car", default="192.168.178.89", help="capture node (Auto stand-in)")
    ap.add_argument("--stim", default="192.168.178.88", help="stimulus central")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--frames", type=int, default=400)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stem = f"LAB_CAPTURE_CAR_{utc}"
    btac_path = EVIDENCE / f"{stem}.btac"
    jsonl_path = EVIDENCE / f"{stem}.jsonl"
    btev_path = EVIDENCE / f"{stem}.btevent.jsonl"

    quiet(args.car, args.stim)
    time.sleep(0.4)
    car_bd = ((get(f"http://{args.car}/api/status").get("onchip") or {}).get("bdAddr") or "").lower()

    # Drain car node BTAC while house "remote-triggers" the session
    # Idle must cover scan/connect gaps — 3s previously dropped mid-session MARKs/STOP.
    recv = subprocess.Popen(
        [
            "python3",
            str(ROOT / "tools" / "btac_recv.py"),
            args.car,
            "-n",
            str(args.frames),
            "-o",
            str(btac_path),
            "--jsonl",
            str(jsonl_path),
            "--idle",
            "18",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.8)

    start = post(f"http://{args.car}/api/capture/session/start")
    post(f"http://{args.car}/api/capture/session/mark", {"label": "REMOTE_START"})
    post(f"http://{args.car}/api/bt/advertise/start", {"name": "car-89", "hid": "1", "ftms": "1"})
    time.sleep(0.6)

    # Stimulus from house central → car peripheral
    post(f"http://{args.stim}/api/bt/scan/start")
    time.sleep(2.5)
    post(f"http://{args.stim}/api/bt/scan/stop")
    post(f"http://{args.stim}/api/bt/connect", {"addr": car_bd, "addrType": "0"})
    for _ in range(48):
        if (get(f"http://{args.stim}/api/status").get("onchip") or {}).get("leConnected"):
            break
        time.sleep(0.25)

    post(f"http://{args.car}/api/capture/session/mark", {"label": "PEER_CONNECTED"})
    post(f"http://{args.stim}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    time.sleep(args.seconds)
    post(f"http://{args.car}/api/capture/session/mark", {"label": "GATT_DONE"})
    # Brief fault on car peer while session active
    post(f"http://{args.car}/api/bt/peer/fault", {"mode": "burst"})
    time.sleep(1.5)
    post(f"http://{args.car}/api/bt/peer/fault", {"mode": "off"})
    post(f"http://{args.car}/api/capture/session/mark", {"label": "FAULT_BURST_DONE"})
    stop = post(f"http://{args.car}/api/capture/session/stop")

    try:
        recv.wait(timeout=12)
    except subprocess.TimeoutExpired:
        recv.terminate()
        try:
            recv.wait(timeout=3)
        except subprocess.TimeoutExpired:
            recv.kill()

    quiet(args.car, args.stim)

    meta_n = hci_n = 0
    if btac_path.exists() and btac_path.stat().st_size > 0:
        m = subprocess.run(
            [
                "python3",
                str(ROOT / "tools" / "btac_to_btevent.py"),
                str(btac_path),
                "-o",
                str(btev_path),
                "--node-id",
                "89",
                "--stats",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        try:
            st = json.loads(m.stdout or "{}")
            meta_n = int(st.get("session_events") or 0)
            hci_n = int(st.get("frames") or 0)
        except json.JSONDecodeError:
            pass

    ok = bool(start.get("ok") and stop.get("ok") and meta_n >= 4 and hci_n >= meta_n)
    out = {
        "utc": utc,
        "gate": "CAPTURE_car_node",
        "topology": "car_89_stim_88_drain_tcp",
        "claim": "remote_trigger_local_bt_capture_not_proxy",
        "car": args.car,
        "stim": args.stim,
        "car_bd": car_bd,
        "session_start": start,
        "session_stop": stop,
        "btac_bytes": btac_path.stat().st_size if btac_path.exists() else 0,
        "hci_frames": hci_n,
        "session_meta_seen": meta_n,
        "ok": ok,
        "note": "Store-and-forward lite: BTAC TCP drain while capture local on car node",
    }
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB Capture Car Node — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · car `{args.car}` · stim `{args.stim}`\n\n"
        f"- sessionId={start.get('sessionId')} · meta={meta_n} · hci={hci_n}\n"
        f"- claim: remote trigger · local BT · not proxy\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "meta": meta_n, "hci": hci_n}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
