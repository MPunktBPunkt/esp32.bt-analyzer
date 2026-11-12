#!/usr/bin/env python3
"""Runs on .108 next to bcl_framer.py / bcl_dummy_hu.py (uploaded by lab_bcl_dummy_hu_a2dp.py).

  hu     Register SPP server via ProfileManager1, keep each RFCOMM fd open,
         answer session init with HANDSHAKE, log every frame as JSONL.
         Needs python3-gi + python3-dbus.
  phone  Synthetic BclCarLink-like RFCOMM client bound to one local adapter.

Every JSONL line has ts (unix s) and event. Epistemic: TEST only.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bcl_dummy_hu import (  # noqa: E402
    SESSION_INIT_INTERVAL_S,
    WATCHDOG_INTERVAL_S,
    DummyHuSession,
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


def run_hu(args: argparse.Namespace) -> int:
    import dbus
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib

    log = JsonlLog(args.log)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    loop = GLib.MainLoop()
    conns: dict[int, dict] = {}

    def close(fd: int, reason: str) -> None:
        c = conns.pop(fd, None)
        if c is None:
            return
        log.write({"event": "rfcomm_closed", "reason": reason}, **c["dev"])
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
        sess: DummyHuSession = c["session"]
        log.write({"event": "rx_bytes", "n": len(data), "hex": data[:64].hex()}, **c["dev"])
        replies = sess.on_bytes(data)
        c["sent"] = _flush_events(log, sess, c["sent"], **c["dev"])
        for r in replies:
            try:
                os.write(fd, r)
                log.write({"event": "tx_bytes", "n": len(r), "hex": r[:64].hex()}, **c["dev"])
            except OSError as exc:
                close(fd, f"write_error:{exc.errno}")
                return False
        return True

    class Profile(dbus.service.Object):
        @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
        def Release(self):
            log.write({"event": "profile_released"})

        @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
        def NewConnection(self, device, fd, properties):
            fd = fd.take()
            dev = device_from_path(device)
            conns[fd] = {
                "dev": dev,
                "session": DummyHuSession(
                    version=args.hu_version, echo_watchdog=args.echo_watchdog
                ),
                "sent": 0,
            }
            log.write({"event": "rfcomm_connected"}, **dev)
            GLib.io_add_watch(fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, on_readable)

        @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
        def RequestDisconnection(self, device):
            dev = device_from_path(device)
            for fd, c in list(conns.items()):
                if c["dev"] == dev:
                    close(fd, "request_disconnection")

    # Well-known name is optional: BlueZ talks to this connection's object path.
    # Without a system.d policy, request_name raises AccessDenied (SDP script already soft-fails).
    try:
        bus.request_name("org.btanalyzer.BclDummyHu")
    except dbus.DBusException as exc:
        log.write({"event": "name_warn", "error": str(exc)})
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
    log.write({"event": "profile_registered", "channel": args.channel, "name": args.name,
               "hu_version": args.hu_version, "echo_watchdog": args.echo_watchdog})
    if args.ready:
        Path(args.ready).write_text("registered\n")

    def stop(*_a) -> bool:
        for fd in list(conns):
            close(fd, "agent_stop")
        try:
            pm.UnregisterProfile(path)
        except dbus.DBusException:
            pass
        log.write({"event": "agent_stopped"})
        loop.quit()
        return False

    GLib.timeout_add_seconds(max(1, int(args.hold)), stop)
    signal.signal(signal.SIGTERM, lambda *_a: GLib.idle_add(stop))
    signal.signal(signal.SIGINT, lambda *_a: GLib.idle_add(stop))
    loop.run()
    return 0


def run_phone(args: argparse.Namespace) -> int:
    log = JsonlLog(args.log)
    sess = PhoneClientSession()
    sent = 0
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        sock.bind((args.adapter_bd, 0))
        sock.settimeout(15)
        sock.connect((args.hu_bd, args.channel))
    except OSError as exc:
        log.write({"event": "rfcomm_connect_failed", "error": repr(exc)})
        return 2
    log.write({"event": "rfcomm_connected", "peer": args.hu_bd, "channel": args.channel})
    sock.settimeout(0.2)

    end = time.time() + args.seconds
    next_init = 0.0
    next_ping = 0.0
    last_rx = time.time()
    hs_logged = False
    while time.time() < end:
        now = time.time()
        if sess.handshake is None and now >= next_init:
            sock.sendall(sess.session_init())
            next_init = now + SESSION_INIT_INTERVAL_S
        if sess.active and now >= next_ping:
            sock.sendall(sess.watchdog_ping())
            log.write({"event": "watchdog_ping"})
            next_ping = now + WATCHDOG_INTERVAL_S
        try:
            data = sock.recv(4096)
        except socket.timeout:
            data = None
        except OSError as exc:
            log.write({"event": "rfcomm_closed", "reason": repr(exc)})
            break
        if data == b"":
            log.write({"event": "rfcomm_closed", "reason": "eof"})
            break
        if data:
            last_rx = now
            for out in sess.on_bytes(data):
                sock.sendall(out)
                log.write({"event": "tx_bytes", "n": len(out), "hex": out.hex()})
            if sess.handshake and not hs_logged:
                log.write({"event": "handshake_rx", **sess.handshake})
                hs_logged = True
        sent = _flush_events(log, sess, sent)
    _flush_events(log, sess, sent)
    log.write({"event": "phone_done", "active": sess.active,
               "rx_silence_s": round(time.time() - last_rx, 1)})
    sock.close()
    return 0 if sess.active else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)
    hu = sub.add_parser("hu")
    hu.add_argument("--channel", type=int, default=5)
    hu.add_argument("--name", default="BMW Connected")
    hu.add_argument("--hu-version", type=int, default=3)
    hu.add_argument("--echo-watchdog", action="store_true")
    hu.add_argument("--hold", type=float, default=120.0)
    hu.add_argument("--log", required=True)
    hu.add_argument("--ready")
    ph = sub.add_parser("phone")
    ph.add_argument("--adapter-bd", required=True)
    ph.add_argument("--hu-bd", required=True)
    ph.add_argument("--channel", type=int, default=5)
    ph.add_argument("--seconds", type=float, default=25.0)
    ph.add_argument("--log", required=True)
    args = ap.parse_args()
    return run_hu(args) if args.mode == "hu" else run_phone(args)


if __name__ == "__main__":
    raise SystemExit(main())
