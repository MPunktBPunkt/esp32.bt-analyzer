#!/usr/bin/env python3
"""Runs on .108 next to bcl_framer.py / bcl_dummy_hu.py (uploaded by lab scripts).

  hu              Register SPP server via ProfileManager1, keep each RFCOMM fd open,
                  answer session init with HANDSHAKE (lab B0.7), log frames as JSONL.
  hu-observe / b2b
                  Same registration, but **never TX** (B2-B field). tx_allowed=false.
  phone           Synthetic BclCarLink-like RFCOMM client (sends INIT_MAGIC).
  phone-observe / b2a
                  RFCOMM connect to peer channel; **recv only** (no BCL TX).

Needs python3-gi + python3-dbus for hu modes. Epistemic: TEST/field capture only.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bcl_classify import classify_bytes  # noqa: E402
from bcl_dummy_hu import (  # noqa: E402
    SESSION_INIT_INTERVAL_S,
    WATCHDOG_INTERVAL_S,
    DummyHuSession,
    ObserveOnlySession,
    PhoneClientSession,
)

SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"


class JsonlLog:
    def __init__(self, path: str) -> None:
        self._fh = open(path, "a", buffering=1)

    def write(self, event: dict, **extra) -> None:
        self._fh.write(json.dumps({"ts": round(time.time(), 3), **event, **extra}) + "\n")


def _flush_events(log: JsonlLog, session, sent: int, **extra) -> int:
    for ev in session.events[sent:]:
        log.write(ev, **extra)
    return len(session.events)


def device_from_path(path: str) -> dict:
    """/org/bluez/hci2/dev_AA_BB_CC_DD_EE_FF → adapter + BD."""
    parts = str(path).split("/")
    adapter = next((p for p in parts if p.startswith("hci")), None)
    dev = next((p for p in parts if p.startswith("dev_")), "")
    return {"adapter": adapter, "peer": dev[4:].replace("_", ":") or None}


def run_hu(args: argparse.Namespace, *, observe_only: bool) -> int:
    import dbus
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib

    log = JsonlLog(args.log)
    session_id = args.session_id or str(uuid.uuid4())
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    loop = GLib.MainLoop()
    conns: dict[int, dict] = {}
    tx_forbidden = observe_only

    meta = {
        "session_id": session_id,
        "mode": "B2-B" if observe_only else "lab_hu",
        "tx_allowed": not observe_only,
        "bcl_tx_enabled": not observe_only,
        "origin": args.origin,
        "source": args.source,
    }
    log.write({"event": "session_start", **meta})

    def close(fd: int, reason: str) -> None:
        c = conns.pop(fd, None)
        if c is None:
            return
        raw = c.get("rx_raw", b"")
        cls = classify_bytes(raw)
        log.write(
            {
                "event": "rfcomm_closed",
                "reason": reason,
                "rx_total": len(raw),
                "bcl_classification": cls["bcl_classification"],
                "classification": cls,
            },
            **c["dev"],
            session_id=session_id,
        )
        try:
            os.close(fd)
        except OSError:
            pass

    def on_readable(fd: int, cond) -> bool:
        c = conns.get(fd)
        if c is None:
            return False
        try:
            data = os.read(fd, 4096) if cond & GLib.IO_IN else b""
        except OSError as exc:
            close(fd, f"read_error:{exc.errno}")
            return False
        if not data:
            close(fd, "eof")
            return False
        c["rx_raw"] = c.get("rx_raw", b"") + data
        sess = c["session"]
        log.write(
            {
                "event": "rx_bytes",
                "n": len(data),
                "hex": data.hex(),
                "rx_total": len(c["rx_raw"]),
            },
            **c["dev"],
            session_id=session_id,
        )
        replies = sess.on_bytes(data)
        c["sent"] = _flush_events(log, sess, c["sent"], **c["dev"], session_id=session_id)
        if replies and tx_forbidden:
            log.write(
                {
                    "event": "tx_blocked",
                    "error": "observe_only_forbids_tx",
                    "would_send_n": sum(len(r) for r in replies),
                },
                **c["dev"],
                session_id=session_id,
            )
            close(fd, "tx_blocked_observe_only")
            return False
        for r in replies:
            try:
                os.write(fd, r)
                log.write(
                    {"event": "tx_bytes", "n": len(r), "hex": r.hex()},
                    **c["dev"],
                    session_id=session_id,
                )
            except OSError as exc:
                close(fd, f"write_error:{exc.errno}")
                return False
        return True

    class Profile(dbus.service.Object):
        @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
        def Release(self):
            log.write({"event": "profile_released", "session_id": session_id})

        @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
        def NewConnection(self, device, fd, properties):
            fd = fd.take()
            dev = device_from_path(device)
            session = (
                ObserveOnlySession()
                if observe_only
                else DummyHuSession(
                    version=args.hu_version, echo_watchdog=args.echo_watchdog
                )
            )
            conns[fd] = {
                "dev": dev,
                "session": session,
                "sent": 0,
                "rx_raw": b"",
            }
            log.write(
                {
                    "event": "rfcomm_connected",
                    "tx_allowed": not observe_only,
                    "props": {str(k): str(v) for k, v in dict(properties).items()},
                },
                **dev,
                session_id=session_id,
            )
            GLib.io_add_watch(fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, on_readable)

        @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
        def RequestDisconnection(self, device):
            dev = device_from_path(device)
            for fd, c in list(conns.items()):
                if c["dev"] == dev:
                    close(fd, "request_disconnection")

    try:
        bus.request_name("org.btanalyzer.BclDummyHu")
    except dbus.DBusException as exc:
        log.write({"event": "name_warn", "error": str(exc), "session_id": session_id})
    path = "/org/bluez/bcl_dummy_hu"
    Profile(bus, path)
    pm = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
    try:
        pm.UnregisterProfile(path)
    except dbus.DBusException:
        pass
    pm.RegisterProfile(
        path,
        SPP_UUID,
        {
            "Name": args.name,
            "Service": SPP_UUID,
            "Role": "server",
            "Channel": dbus.UInt16(args.channel),
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "AutoConnect": False,
        },
    )
    log.write(
        {
            "event": "profile_registered",
            "channel": args.channel,
            "name": args.name,
            "uuid": SPP_UUID,
            "hu_version": args.hu_version,
            "echo_watchdog": args.echo_watchdog,
            "observe_only": observe_only,
            **meta,
        }
    )
    if args.ready:
        Path(args.ready).write_text("registered\n")

    def stop(*_a) -> bool:
        for fd in list(conns):
            close(fd, "agent_stop")
        try:
            pm.UnregisterProfile(path)
        except dbus.DBusException:
            pass
        log.write({"event": "agent_stopped", "session_id": session_id})
        loop.quit()
        return False

    GLib.timeout_add_seconds(max(1, int(args.hold)), stop)
    signal.signal(signal.SIGTERM, lambda *_a: GLib.idle_add(stop))
    signal.signal(signal.SIGINT, lambda *_a: GLib.idle_add(stop))
    loop.run()
    return 0


def run_phone(args: argparse.Namespace, *, observe_only: bool) -> int:
    log = JsonlLog(args.log)
    session_id = args.session_id or str(uuid.uuid4())
    meta = {
        "session_id": session_id,
        "mode": "B2-A" if observe_only else "lab_phone",
        "tx_allowed": not observe_only,
        "bcl_tx_enabled": not observe_only,
        "origin": args.origin,
        "source": args.source,
        "peer": args.hu_bd,
        "channel": args.channel,
    }
    log.write({"event": "session_start", **meta})
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        sock.bind((args.adapter_bd, 0))
        sock.settimeout(15)
        sock.connect((args.hu_bd, args.channel))
    except OSError as exc:
        log.write({"event": "rfcomm_connect_failed", "error": repr(exc), **meta})
        return 2
    log.write({"event": "rfcomm_connected", **meta})
    sock.settimeout(0.2)

    sess = None if observe_only else PhoneClientSession()
    sent = 0
    rx_raw = b""
    end = time.time() + args.seconds
    next_init = 0.0
    next_ping = 0.0
    last_rx = time.time()
    hs_logged = False
    while time.time() < end:
        now = time.time()
        if not observe_only and sess is not None:
            if sess.handshake is None and now >= next_init:
                sock.sendall(sess.session_init())
                next_init = now + SESSION_INIT_INTERVAL_S
            if sess.active and now >= next_ping:
                sock.sendall(sess.watchdog_ping())
                log.write({"event": "watchdog_ping", "session_id": session_id})
                next_ping = now + WATCHDOG_INTERVAL_S
        try:
            data = sock.recv(4096)
        except socket.timeout:
            data = None
        except OSError as exc:
            log.write({"event": "rfcomm_closed", "reason": repr(exc), "session_id": session_id})
            break
        if data == b"":
            log.write({"event": "rfcomm_closed", "reason": "eof", "session_id": session_id})
            break
        if data:
            last_rx = now
            rx_raw += data
            log.write(
                {
                    "event": "rx_bytes",
                    "n": len(data),
                    "hex": data.hex(),
                    "rx_total": len(rx_raw),
                    "session_id": session_id,
                }
            )
            if not observe_only and sess is not None:
                for out in sess.on_bytes(data):
                    sock.sendall(out)
                    log.write(
                        {
                            "event": "tx_bytes",
                            "n": len(out),
                            "hex": out.hex(),
                            "session_id": session_id,
                        }
                    )
                if sess.handshake and not hs_logged:
                    log.write(
                        {"event": "handshake_rx", **sess.handshake, "session_id": session_id}
                    )
                    hs_logged = True
                sent = _flush_events(log, sess, sent, session_id=session_id)
    if not observe_only and sess is not None:
        _flush_events(log, sess, sent, session_id=session_id)
    cls = classify_bytes(rx_raw)
    log.write(
        {
            "event": "phone_done",
            "active": bool(sess and sess.active) if not observe_only else False,
            "rx_silence_s": round(time.time() - last_rx, 1),
            "rx_total": len(rx_raw),
            "bcl_classification": cls["bcl_classification"],
            "classification": cls,
            **meta,
        }
    )
    sock.close()
    if observe_only:
        return 0 if len(rx_raw) >= 0 else 1  # connect success already returned 2
    return 0 if sess and sess.active else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    def add_hu(p: argparse.ArgumentParser) -> None:
        p.add_argument("--channel", type=int, default=5)
        p.add_argument("--name", default="BMW Connected")
        p.add_argument("--hu-version", type=int, default=3)
        p.add_argument("--echo-watchdog", action="store_true")
        p.add_argument("--hold", type=float, default=120.0)
        p.add_argument("--log", required=True)
        p.add_argument("--ready")
        p.add_argument("--session-id", default="")
        p.add_argument("--origin", default="dummy_hu")
        p.add_argument("--source", default="lab")

    hu = sub.add_parser("hu", help="lab Dummy-HU (answers HANDSHAKE)")
    add_hu(hu)
    b2b = sub.add_parser("b2b", help="B2-B observe-only SPP server (no BCL TX)")
    add_hu(b2b)
    b2b_alias = sub.add_parser("hu-observe", help="alias for b2b")
    add_hu(b2b_alias)

    def add_phone(p: argparse.ArgumentParser) -> None:
        p.add_argument("--adapter-bd", required=True)
        p.add_argument("--hu-bd", required=True)
        p.add_argument("--channel", type=int, default=5)
        p.add_argument("--seconds", type=float, default=25.0)
        p.add_argument("--log", required=True)
        p.add_argument("--session-id", default="")
        p.add_argument("--origin", default="bclcarlink")
        p.add_argument("--source", default="lab")

    ph = sub.add_parser("phone", help="lab BclCarLink-like client (sends INIT)")
    add_phone(ph)
    b2a = sub.add_parser("b2a", help="B2-A RFCOMM connect, recv-only (no BCL TX)")
    add_phone(b2a)
    b2a_alias = sub.add_parser("phone-observe", help="alias for b2a")
    add_phone(b2a_alias)

    args = ap.parse_args()
    if args.mode == "hu":
        return run_hu(args, observe_only=False)
    if args.mode in ("b2b", "hu-observe"):
        if args.source == "lab":
            args.source = "field"
        if args.origin == "dummy_hu":
            args.origin = "f20"
        return run_hu(args, observe_only=True)
    if args.mode == "phone":
        return run_phone(args, observe_only=False)
    if args.mode in ("b2a", "phone-observe"):
        if args.source == "lab":
            args.source = "field"
        if args.origin == "bclcarlink":
            args.origin = "f20"
        return run_phone(args, observe_only=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
