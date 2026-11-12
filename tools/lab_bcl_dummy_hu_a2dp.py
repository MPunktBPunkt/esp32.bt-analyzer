#!/usr/bin/env python3
"""B0.7 — Dummy-HU as SPP server *and* A2DP sink, answering BCL session init.

Audit bmw-bcl-rfcomm-role-2026-desk (BclCarLink @7cfd959): the phone app is the
RFCOMM client and only tries devices that are A2DP-connected and list the SPP
UUID. This run mirrors that gate before any RFCOMM attempt.

  --peer synthetic  .87 (A2DP source) plays the phone: pair, A2DP connect, gate,
                    then BclCarLink-order RFCOMM client (init → HANDSHAKE → KNOCK).
  --peer external   wait for a real phone on the HU-dummy adapter and log
                    whatever BCL bytes it sends (needs someone at home).

HU-dummy defaults to .131: it is the adapter that already ran as A2DP sink in the
relay and that the phone is paired with. The dummy must be up *before* pairing /
connecting, otherwise the cached SDP lacks SPP and the app skips the device.

Run on a machine with SSH to .108 (python3-gi + python3-dbus there):
  python3 tools/lab_bcl_dummy_hu_a2dp.py
  python3 tools/lab_bcl_dummy_hu_a2dp.py --peer external --seconds 180 --echo-watchdog

Epistemic: TEST only — proves our Dummy-HU / messkette, not BMW HU behaviour.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import summarize  # noqa: E402
from lab_bcl_dummy_hu_sdp import DEFAULT_SSH, HU_DUMMY, PHONE, btctl, resolve_hci, ssh  # noqa: E402
from lab_pair_agent import service_active  # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence"
REMOTE_DIR = "/tmp/bcl_dummy"
UPLOAD = ("bcl_framer.py", "bcl_dummy_hu.py", "bcl_dummy_hu_agent.py")
NODES = {"131": PHONE, "87": HU_DUMMY}
UUID_SPP = "00001101"
UUID_A2DP_SINK = "0000110b"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def upload() -> None:
    ssh(f"mkdir -p {REMOTE_DIR}", timeout=15)
    files = [str(ROOT / "tools" / f) for f in UPLOAD]
    p = subprocess.run(
        ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", *files,
         f"{DEFAULT_SSH}:{REMOTE_DIR}/"],
        capture_output=True, text=True, timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(f"scp failed: {p.stderr}")


def start_hu_agent(args: argparse.Namespace, hold: float) -> None:
    ready = f"{REMOTE_DIR}/hu.ready"
    opts = f"--channel {args.channel} --hu-version {args.hu_version} --hold {hold}"
    if args.echo_watchdog:
        opts += " --echo-watchdog"
    ssh(f"pkill -f 'bcl_dummy_hu_agent.py hu' ; rm -f {ready} {REMOTE_DIR}/*.jsonl", timeout=15)
    ssh(
        f"nohup python3 {REMOTE_DIR}/bcl_dummy_hu_agent.py hu {opts} "
        f"--log {REMOTE_DIR}/hu.jsonl --ready {ready} >{REMOTE_DIR}/hu.out 2>&1 &",
        timeout=15,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        if ssh(f"test -f {ready}", timeout=10).returncode == 0:
            return
        time.sleep(0.5)
    out = ssh(f"tail -30 {REMOTE_DIR}/hu.out", timeout=10).stdout
    raise RuntimeError(f"hu agent not ready: {out}")


def stop_agents() -> None:
    ssh("pkill -f bcl_dummy_hu_agent.py || true", timeout=15)


def read_jsonl(name: str) -> list[dict]:
    text = ssh(f"cat {REMOTE_DIR}/{name} 2>/dev/null", timeout=20).stdout or ""
    return [json.loads(ln) for ln in text.splitlines() if ln.strip().startswith("{")]


def prepare_hu(hu: dict) -> str:
    return btctl([f"select {hu['bd']}", "power on", "pairable on", "discoverable on",
                  "system-alias BCL-HU-Dummy"], timeout=30)


def device_path(hci: str, bd: str) -> str:
    return f"/org/bluez/{hci}/dev_{bd.upper().replace(':', '_')}"


def a2dp_link(phone: dict, hu: dict, fresh: bool, agent: bool) -> str:
    """Pair phone-emulator → HU-dummy and connect A2DP.

    With bt-pair-agent both sides get DisplayYesNo (Numeric Comparison, like a real
    phone): Pair/Connect go through busctl, which registers no agent, so the
    service answers both. Without it, fall back to a just-works session agent.
    """
    lines = []
    if fresh:
        lines += [f"select {hu['bd']}", f"remove {phone['bd']}",
                  f"select {phone['bd']}", f"remove {hu['bd']}", "@sleep 2"]
    lines += [f"select {phone['bd']}", "power on", "scan on", "@sleep 8", "scan off"]
    if not agent:
        lines = ["agent NoInputNoOutput", "default-agent"] + lines + [
            f"pair {hu['bd']}", "@sleep 8", "yes", f"trust {hu['bd']}",
            f"select {hu['bd']}", f"trust {phone['bd']}",
            f"select {phone['bd']}", f"connect {hu['bd']}", "@sleep 10", "yes"]
        return btctl(lines, timeout=90)
    out = btctl(lines, timeout=60)
    dev = device_path(resolve_hci(phone["bd"]) or phone["hci"], hu["bd"])
    p = ssh(
        f"busctl --timeout=40 call org.bluez {dev} org.bluez.Device1 Pair; echo pair=$?; "
        f"busctl set-property org.bluez {dev} org.bluez.Device1 Trusted b true; "
        f"busctl --timeout=30 call org.bluez {dev} org.bluez.Device1 Connect; echo connect=$?",
        timeout=90,
    )
    return out + (p.stdout or "") + (p.stderr or "")


def link_state(local: dict, peer_bd: str) -> dict:
    """What BclCarLink checks: peer connected, A2DP transport up, SPP in cached UUIDs."""
    info = btctl([f"select {local['bd']}", f"info {peer_bd}"], timeout=20)
    hci = resolve_hci(local["bd"]) or local["hci"]
    dev = "dev_" + peer_bd.upper().replace(":", "_")
    tree = ssh(f"busctl tree --list org.bluez | grep '/{hci}/{dev}/' || true", timeout=20).stdout or ""
    low = info.lower()
    st = {
        "hci": hci,
        "connected": "connected: yes" in low,
        "a2dp_transport": "/fd" in tree,
        "uuid_spp": UUID_SPP in low,
        "uuid_a2dp_sink": UUID_A2DP_SINK in low,
    }
    st["bclcarlink_gate"] = st["connected"] and st["a2dp_transport"] and st["uuid_spp"]
    return st


def a2dp_peers(hu: dict) -> list[str]:
    hci = resolve_hci(hu["bd"]) or hu["hci"]
    tree = ssh(f"busctl tree --list org.bluez | grep '^/org/bluez/{hci}/dev_.*/fd' || true",
               timeout=20).stdout or ""
    peers = {m.group(1).replace("_", ":") for m in re.finditer(r"/dev_([0-9A-F_]{17})/", tree)}
    return sorted(peers)


def run_phone_agent(phone: dict, hu: dict, args: argparse.Namespace) -> None:
    ssh(
        f"python3 {REMOTE_DIR}/bcl_dummy_hu_agent.py phone --adapter-bd {phone['bd']} "
        f"--hu-bd {hu['bd']} --channel {args.channel} --seconds {args.seconds} "
        f"--log {REMOTE_DIR}/phone.jsonl",
        timeout=args.seconds + 30,
    )


def watch_external(seconds: float) -> None:
    seen = 0
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(5)
        events = read_jsonl("hu.jsonl")
        for ev in events[seen:]:
            print("  hu:", json.dumps(ev))
        seen = len(events)


def verdict(peer: str, hu_events: list[dict], phone_events: list[dict],
            gate: dict | None, require_a2dp: bool) -> str:
    hu_sum = summarize(hu_events)
    connected = any(e["event"] == "rfcomm_connected" for e in hu_events)
    knock = hu_sum["frames"].get("rx:KNOCK", 0) > 0
    if peer == "external":
        if hu_sum["session_init"] and knock:
            return "BCL_KNOCK_SEEN"
        if hu_sum["session_init"]:
            return "BCL_INIT_SEEN"
        return "RFCOMM_NO_INIT" if connected else "NO_RFCOMM"
    if require_a2dp and gate is not None and not gate.get("bclcarlink_gate"):
        return "GATE_A2DP_FAIL"
    if any(e["event"] == "rfcomm_connect_failed" for e in phone_events):
        return "RFCOMM_FAIL"
    phone_hs = any(e["event"] == "handshake_rx" for e in phone_events)
    if hu_sum.get("handshake_sent") and phone_hs and knock:
        return "PASS"
    return "NO_HANDSHAKE"


def write_evidence(result: dict) -> tuple[Path, Path]:
    base = f"LAB_BCL_DUMMY_HU_A2DP_{result['utc']}"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    js, md = EVIDENCE / f"{base}.json", EVIDENCE / f"{base}.md"
    js.write_text(json.dumps(result, indent=2) + "\n")
    gate = result.get("gate") or {}
    lines = [
        f"# LAB BCL Dummy-HU A2DP+SPP — {result['verdict']}",
        "",
        f"**UTC:** {result['utc']} · peer `{result['peer']}` · HU-dummy `.{result['hu']}` "
        f"· channel {result['channel']} · hu_version {result['hu_version']}",
        "**claim:** Dummy-HU answers BCL session init behind the BclCarLink A2DP+SPP gate — TEST, not BMW FACT",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| bt-pair-agent active | {result.get('pair_agent')} |",
    ]
    for k in ("connected", "a2dp_transport", "uuid_spp", "uuid_a2dp_sink", "bclcarlink_gate"):
        if k in gate:
            lines.append(f"| gate {k} | {gate[k]} |")
    if result.get("a2dp_peers") is not None:
        lines.append(f"| A2DP peers on HU-dummy | {', '.join(result['a2dp_peers']) or '-'} |")
    lines.append(f"| HU events | `{json.dumps(result['hu_summary'])}` |")
    if result.get("phone_summary"):
        lines.append(f"| phone events | `{json.dumps(result['phone_summary'])}` |")
    lines += ["", "## First HU events", "", "```text"]
    lines += [json.dumps(e) for e in result["hu_events"][:30]]
    lines += [
        "```", "", "## Epistemic", "", "```text",
        "YES:  Dummy-HU keeps RFCOMM open and answers session init with HANDSHAKE",
        "YES:  BclCarLink gate (A2DP connected + SPP UUID) checked before RFCOMM",
        "NO:   real HU HANDSHAKE values, KNOCK reply, watchdog pong layout",
        "```", "",
    ]
    md.write_text("\n".join(lines))
    return js, md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--peer", choices=("synthetic", "external"), default="synthetic")
    ap.add_argument("--hu", choices=tuple(NODES), default="131")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--channel", type=int, default=5)
    ap.add_argument("--hu-version", type=int, default=3, help=">3 makes the phone send SELECTPROTO(3)")
    ap.add_argument("--echo-watchdog", action="store_true", help="echo watchdog DATA (HU pong layout UNKNOWN)")
    ap.add_argument("--no-require-a2dp", action="store_true", help="synthetic: try RFCOMM even if the gate fails")
    ap.add_argument("--keep-pairing", action="store_true", help="synthetic: skip remove/re-pair")
    ap.add_argument("--no-evidence", action="store_true")
    args = ap.parse_args()

    hu = NODES[args.hu]
    phone = next(n for k, n in NODES.items() if k != args.hu)
    require_a2dp = not args.no_require_a2dp
    result: dict = {
        "utc": utc_stamp(), "peer": args.peer, "hu": args.hu, "channel": args.channel,
        "hu_version": args.hu_version, "echo_watchdog": args.echo_watchdog,
        "require_a2dp": require_a2dp, "gate": None,
        "epistemic": {"source": "synthetic" if args.peer == "synthetic" else "real_phone",
                      "evidence_level": "TEST", "claim": "Dummy-HU BCL; not BMW wire FACT"},
    }
    phone_events: list[dict] = []
    try:
        result["pair_agent"] = agent = service_active()
        if not agent:
            print("WARN: bt-pair-agent nicht aktiv — Kopplung vom Handy aus bleibt unbeantwortet, "
                  "synthetisch nur Just Works (python3 tools/lab_pair_agent.py deploy)", file=sys.stderr)
        upload()
        result["prepare_hu_tail"] = prepare_hu(hu)[-600:]
        start_hu_agent(args, hold=args.seconds + (120 if args.peer == "synthetic" else 15))
        if args.peer == "external":
            print(f"Dummy-HU läuft auf .{args.hu} ({hu['bd']}), SPP-Kanal {args.channel}.")
            print("Handy jetzt per A2DP mit 'BCL-HU-Dummy' verbinden (bei Bedarf neu koppeln), App öffnen.")
            print("Passkey steht in der Lab-UI-Karte 'Pairing' — am Handy vergleichen und bestätigen.")
            watch_external(args.seconds)
            result["a2dp_peers"] = a2dp_peers(hu)
        else:
            result["a2dp_link_tail"] = a2dp_link(phone, hu, fresh=not args.keep_pairing,
                                                 agent=agent)[-1500:]
            result["gate"] = link_state(phone, hu["bd"])
            if result["gate"]["bclcarlink_gate"] or not require_a2dp:
                run_phone_agent(phone, hu, args)
                phone_events = read_jsonl("phone.jsonl")
    except Exception as exc:  # noqa: BLE001
        result["error"] = repr(exc)
    finally:
        hu_events = read_jsonl("hu.jsonl")
        stop_agents()

    result["hu_events"] = hu_events
    result["phone_events"] = phone_events
    result["hu_summary"] = summarize(hu_events)
    result["phone_summary"] = summarize(phone_events) if phone_events else None
    result["verdict"] = "ERROR" if "error" in result else verdict(
        args.peer, hu_events, phone_events, result["gate"], require_a2dp)

    print(json.dumps({k: result[k] for k in ("verdict", "gate", "hu_summary", "phone_summary")
                      if k in result}, indent=2))
    if not args.no_evidence:
        js, md = write_evidence(result)
        print(f"\nevidence: {js}\n          {md}")
    return 0 if result["verdict"] in ("PASS", "BCL_INIT_SEEN", "BCL_KNOCK_SEEN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
