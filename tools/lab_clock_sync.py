#!/usr/bin/env python3
"""Clock-offset estimation (NOT PTP / NOT shared clock).

Polls /api/lab/sync-marker; reports offset, RTT, jitter, uncertainty.

Claims:
  PTP: NO
  shared_clock: NO
  estimated_timeline_alignment: YES

Usage:
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
NODES = {"88": "192.168.178.88", "89": "192.168.178.89", "87": "192.168.178.87"}


def fetch_marker(ip: str) -> dict:
    t_before = time.time()
    with urllib.request.urlopen(f"http://{ip}/api/lab/sync-marker", timeout=3) as r:
        body = json.loads(r.read().decode())
    t_after = time.time()
    rtt = t_after - t_before
    mid = (t_before + t_after) / 2.0
    mono_us = int(body.get("mono_us") or 0)
    return {
        "ip": ip,
        "mono_us": mono_us,
        "millis": body.get("millis"),
        "debian_unix_mid": mid,
        "rtt_s": rtt,
        "offset_s": mid - (mono_us / 1_000_000.0),
        "uncertainty_s": rtt / 2.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=20)
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
        time.sleep(0.15)

    offsets = {}
    for name, rows in samples.items():
        ok = [r for r in rows if "offset_s" in r]
        if not ok:
            offsets[name] = {"ok": False, "errors": [r.get("error") for r in rows if r.get("error")]}
            continue
        ok.sort(key=lambda r: r["rtt_s"])
        best = ok[: max(5, len(ok) // 2)]
        offs = [r["offset_s"] for r in best]
        rtts = [r["rtt_s"] * 1000 for r in best]
        uncs = [r["uncertainty_s"] * 1000 for r in best]
        offsets[name] = {
            "ok": True,
            "offset_s_median": statistics.median(offs),
            "offset_s_stdev": statistics.pstdev(offs) if len(offs) > 1 else 0.0,
            "rtt_ms_median": statistics.median(rtts),
            "rtt_ms_jitter": statistics.pstdev(rtts) if len(rtts) > 1 else 0.0,
            "uncertainty_ms_median": statistics.median(uncs),
            "sample_count": len(ok),
            "best_count": len(best),
        }

    skew = {}
    names = [n for n, o in offsets.items() if o.get("ok")]
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            skew[f"{a}-{b}"] = {
                "skew_s": offsets[a]["offset_s_median"] - offsets[b]["offset_s_median"],
            }

    out = {
        "utc": utc,
        "gate": "BT_clock_offset_estimation",
        "method": "http_sync_marker_rtt_midpoint",
        "claims": {
            "PTP": False,
            "shared_clock": False,
            "estimated_timeline_alignment": True,
        },
        "rounds": args.rounds,
        "offsets": offsets,
        "pairwise_skew_s": skew,
        "ok": all(o.get("ok") for o in offsets.values()),
    }
    stem = f"LAB_CLOCK_SYNC_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB clock-offset estimation — {utc}",
        "",
        "**PTP: NO · shared clock: NO · estimated timeline alignment: YES**",
        "",
        "| node | offset_s | stdev | rtt_ms | jitter_ms | uncertainty_ms | n |",
        "|------|----------|-------|--------|-----------|----------------|---|",
    ]
    for name, o in offsets.items():
        if not o.get("ok"):
            lines.append(f"| .{name} | — | — | — | — | — | 0 |")
        else:
            lines.append(
                f"| .{name} | {o['offset_s_median']:.6f} | {o['offset_s_stdev']:.6f} | "
                f"{o['rtt_ms_median']:.2f} | {o['rtt_ms_jitter']:.2f} | {o['uncertainty_ms_median']:.2f} | {o['sample_count']} |"
            )
    lines += ["", "Use for BT19 multi-node timeline alignment only.", ""]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": out["ok"], "stem": stem, "claims": out["claims"], "offsets": {k: v.get("offset_s_median") for k, v in offsets.items()}}, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
