#!/usr/bin/env python3
"""B3 relay via BlueZ ProfileManager — advertises SPP so AAIdrive/MyBMW can find HU.

Raw AF_BLUETOOTH listen (b3_rfcomm_relay rfcomm) does not publish SDP; apps then
sit on ACL waiting for HU. This registers 0x1101 on --listen-channel, accepts the
phone FD, connects outbound RFCOMM to --peer via --connect-adapter-bd, and pumps
bytes through b3_rfcomm_relay.pump_pair (decode + jsonl + raw).

Usage (on .108):
  PYTHONPATH=tools python3 tools/b3_profile_relay.py \\
    --adapter-bd C8:C9:A3:CB:7B:0A \\
    --connect-adapter-bd C8:C9:A3:CB:37:96 \\
    --peer D4:36:39:CF:E1:B5 \\
    --log /tmp/bcl_dummy/b3.jsonl --raw-dir /tmp/bcl_dummy/raw
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
from pathlib import Path

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from b3_rfcomm_relay import RelayLogger, pump_pair  # noqa: E402

SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"
PROFILE_PATH = "/org/btanalyzer/b3_profile_relay"


def _fd_to_socket(fd: int) -> socket.socket:
    sock = socket.fromfd(fd, socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    # fromfd dup's; close the dbus-owned fd we took
    try:
        os.close(fd)
    except OSError:
        pass
    return sock


def run(args: argparse.Namespace) -> int:
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    log = RelayLogger(Path(args.log) if args.log else None)
    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    bus = dbus.SystemBus()
    try:
        bus.request_name("org.btanalyzer.B3ProfileRelay")
    except dbus.DBusException as exc:
        log.write({"event": "name_warn", "error": str(exc)})

    state: dict = {"busy": False, "loop": None}

    def relay_worker(phone_fd: int, device: str, props: dict) -> None:
        phone = hu = None
        try:
            phone = _fd_to_socket(phone_fd)
            log.write(
                {
                    "event": "rfcomm_accepted",
                    "via": "profile",
                    "device": device,
                    "props": props,
                    "adapter": args.adapter_bd,
                    "channel": args.listen_channel,
                }
            )
            hu = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            hu.bind((args.connect_adapter_bd, 0))
            hu.connect((args.peer, args.peer_channel))
            log.write(
                {
                    "event": "rfcomm_connected_hu",
                    "peer": args.peer,
                    "via_adapter": args.connect_adapter_bd,
                    "peer_channel": args.peer_channel,
                }
            )
            # Let F20 finish RFCOMM SABM/MSC before first phone INIT bytes.
            import time as _time
            _time.sleep(0.35)
            log.write({"event": "relay_settle_done", "settle_s": 0.35})
            pump_pair(
                phone,
                hu,
                log,
                a_name="phone",
                b_name="hu",
                raw_dir=raw_dir,
                max_s=float(args.max_s or 0),
            )
        except Exception as exc:  # noqa: BLE001
            log.write({"event": "relay_error", "error": repr(exc)})
        finally:
            for s in (phone, hu):
                if s is not None:
                    try:
                        s.close()
                    except OSError:
                        pass
            state["busy"] = False
            log.write({"event": "relay_worker_done"})

    class Profile(dbus.service.Object):
        @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
        def Release(self) -> None:
            log.write({"event": "profile_released"})

        @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
        def NewConnection(self, device, fd, properties) -> None:
            if state["busy"]:
                raw = fd.take()
                try:
                    os.close(raw)
                except OSError:
                    pass
                log.write({"event": "rfcomm_busy_reject", "device": str(device)})
                return
            state["busy"] = True
            raw = fd.take()
            props = {str(k): str(v) for k, v in dict(properties).items()}
            threading.Thread(
                target=relay_worker,
                args=(raw, str(device), props),
                daemon=True,
            ).start()

        @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
        def RequestDisconnection(self, device) -> None:
            log.write({"event": "profile_request_disconnection", "device": str(device)})

    profile = Profile(bus, PROFILE_PATH)
    pm = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
    for path in (PROFILE_PATH, "/org/bluez/bcl_dummy_hu", "/org/bluez/bcl_dummy_hu_accept_ch6"):
        try:
            pm.UnregisterProfile(path)
        except dbus.DBusException:
            pass
    pm.RegisterProfile(
        PROFILE_PATH,
        SPP_UUID,
        {
            "Name": args.name,
            "Service": SPP_UUID,
            "Role": "server",
            "Channel": dbus.UInt16(args.listen_channel),
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "AutoConnect": False,
        },
    )
    log.write(
        {
            "event": "profile_registered",
            "name": args.name,
            "uuid": SPP_UUID,
            "adapter_hint": args.adapter_bd,
            "channel": args.listen_channel,
            "connect_adapter": args.connect_adapter_bd,
            "peer": args.peer,
            "peer_channel": args.peer_channel,
            "note": "SDP SPP published — AAIdrive/MyBMW can discover HU ch6",
        }
    )
    print(
        f"B3 profile SPP '{args.name}' ch{args.listen_channel} "
        f"→ via {args.connect_adapter_bd} → {args.peer} ch{args.peer_channel}",
        flush=True,
    )
    if args.ready:
        Path(args.ready).write_text("registered\n")

    loop = GLib.MainLoop()
    state["loop"] = loop

    def _stop(*_a):
        try:
            pm.UnregisterProfile(PROFILE_PATH)
        except dbus.DBusException:
            pass
        log.write({"event": "profile_unregistered"})
        log.close()
        loop.quit()
        return False

    import signal

    signal.signal(signal.SIGTERM, lambda *_: _stop())
    signal.signal(signal.SIGINT, lambda *_: _stop())
    loop.run()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter-bd", required=True, help="HU-side BD (SDP/phone connects here)")
    ap.add_argument("--connect-adapter-bd", required=True, help="phone-role BD toward F20")
    ap.add_argument("--peer", required=True, help="F20 BD_ADDR")
    ap.add_argument("--listen-channel", type=int, default=6)
    ap.add_argument("--peer-channel", type=int, default=6)
    ap.add_argument("--name", default="BMW Connected")
    ap.add_argument("--log", default="")
    ap.add_argument("--raw-dir", default="")
    ap.add_argument("--max-s", type=float, default=0.0)
    ap.add_argument("--ready", default="")
    return run(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
