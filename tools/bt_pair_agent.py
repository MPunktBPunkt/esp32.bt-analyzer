#!/usr/bin/env python3
"""BlueZ pairing agent for the HCI-TCP adapters on the BlueZ host (.108).

Port of PiDrive bt_agent_dbus.py (field-tested with the BMW, 2026-09-16) for
several adapters at once. BlueZ asks the *default* agent whenever the remote
side starts pairing (phone pairs with .131, HU pairs with .87). Without one the
pairing is cancelled; a `bluetoothctl agent …` one-shot does not help because
its agent dies with the process.

  capability DisplayYesNo   BMW Numeric Comparison arrives as RequestConfirmation;
                            NoInputNoOutput would force Just Works (MITM-less).
  rule always|window|never  configured adapters follow the rule; any other
                            adapter (e.g. the host's own hci0) only inside a window.
  Trusted after pairing     otherwise BlueZ asks again on every reconnect.

Adapters are matched by BD address, not hciN: the bridge gets a new index after
each reconnect. Per configured adapter the agent sets Alias, Discoverable and
Pairable without timeout and a Class of Device (hciconfig, best effort).

  sudo python3 bt_pair_agent.py --adapter C8:C9:A3:CB:37:96=phone:BT-Analyzer-Phone
  python3 bt_pair_agent.py --open-window 300
  python3 bt_pair_agent.py --status            # JSON for the Lab UI (via SSH)

Standalone on purpose (stdlib + dbus-python + gi only), copied to /opt/bt-analyzer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

STATE_FILE = os.environ.get("BT_PAIR_STATE", "/run/bt-analyzer/pair_agent.json")
EVENTS_FILE = os.environ.get("BT_PAIR_EVENTS", "/var/log/bt-analyzer/pair_events.jsonl")
WINDOW_FILE = os.environ.get("BT_PAIR_WINDOW", "/run/bt-analyzer/pair_window")
SERVICE = "bt-pair-agent"

AGENT_PATH = "/org/btanalyzer/pairagent"
CAPABILITY = "DisplayYesNo"
EVENTS_KEEP = 60

# Class of Device: major/minor class plus service bits a real device of that kind sets.
# bluetoothd ORs in service bits of registered profiles and may rewrite the class on
# power-on, hence re-applied on Powered=true and read back into the state.
CLASS_BY_ROLE = {
    "phone": 0x5A020C,      # Phone/Smartphone · Telephony, Object Transfer, Capturing, Networking
    "car_audio": 0x200420,  # Audio/Video/Car audio · Audio
}

AUDIO_UUIDS = {
    "0000110a-0000-1000-8000-00805f9b34fb",  # AudioSource
    "0000110b-0000-1000-8000-00805f9b34fb",  # AudioSink
    "0000110c-0000-1000-8000-00805f9b34fb",  # A/V RemoteControlTarget
    "0000110d-0000-1000-8000-00805f9b34fb",  # AdvancedAudioDistribution
    "0000110e-0000-1000-8000-00805f9b34fb",  # A/V RemoteControl
    "0000110f-0000-1000-8000-00805f9b34fb",  # A/V RemoteControlController
    "00000019-0000-1000-8000-00805f9b34fb",  # AVDTP
    "00000017-0000-1000-8000-00805f9b34fb",  # AVCTP
}

BD_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")


# ── pure helpers (host-tested) ───────────────────────────────────────────────

def parse_adapter_spec(spec: str) -> dict:
    """`BD=role[:alias]` → {bd, role, alias, cls}. Role must be in CLASS_BY_ROLE or `none`."""
    bd, _, rest = spec.partition("=")
    bd = bd.strip().upper()
    if not BD_RE.match(bd):
        raise ValueError(f"bad BD address in {spec!r}")
    role, _, alias = (rest or "none").partition(":")
    role = role.strip() or "none"
    if role != "none" and role not in CLASS_BY_ROLE:
        raise ValueError(f"unknown role {role!r} (use {', '.join(CLASS_BY_ROLE)} or none)")
    return {"bd": bd, "role": role, "alias": alias.strip(), "cls": CLASS_BY_ROLE.get(role)}


def window_remaining(path: str = None, now: float | None = None) -> float:
    path = path or WINDOW_FILE
    now = time.time() if now is None else now
    try:
        with open(path, encoding="utf-8") as f:
            until = float(f.read().strip())
    except (OSError, ValueError):
        return 0.0
    return max(0.0, until - now)


def open_window(seconds: int, path: str = None) -> float:
    path = path or WINDOW_FILE
    until = time.time() + max(1, int(seconds))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(until))
    return until


def decide_confirm(mode: str, window_s: float, paired_before: bool, known_adapter: bool) -> tuple[bool, str]:
    if paired_before:
        return True, "already paired"
    if not known_adapter:
        mode = "window"
    if mode == "never":
        return False, "rule never"
    if mode == "window":
        if window_s > 0:
            return True, f"window open ({int(window_s)}s)"
        return False, "window closed" if known_adapter else "unconfigured adapter, window closed"
    return True, "rule always"


def split_device_path(path: str) -> tuple[str, str]:
    """/org/bluez/hci2/dev_AA_BB_… → ("/org/bluez/hci2", "AA:BB:…")."""
    m = re.match(r"^(/org/bluez/hci\d+)(?:/dev_([0-9A-Fa-f_]{17}))?", path or "")
    if not m:
        return "", ""
    return m.group(1), (m.group(2) or "").replace("_", ":").upper()


def class_matches(actual: int, wanted: int | None) -> bool | None:
    """Same major/minor class and at least the wanted service bits (BlueZ may add more)."""
    if not wanted:
        return None
    device, services = 0x1FFC, 0xFFE000
    return (actual & device) == (wanted & device) and (actual & wanted & services) == (wanted & services)


def summarize_objects(objects: dict, adapters_cfg: dict) -> list[dict]:
    """GetManagedObjects → per adapter: config, live props and its devices."""
    adapters: dict[str, dict] = {}
    for path, ifaces in objects.items():
        a = ifaces.get("org.bluez.Adapter1")
        if a is None:
            continue
        bd = str(a.get("Address", "")).upper()
        cfg = adapters_cfg.get(bd, {})
        adapters[str(path)] = {
            "hci": str(path).rsplit("/", 1)[-1],
            "bd": bd,
            "role": cfg.get("role", "unconfigured"),
            "alias": str(a.get("Alias", "")),
            "powered": bool(a.get("Powered", False)),
            "discoverable": bool(a.get("Discoverable", False)),
            "pairable": bool(a.get("Pairable", False)),
            "cls": f"0x{int(a.get('Class', 0)):06x}",
            "cls_wanted": f"0x{cfg['cls']:06x}" if cfg.get("cls") else None,
            "cls_ok": class_matches(int(a.get("Class", 0)), cfg.get("cls")),
            "devices": [],
        }
    for path, ifaces in objects.items():
        d = ifaces.get("org.bluez.Device1")
        if d is None:
            continue
        ad_path, mac = split_device_path(str(path))
        if ad_path not in adapters:
            continue
        if not (d.get("Paired") or d.get("Trusted") or d.get("Connected")):
            continue
        adapters[ad_path]["devices"].append({
            "mac": mac,
            "name": str(d.get("Alias") or d.get("Name") or ""),
            "paired": bool(d.get("Paired", False)),
            "trusted": bool(d.get("Trusted", False)),
            "connected": bool(d.get("Connected", False)),
        })
    return sorted(adapters.values(), key=lambda x: x["hci"])


def read_status(events_n: int = 30) -> dict:
    """What `--status` prints: state file + service state + window + recent events."""
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {"running": False}
    try:
        active = subprocess.run(["systemctl", "is-active", SERVICE], capture_output=True,
                                text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        active = "unknown"
    events = []
    try:
        with open(EVENTS_FILE, encoding="utf-8") as f:
            lines = f.readlines()[-events_n:]
        events = [json.loads(ln) for ln in lines if ln.strip().startswith("{")]
    except (OSError, ValueError):
        pass
    return {**state, "service": active, "window_s": round(window_remaining(), 1),
            "events": events, "now": round(time.time(), 3)}


# ── runtime ──────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _write_json_atomic(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _build_agent_class(dbus, dbus_service):
    class Rejected(dbus.DBusException):
        _dbus_error_name = "org.bluez.Error.Rejected"

    class Agent(dbus_service.Object):
        def __init__(self, bus, path, owner):
            super().__init__(bus, path)
            self._owner = owner

        def _confirm(self, method, device, detail):
            ok, reason = self._owner.decide(device)
            self._owner.event(method, device, detail, "yes" if ok else "rejected", reason)
            if not ok:
                raise Rejected(reason)

        @dbus_service.method("org.bluez.Agent1", in_signature="", out_signature="")
        def Release(self):
            self._owner.event("Release")

        @dbus_service.method("org.bluez.Agent1", in_signature="o", out_signature="")
        def RequestAuthorization(self, device):
            self._confirm("RequestAuthorization", str(device), "")

        @dbus_service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
        def RequestConfirmation(self, device, passkey):
            self._confirm("RequestConfirmation", str(device), f"passkey={int(passkey):06d}")
            self._owner.trust(str(device))

        @dbus_service.method("org.bluez.Agent1", in_signature="os", out_signature="")
        def AuthorizeService(self, device, uuid):
            u = str(uuid).lower()
            if u in AUDIO_UUIDS:
                self._owner.event("AuthorizeService", str(device), u, "yes", "audio service")
                return
            self._confirm("AuthorizeService", str(device), u)

        @dbus_service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
        def RequestPasskey(self, device):
            self._owner.event("RequestPasskey", str(device), "", "000000", "fixed")
            return dbus.UInt32(0)

        @dbus_service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
        def RequestPinCode(self, device):
            self._owner.event("RequestPinCode", str(device), "", "0000", "fixed")
            return "0000"

        @dbus_service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
        def DisplayPasskey(self, device, passkey, entered):
            self._owner.event("DisplayPasskey", str(device),
                              f"passkey={int(passkey):06d} entered={int(entered)}")

        @dbus_service.method("org.bluez.Agent1", in_signature="os", out_signature="")
        def DisplayPinCode(self, device, pincode):
            self._owner.event("DisplayPinCode", str(device), f"pin={pincode}")

        @dbus_service.method("org.bluez.Agent1", in_signature="", out_signature="")
        def Cancel(self):
            self._owner.event("Cancel", answer="-", reason="cancelled by BlueZ")

    return Agent


class AgentService:
    def __init__(self, adapters: list[dict], mode: str):
        self.cfg = {a["bd"]: a for a in adapters}
        self.mode = mode
        self.bus = None
        self.events: list[dict] = []
        self.count = 0
        self.started = time.time()

    # -- D-Bus helpers --------------------------------------------------------

    def _props(self, path):
        import dbus
        return dbus.Interface(self.bus.get_object("org.bluez", path), "org.freedesktop.DBus.Properties")

    def _objects(self) -> dict:
        import dbus
        om = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        return om.GetManagedObjects()

    def adapter_bd(self, adapter_path: str) -> str:
        try:
            return str(self._props(adapter_path).Get("org.bluez.Adapter1", "Address")).upper()
        except Exception:  # noqa: BLE001
            return ""

    def device_prop(self, path: str, name: str, default=None):
        try:
            return self._props(path).Get("org.bluez.Device1", name)
        except Exception:  # noqa: BLE001
            return default

    # -- policy ---------------------------------------------------------------

    def decide(self, device_path: str) -> tuple[bool, str]:
        ad_path, _ = split_device_path(device_path)
        known = self.adapter_bd(ad_path) in self.cfg
        paired = bool(self.device_prop(device_path, "Paired", False))
        return decide_confirm(self.mode, window_remaining(), paired, known)

    def trust(self, device_path: str) -> None:
        import dbus
        try:
            self._props(device_path).Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
        except Exception as e:  # noqa: BLE001
            _log(f"Trusted failed for {device_path}: {e}")

    def event(self, method, device="", detail="", answer="", reason=""):
        ad_path, mac = split_device_path(device)
        bd = self.adapter_bd(ad_path) if ad_path else ""
        self.count += 1
        ev = {
            "id": self.count,
            "ts": round(time.time(), 3),
            "method": method,
            "hci": ad_path.rsplit("/", 1)[-1] if ad_path else "",
            "adapter": bd,
            "role": self.cfg.get(bd, {}).get("role", "unconfigured" if bd else ""),
            "device": mac,
            "name": str(self.device_prop(device, "Alias", "") or "") if mac else "",
            "detail": detail,
            "answer": answer,
            "reason": reason,
        }
        self.events = (self.events + [ev])[-EVENTS_KEEP:]
        try:
            os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
            with open(EVENTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except OSError as e:
            _log(f"events file: {e}")
        _log(f"{method} {ev['hci']} {mac} {detail} -> {answer or '-'} ({reason})")
        self.write_state()

    # -- adapter setup --------------------------------------------------------

    def apply_class(self, adapter_path: str, cfg: dict) -> None:
        if not cfg.get("cls"):
            return
        hci = adapter_path.rsplit("/", 1)[-1]
        p = subprocess.run(["hciconfig", hci, "class", f"0x{cfg['cls']:06x}"],
                           capture_output=True, text=True, timeout=5)
        if p.returncode != 0:
            _log(f"{hci}: class failed: {(p.stderr or p.stdout).strip()}")

    def apply_adapter(self, adapter_path: str) -> None:
        import dbus
        bd = self.adapter_bd(adapter_path)
        cfg = self.cfg.get(bd)
        if not cfg:
            return
        p = self._props(adapter_path)
        try:
            if cfg["alias"]:
                p.Set("org.bluez.Adapter1", "Alias", dbus.String(cfg["alias"]))
            p.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
            p.Set("org.bluez.Adapter1", "PairableTimeout", dbus.UInt32(0))
            p.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
            p.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
            p.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
        except Exception as e:  # noqa: BLE001
            _log(f"{adapter_path}: settings failed: {e}")
        self.apply_class(adapter_path, cfg)
        _log(f"{adapter_path} {bd} role={cfg['role']} alias={cfg['alias']!r} discoverable, pairable")

    def write_state(self) -> None:
        try:
            adapters = summarize_objects(self._objects(), self.cfg)
        except Exception as e:  # noqa: BLE001
            adapters = [{"error": str(e)}]
        try:
            _write_json_atomic(STATE_FILE, {
                "running": True, "pid": os.getpid(), "started_ts": self.started,
                "ts": round(time.time(), 3), "mode": self.mode, "capability": CAPABILITY,
                "configured": [{k: v for k, v in a.items() if k != "cls"} for a in self.cfg.values()],
                "adapters": adapters, "event_count": self.count,
            })
        except OSError as e:
            _log(f"state file: {e}")

    # -- signals --------------------------------------------------------------

    def _on_added(self, path, ifaces):
        if "org.bluez.Adapter1" in ifaces:
            self.apply_adapter(str(path))
            self.write_state()

    def _on_props(self, interface, changed, invalidated, path=None):
        path = str(path or "")
        if interface == "org.bluez.Adapter1" and bool(changed.get("Powered", False)):
            cfg = self.cfg.get(self.adapter_bd(path))
            if cfg:
                self.apply_class(path, cfg)
        elif interface == "org.bluez.Device1":
            if bool(changed.get("Paired", False)):
                self.event("Paired", path, "", "-", "reported by BlueZ")
                self.trust(path)
            elif "Connected" in changed:
                self.event("Connected", path, f"connected={bool(changed['Connected'])}", "-",
                           "reported by BlueZ")

    def run(self) -> None:
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib

        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        agent = _build_agent_class(dbus, dbus.service)(self.bus, AGENT_PATH, self)  # noqa: F841
        mgr = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1")
        try:
            mgr.RegisterAgent(AGENT_PATH, CAPABILITY)
        except dbus.DBusException as e:
            if "AlreadyExists" not in str(e):
                raise
        # An interactive `bluetoothctl` with `default-agent` takes this role over until it exits.
        mgr.RequestDefaultAgent(AGENT_PATH)
        _log(f"agent {AGENT_PATH} capability={CAPABILITY} rule={self.mode} adapters={list(self.cfg)}")

        self.bus.add_signal_receiver(self._on_added, dbus_interface="org.freedesktop.DBus.ObjectManager",
                                     signal_name="InterfacesAdded", bus_name="org.bluez")
        self.bus.add_signal_receiver(self._on_props, dbus_interface="org.freedesktop.DBus.Properties",
                                     signal_name="PropertiesChanged", path_keyword="path",
                                     bus_name="org.bluez")
        for path, ifaces in self._objects().items():
            if "org.bluez.Adapter1" in ifaces:
                self.apply_adapter(str(path))
        self.write_state()
        GLib.timeout_add_seconds(5, lambda: (self.write_state(), True)[1])
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                mgr.UnregisterAgent(AGENT_PATH)
            except dbus.DBusException:
                pass
            _write_json_atomic(STATE_FILE, {"running": False, "ts": round(time.time(), 3)})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", action="append", default=[], metavar="BD=ROLE[:ALIAS]",
                    help=f"configured adapter; ROLE in {', '.join(CLASS_BY_ROLE)}, none")
    ap.add_argument("--mode", default=os.environ.get("BT_PAIR_CONFIRM", "always"),
                    choices=("always", "window", "never"))
    ap.add_argument("--open-window", type=int, metavar="SECONDS")
    ap.add_argument("--status", action="store_true", help="print JSON status and exit")
    ap.add_argument("-f", "--foreground", action="store_true", help="accepted for unit-file symmetry")
    args = ap.parse_args(argv)

    if args.status:
        print(json.dumps(read_status()))
        return 0
    if args.open_window is not None:
        until = open_window(args.open_window)
        print(json.dumps({"ok": True, "until": until, "window_s": args.open_window}))
        return 0
    AgentService([parse_adapter_spec(s) for s in args.adapter], args.mode).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
