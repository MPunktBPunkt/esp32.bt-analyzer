#!/usr/bin/env python3
"""P1 minimal PiDrive UI sequence on Dual-ESP BCL.

Proves:
  setData(100,\"PiDrive\") → HU MENU_TEST_ACTION(200) → onActionEvent
  → ack → pidrive_action_sink(selected_action=PI_DRIVE_TEST)

Usage:
  python3 tools/lab_p0_rhmi_pidrive_seq.py --hold 90
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SSH = "root@192.168.178.108"
MENU_TEST_ACTION = 200
PI_DRIVE_TEST = "PI_DRIVE_TEST"


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


def analyze(hold: dict, phone: list[dict], hu: list[dict]) -> dict:
    if phone:
        t0 = float(phone[0].get("ts") or 0) - 2.0
        t1 = float(phone[-1].get("ts") or 0) + 2.0
        hu = [r for r in hu if t0 <= float(r.get("ts") or 0) <= t1]

    setdata = [
        r
        for r in phone
        if r.get("event") in ("pidrive_seq_setData", "mybmw_soak_setData")
        and r.get("modelId") == 100
        and r.get("value") == "PiDrive"
    ]
    action_tx = [
        r
        for r in hu
        if r.get("event") == "rhmi_action_tx" and int(r.get("actionId") or -1) == MENU_TEST_ACTION
    ]
    action_rx = [
        r
        for r in phone
        if r.get("event") == "mybmw_action_event_rx"
        and int(r.get("actionId") or -1) == MENU_TEST_ACTION
    ]
    acks = [
        r
        for r in phone
        if r.get("event") == "mybmw_action_ack_tx"
        and int(r.get("actionId") or -1) == MENU_TEST_ACTION
    ]
    sinks = [
        r
        for r in phone
        if r.get("event") == "pidrive_action_sink"
        and r.get("selected_action") == PI_DRIVE_TEST
    ]
    complete = [r for r in phone if r.get("event") == "pidrive_seq_complete"]
    closes = [
        r
        for r in hu
        if r.get("event") == "rfcomm_closed"
        and str(r.get("reason") or "") not in ("eof", "agent_stop")
    ]
    hold_s = float((hold.get("hold") or {}).get("hold_s") or 0)
    rhmi = (hold.get("hold") or {}).get("rhmi_state")
    abort = (hold.get("hold") or {}).get("abort_reason")
    selected = (hold.get("hold") or {}).get("selected_action")

    criteria = {
        "hold_ge_60s": hold_s >= 60,
        "runtime_active": rhmi == "RUNTIME_ACTIVE",
        "no_abort": not abort,
        "no_hu_close_fatal": not closes,
        "setData_PiDrive": len(setdata) >= 1,
        "action_tx_menu_test": len(action_tx) >= 1,
        "action_rx_menu_test": len(action_rx) >= 1,
        "action_ack": len(acks) >= 1,
        "pidrive_sink_PI_DRIVE_TEST": len(sinks) >= 1,
        "selected_action_done": selected == PI_DRIVE_TEST or bool(complete),
    }
    return {
        "pass": all(criteria.values()),
        "hold_s": hold_s,
        "rhmi_state": rhmi,
        "abort_reason": abort,
        "selected_action": selected,
        "seq_phase": (hold.get("hold") or {}).get("seq_phase"),
        "counts": {
            "setData_PiDrive": len(setdata),
            "action_tx": len(action_tx),
            "action_rx": len(action_rx),
            "acks": len(acks),
            "sinks": len(sinks),
            "complete": len(complete),
        },
        "inject": (hold.get("hold") or {}).get("pidrive_seq_action"),
        "hu_closes_fatal": [r.get("reason") for r in closes],
        "criteria": criteria,
        "chain": [
            "setData(100, PiDrive)",
            "HU MENU_TEST_ACTION(200)",
            "phone onActionEvent",
            "ack",
            "pidrive_action_sink → PI_DRIVE_TEST",
        ],
    }


def write_md(path: Path, report: dict, out_dir: Path) -> None:
    lines = [
        f"# LAB P0 PiDrive UI Sequence — {out_dir.name}",
        "",
        f"**verdict:** {'PASS' if report.get('pass') else 'FAIL'}",
        "",
        f"- hold_s: **{report.get('hold_s')}**",
        f"- rhmi_state: `{report.get('rhmi_state')}`",
        f"- selected_action: `{report.get('selected_action')}`",
        f"- seq_phase: `{report.get('seq_phase')}`",
        f"- counts: `{report.get('counts')}`",
        f"- inject: `{report.get('inject')}`",
        "",
        "## Chain",
        "",
    ]
    for step in report.get("chain") or []:
        lines.append(f"- {step}")
    lines += ["", "## Criteria", "", "| Check | OK |", "|-------|----|"]
    for k, v in (report.get("criteria") or {}).items():
        lines.append(f"| `{k}` | {'yes' if v else 'no'} |")
    lines.append("")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hold", type=float, default=90.0)
    ap.add_argument("--ssh", default=DEFAULT_SSH)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--single-esp", action="store_true")
    args = ap.parse_args()

    stamp = utc_stamp()
    mode = "SINGLE" if args.single_esp else "DUAL"
    out_dir = args.out_dir or (
        ROOT / "docs" / "evidence" / f"LAB_P0_RHMI_PIDRIVE_SEQ_{mode}_{stamp}"
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
        "--rhmi-pidrive-seq",
    ]
    if args.single_esp:
        cmd.append("--single-esp")
    print(f"PIDRIVE_SEQ start hold={args.hold}s -> {out_dir}", flush=True)
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode

    hold_data: dict = {}
    try:
        hold_data = json.loads(hold_out.read_text())
    except Exception:
        hold_data = {}

    remote = None
    md = hold_out.with_suffix(".md")
    if md.exists():
        for line in md.read_text().splitlines():
            if line.startswith("- remote:") and "`" in line:
                remote = line.split("`", 2)[1]
                break
    host = args.ssh
    if remote:
        for name in (
            "phone.jsonl",
            "esp_poll.jsonl",
            "esp_diag_pre.json",
            "esp_diag_post.json",
            "pidrive_seq_action.json",
        ):
            subprocess.run(
                ["scp", "-o", "BatchMode=yes", f"{host}:{remote}/{name}", str(out_dir / name)],
                check=False,
                capture_output=True,
                timeout=60,
            )
        subprocess.run(
            [
                "scp",
                "-o",
                "BatchMode=yes",
                f"{host}:/tmp/bcl_dummy/hu_ab_87131.jsonl",
                str(out_dir / "hu_ab_87131.jsonl"),
            ],
            check=False,
            capture_output=True,
            timeout=120,
        )

    phone = load_jsonl(out_dir / "phone.jsonl")
    hu = load_jsonl(out_dir / "hu_ab_87131.jsonl")
    # Trim HU evidence to window
    if phone and (out_dir / "hu_ab_87131.jsonl").exists():
        t0 = float(phone[0].get("ts") or 0) - 2
        t1 = float(phone[-1].get("ts") or 0) + 2
        hu_w = [r for r in hu if t0 <= float(r.get("ts") or 0) <= t1]
        (out_dir / "hu_ab_87131.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in hu_w)
        )
        hu = hu_w

    report = analyze(hold_data, phone, hu)
    (out_dir / "SEQ_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    write_md(out_dir / "SEQ.md", report, out_dir)
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "hold_s": report["hold_s"],
                "selected_action": report["selected_action"],
                "rc": rc,
                **report["criteria"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(f"wrote {out_dir / 'SEQ.md'}", flush=True)
    return 0 if report["pass"] and rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
