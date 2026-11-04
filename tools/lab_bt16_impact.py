#!/usr/bin/env python3
"""BT16 analyzer-impact matrix — A–D × repeats × duration.

WiFi STA held constant (no BT13 toggles). Reports median/p10/p90 and Δ vs baseline.
Does NOT claim “analyzer makes it faster” from single-run noise.

Usage:
  python3 tools/lab_bt16_impact.py
  python3 tools/lab_bt16_impact.py --duration 60 --repeats 3
  python3 tools/lab_bt16_impact.py --quick
"""

from __future__ import annotations

import argparse
import json
import statistics
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
    time.sleep(0.6)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(3.5)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    for _ in range(30):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return
        time.sleep(0.3)
    raise RuntimeError("connect_failed")


def pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def sample_rate(duration: float) -> dict:
    vals = []
    peer_vals = []
    loss = []
    t0 = time.time()
    while time.time() - t0 < duration:
        time.sleep(1.0)
        h = get(f"http://{HOST}/api/status")
        p = get(f"http://{PEER}/api/status")
        oc = h.get("onchip") or {}
        poc = p.get("onchip") or {}
        rx = float(oc.get("appRxBps") or 0)
        tx = float(poc.get("appTxBps") or 0)
        vals.append(rx if rx > 1 else tx)
        peer_vals.append(tx)
        loss.append(int(oc.get("appSeqGaps") or oc.get("thrLoss") or 0))
    return {
        "median_Bps": statistics.median(vals) if vals else 0,
        "p10_Bps": pct(vals, 10),
        "p90_Bps": pct(vals, 90),
        "mean_Bps": statistics.mean(vals) if vals else 0,
        "stdev_Bps": statistics.pstdev(vals) if len(vals) > 1 else 0,
        "app_seq_gaps_end": loss[-1] if loss else 0,
        "peer_tx_median": statistics.median(peer_vals) if peer_vals else 0,
        "wifi_rssi": get(f"http://{HOST}/api/status").get("rssi"),
        "heap": get(f"http://{HOST}/api/status").get("heap"),
    }


def one_run(name: str, with_btac: bool, with_poll: bool, duration: float) -> dict:
    connect()
    proc = None
    if with_btac:
        out = EVIDENCE / f"_impact_{name}_{int(time.time())}.btac"
        proc = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tools" / "btac_recv.py"),
                HOST,
                "-n",
                "500000",
                "-o",
                str(out),
                "--idle",
                str(int(duration) + 5),
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
    post(f"http://{PEER}/api/bt/throughput/start", {"mode": "notify", "payload": "20", "mtu": "247"})
    post(f"http://{HOST}/api/bt/throughput/start", {"mode": "notify", "payload": "20", "mtu": "247"})
    time.sleep(2.0)
    if with_poll:
        end = time.time() + min(5.0, duration / 4)
        while time.time() < end:
            get(f"http://{HOST}/api/status")
            get(f"http://{PEER}/api/status")
            time.sleep(0.25)
    rates = sample_rate(duration)
    quiet()
    if proc:
        try:
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    rates.update(
        {
            "name": name,
            "with_btac": with_btac,
            "with_ui_poll": with_poll,
            "wifi_axis": "sta_connected_constant",
            "coex_note": "BT13 toggles not used",
            "duration_s": duration,
        }
    )
    return rates


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if args.quick:
        args.duration = 8.0
        args.repeats = 1

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    specs = [
        ("A_baseline_no_btac", False, False),
        ("B_ring_capture", False, False),
        ("C_capture_btac", True, False),
        ("D_capture_btac_ui_poll", True, True),
    ]
    cases = []
    for name, btac, poll in specs:
        runs = []
        for i in range(args.repeats):
            print(f"[impact] {name} {i+1}/{args.repeats}", flush=True)
            try:
                runs.append(one_run(name, btac, poll, args.duration))
            except Exception as exc:  # noqa: BLE001
                runs.append({"name": name, "error": str(exc), "median_Bps": 0})
        meds = [r.get("median_Bps") or 0 for r in runs]
        cases.append(
            {
                "name": name,
                "with_btac": btac,
                "with_ui_poll": poll,
                "repeats": args.repeats,
                "duration_s": args.duration,
                "median_of_medians_Bps": statistics.median(meds) if meds else 0,
                "p10_of_medians_Bps": pct(meds, 10),
                "p90_of_medians_Bps": pct(meds, 90),
                "stdev_of_medians_Bps": statistics.pstdev(meds) if len(meds) > 1 else 0,
                "runs": runs,
            }
        )

    base = cases[0]["median_of_medians_Bps"] or 1.0
    for c in cases:
        c["delta_pct_vs_A"] = round(100.0 * ((c["median_of_medians_Bps"] - base) / base), 2)
        c["note"] = (
            "delta within stdev → do not claim overhead"
            if abs(c["delta_pct_vs_A"]) < max(5.0, 100.0 * (c["stdev_of_medians_Bps"] / base))
            else "delta exceeds rough noise band — investigate"
        )

    out = {
        "utc": utc,
        "gate": "BT16_impact",
        "ok": True,
        "claim": "overhead_estimate_only_if_delta_gt_stdev",
        "wifi_axis": "sta_constant",
        "cases": cases,
    }
    stem = f"LAB_BT16_IMPACT_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB BT16 impact — {utc}",
        "",
        f"duration={args.duration}s × repeats={args.repeats}",
        "",
        "| case | median B/s | p10 | p90 | Δ% vs A | stdev | note |",
        "|------|------------|-----|-----|---------|-------|------|",
    ]
    for c in cases:
        lines.append(
            f"| {c['name']} | {c['median_of_medians_Bps']:.0f} | {c['p10_of_medians_Bps']:.0f} | "
            f"{c['p90_of_medians_Bps']:.0f} | {c['delta_pct_vs_A']} | {c['stdev_of_medians_Bps']:.0f} | {c['note']} |"
        )
    lines += ["", "WiFi STA constant. Do not interpret single-run +% as analyzer speedup.", ""]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "stem": stem, "summary": [{k: c[k] for k in ('name', 'median_of_medians_Bps', 'delta_pct_vs_A', 'note')} for c in cases]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
