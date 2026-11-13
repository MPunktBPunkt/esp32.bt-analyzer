#!/usr/bin/env python3
"""Short F20 field session helper: B1 SDP + B2-A/B2-B observe-only (+ btmon).

Designed for a ~1 h car window. Runs commands on .108 via SSH (default).
Does **not** send BCL. Channel for B2-A comes from B1 JSON (never assume 5).

Examples (from laptop with SSH to .108):
  python3 tools/field_b1_b2.py preflight
  python3 tools/field_b1_b2.py b1 --state A
  python3 tools/field_b1_b2.py b2a --channel X          # after B1
  python3 tools/field_b1_b2.py b2b --hold 90            # observe-only server
  python3 tools/field_b1_b2.py pack --session-id SID    # write evidence stub

Control before RFCOMM: MyBMW + AAIdrive force-stopped on phone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
DEFAULT_SSH = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")
HU_BD = os.environ.get("BT_HU_BD", "D4:36:39:CF:E1:B5")
PHONE_BD = os.environ.get("BT_PHONE_BD", "C8:C9:A3:CB:37:96")  # .87
REMOTE_TOOLS = "/tmp/bt-analyzer-field"
AGENT = "bcl_dummy_hu_agent.py"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ssh(cmd: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=accept-new",
            DEFAULT_SSH,
            f"bash -lc {shlex.quote(cmd)}",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def scp_to(local: Path, remote: str) -> None:
    p = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=accept-new",
            str(local),
            f"{DEFAULT_SSH}:{remote}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(f"scp failed: {p.stderr}")


def resolve_hci(bd: str) -> str | None:
    out = ssh("hciconfig -a", timeout=15).stdout or ""
    for block in re.split(r"\n(?=hci\d+:)", out):
        if bd.lower() in block.lower():
            return block.split(":", 1)[0].strip()
    return None


def ensure_remote_tools() -> None:
    ssh(f"mkdir -p {REMOTE_TOOLS}", timeout=15)
    for name in (
        "bcl_dummy_hu_agent.py",
        "bcl_dummy_hu.py",
        "bcl_framer.py",
        "bcl_classify.py",
        "bcl_sdp_probe.py",
    ):
        scp_to(ROOT / "tools" / name, f"{REMOTE_TOOLS}/{name}")


def cmd_preflight(_: argparse.Namespace) -> int:
    print(f"SSH {DEFAULT_SSH}")
    st = ssh("curl -s --max-time 3 http://192.168.178.87/api/status || echo FAIL", timeout=20)
    print("—.87 /api/status—")
    print((st.stdout or st.stderr or "")[:800])
    hci = resolve_hci(PHONE_BD)
    print(f".87 BD {PHONE_BD} → {hci or 'NOT FOUND'}")
    agent = ssh("systemctl is-active bt-pair-agent || true", timeout=15)
    print(f"bt-pair-agent: {(agent.stdout or '').strip()}")
    print("Control reminder: MyBMW OFF, AAIdrive OFF before B2.")
    return 0 if hci else 1


def cmd_btmon_start(args: argparse.Namespace) -> int:
    hci = resolve_hci(PHONE_BD) or args.hci
    if not hci:
        print("no hci for .87", file=sys.stderr)
        return 1
    stamp = utc_stamp()
    path = f"/tmp/field_{stamp}.btsnoop"
    ssh(f"pkill -f 'btmon -i {hci}' || true", timeout=15)
    ssh(
        f"nohup btmon -i {hci} -w {path} >/tmp/field_btmon_{stamp}.log 2>&1 & echo $!",
        timeout=15,
    )
    print(json.dumps({"hci": hci, "btsnoop": path, "ts": stamp}, indent=2))
    return 0


def cmd_b1(args: argparse.Namespace) -> int:
    ensure_remote_tools()
    hci = resolve_hci(PHONE_BD) or args.hci
    if not hci:
        print("no hci", file=sys.stderr)
        return 1
    sid = args.session_id or f"FIELD_B1_{utc_stamp()}"
    remote_json = f"/tmp/{sid}.json"
    cmd = (
        f"python3 {REMOTE_TOOLS}/bcl_sdp_probe.py -i {shlex.quote(hci)} "
        f"hu={shlex.quote(args.hu_bd)} --records --json {shlex.quote(remote_json)}"
    )
    p = ssh(cmd, timeout=90)
    print(p.stdout or "")
    if p.stderr:
        print(p.stderr, file=sys.stderr)
    pull = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            f"{DEFAULT_SSH}:{remote_json}",
            str(EVIDENCE / f"{sid}.json"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    local = EVIDENCE / f"{sid}.json"
    if pull.returncode == 0 and local.exists():
        raw = json.loads(local.read_text())
        # bcl_sdp_probe writes {"ts", "results":[{verdict, records, ...}]}
        results = raw.get("results") or [raw]
        primary = results[0] if results else {}
        channels = []
        named = []
        for res in results:
            for rec in res.get("records") or []:
                if not isinstance(rec, dict):
                    continue
                ch = rec.get("rfcomm")
                if ch is not None:
                    channels.append(ch)
                    named.append({"name": rec.get("name"), "rfcomm": ch, "tags": rec.get("tags")})
        data = {
            "session_id": sid,
            "gate": "B1",
            "state": args.state,
            "source": "field",
            "origin": "f20",
            "tx_allowed": False,
            "control": {
                "mybmw": args.mybmw,
                "aaidrive": args.aaidrive,
                "a2dp": args.a2dp,
            },
            "hci": hci,
            "hu_bd": args.hu_bd,
            "verdict": primary.get("verdict"),
            "channels": channels,
            "rfcomm_services": named,
            "probe": raw,
        }
        local.write_text(json.dumps(data, indent=2) + "\n")
        md = EVIDENCE / f"{sid}.md"
        md.write_text(
            f"# {sid}\n\n"
            f"- gate: B1 state {args.state}\n"
            f"- verdict: {data.get('verdict')}\n"
            f"- hci: {hci}\n"
            f"- hu: {args.hu_bd}\n"
            f"- channels (X): {channels}\n"
            f"- services: {named}\n"
            f"- control: MyBMW={args.mybmw} AAIdrive={args.aaidrive} A2DP={args.a2dp}\n"
            f"- tx_allowed: false\n"
            f"\nNext: `python3 tools/field_b1_b2.py b2a --channel X` "
            f"with X from channels above (never assume 5).\n"
        )
        print(f"wrote {local}")
        print(f"verdict={data.get('verdict')} channels={channels}")
        if channels:
            print(f"HINT: python3 tools/field_b1_b2.py b2a --channel {channels[0]}")
    return p.returncode


def cmd_b2a(args: argparse.Namespace) -> int:
    if args.channel is None:
        print("B2-A needs --channel X from B1 (never assume 5)", file=sys.stderr)
        return 2
    ensure_remote_tools()
    sid = args.session_id or f"FIELD_B2A_{utc_stamp()}"
    log = f"/tmp/{sid}.jsonl"
    cmd = (
        f"python3 {REMOTE_TOOLS}/{AGENT} b2a "
        f"--adapter-bd {shlex.quote(PHONE_BD)} "
        f"--hu-bd {shlex.quote(args.hu_bd)} "
        f"--channel {int(args.channel)} "
        f"--seconds {float(args.seconds)} "
        f"--session-id {shlex.quote(sid)} "
        f"--origin f20 --source field "
        f"--log {shlex.quote(log)}"
    )
    print(f"B2-A observe-only connect ch={args.channel} ({args.seconds}s)")
    p = ssh(cmd, timeout=float(args.seconds) + 40)
    print(p.stdout or "")
    if p.stderr:
        print(p.stderr, file=sys.stderr)
    _pull_log(log, sid, gate="B2-A", extra={"channel": args.channel, "tx_allowed": False})
    return p.returncode


def cmd_b2b(args: argparse.Namespace) -> int:
    ensure_remote_tools()
    sid = args.session_id or f"FIELD_B2B_{utc_stamp()}"
    log = f"/tmp/{sid}.jsonl"
    ready = f"/tmp/{sid}.ready"
    # Lab Dummy used ch.5; for B2-B we still advertise a channel — record it as lab/offer.
    # HU may dial a different conceptual service; capture proves what happened.
    cmd = (
        f"rm -f {shlex.quote(ready)}; "
        f"python3 {REMOTE_TOOLS}/{AGENT} b2b "
        f"--channel {int(args.channel)} "
        f"--name {shlex.quote(args.name)} "
        f"--hold {float(args.hold)} "
        f"--session-id {shlex.quote(sid)} "
        f"--origin f20 --source field "
        f"--log {shlex.quote(log)} "
        f"--ready {shlex.quote(ready)}"
    )
    print(
        f"B2-B observe-only SPP server ch={args.channel} name={args.name!r} "
        f"hold={args.hold}s — NO BCL TX"
    )
    p = ssh(cmd, timeout=float(args.hold) + 40)
    print(p.stdout or "")
    if p.stderr:
        print(p.stderr, file=sys.stderr)
    _pull_log(
        log,
        sid,
        gate="B2-B",
        extra={
            "channel_offered": args.channel,
            "service_name": args.name,
            "tx_allowed": False,
            "bcl_tx_enabled": False,
            "note": "channel_offered is lab SDP value; not F20 HU channel X",
        },
    )
    return p.returncode


def _pull_log(remote_log: str, sid: str, *, gate: str, extra: dict) -> None:
    local = EVIDENCE / f"{sid}.jsonl"
    pull = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            f"{DEFAULT_SSH}:{remote_log}",
            str(local),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if pull.returncode != 0:
        print(f"warn: could not pull {remote_log}: {pull.stderr}", file=sys.stderr)
        return
    events = []
    for line in local.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    summary = {
        "session_id": sid,
        "gate": gate,
        "source": "field",
        "origin": "f20",
        "ts_utc": utc_stamp(),
        "event_count": len(events),
        "events_head": events[:5],
        "events_tail": events[-10:],
        **extra,
    }
    # Last classification if present
    for ev in reversed(events):
        if "bcl_classification" in ev:
            summary["bcl_classification"] = ev["bcl_classification"]
            summary["classification"] = ev.get("classification")
            break
    tx = [e for e in events if e.get("event") == "tx_bytes"]
    blocked = [e for e in events if e.get("event") == "tx_blocked"]
    summary["tx_bytes_events"] = len(tx)
    summary["tx_blocked_events"] = len(blocked)
    if gate == "B2-B" and tx:
        summary["FAIL"] = "B2-B must not TX"
    out = EVIDENCE / f"{sid}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    (EVIDENCE / f"{sid}.md").write_text(
        f"# {sid}\n\n"
        f"- gate: {gate}\n"
        f"- bcl_classification: {summary.get('bcl_classification', 'n/a')}\n"
        f"- tx_allowed: false\n"
        f"- tx_bytes_events: {len(tx)}\n"
        f"- jsonl: {local.name}\n"
    )
    print(f"wrote {out}")


def cmd_pack(args: argparse.Namespace) -> int:
    sid = args.session_id or f"FIELD_PACK_{utc_stamp()}"
    pack = {
        "session_id": sid,
        "source": "field",
        "origin": "f20",
        "tx_allowed": False,
        "gates": ["B1", "B2-A", "B2-B"],
        "hu_bd": args.hu_bd,
        "phone_bd": PHONE_BD,
        "control": {
            "mybmw": "OFF",
            "aaidrive": "OFF",
            "note": "Versuchsbedingung, kein Protokollfakt",
        },
        "epistemic": {
            "rfcomm_initiator": "UNKNOWN until SABM in captures",
            "bcl": "UNKNOWN until classification ≥ BCL_FIELD_CONFIRMED",
            "channel_5": "lab_only",
        },
        "checklist": [
            "btmon btsnoop saved",
            "B1 JSON with channel X",
            "B2-A jsonl (connect + SABM direction in btmon)",
            "B2-B jsonl with tx_bytes_events==0",
            "MyBMW/AAIdrive state documented",
        ],
    }
    path = EVIDENCE / f"{sid}.json"
    path.write_text(json.dumps(pack, indent=2) + "\n")
    print(path)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hu-bd", default=HU_BD)
    ap.add_argument("--hci", default="", help="override hciN for .87")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pre = sub.add_parser("preflight")
    pre.set_defaults(func=cmd_preflight)

    bm = sub.add_parser("btmon-start")
    bm.set_defaults(func=cmd_btmon_start)

    b1 = sub.add_parser("b1")
    b1.add_argument("--state", default="A", help="A paired / B +A2DP / C +MyBMW / D +AAIdrive")
    b1.add_argument("--session-id", default="")
    b1.add_argument("--mybmw", default="OFF")
    b1.add_argument("--aaidrive", default="OFF")
    b1.add_argument("--a2dp", default="unknown")
    b1.set_defaults(func=cmd_b1)

    b2a = sub.add_parser("b2a")
    b2a.add_argument("--channel", type=int, required=True)
    b2a.add_argument("--seconds", type=float, default=20.0)
    b2a.add_argument("--session-id", default="")
    b2a.set_defaults(func=cmd_b2a)

    b2b = sub.add_parser("b2b")
    b2b.add_argument("--channel", type=int, default=5, help="offered lab channel (not HU X)")
    b2b.add_argument("--name", default="BMW Connected")
    b2b.add_argument("--hold", type=float, default=90.0)
    b2b.add_argument("--session-id", default="")
    b2b.set_defaults(func=cmd_b2b)

    pk = sub.add_parser("pack")
    pk.add_argument("--session-id", default="")
    pk.set_defaults(func=cmd_pack)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
