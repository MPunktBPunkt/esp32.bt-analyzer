#!/usr/bin/env python3
"""Lab Music NP spine sequence (frozen Handle-23 IDs).

Proves:
  setData(444/445/446/447) → triggerEvent(660/661)
  → HU actions 336+248 → ack → MUSIC_NP_SPINE sink

Usage:
  python3 tools/lab_music_np_spine_seq.py --hold 60
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

MODELS = (444, 445, 446, 447)
EVENTS = (660, 661)
ACTIONS = (336, 248)
SINK = "MUSIC_NP_SPINE"


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
        if r.get("event") in ("music_np_seq_setData", "mybmw_soak_setData")
        and int(r.get("modelId") or -1) in MODELS
    ]
    models_seen = sorted({int(r["modelId"]) for r in setdata if r.get("modelId") is not None})
    triggers = [
        r
        for r in phone
        if r.get("event") == "music_np_triggerEvent"
        and int(r.get("eventId") or -1) in EVENTS
    ]
    events_seen = sorted({int(r["eventId"]) for r in triggers if r.get("eventId") is not None})
    action_tx = [
        r
        for r in hu
        if r.get("event") == "rhmi_action_tx" and int(r.get("actionId") or -1) in ACTIONS
    ]
    action_rx = [
        r
        for r in phone
        if r.get("event") == "mybmw_action_event_rx"
        and int(r.get("actionId") or -1) in ACTIONS
    ]
    acks = [
        r
        for r in phone
        if r.get("event") == "mybmw_action_ack_tx"
        and int(r.get("actionId") or -1) in ACTIONS
    ]
    sinks = [
        r
        for r in phone
        if r.get("event") == "music_np_action_sink"
        and int(r.get("actionId") or -1) in ACTIONS
    ]
    complete = [r for r in phone if r.get("event") == "music_np_seq_complete"]
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
        "hold_ge_45s": hold_s >= 45,
        "runtime_active": rhmi == "RUNTIME_ACTIVE",
        "no_abort": not abort,
        "no_hu_close_fatal": not closes,
        "setData_models_444_447": set(MODELS).issubset(models_seen),
        "trigger_events_660_661": set(EVENTS).issubset(events_seen),
        "action_tx_336_248": {int(r.get("actionId")) for r in action_tx} >= set(ACTIONS),
        "action_rx_336_248": {int(r.get("actionId")) for r in action_rx} >= set(ACTIONS),
        "action_ack_336_248": {int(r.get("actionId")) for r in acks} >= set(ACTIONS),
        "music_np_sink": len(sinks) >= 2 or selected == SINK or bool(complete),
        "selected_or_complete": selected == SINK or bool(complete),
    }
    return {
        "pass": all(criteria.values()),
        "hold_s": hold_s,
        "rhmi_state": rhmi,
        "abort_reason": abort,
        "selected_action": selected,
        "seq_phase": (hold.get("hold") or {}).get("seq_phase"),
        "counts": {
            "setData": len(setdata),
            "models_seen": models_seen,
            "triggers": len(triggers),
            "events_seen": events_seen,
            "action_tx": len(action_tx),
            "action_rx": len(action_rx),
            "acks": len(acks),
            "sinks": len(sinks),
            "complete": len(complete),
        },
        "inject": (hold.get("hold") or {}).get("music_np_seq_action"),
        "hu_closes_fatal": [r.get("reason") for r in closes],
        "criteria": criteria,
        "chain": [
            "setData(444 source, 445 artist, 446/447 title)",
            "triggerEvent(660 multimediaInfo, 661 statusbar)",
            "HU actions 336 + 248",
            "phone ack + MUSIC_NP_SPINE sink",
        ],
    }


def write_md(path: Path, report: dict, out_dir: Path) -> None:
    lines = [
        f"# LAB Music NP Spine Sequence — {out_dir.name}",
        "",
        f"**verdict:** {'PASS' if report.get('pass') else 'FAIL'}",
        "",
        f"- hold_s: **{report.get('hold_s')}**",
        f"- rhmi_state: `{report.get('rhmi_state')}`",
        f"- selected_action: `{report.get('selected_action')}`",
        f"- seq_phase: `{report.get('seq_phase')}`",
        f"- counts: `{report.get('counts')}`",
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
    ap.add_argument("--hold", type=float, default=60.0)
    ap.add_argument("--ssh", default=DEFAULT_SSH)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--single-esp", action="store_true")
    args = ap.parse_args()

    stamp = utc_stamp()
    mode = "SINGLE" if args.single_esp else "DUAL"
    out_dir = args.out_dir or (
        ROOT / "docs" / "evidence" / f"LAB_MUSIC_NP_SPINE_SEQ_{mode}_{stamp}"
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
        "--rhmi-music-np-seq",
    ]
    if args.single_esp:
        cmd.append("--single-esp")
    print(f"MUSIC_NP_SEQ start hold={args.hold}s -> {out_dir}", flush=True)
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
            "music_np_seq_action.json",
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
