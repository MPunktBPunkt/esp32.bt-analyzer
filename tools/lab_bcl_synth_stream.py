#!/usr/bin/env python3
"""B0.5 — Synthetic BCL stream through the capture/decode chain (no BMW).

Validates BCL frame recognition, fragmentation reassembly, direction tags,
timestamps and JSONL/PCAP-friendly evidence using the hu-probe CaC1 lab stream.

Modes:
  offline  (default)  feed synthetic bytes through BclFramer in chunks
  rfcomm              optional: RFCOMM loop on .108 between hci1 (.87) and hci2 (.131)

Epistemic:
  source=synthetic · evidence_level=TEST · direct_observation=false
  Proves decoder / messkette mechanics — NOT NBT Evo / Connected wire FACT.

Usage:
  python3 tools/lab_bcl_synth_stream.py
  python3 tools/lab_bcl_synth_stream.py --mode rfcomm --seconds 20
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_framer import (  # noqa: E402
    CA_C1_LAB_CHUNKS,
    BclFramer,
    BclParseError,
    build_ca_c1_lab_bcl_stream,
    cmd_desk_name,
    dest_desk_label,
    feed_chunked,
    iter_chunks,
)

EVIDENCE = ROOT / "docs" / "evidence"
DEFAULT_SSH = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")

# Lab mapping from live status / hciconfig (2026-11-12):
#   hci1 C8:C9:A3:CB:37:96  ← .87  (car / HU-dummy side)
#   hci2 C8:C9:A3:CB:7B:0A  ← .131 (phone side)
HU_DUMMY = {
    "ip": "192.168.178.87",
    "hci": "hci1",
    "bd": "C8:C9:A3:CB:37:96",
    "role": "hu_dummy",
}
PHONE = {
    "ip": "192.168.178.131",
    "hci": "hci2",
    "bd": "C8:C9:A3:CB:7B:0A",
    "role": "phone_side",
}
RFCOMM_CHANNEL = 5


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ssh(remote: str, timeout: float = 60.0, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run one remote shell command string (must be a single argv for OpenSSH)."""
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
        DEFAULT_SSH,
        remote,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input_text)


def frame_event(ts_us: int, direction: str, frame, chunk_i: int | None = None) -> dict:
    return {
        "t_us": ts_us,
        "direction": direction,
        "chunk_i": chunk_i,
        "cmd": frame.cmd,
        "cmd_name": cmd_desk_name(frame.cmd),
        "src": frame.src,
        "dest": frame.dest,
        "dest_label": dest_desk_label(frame.dest),
        "len": frame.length,
        "payload_hex": frame.payload.hex(),
        "raw_hex": frame.raw.hex(),
    }


def run_offline() -> dict:
    stream = build_ca_c1_lab_bcl_stream()
    t0 = time.time_ns() // 1000
    events: list[dict] = []
    fr = BclFramer()
    frames_all = []
    last_error = None

    for i, chunk in enumerate(iter_chunks(stream, CA_C1_LAB_CHUNKS)):
        r = fr.feed(chunk)
        ts = t0 + i * 1000
        for f in r.frames:
            frames_all.append(f)
            events.append(frame_event(ts, "hu_dummy→phone", f, chunk_i=i))
        if r.error:
            last_error = {
                "t_us": ts,
                "error_code": int(r.error_code),
                "error_name": r.error_code.name,
                "error_detail": r.error_detail,
                "chunk_i": i,
            }
            events.append({"t_us": ts, "direction": "hu_dummy→phone", "chunk_i": i, **last_error})
            break

    # Reference: one-shot feed must match until error
    ref_frames, ref_last = feed_chunked(stream, (len(stream),))
    ok = (
        len(frames_all) == 3
        and frames_all[0].cmd == 4
        and frames_all[1].payload == b"SYNTH01"
        and frames_all[2].cmd == 0x00EE
        and last_error is not None
        and last_error["error_code"] == int(BclParseError.PAYLOAD_TOO_LARGE)
        and len(ref_frames) == 3
        and ref_last.error
    )

    return {
        "mode": "offline",
        "ok": ok,
        "stream_bytes": len(stream),
        "stream_hex": stream.hex(),
        "chunk_sizes": list(CA_C1_LAB_CHUNKS),
        "frames": [f.as_dict() for f in frames_all],
        "frame_count": len(frames_all),
        "error": last_error,
        "checks": {
            "handshake_cmd4": frames_all[0].cmd == 4 if frames_all else False,
            "data_synth01": frames_all[1].payload == b"SYNTH01" if len(frames_all) > 1 else False,
            "unknown_cmd_ee": frames_all[2].cmd == 0x00EE if len(frames_all) > 2 else False,
            "payload_too_large": last_error is not None
            and last_error["error_code"] == int(BclParseError.PAYLOAD_TOO_LARGE),
            "oneshot_matches_chunked_count": len(ref_frames) == len(frames_all),
        },
        "events": events,
        "epistemic": {
            "source": "synthetic",
            "evidence_level": "TEST",
            "direct_observation": False,
            "claim": "BCL framer mechanics + fragmentation; not BMW wire FACT",
        },
    }


_RFCOMM_REMOTE = r'''
import json, socket, sys, threading, time

CHANNEL = int(sys.argv[1])
SERVER_BD = sys.argv[2]
CLIENT_BD = sys.argv[3]
STREAM_HEX = sys.argv[4]
SECONDS = float(sys.argv[5])

AF = socket.AF_BLUETOOTH
PROTO = socket.BTPROTO_RFCOMM
ANY = "00:00:00:00:00:00"
stream = bytes.fromhex(STREAM_HEX)
result = {"ok": False, "phase": "start", "rx_hex": "", "tx_len": 0, "error": None}


def bind_sock(bd, channel):
    s = socket.socket(AF, socket.SOCK_STREAM, PROTO)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(SECONDS)
    try:
        s.bind((bd, channel))
    except OSError as e:
        result.setdefault("bind_fallback", []).append(f"{bd}:{e}")
        s.bind((ANY, channel))
    return s


def server():
    try:
        srv = bind_sock(SERVER_BD, CHANNEL)
        srv.listen(1)
        result["phase"] = "listening"
        result["listening"] = True
        conn, addr = srv.accept()
        conn.settimeout(SECONDS)
        result["peer"] = str(addr)
        buf = b""
        while len(buf) < len(stream):
            chunk = conn.recv(min(4096, len(stream) - len(buf) or 1))
            if not chunk:
                break
            buf += chunk
        result["rx_hex"] = buf.hex()
        result["rx_len"] = len(buf)
        result["rx_ok"] = buf == stream
        conn.close()
        srv.close()
    except Exception as e:
        result["server_err"] = repr(e)


th = threading.Thread(target=server, daemon=True)
th.start()
time.sleep(0.4)

try:
    cli = bind_sock(CLIENT_BD, 0)
    result["phase"] = "connecting"
    deadline = time.time() + SECONDS
    last_err = None
    while time.time() < deadline:
        try:
            cli.connect((SERVER_BD, CHANNEL))
            last_err = None
            break
        except OSError as e:
            last_err = str(e)
            time.sleep(0.3)
    if last_err is not None and "connected" not in result:
        # connect may have succeeded on last try; check via send
        try:
            cli.getpeername()
            last_err = None
        except OSError:
            result["error"] = f"connect_timeout:{last_err}"
            result["phase"] = "connect_fail"
            print(json.dumps(result))
            raise SystemExit(2)
    result["phase"] = "transfer"
    cli.sendall(stream)
    result["tx_len"] = len(stream)
    result["connected"] = True
    cli.close()
except Exception as e:
    result["client_err"] = repr(e)
    result["phase"] = "exception"

th.join(timeout=SECONDS)
result["ok"] = bool(result.get("rx_ok"))
result["phase"] = "done" if result["ok"] else result.get("phase", "fail")
print(json.dumps(result))
'''


def prep_rfcomm_adapters() -> dict:
    """Power/discoverable both adapters; alias HU-dummy. SDP optional (known channel)."""
    from lab_bcl_dummy_hu_sdp import prep_adapter

    steps = {}
    for side in (HU_DUMMY, PHONE):
        alias = "BCL-HU-Dummy" if side is HU_DUMMY else "BCL-Phone"
        steps[f"btctl_{side['role']}"] = prep_adapter(side, alias)

    # Best-effort Serial Port SDP on HU-dummy (may fail on virtual HCI — channel still works).
    sdp_cmd = (
        f"sdptool -i {HU_DUMMY['hci']} add --channel={RFCOMM_CHANNEL} SP 2>&1 || true"
    )
    p = ssh(f"bash -lc {shlex.quote(sdp_cmd)}", timeout=15)
    out = p.stdout or ""
    steps["sdp_add_sp"] = {
        "ok": "Service record" in out,
        "stdout": out[-400:],
        "note": "optional; RFCOMM uses known channel without SDP",
    }
    return steps


def run_rfcomm(seconds: float) -> dict:
    stream = build_ca_c1_lab_bcl_stream()
    prep = prep_rfcomm_adapters()

    cap_dir = f"/tmp/bcl_synth_{utc_stamp()}"
    ssh(f"bash -lc {shlex.quote(f'mkdir -p {cap_dir}')}", timeout=10)
    btmon_cmd = (
        f"btmon -i {HU_DUMMY['hci']} -w {cap_dir}/hu.btsnoop >/dev/null 2>&1 & "
        f"btmon -i {PHONE['hci']} -w {cap_dir}/phone.btsnoop >/dev/null 2>&1 & "
        f"sleep 0.3; echo ok"
    )
    ssh(f"bash -lc {shlex.quote(btmon_cmd)}", timeout=10)

    # Upload remote script via scp (argv must be reliable; stdin-as-script was fragile).
    remote_path = "/tmp/bcl_rfcomm_xfer.py"
    local_tmp = Path("/tmp/bcl_rfcomm_xfer.py")
    local_tmp.write_text(_RFCOMM_REMOTE)
    scp = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=accept-new",
            str(local_tmp),
            f"{DEFAULT_SSH}:{remote_path}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if scp.returncode != 0:
        return {
            "mode": "rfcomm",
            "ok": False,
            "transport_ok": False,
            "decode_ok": False,
            "error": {"error_detail": f"scp_failed: {(scp.stderr or scp.stdout)[-400:]}"},
            "prep": prep,
            "stream_bytes": len(stream),
            "frames": [],
            "capture_dir_host": cap_dir,
            "epistemic": {
                "source": "synthetic",
                "evidence_level": "TEST",
                "direct_observation": False,
                "claim": "RFCOMM path can carry synthetic BCL; not BMW service FACT",
            },
        }

    cmd = (
        f"python3 {remote_path} {RFCOMM_CHANNEL} {HU_DUMMY['bd']} {PHONE['bd']} "
        f"{stream.hex()} {seconds}"
    )
    p = ssh(f"bash -lc {shlex.quote(cmd)}", timeout=seconds + 45)
    try:
        lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip().startswith("{")]
        remote_result = json.loads(lines[-1]) if lines else {
            "ok": False,
            "error": "no_json",
            "stdout": (p.stdout or "")[-800:],
            "stderr": (p.stderr or "")[-800:],
            "returncode": p.returncode,
        }
    except Exception as exc:  # noqa: BLE001
        remote_result = {
            "ok": False,
            "error": f"parse_remote: {exc}",
            "stdout": (p.stdout or "")[-1000:],
            "stderr": (p.stderr or "")[-1000:],
            "returncode": p.returncode,
        }

    rx = bytes.fromhex(remote_result.get("rx_hex") or "")
    frames, last = feed_chunked(rx, CA_C1_LAB_CHUNKS) if rx else ([], None)
    decode_ok = (
        len(frames) == 3
        and frames[1].payload == b"SYNTH01"
        and last is not None
        and last.error
        and last.error_code == BclParseError.PAYLOAD_TOO_LARGE
    )

    ssh("bash -lc " + shlex.quote("pkill -f 'btmon -i hci[12] -w /tmp/bcl_synth_' || true"), timeout=10)

    return {
        "mode": "rfcomm",
        "ok": bool(remote_result.get("ok")) and decode_ok,
        "transport_ok": bool(remote_result.get("ok")),
        "decode_ok": decode_ok,
        "hu_dummy": HU_DUMMY,
        "phone_side": PHONE,
        "rfcomm_channel": RFCOMM_CHANNEL,
        "prep": prep,
        "remote": remote_result,
        "stream_bytes": len(stream),
        "frame_count": len(frames),
        "frames": [f.as_dict() for f in frames],
        "error": {
            "error_code": int(last.error_code) if last and last.error else None,
            "error_detail": last.error_detail if last else None,
        },
        "capture_dir_host": cap_dir,
        "epistemic": {
            "source": "synthetic",
            "evidence_level": "TEST",
            "direct_observation": False,
            "claim": "RFCOMM path can carry synthetic BCL; not BMW service FACT",
        },
    }


def write_evidence(result: dict) -> tuple[Path, Path]:
    stamp = utc_stamp()
    base = f"LAB_BCL_SYNTH_STREAM_{stamp}"
    js = EVIDENCE / f"{base}.json"
    md = EVIDENCE / f"{base}.md"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(result, indent=2) + "\n")

    frames = result.get("frames") or []
    lines = [
        f"# LAB BCL synthetic stream — {'PASS' if result.get('ok') else 'FAIL'}",
        "",
        f"**UTC:** {stamp} · mode `{result.get('mode')}` · claim: decoder/messkette TEST only",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| overall | {'PASS' if result.get('ok') else 'FAIL'} |",
        f"| stream_bytes | {result.get('stream_bytes')} |",
        f"| frames_decoded | {result.get('frame_count', len(frames))} |",
    ]
    if result.get("mode") == "offline":
        for k, v in (result.get("checks") or {}).items():
            lines.append(f"| {k} | {'PASS' if v else 'FAIL'} |")
    else:
        lines.append(f"| transport_ok | {'PASS' if result.get('transport_ok') else 'FAIL'} |")
        lines.append(f"| decode_ok | {'PASS' if result.get('decode_ok') else 'FAIL'} |")
        lines.append(f"| RFCOMM channel | {result.get('rfcomm_channel')} |")
        lines.append(f"| capture on host | `{result.get('capture_dir_host')}` |")

    lines += [
        "",
        "## Frames",
        "",
    ]
    for i, f in enumerate(frames):
        label = f.get("dest_label") or "-"
        lines.append(
            f"- [{i}] cmd={f.get('cmd_name')}({f.get('cmd')}) "
            f"src={f.get('src')} dest={f.get('dest')}({label}) "
            f"len={f.get('len')} payload=`{f.get('payload_hex')}`"
        )
    err = result.get("error")
    if err:
        lines += ["", f"**Terminal error (expected for lab stream):** `{err}`", ""]
    lines += [
        "## Epistemic boundary",
        "",
        "```text",
        "YES:  synthetic BCL bytes → framer → JSONL events",
        "YES:  fragmentation / PayloadTooLarge sticky error",
        "NO:   BMW HU / Connected app wire claim",
        "```",
        "",
        "Next: Dummy-HU SDP/RFCOMM with known service, then A6/B1 on real HU.",
        "",
    ]
    md.write_text("\n".join(lines))
    return js, md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("offline", "rfcomm"), default="offline")
    ap.add_argument("--seconds", type=float, default=25.0, help="RFCOMM timeout budget")
    ap.add_argument("--no-evidence", action="store_true")
    args = ap.parse_args()

    if args.mode == "offline":
        result = run_offline()
    else:
        result = run_rfcomm(args.seconds)

    paths = None
    if not args.no_evidence:
        paths = write_evidence(result)

    print(json.dumps({k: result[k] for k in result if k != "events"}, indent=2))
    if paths:
        print(f"\nevidence: {paths[0]}\n          {paths[1]}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
