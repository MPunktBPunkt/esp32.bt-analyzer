#!/usr/bin/env python3
"""Logged B3 tcp-lab test: PhoneClientSession ↔ B3 ↔ f20_sim DummyHuSession.

Produces JSONL + SUMMARY under --out. Claim: LAB only.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from bcl_dummy_hu import DummyHuSession, PhoneClientSession, apply_hu_profile  # noqa: E402


def log_jsonl(path: Path, obj: dict) -> None:
    with path.open("a") as fh:
        fh.write(json.dumps(obj, default=str) + "\n")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seconds", type=float, default=25.0)
    ap.add_argument("--listen", default="127.0.0.1:9701")
    ap.add_argument("--hu", default="127.0.0.1:9702")
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(exist_ok=True)

    # --- HU process ---
    hu_py = r"""
import json, socket, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from bcl_dummy_hu import DummyHuSession, apply_hu_profile
out = Path(sys.argv[2])
host, _, port = sys.argv[3].rpartition(":")
prof = apply_hu_profile("f20_sim")
sess = DummyHuSession(
    version=int(prof["version"]),
    instance_id=int(prof["instance_id"]),
    buffer_size=int(prof["buffer_size"]),
    echo_watchdog=True,
    send_dataack=True,
    etch_stub=True,
    sas_probe=str(prof["sas_probe"]),
    etch_reply_src=prof.get("etch_reply_src"),
)
def L(o):
    with (out / "hu.jsonl").open("a") as f:
        f.write(json.dumps(o, default=str) + "\n")
srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((host or "127.0.0.1", int(port)))
srv.listen(1)
(out / "hu.ready").write_text("ok\n")
L({"event": "tcp_hu_listen", "addr": sys.argv[3], "profile": "f20_sim"})
srv.settimeout(120)
c, addr = srv.accept()
L({"event": "tcp_hu_accept", "peer": list(addr)})
c.settimeout(0.4)
t_end = time.time() + float(sys.argv[4])
while time.time() < t_end:
    try:
        data = c.recv(8192)
    except socket.timeout:
        data = b""
    except Exception as e:
        L({"event": "hu_err", "error": str(e)})
        break
    if data:
        L({"event": "rx", "n": len(data), "hex_head": data[:64].hex()})
        for chunk in sess.on_bytes(data):
            if chunk:
                c.sendall(chunk)
                L({"event": "tx", "n": len(chunk), "hex_head": chunk[:64].hex()})
    else:
        time.sleep(0.02)
L({"event": "hu_done", "sess_event_n": len(sess.events)})
for e in sess.events:
    L({"event": "sess", "inner": e.get("event"), "cmd_name": e.get("cmd_name"),
       "dir": e.get("dir"), "method": e.get("method"), "src": e.get("src"), "dest": e.get("dest")})
try:
    c.close()
except Exception:
    pass
srv.close()
"""
    hu = subprocess.Popen(
        [sys.executable, "-c", hu_py, str(TOOLS), str(out), args.hu, str(args.seconds + 30)],
        stdout=(out / "hu.out").open("w"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(50):
        if (out / "hu.ready").exists():
            break
        time.sleep(0.1)
    if not (out / "hu.ready").exists():
        print("FAIL: HU not ready", file=sys.stderr)
        hu.kill()
        return 1

    # --- B3 ---
    b3 = subprocess.Popen(
        [
            sys.executable,
            str(TOOLS / "b3_rfcomm_relay.py"),
            "tcp-lab",
            "--listen",
            args.listen,
            "--connect",
            args.hu,
            "--log",
            str(out / "b3.jsonl"),
            "--raw-dir",
            str(out / "raw"),
            "--max-s",
            str(args.seconds + 20),
        ],
        cwd=str(TOOLS),
        stdout=(out / "b3.out").open("w"),
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": str(TOOLS)},
    )
    time.sleep(0.4)
    if b3.poll() is not None:
        print("FAIL: B3 exited", (out / "b3.out").read_text(), file=sys.stderr)
        hu.kill()
        return 1

    # --- Phone ---
    host, _, port_s = args.listen.rpartition(":")
    sock = socket.create_connection((host or "127.0.0.1", int(port_s)), timeout=5)
    sock.settimeout(0.5)
    phone = PhoneClientSession(
        selectproto=4,
        knock_payload="wire_v5",
        mybmw_sim=True,
    )
    log_jsonl(out / "phone.jsonl", {"event": "phone_start", "peer": args.listen})
    tx: list[bytes] = [phone.session_init()]
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        for chunk in tx:
            if isinstance(chunk, (bytes, bytearray)) and chunk:
                sock.sendall(chunk)
                log_jsonl(
                    out / "phone.jsonl",
                    {"event": "tx", "n": len(chunk), "hex_head": bytes(chunk)[:48].hex()},
                )
        tx = []
        try:
            data = sock.recv(8192)
        except socket.timeout:
            data = b""
        if data:
            log_jsonl(
                out / "phone.jsonl",
                {"event": "rx", "n": len(data), "hex_head": data[:48].hex()},
            )
            tx.extend(phone.on_bytes(data))
        else:
            if phone.active:
                try:
                    ping = phone.watchdog_ping()
                    if isinstance(ping, (bytes, bytearray)) and ping:
                        tx.append(bytes(ping))
                except Exception:
                    pass
            time.sleep(0.05)
        # stop early if we saw meaningful etch traffic in phone events
        ev = [e.get("event") for e in phone.events]
        if ev.count("frame") > 15 or any(
            "sas" in str(e.get("event", "")).lower() or e.get("cmd_name") == "DATA"
            for e in phone.events[-5:]
        ):
            # keep going a bit for SAS
            pass
        snap = phone.forensic_snapshot() if hasattr(phone, "forensic_snapshot") else {}
        if snap.get("auth_state") in ("AUTHENTICATED", "LOGIN_SENT") or getattr(
            phone, "_auth_state", None
        ) in ("AUTHENTICATED",):
            log_jsonl(out / "phone.jsonl", {"event": "early_stop", "snap": snap})
            break

    for e in phone.events:
        log_jsonl(
            out / "phone.jsonl",
            {
                "event": "sess",
                "inner": e.get("event"),
                "cmd_name": e.get("cmd_name"),
                "method": e.get("method"),
                "src": e.get("src"),
                "dest": e.get("dest"),
            },
        )
    try:
        sock.close()
    except OSError:
        pass

    time.sleep(1)
    b3.send_signal(signal.SIGINT)
    try:
        b3.wait(timeout=8)
    except subprocess.TimeoutExpired:
        b3.kill()
    try:
        hu.wait(timeout=8)
    except subprocess.TimeoutExpired:
        hu.kill()

    def load_events(path: Path) -> list[str]:
        if not path.exists():
            return []
        out_e = []
        for ln in path.read_text().splitlines():
            try:
                out_e.append(json.loads(ln).get("event"))
            except json.JSONDecodeError:
                pass
        return out_e

    b3_ev = load_events(out / "b3.jsonl")
    hu_ev = load_events(out / "hu.jsonl")
    phone_ev = load_events(out / "phone.jsonl")
    b3c, huc, pc = Counter(b3_ev), Counter(hu_ev), Counter(phone_ev)

    etch_methods = []
    if (out / "b3.jsonl").exists():
        for ln in (out / "b3.jsonl").read_text().splitlines():
            try:
                o = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if o.get("event") == "etch" and o.get("method"):
                etch_methods.append(o["method"])

    ok = (
        b3c.get("handshake", 0) >= 1
        and b3c.get("bcl_frame", 0) >= 5
        and b3c.get("accepted", 0) >= 1
        and huc.get("tcp_hu_accept", 0) >= 1
    )
    summary = {
        "ok": ok,
        "claim": "LAB",
        "b3": dict(b3c),
        "hu": dict(huc),
        "phone": dict(pc),
        "etch_methods": etch_methods[:40],
        "etch_method_counts": dict(Counter(etch_methods)),
        "b3_rc": b3.returncode,
        "hu_rc": hu.returncode,
        "raw_files": [p.name for p in (out / "raw").glob("*")],
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    md = [
        "# B3 tcp-lab logged test",
        "",
        f"- **ok:** {ok}",
        f"- claim: **LAB**",
        f"- handshake: {b3c.get('handshake', 0)}",
        f"- bcl_frames: {b3c.get('bcl_frame', 0)}",
        f"- etch events: {b3c.get('etch', 0)}",
        f"- etch methods: `{dict(Counter(etch_methods))}`",
        f"- raw: {summary['raw_files']}",
        "",
        "What was logged: BCL INIT/HS/frames, Etch methods + mid correlation, raw bin both dirs.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(md))
    print("\n".join(md))
    print(json.dumps({k: summary[k] for k in ("ok", "etch_method_counts", "b3")}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
