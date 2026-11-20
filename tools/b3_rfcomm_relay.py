#!/usr/bin/env python3
"""B3 transparent RFCOMM/TCP relay — byte-exact copy + BCL/Etch decode.

Design rules (gate doc):
  - Copy bytes 1:1; never mutate SAS/BCL/Etch payloads
  - Preserve BCL src/dest
  - Decode Etch methods/hashes; correlate _messageId / _inReplyTo
  - Log both directions to JSONL + optional raw .bin

Modes:
  tcp-lab   Listen on --listen, connect to --connect (unit/lab soak of relay logic)
  rfcomm    AF_BLUETOOTH RFCOMM: accept on --listen-channel, connect to --peer/--peer-channel
            (run on .108 host when Phone↔.131↔.87 path is wired)

Epistemic:
  LAB when tcp-lab or loopback. FIELD only when live Phone↔F20 bytes pass through.

Usage:
  # Lab self-test (bytes identity + decode)
  PYTHONPATH=tools python3 tools/b3_rfcomm_relay.py selftest --out /tmp/b3_selftest

  # TCP relay
  PYTHONPATH=tools python3 tools/b3_rfcomm_relay.py tcp-lab \\
    --listen 127.0.0.1:9701 --connect 127.0.0.1:9702 --log /tmp/b3.jsonl
"""

from __future__ import annotations

import argparse
import json
import select
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_framer import (  # noqa: E402
    DEST_ETCH_DESK,
    INIT_MAGIC,
    BclFramer,
    cmd_desk_name,
    dest_desk_label,
)
from etch_codec import decode_etch_message  # noqa: E402


CMD_DATA = 2
CMD_HANDSHAKE = 4


@dataclass
class SideState:
    name: str
    framer: BclFramer = field(default_factory=BclFramer)
    bytes_total: int = 0
    frames: int = 0
    etch_msgs: int = 0
    open_mids: dict[int, dict[str, Any]] = field(default_factory=dict)
    correlated: int = 0


class RelayLogger:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._fh: BinaryIO | None = None
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = path.open("ab")
        self.lock = threading.Lock()

    def write(self, obj: dict[str, Any]) -> None:
        line = (json.dumps(obj, default=str) + "\n").encode()
        with self.lock:
            if self._fh:
                self._fh.write(line)
                self._fh.flush()

    def close(self) -> None:
        with self.lock:
            if self._fh:
                self._fh.close()
                self._fh = None


def _decode_etch_side(st: SideState, payload: bytes, direction: str) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        dec = decode_etch_message(payload)
    except Exception as exc:  # noqa: BLE001
        return {"event": "etch_decode_error", "direction": direction, "error": str(exc)}
    fields = dec.get("fields") or {}
    raw = dec.get("raw_fields") or {}
    mid = fields.get("_messageId")
    if mid is None and isinstance(raw, dict):
        mid = raw.get("_messageId")
    irt = fields.get("_inReplyTo")
    if irt is None and isinstance(raw, dict):
        irt = raw.get("_inReplyTo")
    method = dec.get("method")
    entry: dict[str, Any] = {
        "event": "etch",
        "direction": direction,
        "method": method,
        "type_hash": dec.get("type_hash"),
        "messageId": mid,
        "inReplyTo": irt,
        "payload_len": len(payload),
    }
    # SAS pad cross-check fields (serial / challenge / login) — CASE A Test A
    if method in (
        "sas_certificate",
        "_result_sas_certificate",
        "sas_login",
        "_result_sas_login",
    ):
        try:
            from etch_codec import summarize_sas_wire_fields

            entry["sas"] = summarize_sas_wire_fields(str(method), raw if isinstance(raw, dict) else {})
        except Exception as exc:  # noqa: BLE001
            entry["sas_error"] = str(exc)
    if isinstance(mid, int) and method and not str(method).startswith("_result_"):
        st.open_mids[mid] = {"method": method, "ts": time.time()}
    if isinstance(irt, int) and irt in st.open_mids:
        entry["correlates_to"] = st.open_mids.pop(irt)
        st.correlated += 1
    # Cross-side correlation: peer may hold the open mid
    st.etch_msgs += 1
    return entry


def handle_chunk(
    st: SideState,
    peer: SideState,
    data: bytes,
    log: RelayLogger,
    *,
    raw_fh: BinaryIO | None = None,
) -> None:
    """Feed bytes into framer, emit decode events. Caller already forwarded raw bytes."""
    st.bytes_total += len(data)
    if raw_fh:
        raw_fh.write(data)
        raw_fh.flush()
    log.write(
        {
            "event": "bytes",
            "direction": f"{st.name}->{peer.name}",
            "n": len(data),
            "hex_head": data[:64].hex(),
        }
    )
    # INIT magic detection (session start)
    if INIT_MAGIC in data:
        log.write(
            {
                "event": "bcl_init_magic",
                "direction": f"{st.name}->{peer.name}",
                "count": data.count(INIT_MAGIC),
            }
        )
    fed = st.framer.feed(data)
    for fr in fed.frames:
        st.frames += 1
        rec: dict[str, Any] = {
            "event": "bcl_frame",
            "direction": f"{st.name}->{peer.name}",
            "cmd": fr.cmd,
            "cmd_name": cmd_desk_name(fr.cmd),
            "src": fr.src,
            "dest": fr.dest,
            "dest_label": dest_desk_label(fr.dest),
            "len": fr.length,
            "payload_hex_head": fr.payload[:48].hex(),
        }
        log.write(rec)
        if fr.cmd == CMD_HANDSHAKE and len(fr.payload) >= 8:
            # version u16, instanceId u16, bufferSize u32 — desk layout
            ver, iid, buf = struct.unpack(">HHI", fr.payload[:8])
            log.write(
                {
                    "event": "handshake",
                    "direction": f"{st.name}->{peer.name}",
                    "version": ver,
                    "instanceId": iid,
                    "bufferSize": buf,
                }
            )
        if fr.cmd == CMD_DATA and (
            fr.dest == DEST_ETCH_DESK or fr.src == DEST_ETCH_DESK or fr.dest in (10, 12, 18)
            or fr.src in (10, 12, 18)
        ):
            # Cross-correlate: open mids live on TX side; replies on peer
            etch = _decode_etch_side(st, fr.payload, f"{st.name}->{peer.name}")
            if etch:
                # Also try peer open_mids for inReplyTo
                irt = etch.get("inReplyTo")
                if isinstance(irt, int) and "correlates_to" not in etch:
                    if irt in peer.open_mids:
                        etch["correlates_to"] = peer.open_mids.pop(irt)
                        peer.correlated += 1
                    elif irt in st.open_mids:
                        etch["correlates_to"] = st.open_mids.pop(irt)
                        st.correlated += 1
                log.write(etch)


def pump_pair(
    a: socket.socket,
    b: socket.socket,
    log: RelayLogger,
    *,
    a_name: str = "phone",
    b_name: str = "hu",
    raw_dir: Path | None = None,
    idle_s: float = 0.2,
    max_s: float = 0.0,
) -> dict[str, Any]:
    """Bidirectional transparent copy until EOF/error/max_s."""
    sa, sb = SideState(a_name), SideState(b_name)
    raw_a = raw_b = None
    if raw_dir:
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_a = (raw_dir / f"{a_name}_to_{b_name}.bin").open("ab")
        raw_b = (raw_dir / f"{b_name}_to_{a_name}.bin").open("ab")
    t0 = time.time()
    log.write({"event": "relay_start", "a": a_name, "b": b_name, "ts": t0})
    try:
        a.setblocking(False)
        b.setblocking(False)
        while True:
            if max_s > 0 and (time.time() - t0) >= max_s:
                log.write({"event": "relay_max_time", "elapsed_s": round(time.time() - t0, 2)})
                break
            r, _, _ = select.select([a, b], [], [], idle_s)
            if not r:
                continue
            if a in r:
                try:
                    data = a.recv(4096)
                except OSError as exc:
                    log.write({"event": "socket_error", "side": a_name, "error": repr(exc)})
                    break
                if not data:
                    log.write({"event": "eof", "side": a_name})
                    break
                try:
                    b.sendall(data)  # transparent — no mutation
                except OSError as exc:
                    log.write({"event": "socket_error", "side": b_name, "error": repr(exc)})
                    break
                handle_chunk(sa, sb, data, log, raw_fh=raw_a)
            if b in r:
                try:
                    data = b.recv(4096)
                except OSError as exc:
                    log.write({"event": "socket_error", "side": b_name, "error": repr(exc)})
                    break
                if not data:
                    log.write({"event": "eof", "side": b_name})
                    break
                try:
                    a.sendall(data)
                except OSError as exc:
                    log.write({"event": "socket_error", "side": a_name, "error": repr(exc)})
                    break
                handle_chunk(sb, sa, data, log, raw_fh=raw_b)
    finally:
        for fh in (raw_a, raw_b):
            if fh:
                fh.close()
    summary = {
        "event": "relay_done",
        "elapsed_s": round(time.time() - t0, 3),
        a_name: {
            "bytes": sa.bytes_total,
            "frames": sa.frames,
            "etch_msgs": sa.etch_msgs,
            "correlated": sa.correlated,
        },
        b_name: {
            "bytes": sb.bytes_total,
            "frames": sb.frames,
            "etch_msgs": sb.etch_msgs,
            "correlated": sb.correlated,
        },
    }
    log.write(summary)
    return summary


def run_selftest(out: Path) -> int:
    """Prove byte-identity + BCL/Etch decode through a TCP relay."""
    from bcl_etch_stub import build_sas_challenge_payload
    from bcl_framer import build_synthetic_frame

    out.mkdir(parents=True, exist_ok=True)
    log = RelayLogger(out / "relay.jsonl")
    result_box: dict[str, Any] = {}

    challenge = build_sas_challenge_payload(
        challenge=b"\x11" * 16, in_reply_to=1, msg_id=2
    )
    stream = (
        INIT_MAGIC
        + build_synthetic_frame(CMD_HANDSHAKE, 0, 0, struct.pack(">HHI", 5, 14, 0x4000))
        + build_synthetic_frame(CMD_DATA, 10, DEST_ETCH_DESK, challenge)
    )

    # Topology: prod → rel_listen → pump → sink_srv
    # Avoid deadlock: accept sink in a thread before connecting prod.
    sink_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sink_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sink_srv.bind(("127.0.0.1", 0))
    sink_srv.listen(1)
    sink_port = sink_srv.getsockname()[1]

    rel_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rel_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rel_srv.bind(("127.0.0.1", 0))
    rel_srv.listen(1)
    rel_port = rel_srv.getsockname()[1]

    sink_box: list[socket.socket] = []

    def _accept_sink() -> None:
        c, _ = sink_srv.accept()
        sink_box.append(c)

    sink_th = threading.Thread(target=_accept_sink, daemon=True)
    sink_th.start()

    def _relay_main() -> None:
        phone_c, _ = rel_srv.accept()
        hu_c = socket.create_connection(("127.0.0.1", sink_port), timeout=2)
        try:
            result_box["summary"] = pump_pair(
                phone_c,
                hu_c,
                log,
                a_name="phone",
                b_name="hu",
                raw_dir=out / "raw",
                max_s=2.0,
            )
        finally:
            try:
                phone_c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                hu_c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            phone_c.close()
            hu_c.close()

    rt = threading.Thread(target=_relay_main, daemon=True)
    rt.start()

    prod = socket.create_connection(("127.0.0.1", rel_port), timeout=2)
    sink_th.join(timeout=2)
    if not sink_box:
        log.close()
        return 1
    sink = sink_box[0]
    sink.settimeout(2.0)
    prod.sendall(stream)
    try:
        prod.shutdown(socket.SHUT_WR)
    except OSError:
        pass

    got = b""
    try:
        while len(got) < len(stream):
            chunk = sink.recv(4096)
            if not chunk:
                break
            got += chunk
    except socket.timeout:
        pass

    prod.close()
    sink.close()
    rt.join(timeout=3)
    sink_srv.close()
    rel_srv.close()
    log.close()

    identity = got == stream
    report = {
        "byte_identity": identity,
        "sent": len(stream),
        "recv": len(got),
        "summary": result_box.get("summary"),
        "claim_level": "LAB",
        "note": "transparent relay selftest — not Field",
    }
    (out / "SELFTEST.json").write_text(json.dumps(report, indent=2) + "\n")
    md = [
        "# B3 Relay Selftest",
        "",
        f"- byte_identity: **{'PASS' if identity else 'FAIL'}**",
        f"- sent/recv: {len(stream)}/{len(got)}",
        f"- summary: `{json.dumps(result_box.get('summary'))}`",
        "",
        "Claim: LAB only.",
        "",
    ]
    (out / "SELFTEST.md").write_text("\n".join(md))
    print("\n".join(md))
    return 0 if identity else 1


def run_tcp_lab(args: argparse.Namespace) -> int:
    host, _, port_s = args.listen.rpartition(":")
    listen_port = int(port_s)
    chost, _, cport_s = args.connect.rpartition(":")
    connect_port = int(cport_s)
    log = RelayLogger(Path(args.log) if args.log else None)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host or "0.0.0.0", listen_port))
    srv.listen(1)
    log.write({"event": "listening", "addr": args.listen, "forward": args.connect})
    print(f"B3 tcp-lab listening {args.listen} → {args.connect}", flush=True)
    phone_c, addr = srv.accept()
    log.write({"event": "accepted", "peer": list(addr)})
    hu_c = socket.create_connection((chost, connect_port), timeout=10)
    raw = Path(args.raw_dir) if args.raw_dir else None
    try:
        pump_pair(
            phone_c,
            hu_c,
            log,
            a_name="phone",
            b_name="hu",
            raw_dir=raw,
            max_s=float(args.max_s or 0),
        )
    finally:
        phone_c.close()
        hu_c.close()
        srv.close()
        log.close()
    return 0


def run_rfcomm(args: argparse.Namespace) -> int:
    """Accept RFCOMM on listen-channel, connect outbound to peer channel; relay.

    Outbound socket is bound to --connect-adapter-bd (default: same as listen
    adapter) so dual-BlueZ hosts (.131 listen / .87 peer) use the right radio.
    """
    if not hasattr(socket, "AF_BLUETOOTH"):
        print("AF_BLUETOOTH unavailable", file=sys.stderr)
        return 2
    log = RelayLogger(Path(args.log) if args.log else None)
    connect_bd = (args.connect_adapter_bd or args.adapter_bd).strip()
    listen = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    listen.bind((args.adapter_bd, args.listen_channel))
    listen.listen(1)
    log.write(
        {
            "event": "rfcomm_listening",
            "adapter": args.adapter_bd,
            "channel": args.listen_channel,
            "connect_adapter": connect_bd,
            "peer": args.peer,
            "peer_channel": args.peer_channel,
            "claim_note": "FIELD only when live Phone↔F20 traffic",
        }
    )
    print(
        f"B3 rfcomm listen {args.adapter_bd} ch{args.listen_channel} "
        f"→ via {connect_bd} → {args.peer} ch{args.peer_channel}",
        flush=True,
    )
    phone_c, pinfo = listen.accept()
    log.write({"event": "rfcomm_accepted", "peer_info": repr(pinfo)})
    hu_c = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    # channel 0 = ephemeral local channel for outbound RFCOMM client
    hu_c.bind((connect_bd, 0))
    hu_c.connect((args.peer, args.peer_channel))
    log.write(
        {
            "event": "rfcomm_connected_hu",
            "peer": args.peer,
            "via_adapter": connect_bd,
        }
    )
    raw = Path(args.raw_dir) if args.raw_dir else None
    try:
        pump_pair(
            phone_c,
            hu_c,
            log,
            a_name="phone",
            b_name="hu",
            raw_dir=raw,
            max_s=float(args.max_s or 0),
        )
    finally:
        phone_c.close()
        hu_c.close()
        listen.close()
        log.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    st = sub.add_parser("selftest", help="LAB byte-identity + decode selftest")
    st.add_argument("--out", type=Path, required=True)

    tcp = sub.add_parser("tcp-lab", help="TCP transparent relay")
    tcp.add_argument("--listen", required=True, help="host:port accept phone side")
    tcp.add_argument("--connect", required=True, help="host:port HU side")
    tcp.add_argument("--log", default="")
    tcp.add_argument("--raw-dir", default="")
    tcp.add_argument("--max-s", type=float, default=0.0)

    rf = sub.add_parser("rfcomm", help="RFCOMM transparent relay (host BT)")
    rf.add_argument("--adapter-bd", required=True, help="local BD that phones connect to")
    rf.add_argument(
        "--connect-adapter-bd",
        default="",
        help="local BD for outbound RFCOMM to peer (default: --adapter-bd)",
    )
    rf.add_argument("--listen-channel", type=int, default=6)
    rf.add_argument("--peer", required=True, help="HU BD_ADDR")
    rf.add_argument("--peer-channel", type=int, default=6)
    rf.add_argument("--log", default="")
    rf.add_argument("--raw-dir", default="")
    rf.add_argument("--max-s", type=float, default=0.0)

    args = ap.parse_args()
    if args.mode == "selftest":
        return run_selftest(args.out)
    if args.mode == "tcp-lab":
        return run_tcp_lab(args)
    if args.mode == "rfcomm":
        return run_rfcomm(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
