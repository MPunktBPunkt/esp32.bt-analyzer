#!/usr/bin/env python3
"""Classify BTAC/capture gaps vs ring drops (instrument fidelity).

Usage:
  python3 tools/lab_gap_classify.py --host 192.168.178.88 --btac path.btac
  python3 tools/lab_gap_classify.py --from-status before.json after.json --btac path.btac
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def get_status(ip: str) -> dict:
    with urllib.request.urlopen(f"http://{ip}/api/status", timeout=5) as r:
        return json.loads(r.read().decode())


def decode_stats(btac: Path) -> dict:
    p = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "btac_decode.py"), str(btac), "--stats"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "raw": p.stdout[-400:], "stderr": p.stderr[-200:]}


def classify(
    dropped_delta: int,
    seq_gaps_session_delta: int,
    file_gaps: int,
    btac_connected: bool,
) -> dict:
    reasons: list[str] = []
    if dropped_delta > 0 and not btac_connected:
        reasons.append("ring_overflow_no_btac_client")
    if dropped_delta > 0 and btac_connected:
        reasons.append("ring_overflow_or_tcp_backpressure")
    if file_gaps > 0 and dropped_delta == 0 and seq_gaps_session_delta == 0:
        reasons.append("collector_or_decode_anomaly")
    if file_gaps > 0 and (dropped_delta > 0 or seq_gaps_session_delta > 0):
        reasons.append("capture_path_loss_matches_file_gaps")
    if dropped_delta == 0 and seq_gaps_session_delta == 0 and file_gaps == 0:
        reasons.append("clean_session")
    if seq_gaps_session_delta > 0 and dropped_delta == 0:
        reasons.append("btac_forward_seq_gap_without_ring_drop")

    return {
        "ring_enqueue_ok": dropped_delta == 0,
        "e2e_file_ok": file_gaps == 0,
        "claim": {
            "drops_zero": "ring_enqueue_ok_in_window" if dropped_delta == 0 else "ring_drops_in_window",
            "e2e": "file_gaps_zero" if file_gaps == 0 else "file_has_gaps",
        },
        "metrics": {
            "dropped_delta": dropped_delta,
            "btac_seqGapsSession_delta": seq_gaps_session_delta,
            "file_gaps": file_gaps,
            "btac_connected": btac_connected,
        },
        "attribution": reasons,
        "ok": file_gaps == 0 and dropped_delta == 0,
    }


def window_deltas(before: dict, after: dict) -> tuple[int, int, bool]:
    cap_b, cap_a = before.get("capture") or {}, after.get("capture") or {}
    bt_b, bt_a = before.get("btac") or {}, after.get("btac") or {}
    if "droppedSession" in cap_a:
        dropped_delta = max(0, int(cap_a.get("droppedSession") or 0) - int(cap_b.get("droppedSession") or 0))
    else:
        dropped_delta = max(0, int(cap_a.get("dropped") or 0) - int(cap_b.get("dropped") or 0))
    if "seqGapsSession" in bt_a:
        gaps_delta = max(0, int(bt_a.get("seqGapsSession") or 0) - int(bt_b.get("seqGapsSession") or 0))
    else:
        gaps_delta = max(0, int(bt_a.get("seqGaps") or 0) - int(bt_b.get("seqGaps") or 0))
    return dropped_delta, gaps_delta, bool(bt_a.get("connected"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="192.168.178.88")
    ap.add_argument("--btac", type=Path, help="BTAC file to decode for file_gaps")
    ap.add_argument("--from-status", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("-o", type=Path, help="Write JSON result")
    args = ap.parse_args()

    if args.from_status:
        before = json.loads(Path(args.from_status[0]).read_text(encoding="utf-8"))
        after = json.loads(Path(args.from_status[1]).read_text(encoding="utf-8"))
        dropped_delta, gaps_delta, connected = window_deltas(before, after)
    else:
        after = get_status(args.host)
        # Session counters = since last BTAC connect (best live estimate)
        cap = after.get("capture") or {}
        bt = after.get("btac") or {}
        dropped_delta = int(cap.get("droppedSession") or 0)
        gaps_delta = int(bt.get("seqGapsSession") or 0)
        connected = bool(bt.get("connected"))

    file_gaps = 0
    dec: dict = {}
    if args.btac and args.btac.is_file():
        dec = decode_stats(args.btac)
        file_gaps = int(dec.get("gaps") or 0)

    result = classify(dropped_delta, gaps_delta, file_gaps, connected)
    result["decode"] = dec or None
    if not args.from_status:
        result["lifetime_note"] = {
            "dropped": (after.get("capture") or {}).get("dropped"),
            "seqGaps": (after.get("btac") or {}).get("seqGaps"),
            "warning": "Do not compare lifetime seqGaps to drops_delta — use session deltas",
        }

    text = json.dumps(result, indent=2) + "\n"
    if args.o:
        args.o.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
