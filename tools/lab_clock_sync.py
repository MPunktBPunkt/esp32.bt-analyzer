#!/usr/bin/env python3
"""Multi-node clock sync markers (P1 mini-gate before correlation).

Polls /api/lab/sync-marker on .88/.89/.87 and Debian wall clock to estimate
offsets. Not PTP — good enough for HU↔Phone event correlation (±ms..tens ms).

Usage:
  python3 tools/lab_clock_sync.py
  python3 tools/lab_clock_sync.py --rounds 20
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
NODES = {
    "88": "192.168.178.88",
    "89": "192.168.178.89",
    "87": "192.168.178.87",
}


def fetch_marker(ip: str) -> dict:
    t_before = time.time()
    with urllib.request.urlopen(f"http://{ip}/api/lab/sync-marker", timeout=3) as r:
        body = json.loads(r.read().decode())
    t_after = time.time()
    rtt = t_after - t_before
    debian_mid = (t_before + t_after) / 2.0
    mono_us = int(body.get("mono_us") or 0)
    # Estimate: node_mono ≈ debian_mid (wall) mapped via offset
    return {
        "ip": ip,
        "mono_us": mono_us,
        "millis": body.get("millis"),
        "debian_unix": debian_mid,
        "rtt_s": rtt,
        "raw": body,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=10)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    samples: dict[str, list[dict]] = {k: [] for k in NODES}
    for _ in range(args.rounds):
        for name, ip in NODES.items():
            try:
                samples[name].append(fetch_marker(ip))
            except Exception as exc:  # noqa: BLE001
                samples[name].append({"ip": ip, "error": str(exc)})
        time.sleep(0.2)

    # Offset estimate: debian_unix - mono_us/1e6  (seconds); use median RTT/2 samples
    offsets = {}
    for name, rows in samples.items():
        ok = [r for r in rows if "mono_us" in r and r.get("mono_us")]
        if not ok:
            offsets[name] = {"ok": False}
            continue
        # Prefer low-RTT samples
        ok.sort(key=lambda r: r.get("rtt_s") or 9)
        best = ok[: max(3, len(ok) // 2)]
        offs = [r["debian_unix"] - (r["mono_us"] / 1_000_000.0) for r in best]
        offsets[name] = {
            "ok": True,
            "offset_s_median": statistics.median(offs),
            "offset_s_stdev": statistics.pstdev(offs) if len(offs) > 1 else 0.0,
            "rtt_ms_median": statistics.median([r["rtt_s"] * 1000 for r in best]),
            "samples": len(ok),
        }

    # Pairwise node skew via debian bridge
    skew = {}
    names = [n for n, o in offsets.items() if o.get("ok")]
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            skew[f"{a}-{b}"] = {
                "skew_s": offsets[a]["offset_s_median"] - offsets[b]["offset_s_median"],
                "note": "positive => a’s mono lags b relative to debian mapping",
            }

    out = {
        "utc": utc,
        "gate": "BT_clock_sync",
        "method": "http_sync_marker_rtt_midpoint",
        "rounds": args.rounds,
        "offsets": offsets,
        "pairwise_skew_s": skew,
        "ok": all(o.get("ok") for o in offsets.values()),
        "claim": "MEASURED_offset_estimate_not_PTP",
    }
    stem = f"LAB_CLOCK_SYNC_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB clock sync — {utc}",
        "",
        "| node | offset_s median | stdev | rtt_ms | ok |",
        "|------|-----------------|-------|--------|----|",
    ]
    for name, o in offsets.items():
        if not o.get("ok"):
            lines.append(f"| .{name} | — | — | — | False |")
        else:
            lines.append(
                f"| .{name} | {o['offset_s_median']:.6f} | {o['offset_s_stdev']:.6f} | "
                f"{o['rtt_ms_median']:.1f} | True |"
            )
    lines += ["", "Not PTP. Use for multi-node timeline correlation (±RTT).", ""]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": out["ok"], "stem": stem, "offsets": {k: v.get("offset_s_median") for k, v in offsets.items()}}, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
