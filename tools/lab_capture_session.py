#!/usr/bin/env python3
"""0.3.9 — Capture session START/MARK/STOP + HCI activity + BT_EVENT map.

Starts BTAC recv first (so the ring drains live), then session control + LE traffic.

Usage:
  python3 tools/lab_capture_session.py
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
    ap.add_argument("--host", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--frames", type=int, default=400)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stem = f"LAB_CAPTURE_SESSION_{utc}"
    btac_path = EVIDENCE / f"{stem}.btac"
    jsonl_path = EVIDENCE / f"{stem}.jsonl"
    btev_path = EVIDENCE / f"{stem}.btevent.jsonl"

    quiet(args.host, args.peer)
    time.sleep(0.4)
    bd = ((get(f"http://{args.peer}/api/status").get("onchip") or {}).get("bdAddr") or "").lower()

    # Live drain while session runs
    recv_proc = subprocess.Popen(
        [
            "python3",
            str(ROOT / "tools" / "btac_recv.py"),
            args.host,
            "-n",
            str(args.frames),
            "-o",
            str(btac_path),
            "--jsonl",
            str(jsonl_path),
            "--idle",
            "3",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(0.8)

    start = post(f"http://{args.host}/api/capture/session/start")
    sid = start.get("sessionId")
    post(f"http://{args.host}/api/capture/session/mark", {"label": "APP_START"})

    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "cap-sess", "hid": "1", "ftms": "1"})
    time.sleep(0.5)
    post(f"http://{args.host}/api/bt/scan/start")
    time.sleep(2.0)
    post(f"http://{args.host}/api/bt/scan/stop")
    post(f"http://{args.host}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{args.host}/api/status").get("onchip") or {}).get("leConnected"):
            break
        time.sleep(0.25)

    post(f"http://{args.host}/api/capture/session/mark", {"label": "LE_CONNECTED"})
    post(f"http://{args.host}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    time.sleep(args.seconds)
    post(f"http://{args.host}/api/capture/session/mark", {"label": "GATT_DISCOVER"})
    stop = post(f"http://{args.host}/api/capture/session/stop")

    # Allow idle flush
    try:
        recv_proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        recv_proc.terminate()
        try:
            recv_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            recv_proc.kill()

    quiet(args.host, args.peer)

    meta_n = 0
    hci_n = 0
    if btac_path.exists() and btac_path.stat().st_size > 0:
        m = subprocess.run(
            [
                "python3",
                str(ROOT / "tools" / "btac_to_btevent.py"),
                str(btac_path),
                "-o",
                str(btev_path),
                "--node-id",
                "88",
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

    ok = bool(start.get("ok") and stop.get("ok") and sid and meta_n >= 3 and hci_n >= meta_n)
    out = {
        "utc": utc,
        "gate": "CAPTURE_session",
        "claim": "HCI_session_recorder_not_air",
        "session_start": start,
        "session_stop": stop,
        "btac_bytes": btac_path.stat().st_size if btac_path.exists() else 0,
        "hci_frames": hci_n,
        "session_meta_seen": meta_n,
        "ok": ok,
        "artifacts": {
            "btac": str(btac_path.relative_to(ROOT)),
            "jsonl": str(jsonl_path.relative_to(ROOT)),
            "btevent": str(btev_path.relative_to(ROOT)) if btev_path.exists() else None,
        },
        "note": "Recorder foundation — Classic SDP/AVRCP decode deferred until BMW/AAIdrive run",
    }
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB Capture Session — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · sessionId={sid} · marks={stop.get('markCount')}\n\n"
        f"- HCI frames: {hci_n}\n- session meta: {meta_n}\n- BTAC bytes: {out['btac_bytes']}\n\n"
        "See [`CAPTURE_SESSION.md`](../CAPTURE_SESSION.md).\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "sessionId": sid, "meta": meta_n, "hci": hci_n}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
