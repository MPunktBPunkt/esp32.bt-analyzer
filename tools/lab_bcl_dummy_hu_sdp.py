#!/usr/bin/env python3
"""B0.6 — Dummy-HU advertises an RFCOMM/SPP service; phone-side SDP must see it.

Registers a Serial Port profile via BlueZ ProfileManager1 (modern SDP path;
sdptool add needs bluetoothd --compat and fails on stock .108).

Topology (lab, no BMW):
  .87 / hci1  = HU-dummy (advertises "BMW Connected" SPP ch.5)
  .131 / hci2 = phone side (sdptool browse + bcl_sdp_probe verdict)

Epistemic: TEST only — proves our SDP/RFCOMM messkette, not HU wire FACT.

Run on .108 (needs python3-gi + python3-dbus):
  python3 tools/lab_bcl_dummy_hu_sdp.py
  python3 tools/lab_bcl_dummy_hu_sdp.py --seconds 40 --channel 5
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_sdp_probe import classify, parse_sdptool, report, verdict  # noqa: E402

DEFAULT_SSH = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")
EVIDENCE = ROOT / "docs" / "evidence"

HU_DUMMY = {
    "ip": "192.168.178.87",
    "hci": "hci1",
    "bd": "C8:C9:A3:CB:37:96",
    "role": "hu_dummy",
}
PHONE = {
    "ip": "192.168.178.131",
    "hci": "hci2",
    "bd": "C8:C9:A3:CB:7B:0A",
    "role": "phone_side",
}

SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"
SERVICE_NAME = "BMW Connected"
PROFILE_PATH = "/org/bluez/bcl_dummy_hu"


_REGISTER_SCRIPT = r'''
import dbus, dbus.service, dbus.mainloop.glib, sys, time
from gi.repository import GLib

CHANNEL = int(sys.argv[1])
NAME = sys.argv[2]
UUID = sys.argv[3]
PATH = sys.argv[4]
HOLD = float(sys.argv[5])
READY = sys.argv[6]

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class Profile(dbus.service.Object):
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, fd, properties):
        pass

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        pass

bus = dbus.SystemBus()
# Own a unique name so the profile object is reachable.
name = "org.btanalyzer.BclDummyHu"
try:
    bus.request_name(name)
except Exception as e:
    print("NAME_WARN", e, flush=True)

profile = Profile(bus, PATH)
pm = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
opts = {
    "Name": NAME,
    "Service": NAME,
    "Role": "server",
    "Channel": dbus.UInt16(CHANNEL),
    "RequireAuthentication": False,
    "RequireAuthorization": False,
    "AutoConnect": False,
}
try:
    pm.UnregisterProfile(PATH)
except Exception:
    pass
pm.RegisterProfile(PATH, UUID, opts)
open(READY, "w").write("registered\n")
print("REGISTERED", NAME, "ch", CHANNEL, flush=True)
loop = GLib.MainLoop()
def stop(*_a):
    try:
        pm.UnregisterProfile(PATH)
    except Exception:
        pass
    loop.quit()
GLib.timeout_add_seconds(max(1, int(HOLD)), stop)
signal = __import__("signal")
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
loop.run()
print("DONE", flush=True)
'''


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ssh(remote: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    """Run one remote command string as a single SSH argv (OpenSSH-safe)."""
    import shlex

    return subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=accept-new",
            DEFAULT_SSH,
            f"bash -lc {shlex.quote(remote)}",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def prep_adapters(channel: int) -> dict:
    steps = {}
    for side, alias in ((HU_DUMMY, "BCL-HU-Dummy"), (PHONE, "BCL-Phone")):
        script = (
            f"bluetoothctl select {side['bd']}; "
            f"bluetoothctl power on; "
            f"bluetoothctl pairable on; "
            f"bluetoothctl discoverable on; "
            f"bluetoothctl system-alias {alias}; "
            f"hciconfig {side['hci']} piscan; "
            f"hciconfig {side['hci']} sspmode 1"
        )
        p = ssh(script, timeout=30)
        steps[side["hci"]] = {"ok": p.returncode == 0, "stderr": (p.stderr or "")[-300:]}
    return steps


def start_profile(channel: int, hold_s: float) -> tuple[str, Path]:
    """Upload and start ProfileManager registrar on .108; return ready-file path marker."""
    import shlex

    remote_py = "/tmp/bcl_dummy_hu_profile.py"
    ready = f"/tmp/bcl_dummy_hu_ready_{os.getpid()}"
    local = Path("/tmp/bcl_dummy_hu_profile.py")
    local.write_text(_REGISTER_SCRIPT)
    scp = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=accept-new",
            str(local),
            f"{DEFAULT_SSH}:{remote_py}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if scp.returncode != 0:
        raise RuntimeError(f"scp failed: {scp.stderr}")

    ssh(f"rm -f {ready}; pkill -f bcl_dummy_hu_profile.py || true", timeout=15)
    # Args after script: channel name uuid path hold ready — name may contain spaces.
    start = (
        f"nohup python3 {remote_py} {channel} {shlex.quote(SERVICE_NAME)} "
        f"{SPP_UUID} {PROFILE_PATH} {hold_s} {ready} "
        f">/tmp/bcl_dummy_hu_profile.log 2>&1 & echo $!"
    )
    p = ssh(start, timeout=15)
    pid = (p.stdout or "").strip().splitlines()[-1] if p.stdout else "?"
    deadline = time.time() + 15
    while time.time() < deadline:
        chk = ssh(f"test -f {ready} && cat {ready}", timeout=10)
        if chk.returncode == 0 and "registered" in (chk.stdout or ""):
            return pid, Path(ready)
        time.sleep(0.4)
    log = ssh("tail -40 /tmp/bcl_dummy_hu_profile.log", timeout=10)
    raise RuntimeError(f"profile not ready: {(log.stdout or '') + (log.stderr or '')}")


def prepare_link() -> dict:
    """Power both controllers, drop stale ACLs, brief inquiry.

    sdptool browse opens its own short ACL; half-open leftover links cause
    'Operation already in progress' / 'Invalid argument'. Clean slate matters more
    than a pre-held hcitool connection.
    """
    script = f"""
set +e
for bd in {PHONE['bd']} {HU_DUMMY['bd']}; do
  bluetoothctl select "$bd" >/dev/null
  bluetoothctl power off >/dev/null
done
sleep 2
for bd in {PHONE['bd']} {HU_DUMMY['bd']}; do
  bluetoothctl select "$bd" >/dev/null
  bluetoothctl power on >/dev/null
done
sleep 1
hciconfig {PHONE['hci']} up; hciconfig {PHONE['hci']} piscan; hciconfig {PHONE['hci']} sspmode 1
hciconfig {HU_DUMMY['hci']} up; hciconfig {HU_DUMMY['hci']} piscan; hciconfig {HU_DUMMY['hci']} sspmode 1
# drop any leftover ACLs on both sides
for h in {PHONE['hci']} {HU_DUMMY['hci']}; do
  hcitool -i $h con 2>/dev/null | while read -r _ _ addr _; do
    case "$addr" in *:*) hcitool -i $h dc "$addr" 2>/dev/null;; esac
  done
done
sleep 1
timeout 10 hcitool -i {PHONE['hci']} inq
echo CONS_PHONE; hcitool -i {PHONE['hci']} con
echo CONS_HU; hcitool -i {HU_DUMMY['hci']} con
echo PREP_DONE=1
"""
    p = ssh(script, timeout=60)
    out = (p.stdout or "") + (p.stderr or "")
    return {
        # Inquiry may miss once after power-cycle; prep itself is enough for sdptool.
        "ok": "PREP_DONE=1" in out,
        "seen_hu_in_inq": HU_DUMMY["bd"].lower() in out.lower(),
        "raw": out[-2000:],
    }


def probe_sdp(use_records: bool) -> dict:
    # `records` often hangs on virtual HCI; `browse` is enough for SPP/channel.
    modes = ["records", "browse"] if use_records else ["browse"]
    text = ""
    mode_used = modes[0]
    rc = 1
    for mode in modes:
        mode_used = mode
        cmd = f"timeout 35 sdptool -i {PHONE['hci']} {mode} {HU_DUMMY['bd']}"
        try:
            p = ssh(cmd, timeout=50)
        except subprocess.TimeoutExpired as exc:
            text += f"\n__timeout__ {mode}: {exc}\n"
            continue
        text = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
        recs = parse_sdptool(text)
        if recs:
            break
    else:
        recs = parse_sdptool(text)
    info = ssh(
        f"bluetoothctl select {PHONE['bd']}; bluetoothctl info {HU_DUMMY['bd']}",
        timeout=20,
    )
    info_text = (info.stdout or "") + (info.stderr or "")
    return {
        "source": f"sdptool {mode_used}",
        "returncode": rc,
        "raw": text,
        "records": recs,
        "verdict": verdict(recs),
        "bluetoothctl_info_tail": info_text[-800:],
    }


def stop_profile() -> None:
    ssh("pkill -f bcl_dummy_hu_profile.py || true; rm -f /tmp/bcl_dummy_hu_ready_*", timeout=15)


def write_evidence(result: dict) -> tuple[Path, Path]:
    stamp = result["utc"]
    base = f"LAB_BCL_DUMMY_HU_SDP_{stamp}"
    js = EVIDENCE / f"{base}.json"
    md = EVIDENCE / f"{base}.md"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(result, indent=2) + "\n")

    recs = result.get("sdp", {}).get("records") or []
    lines = [
        f"# LAB BCL Dummy-HU SDP — {'PASS' if result.get('ok') else 'FAIL'}",
        "",
        f"**UTC:** {stamp} · channel {result.get('channel')} · service `{SERVICE_NAME}`",
        "**claim:** ProfileManager SPP visible via phone-side sdptool — TEST, not BMW FACT",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| overall | {'PASS' if result.get('ok') else 'FAIL'} |",
        f"| profile registered | {result.get('profile_ok')} |",
        f"| link prep | {result.get('link', {}).get('ok')} |",
        f"| SDP verdict | `{result.get('sdp', {}).get('verdict')}` |",
        f"| records | {len(recs)} |",
        "",
        "## Records",
        "",
    ]
    for r in recs:
        tags = classify(r)
        lines.append(
            f"- {r.get('name') or '-'} classes={','.join(r.get('classes') or [])} "
            f"rfcomm={r.get('rfcomm')} tags={tags}"
        )
    lines += [
        "",
        "## Epistemic",
        "",
        "```text",
        "YES:  Dummy-HU can advertise SPP/RFCOMM over BlueZ SDP",
        "YES:  bcl_sdp_probe verdict path works against a known service",
        "NO:   what the real BMW HU offers",
        "```",
        "",
    ]
    md.write_text("\n".join(lines))
    return js, md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=35.0, help="how long to hold the profile")
    ap.add_argument("--channel", type=int, default=5)
    ap.add_argument("--records", action="store_true")
    ap.add_argument("--no-evidence", action="store_true")
    args = ap.parse_args()

    utc = utc_stamp()
    result: dict = {
        "utc": utc,
        "channel": args.channel,
        "service_name": SERVICE_NAME,
        "spp_uuid": SPP_UUID,
        "hu_dummy": HU_DUMMY,
        "phone_side": PHONE,
        "ok": False,
        "epistemic": {
            "source": "synthetic",
            "evidence_level": "TEST",
            "direct_observation": False,
            "claim": "Dummy-HU SDP advertisement; not BMW wire FACT",
        },
    }

    try:
        result["prep"] = prep_adapters(args.channel)
        # Clean radios first, then register — profile must stay up across power cycle.
        result["link"] = prepare_link()
        pid, ready = start_profile(args.channel, args.seconds + 25)
        result["profile_ok"] = True
        result["profile_pid"] = pid
        time.sleep(1.0)
        sdp = probe_sdp(args.records)
        result["sdp"] = {
            "source": sdp["source"],
            "returncode": sdp["returncode"],
            "verdict": sdp["verdict"],
            "records": sdp["records"],
            "raw_tail": sdp["raw"][-2000:],
            "bluetoothctl_info_tail": sdp["bluetoothctl_info_tail"],
        }
        # PASS if probe finds SPP / name hint (CANDIDATE*)
        v = sdp["verdict"]
        result["ok"] = v.startswith("CANDIDATE")
        # pretty print like bcl_sdp_probe
        report("hu_dummy", sdp["source"], sdp["records"])
    except Exception as exc:  # noqa: BLE001
        result["error"] = repr(exc)
        result["ok"] = False
    finally:
        stop_profile()

    paths = None
    if not args.no_evidence:
        paths = write_evidence(result)

    print(json.dumps({k: result[k] for k in result if k != "prep"}, indent=2))
    if paths:
        print(f"\nevidence: {paths[0]}\n          {paths[1]}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
