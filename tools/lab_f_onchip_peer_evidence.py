#!/usr/bin/env python3
"""F_ONCHIP peer evidence: .89 advertises, .88 scans + BTAC capture → docs/evidence/.

Topology: F_ONCHIP (L1 onchip_vhci). Claim: HCI peer visibility + BTAC/JSONL path.
Not RF/Air FACT.

Usage:
  python3 tools/lab_f_onchip_peer_evidence.py
  python3 tools/lab_f_onchip_peer_evidence.py --host 192.168.178.88 --peer 192.168.178.89
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"


def http_json(url: str, timeout: float = 5.0) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def http_post(url: str, fields: dict[str, str] | None = None, timeout: float = 5.0) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode(errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="F_ONCHIP peer + BTAC evidence run")
    ap.add_argument("--host", default="192.168.178.88", help="Central / scanner (BTAC source)")
    ap.add_argument("--peer", default="192.168.178.89", help="Peripheral / advertiser")
    ap.add_argument("--name", default="bt-peer-89", help="Advertise Complete Local Name")
    ap.add_argument("--scan-s", type=float, default=8.0)
    ap.add_argument("--frames", type=int, default=64)
    args = ap.parse_args()

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"LAB_F_ONCHIP_PEER_{utc}"
    out_dir = EVIDENCE
    out_dir.mkdir(parents=True, exist_ok=True)
    btac_path = out_dir / f"{stem}.btac"
    jsonl_path = out_dir / f"{stem}.jsonl"
    meta_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    host_st = http_json(f"http://{args.host}/api/status")
    peer_st = http_json(f"http://{args.peer}/api/status")
    peer_bd = (peer_st.get("onchip") or {}).get("bdAddr")
    host_bd = (host_st.get("onchip") or {}).get("bdAddr")

    # Stop noise, then peer advertises, host scans.
    for ip in (args.host, args.peer):
        try:
            http_post(f"http://{ip}/api/bt/scan/stop")
            http_post(f"http://{ip}/api/bt/advertise/stop")
        except Exception:  # noqa: BLE001
            pass

    code, body = http_post(
        f"http://{args.peer}/api/bt/advertise/start",
        {"name": args.name},
    )
    if code != 200 or "true" not in body:
        print(f"advertise failed: {code} {body}", file=sys.stderr)
        return 1

    http_post(f"http://{args.host}/api/bt/scan/start")
    time.sleep(1.0)

    # BTAC receive while scanning
    recv = [
        sys.executable,
        str(ROOT / "tools" / "btac_recv.py"),
        args.host,
        "-n",
        str(args.frames),
        "-o",
        str(btac_path),
        "--jsonl",
        str(jsonl_path),
        "--idle",
        "6",
    ]
    proc = subprocess.run(recv, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    print(proc.stdout)
    if proc.returncode not in (0, 1):
        print(proc.stderr, file=sys.stderr)

    time.sleep(max(0.0, args.scan_s - 2.0))
    devices = http_json(f"http://{args.host}/api/bt/devices").get("devices") or []
    http_post(f"http://{args.host}/api/bt/scan/stop")
    http_post(f"http://{args.peer}/api/bt/advertise/stop")

    peer_seen = False
    matched = []
    for d in devices:
        addr = (d.get("addr") or "").lower()
        name = d.get("name") or ""
        hit = False
        if peer_bd and addr == str(peer_bd).lower():
            hit = True
        if args.name and args.name in name:
            hit = True
        if hit:
            peer_seen = True
            matched.append(d)

    # Decode stats (BT7)
    dec = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "btac_decode.py"),
            str(btac_path),
            "--stats",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        decode_stats = json.loads(dec.stdout) if dec.stdout.strip() else {}
    except json.JSONDecodeError:
        decode_stats = {"raw": dec.stdout, "stderr": dec.stderr}

    host_after = http_json(f"http://{args.host}/api/status")
    meta = {
        "topology": "F_ONCHIP",
        "claim_layer": "L1_onchip_vhci",
        "utc": utc,
        "host": {
            "ip": args.host,
            "version": host_st.get("version"),
            "bdAddr": host_bd,
            "role": "central_scan",
        },
        "peer": {
            "ip": args.peer,
            "version": peer_st.get("version"),
            "bdAddr": peer_bd,
            "role": "peripheral_advertise",
            "adv_name": args.name,
        },
        "peer_seen_on_host": peer_seen,
        "matched_devices": matched,
        "devices_total": len(devices),
        "btac": str(btac_path.relative_to(ROOT)),
        "jsonl": str(jsonl_path.relative_to(ROOT)),
        "decode": decode_stats,
        "btac_status": host_after.get("btac"),
        "capture": (host_after.get("capture")),
        "boundary": {
            "in_scope": ["HCI VHCI frames", "BLE peer advertise/scan", "BTAC→JSONL"],
            "out_of_scope": ["RF/Air FACT", "MITM", "Classic-on-S3"],
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    md = f"""# Lab F_ONCHIP peer — MEASURED

**Date (UTC):** {utc}
**Topology ID:** F_ONCHIP
**Firmware:** host `{args.host}` {host_st.get("version")} · peer `{args.peer}` {peer_st.get("version")}
**Raw:** [`{stem}.json`]({stem}.json) · [`{stem}.btac`]({stem}.btac) · [`{stem}.jsonl`]({stem}.jsonl)
**Repro:** `python3 tools/lab_f_onchip_peer_evidence.py`

Classification: **MEASURED** (this lab run).

## Claim boundary

| In scope | Out of scope |
|----------|----------------|
| L1 on-chip VHCI · BLE peer advertise/scan · BTAC/JSONL | RF / Air / MITM / Classic-on-S3 |

## Setup

| Item | Value |
|------|-------|
| Central (scan + BTAC) | `{args.host}` BD_ADDR `{host_bd}` |
| Peripheral (advertise) | `{args.peer}` BD_ADDR `{peer_bd}` name `{args.name}` |
| Capture | ESP `:9753` BTAC v1 → JSONL (BT4/BT7) |

## Results

| Metric | Value |
|--------|------:|
| peer_seen_on_host | `{peer_seen}` |
| devices_listed | {len(devices)} |
| btac_frames | {decode_stats.get("frames")} |
| btac_gaps | {decode_stats.get("gaps")} |
| crc_fail | {decode_stats.get("crc_fail")} |

Matched: `{json.dumps(matched)}`

## Epistemic notes

| Claim | Status |
|-------|--------|
| `.89` advertises; `.88` HCI scan lists peer | {"MEASURED" if peer_seen else "UNKNOWN / FAIL this run"} |
| BTAC stream decode → JSONL | {"MEASURED" if decode_stats.get("ok") else "PARTIAL"} |
| HCI = Air/RF | **REJECTED** |

## NEXT TEST

BT8 PCAPNG export · BT9 longer BLE connect · BT10 Classic on `.87` discoverable
"""
    md_path.write_text(md, encoding="utf-8")
    ok = bool(peer_seen) and bool(decode_stats.get("ok"))
    print(json.dumps({"ok": ok, "peer_seen": peer_seen, "meta": str(meta_path), "md": str(md_path)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(2)
