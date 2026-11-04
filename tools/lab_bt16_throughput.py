#!/usr/bin/env python3
"""BT16 — BLE ATT throughput lab (.88 central ↔ .89 peripheral).

Matrix v1: MTU 23/247 · payload 20/200 · notify + write · 10s.
Evidence: docs/evidence/LAB_BT16_<UTC>.*

Usage:
  python3 tools/lab_bt16_throughput.py
  python3 tools/lab_bt16_throughput.py --duration 10 --modes notify,write
"""

from __future__ import annotations

import argparse
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


def get(url: str, timeout: float = 8.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None, timeout: float = 8.0) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode(errors="replace")


def quiet(*ips: str) -> None:
    for ip in ips:
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
    quiet(HOST, PEER)
    time.sleep(0.3)
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(0.8)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    if peer_bd:
        post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    deadline = time.time() + 10
    while time.time() < deadline:
        oc = get(f"http://{HOST}/api/status").get("onchip") or {}
        if oc.get("leConnected"):
            return peer_bd or ""
        time.sleep(0.3)
    raise RuntimeError("connect_failed")


def sample_rates(duration: float) -> dict:
    t0 = time.time()
    host0 = get(f"http://{HOST}/api/status")
    peer0 = get(f"http://{PEER}/api/status")
    samples = []
    while time.time() - t0 < duration:
        time.sleep(1.0)
        h = get(f"http://{HOST}/api/status")
        p = get(f"http://{PEER}/api/status")
        samples.append(
            {
                "t": round(time.time() - t0, 2),
                "host": {
                    "appTxBps": (h.get("onchip") or {}).get("appTxBps"),
                    "appRxBps": (h.get("onchip") or {}).get("appRxBps"),
                    "aclTxBps": (h.get("hciCapture") or {}).get("aclTxBps"),
                    "aclRxBps": (h.get("hciCapture") or {}).get("aclRxBps"),
                    "fwdBps": (h.get("btac") or {}).get("fwdBps"),
                    "thrLoss": (h.get("onchip") or {}).get("thrLoss"),
                },
                "peer": {
                    "appTxBps": (p.get("onchip") or {}).get("appTxBps"),
                    "appRxBps": (p.get("onchip") or {}).get("appRxBps"),
                    "aclTxBps": (p.get("hciCapture") or {}).get("aclTxBps"),
                    "aclRxBps": (p.get("hciCapture") or {}).get("aclRxBps"),
                },
            }
        )
    host1 = get(f"http://{HOST}/api/status")
    peer1 = get(f"http://{PEER}/api/status")

    def avg(key_path: str, side: str) -> float:
        vals = []
        for s in samples:
            node = s[side]
            v = node.get(key_path)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "duration_s": duration,
        "samples": samples,
        "avg_host_appTxBps": avg("appTxBps", "host"),
        "avg_host_appRxBps": avg("appRxBps", "host"),
        "avg_host_aclTxBps": avg("aclTxBps", "host"),
        "avg_host_aclRxBps": avg("aclRxBps", "host"),
        "avg_host_fwdBps": avg("fwdBps", "host"),
        "host_appTxBytes": (host1.get("onchip") or {}).get("appTxBytes"),
        "host_appRxBytes": (host1.get("onchip") or {}).get("appRxBytes"),
        "peer_appTxBytes": (peer1.get("onchip") or {}).get("appTxBytes"),
        "peer_appRxBytes": (peer1.get("onchip") or {}).get("appRxBytes"),
        "thrLoss": (host1.get("onchip") or {}).get("thrLoss"),
        "thrReorder": (host1.get("onchip") or {}).get("thrReorder"),
        "attMtu_host": (host1.get("onchip") or {}).get("attMtu"),
        "attMtu_peer": (peer1.get("onchip") or {}).get("attMtu"),
        "connected": bool((host1.get("onchip") or {}).get("leConnected")),
        "versions": {
            HOST: host0.get("version"),
            PEER: peer0.get("version"),
        },
    }


def run_case(mode: str, mtu: int, payload: int, duration: float, capture: bool) -> dict:
    quiet(HOST, PEER)
    ensure_link()
    btac_path = None
    recv = None
    if capture:
        btac_path = EVIDENCE / f"_bt16_tmp_{mode}_{mtu}_{payload}.btac"
        recv = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tools" / "btac_recv.py"),
                HOST,
                "-n",
                "5000",
                "-o",
                str(btac_path),
                "--idle",
                str(max(2, int(duration) + 2)),
            ],
            cwd=str(ROOT),
        )
        time.sleep(0.5)

    # Peer peripheral notify source; host central receives (or write flood from host)
    if mode == "notify":
        post(f"http://{PEER}/api/bt/throughput/start", {"mode": "notify", "payload": str(payload), "mtu": str(mtu)})
        post(f"http://{HOST}/api/bt/throughput/start", {"mode": "notify", "payload": str(payload), "mtu": str(mtu)})
    else:
        post(f"http://{PEER}/api/bt/throughput/start", {"mode": "write", "payload": str(payload), "mtu": str(mtu)})
        post(f"http://{HOST}/api/bt/throughput/start", {"mode": "write", "payload": str(payload), "mtu": str(mtu)})

    rates = sample_rates(duration)
    quiet(HOST, PEER)
    file_gaps = None
    if recv:
        try:
            recv.wait(timeout=duration + 15)
        except Exception:  # noqa: BLE001
            recv.kill()
        if btac_path and btac_path.is_file():
            dec = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "btac_decode.py"), str(btac_path), "--stats"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            try:
                file_gaps = int(json.loads(dec.stdout).get("gaps") or 0)
            except json.JSONDecodeError:
                file_gaps = -1
    rates["mode"] = mode
    rates["mtu"] = mtu
    rates["payload"] = payload
    rates["capture"] = capture
    rates["file_gaps"] = file_gaps
    rates["ok"] = bool(rates.get("connected")) and (
        (rates.get("avg_host_appTxBps") or 0) > 0 or (rates.get("avg_host_appRxBps") or 0) > 0
    )
    return rates


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--modes", default="notify,write")
    ap.add_argument("--mtus", default="23,247")
    ap.add_argument("--payloads", default="20,200")
    ap.add_argument("--no-capture", action="store_true")
    args = ap.parse_args()

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    mtus = [int(x) for x in args.mtus.split(",") if x.strip()]
    payloads = [int(x) for x in args.payloads.split(",") if x.strip()]

    results = {
        "utc": utc,
        "topology": "F_ONCHIP",
        "gate": "BT16",
        "claim": "L2_ATT_throughput_over_HCI_not_air",
        "cases": [],
    }
    for mode in modes:
        for mtu in mtus:
            for payload in payloads:
                # Skip oversized value vs MTU (opcode+handle+value)
                if payload + 3 > mtu:
                    continue
                print(f"[bt16] case mode={mode} mtu={mtu} payload={payload}", flush=True)
                try:
                    case = run_case(mode, mtu, payload, args.duration, not args.no_capture)
                except Exception as exc:  # noqa: BLE001
                    case = {"ok": False, "mode": mode, "mtu": mtu, "payload": payload, "error": str(exc)}
                results["cases"].append(case)

    results["ok"] = any(bool(c.get("ok")) for c in results["cases"])
    stem = f"LAB_BT16_{utc}"
    meta = EVIDENCE / f"{stem}.json"
    md = EVIDENCE / f"{stem}.md"
    meta.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB BT16 throughput — {'PASS' if results['ok'] else 'PARTIAL'}",
        "",
        f"**UTC:** {utc}",
        "**Topology:** F_ONCHIP (.88 central ↔ .89 peripheral)",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        "| mode | mtu | payload | appTx B/s | appRx B/s | hciTx | hciRx | btac | loss | file_gaps | ok |",
        "|------|-----|---------|-----------|-----------|-------|-------|------|------|-----------|----|",
    ]
    for c in results["cases"]:
        lines.append(
            f"| {c.get('mode')} | {c.get('mtu')} | {c.get('payload')} | "
            f"{c.get('avg_host_appTxBps', 0):.0f} | {c.get('avg_host_appRxBps', 0):.0f} | "
            f"{c.get('avg_host_aclTxBps', 0):.0f} | {c.get('avg_host_aclRxBps', 0):.0f} | "
            f"{c.get('avg_host_fwdBps', 0):.0f} | {c.get('thrLoss')} | {c.get('file_gaps')} | {c.get('ok')} |"
        )
    lines += ["", "## Claim", "L2 ATT over HCI ACL only — not RF/Air FACT.", ""]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    quiet(HOST, PEER)
    print(json.dumps({"ok": results["ok"], "meta": str(meta), "cases": len(results["cases"])}, indent=2))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
