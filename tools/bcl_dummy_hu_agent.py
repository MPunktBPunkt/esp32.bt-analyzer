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
    KNOCK_DEFAULT_PAYLOAD,
    SESSION_INIT_INTERVAL_S,
    WATCHDOG_INTERVAL_S,
    WATCHDOG_PING,
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


def _parse_hu_open_srcs(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return ()
    out: list[int] = []
    for part in str(raw).replace(" ", "").split(","):
        if not part:
            continue
        out.append(int(part, 0))
    return tuple(out)


def _make_dummy_session(args: argparse.Namespace) -> DummyHuSession:
    return DummyHuSession(
        version=int(args.hu_version),
        instance_id=int(args.hu_instance_id),
        buffer_size=int(args.hu_buffer_size),
        echo_watchdog=bool(args.echo_watchdog),
        send_dataack=bool(args.send_dataack),
        etch_stub=bool(args.etch_stub),
        sas_probe=str(getattr(args, "sas_probe", "challenge")),
        handshake_delay_s=float(getattr(args, "handshake_delay_s", 0.0) or 0.0),
        wd_pong_max=int(getattr(args, "wd_pong_max", 0) or 0),
        wd_pong_skip_mod=int(getattr(args, "wd_pong_skip_mod", 0) or 0),
        wd_pong_payload=(
            bytes.fromhex(args.wd_pong_payload) if args.wd_pong_payload else None
        ),
        wd_pong_delay_s=float(getattr(args, "wd_pong_delay_s", 0.0) or 0.0),
        etch_reply_src=getattr(args, "etch_reply_src", None),
        hu_open_srcs=_parse_hu_open_srcs(getattr(args, "hu_open_srcs", None)),
        cds_push=bool(getattr(args, "cds_push", False)),
    )


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
    refuse_channel = getattr(args, "channel_refuse", None)
    if refuse_channel is not None:
        refuse_channel = int(refuse_channel)
        if refuse_channel == int(args.channel):
            raise SystemExit("--channel-refuse must differ from --channel")

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
            try:
                os.close(fd)
            except OSError:
                pass
            return
        raw = c.get("rx_raw", b"")
        cls = classify_bytes(raw)
        log.write(
            {
                "event": "rfcomm_closed",
                "reason": reason,
                "channel_role": c.get("channel_role"),
                "rfcomm_channel": c.get("rfcomm_channel"),
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
                "rfcomm_channel": c.get("rfcomm_channel"),
            },
            **c["dev"],
            session_id=session_id,
        )
        if c.get("channel_role") == "refuse":
            log.write(
                {
                    "event": "rfcomm_refuse_rx",
                    "n": len(data),
                    "note": "SCN refuse channel — closing (SCN failover probe)",
                },
                **c["dev"],
                session_id=session_id,
            )
            close(fd, "refuse_channel")
            return False
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

    def accept_connection(
        device, fd, properties, *, channel: int, role: str
    ) -> None:
        fd = fd.take()
        dev = device_from_path(device)
        if role == "refuse":
            # Immediate close ≈ Phone sees short-lived / refused SCN (failover probe).
            # Not a true RFCOMM DM; epistemic LAB_TEST only.
            log.write(
                {
                    "event": "rfcomm_connected",
                    "tx_allowed": False,
                    "channel_role": "refuse",
                    "rfcomm_channel": channel,
                    "props": {str(k): str(v) for k, v in dict(properties).items()},
                    "note": "LAB SCN refuse — close without BCL (not wire DM)",
                },
                **dev,
                session_id=session_id,
            )
            conns[fd] = {
                "dev": dev,
                "session": ObserveOnlySession(),
                "sent": 0,
                "rx_raw": b"",
                "channel_role": "refuse",
                "rfcomm_channel": channel,
            }
            GLib.io_add_watch(fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, on_readable)

            # Close ASAP so Phone can failover to accept SCN.
            def _refuse_close(_fd=fd) -> bool:
                close(_fd, "refuse_immediate")
                return False

            GLib.idle_add(_refuse_close)
            return

        if observe_only:
            session = ObserveOnlySession()
        else:
            session = _make_dummy_session(args)
        conns[fd] = {
            "dev": dev,
            "session": session,
            "sent": 0,
            "rx_raw": b"",
            "channel_role": role,
            "rfcomm_channel": channel,
        }
        log.write(
            {
                "event": "rfcomm_connected",
                "tx_allowed": not observe_only,
                "channel_role": role,
                "rfcomm_channel": channel,
                "props": {str(k): str(v) for k, v in dict(properties).items()},
            },
            **dev,
            session_id=session_id,
        )
        GLib.io_add_watch(fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, on_readable)

    class Profile(dbus.service.Object):
        def __init__(self, bus, path, *, channel: int, role: str):
            self._channel = channel
            self._role = role
            super().__init__(bus, path)

        @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
        def Release(self):
            log.write(
                {
                    "event": "profile_released",
                    "rfcomm_channel": self._channel,
                    "channel_role": self._role,
                    "session_id": session_id,
                }
            )

        @dbus.service.method(
            "org.bluez.Profile1", in_signature="oha{sv}", out_signature=""
        )
        def NewConnection(self, device, fd, properties):
            accept_connection(
                device, fd, properties, channel=self._channel, role=self._role
            )

        @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
        def RequestDisconnection(self, device):
            dev = device_from_path(device)
            for f, c in list(conns.items()):
                if c["dev"] == dev:
                    close(f, "request_disconnection")

    try:
        bus.request_name("org.btanalyzer.BclDummyHu")
    except dbus.DBusException as exc:
        log.write({"event": "name_warn", "error": str(exc), "session_id": session_id})

    pm = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1"
    )
    profiles: list[tuple[str, Profile]] = []

    def register_one(channel: int, role: str) -> bool:
        path = f"/org/bluez/bcl_dummy_hu_{role}_ch{channel}"
        try:
            pm.UnregisterProfile(path)
        except dbus.DBusException:
            pass
        # legacy path cleanup for single-channel runs
        if role == "accept" and channel == int(args.channel):
            try:
                pm.UnregisterProfile("/org/bluez/bcl_dummy_hu")
            except dbus.DBusException:
                pass
        prof = Profile(bus, path, channel=channel, role=role)
        try:
            pm.RegisterProfile(
                path,
                SPP_UUID,
                {
                    "Name": args.name if role == "accept" else f"{args.name} refuse",
                    "Service": SPP_UUID,
                    "Role": "server",
                    "Channel": dbus.UInt16(channel),
                    "RequireAuthentication": False,
                    "RequireAuthorization": False,
                    "AutoConnect": False,
                },
            )
        except dbus.DBusException as exc:
            log.write(
                {
                    "event": "profile_register_failed",
                    "rfcomm_channel": channel,
                    "channel_role": role,
                    "error": str(exc),
                    "session_id": session_id,
                    "note": "BlueZ often allows only one 0x1101 registration",
                }
            )
            return False
        profiles.append((path, prof))
        log.write(
            {
                "event": "profile_registered",
                "channel": channel,
                "rfcomm_channel": channel,
                "channel_role": role,
                "name": args.name,
                "uuid": SPP_UUID,
                "hu_profile": getattr(args, "hu_profile", "legacy"),
                "hu_version": args.hu_version,
                "hu_instance_id": args.hu_instance_id,
                "hu_buffer_size": args.hu_buffer_size,
                "echo_watchdog": args.echo_watchdog,
                "send_dataack": args.send_dataack,
                "etch_stub": args.etch_stub,
                "sas_probe": getattr(args, "sas_probe", None),
                "handshake_delay_s": getattr(args, "handshake_delay_s", 0.0),
                "wd_pong_max": args.wd_pong_max,
                "wd_pong_skip_mod": args.wd_pong_skip_mod,
                "wd_pong_payload": args.wd_pong_payload or None,
                "wd_pong_delay_s": getattr(args, "wd_pong_delay_s", 0.0),
                "etch_reply_src": getattr(args, "etch_reply_src", None),
                "hu_open_srcs": list(
                    _parse_hu_open_srcs(getattr(args, "hu_open_srcs", None))
                ),
                "cds_push": bool(getattr(args, "cds_push", False)),
                "channel_refuse": refuse_channel,
                "observe_only": observe_only,
                **meta,
            }
        )
        return True

    ok_accept = register_one(int(args.channel), "accept")
    if not ok_accept:
        raise SystemExit(f"failed to register accept channel {args.channel}")
    if refuse_channel is not None:
        register_one(refuse_channel, "refuse")

    if args.ready:
        Path(args.ready).write_text("registered\n")

    def stop(*_a) -> bool:
        for fd in list(conns):
            close(fd, "agent_stop")
        for path, _prof in profiles:
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

    # Live CDS inject: append JSON lines to /tmp/bcl_dummy/inject_cds.jsonl
    # e.g. {"engine.RPMSpeed": 4321, "sensors.fuel": {"range": 99, "reserve": 0, "tanklevel": 11}}
    inject_path = Path(getattr(args, "inject_cds", "/tmp/bcl_dummy/inject_cds.jsonl") or "")
    inject_offset = 0
    if inject_path:
        inject_path.parent.mkdir(parents=True, exist_ok=True)
        inject_path.touch(exist_ok=True)
        inject_offset = inject_path.stat().st_size
        log.write(
            {
                "event": "inject_watch",
                "path": str(inject_path),
                "session_id": session_id,
            }
        )

    def poll_inject() -> bool:
        nonlocal inject_offset
        if not inject_path or observe_only or tx_forbidden:
            return True
        try:
            data = inject_path.read_bytes()
        except OSError:
            return True
        # File was truncated/rewritten — rescan from start.
        if len(data) < inject_offset:
            inject_offset = 0
        if len(data) <= inject_offset:
            return True
        chunk = data[inject_offset:]
        inject_offset = len(data)
        for ln in chunk.decode("utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln.startswith("{"):
                continue
            try:
                updates = json.loads(ln)
            except json.JSONDecodeError as exc:
                log.write(
                    {
                        "event": "inject_error",
                        "error": str(exc),
                        "line": ln[:200],
                        "session_id": session_id,
                    }
                )
                continue
            if not isinstance(updates, dict) or not updates:
                continue
            # RHMI iDrive action inject: {"_rhmi_action":{"src":19,"handle":17,"actionId":541,"args":{"0":0}}}
            rhmi = updates.get("_rhmi_action")
            if isinstance(rhmi, dict):
                log.write(
                    {
                        "event": "inject_rhmi_request",
                        "action": rhmi,
                        "open_conns": len(conns),
                        "session_id": session_id,
                    }
                )
                for fd, c in list(conns.items()):
                    sess = c.get("session")
                    if not isinstance(sess, DummyHuSession):
                        continue
                    args_map = rhmi.get("args") or {0: 0}
                    # JSON keys are str — coerce numeric keys
                    coerced: dict = {}
                    for k, v in dict(args_map).items():
                        try:
                            coerced[int(k)] = v
                        except (TypeError, ValueError):
                            coerced[k] = v
                    replies = sess.inject_rhmi_action(
                        src=int(rhmi.get("src") or 19),
                        handle=int(rhmi.get("handle") or 0),
                        action_id=int(rhmi.get("actionId") or rhmi.get("action_id") or 0),
                        args=coerced,
                        ident=rhmi.get("ident", 0),
                    )
                    c["sent"] = _flush_events(
                        log, sess, c["sent"], **c["dev"], session_id=session_id
                    )
                    for r in replies:
                        try:
                            os.write(fd, r)
                            log.write(
                                {
                                    "event": "tx_bytes",
                                    "n": len(r),
                                    "hex": r.hex(),
                                    "reason": "inject_rhmi_action",
                                },
                                **c["dev"],
                                session_id=session_id,
                            )
                        except OSError as exc:
                            close(fd, f"inject_write_error:{exc.errno}")
                            break
                # Default pacing avoids same-ms action floods that correlated with RFCOMM drops.
                # Override per line: {"_rhmi_action":{...},"_pace_ms":0} or env RHMI_ACTION_PACE_MS.
                try:
                    pace_ms = float(
                        updates.get("_pace_ms")
                        if updates.get("_pace_ms") is not None
                        else rhmi.get("pace_ms", os.environ.get("RHMI_ACTION_PACE_MS", "80"))
                    )
                except (TypeError, ValueError):
                    pace_ms = 80.0
                if pace_ms > 0:
                    time.sleep(pace_ms / 1000.0)
                continue

            cds_updates = {k: v for k, v in updates.items() if not str(k).startswith("_")}
            if not cds_updates:
                continue
            log.write(
                {
                    "event": "inject_cds_request",
                    "updates": cds_updates,
                    "open_conns": len(conns),
                    "session_id": session_id,
                }
            )
            for fd, c in list(conns.items()):
                sess = c.get("session")
                if not isinstance(sess, DummyHuSession):
                    continue
                replies = sess.inject_cds(cds_updates)
                c["sent"] = _flush_events(
                    log, sess, c["sent"], **c["dev"], session_id=session_id
                )
                for r in replies:
                    try:
                        os.write(fd, r)
                        log.write(
                            {
                                "event": "tx_bytes",
                                "n": len(r),
                                "hex": r.hex(),
                                "reason": "inject_cds",
                            },
                            **c["dev"],
                            session_id=session_id,
                        )
                    except OSError as exc:
                        close(fd, f"inject_write_error:{exc.errno}")
                        break
        return True

    if inject_path and not observe_only:
        GLib.timeout_add(400, poll_inject)

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
    knock_arg = getattr(args, "knock", None)
    knock_payload: bytes | str | None = None
    skip_knock = knock_arg == "none"
    if knock_arg == "wire_v5":
        knock_payload = "wire_v5"
    elif knock_arg == "desk":
        # Pre-set bytes so SP4 auto wire_v5 does not override (truthy).
        knock_payload = KNOCK_DEFAULT_PAYLOAD
    mybmw_sim = bool(getattr(args, "mybmw_sim", False))
    sess = None if observe_only else PhoneClientSession(
        selectproto=sp,
        wire_open5001=bool(getattr(args, "wire_open5001", False)) or mybmw_sim,
        open_etch=bool(getattr(args, "open_etch", False)) or mybmw_sim,
        etch_src=int(getattr(args, "etch_src", 10) or 10),
        knock_payload=knock_payload,
        skip_knock=skip_knock,
        mybmw_sim=mybmw_sim,
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
    miss_limit = int(getattr(args, "wd_miss_limit", 3) or 3)
    # FIFO of outstanding pings: (seq, ping_ts). Never overwrite an open ping.
    pending_pings: list[tuple[int, float]] = []
    ping_seq = 0
    wd_misses = 0
    abort_reason: str | None = None
    from bcl_dummy_hu import (  # noqa: WPS433 — hold metrics only on phone path
        CMD_DATA,
        CMD_DATAACK,
        CMD_OPEN,
    )
    from bcl_framer import DEST_ETCH_DESK, BclFramer

    rx_framer = BclFramer()
    while time.time() < end and abort_reason is None:
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
            # Age out oldest outstanding ping before issuing the next.
            if pending_pings:
                old_seq, old_ts = pending_pings.pop(0)
                wd_misses += 1
                log.write(
                    {
                        "event": "watchdog_echo_missed",
                        "misses": wd_misses,
                        "miss_limit": miss_limit,
                        "ping_seq": old_seq,
                        "waited_s": round(now - old_ts, 3),
                        "session_id": session_id,
                    }
                )
                if miss_limit > 0 and wd_misses >= miss_limit:
                    abort_reason = "wd_echo_miss_limit"
                    log.write(
                        {
                            "event": "hold_abort",
                            "reason": abort_reason,
                            "misses": wd_misses,
                            "session_id": session_id,
                        }
                    )
                    break
            sock.sendall(sess.watchdog_ping())
            ping_seq += 1
            pending_pings.append((ping_seq, now))
            log.write(
                {
                    "event": "watchdog_ping",
                    "session_id": session_id,
                    "interval_s": wd_interval,
                    "ping_ts": now,
                    "ping_seq": ping_seq,
                }
            )
            next_ping = now + wd_interval
        try:
            data = sock.recv(4096)
        except socket.timeout:
            data = None
            # Drain any deferred MyBMW Etch TX even on idle polls.
            if sess is not None and getattr(sess, "mybmw_sim", False):
                for out in sess.drain_tx():
                    try:
                        sock.sendall(out)
                        log.write(
                            {
                                "event": "tx_bytes",
                                "n": len(out),
                                "hex": out.hex()[:128],
                                "kind": "mybmw_deferred",
                                "session_id": session_id,
                            }
                        )
                    except OSError as exc:
                        log.write(
                            {
                                "event": "rfcomm_closed",
                                "reason": repr(exc),
                                "session_id": session_id,
                            }
                        )
                        abort_reason = "tx_error"
                        break
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
            # Hold metrics: WD RTT, HU DATAACK values, unsolicited OPEN/DATA→4004
            for fr in rx_framer.feed(data).frames:
                if (
                    fr.cmd == CMD_DATA
                    and fr.src == 5001
                    and fr.dest == 5001
                    and fr.payload == WATCHDOG_PING
                    and pending_pings
                ):
                    echo_ts = time.time()
                    seq, ping_ts = pending_pings.pop(0)
                    rtt_ms = round((echo_ts - ping_ts) * 1000.0, 1)
                    log.write(
                        {
                            "event": "watchdog_echo_rtt",
                            "rtt_ms": rtt_ms,
                            "ping_seq": seq,
                            "misses_reset_from": wd_misses,
                            "session_id": session_id,
                        }
                    )
                    wd_misses = 0
                if fr.cmd == CMD_DATAACK and len(fr.payload) >= 4:
                    ack_n = int.from_bytes(fr.payload[:4], "big")
                    log.write(
                        {
                            "event": "hu_dataack",
                            "ack_n": ack_n,
                            # Selective: SP/OPEN/DATA match 8+payload_len; KNOCK≠56 observed
                            "note": "matches_8_plus_payload_len_when_acked",
                            "payload_hex": fr.payload.hex(),
                            "session_id": session_id,
                        }
                    )
                if fr.cmd in (CMD_OPEN, CMD_DATA) and (
                    fr.dest == DEST_ETCH_DESK or fr.src in (10, 12, 18)
                ):
                    log.write(
                        {
                            "event": "hu_unsolicited",
                            "cmd": fr.cmd,
                            "src": fr.src,
                            "dest": fr.dest,
                            "len": len(fr.payload),
                            "payload_hex": fr.payload[:64].hex(),
                            "model_a_hint": fr.dest == DEST_ETCH_DESK,
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
            "abort_reason": abort_reason,
            "wd_misses": wd_misses,
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
            choices=sorted(("legacy", "f20", "f20_sim")),
            default=default_profile,
            help="legacy=v3/iid1/0x8000; f20=v5/iid14/0x4000+challenge probe; f20_sim=full F20 BMWRemoting server (SAS+AM+RHMI+CDS+AV)",
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
            "--sas-probe",
            choices=("none", "dataack", "challenge", "challenge_rhmi", "adaptive", "f20_full"),
            default=None,
            help=(
                "Etch reply after OPEN 4004: "
                "none=no etch; dataack=DATAACK only; "
                "challenge=non-zero SAS challenge; "
                "challenge_rhmi=challenge+RHMI stub; "
                "adaptive=challenge then escalate on Phone TX "
                "(default from profile)"
            ),
        )
        p.add_argument(
            "--handshake-delay",
            type=float,
            default=None,
            dest="handshake_delay_s",
            help="seconds to wait before HS TX (field ~3.0; default 0 / profile)",
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
        p.add_argument(
            "--wd-pong-delay",
            type=float,
            default=None,
            dest="wd_pong_delay_s",
            help="seconds to delay each WD pong (timeout probe; default 0)",
        )
        p.add_argument(
            "--etch-reply-src",
            type=lambda x: int(x, 0),
            default=None,
            help=(
                "HU etch DATA as src=N dest=4004 (field-shaped); "
                "omit for desk src=4004 dest=phone"
            ),
        )
        p.add_argument(
            "--hu-open-srcs",
            default="",
            help="comma ports: after KNOCK send HU OPEN src→4004 (e.g. 10,12,18)",
        )
        p.add_argument(
            "--channel-refuse",
            type=int,
            default=None,
            help=(
                "also register this SCN and close immediately on connect "
                "(SCN6 refuse → SCN10 accept failover probe; BlueZ may reject "
                "second 0x1101)"
            ),
        )
        p.add_argument(
            "--cds-push",
            action=argparse.BooleanOptionalAction,
            default=False,
            help=(
                "after OPEN challenge, push unsolicited field-like CDS once "
                "(SOCBattery / iva_MYV_LIGHT_INTERIOR / VIN stub)"
            ),
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

    def add_phone_client_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--full-client",
            action="store_true",
            help="after HANDSHAKE continue SELECTPROTO/KNOCK/OPEN (lab only by default)",
        )
        p.add_argument(
            "--selectproto",
            type=int,
            default=3,
            help="SELECTPROTO payload u16 after HS version>3 (desk=3, Dummy-wire=2)",
        )
        p.add_argument(
            "--wd-interval",
            type=float,
            default=WATCHDOG_INTERVAL_S,
            help="watchdog ping interval seconds after OPEN 5001 (desk 5, lab-wire ~2.5)",
        )
        p.add_argument(
            "--wire-open5001",
            action="store_true",
            help="OPEN watchdog as src=dest=5001 (AAIdrive lab wire) instead of src=1",
        )
        p.add_argument(
            "--open-etch",
            action="store_true",
            help="after OPEN 5001 also OPEN Etch dest=4004 (lab: src=10)",
        )
        p.add_argument(
            "--etch-src",
            type=int,
            default=10,
            help="BCL src port for OPEN 4004 (lab MyBMW used 10..12)",
        )
        p.add_argument(
            "--knock",
            choices=("wire_v5", "desk", "none"),
            default=None,
            help="KNOCK: wire_v5=UUID+TouchCommand/7; desk=empty A4A; none=skip KNOCK "
            "(isolation); default auto wire_v5 when SP≥4 / HS v5",
        )
        p.add_argument(
            "--wd-miss-limit",
            type=int,
            default=3,
            help="abort hold after N consecutive missed WD echoes (0=never)",
        )
        p.add_argument(
            "--mybmw-sim",
            action="store_true",
            help="simulate MyBMW/AAIdrive Etch client after OPEN 4004 "
            "(sas_certificate→login→CDS/RHMI/AM/AV); implies --open-etch --wire-open5001",
        )

    ph = sub.add_parser("phone", help="lab BclCarLink-like client (sends INIT)")
    add_phone(ph)
    add_phone_client_opts(ph)
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
    add_phone_client_opts(b2a_tx)

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
        if getattr(ns, "sas_probe", None) is None:
            ns.sas_probe = str(prof.get("sas_probe", "challenge"))
        if getattr(ns, "handshake_delay_s", None) is None:
            ns.handshake_delay_s = float(prof.get("handshake_delay_s", 0.0))
        if getattr(ns, "wd_pong_delay_s", None) is None:
            ns.wd_pong_delay_s = float(prof.get("wd_pong_delay_s", 0.0))
        if getattr(ns, "etch_reply_src", None) is None and "etch_reply_src" in prof:
            ns.etch_reply_src = prof.get("etch_reply_src")
        if not getattr(ns, "hu_open_srcs", None):
            srcs = prof.get("hu_open_srcs") or ()
            if srcs:
                ns.hu_open_srcs = ",".join(str(x) for x in srcs)

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
