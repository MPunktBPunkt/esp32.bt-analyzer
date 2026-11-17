#!/usr/bin/env python3
"""P0 RHMI soak: 10 min Connected lifecycle + phased setData/Actions.

Phases (phone clock after RUNTIME_ACTIVE; HU actions on hold wall clock):
  0–1 min   stabilize
  1–3 min   setData repeat (models 100/101)
  3–5 min   multi-model + light setProperty
  5–7 min   HU→phone actions (phone acks)
  7–10 min  mixed setData/setProperty + slower actions

Usage:
  python3 tools/lab_p0_rhmi_soak.py --hold 600
  python3 tools/lab_p0_rhmi_soak.py --hold 600 --single-esp
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SSH = "root@192.168.178.108"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def count_events(rows: list[dict], key: str = "event") -> dict[str, int]:
    c: Counter[str] = Counter()
    for r in rows:
        c[str(r.get(key) or "?")] += 1
    return dict(c)


def analyze(out_dir: Path, hold: dict, phone: list[dict], hu: list[dict]) -> dict:
    phone_ev = count_events(phone)
    # HU agent jsonl is append-only across runs — only score this soak window.
    if phone:
        t0 = float(phone[0].get("ts") or 0) - 2.0
        t1 = float(phone[-1].get("ts") or 0) + 2.0
        hu = [r for r in hu if t0 <= float(r.get("ts") or 0) <= t1]
    hu_ev = count_events(hu)
    methods_tx = Counter(
        str(r.get("method"))
        for r in phone
        if r.get("event") == "mybmw_rpc_tx" and r.get("method")
    )
    methods_rx = Counter(
        str(r.get("method"))
        for r in phone
        if r.get("event") == "mybmw_rpc_rx" and r.get("method")
    )
    eagain = [r for r in hu if r.get("event") in ("tx_write_eagain", "tx_write_eagain_recovered", "tx_write_failed")]
    # Ignore terminal eof when phone ends the hold cleanly.
    closes = [
        r
        for r in hu
        if r.get("event") == "rfcomm_closed"
        and str(r.get("reason") or "") not in ("eof", "agent_stop")
    ]
    se = [r for r in phone if r.get("event") == "mybmw_setdata_service_exception"]
    phases = [r for r in phone if r.get("event") in ("mybmw_soak_start", "mybmw_soak_phase")]
    setdata_soak = [r for r in phone if r.get("event") == "mybmw_soak_setData"]
    actions_rx = [r for r in phone if r.get("event") == "mybmw_action_event_rx"]
    acks = [r for r in phone if r.get("event") == "mybmw_action_ack_tx"]
    action_tx = [r for r in hu if r.get("event") == "rhmi_action_tx"]
    esp_reset = False
    # bootGen bump detection left to hold.json esp_diag_*; surface if present later

    hold_s = float((hold.get("hold") or {}).get("hold_s") or 0)
    rhmi = (hold.get("hold") or {}).get("rhmi_state")
    abort = (hold.get("hold") or {}).get("abort_reason")
    wait_class = (hold.get("hold") or {}).get("wait_class")
    ok = (
        hold_s >= 540
        and rhmi == "RUNTIME_ACTIVE"
        and not abort
        and not closes
        and len(setdata_soak) >= 10
        and len(action_tx) >= 5
        and len(acks) >= 5
    )
    report = {
        "pass": ok,
        "hold_s": hold_s,
        "rhmi_state": rhmi,
        "abort_reason": abort,
        "wait_class": wait_class,
        "phone_events": phone_ev,
        "hu_events_key": {
            k: hu_ev[k]
            for k in (
                "rfcomm_closed",
                "tx_write_eagain",
                "tx_write_eagain_recovered",
                "tx_write_failed",
                "rhmi_action_tx",
                "inject_rhmi_request",
                "rhmi_setdata_reject",
            )
            if k in hu_ev
        },
        "methods_tx": dict(methods_tx),
        "methods_rx": dict(methods_rx),
        "eagain_events": len(eagain),
        "eagain_recovered": sum(1 for r in eagain if r.get("event") == "tx_write_eagain_recovered"),
        "hu_closes": [r.get("reason") for r in closes],
        "service_exceptions": [
            {"errorCode": r.get("errorCode"), "detail": r.get("detailMessage")} for r in se
        ],
        "soak_phases": phases,
        "soak_setData": len(setdata_soak),
        "soak_setData_models": sorted({r.get("modelId") for r in setdata_soak}),
        "actions_tx_hu": len(action_tx),
        "actions_rx_phone": len(actions_rx),
        "action_acks": len(acks),
        "soak_counts_done": (hold.get("hold") or {}).get("soak_counts"),
        "soak_actions_injected": (hold.get("hold") or {}).get("soak_actions"),
        "criteria": {
            "hold_ge_540s": hold_s >= 540,
            "runtime_active": rhmi == "RUNTIME_ACTIVE",
            "no_abort": not abort,
            "no_hu_close_fatal": not closes,
            "setData_soak_ge_10": len(setdata_soak) >= 10,
            "actions_tx_ge_5": len(action_tx) >= 5,
            "action_acks_ge_5": len(acks) >= 5,
        },
        "esp_reset_hint": esp_reset,
    }
    return report


def write_md(path: Path, report: dict, out_dir: Path) -> None:
    crit = report.get("criteria") or {}
    lines = [
        f"# LAB P0 RHMI Soak — {out_dir.name}",
        "",
        f"**verdict:** {'PASS' if report.get('pass') else 'FAIL'}",
        "",
        f"- hold_s: **{report.get('hold_s')}**",
        f"- rhmi_state: `{report.get('rhmi_state')}`",
        f"- abort: `{report.get('abort_reason')}`",
        f"- wait_class: `{report.get('wait_class')}`",
        f"- soak setData: **{report.get('soak_setData')}** models={report.get('soak_setData_models')}",
        f"- HU action TX: **{report.get('actions_tx_hu')}** · phone RX **{report.get('actions_rx_phone')}** · acks **{report.get('action_acks')}**",
        f"- EAGAIN events: {report.get('eagain_events')} (recovered={report.get('eagain_recovered')})",
        f"- HU closes: `{report.get('hu_closes')}`",
        f"- ServiceExceptions: {len(report.get('service_exceptions') or [])}",
        "",
        "## Pass criteria",
        "",
        "| Check | OK |",
        "|-------|----|",
    ]
    for k, v in crit.items():
        lines.append(f"| `{k}` | {'yes' if v else 'no'} |")
    lines += [
        "",
        "## Soak phases",
        "",
        "```json",
        json.dumps(report.get("soak_phases"), indent=2),
        "```",
        "",
        "## Counts (phone_done)",
        "",
        "```json",
        json.dumps(report.get("soak_counts_done"), indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hold", type=float, default=600.0)
    ap.add_argument("--ssh", default=DEFAULT_SSH)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--single-esp", action="store_true")
    args = ap.parse_args()

    stamp = utc_stamp()
    mode = "SINGLE" if args.single_esp else "DUAL"
    out_dir = args.out_dir or (
        ROOT / "docs" / "evidence" / f"LAB_P0_RHMI_SOAK_{mode}_{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    hold_out = out_dir / f"hold_{stamp}.json"
    cmd = [
        "python3",
        str(ROOT / "tools" / "lab_p0_dual_esp_hold.py"),
        "--hold",
        str(args.hold),
        "--out",
        str(hold_out),
        "--ssh",
        args.ssh,
        "--rhmi-soak",
    ]
    if args.single_esp:
        cmd.append("--single-esp")
    print(f"SOAK start hold={args.hold}s -> {out_dir}", flush=True)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode

    # Pull phone + HU logs from latest remote hold (hold script already fetched hold.json)
    # Re-fetch companion artifacts via ssh from hold.md remote path if present.
    hold_data: dict = {}
    try:
        hold_data = json.loads(hold_out.read_text())
    except Exception:
        hold_data = {}

    # hold.py stores remote phone.jsonl under OUT; try to scp from companion path in md
    md = hold_out.with_suffix(".md")
    remote = None
    if md.exists():
        for line in md.read_text().splitlines():
            if line.startswith("- remote:"):
                remote = line.split("`", 2)[1] if "`" in line else None
                break
    host = args.ssh
    if remote:
        for name in ("phone.jsonl", "esp_poll.jsonl", "esp_diag_pre.json", "esp_diag_post.json", "soak_actions.json"):
            subprocess.run(
                ["scp", "-o", "BatchMode=yes", f"{host}:{remote}/{name}", str(out_dir / name)],
                check=False,
                capture_output=True,
                timeout=60,
            )
        subprocess.run(
            ["scp", "-o", "BatchMode=yes", f"{host}:/tmp/bcl_dummy/hu_ab_87131.jsonl", str(out_dir / "hu_ab_87131.jsonl")],
            check=False,
            capture_output=True,
            timeout=120,
        )

    phone = load_jsonl(out_dir / "phone.jsonl")
    hu = load_jsonl(out_dir / "hu_ab_87131.jsonl")
    report = analyze(out_dir, hold_data, phone, hu)
    (out_dir / "SOAK_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    write_md(out_dir / "SOAK.md", report, out_dir)
    print(json.dumps({"pass": report["pass"], "hold_s": report["hold_s"], "rc": rc, **report["criteria"]}, ensure_ascii=False), flush=True)
    print(f"wrote {out_dir / 'SOAK.md'}", flush=True)
    return 0 if report["pass"] and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
