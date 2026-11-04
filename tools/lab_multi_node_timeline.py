#!/usr/bin/env python3
"""BT19 — multi-node timeline using clock-offset estimation.

Collects sync markers + status samples from .88/.89/.87 into one JSONL with
debian_unix timestamps. Not PTP / not shared clock — estimated alignment only.

Usage:
  python3 tools/lab_multi_node_timeline.py --seconds 20
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


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=4) as r:
        return json.loads(r.read().decode())


def fetch_marker(ip: str) -> dict:
    t_before = time.time()
    body = get_json(f"http://{ip}/api/lab/sync-marker")
    t_after = time.time()
    rtt = t_after - t_before
    mid = (t_before + t_after) / 2.0
    mono_us = int(body.get("mono_us") or 0)
    return {
        "mono_us": mono_us,
        "rtt_s": rtt,
        "offset_s": mid - (mono_us / 1_000_000.0),
        "uncertainty_s": rtt / 2.0,
    }


def estimate_offsets(rounds: int = 12) -> dict:
    samples: dict[str, list[dict]] = {k: [] for k in NODES}
    for _ in range(rounds):
        for name, ip in NODES.items():
            try:
                samples[name].append(fetch_marker(ip))
            except Exception as exc:  # noqa: BLE001
                samples[name].append({"error": str(exc)})
        time.sleep(0.1)

    out = {}
    for name, rows in samples.items():
        ok = [r for r in rows if "offset_s" in r]
        if not ok:
            out[name] = {"ok": False, "errors": [r.get("error") for r in rows if r.get("error")]}
            continue
        ok.sort(key=lambda r: r["rtt_s"])
        best = ok[: max(5, len(ok) // 2)]
        offs = [r["offset_s"] for r in best]
        rtts = [r["rtt_s"] * 1000 for r in best]
        uncs = [r["uncertainty_s"] * 1000 for r in best]
        out[name] = {
            "ok": True,
            "offset_s_median": statistics.median(offs),
            "offset_s_stdev": statistics.pstdev(offs) if len(offs) > 1 else 0.0,
            "rtt_ms_median": statistics.median(rtts),
            "rtt_ms_jitter": statistics.pstdev(rtts) if len(rtts) > 1 else 0.0,
            "uncertainty_ms_median": statistics.median(uncs),
            "sample_count": len(ok),
            "best_count": len(best),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--offset-rounds", type=int, default=12)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    offsets = estimate_offsets(args.offset_rounds)
    skew = {}
    names = [n for n, o in offsets.items() if o.get("ok")]
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            skew[f"{a}-{b}"] = {
                "skew_s": offsets[a]["offset_s_median"] - offsets[b]["offset_s_median"],
            }

    meta = {
        "utc": utc,
        "gate": "BT19_timeline",
        "fw": "0.3.0",
        "method": "http_sync_marker_rtt_midpoint",
        "offsets": offsets,
        "skew_s": skew,
        "claims": {
            "PTP": False,
            "shared_clock": False,
            "estimated_timeline_alignment": True,
        },
        "claim": "correlated_via_debian_bridge_not_PTP",
    }
    meta_path = EVIDENCE / f"LAB_TIMELINE_{utc}.meta.json"
    md_path = EVIDENCE / f"LAB_TIMELINE_{utc}.md"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    out_path = EVIDENCE / f"LAB_TIMELINE_{utc}.jsonl"
    t_end = time.time() + args.seconds
    n = 0
    errors = 0
    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "meta", **meta}) + "\n")
        while time.time() < t_end:
            for name, ip in NODES.items():
                try:
                    st = get_json(f"http://{ip}/api/status")
                    mk = get_json(f"http://{ip}/api/lab/sync-marker")
                    mono = int(mk.get("mono_us") or 0)
                    off = offsets.get(name, {}).get("offset_s_median")
                    debian_est = (mono / 1e6 + off) if off is not None else None
                    oc = st.get("onchip") or {}
                    rec = {
                        "type": "sample",
                        "node": name,
                        "ip": ip,
                        "debian_unix_est": debian_est,
                        "mono_us": mono,
                        "uncertainty_ms": offsets.get(name, {}).get("uncertainty_ms_median"),
                        "state": oc.get("state"),
                        "leConnected": oc.get("leConnected"),
                        "appTxBps": oc.get("appTxBps"),
                        "appRxBps": oc.get("appRxBps"),
                        "aclTxBps": (st.get("hciCapture") or {}).get("aclTxBps"),
                        "droppedSession": (st.get("capture") or {}).get("droppedSession"),
                        "seqGapsSession": (st.get("btac") or {}).get("seqGapsSession"),
                    }
                    f.write(json.dumps(rec) + "\n")
                    n += 1
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    f.write(json.dumps({"type": "error", "node": name, "error": str(exc)}) + "\n")
            time.sleep(0.5)

    ok_nodes = sum(1 for o in offsets.values() if o.get("ok"))
    lines = [
        f"# LAB TIMELINE BT19 — nodes_ok={ok_nodes}/3 · samples={n}",
        "",
        f"**UTC:** {utc} · **seconds:** {args.seconds}",
        f"**Raw:** [`LAB_TIMELINE_{utc}.jsonl`](LAB_TIMELINE_{utc}.jsonl) · [`LAB_TIMELINE_{utc}.meta.json`](LAB_TIMELINE_{utc}.meta.json)",
        "",
        "## Claims",
        "- PTP: **NO**",
        "- shared_clock: **NO**",
        "- estimated_timeline_alignment: **YES**",
        "",
        "| node | offset_s median | rtt_ms | jitter | uncertainty_ms | n |",
        "|------|-----------------|--------|--------|----------------|---|",
    ]
    for name, o in offsets.items():
        if not o.get("ok"):
            lines.append(f"| {name} | FAIL | — | — | — | 0 |")
            continue
        lines.append(
            f"| {name} | {o['offset_s_median']:.6f} | {o['rtt_ms_median']:.2f} | "
            f"{o['rtt_ms_jitter']:.2f} | {o['uncertainty_ms_median']:.2f} | {o['sample_count']} |"
        )
    lines += ["", f"errors_during_sample: {errors}", ""]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = {
        "ok": ok_nodes == 3 and n > 0,
        "samples": n,
        "errors": errors,
        "jsonl": str(out_path),
        "meta": str(meta_path),
        "md": str(md_path),
        "offsets_ok": ok_nodes,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
