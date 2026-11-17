#!/usr/bin/env python3
"""W0: correlate phone+HU jsonl for checkResource reply path (Fall A–E).

Usage:
  python3 tools/lab_w0_reply_forensic.py \\
    --phone docs/evidence/LAB_RETEST_USB_phone_20261117.jsonl \\
    --hu docs/evidence/LAB_RETEST_USB_hu_20261117.jsonl \\
    --out docs/evidence/LAB_W0_FORENSIC_TABLE_20261117.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _load(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _methods_hu(ev: list[dict]) -> Counter:
    c: Counter = Counter()
    for e in ev:
        if e.get("event") in ("f20_rpc_rx", "phone_tx_classified"):
            m = e.get("method") or e.get("rpc") or e.get("type_name")
            if m:
                c[str(m)] += 1
        if e.get("event") == "rhmi_check_resource":
            c["rhmi_check_resource_event"] += 1
    return c


def analyze(phone: list[dict], hu: list[dict]) -> dict[str, Any]:
    p_ev = Counter(e.get("event") for e in phone)
    h_ev = Counter(e.get("event") for e in hu)
    hu_methods = _methods_hu(hu)

    checks_tx = [e for e in phone if e.get("event") == "mybmw_check_resource_tx"]
    checks_rx = [e for e in phone if e.get("event") == "mybmw_check_resource_rx"]
    orphans = [e for e in phone if e.get("event") == "mybmw_check_resource_orphan"]
    uploads = [e for e in phone if e.get("event") == "mybmw_set_resource_tx"]
    menu = [e for e in phone if e.get("event") == "mybmw_menu_upload_queued"]
    done = next((e for e in phone if e.get("event") == "phone_done"), {})
    wd_miss = p_ev.get("watchdog_echo_missed", 0)
    wd_echo = p_ev.get("watchdog_echo_rtt", 0) + h_ev.get("watchdog_echo", 0)

    table: list[dict] = []
    for e in phone:
        evn = e.get("event")
        if evn == "mybmw_check_resource_tx":
            table.append(
                {
                    "dir": "Phone→HU",
                    "layer": "Etch",
                    "method": "rhmi_checkResource",
                    "type": e.get("type"),
                    "msg_id": e.get("msg_id"),
                    "hash": e.get("hash"),
                    "size": e.get("size"),
                    "bcl_src": e.get("bcl_src"),
                    "bcl_dest": e.get("bcl_dest"),
                }
            )
        elif evn == "mybmw_check_resource_rx":
            table.append(
                {
                    "dir": "HU→Phone",
                    "layer": "Etch",
                    "method": "_result_rhmi_checkResource",
                    "type": e.get("type"),
                    "inReplyTo": e.get("inReplyTo"),
                    "result": e.get("result"),
                    "cache": e.get("cache"),
                }
            )
        elif evn == "mybmw_set_resource_tx":
            table.append(
                {
                    "dir": "Phone→HU",
                    "layer": "Etch",
                    "method": "rhmi_setResource",
                    "type": e.get("type"),
                    "bytes": e.get("bytes"),
                    "sha256": e.get("sha256"),
                }
            )
        elif evn == "mybmw_menu_upload_queued":
            table.append(
                {
                    "dir": "Phone",
                    "layer": "State",
                    "method": "initialize+runtime_queued",
                    "uploads": e.get("uploads"),
                    "cache_hits": e.get("cache_hits"),
                }
            )
        elif evn in ("hold_abort", "phone_done"):
            table.append(
                {
                    "dir": "Phone",
                    "layer": "Session",
                    "method": evn,
                    "abort_reason": e.get("abort_reason") or e.get("reason"),
                    "wd_misses": e.get("wd_misses") or e.get("misses"),
                    "wait_class": e.get("wait_class"),
                    "rhmi_state": e.get("rhmi_state"),
                }
            )

    # Fall A–E classifier (USB/air forensic; Fall E is success path).
    case = "OPEN"
    detail = ""
    if checks_rx and not any(c.get("cache") == "miss" for c in checks_rx) and not uploads and menu:
        case = "E"
        detail = "cache_hit_path: replies seen, no setResource, initialize queued"
    elif checks_tx and not checks_rx:
        hu_saw_check = (
            hu_methods.get("rhmi_checkResource", 0) > 0
            or hu_methods.get("rhmi_check_resource_event", 0) > 0
        )
        if not hu_saw_check:
            # Phone TX logged; HU never classified checkResource → A or C
            # If HU got other late RPCs after creates, more like A (never arrived)
            # If HU rfcomm_closed soon after AM wave: transport.
            if h_ev.get("rfcomm_connected") and not hu_saw_check:
                case = "A_or_C"
                detail = (
                    "checkResource TX on phone; HU f20_rpc_rx has no rhmi_checkResource — "
                    "request never reached stub decode (A: not on wire / C: lost in reassembly)"
                )
        else:
            case = "B_or_D"
            detail = "HU saw checkResource but phone has no check_rx (B: RX loss / D: unmatched)"
    elif orphans:
        case = "D"
        detail = f"orphan inReplyTo count={len(orphans)}"
    elif checks_tx and checks_rx:
        case = "OK_PARTIAL" if not menu else "OK"
        detail = "check TX/RX correlated"

    wait_class = done.get("wait_class")
    if not wait_class and checks_tx and not checks_rx and wd_miss:
        wait_class = "WATCHDOG_MISS_NO_ETCH_REPLY"

    return {
        "claim_level": "LAB FORENSIC (W0 correlator)",
        "case": case,
        "case_detail": detail,
        "wait_class": wait_class,
        "counts": {
            "phone_events": dict(p_ev),
            "hu_events": {k: h_ev[k] for k in sorted(h_ev) if h_ev[k]},
            "hu_rpc_methods": dict(hu_methods),
            "check_tx": len(checks_tx),
            "check_rx": len(checks_rx),
            "orphans": len(orphans),
            "uploads": len(uploads),
            "wd_miss_phone": wd_miss,
            "wd_echo": wd_echo,
        },
        "transactions": table,
        "phone_done": {
            "abort_reason": done.get("abort_reason"),
            "wd_misses": done.get("wd_misses"),
            "rx_total": done.get("rx_total"),
            "active": done.get("active"),
            "rhmi_state": done.get("rhmi_state"),
            "wait_class": done.get("wait_class"),
            "open_txns": done.get("open_txns"),
        },
        "fall_legend": {
            "A": "HU antwortet nicht / Request nicht dekodiert",
            "B": "HU TX, Adapter kein RX",
            "C": "RX da, BCL/Etch verloren",
            "D": "Reply unmatched (inReplyTo)",
            "E": "Cache-Hit — kein setResource (kein Fehler)",
            "A_or_C": "TX ohne HU-RPC — Wire vs Reassembly noch offen",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phone", required=True, type=Path)
    ap.add_argument("--hu", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if not args.phone.is_file() or not args.hu.is_file():
        print("missing jsonl", file=sys.stderr)
        return 2
    report = analyze(_load(args.phone), _load(args.hu))
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
        print(f"wrote {args.out} case={report['case']} wait={report.get('wait_class')}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
