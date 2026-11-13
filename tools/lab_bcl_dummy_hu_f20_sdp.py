#!/usr/bin/env python3
"""B0.6b — advertise an F20-shaped Dummy-HU SDP on .108 (Lab TEST, not BMW FACT).

Mirrors the measured NBT Evo RFCOMM map (FIELD_B1):
  ch 5  = vendor UUID 00000000-deca-fade-deca-deafdecacaff  ("SPP Server 0")
  ch 6–10 = five SPP 0x1101 records ("SPP Server 1–5")

BlueZ ProfileManager1 normally allows **one** registration per UUID, so ch7–10
may fail to register; the script records that limitation. ch5 + ch6 are the
required mirror for Android createRfcommSocketToServiceRecord(0x1101) → first hit.

Topology (both controllers on .108):
  HU-dummy  = C8:C9:A3:CB:7B:0A  (BT-Analyzer-Car)
  phone     = C8:C9:A3:CB:37:96  (BT-Analyzer-Phone)

  python3 tools/lab_bcl_dummy_hu_f20_sdp.py
  python3 tools/lab_bcl_dummy_hu_f20_sdp.py --hold 90 --browse-timeout 40
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_sdp_probe import parse_sdptool  # noqa: E402

DEFAULT_SSH = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")
EVIDENCE = ROOT / "docs" / "evidence"

HU = {"bd": "C8:C9:A3:CB:7B:0A", "role": "hu_dummy", "alias": "BCL-HU-Dummy"}
PHONE = {"bd": "C8:C9:A3:CB:37:96", "role": "phone", "alias": "BCL-Phone"}

SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"
DECA_UUID = "00000000-deca-fade-deca-deafdecacaff"

# (channel, name, uuid) — F20 order: vendor first as ch5, then 0x1101 as 6..10
F20_RECORDS = [
    (5, "SPP Server 0", DECA_UUID),
    (6, "SPP Server 1", SPP_UUID),
    (7, "SPP Server 2", SPP_UUID),
    (8, "SPP Server 3", SPP_UUID),
    (9, "SPP Server 4", SPP_UUID),
    (10, "SPP Server 5", SPP_UUID),
]

_REGISTER_SCRIPT = r'''
import dbus, dbus.service, dbus.mainloop.glib, json, sys, time, signal
from gi.repository import GLib

HOLD = float(sys.argv[1])
READY = sys.argv[2]
LOG = sys.argv[3]
RECORDS = json.load(open(sys.argv[4]))  # list of [channel, name, uuid]

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
try:
    bus.request_name("org.btanalyzer.F20SdpMirror")
except Exception as e:
    print("NAME_WARN", e, flush=True)

pm = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
results = []
objs = []

class Profile(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        pass
    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, fd, properties):
        # Observe-only: keep fd open, log, never TX (lab phone differential).
        import os, json as _json
        raw_fd = fd.take()
        peer = str(device)
        print("NEWCONN", peer, "fd", raw_fd, "props", dict(properties), flush=True)
        open(LOG, "a").write(_json.dumps({"event": "new_connection", "device": peer, "fd": raw_fd, "t": time.time()}) + "\n")
        def _on_read(f, cond):
            try:
                data = os.read(f, 4096) if cond & GLib.IO_IN else b""
            except OSError:
                data = b""
            if not data:
                print("EOF", peer, "fd", f, flush=True)
                open(LOG, "a").write(_json.dumps({"event": "eof", "device": peer, "fd": f, "t": time.time()}) + "\n")
                try:
                    os.close(f)
                except OSError:
                    pass
                return False
            hx = data[:64].hex()
            print("RX", peer, "n", len(data), "hex", hx, flush=True)
            open(LOG, "a").write(_json.dumps({"event": "rx", "device": peer, "fd": f, "n": len(data), "hex": hx, "t": time.time()}) + "\n")
            return True
        GLib.io_add_watch(raw_fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, _on_read)
    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        print("DISC_REQ", device, flush=True)
        open(LOG, "a").write(json.dumps({"event": "disconnect_req", "device": str(device), "t": time.time()}) + "\n")

for ch, name, uuid in RECORDS:
    path = f"/org/btanalyzer/f20_sdp/ch{ch}"
    try:
        pm.UnregisterProfile(path)
    except Exception:
        pass
    prof = Profile(bus, path)
    objs.append(prof)
    opts = {
        "Name": name,
        "Service": name,
        "Role": "server",
        "Channel": dbus.UInt16(int(ch)),
        "RequireAuthentication": False,
        "RequireAuthorization": False,
        "AutoConnect": False,
    }
    try:
        pm.RegisterProfile(path, uuid, opts)
        results.append({"channel": ch, "name": name, "uuid": uuid, "ok": True, "error": None})
        print("REGISTERED", name, "ch", ch, uuid, flush=True)
    except Exception as e:
        results.append({"channel": ch, "name": name, "uuid": uuid, "ok": False, "error": str(e)})
        print("FAIL", name, "ch", ch, e, flush=True)

open(READY, "w").write(json.dumps(results) + "\n")
open(LOG, "w").write(json.dumps(results, indent=2) + "\n")
loop = GLib.MainLoop()

def stop(*_a):
    for ch, name, uuid in RECORDS:
        path = f"/org/btanalyzer/f20_sdp/ch{ch}"
        try:
            pm.UnregisterProfile(path)
        except Exception:
            pass
    loop.quit()

GLib.timeout_add_seconds(max(1, int(HOLD)), stop)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
loop.run()
print("DONE", flush=True)
'''


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ssh(remote: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            "-o", "StrictHostKeyChecking=accept-new",
            DEFAULT_SSH,
            f"bash -lc {shlex.quote(remote)}",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def resolve_hci(bd: str) -> str | None:
    out = ssh("hciconfig -a", timeout=15).stdout or ""
    for block in re.split(r"\n(?=hci\d+:)", out):
        if bd.lower() in block.lower():
            return block.split(":", 1)[0].strip()
    return None


def prep_sides() -> dict:
    info = {}
    for side in (HU, PHONE):
        hci = resolve_hci(side["bd"])
        if not hci:
            info[side["role"]] = {"ok": False, "error": f"BD {side['bd']} not found"}
            continue
        feed = (
            f"{{ echo select {side['bd']}; echo power on; echo pairable on; "
            f"echo discoverable on; echo system-alias {shlex.quote(side['alias'])}; echo quit; }} "
            f"| bluetoothctl"
        )
        ssh(feed, timeout=30)
        p = ssh(f"hciconfig {hci} up; hciconfig {hci} piscan; hciconfig {hci} sspmode 1", timeout=15)
        info[side["role"]] = {
            "ok": p.returncode == 0,
            "hci": hci,
            "bd": side["bd"],
            "alias": side["alias"],
        }
    return info


def start_mirror(hold_s: float) -> tuple[str, list[dict]]:
    remote_py = "/tmp/bcl_f20_sdp_mirror.py"
    ready = f"/tmp/bcl_f20_sdp_ready_{os.getpid()}"
    log = "/tmp/bcl_f20_sdp_mirror.log"
    local = Path("/tmp/bcl_f20_sdp_mirror.py")
    local.write_text(_REGISTER_SCRIPT)
    scp = subprocess.run(
        [
            "scp",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            "-o", "StrictHostKeyChecking=accept-new",
            str(local),
            f"{DEFAULT_SSH}:{remote_py}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if scp.returncode != 0:
        raise RuntimeError(f"scp failed: {scp.stderr}")

    records_remote = "/tmp/bcl_f20_sdp_records.json"
    ssh(
        f"cat > {records_remote} <<'EOF'\n{json.dumps(F20_RECORDS)}\nEOF\n"
        f"rm -f {ready}; pkill -f bcl_f20_sdp_mirror.py || true",
        timeout=15,
    )
    start = (
        f"nohup python3 {remote_py} {hold_s} {ready} {log} {records_remote} "
        f">/tmp/bcl_f20_sdp_stdout.log 2>&1 & echo $!"
    )
    p = ssh(start, timeout=15)
    pid = (p.stdout or "").strip().splitlines()[-1] if p.stdout else "?"
    deadline = time.time() + 20
    while time.time() < deadline:
        chk = ssh(f"test -f {ready} && cat {ready}", timeout=10)
        if chk.returncode == 0 and (chk.stdout or "").strip().startswith("["):
            return pid, json.loads(chk.stdout)
        time.sleep(0.4)
    tail = ssh("tail -80 /tmp/bcl_f20_sdp_stdout.log; echo ---; cat /tmp/bcl_f20_sdp_mirror.log 2>/dev/null", timeout=10)
    raise RuntimeError(f"mirror not ready: {(tail.stdout or '') + (tail.stderr or '')}")


def browse_from_phone(phone_hci: str, hold_browse: float) -> dict:
    cmd = f"timeout {int(hold_browse)} sdptool -i {phone_hci} browse {HU['bd']}"
    try:
        p = ssh(cmd, timeout=hold_browse + 15)
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"timeout: {exc}", "records": [], "raw": ""}
    text = (p.stdout or "") + (p.stderr or "")
    recs = parse_sdptool(text)
    return {
        "ok": bool(recs),
        "returncode": p.returncode,
        "raw": text,
        "records": recs,
        "source": f"sdptool -i {phone_hci} browse {HU['bd']}",
    }


def stop_mirror() -> None:
    ssh("pkill -f bcl_f20_sdp_mirror.py || true; rm -f /tmp/bcl_f20_sdp_ready_*", timeout=15)


def summarize(reg: list[dict], browse: dict) -> dict:
    reg_ok = {r["channel"]: r for r in reg if r.get("ok")}
    reg_fail = [r for r in reg if not r.get("ok")]
    browsed_ch = sorted(
        {
            int(r.get("rfcomm") if r.get("rfcomm") is not None else r.get("rfcomm_channel"))
            for r in (browse.get("records") or [])
            if r.get("rfcomm") is not None or r.get("rfcomm_channel") is not None
        }
    )
    uuids = []
    for r in browse.get("records") or []:
        for c in r.get("classes") or []:
            uuids.append(str(c).lower())
        for k in (r.get("profiles") or {}):
            uuids.append(str(k).lower())
    has_deca = any("deca-fade" in u for u in uuids)
    has_spp = any("1101" in u or "serial port" in u or "spp" in u for u in uuids)
    # PASS: ch5+ch6 registered AND peer browse sees both RFCOMM channels
    ok = 5 in reg_ok and 6 in reg_ok and 5 in browsed_ch and 6 in browsed_ch
    return {
        "ok": ok,
        "registered_channels": sorted(reg_ok),
        "register_failures": reg_fail,
        "browsed_rfcomm_channels": browsed_ch,
        "browse_saw_ch5_deca": 5 in browsed_ch and has_deca,
        "browse_saw_ch6_spp": 6 in browsed_ch and has_spp,
        "browse_saw_deca_fade": has_deca,
        "browse_saw_spp_1101": has_spp,
        "bluez_multi_spp_limitation": any(
            r.get("channel") in (7, 8, 9, 10) and not r.get("ok") for r in reg
        ),
        "epistemic": "LAB_TEST — F20-shaped Dummy SDP; not BMW HU FACT",
    }


def write_evidence(result: dict) -> tuple[Path, Path]:
    stamp = result["utc"]
    base = f"LAB_F20_SDP_MIRROR_{stamp}"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    js = EVIDENCE / f"{base}.json"
    md = EVIDENCE / f"{base}.md"
    js.write_text(json.dumps(result, indent=2) + "\n")
    s = result["summary"]
    lines = [
        f"# LAB F20 SDP Mirror — {'PASS' if s.get('ok') else 'FAIL'}",
        "",
        f"**UTC:** {stamp}",
        "**claim:** BlueZ Dummy advertises F20-like ch5 `deca-fade` + ch6(+)|`0x1101` — **LAB_TEST**, not BMW FACT",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| overall | {'PASS' if s.get('ok') else 'FAIL'} |",
        f"| registered channels | {s.get('registered_channels')} |",
        f"| browsed RFCOMM channels | {s.get('browsed_rfcomm_channels')} |",
        f"| browse ch5 deca-fade | {s.get('browse_saw_ch5_deca')} |",
        f"| browse ch6 SPP 0x1101 | {s.get('browse_saw_ch6_spp')} |",
        f"| BlueZ multi-SPP limit hit (ch7–10) | {s.get('bluez_multi_spp_limitation')} |",
        "",
        "## Register attempts",
        "",
    ]
    for r in result.get("register") or []:
        mark = "OK" if r.get("ok") else f"FAIL ({r.get('error')})"
        lines.append(f"- ch {r['channel']} `{r['name']}` `{r['uuid']}` → {mark}")
    lines += [
        "",
        "## Epistemic",
        "",
        "```text",
        "YES:  lab can advertise vendor UUID + first 0x1101 (Android first-match path)",
        "MAYBE: ch7–10 identical 0x1101 — BlueZ ProfileManager often one-UUID-one-profile",
        "NO:   this is not F20 wire; State C / BCL still UNKNOWN",
        "```",
        "",
        f"Browse source: `{result.get('browse', {}).get('source')}`",
        "",
    ]
    md.write_text("\n".join(lines) + "\n")
    return js, md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hold", type=float, default=120.0, help="seconds to keep profiles registered")
    ap.add_argument("--browse-timeout", type=float, default=35.0)
    ap.add_argument("--keep", action="store_true", help="do not kill mirror after browse")
    args = ap.parse_args()

    utc = utc_stamp()
    prep = prep_sides()
    if not all(v.get("ok") for v in prep.values()):
        print("PREP_FAIL", json.dumps(prep, indent=2))
        return 2

    phone_hci = prep["phone"]["hci"]
    try:
        pid, reg = start_mirror(args.hold)
        print("REGISTER", json.dumps(reg, indent=2))
        # give SDP a moment to publish
        time.sleep(2)
        browse = browse_from_phone(phone_hci, args.browse_timeout)
        summary = summarize(reg, browse)
        result = {
            "gate": "LAB_F20_SDP_MIRROR",
            "utc": utc,
            "epistemic_status": "lab_test",
            "prep": prep,
            "register": reg,
            "register_pid": pid,
            "browse": {
                "ok": browse.get("ok"),
                "returncode": browse.get("returncode"),
                "source": browse.get("source"),
                "records": browse.get("records"),
                "raw_tail": (browse.get("raw") or "")[-2500:],
                "error": browse.get("error"),
            },
            "summary": summary,
            "ok": summary["ok"],
        }
        js, md = write_evidence(result)
        print("SUMMARY", json.dumps(summary, indent=2))
        print("EVIDENCE", js)
        print("EVIDENCE", md)
        return 0 if summary["ok"] else 1
    finally:
        if not args.keep:
            stop_mirror()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        stop_mirror()
        raise SystemExit(3)
