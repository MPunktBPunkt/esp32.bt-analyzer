#!/usr/bin/env python3
"""Register a temporary BlueZ MediaPlayer1 (Title/Album) on an adapter.

Run on the BlueZ host (.108), with the HU already A2DP-connected:

  python3 tools/lab_avrcp_set_track.py --adapter hci2 \\
      --title 'Feldtest Titel' --album 'F20 Session' --hold 180

Epistemic: lab/field stimulus — not a BCL claim.
"""

from __future__ import annotations

import argparse
import signal
import sys

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

IFACE = "org.bluez.MediaPlayer1"


class Player(dbus.service.Object):
    def __init__(self, bus: dbus.Bus, path: str, title: str, artist: str, album: str) -> None:
        dbus.service.Object.__init__(self, bus, path)
        self.path = path
        self._props = dbus.Dictionary(
            {
                "Name": dbus.String("BT-Analyzer"),
                "Type": dbus.String("Audio"),
                "Status": dbus.String("playing"),
                "Position": dbus.UInt32(15000),
                "Track": self._track(title, artist, album, 3),
            },
            signature="sv",
        )
        self._n = 3

    @staticmethod
    def _track(title: str, artist: str, album: str, num: int) -> dbus.Dictionary:
        return dbus.Dictionary(
            {
                "Title": dbus.String(title),
                "Artist": dbus.String(artist),
                "Album": dbus.String(album),
                "Genre": dbus.String("Test"),
                "NumberOfTracks": dbus.UInt32(10),
                "TrackNumber": dbus.UInt32(num),
                "Duration": dbus.UInt32(240000),
            },
            signature="sv",
        )

    def bump(self, title: str, album: str) -> None:
        self._n += 1
        track = self._track(title, "bt-analyzer", album, self._n)
        self.Set(IFACE, "Track", track)
        print(f"TRACK → Title={title!r} Album={album!r} #{self._n}", flush=True)

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self._props[prop]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self._props

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv")
    def Set(self, interface, prop, value):
        self._props[prop] = value
        self.PropertiesChanged(interface, {prop: value}, [])

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    @dbus.service.method(IFACE)
    def Play(self):
        print("AVRCP Play", flush=True)
        self.Set(IFACE, "Status", dbus.String("playing"))

    @dbus.service.method(IFACE)
    def Pause(self):
        print("AVRCP Pause", flush=True)
        self.Set(IFACE, "Status", dbus.String("paused"))

    @dbus.service.method(IFACE)
    def Stop(self):
        print("AVRCP Stop", flush=True)
        self.Set(IFACE, "Status", dbus.String("stopped"))

    @dbus.service.method(IFACE)
    def Next(self):
        print("AVRCP Next (HU FORWARD)", flush=True)
        self.bump(f"Titel nach FORWARD #{self._n + 1}", "F20 Session Live")

    @dbus.service.method(IFACE)
    def Previous(self):
        print("AVRCP Previous (HU BACKWARD)", flush=True)
        self.bump(f"Titel nach BACKWARD #{self._n + 1}", "F20 Session Live")

    @dbus.service.method(IFACE)
    def FastForward(self):
        print("AVRCP FastForward", flush=True)

    @dbus.service.method(IFACE)
    def Rewind(self):
        print("AVRCP Rewind", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", default="hci2", help="hciN owning the HU ACL")
    ap.add_argument("--path", default="/test/player0")
    ap.add_argument("--title", default="Feldtest Titel")
    ap.add_argument("--artist", default="bt-analyzer")
    ap.add_argument("--album", default="F20 Session")
    ap.add_argument("--hold", type=int, default=180)
    args = ap.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = f"/org/bluez/{args.adapter}"
    player = Player(bus, args.path, args.title, args.artist, args.album)
    media = dbus.Interface(bus.get_object("org.bluez", adapter), "org.bluez.Media1")
    try:
        media.UnregisterPlayer(args.path)
    except dbus.DBusException:
        pass
    media.RegisterPlayer(args.path, player._props)
    print(
        f"REGISTERED {args.path} on {adapter}: "
        f"Title={args.title!r} Album={args.album!r}",
        flush=True,
    )
    print("Press FORWARD/BACKWARD on HU — should log Next/Previous here.", flush=True)

    loop = GLib.MainLoop()

    def stop(*_a):
        try:
            media.UnregisterPlayer(args.path)
        except dbus.DBusException:
            pass
        print("UNREGISTERED", flush=True)
        loop.quit()
        return False

    GLib.timeout_add_seconds(max(5, args.hold), stop)
    signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(stop))
    signal.signal(signal.SIGINT, lambda *_: GLib.idle_add(stop))
    loop.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except dbus.DBusException as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
