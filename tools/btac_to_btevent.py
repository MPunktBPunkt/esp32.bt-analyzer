#!/usr/bin/env python3
"""Map BTAC frames → BT_EVENT JSONL (0.3.9 recorder view).

Usage:
  python3 tools/btac_to_btevent.py capture.btac -o capture.btevent.jsonl
  python3 tools/btac_to_btevent.py capture.btac --stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import btac  # noqa: E402

DIR_MAP = {
    "host_to_controller": "tx",
    "controller_to_host": "rx",
    "unknown": "unknown",
}


def to_btevent(fr: dict, *, node_id: str = "unknown") -> dict:
    ptype = fr.get("type") or "unknown"
    payload_hex = fr.get("payload_hex") or ""
    ev: dict = {
        "seq": fr.get("seq"),
        "timestamp_us": fr.get("ts_us"),
        "node_id": node_id,
        "transport": "hci",
        "layer": "hci" if ptype != "meta" else "session",
        "direction": DIR_MAP.get(fr.get("dir") or "unknown", "unknown"),
        "event_type": ptype,
        "length": fr.get("length"),
        "payload_hex": payload_hex,
        "crc_ok": fr.get("crc_ok"),
        "claim": "HCI_session_recorder_not_air",
    }
    if ptype == "meta" and payload_hex:
        try:
            meta = json.loads(bytes.fromhex(payload_hex).decode("utf-8"))
            ev["session_id"] = meta.get("sid")
            ev["connection_id"] = meta.get("cid")
            ev["event_type"] = f"session_{str(meta.get('k') or 'meta').lower()}"
            if meta.get("label"):
                ev["label"] = meta["label"]
            ev["meta"] = meta
        except Exception:  # noqa: BLE001
            ev["meta_parse_error"] = True
    return ev


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--node-id", default="unknown")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    if not args.input.is_file():
        print(f"missing {args.input}", file=sys.stderr)
        return 2

    events = []
    out_f = args.output.open("w", encoding="utf-8") if args.output else None
    try:
        for fr in btac.iter_file(str(args.input)):
            ev = to_btevent(fr, node_id=args.node_id)
            events.append(ev)
            line = json.dumps(ev, ensure_ascii=False) + "\n"
            if out_f:
                out_f.write(line)
            elif not args.stats:
                sys.stdout.write(line)
    finally:
        if out_f:
            out_f.close()

    session_ev = [e for e in events if str(e.get("event_type", "")).startswith("session_")]
    summary = {
        "ok": len(events) > 0,
        "frames": len(events),
        "session_events": len(session_ev),
        "by_type": {},
        "input": str(args.input),
        "output": str(args.output) if args.output else None,
    }
    for e in events:
        t = e.get("event_type") or "?"
        summary["by_type"][t] = summary["by_type"].get(t, 0) + 1
    if args.stats:
        print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
