#!/usr/bin/env python3
"""Runs on .108 next to bcl_framer.py / bcl_dummy_hu.py / bcl_etch_stub.py (lab upload).

  hu              Register SPP server via ProfileManager1, keep each RFCOMM fd open,
                  answer INIT with HANDSHAKE; default --hu-profile f20 (DATAACK+WD+Etch stub).
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
    apply_hu_profile,
)
from bcl_framer import INIT_MAGIC  # noqa: E402

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
            if observe_only:
                session = ObserveOnlySession()
            else:
                session = DummyHuSession(
                    version=int(args.hu_version),
                    instance_id=int(args.hu_instance_id),
                    buffer_size=int(args.hu_buffer_size),
                    echo_watchdog=bool(args.echo_watchdog),
                    send_dataack=bool(args.send_dataack),
                    etch_stub=bool(args.etch_stub),
                    wd_pong_max=args.wd_pong_max,
                    wd_pong_skip_mod=args.wd_pong_skip_mod,
                    wd_pong_payload=(
                        bytes.fromhex(args.wd_pong_payload)
                        if args.wd_pong_payload
                        else None
                    ),
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
            "hu_profile": getattr(args, "hu_profile", "legacy"),
            "hu_version": args.hu_version,
            "hu_instance_id": args.hu_instance_id,
            "hu_buffer_size": args.hu_buffer_size,
            "echo_watchdog": args.echo_watchdog,
            "send_dataack": args.send_dataack,
            "etch_stub": args.etch_stub,
            "wd_pong_max": args.wd_pong_max,
            "wd_pong_skip_mod": args.wd_pong_skip_mod,
            "wd_pong_payload": args.wd_pong_payload or None,
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


def run_phone(
    args: argparse.Namespace,
    *,
    observe_only: bool,
    controlled_init: bool = False,
) -> int:
    """Phone-side RFCOMM client.

    observe_only: B2-A — connect + recv, no TX (expected empty under BclCarLink model).
    controlled_init (b2a-tx): send INIT_MAGIC a few times, then observe for HANDSHAKE;
      do **not** auto KNOCK/OPEN unless --full-client (field-safe discriminator for H-A).
    lab phone: full BclCarLink-like client (INIT → HANDSHAKE → SELECTPROTO/KNOCK/OPEN).
    """
    log = JsonlLog(args.log)
    session_id = args.session_id or str(uuid.uuid4())
    full_client = bool(getattr(args, "full_client", False)) and not observe_only
    init_count = int(getattr(args, "init_count", 1) or 1)
    if controlled_init:
        mode = "B2-A-TX"
        tx_allowed = True
        bcl_tx = True
        bcl_tx_mode = "controlled_init"
    elif observe_only:
        mode = "B2-A"
        tx_allowed = False
        bcl_tx = False
        bcl_tx_mode = "none"
    else:
        mode = "lab_phone"
        tx_allowed = True
        bcl_tx = True
        bcl_tx_mode = "full_client"
    meta = {
        "session_id": session_id,
        "mode": mode,
        "tx_allowed": tx_allowed,
        "bcl_tx_enabled": bcl_tx,
        "bcl_tx_mode": bcl_tx_mode,
        "init_count": init_count if controlled_init else None,
        "full_client": full_client if controlled_init else (not observe_only),
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

    sp = getattr(args, "selectproto", 3)
    sess = None if observe_only else PhoneClientSession(
        selectproto=sp,
        wire_open5001=bool(getattr(args, "wire_open5001", False)),
        open_etch=bool(getattr(args, "open_etch", False)),
        etch_src=int(getattr(args, "etch_src", 10) or 10),
    )
    sent = 0
    rx_raw = b""
    end = time.time() + args.seconds
    next_init = 0.0
    next_ping = 0.0
    last_rx = time.time()
    hs_logged = False
    inits_sent = 0
    wd_interval = float(getattr(args, "wd_interval", WATCHDOG_INTERVAL_S) or WATCHDOG_INTERVAL_S)
    while time.time() < end:
        now = time.time()
        if controlled_init and sess is not None and sess.handshake is None:
            if inits_sent < init_count and now >= next_init:
                sock.sendall(INIT_MAGIC)
                inits_sent += 1
                log.write(
                    {
                        "event": "tx_bytes",
                        "n": len(INIT_MAGIC),
                        "hex": INIT_MAGIC.hex(),
                        "kind": "session_init",
                        "init_i": inits_sent,
                        "session_id": session_id,
                    }
                )
                next_init = now + SESSION_INIT_INTERVAL_S
        elif not observe_only and not controlled_init and sess is not None:
            if sess.handshake is None and now >= next_init:
                sock.sendall(sess.session_init())
                next_init = now + SESSION_INIT_INTERVAL_S
        # WD pings once ACTIVE — including controlled_init --full-client (was missing before)
        if (
            sess is not None
            and sess.active
            and (full_client or not controlled_init)
            and not observe_only
            and now >= next_ping
        ):
            sock.sendall(sess.watchdog_ping())
            log.write(
                {
                    "event": "watchdog_ping",
                    "session_id": session_id,
                    "interval_s": wd_interval,
                }
            )
            next_ping = now + wd_interval
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
            if sess is not None and (controlled_init or not observe_only):
                replies = sess.on_bytes(data)
                if sess.handshake and not hs_logged:
                    log.write(
                        {"event": "handshake_rx", **sess.handshake, "session_id": session_id}
                    )
                    hs_logged = True
                # Field-safe: controlled_init stops after HANDSHAKE unless --full-client
                if controlled_init and not full_client:
                    replies = []
                if not observe_only or controlled_init:
                    for out in replies:
                        sock.sendall(out)
                        log.write(
                            {
                                "event": "tx_bytes",
                                "n": len(out),
                                "hex": out.hex(),
                                "session_id": session_id,
                            }
                        )
                sent = _flush_events(log, sess, sent, session_id=session_id)
    if sess is not None:
        _flush_events(log, sess, sent, session_id=session_id)
    cls = classify_bytes(rx_raw)
    log.write(
        {
            "event": "phone_done",
            "active": bool(sess and sess.active) if sess else False,
            "handshake": bool(sess and sess.handshake) if sess else False,
            "handshake_fields": (sess.handshake if sess else None),
            "inits_sent": inits_sent if controlled_init else None,
            "rx_silence_s": round(time.time() - last_rx, 1),
            "rx_total": len(rx_raw),
            "bcl_classification": cls["bcl_classification"],
            "classification": cls,
            **meta,
        }
    )
    sock.close()
    if observe_only and not controlled_init:
        return 0
    if controlled_init:
        return 0 if (sess and sess.handshake) else 1
    return 0 if sess and sess.active else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    def add_hu(p: argparse.ArgumentParser, *, default_profile: str = "legacy") -> None:
        p.add_argument("--channel", type=int, default=5)
        p.add_argument("--name", default="BMW Connected")
        p.add_argument(
            "--hu-profile",
            choices=sorted(("legacy", "f20")),
            default=default_profile,
            help="legacy=v3/iid1/0x8000; f20=v5/iid14/0x4000+DATAACK+WD+Etch stub",
        )
        p.add_argument(
            "--hu-version",
            type=int,
            default=None,
            help="override HS version (default from --hu-profile)",
        )
        p.add_argument(
            "--hu-instance-id",
            type=int,
            default=None,
            help="override HS instanceId (default from --hu-profile)",
        )
        p.add_argument(
            "--hu-buffer-size",
            type=lambda x: int(x, 0),
            default=None,
            help="override HS bufferSize (default from --hu-profile; accepts 0x4000)",
        )
        p.add_argument(
            "--echo-watchdog",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="echo WD DATA 13371337 (default from --hu-profile)",
        )
        p.add_argument(
            "--send-dataack",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="TX DATAACK(8+len) per RX frame like F20 (default from profile)",
        )
        p.add_argument(
            "--etch-stub",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="minimal SAS challenge + CDS stub on dest 4004 (default from profile)",
        )
        p.add_argument(
            "--wd-pong-max",
            type=int,
            default=0,
            help="stop echoing after N pongs (0=unlimited); C-L12 timeout probe",
        )
        p.add_argument(
            "--wd-pong-skip-mod",
            type=int,
            default=0,
            help="if >1, echo only when ping_index %% mod == 1",
        )
        p.add_argument(
            "--wd-pong-payload",
            default="",
            help="hex override for WD pong payload (empty=mirror ping)",
        )
        p.add_argument("--hold", type=float, default=120.0)
        p.add_argument("--log", required=True)
        p.add_argument("--ready")
        p.add_argument("--session-id", default="")
        p.add_argument("--origin", default="dummy_hu")
        p.add_argument("--source", default="lab")

    hu = sub.add_parser("hu", help="lab Dummy-HU (answers HANDSHAKE); default profile f20")
    add_hu(hu, default_profile="f20")
    b2b = sub.add_parser("b2b", help="B2-B observe-only SPP server (no BCL TX)")
    add_hu(b2b, default_profile="legacy")
    b2b_alias = sub.add_parser("hu-observe", help="alias for b2b")
    add_hu(b2b_alias, default_profile="legacy")

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
    b2a_tx = sub.add_parser(
        "b2a-tx",
        help="B2-A controlled INIT (12 34 56 78) then observe HANDSHAKE; no KNOCK unless --full-client",
    )
    add_phone(b2a_tx)
    b2a_tx.add_argument(
        "--init-count",
        type=int,
        default=3,
        help="how many INIT_MAGIC bursts (1 s apart) before observe-only",
    )
    b2a_tx.add_argument(
        "--full-client",
        action="store_true",
        help="after HANDSHAKE continue SELECTPROTO/KNOCK/OPEN (lab only by default)",
    )
    b2a_tx.add_argument(
        "--selectproto",
        type=int,
        default=3,
        help="SELECTPROTO payload u16 after HS version>3 (desk=3, Dummy-wire=2)",
    )
    b2a_tx.add_argument(
        "--wd-interval",
        type=float,
        default=WATCHDOG_INTERVAL_S,
        help="watchdog ping interval seconds after OPEN 5001 (desk 5, lab-wire ~2.5)",
    )
    b2a_tx.add_argument(
        "--wire-open5001",
        action="store_true",
        help="OPEN watchdog as src=dest=5001 (AAIdrive lab wire) instead of src=1",
    )
    b2a_tx.add_argument(
        "--open-etch",
        action="store_true",
        help="after OPEN 5001 also OPEN Etch dest=4004 (lab: src=10)",
    )
    b2a_tx.add_argument(
        "--etch-src",
        type=int,
        default=10,
        help="BCL src port for OPEN 4004 (lab MyBMW used 10..12)",
    )

    args = ap.parse_args()

    def _resolve_hu_profile(ns: argparse.Namespace) -> None:
        if not hasattr(ns, "hu_profile"):
            return
        prof = apply_hu_profile(ns.hu_profile)
        if ns.hu_version is None:
            ns.hu_version = int(prof["version"])
        if ns.hu_instance_id is None:
            ns.hu_instance_id = int(prof["instance_id"])
        if ns.hu_buffer_size is None:
            ns.hu_buffer_size = int(prof["buffer_size"])
        if ns.echo_watchdog is None:
            ns.echo_watchdog = bool(prof["echo_watchdog"])
        if ns.send_dataack is None:
            ns.send_dataack = bool(prof["send_dataack"])
        if ns.etch_stub is None:
            ns.etch_stub = bool(prof["etch_stub"])

    _resolve_hu_profile(args)

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
    if args.mode == "b2a-tx":
        # Field default: origin f20 unless caller overrides for lab dummy.
        if args.origin == "bclcarlink":
            args.origin = "f20"
        return run_phone(args, observe_only=False, controlled_init=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
