#!/usr/bin/env python3
"""Capture session under peer fault (burst/gap/drop) — recorder must keep meta+HCI.

Usage:
  python3 tools/lab_capture_fault.py
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
        post(f"http://{ip}/api/bt/peer/fault", {"mode": "off"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stem = f"LAB_CAPTURE_FAULT_{utc}"
    btac_path = EVIDENCE / f"{stem}.btac"
    jsonl_path = EVIDENCE / f"{stem}.jsonl"

    quiet(args.host, args.peer)
    time.sleep(0.3)
    bd = ((get(f"http://{args.peer}/api/status").get("onchip") or {}).get("bdAddr") or "").lower()

    recv = subprocess.Popen(
        [
            "python3",
            str(ROOT / "tools" / "btac_recv.py"),
            args.host,
            "-n",
            "500",
            "-o",
            str(btac_path),
            "--jsonl",
            str(jsonl_path),
            "--idle",
            "15",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.7)

    start = post(f"http://{args.host}/api/capture/session/start")
    post(f"http://{args.host}/api/capture/session/mark", {"label": "FAULT_RUN_START"})
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "cap-fault", "hid": "1", "ftms": "1"})
    time.sleep(0.5)
    post(f"http://{args.host}/api/bt/scan/start")
    time.sleep(2.0)
    post(f"http://{args.host}/api/bt/scan/stop")
    post(f"http://{args.host}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{args.host}/api/status").get("onchip") or {}).get("leConnected"):
            break
        time.sleep(0.25)

    post(f"http://{args.host}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    time.sleep(1.5)
    post(f"http://{args.host}/api/bt/flavor/hogp/start")
    time.sleep(0.8)

    phases = []
    for mode in ("burst", "gap", "slow"):
        post(f"http://{args.host}/api/capture/session/mark", {"label": f"FAULT_{mode.upper()}"})
        post(f"http://{args.peer}/api/bt/peer/fault", {"mode": mode})
        time.sleep(1.2)
        st = get(f"http://{args.host}/api/status")
        phases.append(
            {
                "mode": mode,
                "leConnected": (st.get("onchip") or {}).get("leConnected"),
                "session_active": (st.get("captureSession") or {}).get("active"),
            }
        )
    post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "off"})

    # Drop mode: peer disconnects after N notifies — session must still STOP cleanly
    post(f"http://{args.host}/api/capture/session/mark", {"label": "FAULT_DROP"})
    post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "drop", "after_n": "4"})
    time.sleep(3.0)
    post(f"http://{args.peer}/api/bt/peer/fault", {"mode": "off"})
    stop = post(f"http://{args.host}/api/capture/session/stop")

    try:
        recv.wait(timeout=12)
    except subprocess.TimeoutExpired:
        recv.terminate()
        try:
            recv.wait(timeout=3)
        except subprocess.TimeoutExpired:
            recv.kill()

    quiet(args.host, args.peer)

    meta_n = 0
    if btac_path.exists() and btac_path.stat().st_size > 0:
        m = subprocess.run(
            ["python3", str(ROOT / "tools" / "btac_to_btevent.py"), str(btac_path), "--stats", "--node-id", "88"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        try:
            meta_n = int(json.loads(m.stdout or "{}").get("session_events") or 0)
        except json.JSONDecodeError:
            pass

    ok = bool(start.get("ok") and stop.get("ok") and meta_n >= 4 and all(p.get("session_active") for p in phases))
    out = {
        "utc": utc,
        "gate": "CAPTURE_fault",
        "claim": "session_survives_peer_fault_modes",
        "phases": phases,
        "session_start": start,
        "session_stop": stop,
        "session_meta_seen": meta_n,
        "btac_bytes": btac_path.stat().st_size if btac_path.exists() else 0,
        "ok": ok,
    }
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB Capture Fault — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · meta={meta_n}\n\n"
        + "\n".join(f"- {p['mode']}: session_active={p['session_active']} le={p['leConnected']}" for p in phases)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "meta": meta_n, "phases": phases}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
