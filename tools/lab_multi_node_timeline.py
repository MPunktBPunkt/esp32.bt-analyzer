#!/usr/bin/env python3
"""BT19 scaffold — multi-node timeline using clock-sync offsets.

Collects sync markers + brief status samples from .88/.89/.87 into one JSONL
with debian_unix timestamps. Not a full USB+AOA correlator — foundation only.

Usage:
  python3 tools/lab_multi_node_timeline.py --seconds 15
"""

from __future__ import annotations

import argparse
import json
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    # One-shot offsets via sync markers
    offsets = {}
    for name, ip in NODES.items():
        t0 = time.time()
        try:
            m = get_json(f"http://{ip}/api/lab/sync-marker")
            t1 = time.time()
            mid = (t0 + t1) / 2
            offsets[name] = mid - (int(m.get("mono_us") or 0) / 1e6)
        except Exception as exc:  # noqa: BLE001
            offsets[name] = None
            print(f"offset fail .{name}: {exc}")

    out_path = EVIDENCE / f"LAB_TIMELINE_{utc}.jsonl"
    meta = {
        "utc": utc,
        "gate": "BT19_timeline_scaffold",
        "offsets_s": offsets,
        "claims": {
            "PTP": False,
            "shared_clock": False,
            "estimated_timeline_alignment": True,
        },
        "claim": "correlated_via_debian_bridge_not_PTP",
    }
    (EVIDENCE / f"LAB_TIMELINE_{utc}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    t_end = time.time() + args.seconds
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "meta", **meta}) + "\n")
        while time.time() < t_end:
            for name, ip in NODES.items():
                try:
                    st = get_json(f"http://{ip}/api/status")
                    mk = get_json(f"http://{ip}/api/lab/sync-marker")
                    mono = int(mk.get("mono_us") or 0)
                    off = offsets.get(name)
                    debian_est = (mono / 1e6 + off) if off is not None else None
                    oc = st.get("onchip") or {}
                    rec = {
                        "type": "sample",
                        "node": name,
                        "ip": ip,
                        "debian_unix_est": debian_est,
                        "mono_us": mono,
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
                    f.write(json.dumps({"type": "error", "node": name, "error": str(exc)}) + "\n")
            time.sleep(0.5)

    print(json.dumps({"ok": True, "samples": n, "jsonl": str(out_path), "offsets": offsets}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
